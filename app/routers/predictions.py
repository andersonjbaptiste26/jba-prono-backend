from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import desc

from ..database import get_db
from ..models import Prediction, Event, Match

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
    min_probability: float = Query(80, ge=0, le=100, description="Seuil de confiance minimum. Objectif produit : 80. Peut être abaissé temporairement pour tester avec moins de données."),
    db: Session = Depends(get_db),
):
    """GET /predictions/best — la page 'Best Picks'. Seuil réglable via min_probability
    (80 par défaut, l'objectif produit officiel)."""
    rows = (
        db.query(Prediction)
        .filter(Prediction.probability >= min_probability)
        .order_by(desc(Prediction.probability))
        .limit(limit)
        .all()
    )
    return [_serialize(p) for p in rows]


def _serialize(p: Prediction) -> dict:
    event = p.event
    match = event.match if event else None
    return {
        "prediction_id": p.id,
        "match": f"{match.home_team.name} vs {match.away_team.name}" if match else None,
        "kickoff_at": match.kickoff_at.isoformat() if match else None,
        "event": event.label if event else None,
        "probability": float(p.probability),
        "confidence_tier": p.confidence_tier,
        "odds": float(event.odds_value) if event and event.odds_value else None,
        "explanation": p.explanation,
    }
