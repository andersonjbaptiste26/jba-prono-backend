import os
import secrets
from fastapi import APIRouter, Depends, HTTPException, Header, Query
from sqlalchemy.orm import Session

from ..database import get_db
from ..ingestion.sync import sync_all_leagues
from ..ingestion.sync_stats import sync_all_team_stats
from ..ingestion.results import sync_all_results
from ..prediction.engine import generate_all_predictions
from ..models import InvitationCode
from ..cache import cache_invalidate, cache_stats

router = APIRouter(prefix="/admin", tags=["admin"])

ADMIN_TOKEN = os.getenv("ADMIN_TOKEN", "")


def _check_token(x_admin_token: str = Header(...)):
    if not ADMIN_TOKEN or x_admin_token != ADMIN_TOKEN:
        raise HTTPException(status_code=401, detail="Token admin invalide.")


def _generate_code() -> str:
    chars = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    part = lambda: "".join(secrets.choice(chars) for _ in range(4))
    return f"JBA-{part()}-{part()}"


@router.post("/generate-codes")
def generate_codes(
    count: int = Query(1, ge=1, le=50),
    label: str = Query(None),
    db: Session = Depends(get_db),
    _: None = Depends(_check_token),
):
    codes = []
    for _i in range(count):
        code = _generate_code()
        while db.query(InvitationCode).filter(InvitationCode.code == code).first():
            code = _generate_code()
        db.add(InvitationCode(code=code, label=label))
        codes.append(code)
    db.commit()
    return {"codes": codes}


@router.get("/codes")
def list_codes(db: Session = Depends(get_db), _: None = Depends(_check_token)):
    rows = db.query(InvitationCode).order_by(InvitationCode.created_at.desc()).all()
    return [
        {"code": c.code, "label": c.label, "used": c.user_id is not None,
         "created_at": c.created_at.isoformat()}
        for c in rows
    ]


@router.post("/sync-odds")
def sync_odds(db: Session = Depends(get_db), _: None = Depends(_check_token)):
    result = sync_all_leagues(db)
    cache_invalidate("predictions_")
    cache_invalidate("matches_")
    cache_invalidate("teams_")
    return {"results": result}


@router.post("/sync-stats")
def sync_stats(db: Session = Depends(get_db), _: None = Depends(_check_token)):
    result = sync_all_team_stats(db)
    cache_invalidate("predictions_")
    cache_invalidate("teams_")
    return {"results": result}


@router.post("/generate-predictions")
def generate_predictions(db: Session = Depends(get_db), _: None = Depends(_check_token)):
    result = generate_all_predictions(db)
    cache_invalidate("predictions_")
    cache_invalidate("tickets_")
    return result


@router.post("/sync-results")
def sync_results(db: Session = Depends(get_db), _: None = Depends(_check_token)):
    result = sync_all_results(db)
    cache_invalidate("results_")
    cache_invalidate("matches_")
    return {"results": result}


# ---------------------------------------------------------------------------
# Cache admin
# ---------------------------------------------------------------------------
@router.post("/cache/clear")
def cache_clear(
    prefix: str = Query(None, description="Optionnel : ne vide que ce préfixe"),
    _: None = Depends(_check_token),
):
    n = cache_invalidate(prefix)
    return {"invalidated": n, "prefix": prefix}


@router.get("/cache/stats")
def cache_status(_: None = Depends(_check_token)):
    return cache_stats()
