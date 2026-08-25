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
    return [
