"""
Client The Odds API v4
Récupère les cotes des bookmakers pour chaque match.
Doc : https://the-odds-api.com/liveapi/guides/v4/
"""
import os
import httpx
from typing import Optional
from datetime import datetime, timedelta

ODDS_API_BASE = "https://api.the-odds-api.com/v4"
ODDS_API_KEY = os.getenv("ODDS_API_KEY", "")

# ============================================================
# SPORTS SUPPORTÉS (slugs The Odds API)
# Vérifie la liste live : GET /v4/sports?apiKey=XXX
# ============================================================
SPORTS = {
    # --- Clubs ---
    "soccer_epl": "Premier League",
    "soccer_germany_bundesliga": "Bundesliga",
    "soccer_italy_serie_a": "Serie A",
    "soccer_spain_la_liga": "La Liga",
    "soccer_france_ligue_one": "Ligue 1",
    "soccer_netherlands_eredivisie": "Eredivisie",
    "soccer_portugal_primeira_liga": "Primeira Liga",
    "soccer_brazil_campeonato": "Brasileirão",
    "soccer_efl_champ": "EFL Championship",
    "soccer_uefa_champs_league": "UEFA Champions League",
    "soccer_uefa_europa_league": "UEFA Europa League",
    "soccer_uefa_europa_conference_league": "UEFA Europa Conference League",
    # --- Sélections nationales ---
    "soccer_uefa_nations_league": "UEFA Nations League",
    "soccer_uefa_euro_championship": "UEFA Euro",
    "soccer_fifa_world_cup": "FIFA World Cup",
    "soccer_fifa_world_cup_qualifiers_uefa": "WC Qualifiers UEFA",
}

# Mapping slug Odds API -> code football-data.org
ODDS_TO_FD_CODE = {
    "soccer_epl": "PL",
    "soccer_germany_bundesliga": "BL1",
    "soccer_italy_serie_a": "SA",
    "soccer_spain_la_liga": "PD",
    "soccer_france_ligue_one": "FL1",
    "soccer_netherlands_eredivisie": "DED",
    "soccer_portugal_primeira_liga": "PPL",
    "soccer_brazil_campeonato": "BSA",
    "soccer_efl_champ": "ELC",
    "soccer_uefa_champs_league": "CL",
    "soccer_uefa_europa_league": "EL",
    "soccer_uefa_europa_conference_league": "ECL",
    "soccer_uefa_nations_league": "UNL",
    "soccer_uefa_euro_championship": "EC",
    "soccer_fifa_world_cup": "WC",
}


def fetch_odds(
    sport: str = "soccer_epl",
    regions: str = "eu",
    markets: str = "h2h",
    odds_format: str = "decimal",
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
) -> list[dict]:
    """
    Récupère les cotes pour un sport donné.
    - sport : slug (ex: 'soccer_epl', 'soccer_uefa_nations_league')
    - regions : 'eu', 'us', 'uk', 'au'
    - markets : 'h2h', 'totals', 'btts'
    - odds_format : 'decimal' (européen) ou 'american'
    """
    if not ODDS_API_KEY:
        print("[ODDS] Clé API manquante (ODDS_API_KEY)")
        return []

    url = f"{ODDS_API_BASE}/sports/{sport}/odds"
    params = {
        "apiKey": ODDS_API_KEY,
        "regions": regions,
        "markets": markets,
        "oddsFormat": odds_format,
    }
    if date_from:
        params["commenceTimeFrom"] = date_from
    if date_to:
        params["commenceTimeTo"] = date_to

    try:
        with httpx.Client(timeout=30) as client:
            r = client.get(url, params=params)
            r.raise_for_status()
            data = r.json()
            # Log du quota restant (utile en free tier)
            remaining = r.headers.get("x-requests-remaining", "?")
            print(f"[ODDS] {sport} : {len(data)} matchs | quota restant : {remaining}")
            return data
    except httpx.HTTPStatusError as e:
        print(f"[ODDS] Erreur HTTP {e.response.status_code} pour {sport}: {e.response.text[:200]}")
        return []
    except Exception as e:
        print(f"[ODDS] Erreur fetch_odds {sport}: {e}")
        return []


def fetch_all_odds(regions: str = "eu", markets: str = "h2h") -> dict:
    """
    Récupère les cotes pour TOUS les sports supportés.
    ⚠️ Attention au quota (free tier = 500 req/mois).
    """
    results = {}
    for sport in SPORTS.keys():
        odds = fetch_odds(sport=sport, regions=regions, markets=markets)
        if odds:
            results[sport] = odds
    return results


def extract_best_odds(event: dict) -> Optional[dict]:
    """
    Extrait les meilleures cotes 1/X/2 d'un event Odds API.
    Retourne {'1': float, 'X': float, '2': float, 'bookmaker': str}
    """
    if not event.get("bookmakers"):
        return None

    best = {"1": 0.0, "X": 0.0, "2": 0.0, "bookmaker": ""}
    for bm in event["bookmakers"]:
        for market in bm.get("markets", []):
            if market.get("key") != "h2h":
                continue
            outcomes = {o["name"]: o["price"] for o in market.get("outcomes", [])}
            home = event.get("home_team", "")
            away = event.get("away_team", "")

            odd_1 = outcomes.get(home, 0)
            odd_2 = outcomes.get(away, 0)
            odd_x = outcomes.get("Draw", 0)

            # On garde les meilleures cotes (les plus élevées)
            if odd_1 > best["1"]:
                best["1"] = odd_1
                best["bookmaker"] = bm.get("title", "")
            if odd_x > best["X"]:
                best["X"] = odd_x
            if odd_2 > best["2"]:
                best["2"] = odd_2

    if best["1"] > 0 and best["X"] > 0 and best["2"] > 0:
        return best
    return None


def get_fd_code(sport_slug: str) -> Optional[str]:
    """Convertit un slug Odds API en code football-data.org."""
    return ODDS_TO_FD_CODE.get(sport_slug)
