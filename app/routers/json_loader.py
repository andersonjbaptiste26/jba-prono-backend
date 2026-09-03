from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session
from sqlalchemy import text
import json

# Importation de votre gestionnaire de session (chemin relatif cohérent avec votre structure)
from ..database import get_db

router = APIRouter()

@router.post("/admin/upload-json-matches")
async def upload_json_matches(file: UploadFile = File(...), db: Session = Depends(get_db)):
    """
    Endpoint pour téléverser un fichier JSON et mettre à jour la table matches_cache
    en utilisant SQLAlchemy.
    """
    try:
        contents = await file.read()
        matches_list = json.loads(contents.decode("utf-8"))
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Le fichier fourni n'est pas un format JSON valide.")

    if not isinstance(matches_list, list):
        raise HTTPException(status_code=400, detail="Le fichier JSON doit contenir une liste de matchs.")

    try:
        # 1. Nettoyage des matchs passés via SQLAlchemy text()
        db.execute(text("DELETE FROM matches_cache WHERE match_date < CURRENT_DATE;"))

        inserted_count = 0
        for index, m in enumerate(matches_list):
            # Validation des champs obligatoires
            date_val = m.get("date")
            home_team = m.get("home_team")
            away_team = m.get("away_team")

            if not date_val or not home_team or not away_team:
                raise HTTPException(
                    status_code=400, 
                    detail=f"Erreur à l'élément #{index + 1} : les champs 'date', 'home_team' et 'away_team' sont obligatoires."
                )

            # Sécurisation de la probabilité (gère le cas "75%")
            raw_prob = m.get("probability", 70)
            if isinstance(raw_prob, str):
                raw_prob = raw_prob.replace("%", "").strip()
            try:
                probability = int(raw_prob)
            except (ValueError, TypeError):
                probability = 70

            # 2. Insertion sécurisée en utilisant les paramètres nommés de SQLAlchemy
            db.execute(
                text("""
                    INSERT INTO matches_cache (match_date, home_team, away_team, league, match_time, probability, tip, updated_at)
                    VALUES (:match_date, :home_team, :away_team, :league, :match_time, :probability, :tip, CURRENT_TIMESTAMP)
                """),
                {
                    "match_date": date_val,
                    "home_team": home_team,
                    "away_team": away_team,
                    "league": m.get("league", "Inconnue"),
                    "match_time": m.get("time", "20:00"),
                    "probability": probability,
                    "tip": m.get("tip", "1X")
                }
            )
            inserted_count += 1

        # Validation de la transaction
        db.commit()

        return {
            "status": "success",
            "message": f"{inserted_count} matchs importés avec succès dans matches_cache via SQLAlchemy !"
        }

    except HTTPException as he:
        db.rollback()
        raise he
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Erreur lors de l'importation SQLAlchemy : {str(e)}")
