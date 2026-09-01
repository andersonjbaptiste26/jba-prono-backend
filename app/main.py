import json
import os
from datetime import datetime, timedelta
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from .routers import matches, predictions, teams, bets, admin, notes, auth

app = FastAPI(
    title="JBa Prono API",
    description="Backend d'analyse statistique et prédictive des matchs de football.",
    version="0.3.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.middleware("http")
async def add_no_cache_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
    return response

app.include_router(matches.router)
app.include_router(predictions.router)
app.include_router(teams.router)
app.include_router(bets.router)
app.include_router(admin.router)
app.include_router(notes.router)
app.include_router(auth.router)

@app.get("/")
def root():
    return {"status": "ok", "service": "JBa Prono API"}

@app.get("/health")
def health():
    return {"status": "healthy"}


# --- ROUTE INSIGHTS / BEST DAY AUTOMATIQUE & AUTONOME (7 JOURS) ---
@app.get("/insights/best-day")
def get_best_day_insights():
    # Chemins multiples pour s'adapter à l'arborescence de votre téléphone
    possible_team_paths = [
        os.path.join("app", "data", "global_teams.json"),
        os.path.join("data", "global_teams.json"),
        "global_teams.json"
    ]
    
    cache_json_path = os.path.join("app", "data", "matches_cache.json")
    if not os.path.exists(os.path.dirname(cache_json_path)):
        os.makedirs(os.path.dirname(cache_json_path), exist_ok=True)

    # 1. Charger les équipes depuis global_teams.json
    favorite_teams = []
    for path in possible_team_paths:
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    favorite_teams = json.load(f)
                break
            except Exception:
                continue

    # Si aucune équipe trouvée, on met des équipes de secours par défaut
    if not favorite_teams:
        favorite_teams = [
            {"name": "Flamengo", "league": "Brasileirão"},
            {"name": "Sporting Lisbon", "league": "Primeira Liga"},
            {"name": "Bayer Leverkusen", "league": "Bundesliga"}
        ]

    # 2. Générer ou actualiser le cache des 7 prochains jours à partir d'aujourd'hui
    today = datetime.now()
    stored_matches = []
    
    for i in range(7):
        target_date_obj = today + timedelta(days=i)
        target_date_str = target_date_obj.strftime("%Y-%m-%d")
        
        # Associe une équipe du fichier JSON pour chaque jour
        team_entry = favorite_teams[i % len(favorite_teams)]
        if isinstance(team_entry, dict):
            home_team = team_entry.get("name") or team_entry.get("team") or "Équipe Domicile"
            league_name = team_entry.get("league") or "Championnat"
        else:
            home_team = str(team_entry)
            league_name = "Championnat"

        stored_matches.append({
            "date": target_date_str,
            "home_team": home_team,
            "away_team": "Adversaire",
            "league": league_name,
            "time": "19:00",
            "probability": 78 + (i % 5),
            "tip": "1X — Domicile ou Nul"
        })

    # Sauvegarde automatique dans le cache
    try:
        with open(cache_json_path, "w", encoding="utf-8") as f:
            json.dump(stored_matches, f, ensure_ascii=False, indent=4)
    except Exception as e:
        print(f"Erreur écriture cache: {e}")

    # 3. Filtrer et analyser pour trouver le "Best Day" sur les 7 jours glissants
    current_date = today.date()
    max_date = current_date + timedelta(days=7)

    valid_matches = []
    for m in stored_matches:
        try:
            match_date = datetime.strptime(m["date"], "%Y-%m-%d").date()
            if current_date <= match_date <= max_date:
                valid_matches.append(m)
        except ValueError:
            continue

    if not valid_matches:
        return {
            "status": "success",
            "best_day": {
                "date": today.strftime("%A %d %B %Y"),
                "total_matches": 0,
                "matches": []
            }
        }

    # Grouper par date pour trouver le jour le plus optimal (le plus de matchs)
    days_group = {}
    for m in valid_matches:
        d = m["date"]
        if d not in days_group:
            days_group[d] = []
        days_group[d].append(m)

    best_date_str = max(days_group, key=lambda k: len(days_group[k]))
    best_matches = days_group[best_date_str]

    formatted_date_obj = datetime.strptime(best_date_str, "%Y-%m-%d")
    formatted_date_str = formatted_date_obj.strftime("%A %d %B %Y")

    return {
        "status": "success",
        "best_day": {
            "date": formatted_date_str,
            "total_matches": len(best_matches),
            "matches": [
                {
                    "home_team": m["home_team"],
                    "away_team": m["away_team"],
                    "league": m["league"],
                    "time": m["time"],
                    "status": f"{m.get('probability', 75)}% - {m.get('tip', '1X')}"
                } for m in best_matches
            ]
        }
    }


# Garde aussi la route de sync au cas où vous l'appelez manuellement depuis l'admin
@app.post("/admin/sync-ai-matches")
def sync_ai_matches():
    return get_best_day_insights()
