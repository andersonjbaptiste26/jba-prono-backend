"""
Combine des pronostics de deux jours consécutifs en tickets multiples,
selon les critères :
- cote combinée entre 3 et 6
- somme des probabilités individuelles >= 75%
- 2 à 4 matchs par ticket

Affiche aussi la VRAIE probabilité combinée (produit des probabilités,
pas la somme) pour rester honnête — la somme demandée sert de filtre,
mais ne représente pas la chance réelle de gagner le ticket entier.
"""
from itertools import combinations
from collections import defaultdict
from sqlalchemy.orm import Session
from sqlalchemy import func

from ..models import Prediction, Event, Match

MIN_INDIVIDUAL_PROB = 50.0
MIN_COMBO_SIZE = 2
MAX_COMBO_SIZE = 4
MIN_TOTAL_ODDS = 3.0
MAX_TOTAL_ODDS = 6.0
MIN_PROB_SUM = 75.0
TOP_N_RESULTS = 3


def _eligible_predictions(db: Session) -> list[Prediction]:
    return (
        db.query(Prediction)
        .join(Event, Prediction.event_id == Event.id)
        .join(Match, Event.match_id == Match.id)
        .filter(Prediction.probability >= MIN_INDIVIDUAL_PROB)
        .filter(Match.kickoff_at >= func.now())
        .all()
    )


def _group_by_date(predictions: list[Prediction]) -> dict:
    by_date = defaultdict(list)
    for p in predictions:
        d = p.event.match.kickoff_at.date()
        by_date[d].append(p)
    return by_date


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


def generate_ticket_combos(db: Session) -> list[dict]:
    predictions = _eligible_predictions(db)
    by_date = _group_by_date(predictions)
    dates_sorted = sorted(by_date.keys())

    candidates = []

    for i in range(len(dates_sorted) - 1):
        d1, d2 = dates_sorted[i], dates_sorted[i + 1]
        if (d2 - d1).days != 1:
            continue

        pool = by_date[d1] + by_date[d2]

        for size in range(MIN_COMBO_SIZE, MAX_COMBO_SIZE + 1):
            for combo in combinations(pool, size):
                match_ids = {p.event.match_id for p in combo}
                if len(match_ids) != size:
                    continue

                metrics = compute_combo(list(combo))
                if not metrics:
                    continue

                if MIN_TOTAL_ODDS <= metrics["total_odds"] <= MAX_TOTAL_ODDS and metrics["probability_sum"] >= MIN_PROB_SUM:
                    candidates.append({
                        "selections": combo,
                        "dates": [d1.isoformat(), d2.isoformat()],
                        **metrics,
                    })

    candidates.sort(key=lambda c: c["real_combined_probability"], reverse=True)
    return candidates[:TOP_N_RESULTS]
