"""
Détermine si chaque sélection d'un pari est gagnée ou perdue en comparant
au résultat réel du match. Gère les types : "resultat", "buts", "double_chance".

Le règlement utilise le LABEL INSTANTANÉ stocké dans BetSelection
(celui que l'utilisateur a vu au moment du clic), pas le label actuel
de l'Event en DB — cela garantit la cohérence.
"""
import re
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..models import Bet, BetSelection, Event, Match, Notification

BUTS_RE = re.compile(r"([+-]?)\s*([\d]+(?:[.,]\d+)?)", re.IGNORECASE)


def _parse_goals_line(label: str) -> tuple[str, float] | None:
    """Retourne ('over'|'under', line) ou None."""
    m = BUTS_RE.search(label)
    if not m:
        return None
    sign = m.group(1)
    try:
        line = float(m.group(2).replace(",", "."))
    except ValueError:
        return None
    if sign == "+" or label.strip().startswith("+"):
        return ("over", line)
    if sign == "-" or label.strip().startswith("-"):
        return ("under", line)
    return None


def _evaluate_resultat(label: str, home: int, away: int) -> str | None:
    """Évalue un pari 1/X/2 simple."""
    if label.startswith("1"):
        return "gagne" if home > away else "perdu"
    if label.startswith("X"):
        return "gagne" if home == away else "perdu"
    if label.startswith("2"):
        return "gagne" if away > home else "perdu"
    return None


def _evaluate_double_chance(label: str, home: int, away: int) -> str | None:
    """
    Évalue un pari double chance :
      - 1X : gagné si victoire domicile OU match nul
      - X2 : gagné si match nul OU victoire extérieur
      - 12 : gagné si victoire domicile OU victoire extérieur
    """
    up = label.upper()
    # Détection insensible à la casse/espaces
    if "1X" in up:
        return "gagne" if home >= away else "perdu"
    if "X2" in up:
        return "gagne" if away >= home else "perdu"
    if "12" in up:
        return "gagne" if home != away else "perdu"
    return None


def _evaluate_selection(selection: BetSelection) -> str | None:
    event: Event = selection.event
    if not event or not event.match:
        return None
    match: Match = event.match
    if match.status != "finished" or match.home_score is None or match.away_score is None:
        return None

    home, away = match.home_score, match.away_score

    # Le label instantané prime (celui vu par l'utilisateur au moment du clic)
    label = selection.event_label or event.label
    etype = selection.event_type or event.type

    if etype == "double_chance":
        return _evaluate_double_chance(label, home, away)

    if etype == "resultat":
        return _evaluate_resultat(label, home, away)

    if etype == "buts":
        total_goals = home + away
        parsed = _parse_goals_line(label)
        if not parsed:
            return None
        direction, line = parsed
        if direction == "over":
            return "gagne" if total_goals > line else "perdu"
        if direction == "under":
            return "gagne" if total_goals < line else "perdu"

    return None


def settle_all_bets(db: Session) -> dict:
    bets = db.query(Bet).filter(Bet.status == "en_cours").all()
    settled, notified = 0, 0

    for bet in bets:
        results = []
        for selection in bet.selections:
            if selection.result is None:
                outcome = _evaluate_selection(selection)
                if outcome:
                    selection.result = outcome
                    if outcome == "gagne":
                        match = selection.event.match
                        db.add(Notification(
                            user_id=bet.user_id,
                            bet_id=bet.id,
                            message=(
                                f"✅ Gagné : {match.home_team.name} vs "
                                f"{match.away_team.name} — "
                                f"{selection.event_label or selection.event.label}"
                            ),
                        ))
                        notified += 1
            results.append(selection.result)

        if results and all(r is not None for r in results):
            final_status = "gagne" if all(r == "gagne" for r in results) else "perdu"
            bet.status = final_status
            bet.settled_at = func.now()

            emoji = "🎉" if final_status == "gagne" else "😔"
            label = "Pari gagné" if final_status == "gagne" else "Pari perdu"
            db.add(Notification(
                user_id=bet.user_id,
                bet_id=bet.id,
                message=(
                    f"{emoji} {label} — cote totale {float(bet.total_odds):.2f} "
                    f"({len(bet.selections)} sélections)"
                ),
            ))
            settled += 1
            notified += 1

    db.commit()
    return {
        "bets_settled": settled,
        "notifications_created": notified,
        "bets_checked": len(bets),
    }
