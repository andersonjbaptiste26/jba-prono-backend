"""
Moteur de probabilité v1 (roadmap phase 4) — approche statistique,
avant de passer au Machine Learning plus tard.

Combine deux sources :
  - Probabilité implicite du marché (cotes des bookmakers, marge retirée)
  - Probabilité issue du Team Rating (forme, attaque, défense...)
Si une des deux équipes n'a pas de Team Rating fiable (nom non reconnu
entre les APIs), on se fie au marché seul plutôt que d'imposer un
rating par défaut arbitraire.
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

    has_ratings = home_rating_row is not None and away_rating_row is not None

    if has_ratings:
        rating_home = float(home_rating_row.rating)
        rating_away = float(away_rating_row.rating)
        rating_probs = rating_based_probabilities(rating_home, ratin
