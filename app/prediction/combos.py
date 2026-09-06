"""
Combine des pronostics (Best Picks uniquement) en tickets multiples,
sans restriction de jours consécutifs.
Critères :
- cote combinée entre 3 et 6
- somme des probabilités individuelles >= 75%
- 2 à 4 matchs par ticket
- matchs futurs uniquement

Affiche la VRAIE probabilité combinée (produit des probabilités)
en plus de la somme, pour une évaluation honnête.
"""
from itertools import combinations
from sqlalchemy.orm import Session
from sqlalchemy import func

from ..models import Prediction, Event, Match

# Seuil aligné sur les Best Picks (>= 66%)
MIN_INDIVIDUAL_PROB = 66.0
MIN_COMBO_SIZE = 2
MAX_COMBO_SIZE = 4
MIN_TOTAL_ODDS = 3.0
MAX_TOTAL_ODDS = 6.0
MIN_PROB_SUM = 75.0
TOP_N_RESULTS = 3


def _eligible_predictions(db: Session) -> list[Prediction]:
    """Récupère les prédictions Best Picks (proba >= 66%) pour des matchs futurs."""
    return (
        db.query(Prediction)
        .join(Event, Prediction.event_id == Event.id)
        .join(Match, Event.match_id == Match.id)
        .filter(Prediction.probability >= MIN_INDIVIDUAL_PROB)
        .filter(Match.kickoff_at >= func.now())
        .all()
    )


def compute_combo(selections: list[Prediction]) -> dict | None:
    """Calcule les métriques d'une combinaison donnée."""
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


def generate_ticket_combos(db: Session) -> list[dict]:
    """Génère les meilleures combinaisons sans restriction de jours."""
    predictions = _eligible_predictions(db)

    # Si moins de 2 prédictions, pas de combinaison possible
    if len(predictions) < MIN_COMBO_SIZE:
        return []

    candidates = []

    # Parcourir toutes les combinaisons de taille 2 à 4
    for size in range(MIN_COMBO_SIZE, MAX_COMBO_SIZE + 1):
        for combo in combinations(predictions, size):
            # Vérifier qu'aucun match n'est dupliqué (même match_id)
            match_ids = {p.event.match_id for p in combo}
            if len(match_ids) != size:
                continue

            metrics = compute_combo(list(combo))
            if not metrics:
                continue

            if MIN_TOTAL_ODDS <= metrics["total_odds"] <= MAX_TOTAL_ODDS and metrics["probability_sum"] >= MIN_PROB_SUM:
                # Récupérer les dates pour l'affichage (optionnel)
                dates = sorted({p.event.match.kickoff_at.date().isoformat() for p in combo})
                candidates.append({
                    "selections": combo,
                    "dates": dates,
                    **metrics,
                })

    # Trier par probabilité réelle combinée décroissante
    candidates.sort(key=lambda c: c["real_combined_probability"], reverse=True)
    return candidates[:TOP_N_RESULTS]
