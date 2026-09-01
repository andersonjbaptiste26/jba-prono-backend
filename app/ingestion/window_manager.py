import json
import os
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from ..models import Match

def load_catalog():
    """Charge le catalogue mondial des équipes."""
    path = os.path.join(os.path.dirname(__file__), "..", "data", "global_teams.json")
    if not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def clean_old_matches(db: Session):
    """
    Auto-update / Nettoyage : Supprime les matchs dont la date est passée 
    (par exemple de plus de 7 jours) pour garder la base légère.
    """
    threshold_date = datetime.utcnow() - timedelta(days=7)
    deleted_rows = db.query(Match).filter(Match.utc_date < threshold_date).delete()
    db.commit()
    return deleted_rows

def save_weekly_matches(db: Session, incoming_matches: list[dict]):
    """
    Enregistre les matchs des 7 jours à venir en vérifiant qu'ils 
    appartiennent bien au catalogue mondial.
    """
    # 1. Nettoyer d'abord les anciens matchs périmés
    clean_old_matches(db)
    
    catalog = load_catalog()
    tracked_teams = set()
    for country, data in catalog.items():
        tracked_teams.update(data.get("equipes", []))

    now = datetime.utcnow()
    max_date = now + timedelta(days=7)
    
    added_count = 0
    for m in incoming_matches:
        match_date = datetime.fromisoformat(m["utc_date"])
        
        # Filtrer : Doit être dans la fenêtre des 7 jours à venir
        if not (now <= match_date <= max_date):
            continue
            
        home = m.get("home_team")
        away = m.get("away_team")
        
        # Filtrer : L'une des équipes doit appartenir à votre catalogue
        if home in tracked_teams or away in tracked_teams:
            exists = db.query(Match).filter(
                Match.home_team == home,
                Match.away_team == away,
                Match.utc_date == match_date
            ).first()
            
            if not exists:
                new_match = Match(
                    home_team=home,
                    away_team=away,
                    utc_date=match_date,
                    league_name=m.get("league_name", "International"),
                    status="scheduled"
                )
                db.add(new_match)
                added_count += 1
                
    db.commit()
    return {"status": "success", "new_matches_saved": added_count}
