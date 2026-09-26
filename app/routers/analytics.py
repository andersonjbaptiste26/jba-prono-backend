"""
Analytics minimaliste :
- POST /analytics/ping    → INSERT ou UPDATE d'une session
- GET  /analytics/stats   → total utilisateurs + historique N jours

Aucune IP n'est stockée. Seul un session_id anonyme est conservé.
"""
from datetime import date, datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session
from sqlalchemy import func
from pydantic import BaseModel

from ..database import get_db
from ..models import AnalyticsSession

router = APIRouter(prefix="/analytics", tags=["analytics"])


class PingIn(BaseModel):
    session_id: str


@router.post("/ping")
def ping(payload: PingIn, request: Request, db: Session = Depends(get_db)):
    """
    - 1ʳᵉ fois pour cette session → INSERT
    - Ensuite → UPDATE last_seen_at uniquement
    """
    ua = (request.headers.get("user-agent", "") or "")[:500]
    today = date.today()
    now = datetime.now(timezone.utc)

    row = (
        db.query(AnalyticsSession)
        .filter(AnalyticsSession.session_id == payload.session_id)
        .first()
    )
    if row:
        row.last_seen_at = now
    else:
        db.add(AnalyticsSession(
            session_id=payload.session_id,
            first_seen_date=today,
            user_agent=ua,
        ))
    db.commit()
    return {"ok": True}


@router.get("/stats")
def stats(
    days: int = Query(15, ge=1, le=90),
    db: Session = Depends(get_db),
):
    """
    Retourne :
      - total_users   : sessions uniques depuis toujours
      - total_today   : nouvelles sessions créées aujourd'hui
      - daily         : liste { date, count } sur N jours
      - period_total  : somme sur la période
    """
    total_users = (
        db.query(func.count(AnalyticsSession.id)).scalar() or 0
    )

    today = date.today()
    total_today = (
        db.query(func.count(AnalyticsSession.id))
        .filter(AnalyticsSession.first_seen_date == today)
        .scalar() or 0
    )

    cutoff = today - timedelta(days=days - 1)
    rows = (
        db.query(AnalyticsSession.first_seen_date, func.count(AnalyticsSession.id))
        .filter(AnalyticsSession.first_seen_date >= cutoff)
        .group_by(AnalyticsSession.first_seen_date)
        .order_by(AnalyticsSession.first_seen_date)
        .all()
    )

    by_date = {r[0].isoformat(): r[1] for r in rows}
    daily = []
    period_total = 0
    for i in range(days):
        d = cutoff + timedelta(days=i)
        key = d.isoformat()
        c = by_date.get(key, 0)
        daily.append({"date": key, "count": c})
        period_total += c

    return {
        "total_users": total_users,
        "total_today": total_today,
        "daily": daily,
        "period_days": days,
        "period_total": period_total,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
