"""
Combine des pronostics de tous les matchs futurs en tickets multiples,
selon les critères :
- cote combinée entre 3 et 6 (étendu à 6.90 pour la catégorie haute)
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
MAX_COMBO_SIZE = 5              # nombre de matchs par ticket
MIN_TOTAL_ODDS = 3.0
MAX_TOTAL_ODDS = 6.90           # étendu à 6.90
MIN_PROB_SUM = 75.0

# Fourchettes de cotes et nombre souhaité
CATEGORIES = [
    {"min": 3.0, "max": 4.0, "desired": 2},      # catégorie basse
    {"min": 4.0, "max": 5.90, "desired": 2},     # catégorie moyenne
    {"min": 5.90, "max": 6.90, "desired": 1},    # catégorie haute
]


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


def _get_teams_from_combo(combo):
    """Extrait les noms des équipes d'une combinaison."""
    teams = set()
    for p in combo:
        match = p.event.match
        teams.add(match.home_team.name)
        teams.add(match.away_team.name)
    return teams


def generate_ticket_combos(db: Session) -> list[dict]:
    predictions = _eligible_predictions(db)
    if len(predictions) < MIN_COMBO_SIZE:
        return []

    # Générer toutes les combinaisons éligibles
    all_candidates = []
    pool = predictions
    for size in range(MIN_COMBO_SIZE, min(MAX_COMBO_SIZE, len(pool)) + 1):
        for combo in combinations(pool, size):
            match_ids = {p.event.match_id for p in combo}
            if len(match_ids) != size:
                continue
            metrics = compute_combo(list(combo))
            if not metrics:
                continue
            if MIN_TOTAL_ODDS <= metrics["total_odds"] <= MAX_TOTAL_ODDS and metrics["probability_sum"] >= MIN_PROB_SUM:
                dates = sorted({p.event.match.kickoff_at.date().isoformat() for p in combo})
                all_candidates.append({
                    "selections": combo,
                    "dates": dates,
                    **metrics,
                })

    if not all_candidates:
        return []

    # Tri par probabilité réelle décroissante (pour chaque catégorie on triera)
    # On va constituer une liste de tickets sélectionnés
    selected_tickets = []
    used_teams = set()  # équipes déjà utilisées

    # Fonction de sélection pour une catégorie
    def select_from_category(cat_min, cat_max, desired):
        # Filtrer les candidats dans la fourchette
        eligible = [c for c in all_candidates if cat_min <= c["total_odds"] < cat_max]
        # Trier par probabilité réelle décroissante
        eligible.sort(key=lambda c: c["real_combined_probability"], reverse=True)
        chosen = []
        for c in eligible:
            if len(chosen) >= desired:
                break
            teams = _get_teams_from_combo(c["selections"])
            # Vérifier qu'aucune équipe n'est déjà utilisée
            if not (teams & used_teams):
                chosen.append(c)
                used_teams.update(teams)
        return chosen

    # Sélectionner pour chaque catégorie
    for cat in CATEGORIES:
        chosen = select_from_category(cat["min"], cat["max"], cat["desired"])
        selected_tickets.extend(chosen)

    # Si on n'a pas assez de tickets, on pourrait compléter avec les meilleurs restants
    # mais on s'arrête là pour respecter les catégories.

    # Construire la réponse au format attendu
    result = []
    for c in selected_tickets:
        selections = []
        for p in c["selections"]:
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
        result.append({
            "selections": selections,
            "total_odds": c["total_odds"],
            "probability_sum": c["probability_sum"],
            "real_combined_probability": c["real_combined_probability"],
            "dates": c["dates"],
        })
    return result
