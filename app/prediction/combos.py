"""
Combine des pronostics de tous les matchs futurs en tickets multiples,
selon les critères :
- cote combinée entre 3 et 6
- somme des probabilités individuelles >= 75%
- 2 à 5 matchs par ticket
- Les matchs sont exclusivement ceux des Best Picks (probabilité >= 66%)

Affiche aussi la VRAIE probabilité combinée (produit des probabilités,
pas la somme) pour rester honnête.
"""
from itertools import combinations
from sqlalchemy.orm import Session
from sqlalchemy import func

from ..models import Prediction, Event, Match

# ── Paramètres ajustables ──
MIN_INDIVIDUAL_PROB = 66.0      # seuil Best Picks
MIN_COMBO_SIZE = 2
MAX_COMBO_SIZE = 5              # étendu à 5 matchs par ticket
MIN_TOTAL_ODDS = 3.0
MAX_TOTAL_ODDS = 6.0
MIN_PROB_SUM = 75.0
TOP_N_RESULTS = 7               # nombre maximum de tickets retournés


def _eligible_predictions(db: Session) -> list[Prediction]:
    """Récupère les prédictions Best Picks (>= 66%) avec matchs futurs."""
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
    """
    Génère les meilleures combinaisons de tickets à partir de tous les
    matchs Best Picks futurs, sans limitation de jours.
    """
    predictions = _eligible_predictions(db)
    # Trier par date pour avoir un ordre cohérent
    predictions.sort(key=lambda p: p.event.match.kickoff_at)

    if len(predictions) < MIN_COMBO_SIZE:
        return []

    candidates = []
    pool = predictions

    # Générer les combinaisons de 2 à MAX_COMBO_SIZE matchs
    for size in range(MIN_COMBO_SIZE, min(MAX_COMBO_SIZE, len(pool)) + 1):
        for combo in combinations(pool, size):
            # Vérifier que les matchs sont distincts (pas deux sélections sur le même match)
            match_ids = {p.event.match_id for p in combo}
            if len(match_ids) != size:
                continue
            metrics = compute_combo(list(combo))
            if not metrics:
                continue
            if MIN_TOTAL_ODDS <= metrics["total_odds"] <= MAX_TOTAL_ODDS and metrics["probability_sum"] >= MIN_PROB_SUM:
                # Récupérer les dates uniques des matchs
                dates = sorted({p.event.match.kickoff_at.date().isoformat() for p in combo})
                candidates.append({
                    "selections": combo,
                    "dates": dates,
                    **metrics,
                })

    # Trier par probabilité réelle combinée (produit) décroissante
    candidates.sort(key=lambda c: c["real_combined_probability"], reverse=True)
    return candidates[:TOP_N_RESULTS]
