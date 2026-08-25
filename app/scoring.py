from dataclasses import dataclass

WEIGHTS = {
    "form": 0.20, "attack": 0.20, "defense": 0.20,
    "home_away": 0.10, "season": 0.15, "h2h": 0.05, "squad": 0.10,
}


@dataclass
class TeamStats:
    matches_played: int
    wins: int
    draws: int
    losses: int
    goals_for: int
    goals_against: int
    clean_sheets: int
    form_last5: str
    home_wins: int
    away_wins: int
    h2h_win_rate: float
    squad_availability: float


def _score_form(stats: TeamStats) -> float:
    points = {"V": 3, "N": 1, "D": 0}
    total = sum(points.get(r, 0) for r in stats.form_last5[-5:])
    return (total / 15) * 100 if stats.form_last5 else 50.0


def _score_attack(stats: TeamStats) -> float:
    if stats.matches_played == 0:
        return 50.0
    avg = stats.goals_for / stats.matches_played
    return min(100.0, (avg / 2.5) * 100)


def _score_defense(stats: TeamStats) -> float:
    if stats.matches_played == 0:
        return 50.0
    avg_conceded = stats.goals_against / stats.matches_played
    clean_sheet_rate = stats.clean_sheets / stats.matches_played
    base = max(0.0, 100 - (avg_conceded / 2.0) * 100)
    return min(100.0, base * 0.7 + clean_sheet_rate * 100 * 0.3)


def _score_home_away(stats: TeamStats) -> float:
    if stats.matches_played == 0:
        return 50.0
    total_wins = stats.home_wins + stats.away_wins
    return min(100.0, (total_wins / stats.matches_played) * 150)


def _score_season(stats: TeamStats) -> float:
    if stats.matches_played == 0:
        return 50.0
    points = stats.wins * 3 + stats.draws
    ppm = points / stats.matches_played
    return min(100.0, (ppm / 3) * 100)


def _score_h2h(stats: TeamStats) -> float:
    return stats.h2h_win_rate * 100


def _score_squad(stats: TeamStats) -> float:
    return stats.squad_availability * 100


def compute_team_rating(stats: TeamStats) -> dict:
    sub_scores = {
        "form": _score_form(stats), "attack": _score_attack(stats),
        "defense": _score_defense(stats), "home_away": _score_home_away(stats),
        "season": _score_season(stats), "h2h": _score_h2h(stats),
        "squad": _score_squad(stats),
    }
    rating = sum(sub_scores[k] * WEIGHTS[k] for k in WEIGHTS)
    return {"rating": round(rating, 2), "sub_scores": {k: round(v, 2) for k, v in sub_scores.items()}}


def confidence_tier(probability: float) -> str:
    if probability >= 90:
        return "tresforte"
    if probability >= 85:
        return "forte"
    if probability >= 80:
        return "elevee"
    return "faible"
