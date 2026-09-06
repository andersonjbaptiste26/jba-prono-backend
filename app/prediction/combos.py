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
    try:
        return (
            db.query(Prediction)
            .join(Event, Prediction.event_id == Event.id)
            .join(Match, Event.match_id == Match.id)
            .filter(Prediction.probability >= MIN_INDIVIDUAL_PROB)
            .filter(Match.kickoff_at >= func.now())
            .all()
        )
    except Exception as e:
        print(f"❌ Erreur dans _eligible_predictions : {e}")
        return []


def compute_combo(selections: list[Prediction]) -> dict | None:
    """Calcule les métriques d'une combinaison donnée."""
    total_odds = 1.0
    prob_sum = 0.0
    real_prob = 1.0
    for p in selections:
        if not p.event or not p.event.odds_value:
            return None
        odds = float(p.event.odds_value)
        total_odds *= odds
        prob_sum += float(p.probability)
        real_prob *= (float(p.probability) / 100.0)
    return {
        "total_odds": round(total_odds, 3),
        "probability_sum": round(prob_sum, 2),
        "real_combined_probability": round(real_prob * 100, 2),
    }


def _get_teams_from_combo(combo):
    """Extrait les noms des équipes d'une combinaison (avec sécurité)."""
    teams = set()
    for p in combo:
        try:
            match = p.event.match
            if match.home_team:
                teams.add(match.home_team.name)
            if match.away_team:
                teams.add(match.away_team.name)
        except Exception:
            # Si une relation est manquante, on ignore
            pass
    return teams


def _get_match_info(p):
    """Récupère les infos d'un match de manière sécurisée."""
    try:
        match = p.event.match
        home = match.home_team.name if match.home_team else "?"
        away = match.away_team.name if match.away_team else "?"
        comp = match.competition.name if match.competition else None
        return home, away, comp
    except Exception as e:
        print(f"⚠️ Erreur récupération match info : {e}")
        return "?", "?", None


def generate_ticket_combos(db: Session) -> list[dict]:
    predictions = _eligible_predictions(db)
    if len(predictions) < MIN_COMBO_SIZE:
        print("⚠️ Pas assez de prédictions éligibles (>=66%)")
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
        print("⚠️ Aucune combinaison éligible après filtrage")
        return []

    # Tri par probabilité réelle décroissante (pour chaque catégorie on triera)
    selected_tickets = []
    used_teams = set()

    def select_from_category(cat_min, cat_max, desired):
        eligible = [c for c in all_candidates if cat_min <= c["total_odds"] < cat_max]
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

    # Construire la réponse au format attendu
    result = []
    for c in selected_tickets:
        selections = []
        for p in c["selections"]:
            home, away, comp = _get_match_info(p)
            event = p.event
            selections.append({
                "event_id": event.id,
                "match": f"{home} vs {away}",
                "competition": comp,
                "kickoff_at": event.match.kickoff_at.isoformat() if event.match and event.match.kickoff_at else None,
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
