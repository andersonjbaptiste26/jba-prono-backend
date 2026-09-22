from datetime import datetime, timezone
from math import prod
import uuid as uuid_lib

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List

from ..database import get_db
from ..models import Bet, BetSelection, Event, Prediction, User

router = APIRouter(prefix="/bets", tags=["bets"])


class SelectionIn(BaseModel):
    event_id: int


class BetIn(BaseModel):
    user_id: str
    selections: List[SelectionIn]


def _get_or_create_anonymous_user(db: Session, user_id: str) -> str:
    try:
        parsed = uuid_lib.UUID(user_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="user_id doit être un UUID valide.")

    user = db.query(User).filter(User.id == parsed).first()
    if not user:
        user = User(
            id=parsed,
            email=f"anon-{parsed}@device.local",
            password_hash="",
            display_name="Utilisateur anonyme",
        )
        db.add(user)
        db.flush()
    return str(parsed)


@router.post("")
def create_bet(payload: BetIn, db: Session = Depends(get_db)):
    if not payload.selections:
        raise HTTPException(status_code=400, detail="Aucune sélection fournie.")

    user_id = _get_or_create_anonymous_user(db, payload.user_id)

    event_ids = [s.event_id for s in payload.selections]
    if len(set(event_ids)) != len(event_ids):
        raise HTTPException(status_code=400, detail="Sélections dupliquées.")

    events = db.query(Event).filter(Event.id.in_(event_ids)).all()
    if len(events) != len(event_ids):
        raise HTTPException(status_code=400, detail="Un ou plusieurs événements sont introuvables.")

    missing = [e.id for e in events if e.odds_value is None]
    if missing:
        raise HTTPException(status_code=400, detail=f"Cotes manquantes pour : {missing}")

    now = datetime.now(timezone.utc)
    started = [e.id for e in events if e.match and e.match.kickoff_at < now]
    if started:
        raise HTTPException(status_code=400, detail=f"Matchs déjà commencés : {started}")

    odds_values = [float(e.odds_value) for e in events]
    total_odds = prod(odds_values)

    bet = Bet(
        user_id=user_id,
        stake=None,
        total_odds=round(total_odds, 3),
        potential_gain=None,
        status="en_cours",
    )
    db.add(bet)
    db.flush()

    preds_by_event = {
        p.event_id: float(p.probability)
        for p in db.query(Prediction).filter(Prediction.event_id.in_(event_ids)).all()
    }

    for e in events:
        db.add(BetSelection(
            bet_id=bet.id,
            event_id=e.id,
            odds_value=e.odds_value,
            probability_at_bet=preds_by_event.get(e.id),
        ))

    db.commit()
    return {
        "bet_id": str(bet.id),
        "total_odds": float(bet.total_odds),
        "selections_count": len(events),
    }


@router.get("/history")
def bet_history(user_id: str, db: Session = Depends(get_db)):
    try:
        parsed = uuid_lib.UUID(user_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="user_id invalide.")

    bets = db.query(Bet).filter(Bet.user_id == parsed).order_by(Bet.created_at.desc()).all()

    total = len(bets)
    won = len([b for b in bets if b.status == "gagne"])
    lost = len([b for b in bets if b.status == "perdu"])

    return {
        "bets": [
            {
                "id": str(b.id),
                "total_odds": float(b.total_odds),
                "status": b.status,
                "created_at": b.created_at.isoformat(),
                "selections": [
                    {
                        "match": (
                            f"{s.event.match.home_team.name} vs {s.event.match.away_team.name}"
                            if s.event and s.event.match
                            else None
                        ),
                        "event": s.event.label if s.event else None,
                        "odds": float(s.odds_value),
                        "result": s.result,
                    }
                    for s in b.selections
                ],
            }
            for b in bets
        ],
        "stats": {
            "total_bets": total,
            "won": won,
            "lost": lost,
            "en_cours": total - won - lost,
            "success_rate": round((won / (won + lost) * 100), 1) if (won + lost) > 0 else 0,
        },
    }
