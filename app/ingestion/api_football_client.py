"""
Client HTTP pour API-Football (api-sports.io v3).
"""
import os
import requests

BASE_URL = "https://v3.football.api-sports.io"
API_KEY = os.getenv("API_FOOTBALL_KEY", "")

LEAGUE_IDS = {
    "Premier League": 39,
    "La Liga": 140,
    "Serie A": 135,
    "Bundesliga": 78,
    "Ligue 1": 61,
    "Champions League": 2,
}

CURRENT_SEASON = int(os.getenv("API_FOOTBALL_SEASON", "2026"))


class ApiFootballError(Exception):
    pass


def _headers() -> dict:
    if not API_KEY:
        raise ApiFootballError("API_FOOTBALL_KEY n'est pas configurée.")
    return {"x-apisports-key": API_KEY}


def get_teams(league_id: int, season: int = CURRENT_SEASON) -> list[dict]:
    resp = requests.get(
        f"{BASE_URL}/teams",
        headers=_headers(),
        params={"league": league_id, "season": season},
        timeout=15,
    )
    _check_response(resp)
    return resp.json().get("response", [])


def get_team_statistics(league_id: int, team_id: int, season: int = CURRENT_SEASON) -> dict:
    resp = requests.get(
        f"{BASE_URL}/teams/statistics",
        headers=_headers(),
        params={"league": league_id, "team": team_id, "season": season},
        timeout=15,
    )
    _check_response(resp)
    return resp.json().get("response", {})


def _check_response(resp: requests.Response):
    if resp.status_code == 401 or resp.status_code == 403:
        raise ApiFootballError("Clé API invalide ou accès refusé.")
    if resp.status_code == 429:
        raise ApiFootballError("Limite de requêtes journalière atteinte (100/jour en gratuit).")
    resp.raise_for_status()
    body = resp.json()
    if body.get("errors"):
        raise ApiFootballError(str(body["errors"]))
