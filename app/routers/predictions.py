from collections import defaultdict
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import desc, func

from ..database import get_db
from ..models import Prediction, Event, Match

router = APIRouter(prefix="/predictions", tags=["predictions"])

ODDS_THRESHOLD = 1.35
OTHER_MARKET_THRESHOLD = 70.0


@router.get("")
def list_predictions(
    min_probability: float = Query(0, ge=0, le=100),
    only_upcoming: bool = Query(True, description="Exclut les matchs déjà commencés/joués."),
    db: Session = Depends(get_db),
):
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
    limit: int = 20,
    db: Session = Depends(get_db),
):
    rows = (
        db.query(Prediction)
        .join(Event, Prediction.event_id == Event.id)
        .join(Match, Event.match_id == Match.id)
        .filter(Match.kickoff_at >= func.now())
        .all()
    )

    by_match = defaultdict(list)
    for p in rows:
        by_match[p.event.match_id].append(p)

    selected = []
    for match_id, preds in by_match.items():
        resultat_preds = [p for p in preds if p.event.type == "resultat"]
        other_preds = [p for p in preds if p.event.type != "resultat"]

        best_resultat = max(resultat_preds, key=lambda p: p.probability, default=None)
        resultat_candidate = None
        if best_resultat and best_resultat.event.odds_value and float(best_resultat.event.odds_value) > ODDS_THRESHOLD:
            resultat_candidate = best_resultat

        best_other = max(other_preds, key=lambda p: p.probability, default=None)
        other_candidate = best_other if (best_other and float(best_other.probability) >= OTHER_MARKET_THRESHOLD) else None

        if resultat_candidate and other_candidate:
            chosen = other_candidate if other_candidate.probability > resultat_candidate.probability else resultat_candidate
        elif resultat_candidate:
            chosen = resultat_candidate
        elif other_candidate:
            chosen = other_candidate
        else:
            chosen = None

        if chosen:
            selected.append(chosen)

    selected.sort(key=lambda p: p.event.match.kickoff_at)

    return [_serialize(p) for p in selected[:limit]]


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
        "event_type": event.type if event else None,
        "probability": float(p.probability),
        "confidence_tier": p.confidence_tier,
        "odds": float(event.odds_value) if event and event.odds_value else None,
        "explanation": p.explanation,
    }
