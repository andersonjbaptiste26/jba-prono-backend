from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List
from math import prod
from uuid import UUID

from ..database import get_db
from ..models import Bet, BetSelection, Event

router = APIRouter(prefix="/bets", tags=["bets"])


class SelectionIn(BaseModel):
    event_id: int


class BetIn(BaseModel):
    user_id: UUID
    stake: float
    selections: List[SelectionIn]


@router.post("")
def create_bet(payload: BetIn, db: Session = Depends(get_db)):
    """POST /bets — construit le panier, calcule cote totale + gain potentiel."""
    if not payload.selections:
        raise HTTPException(status_code=400, detail="Au moins une sélection est requise")

    event_ids = [s.event_id for s in payload.selections]
    events = db.query(Event).filter(Event.id.in_(event_ids)).all()
    if len(events) != len(event_ids):
        raise HTTPException(status_code=400, detail="Un ou plusieurs événements sont introuvables")

    odds_values = []
    for e in events:
        if e.odds_value is None:
            raise HTTPException(status_code=400, detail=f"Cote manquante pour l'événement {e.id}")
        odds_values.append(float(e.odds_value))

    total_odds = prod(odds_values) if odds_values else 1.0
    potential_gain = round(payload.stake * total_odds, 2)

    bet = Bet(
        user_id=str(payload.user_id),
        stake=payload.stake,
        total_odds=round(total_odds, 3),
        potential_gain=potential_gain,
        status="en_cours",
    )
    db.add(bet)
    db.flush()

    for e in events:
        db.add(BetSelection(bet_id=bet.id, event_id=e.id, odds_value=e.odds_value))

    db.commit()
    return {
        "bet_id": str(bet.id),
        "total_odds": float(bet.total_odds),
        "stake": float(bet.stake),
        "potential_gain": float(bet.potential_gain),
        "potential_profit": round(potential_gain - payload.stake, 2),
    }


@router.get("/history")
def bet_history(user_id: str, db: Session = Depends(get_db)):
    """GET /bets/history — historique + statistiques agrégées."""
    bets = db.query(Bet).filter(Bet.user_id == user_id).order_by(Bet.created_at.desc()).all()

    total = len(bets)
    won = len([b for b in bets if b.status == "gagne"])
    lost = len([b for b in bets if b.status == "perdu"])
    total_stake = sum(float(b.stake) for b in bets)
    profit = sum(
        (float(b.potential_gain) - float(b.stake)) if b.status == "gagne" else -float(b.stake)
        for b in bets if b.status in ("gagne", "perdu")
    )

    return {
        "bets": [
            {
                "id": str(b.id),
                "stake": float(b.stake),
                "total_odds": float(b.total_odds),
                "potential_gain": float(b.potential_gain),
                "status": b.status,
                "created_at": b.created_at.isoformat(),
            }
            for b in bets
        ],
        "stats": {
            "total_bets": total,
            "won": won,
            "lost": lost,
            "success_rate": round((won / (won + lost) * 100), 1) if (won + lost) > 0 else 0,
            "total_stake": total_stake,
            "profit": round(profit, 2),
        },
    }
