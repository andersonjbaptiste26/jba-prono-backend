from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import desc

from ..database import get_db
from ..models import TeamRating, Team

router = APIRouter(prefix="/teams", tags=["teams"])


@router.get("/top")
def top_teams(
    league_id: int = Query(..., description="ID du championnat"),
    limit: int = 5,
    db: Session = Depends(get_db),
):
    """GET /teams/top?league_id=... — les 5 meilleures équipes, calculées dynamiquement
    par le Team Rating (jamais codées en dur)."""
    rows = (
        db.query(TeamRating)
        .filter(TeamRating.league_id == league_id)
        .order_by(desc(TeamRating.rating))
        .limit(limit)
        .all()
    )
    return [
        {
            "team_id": r.team_id,
            "team_name": db.query(Team).get(r.team_id).name,
            "rating": float(r.rating),
            "sub_scores": {
                "forme": float(r.form_score or 0),
                "attaque": float(r.attack_score or 0),
                "defense": float(r.defense_score or 0),
                "domicile_exterieur": float(r.home_away_score or 0),
                "saison": float(r.season_score or 0),
                "h2h": float(r.h2h_score or 0),
                "effectif": float(r.squad_score or 0),
            },
        }
        for r in rows
    ]
