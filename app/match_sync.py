import json
import os
import urllib.request
import urllib.error
from datetime import datetime, timedelta
import logging
import psycopg2
import psycopg2.extras

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("match_sync")

def get_db_connection():
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        raise Exception("La variable d'environnement DATABASE_URL n'est pas configurée.")
    return psycopg2.connect(database_url, cursor_factory=psycopg2.extras.RealDictCursor)

def sync_teams_and_fetch_matches_to_neon():
    logger.info("Début de la synchronisation des matchs via Groq...")
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        cur.execute("SELECT country, league, team_name FROM global_teams;")
        db_teams = cur.fetchall()
        
        if not db_teams:
            logger.error("Aucune équipe trouvée dans la table global_teams.")
            cur.close()
            conn.close()
            return False

        teams_summary = []
        for row in db_teams:
            teams_summary.append(f"- {row['team_name']} ({row['league']}, {row['country']})")

        teams_str = "\n".join(teams_summary[:40])
        today_str = datetime.now().strftime("%Y-%m-%d")
        end_date_str = (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d")

        api_key = os.environ.get("GROQ_API_KEY")
        if not api_key:
            logger.error("Clé API GROQ_API_KEY introuvable dans l'environnement Railway.")
            cur.close()
            conn.close()
            return False

        logger.info(f"Envoi de la requête à Groq pour {min(len(db_teams), 40)} équipes...")

        prompt = f"""
        Aujourd'hui nous sommes le {today_str}. Donne les matchs officiels de football prévus entre le {today_str} et le {end_date_str} pour ces équipes :
        {teams_str}

        Renvoie UNIQUEMENT un tableau JSON valide (sans texte additionnel, sans balises markdown autour) avec cette structure exacte :
        [
          {{
            "date": "YYYY-MM-DD",
            "home_team": "Nom équipe domicile",
            "away_team": "Nom équipe extérieur",
            "league": "Nom du championnat",
            "time": "HH:MM",
            "probability": 78,
            "tip": "1X — Domicile ou Nul"
          }}
        ]
        Si tu n'as pas de certitude sur un match exact à ces dates, renvoie un tableau vide [].
        """

        url = "https://api.groq.com/openai/v1/chat/completions"
        payload = {
            "model": "llama-3.1-8b-instant",  # Modèle mis à jour et garanti disponible
            "messages": [
                {"role": "system", "content": "Tu es un expert en football et en analyse de données sportives. Tu réponds toujours en JSON strict."},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.1
        }

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }

        req = urllib.request.Request(
            url,
            data=bytes(json.dumps(payload), encoding="utf-8"),
            headers=headers,
            method="POST"
        )

        matches_list = []
        try:
            with urllib.request.urlopen(req, timeout=40) as response:
                res_data = json.loads(response.read().decode("utf-8"))
                choices = res_data.get("choices", [])
                if choices:
                    text_response = choices[0].get("message", {}).get("content", "").strip()
                    
                    if "```json" in text_response:
                        text_response = text_response.split("```json")[1].split("```")[0].strip()
                    elif "```" in text_response:
                        text_response = text_response.split("```")[1].split("```")[0].strip()
                    
                    matches_list = json.loads(text_response)
        except urllib.error.HTTPError as e:
            error_body = e.read().decode("utf-8")
            logger.error(f"Erreur HTTP Groq ({e.code}) : {error_body}")
            cur.close()
            conn.close()
            return False
        except Exception as e:
            logger.error(f"Erreur inattendue lors de l'appel Groq : {e}")
            cur.close()
            conn.close()
            return False

        if not isinstance(matches_list, list) or len(matches_list) == 0:
            logger.warning("Aucun match retourné par l'IA ou format JSON invalide.")
            cur.close()
            conn.close()
            return False

        logger.info(f"{len(matches_list)} matchs reçus de l'IA. Insertion dans Neon...")

        cur.execute("DELETE FROM matches_cache WHERE match_date < CURRENT_DATE;")

        for m in matches_list:
            cur.execute("""
                INSERT INTO matches_cache (match_date, home_team, away_team, league, match_time, probability, tip, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
            """, (
                m.get("date"),
                m.get("home_team"),
                m.get("away_team"),
                m.get("league"),
                m.get("time", "19:00"),
                m.get("probability", 75),
                m.get("tip", "1X")
            ))

        conn.commit()
        cur.close()
        conn.close()
        logger.info(f"Succès total : {len(matches_list)} matchs insérés dans Neon via Groq.")
        return True

    except Exception as e:
        logger.error(f"Erreur générale critique dans la synchronisation : {e}")
        return False
