"""
Client football-data.org v4
Récupère matchs, classements, équipes, stats.
Doc : https://www.football-data.org/documentation/quickstart
"""
import os
import httpx
from typing import Optional
from datetime import datetime, timedelta

FOOTBALL_DATA_BASE = "https://api.football-data.org/v4"
FOOTBALL_DATA_KEY = os.getenv("FOOTBALL_DATA_API_KEY", "")

# ============================================================
# COMPÉTITIONS SUPPORTÉES
# ============================================================
COMPETITIONS = {
    # --- Clubs ---
    "PL":  "Premier League",
    "BL1": "Bundesliga",
    "SA":  "Serie A",
    "PD":  "La Liga",
    "FL1": "Ligue 1",
    "DED": "Eredivisie",
    "PPL": "Primeira Liga",
    "BSA": "Brasileirão",
    "ELC": "EFL Championship",
    "CL":  "UEFA Champions League",
    "EL":  "UEFA Europa League",
    "ECL": "UEFA Europa Conference League",
    # --- Sélections nationales ---
    "UNL": "UEFA Nations League",
    "EC":  "UEFA Euro",
    "WC":  "FIFA World Cup",
}

# Type de compétition pour chaque code (utile pour le moteur de prédiction)
COMPETITION_TYPE = {
    "PL": "club", "BL1": "club", "SA": "club", "PD": "club",
    "FL1": "club", "DED": "club", "PPL": "club", "BSA": "club",
    "ELC": "club",
    "CL": "cup", "EL": "cup", "ECL": "cup",
    "UNL": "national_team",
    "EC": "national_team",
    "WC": "national_team",
}


def _headers() -> dict:
    return {"X-Auth-Token": FOOTBALL_DATA_KEY}


def fetch_matches(
    competition: str = "PL",
    season: Optional[int] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    matchday: Optional[int] = None,
) -> list[dict]:
    """
    Récupère les matchs d'une compétition.
    - competition : code (ex: 'PL', 'UNL')
    - season : année de début de saison (ex: 2025 pour 2025-2026)
    - date_from / date_to : format 'YYYY-MM-DD'
    """
    if competition not in COMPETITIONS:
        raise ValueError(f"Compétition inconnue : {competition}")

    url = f"{FOOTBALL_DATA_BASE}/competitions/{competition}/matches"
    params = {}
    if season:
        params["season"] = season
    if date_from:
        params["dateFrom"] = date_from
    if date_to:
        params["dateTo"] = date_to
    if matchday:
        params["matchday"] = matchday

    try:
        with httpx.Client(timeout=30) as client:
            r = client.get(url, headers=_headers(), params=params)
            r.raise_for_status()
            data = r.json()
            return data.get("matches", [])
    except httpx.HTTPStatusError as e:
        print(f"[FD] Erreur HTTP {e.response.status_code} pour {competition}: {e.response.text[:200]}")
        return []
    except Exception as e:
        print(f"[FD] Erreur fetch_matches {competition}: {e}")
        return []


def fetch_standings(competition: str = "PL", season: Optional[int] = None) -> list[dict]:
    """Récupère le classement d'une compétition."""
    url = f"{FOOTBALL_DATA_BASE}/competitions/{competition}/standings"
    params = {}
    if season:
        params["season"] = season

    try:
        with httpx.Client(timeout=30) as client:
            r = client.get(url, headers=_headers(), params=params)
            r.raise_for_status()
            data = r.json()
            standings = data.get("standings", [])
            for s in standings:
                if s.get("type") == "TOTAL":
                    return s.get("table", [])
            return standings[0].get("table", []) if standings else []
    except Exception as e:
        print(f"[FD] Erreur fetch_standings {competition}: {e}")
        return []


def fetch_team(team_id: int) -> Optional[dict]:
    """Récupère les infos d'une équipe."""
    url = f"{FOOTBALL_DATA_BASE}/teams/{team_id}"
    try:
        with httpx.Client(timeout=30) as client:
            r = client.get(url, headers=_headers())
            r.raise_for_status()
            return r.json()
    except Exception as e:
        print(f"[FD] Erreur fetch_team {team_id}: {e}")
        return None


def fetch_scorers(competition: str = "PL", season: Optional[int] = None, limit: int = 10) -> list[dict]:
    """Top buteurs d'une compétition."""
    url = f"{FOOTBALL_DATA_BASE}/competitions/{competition}/scorers"
    params = {"limit": limit}
    if season:
        params["season"] = season
    try:
        with httpx.Client(timeout=30) as client:
            r = client.get(url, headers=_headers(), params=params)
            r.raise_for_status()
            return r.json().get("scorers", [])
    except Exception as e:
        print(f"[FD] Erreur fetch_scorers {competition}: {e}")
        return []


def get_competition_type(competition_code: str) -> str:
    """Retourne 'club', 'cup' ou 'national_team'."""
    return COMPETITION_TYPE.get(competition_code, "club")
