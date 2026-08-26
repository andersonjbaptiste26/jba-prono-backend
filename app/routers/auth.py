"""
Système d'accès par code d'invitation. Un code = une personne = un compte
permanent. Le même code sert à la fois pour le premier accès et pour
retrouver son compte depuis un autre appareil/navigateur (récupération).
"""
import uuid as uuid_lib
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel

from ..database import get_db
from ..models import InvitationCode, User

router = APIRouter(prefix="/auth", tags=["auth"])


class RedeemIn(BaseModel):
    code: str


@router.post("/redeem")
def redeem_code(payload: RedeemIn, db: Session = Depends(get_db)):
    code = payload.code.strip().upper()
    invitation = db.query(InvitationCode).filter(InvitationCode.code == code).first()

    if not invitation:
        raise HTTPException(status_code=404, detail="Code d'invitation invalide.")

    if invitation.user_id:
        return {"user_id": str(invitation.user_id), "is_new": False}

    new_user = User(
        id=uuid_lib.uuid4(),
        email=f"invite-{code.lower()}@jbaprono.local",
        password_hash="",
        display_name=invitation.label or "Utilisateur",
    )
    db.add(new_user)
    db.flush()

    invitation.user_id = new_user.id
    from sqlalchemy import func
    invitation.used_at = func.now()

    db.commit()
    return {"user_id": str(new_user.id), "is_new": True}
