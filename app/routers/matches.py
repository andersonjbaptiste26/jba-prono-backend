from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Match

router = APIRouter(prefix="/matches", tags=["matches"])


@router.get("")
def list_matches(db: Session = Depends(get_db)):
    """GET /matches"""
    matches = db.query(Match).order_by(Match.kickoff_at).all()
    return [_serialize(m) for m in matches]


@router.get("/{match_id}")
def get_match(match_id: int, db: Session = Depends(get_db)):
    """GET /matches/:id"""
    match = db.query(Match).filter(Match.id == match_id).first()
    if not match:
        raise HTTPException(status_code=404, detail="Match introuvable")
    return _serialize(match, detailed=True)


def _serialize(m: Match, detailed: bool = False) -> dict:
    data = {
        "id": m.id,
        "home_team": m.home_team.name,
        "away_team": m.away_team.name,
        "kickoff_at": m.kickoff_at.isoformat(),
        "status": m.status,
        "home_score": m.home_score,
        "away_score": m.away_score,
    }
    if detailed:
        data["events"] = [
            {"id": e.id, "type": e.type, "label": e.label, "odds": float(e.odds_value) if e.odds_value else None}
            for e in m.events
        ]
    return data
