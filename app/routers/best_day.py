"""
Import d'une liste de matchs favoris depuis un fichier JSON.
"""
import os
from datetime import date as date_type
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Header, Response
from sqlalchemy.orm import Session
from pydantic import BaseModel

from ..database import get_db
from ..models import MatchesBestDay, BestDay
from ..utils.cache import cache_memory, invalidate_cache

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
    response: Response,
    db: Session = Depends(get_db),
    _: None = Depends(_check_token),
):
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"

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
            pays=t.pays
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
            pays=m.pays
        ))
        matches_added += 1

    db.commit()

    # 🔄 On invalide les caches après import
    invalidate_cache("bestday_matches")
    invalidate_cache("bestday_teams")
    print("🔄 Caches Best Day invalidés après import")

    return {
        "teams_added": teams_added,
        "teams_deja_existantes": teams_skipped,
        "matches_added": matches_added,
        "matches_deja_existants": matches_skipped,
    }


@router.get("/best-day/matches")
@cache_memory(ttl_seconds=1800, key="bestday_matches")  # 🆕 10 min → 30 min
def list_best_day_matches(response: Response, db: Session = Depends(get_db)):
    response.headers["Cache-Control"] = "public, max-age=1800, s-maxage=1800, stale-while-revalidate=3600"

    today = date_type.today()

    db.query(BestDay).filter(
        BestDay.date < today, BestDay.status == "Not Yet"
    ).update({"status": "Finish"})
    db.commit()

    favorite_teams = {row.equipe for row in db.query(MatchesBestDay.equipe).all()}

    matches = (
        db.query(BestDay)
        .filter(BestDay.date >= today)
        .order_by(BestDay.date, BestDay.heure)
        .all()
    )

    result = []
    for m in matches:
        if m.equipe_domicile in favorite_teams and m.equipe_exterieur in favorite_teams:
            continue
        result.append({
            "id": m.id,
            "championnat": m.championnat,
            "equipe_domicile": m.equipe_domicile,
            "equipe_exterieur": m.equipe_exterieur,
            "date": m.date.isoformat(),
            "heure": m.heure,
            "status": m.status,
            "pays": m.pays
        })
    return result


@router.get("/best-day/teams")
@cache_memory(ttl_seconds=7200, key="bestday_teams")  # 🆕 30 min → 2 h
def list_favorite_teams(response: Response, db: Session = Depends(get_db)):
    response.headers["Cache-Control"] = "public, max-age=7200, s-maxage=7200, stale-while-revalidate=14400"

    rows = db.query(MatchesBestDay).order_by(MatchesBestDay.championnat, MatchesBestDay.classement_2025).all()
    return [
        {
            "id": r.id,
            "championnat": r.championnat,
            "classement_2025": r.classement_2025,
            "equipe": r.equipe,
            "pays": r.pays
        }
        for r in rows
    ]
