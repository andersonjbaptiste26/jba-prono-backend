"""
Client HTTP pour The Odds API (the-odds-api.com).
Documentation : https://the-odds-api.com/liveapi/guides/v4/
"""
import os
import requests

BASE_URL = "https://api.the-odds-api.com/v4"
API_KEY = os.getenv("ODDS_API_KEY", "")

LEAGUE_KEYS = {
    "soccer_epl": "Premier League",
    "soccer_spain_la_liga": "La Liga",
    "soccer_italy_serie_a": "Serie A",
    "soccer_germany_bundesliga": "Bundesliga",
    "soccer_france_ligue_one": "Ligue 1",
    "soccer_uefa_champs_league": "Champions League",
}


class OddsApiError(Exception):
    pass


def fetch_odds(sport_key: str, regions: str = "eu", markets: str = "h2h,totals") -> list[dict]:
    """Récupère les matchs à venir + cotes pour plusieurs types d'événements
    (résultat, buts +/-) en un seul appel. Coût : 1 crédit par marché
    demandé x 1 région (2 marchés = 2 crédits par appel).

    Note : 'btts' n'est PAS un marché valide sur cet endpoint "en masse" —
    seuls h2h, spreads et totals le sont. BTTS existe uniquement via
    l'endpoint par match (1 appel/match), trop coûteux pour le quota
    gratuit actuel. À réintégrer si on passe sur un plan payant."""
    if not API_KEY:
        raise OddsApiError("ODDS_API_KEY n'est pas configurée (variable d'environnement manquante).")

    url = f"{BASE_URL}/sports/{sport_key}/odds"
    params = {
        "apiKey": API_KEY,
        "regions": regions,
        "markets": markets,
        "oddsFormat": "decimal",
        "dateFormat": "iso",
    }
    resp = requests.get(url, params=params, timeout=15)
    if resp.status_code == 401:
        raise OddsApiError("Clé API invalide ou expirée.")
    if resp.status_code == 429:
        raise OddsApiError("Limite de requêtes atteinte, réessaie plus tard.")
    resp.raise_for_status()
    return resp.json()


def get_remaining_quota(response: requests.Response) -> dict:
    return {
        "remaining": response.headers.get("x-requests-remaining"),
        "used": response.headers.get("x-requests-used"),
        "last_cost": response.headers.get("x-requests-last"),
    }
