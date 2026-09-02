import os
from datetime import datetime
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import psycopg2
import psycopg2.extras

# Importation de vos routeurs et du chargeur JSON
from .routers import matches, predictions, teams, bets, admin, notes, auth
from app import json_loader

app = FastAPI(
    title="JBa Prono API",
    description="Backend d'analyse statistique et prédictive des matchs de football (Multi-utilisateurs).",
    version="0.7.0",
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

# Inclusion des routeurs existants
app.include_router(matches.router)
app.include_router(predictions.router)
app.include_router(teams.router)
app.include_router(bets.router)
app.include_router(admin.router)
app.include_router(notes.router)
app.include_router(auth.router)

# Inclusion du nouveau module d'importation JSON
app.include_router(json_loader.router)

@app.get("/")
def root():
    return {
        "status": "ok", 
        "service": "JBa Prono API (Neon DB Active + JSON Sync)",
        "legal_notice": "Avertissement : Les analyses et pronostics fournis sont à titre purement indicatif. Jouez de manière responsable."
    }

@app.get("/disclaimer")
def get_legal_disclaimer():
    return {
        "status": "success",
        "disclaimer": {
            "title": "Avertissement légal et politique de non-responsabilité",
            "warning": "JBa Prono est un outil d'analyse statistique et informative. En aucun cas les informations, probabilités ou pronostics fournis ne constituent une garantie de gain ou une incitation financière à parier.",
            "liability": "Les créateurs et administrateurs de JBa Prono déclinent toute responsabilité en cas de pertes financières, de paris sportifs infructueux ou d'erreurs de calendrier provenant des sources externes.",
            "gambling_addiction": "Les jeux d'argent et de hasard comportent des risques : endettement, isolement, dépendance. Pour être aidé, jouez avec modération.",
            "age_restriction": "L'utilisation de cette application et les paris sportifs sont strictement réservés à un public majeur selon la législation de votre pays."
        }
    }

# --- ROUTE INSIGHTS / BEST DAY ---
@app.get("/insights/best-day")
def get_best_day_insights():
    try:
        database_url = os.environ.get("DATABASE_URL")
        if not database_url:
            raise Exception("DATABASE_URL non configurée.")
        
        conn = psycopg2.connect(database_url, cursor_factory=psycopg2.extras.RealDictCursor)
        cur = conn.cursor()

        cur.execute("""
            SELECT match_date, home_team, away_team, league, match_time, probability, tip
            FROM matches_cache
            WHERE match_date >= CURRENT_DATE AND match_date <= CURRENT_DATE + INTERVAL '7 days'
            ORDER BY match_date ASC;
        """)
        valid_matches = cur.fetchall()
        cur.close()
        conn.close()

        if not valid_matches:
            return {
                "status": "success",
                "disclaimer": "Informations indicatives. Les jeux d'argent comportent des risques.",
                "best_day": {
                    "date": datetime.now().strftime("%A %d %B %Y"),
                    "total_matches": 0,
                    "matches": []
                }
            }

        days_group = {}
        for m in valid_matches:
            d_str = str(m["match_date"])
            if d_str not in days_group:
                days_group[d_str] = []
            days_group[d_str].append(m)

        best_date_str = max(days_group, key=lambda k: len(days_group[k]))
        best_matches = days_group[best_date_str]

        formatted_date_obj = datetime.strptime(best_date_str, "%Y-%m-%d")
        formatted_date_str = formatted_date_obj.strftime("%A %d %B %Y")

        return {
            "status": "success",
            "disclaimer": "Avertissement : Les pronostics sont fournis à titre informatif et sans aucune garantie de gain.",
            "best_day": {
                "date": formatted_date_str,
                "total_matches": len(best_matches),
                "matches": [
                    {
                        "home_team": m["home_team"],
                        "away_team": m["away_team"],
                        "league": m["league"],
                        "time": m["match_time"],
                        "status": f"{m['probability']}% - {m['tip']}"
                    } for m in best_matches
                ]
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur lors de la récupération des insights : {e}")
