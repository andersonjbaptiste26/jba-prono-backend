"""
Détermine si chaque sélection d'un pari est gagnée ou perdue, en comparant
au résultat réel du match (nécessite que /admin/sync-results ait tourné
avant). Crée une notification à chaque événement gagné, et une autre
quand le pari combiné entier est définitivement gagné ou perdu.
"""
from sqlalchemy.orm import Session

from ..models import Bet, BetSelection, Event, Match, Notification


def _evaluate_selection(selection: BetSelection) -> str | None:
    """Retourne 'gagne', 'perdu', ou None si le match n'est pas terminé."""
    event = selection.event
    match = event.match
    if match.status != "finished" or match.home_score is None or match.away_score is None:
        return None

    home, away = match.home_score, match.away_score

    if event.type == "resultat":
        if event.label.startswith("1"):
            return "gagne" if home > away else "perdu"
        if event.label.startswith("X"):
            return "gagne" if home == away else "perdu"
        if event.label.startswith("2"):
            return "gagne" if away > home else "perdu"

    if event.type == "buts":
        total_goals = home + away
        try:
            line = float(event.label.replace("+", "").replace("-", "").replace(" buts", ""))
        except ValueError:
            return None
        if event.label.startswith("+"):
            return "gagne" if total_goals > line else "perdu"
        if event.label.startswith("-"):
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
                            message=f"✅ Gagné : {match.home_team.name} vs {match.away_team.name} — {selection.event.label}",
                        ))
                        notified += 1
            results.append(selection.result)

        if all(r is not None for r in results):
            final_status = "gagne" if all(r == "gagne" for r in results) else "perdu"
            bet.status = final_status
            from sqlalchemy import func
            bet.settled_at = func.now()

            emoji = "🎉" if final_status == "gagne" else "😔"
            label = "Pari gagné" if final_status == "gagne" else "Pari perdu"
            db.add(Notification(
                user_id=bet.user_id,
                bet_id=bet.id,
                message=f"{emoji} {label} — cote totale {float(bet.total_odds):.2f} ({len(bet.selections)} sélections)",
            ))
            settled += 1
            notified += 1

    db.commit()
    return {"bets_settled": settled, "notifications_created": notified, "bets_checked": len(bets)}
