"""
Combine des pronostics de tous les matchs futurs en tickets multiples,
avec des plages de cotes ciblées et en évitant les répétitions d'équipes.

Critères :
- Matchs issus des Best Picks (probabilité >= 66%)
- Cote combinée :
  - Catégorie A : > 3.0 (général)
  - Catégorie B : 4.0 - 5.90
  - Catégorie C : 5.90 - 6.90
- Somme des probabilités individuelles >= 75%
- 2 à 5 matchs par ticket
- Nombre de tickets souhaité : 2 (A), 2 (B), 1 (C) (ajustable)
- Évite au maximum les doublons d'équipes entre tickets d'une même catégorie
"""
from itertools import combinations
from collections import defaultdict
from sqlalchemy.orm import Session
from sqlalchemy import func

from ..models import Prediction, Event, Match

# ── Paramètres ──
MIN_INDIVIDUAL_PROB = 66.0
MIN_COMBO_SIZE = 2
MAX_COMBO_SIZE = 5
MIN_PROB_SUM = 75.0

# Plages de cotes
PLAGE_A_MIN = 3.0      # >3
PLAGE_A_MAX = 6.9      # (borne supérieure pour toutes)
PLAGE_B_MIN = 4.0
PLAGE_B_MAX = 5.90
PLAGE_C_MIN = 5.90
PLAGE_C_MAX = 6.90

# Nombre de tickets souhaités par catégorie
TARGET_A = 2
TARGET_B = 2
TARGET_C = 1

def _eligible_predictions(db: Session) -> list[Prediction]:
    return (
        db.query(Prediction)
        .join(Event, Prediction.event_id == Event.id)
        .join(Match, Event.match_id == Match.id)
        .filter(Prediction.probability >= MIN_INDIVIDUAL_PROB)
        .filter(Match.kickoff_at >= func.now())
        .all()
    )


def compute_combo(selections: list[Prediction]) -> dict | None:
    total_odds = 1.0
    prob_sum = 0.0
    real_prob = 1.0
    for p in selections:
        odds = float(p.event.odds_value) if p.event.odds_value else None
        if not odds:
            return None
        total_odds *= odds
        prob_sum += float(p.probability)
        real_prob *= (float(p.probability) / 100.0)
    return {
        "total_odds": round(total_odds, 3),
        "probability_sum": round(prob_sum, 2),
        "real_combined_probability": round(real_prob * 100, 2),
    }


def _get_teams_set(selections):
    """Retourne l'ensemble des noms d'équipes impliquées dans une combinaison."""
    teams = set()
    for p in selections:
        match = p.event.match
        teams.add(match.home_team.name)
        teams.add(match.away_team.name)
    return teams


def _select_diverse_combos(candidates: list[dict], target_count: int, max_team_repeats: int = 1) -> list[dict]:
    """
    Sélectionne les meilleures combinaisons en évitant au maximum les chevauchements d'équipes.

    - candidates : liste de dictionnaires contenant 'selections', 'total_odds', 'probability_sum', 'real_combined_probability'
    - target_count : nombre souhaité
    - max_team_repeats : combien de fois une même équipe peut apparaître dans l'ensemble des tickets sélectionnés (1 = pas de répétition)
    """
    if not candidates:
        return []

    # Trier par probabilité réelle décroissante
    candidates_sorted = sorted(candidates, key=lambda c: c["real_combined_probability"], reverse=True)

    selected = []
    team_usage = defaultdict(int)  # compteur d'apparitions par équipe

    for cand in candidates_sorted:
        teams = _get_teams_set(cand["selections"])
        # Vérifier si toutes les équipes ont déjà atteint le quota max
        if any(team_usage[team] >= max_team_repeats for team in teams):
            continue
        selected.append(cand)
        for team in teams:
            team_usage[team] += 1
        if len(selected) >= target_count:
            break

    return selected


def generate_ticket_combos(db: Session) -> list[dict]:
    """Génère les tickets selon les plages de cotes et en évitant les doublons d'équipes."""
    predictions = _eligible_predictions(db)
    if len(predictions) < MIN_COMBO_SIZE:
        return []

    # Générer toutes les combinaisons valides (filtrage préliminaire : cote globale entre 3 et 6.9, prob sum >= 75)
    all_candidates = []
    for size in range(MIN_COMBO_SIZE, min(MAX_COMBO_SIZE, len(predictions)) + 1):
        for combo in combinations(predictions, size):
            match_ids = {p.event.match_id for p in combo}
            if len(match_ids) != size:
                continue
            metrics = compute_combo(list(combo))
            if not metrics:
                continue
            total_odds = metrics["total_odds"]
            prob_sum = metrics["probability_sum"]
            if not (3.0 <= total_odds <= 6.9 and prob_sum >= MIN_PROB_SUM):
                continue
            all_candidates.append({
                "selections": combo,
                "total_odds": total_odds,
                "probability_sum": prob_sum,
                "real_combined_probability": metrics["real_combined_probability"],
            })

    # Classer en catégories
    cat_a = [c for c in all_candidates if c["total_odds"] > PLAGE_A_MIN]
    cat_b = [c for c in all_candidates if PLAGE_B_MIN <= c["total_odds"] <= PLAGE_B_MAX]
    cat_c = [c for c in all_candidates if PLAGE_C_MIN < c["total_odds"] <= PLAGE_C_MAX]

    # Sélectionner les meilleurs tickets par catégorie avec diversité d'équipes
    selected_a = _select_diverse_combos(cat_a, TARGET_A, max_team_repeats=2)
    selected_b = _select_diverse_combos(cat_b, TARGET_B, max_team_repeats=2)
    selected_c = _select_diverse_combos(cat_c, TARGET_C, max_team_repeats=1)

    # Fusionner les résultats (on peut aussi les trier globalement ou garder l'ordre)
    final = selected_a + selected_b + selected_c

    # Mettre en forme la sortie comme attendue par le front-end
    result = []
    for cand in final:
        selections = []
        for p in cand["selections"]:
            event = p.event
            match = event.match
            selections.append({
                "event_id": event.id,
                "match": f"{match.home_team.name} vs {match.away_team.name}",
                "competition": match.competition.name if match.competition else None,
                "kickoff_at": match.kickoff_at.isoformat(),
                "event": event.label,
                "probability": float(p.probability),
                "odds": float(event.odds_value),
            })
        dates = sorted({p.event.match.kickoff_at.date().isoformat() for p in cand["selections"]})
        result.append({
            "selections": selections,
            "total_odds": cand["total_odds"],
            "probability_sum": cand["probability_sum"],
            "real_combined_probability": cand["real_combined_probability"],
            "dates": dates,
        })

    return result
