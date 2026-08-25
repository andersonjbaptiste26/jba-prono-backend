import os
from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy.orm import Session

from ..database import get_db
from ..ingestion.sync import sync_all_leagues
from ..ingestion.sync_stats import sync_all_team_stats
from ..ingestion.results import sync_all_results
from ..prediction.engine import generate_all_predictions
from ..prediction.settlement import settle_all_bets

router = APIRouter(prefix="/admin", tags=["admin"])

ADMIN_TOKEN = os.getenv("ADMIN_TOKEN", "")


def _check_token(x_admin_token: str = Header(...)):
    if not ADMIN_TOKEN or x_admin_token != ADMIN_TOKEN:
        raise HTTPException(status_code=401, detail="Token admin invalide.")


@router.post("/sync-odds")
def sync_odds(db: Session = Depends(get_db), _: None = Depends(_check_token)):
    return {"results": sync_all_leagues(db)}


@router.post("/sync-stats")
def sync_stats(db: Session = Depends(get_db), _: None = Depends(_check_token)):
    return {"results": sync_all_team_stats(db)}


@router.post("/generate-predictions")
def generate_predictions(db: Session = Depends(get_db), _: None = Depends(_check_token)):
    return generate_all_predictions(db)


@router.post("/sync-results")
def sync_results(db: Session = Depends(get_db), _: None = Depends(_check_token)):
    """Récupère les scores finaux des matchs joués récemment (nécessaire
    avant /admin/settle-bets)."""
    return {"results": sync_all_results(db)}


@router.post("/settle-bets")
def settle_bets(db: Session = Depends(get_db), _: None = Depends(_check_token)):
    """Détermine gagné/perdu pour chaque pari en cours et crée les
    notifications correspondantes. À lancer APRÈS /admin/sync-results."""
    return settle_all_bets(db)
