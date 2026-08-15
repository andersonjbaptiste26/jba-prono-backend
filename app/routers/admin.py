import os
from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy.orm import Session

from ..database import get_db
from ..ingestion.sync import sync_all_leagues
from ..ingestion.sync_stats import sync_all_team_stats

router = APIRouter(prefix="/admin", tags=["admin"])

ADMIN_TOKEN = os.getenv("ADMIN_TOKEN", "")


def _check_token(x_admin_token: str = Header(...)):
    if not ADMIN_TOKEN or x_admin_token != ADMIN_TOKEN:
        raise HTTPException(status_code=401, detail="Token admin invalide.")


@router.post("/sync-odds")
def sync_odds(db: Session = Depends(get_db), _: None = Depends(_check_token)):
    results = sync_all_leagues(db)
    return {"results": results}


@router.post("/sync-stats")
def sync_stats(db: Session = Depends(get_db), _: None = Depends(_check_token)):
    results = sync_all_team_stats(db)
    return {"results": results}
