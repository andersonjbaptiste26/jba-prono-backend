from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import desc

from ..database import get_db
from ..models import Prediction

router = APIRouter(prefix="/predictions", tags=["predictions"])


@router.get("")
def list_predictions(
    min_probability: float = Query(0, ge=0, le=100),
    db: Session = Depends(get_db),
):
    """GET /predictions — toutes les prédictions, filtrables par probabilité min."""
    rows = (
        db.query(Prediction)
        .filter(Prediction.probability >= min_probability)
        .order_by(desc(Prediction.probability))
        .all()
    )
    return [_serialize(p) for p in rows]


@router.get("/best")
def best_predictions(
    limit: int = 10,
    db: Session = Depends(get_db),
):
    """GET /predictions/best — la page 'Best Picks' (probabilité >= 80% par défaut)."""
    rows = (
        db.query(Prediction)
        .filter(Prediction.probability >= 80)
        .order_by(desc(Prediction.probability))
        .limit(limit)
        .all()
    )
    return [_serialize(p) for p in rows]


def _serialize(p: Prediction) -> dict:
    event = getattr(p, "event", None)
    match = getattr(event, "match", None) if event else None
    home_team = getattr(match, "home_team", None)
    away_team = getattr(match, "away_team", None)
    match_name = None
    kickoff = None
    if match:
        ht_name = getattr(home_team, "name", None) if home_team else None
        at_name = getattr(away_team, "name", None) if away_team else None
        if ht_name or at_name:
            match_name = f"{ht_name or '?'} vs {at_name or '?'}"
        kickoff = match.kickoff_at.isoformat() if getattr(match, "kickoff_at", None) else None

    return {
        "prediction_id": p.id,
        "match": match_name,
        "kickoff_at": kickoff,
        "event": getattr(event, "label", None),
        "probability": float(p.probability),
        "confidence_tier": p.confidence_tier,
        "odds": float(getattr(event, "odds_value", None)) if event and getattr(event, "odds_value", None) is not None else None,
        "explanation": p.explanation,
    }
