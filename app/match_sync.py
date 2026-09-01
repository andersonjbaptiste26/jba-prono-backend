import json
import os
import urllib.request
import urllib.error
from datetime import datetime, timedelta
import psycopg2
import psycopg2.extras

# Fonction utilitaire de connexion à Neon
def get_db_connection():
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        raise Exception("La variable d'environnement DATABASE_URL n'est pas configurée.")
    return psycopg2.connect(database_url, cursor_factory=psycopg2.extras.RealDictCursor)

def sync_teams_and_fetch_matches_to_neon():
    teams_json_path = os.path.join("app", "data", "global_teams.json")
    
    # 1. Lecture du JSON
    if not os.path.exists(teams_json_path):
        print(f"Fichier introuvable : {teams_json_path}")
        return False

    try:
        with open(teams_json_path, "r", encoding="utf-8") as f:
            teams_data = json.load(f)
    except Exception as e:
        print(f"Erreur lecture JSON : {e}")
        return False

    teams_summary = []
    if isinstance(teams_data, dict):
        for country, info in teams_data.items():
            league = info.get("championnat", "")
            equipes = info.get("equipes", [])
            for eq in equipes:
                teams_summary.append(f"- {eq} ({league}, {country})")

    if not teams_summary:
        print("Aucune équipe trouvée dans global_teams.json.")
        return False

    teams_str = "\n".join(teams_summary[:50])
    today_str = datetime.now().strftime("%Y-%m-%d")
    end_date_str = (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d")

    # 2. Requête IA + Web (Gemini)
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("Clé API Gemini introuvable.")
        return False

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

    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={api_key}"
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
    except Exception as e:
        print(f"Erreur appel Gemini Web Search : {e}")
        return False

    if not isinstance(matches_list, list) or len(matches_list) == 0:
        print("Aucun match retourné par l'IA.")
        return False

    # 3. Insertion SQL dans Neon
    try:
        conn = get_db_connection()
        cur = conn.cursor()

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
        print(f"Succès : {len(matches_list)} matchs insérés dans Neon.")
        return True
    except Exception as e:
        print(f"Erreur insertion Neon : {e}")
        return False
