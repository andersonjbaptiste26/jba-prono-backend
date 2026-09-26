from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from sqlalchemy import text

from .database import engine
from .routers import (
    matches, predictions, teams, admin,
    notes, auth, best_day, tickets, results,
)
# `bets` retiré : paris gérés en localStorage depuis v0.3.0

APP_VERSION = "0.3.1"


@asynccontextmanager
async def lifespan(app: FastAPI):
    print(f"[JBa Prono] Démarrage v{APP_VERSION}")
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        print("[JBa Prono] ✅ Connexion PostgreSQL OK")
    except Exception as e:
        print(f"[JBa Prono] ❌ Erreur PostgreSQL : {e}")
    yield
    print("[JBa Prono] Arrêt.")


app = FastAPI(
    title="JBa Prono API",
    description="Backend d'analyse statistique et prédictive des matchs de football.",
    version=APP_VERSION,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ⚡ Compression GZip : réduit les réponses > 1 KB de 50-70 %
app.add_middleware(GZipMiddleware, minimum_size=1000)


@app.middleware("http")
async def add_no_cache_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
    return response


app.include_router(matches.router)
app.include_router(predictions.router)
app.include_router(teams.router)
app.include_router(admin.router)
app.include_router(notes.router)
app.include_router(auth.router)
app.include_router(best_day.router)
app.include_router(tickets.router)
app.include_router(results.router)
# app.include_router(bets.router)  # DÉPRÉCIÉ v0.3.0


@app.get("/")
def root():
    return {"status": "ok", "service": "JBa Prono API", "version": APP_VERSION}


@app.get("/health")
def health():
    db_status = "ok"
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception as e:
        db_status = f"error: {e}"
    return {"status": "healthy", "version": APP_VERSION, "db": db_status}
