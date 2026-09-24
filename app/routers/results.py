"""
Route publique : renvoie les résultats des matchs terminés récents
(aujourd'hui + les 7 derniers jours). Utilisée par le front pour
régler localement les paris (dans localStorage).
"""
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Match

router = APIRouter(prefix="/results", tags=["results"])


@router.get("/recent")
def recent_results(
    days: int = Query(7, ge=1, le=30, description="Nombre de jours en arrière"),
    db: Session = Depends(get_db),
):
    """
    Renvoie tous les événements des matchs terminés sur la fenêtre
    [aujourd'hui - `days`, aujourd'hui].

    Format :
    [
      {
        "event_id": 42,
        "match_id": 5,
        "match": "Arsenal vs Chelsea",
        "event_type": "resultat",
        "event_label": "1 — Victoire domicile",
        "home_score": 2,
        "away_score": 1,
        "kickoff_at": "2026-09-24T18:00:00+00:00"
      },
      ...
    ]
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    matches = (
        db.query(Match)
        .filter(
            Match.status == "finished",
            Match.kickoff_at >= cutoff,
            Match.home_score.isnot(None),
            Match.away_score.isnot(None),
        )
        .order_by(Match.kickoff_at.desc())
        .all()
    )

    result = []
    for m in matches:
        match_label = (
            f"{m.home_team.name} vs {m.away_team.name}"
            if m.home_team and m.away_team
            else None
        )
        for e in m.events:
            result.append({
                "event_id": e.id,
                "match_id": m.id,
                "match": match_label,
                "event_type": e.type,
                "event_label": e.label,
                "home_score": m.home_score,
                "away_score": m.away_score,
                "kickoff_at": m.kickoff_at.isoformat() if m.kickoff_at else None,
            })

    return result
