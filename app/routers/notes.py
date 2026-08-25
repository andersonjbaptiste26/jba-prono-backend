import csv
import io
import uuid as uuid_lib
from datetime import date as date_type
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional

from ..database import get_db
from ..models import DailyNote, User

router = APIRouter(prefix="/notes", tags=["notes"])


class NoteIn(BaseModel):
    user_id: str
    date: Optional[date_type] = None
    capital_investissement: Optional[float] = None
    bet_trade: Optional[float] = None
    bet_statut: Optional[str] = None
    argent: Optional[float] = None
    notebook: Optional[str] = None


def _get_or_create_user(db: Session, user_id: str) -> str:
    try:
        parsed = uuid_lib.UUID(user_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="user_id doit être un UUID valide.")
    user = db.query(User).filter(User.id == parsed).first()
    if not user:
        user = User(id=parsed, email=f"anon-{parsed}@device.local", password_hash="", display_name="Utilisateur anonyme")
        db.add(user)
        db.flush()
    return str(parsed)


@router.post("")
def create_note(payload: NoteIn, db: Session = Depends(get_db)):
    """POST /notes — ajoute une ligne au journal. Stocké durablement en
    base de données, filtré par utilisateur."""
    user_id = _get_or_create_user(db, payload.user_id)

    if payload.bet_statut and payload.bet_statut not in ("gagne", "perdu"):
        raise HTTPException(status_code=400, detail="bet_statut doit être 'gagne' ou 'perdu'.")

    note = DailyNote(
        user_id=user_id,
        date=payload.date or date_type.today(),
        capital_investissement=payload.capital_investissement,
        bet_trade=payload.bet_trade,
        bet_statut=payload.bet_statut,
        argent=payload.argent,
        notebook=payload.notebook,
    )
    db.add(note)
    db.commit()
    db.refresh(note)
    return _serialize(note)


@router.get("")
def list_notes(user_id: str, db: Session = Depends(get_db)):
    """GET /notes?user_id=... — le journal complet, plus récent en premier."""
    try:
        parsed = uuid_lib.UUID(user_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="user_id invalide")
    notes = db.query(DailyNote).filter(DailyNote.user_id == parsed).order_by(DailyNote.date.desc()).all()
    return [_serialize(n) for n in notes]


@router.put("/{note_id}")
def update_note(note_id: int, payload: NoteIn, db: Session = Depends(get_db)):
    note = db.query(DailyNote).filter(DailyNote.id == note_id).first()
    if not note:
        raise HTTPException(status_code=404, detail="Ligne introuvable")
    if payload.date is not None:
        note.date = payload.date
    if payload.capital_investissement is not None:
        note.capital_investissement = payload.capital_investissement
    if payload.bet_trade is not None:
        note.bet_trade = payload.bet_trade
    if payload.bet_statut is not None:
        note.bet_statut = payload.bet_statut
    if payload.argent is not None:
        note.argent = payload.argent
    if payload.notebook is not None:
        note.notebook = payload.notebook
    db.commit()
    db.refresh(note)
    return _serialize(note)


@router.delete("/{note_id}")
def delete_note(note_id: int, db: Session = Depends(get_db)):
    note = db.query(DailyNote).filter(DailyNote.id == note_id).first()
    if not note:
        raise HTTPException(status_code=404, detail="Ligne introuvable")
    db.delete(note)
    db.commit()
    return {"status": "supprimé"}


@router.get("/export")
def export_notes_csv(user_id: str, db: Session = Depends(get_db)):
    """GET /notes/export?user_id=... — télécharge le journal en CSV
    (ouvrable directement dans Excel/Google Sheets)."""
    try:
        parsed = uuid_lib.UUID(user_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="user_id invalide")
    notes = db.query(DailyNote).filter(DailyNote.user_id == parsed).order_by(DailyNote.date.desc()).all()

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["Date", "Capital Investissement", "BetTrade", "BetStatut", "Argent", "NoteBook"])
    for n in notes:
        writer.writerow([
            n.date.isoformat() if n.date else "",
            n.capital_investissement, n.bet_trade, n.bet_statut, n.argent, n.notebook or "",
        ])
    buffer.seek(0)

    return StreamingResponse(
        iter([buffer.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=journal_jba_prono.csv"},
    )


def _serialize(n: DailyNote) -> dict:
    return {
        "id": n.id,
        "date": n.date.isoformat() if n.date else None,
        "capital_investissement": float(n.capital_investissement) if n.capital_investissement is not None else None,
        "bet_trade": float(n.bet_trade) if n.bet_trade is not None else None,
        "bet_statut": n.bet_statut,
        "argent": float(n.argent) if n.argent is not None else None,
        "notebook": n.notebook,
}
