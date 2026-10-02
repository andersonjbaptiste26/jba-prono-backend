import os
import re
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Header
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import SessionLocal
from ..models import Ad


router = APIRouter(tags=["ads"])

ADMIN_TOKEN = os.getenv("ADMIN_TOKEN", "")
ALLOWED_DURATIONS = {7, 30, 90, 180}


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def require_admin(x_admin_token: str = Header(default="")):
    if ADMIN_TOKEN and x_admin_token != ADMIN_TOKEN:
        raise HTTPException(status_code=401, detail="Token admin invalide")
    return True


def convert_drive_url(url: str) -> str:
    """Convertit un lien Google Drive partagé en URL directe exploitable dans <img src>."""
    if not url:
        return url
    s = url.strip()
    m = re.search(r"/file/d/([^/?#]+)", s)
    if m:
        return f"https://lh3.googleusercontent.com/d/{m.group(1)}"
    m = re.search(r"[?&]id=([^&#]+)", s)
    if m:
        return f"https://lh3.googleusercontent.com/d/{m.group(1)}"
    return s


# ============================================================
# SCHÉMAS PYDANTIC
# ============================================================
class AdCreate(BaseModel):
    advertiser_name: Optional[str] = Field(default=None, max_length=120)
    image_url: str
    target_url: str
    duration_days: int


class AdUpdate(BaseModel):
    is_active: Optional[bool] = None
    display_order: Optional[int] = None
    advertiser_name: Optional[str] = None


class AdRenew(BaseModel):
    duration_days: int


# ============================================================
# ENDPOINT PUBLIC (utilisé par app.html)
# ============================================================
@router.get("/ads/active")
def list_active_ads(db: Session = Depends(get_db)):
    now = datetime.utcnow()
    stmt = (
        select(Ad)
        .where(Ad.is_active == True, Ad.expires_at > now)
        .order_by(Ad.display_order.asc(), Ad.id.asc())
    )
    rows = db.execute(stmt).scalars().all()
    return [
        {
            "id": a.id,
            "image_url": a.image_url,
            "target_url": a.target_url,
            "advertiser_name": a.advertiser_name,
        }
        for a in rows
    ]


# ============================================================
# ENDPOINTS ADMIN (utilisés par index_dashboard.html)
# ============================================================
@router.get("/admin/ads", dependencies=[Depends(require_admin)])
def list_all_ads(db: Session = Depends(get_db)):
    now = datetime.utcnow()
    stmt = select(Ad).order_by(Ad.display_order.asc(), Ad.id.desc())
    rows = db.execute(stmt).scalars().all()
    out = []
    for a in rows:
        expired = a.expires_at <= now
        days_left = max(0, (a.expires_at - now).days) if not expired else 0
        out.append({
            "id": a.id,
            "advertiser_name": a.advertiser_name,
            "image_url": a.image_url,
            "target_url": a.target_url,
            "duration_days": a.duration_days,
            "display_order": a.display_order,
            "is_active": a.is_active,
            "created_at": a.created_at.isoformat(),
            "expires_at": a.expires_at.isoformat(),
            "is_expired": expired,
            "days_left": days_left,
        })
    return out


@router.post("/admin/ads", dependencies=[Depends(require_admin)])
def create_ad(payload: AdCreate, db: Session = Depends(get_db)):
    if payload.duration_days not in ALLOWED_DURATIONS:
        raise HTTPException(400, f"Durée invalide. Autorisé : {sorted(ALLOWED_DURATIONS)}")

    image_url = convert_drive_url(payload.image_url)
    now = datetime.utcnow()
    ad = Ad(
        advertiser_name=(payload.advertiser_name or "").strip() or None,
        image_url=image_url,
        target_url=payload.target_url.strip(),
        duration_days=payload.duration_days,
        display_order=0,
        is_active=True,
        created_at=now,
        expires_at=now + timedelta(days=payload.duration_days),
    )
    db.add(ad)
    db.commit()
    db.refresh(ad)
    return {"id": ad.id, "image_url": ad.image_url, "expires_at": ad.expires_at.isoformat()}


@router.patch("/admin/ads/{ad_id}", dependencies=[Depends(require_admin)])
def update_ad(ad_id: int, payload: AdUpdate, db: Session = Depends(get_db)):
    ad = db.get(Ad, ad_id)
    if not ad:
        raise HTTPException(404, "Pub introuvable")
    if payload.is_active is not None:
        ad.is_active = payload.is_active
    if payload.display_order is not None:
        ad.display_order = payload.display_order
    if payload.advertiser_name is not None:
        ad.advertiser_name = payload.advertiser_name.strip() or None
    db.commit()
    return {"ok": True}


@router.post("/admin/ads/{ad_id}/renew", dependencies=[Depends(require_admin)])
def renew_ad(ad_id: int, payload: AdRenew, db: Session = Depends(get_db)):
    if payload.duration_days not in ALLOWED_DURATIONS:
        raise HTTPException(400, f"Durée invalide. Autorisé : {sorted(ALLOWED_DURATIONS)}")

    ad = db.get(Ad, ad_id)
    if not ad:
        raise HTTPException(404, "Pub introuvable")

    now = datetime.utcnow()
    base = ad.expires_at if ad.expires_at > now else now
    ad.expires_at = base + timedelta(days=payload.duration_days)
    ad.is_active = True
    db.commit()
    return {"ok": True, "expires_at": ad.expires_at.isoformat()}


@router.delete("/admin/ads/{ad_id}", dependencies=[Depends(require_admin)])
def delete_ad(ad_id: int, db: Session = Depends(get_db)):
    ad = db.get(Ad, ad_id)
    if not ad:
        raise HTTPException(404, "Pub introuvable")
    db.delete(ad)
    db.commit()
    return {"ok": True}
