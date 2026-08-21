from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import desc, func

from ..database import get_db
from ..models import Prediction, Event, Match

router = APIRouter(prefix="/predictions", tags=["predictions"])


@router.get("")
def list_predictions(
    min_probability: float = Query(0, ge=0, le=100),
    only_upcoming: bool = Query(True, description="Exclut les matchs déjà commencés/joués."),
    db: Session = Depends(get_db),
):
    """GET /predictions — toutes les prédictions, filtrables par probabilité min."""
    query = (
        db.query(Prediction)
        .join(Event, Prediction.event_id == Event.id)
        .join(Match, Event.match_id == Match.id)
        .filter(Prediction.probability >= min_probability)
    )
    if only_upcoming:
        query = query.filter(Match.kickoff_at >= func.now())
    rows = query.order_by(desc(Prediction.probability)).all()
    return [_serialize(p) for p in rows]


@router.get("/best")
def best_predictions(
    limit: int = 10,
    min_probability: float = Query(80, ge=0, le=100, description="Seuil de confiance minimum. Objectif produit : 80. Peut être abaissé temporairement pour tester avec moins de données."),
    db: Session = Depends(get_db),
):
    rows = (
        db.query(Prediction)
        .join(Event, Prediction.event_id == Event.id)
        .join(Match, Event.match_id == Match.id)
        .filter(Prediction.probability >= min_probability)
        .filter(Match.kickoff_at >= func.now())
        .order_by(desc(Prediction.probability))
        .all()
    )

    best_per_match: dict[int, Prediction] = {}
    for p in rows:
        match_id = p.event.match_id
        if match_id not in best_per_match:
            best_per_match[match_id] = p

    selected = sorted(best_per_match.values(), key=lambda p: p.probability, reverse=True)[:limit]
    return [_serialize(p) for p in selected]


def _serialize(p: Prediction) -> dict:
    event = p.event
    match = event.match if event else None
    return {
        "prediction_id": p.id,
        "event_id": event.id if event else None,
        "match": f"{match.home_team.name} vs {match.away_team.name}" if match else None,
        "home_team": match.home_team.name if match else None,
        "away_team": match.away_team.name if match else None,
        "competition": match.competition.name if match and match.competition else None,
        "kickoff_at": match.kickoff_at.isoformat() if match else None,
        "event": event.label if event else None,
        "probability": float(p.probability),
        "confidence_tier": p.confidence_tier,
        "odds": float(event.odds_value) if event and event.odds_value else None,
        "explanation": p.explanation,
    }
