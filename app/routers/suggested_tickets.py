"""
Gestion des tickets suggérés par l'admin.

- POST   /admin/suggested-tickets          → Créer un ticket (admin)
- GET    /admin/suggested-tickets          → Liste tous les tickets (admin, inclut archivés)
- DELETE /admin/suggested-tickets/{id}     → Archiver (admin)
- GET    /suggested-tickets                → Liste publique (users)

Aucune autre route existante n'est modifiée.
"""
import os
from datetime import datetime, timezone
from math import prod

from fastapi import APIRouter, Depends, HTTPException, Header, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List, Optional

from ..database import get_db
from ..models import SuggestedTicket, SuggestedTicketSelection, Event
from ..cache import cached, cache_invalidate

router = APIRouter(tags=["suggested-tickets"])

ADMIN_TOKEN = os.getenv("ADMIN_TOKEN", "")

ALLOWED_ENTITIES = {"ParyajLakay", "ParyajPam", "BelTiFich"}


def _check_token(x_admin_token: str = Header(...)):
    if not ADMIN_TOKEN or x_admin_token != ADMIN_TOKEN:
        raise HTTPException(status_code=401, detail="Token admin invalide.")


# ---------------------------------------------------------------------------
# Schémas Pydantic
# ---------------------------------------------------------------------------
class SelectionIn(BaseModel):
    event_id: Optional[int] = None
    match_label: str
    event_label: str
    event_type: Optional[str] = None
    odds_value: float
    probability: Optional[float] = None


class TicketIn(BaseModel):
    entity: str
    bet_link: str
    selections: List[SelectionIn]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _serialize_ticket(t: SuggestedTicket) -> dict:
    return {
        "id": t.id,
        "entity": t.entity,
        "bet_link": t.bet_link,
        "total_odds": float(t.total_odds),
        "status": t.status,
        "published_at": t.published_at.isoformat() if t.published_at else None,
        "selections": [
            {
                "id": s.id,
                "event_id": s.event_id,
                "match": s.match_label,
                "event": s.event_label,
                "event_type": s.event_type,
                "odds": float(s.odds_value),
                "probability": float(s.probability) if s.probability is not None else None,
            }
            for s in t.selections
        ],
    }


# ---------------------------------------------------------------------------
# ADMIN — Créer
# ---------------------------------------------------------------------------
@router.post("/admin/suggested-tickets")
def create_suggested_ticket(
    payload: TicketIn,
    db: Session = Depends(get_db),
    _: None = Depends(_check_token),
):
    # Validations
    if payload.entity not in ALLOWED_ENTITIES:
        raise HTTPException(
            status_code=400,
            detail=f"Entité invalide. Autorisées : {sorted(ALLOWED_ENTITIES)}",
        )
    if not payload.bet_link or not payload.bet_link.strip():
        raise HTTPException(status_code=400, detail="Le lien ou code du pari est obligatoire.")

    clean_link = payload.bet_link.strip()
    if len(clean_link) > 500:
        raise HTTPException(status_code=400, detail="Le lien/code est trop long (max 500 caractères).")

    if not payload.selections:
        raise HTTPException(status_code=400, detail="Aucune sélection fournie.")
    if len(payload.selections) > 20:
        raise HTTPException(status_code=400, detail="Trop de sélections (max 20).")

    for s in payload.selections:
        if not s.match_label or not s.event_label:
            raise HTTPException(status_code=400, detail="Chaque sélection doit avoir un match et un libellé.")
        if not s.odds_value or s.odds_value <= 1:
            raise HTTPException(status_code=400, detail=f"Cote invalide pour '{s.match_label}'.")

    # Cote totale = produit des cotes
    odds_list = [float(s.odds_value) for s in payload.selections]
    total_odds = prod(odds_list)

    # Créer le ticket
    ticket = SuggestedTicket(
        entity=payload.entity,
        bet_link=clean_link,
        total_odds=round(total_odds, 3),
        status="active",
    )
    db.add(ticket)
    db.flush()

    # Créer les sélections
    for s in payload.selections:
        db.add(SuggestedTicketSelection(
            ticket_id=ticket.id,
            event_id=s.event_id,
            match_label=s.match_label.strip()[:300],
            event_label=s.event_label.strip()[:200],
            event_type=s.event_type,
            odds_value=s.odds_value,
            probability=s.probability,
        ))

    db.commit()
    db.refresh(ticket)

    # Invalider le cache de la liste publique
    cache_invalidate("suggested_tickets_list")

    return _serialize_ticket(ticket)


# ---------------------------------------------------------------------------
# ADMIN — Liste complète (active + archivés)
# ---------------------------------------------------------------------------
@router.get("/admin/suggested-tickets")
def list_all_suggested_tickets(
    db: Session = Depends(get_db),
    _: None = Depends(_check_token),
):
    tickets = (
        db.query(SuggestedTicket)
        .order_by(SuggestedTicket.published_at.desc())
        .all()
    )
    return [_serialize_ticket(t) for t in tickets]


# ---------------------------------------------------------------------------
# ADMIN — Archiver (soft delete)
# ---------------------------------------------------------------------------
@router.delete("/admin/suggested-tickets/{ticket_id}")
def archive_suggested_ticket(
    ticket_id: int,
    db: Session = Depends(get_db),
    _: None = Depends(_check_token),
):
    ticket = db.query(SuggestedTicket).filter(SuggestedTicket.id == ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket introuvable.")
    ticket.status = "archived"
    db.commit()
    cache_invalidate("suggested_tickets_list")
    return {"ok": True, "id": ticket_id, "status": "archived"}


# ---------------------------------------------------------------------------
# PUBLIC — Liste des tickets actifs (users)
# ---------------------------------------------------------------------------
@router.get("/suggested-tickets")
@cached(ttl_seconds=120, prefix="suggested_tickets_list")  # 2 min
def list_public_suggested_tickets(db: Session = Depends(get_db)):
    tickets = (
        db.query(SuggestedTicket)
        .filter(SuggestedTicket.status == "active")
        .order_by(SuggestedTicket.published_at.desc())
        .limit(50)
        .all()
    )
    return [_serialize_ticket(t) for t in tickets]
