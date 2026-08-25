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
    avg = stat
