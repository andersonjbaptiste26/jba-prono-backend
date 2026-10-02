import os
import requests

BASE_URL = "https://api.football-data.org/v4"
API_KEY = os.getenv("FOOTBALL_DATA_API_KEY", "")

COMPETITION_CODES = {
    "Premier League": "PL", "La Liga": "PD", "Bundesliga": "BL1",
    "Serie A": "SA", "Ligue 1": "FL1", "Champions League": "CL",
    "Eredivisie": "DED", "Primeira Liga": "PPL",
    "EFL Championship": "ELC", "Brasileirão": "BSA",
}

class FootballDataError(Exception):
    pass


def get_standings(competition_code: str) -> dict:
    if not API_KEY:
        raise FootballDataError("FOOTBALL_DATA_API_KEY n'est pas configurée.")
    resp = requests.get(
        f"{BASE_URL}/competitions/{competition_code}/standings",
        headers={"X-Auth-Token": API_KEY}, timeout=15,
    )
    if resp.status_code == 403:
        raise FootballDataError("Clé API invalide ou compétition non couverte.")
    if resp.status_code == 429:
        raise FootballDataError("Limite de 10 requêtes/minute atteinte.")
    resp.raise_for_status()
    return resp.json()
