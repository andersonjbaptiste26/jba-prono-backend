from fastapi import APIRouter, HTTPException, UploadFile, File
import json
import os
import psycopg2
import psycopg2.extras

router = APIRouter()

def get_db_connection():
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        raise Exception("La variable d'environnement DATABASE_URL n'est pas configurée.")
    return psycopg2.connect(database_url, cursor_factory=psycopg2.extras.RealDictCursor)

@router.post("/admin/upload-json-matches")
async def upload_json_matches(file: UploadFile = File(...)):
    """
    Endpoint pour téléverser un fichier JSON contenant les matchs de la semaine
    et mettre à jour la base de données Neon.
    """
    try:
        contents = await file.read()
        matches_list = json.loads(contents.decode("utf-8"))
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Le fichier fourni n'est pas un format JSON valide.")

    if not isinstance(matches_list, list):
        raise HTTPException(status_code=400, detail="Le fichier JSON doit contenir une liste de matchs.")

    try:
        # Utilisation des context managers pour garantir la fermeture propre et le commit/rollback automatique
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                # Nettoyage optionnel des matchs passés
                cur.execute("DELETE FROM matches_cache WHERE match_date < CURRENT_DATE;")

                inserted_count = 0
                for m in matches_list:
                    cur.execute("""
                        INSERT INTO matches_cache (match_date, home_team, away_team, league, match_time, probability, tip, updated_at)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
                    """, (
                        m.get("date"),
                        m.get("home_team"),
                        m.get("away_team"),
                        m.get("league"),
                        m.get("time", "20:00"),
                        m.get("probability", 70),
                        m.get("tip", "1X"),
                    ))
                    inserted_count += 1
                    
        # La connexion et le curseur se ferment d'eux-mêmes ici, et les changements sont commités.

        return {
            "status": "success",
            "message": f"{inserted_count} matchs importés avec succès depuis le fichier JSON !"
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur lors de l'importation du JSON : {str(e)}")
