import math
from sqlalchemy.orm import Session

from ..models import Match, Event, TeamRating, Prediction
from ..scoring import confidence_tier

MARKET_WEIGHT = 0.6
RATING_WEIGHT = 0.4
HOME_ADVANTAGE = 5.0
BASE_DRAW_RATE = 0.26


def implied_probabilities(odds_home: float, odds_draw: float, odds_away: float) -> list[float]:
    raw = [1 / odds_home, 1 / odds_draw, 1 / odds_away]
    total = sum(raw)
    return [r / total for r in raw]


def implied_probabilities_two_way(odds_a: float, odds_b: float) -> list[float]:
    raw = [1 / odds_a, 1 / odds_b]
    total = sum(raw)
    return [r / total for r in raw]


def rating_based_probabilities(rating_home: float, rating_away: float) -> list[float]:
    adjusted_home = rating_home + HOME_ADVANTAGE
    diff = adjusted_home - rating_away
    p_home_only = 1 / (1 + 10 ** (-diff / 400))
    draw_prob = BASE_DRAW_RATE * math.exp(-abs(diff) / 60)
    remaining = 1 - draw_prob
    return [remaining * p_home_only, draw_prob, remaining * (1 - p_home_only)]


def blend_probabilities(market: list[float], rating: list[float]) -> list[float]:
    blended = [MARKET_WEIGHT * m + RATING_WEIGHT * r for m, r in zip(market, rating)]
    total = sum(blended)
    return [b / total for b in blended]


def _save_prediction(db: Session, event: Event, percentage: float, explanation: dict):
    prediction = db.query(Prediction).filter(Prediction.event_id == event.id).first()
    if not prediction:
        prediction = Prediction(event_id=event.id)
        db.add(prediction)
    prediction.probability = percentage
    prediction.confidence_tier = confidence_tier(percentage)
    prediction.model_version = "v1-statistique"
    prediction.explanation = explanation


def _generate_resultat_predictions(db: Session, match: Match, events: list[Event]) -> bool:
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
    has_ratings = home_rating_row is not None and away_rating_row is not None

    if has_ratings:
        rating_home = float(home_rating_row.rating)
        rating_away = float(away_rating_row.rating)
        rating_probs = rating_based_probabilities(rating_home, rating_away)
        final_probs = blend_probabilities(market_probs, rating_probs)
    else:
        rating_home = float(home_rating_row.rating) if home_rating_row else None
        rating_away = float(away_rating_row.rating) if away_rating_row else None
        rating_probs = market_probs
        final_probs = market_probs

    labels = ["Victoire domicile", "Match nul", "Victoire extérieur"]
    ordered_events = [home_event, draw_event, away_event]
    for idx, (event, prob, label) in enumerate(zip(ordered_events, final_probs, labels)):
        percentage = round(prob * 100, 2)
        explanation = {
            "type_pronostic": label,
            "probabilite_marche_pct": round(market_probs[idx] * 100, 2),
            "probabilite_rating_pct": round(rating_probs[idx] * 100, 2) if has_ratings else None,
            "team_rating_domicile": round(rating_home, 2) if rating_home is not None else None,
            "team_rating_exterieur": round(rating_away, 2) if rating_away is not None else None,
            "rating_disponible": has_ratings,
            "cote": float(event.odds_value),
        }
        _save_prediction(db, event, percentage, explanation)
    return True


def _generate_two_way_predictions(db: Session, events: list[Event], event_type: str) -> bool:
    typed_events = [e for e in events if e.type == event_type and e.odds_value]
    if len(typed_events) < 2:
        return False

    a, b = typed_events[0], typed_events[1]
    probs = implied_probabilities_two_way(float(a.odds_value), float(b.odds_value))

    for event, prob in zip([a, b], probs):
        percentage = round(prob * 100, 2)
        explanation = {
            "type_pronostic": event.label,
            "probabilite_marche_pct": percentage,
            "rating_disponible": False,
            "cote": float(event.odds_value),
        }
        _save_prediction(db, event, percentage, explanation)
    return True


def generate_predictions_for_match(db: Session, match: Match) -> bool:
    all_events = db.query(Event).filter(Event.match_id == match.id).all()
    success = False
    if _generate_resultat_predictions(db, match, all_events):
        success = True
    if _generate_two_way_predictions(db, all_events, "buts"):
        success = True
    return success


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
