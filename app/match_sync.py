import json
import os
import urllib.request
import urllib.error
from datetime import datetime, timedelta
import psycopg2
import psycopg2.extras

def get_db_connection():
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        raise Exception("La variable d'environnement DATABASE_URL n'est pas configurée.")
    return psycopg2.connect(database_url, cursor_factory=psycopg2.extras.RealDictCursor)

def sync_teams_and_fetch_matches_to_neon():
    try:
        # 1. Récupération des équipes depuis la base de données Neon
        conn = get_db_connection()
        cur = conn.cursor()
        
        cur.execute("SELECT country, league, team_name FROM global_teams;")
        db_teams = cur.fetchall()
        
        if not db_teams:
            print("Aucune équipe trouvée dans la table global_teams.")
            cur.close()
            conn.close()
            return False

        teams_summary = []
        for row in db_teams:
            teams_summary.append(f"- {row['team_name']} ({row['league']}, {row['country']})")

        # On limite à 40 équipes par appel pour garder un prompt optimisé
        teams_str = "\n".join(teams_summary[:40])
        today_str = datetime.now().strftime("%Y-%m-%d")
        end_date_str = (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d")

        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            print("Clé API Gemini introuvable dans l'environnement.")
            cur.close()
            conn.close()
            return False

        # 2. Requête IA + Web avec le modèle mis à jour (gemini-3.6-flash)
        prompt = f"""
        Aujourd'hui nous sommes le {today_str}. Utilise la recherche web pour trouver les vrais prochains matchs officiels de football prévus entre le {today_str} et le {end_date_str} pour ces équipes :
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
        Si aucun match réel n'est trouvé, renvoie un tableau vide [].
        """

        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3.6-flash:generateContent?key={api_key}"
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "tools": [{"googleSearch": {}}]
        }

        req = urllib.request.Request(
            url,
            data=bytes(json.dumps(payload), encoding="utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST"
        )

        matches_list = []
        try:
            with urllib.request.urlopen(req, timeout=40) as response:
                res_data = json.loads(response.read().decode("utf-8"))
                candidates = res_data.get("candidates", [])
                if candidates:
                    content_parts = candidates[0].get("content", {}).get("parts", [])
                    text_response = "".join([p.get("text", "") for p in content_parts]).strip()
                    
                    if "```json" in text_response:
                        text_response = text_response.split("```json")[1].split("```")[0].strip()
                    elif "```" in text_response:
                        text_response = text_response.split("```")[1].split("```")[0].strip()
                    
                    matches_list = json.loads(text_response)
        except urllib.error.HTTPError as e:
            error_body = e.read().decode("utf-8")
            print(f"Erreur HTTP Gemini ({e.code}) : {error_body}")
            cur.close()
            conn.close()
            return False
        except Exception as e:
            print(f"Erreur inattendue lors de l'appel Gemini : {e}")
            cur.close()
            conn.close()
            return False

        if not isinstance(matches_list, list) or len(matches_list) == 0:
            print("Aucun match retourné par l'IA ou format JSON invalide.")
            cur.close()
            conn.close()
            return False

        # 3. Insertion SQL des nouveaux matchs
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
        print(f"Succès : {len(matches_list)} matchs insérés dans Neon depuis la base de données.")
        return True

    except Exception as e:
        print(f"Erreur générale dans la synchronisation : {e}")
        return False
