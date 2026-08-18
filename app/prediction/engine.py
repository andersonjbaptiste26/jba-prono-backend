"""
Moteur de probabilité v1 (roadmap phase 4) — approche statistique,
avant de passer au Machine Learning plus tard.
"""
import math
from sqlalchemy.orm import Session

from ..models import Match, Event, TeamRating
from ..scoring import confidence_tier

MARKET_WEIGHT = 0.6
RATING_WEIGHT = 0.4
HOME_ADVANTAGE = 5.0
BASE_DRAW_RATE = 0.26


def implied_probabilities(odds_home: float, odds_draw: float, odds_away: float) -> list[float]:
    raw = [1 / odds_home, 1 / odds_draw, 1 / odds_away]
    total = sum(raw)
    return [r / total for r in raw]


def rating_based_probabilities(rating_home: float, rating_away: float) -> list[float]:
    adjusted_home = rating_home + HOME_ADVANTAGE
    diff = adjusted_home - rating_away
    p_home_only = 1 / (1 + 10 ** (-diff / 400))
    draw_prob = BASE_DRAW_RATE * math.exp(-abs(diff) / 60)
    remaining = 1 - draw_prob
    p_home = remaining * p_home_only
    p_away = remaining * (1 - p_home_only)
    return [p_home, draw_prob, p_away]


def blend_probabilities(market: list[float], rating: list[float]) -> list[float]:
    blended = [MARKET_WEIGHT * m + RATING_WEIGHT * r for m, r in zip(market, rating)]
    total = sum(blended)
    return [b / total for b in blended]


def generate_predictions_for_match(db: Session, match: Match) -> bool:
    events = db.query(Event).filter(Event.match_id == match.id, Event.type == "resultat").all()

    home_event = next((e for e in events if e.label.startswith("1")), None)
    draw_event = next((e for e in events if e.label.startswith("X")), None)
    away_event = next((e for e in events if e.label.startswith("2")), None)

    if not (home_event and draw_event and away_event):
        return False
    if not (home_event.odds_value and draw_event.odds_value and away_event.odds_value):
        return False

    market_probs = implied_probabilities(
        float(home_event.odds_value), float(draw_event.odds_value), float(away_event.odds_value)
    )

    home_rating_row = db.query(TeamRating).filter(TeamRating.team_id == match.home_team_id).first()
    away_rating_row = db.query(TeamRating).filter(TeamRating.team_id == match.away_team_id).first()
    rating_home = float(home_rating_row.rating) if home_rating_row else 50.0
    rating_away = float(away_rating_row.rating) if away_rating_row else 50.0

    rating_probs = rating_based_probabilities(rating_home, rating_away)
    final_probs = blend_probabilities(market_probs, rating_probs)

    labels = ["Victoire domicile", "Match nul", "Victoire extérieur"]
    for event, prob, label in zip([home_event, draw_event, away_event], final_probs, labels):
        percentage = round(prob * 100, 2)
        tier = confidence_tier(percentage)
        idx = [home_event, draw_event, away_event].index(event)
        explanation = {
            "type_pronostic": label,
            "probabilite_marche_pct": round(market_probs[idx] * 100, 2),
            "probabilite_rating_pct": round(rating_probs[idx] * 100, 2),
            "team_rating_domicile": round(rating_home, 2),
            "team_rating_exterieur": round(rating_away, 2),
            "cote": float(event.odds_value),
        }

        from ..models import Prediction
        prediction = db.query(Prediction).filter(Prediction.event_id == event.id).first()
        if not prediction:
            prediction = Prediction(event_id=event.id)
            db.add(prediction)
        prediction.probability = percentage
        prediction.confidence_tier = tier
        prediction.model_version = "v1-statistique"
        prediction.explanation = explanation

    return True


def generate_all_predictions(db: Session) -> dict:
    matches = db.query(Match).filter(Match.status == "scheduled").all()
    processed, skipped = 0, 0

    for match in matches:
        if generate_predictions_for_match(db, match):
            processed += 1
        else:
            skipped += 1

    db.commit()
    return {"matches_processed": processed, "matches_skipped": skipped, "total_matches": len(matches)}
