import re
from sqlalchemy.orm import Session

from ..models import Team, League, TeamStatistics, TeamRating
from ..scoring import compute_team_rating, TeamStats
from .football_data_client import get_standings, COMPETITION_CODES, FootballDataError


def _normalize(name: str) -> str:
    name = re.sub(r"\b(FC|CF|AFC|SC|AC)\b", "", name, flags=re.IGNORECASE)
    return re.sub(r"[^a-z0-9]", "", name.lower())


def _match_team(team_name: str, table: list[dict]) -> dict | None:
    target = _normalize(team_name)
    for entry in table:
        fd_name = entry["team"]["name"]
