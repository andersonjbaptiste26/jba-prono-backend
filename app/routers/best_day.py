from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from ..database import get_db
from ..models import Match
from ..ingestion.window_manager import save_weekly_matches

router = APIRouter(prefix="/insights", tags=["Insights & BestDay"])

@router.get("/best-day")
def get_best_day_insights(db: Session = Depends(get_db)):
    """
    Récupère instantanément les matchs des 7 jours à venir pour le bouton flottant,
    les regroupe par jour et identifie le meilleur jour de paris.
    """
    now = datetime.utcnow()
    next_week = now + timedelta(days=7)
    
    # Filtrer uniquement les matchs dans la fenêtre des 7 jours à venir
    matches = db.query(Match).filter(
        Match.utc_date >= now,
        Match.utc_date <= next_week
    ).all()
    
    days_data = {}
    
    for match in matches:
        day_str = match.utc_date.strftime("%Y-%m-%d") # Format YYYY-MM-DD
        if day_str not in days_data:
            days_data[day_str] = {
                "date": day_str,
                "total_matches": 0,
                "success_rate_estimated": 85.0, # Taux estimé pour vos championnats cibles
                "matches": []
            }
        
        days_data[day_str]["total_matches"] += 1
        days_data[day_str]["matches"].append({
            "id": match.id,
            "home_team": match.home_team,
            "away_team": match.away_team,
            "time": match.utc_date.strftime("%H:%M"),
            "league": match.league_name,
            "status": match.status
        })
        
    # Trier par ordre chronologique
    sorted_schedule = sorted(days_data.values(), key=lambda x: x["date"])
    
    # Identifier le "Best Day" (le jour avec le plus de confrontations de votre liste)
    best_day = max(sorted_schedule, key=lambda x: x["total_matches"]) if sorted_schedule else None

    return {
        "status": "success",
        "best_day": best_day,
        "weekly_schedule": sorted_schedule
    }

@router.post("/sync-matches")
def sync_ai_matches(payload: list[dict], db: Session = Depends(get_db)):
    """
    Point de contact pour votre IA open-source ou script de recherche :
    Reçoit la liste brute des matchs trouvés sur le web, les filtre selon
    votre catalogue mondial et actualise la base de données.
    """
    try:
        result = save_weekly_matches(db, payload)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
