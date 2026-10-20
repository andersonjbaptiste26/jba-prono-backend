import os
from datetime import date as date_type, timedelta
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy.orm import Session
from pydantic import BaseModel

from ..database import get_db
from ..models import MatchesBestDay, BestDay
from ..cache import cached

router = APIRouter(tags=["best-day"])

ADMIN_TOKEN = os.getenv("ADMIN_TOKEN", "")


def _check_token(x_admin_token: str = Header(...)):
    if not ADMIN_TOKEN or x_admin_token != ADMIN_TOKEN:
        raise HTTPException(status_code=401, detail="Token admin invalide.")


class TeamIn(BaseModel):
    championnat: str
    classement_2025: Optional[str] = None
    equipe: str
    pays: Optional[str] = None


class MatchIn(BaseModel):
    championnat: str
    equipe_domicile: str
    equipe_exterieur: str
    date: date_type
    heure: Optional[str] = None
    pays: Optional[str] = None


class ImportPayload(BaseModel):
    teams: List[TeamIn] = []
    matches: List[MatchIn] = []


@router.post("/admin/import-matches-json")
def import_matches_json(
    payload: ImportPayload,
    db: Session = Depends(get_db),
    _: None = Depends(_check_token),
):
    teams_added, teams_skipped = 0, 0
    for t in payload.teams:
        exists = db.query(MatchesBestDay).filter(
            MatchesBestDay.championnat == t.championnat,
            MatchesBestDay.equipe == t.equipe,
        ).first()
        if exists:
            teams_skipped += 1
            continue
        db.add(MatchesBestDay(
            championnat=t.championnat,
            classement_2025=t.classement_2025,
            equipe=t.equipe,
            pays=t.pays,
        ))
        teams_added += 1

    matches_added, matches_skipped = 0, 0
    for m in payload.matches:
        exists = db.query(BestDay).filter(
            BestDay.championnat == m.championnat,
            BestDay.equipe_domicile == m.equipe_domicile,
            BestDay.equipe_exterieur == m.equipe_exterieur,
            BestDay.date == m.date,
        ).first()
        if exists:
            matches_skipped += 1
            continue
        db.add(BestDay(
            championnat=m.championnat,
            equipe_domicile=m.equipe_domicile,
            equipe_exterieur=m.equipe_exterieur,
            date=m.date,
            heure=m.heure,
            status="Not Yet",
            pays=m.pays,
        ))
        matches_added += 1

    db.commit()

    from ..cache import cache_invalidate
    cache_invalidate("best_day_")

    return {
        "teams_added": teams_added,
        "teams_deja_existantes": teams_skipped,
        "matches_added": matches_added,
        "matches_deja_existants": matches_skipped,
    }


# ============================================================
# FONCTION DE NETTOYAGE AUTOMATIQUE
# Supprime les matchs de plus de 1 jour (J-1 et avant)
# ============================================================
def _cleanup_old_matches(db: Session) -> int:
    """
    Supprime les matchs du best_day dont la date est < J-1.
    Garde uniquement : J-1, J, J+1, J+2, ...
    
    Retourne le nombre de matchs supprimés.
    """
    today = date_type.today()
    cutoff_date = today - timedelta(days=1)  # J-1
    
    deleted = db.query(BestDay).filter(
        BestDay.date < cutoff_date
    ).delete(synchronize_session=False)
    
    if deleted > 0:
        db.commit()
        print(f"[Best Day] 🧹 {deleted} match(s) obsolète(s) supprimé(s) (cutoff: {cutoff_date})")
    
    return deleted


@router.get("/best-day/matches")
@cached(ttl_seconds=1500, prefix="best_day_matches")  # 25 min
def list_best_day_matches(db: Session = Depends(get_db)):
    today = date_type.today()

    # ========== NETTOYAGE AUTOMATIQUE ==========
    # Supprime les matchs de J-2 et avant
    deleted_count = _cleanup_old_matches(db)
    if deleted_count > 0:
        # Invalide le cache car la DB a changé
        from ..cache import cache_invalidate
        cache_invalidate("best_day_")
    # ==========================================

    # Marque les matchs du passé (hier) comme "Finish"
    db.query(BestDay).filter(
        BestDay.date < today, BestDay.status == "Not Yet"
    ).update({"status": "Finish"})
    db.commit()

    # Récupère la liste des équipes favorites
    favorite_teams = {row.equipe for row in db.query(MatchesBestDay.equipe).all()}

    # Récupère les matchs d'aujourd'hui et futurs
    matches = (
        db.query(BestDay)
        .filter(BestDay.date >= today)
        .order_by(BestDay.date, BestDay.heure)
        .all()
    )

    result = []
    for m in matches:
        # Garde le match si AU MOINS UNE équipe est favorite
        home_is_fav = m.equipe_domicile in favorite_teams
        away_is_fav = m.equipe_exterieur in favorite_teams

        if not home_is_fav and not away_is_fav:
            continue

        result.append({
            "id": m.id,
            "championnat": m.championnat,
            "equipe_domicile": m.equipe_domicile,
            "equipe_exterieur": m.equipe_exterieur,
            "date": m.date.isoformat(),
            "heure": m.heure,
            "status": m.status,
            "pays": m.pays,
        })
    return result


@router.get("/best-day/teams")
@cached(ttl_seconds=7200, prefix="best_day_teams")  # 2 h
def list_favorite_teams(db: Session = Depends(get_db)):
    rows = db.query(MatchesBestDay).order_by(
        MatchesBestDay.championnat, MatchesBestDay.classement_2025
    ).all()
    return [
        {
            "id": r.id,
            "championnat": r.championnat,
            "classement_2025": r.classement_2025,
            "equipe": r.equipe,
            "pays": r.pays,
        }
        for r in rows
    ]
