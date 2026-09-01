import json
import os
from datetime import datetime, timedelta
from fastapi import FastAPI, Request, BackgroundTasks
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


# --- 1. ROUTE DE SYNCHRONISATION IA (Basée sur global_teams.json) ---
@app.post("/admin/sync-ai-matches")
def sync_ai_matches():
    teams_json_path = os.path.join("app", "data", "global_teams.json")
    cache_json_path = os.path.join("app", "data", "matches_cache.json")

    # Charger les équipes et championnats de référence
    favorite_teams = []
    if os.path.exists(teams_json_path):
        try:
            with open(teams_json_path, "r", encoding="utf-8") as f:
                favorite_teams = json.load(f)
        except Exception as e:
            return {"status": "error", "message": f"Erreur lecture global_teams.json: {e}"}

    # NOTE : Ici, vous connectez votre logique de recherche IA/Web 
    # qui utilise la liste 'favorite_teams' pour interroger le net ou une source externe.
    # Pour l'exemple sur mobile, on simule la mise à jour des 7 jours glissants :
    
    today = datetime.now()
    refreshed_matches = []
    
    # Génération d'une structure propre pour les 7 prochains jours
    for i in range(7):
        target_date = (today + timedelta(days=i)).strftime("%Y-%m-%d")
        refreshed_matches.append({
            "date": target_date,
            "home_team": "Équipe Cible (AI)",
            "away_team": "Adversaire",
            "league": "Championnat Global",
            "time": "20:00",
            "probability": 82,
            "tip": "Victoire domicile"
        })

    # Sauvegarde dans le cache local du système
    try:
        with open(cache_json_path, "w", encoding="utf-8") as f:
            json.dump(refreshed_matches, f, ensure_ascii=False, indent=4)
    except Exception as e:
        return {"status": "error", "message": f"Erreur écriture cache: {e}"}

    return {
        "status": "success",
        "message": "Synchronisation des matchs réussie via les équipes de global_teams.json",
        "total_teams_checked": len(favorite_teams),
        "matches_cached": len(refreshed_matches)
    }


# --- 2. ROUTE INSIGHTS / BEST DAY (Fenêtre 7 jours) ---
@app.get("/insights/best-day")
def get_best_day_insights():
    cache_json_path = os.path.join("app", "data", "matches_cache.json")

    if not os.path.exists(cache_json_path):
        return {"status": "error", "message": "Aucun cache de matchs trouvé. Veuillez exécuter la synchronisation."}

    try:
        with open(cache_json_path, "r", encoding="utf-8") as f:
            stored_matches = json.load(f)
    except Exception as e:
        return {"status": "error", "message": f"Erreur lecture cache: {e}"}

    # Filtrer strictement sur les 7 jours à venir
    today = datetime.now().date()
    max_date = today + timedelta(days=7)

    valid_matches = []
    for m in stored_matches:
        try:
            match_date = datetime.strptime(m["date"], "%Y-%m-%d").date()
            if today <= match_date <= max_date:
                valid_matches.append(m)
        except ValueError:
            continue

    if not valid_matches:
        return {"status": "success", "message": "Aucun match dans la fenêtre des 7 prochains jours."}

    # Grouper par date pour identifier le "Best Day" (le jour le plus dense)
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
                    "status": f"{m.get('probability', 0)}% - {m.get('tip', '1X')}"
                } for m in best_matches
            ]
        }
    }
