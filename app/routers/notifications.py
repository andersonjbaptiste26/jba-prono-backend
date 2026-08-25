from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
import uuid as uuid_lib

from ..database import get_db
from ..models import Notification

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("")
def list_notifications(user_id: str, unread_only: bool = False, db: Session = Depends(get_db)):
    """GET /notifications?user_id=... — liste des notifications de l'utilisateur."""
    try:
        parsed = uuid_lib.UUID(user_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="user_id invalide")

    query = db.query(Notification).filter(Notification.user_id == parsed)
    if unread_only:
        query = query.filter(Notification.read == False)  # noqa: E712
    rows = query.order_by(Notification.created_at.desc()).limit(50).all()

    return {
        "notifications": [
            {
                "id": n.id,
                "message": n.message,
                "created_at": n.created_at.isoformat(),
                "read": n.read,
                "bet_id": str(n.bet_id) if n.bet_id else None,
            }
            for n in rows
        ],
        "unread_count": db.query(Notification).filter(
            Notification.user_id == parsed, Notification.read == False  # noqa: E712
        ).count(),
    }


@router.post("/{notification_id}/read")
def mark_as_read(notification_id: int, db: Session = Depends(get_db)):
    notif = db.query(Notification).filter(Notification.id == notification_id).first()
    if not notif:
        raise HTTPException(status_code=404, detail="Notification introuvable")
    notif.read = True
    db.commit()
    return {"status": "ok"}


@router.post("/mark-all-read")
def mark_all_read(user_id: str, db: Session = Depends(get_db)):
    try:
        parsed = uuid_lib.UUID(user_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="user_id invalide")
    db.query(Notification).filter(
        Notification.user_id == parsed, Notification.read == False  # noqa: E712
    ).update({"read": True})
    db.commit()
    return {"status": "ok"}
