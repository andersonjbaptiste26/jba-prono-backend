"""
Récupère les résultats finaux des matchs depuis The Odds API (endpoint
/scores) pour pouvoir déterminer si un pari est gagné ou perdu.
"""
import os
import requests
from sqlalchemy.orm import Session

from ..models import Match
from .odds_api_client import LEAGUE_KEYS, OddsApiError

BASE_URL = "https://api.the-odds-api.com/v4"
API_KEY = os.getenv("ODDS_API_KEY", "")


def fetch_scores(sport_key: str, days_from: int = 3) -> list[dict]:
    """Coût : 2 crédits par appel. Renvoie les matchs en cours et terminés
    des `days_from` derniers jours (max 3)."""
    if not API_KEY:
        raise OddsApiError("ODDS_API_KEY n'est pas configurée.")
    resp = requests.get(
        f"{BASE_URL}/sports/{sport_key}/scores",
        params={"apiKey": API_KEY, "daysFrom": days_from, "dateFormat": "iso"},
        timeout=15,
    )
    if resp.status_code == 401:
        raise OddsApiError("Clé API invalide ou expirée.")
    if resp.status_code == 429:
        raise OddsApiError("Limite de requêtes atteinte, réessaie plus tard.")
    resp.raise_for_status()
    return resp.json()


def sync_results_for_league(db: Session, sport_key: str, league_name: str) -> dict:
    games = fetch_scores(sport_key)
    updated = 0

    for game in games:
        if not game.get("completed") or not game.get("scores"):
            continue

        match = db.query(Match).filter(Match.external_id == game["id"]).first()
        if not match or match.status == "finished":
            continue

        home_score = away_score = None
        for s in game["scores"]:
            if s["name"] == game["home_team"]:
                home_score = int(s["score"])
            elif s["name"] == game["away_team"]:
                away_score = int(s["score"])

        if home_score is not None and away_score is not None:
            match.home_score = home_score
            match.away_score = away_score
            match.status = "finished"
            updated += 1

    db.commit()
    return {"league": league_name, "matches_updated": updated}


def sync_all_results(db: Session) -> list[dict]:
    results = []
    for sport_key, league_name in LEAGUE_KEYS.items():
        try:
            results.append(sync_results_for_league(db, sport_key, league_name))
        except OddsApiError as e:
            results.append({"league": league_name, "error": str(e)})
    return results
