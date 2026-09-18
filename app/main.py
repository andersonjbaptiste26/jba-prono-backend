from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware

from .routers import matches, predictions, teams, bets, admin, notes, auth, best_day, tickets
from .utils.cache import cache_info, invalidate_cache

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

# ⚠️ IMPORTANT : Le middleware no-cache a été RETIRÉ.
#    Il écrasait tous les en-têtes Cache-Control des routes, ce qui
#    empêchait tout cache. Chaque route définit maintenant SES PROPRES
#    en-têtes.

app.include_router(matches.router)
app.include_router(predictions.router)
app.include_router(teams.router)
app.include_router(bets.router)
app.include_router(admin.router)
app.include_router(notes.router)
app.include_router(auth.router)
app.include_router(best_day.router)
app.include_router(tickets.router)


@app.get("/")
def root(response: Response):
    response.headers["Cache-Control"] = "no-store"
    return {"status": "ok", "service": "JBa Prono API"}


@app.get("/health")
def health(response: Response):
    response.headers["Cache-Control"] = "no-store"
    return {"status": "healthy"}


# ─── 🔧 Endpoints de debug/invalidation du cache ───
@app.get("/_cache/info")
def get_cache_info(response: Response):
    response.headers["Cache-Control"] = "no-store"
    return cache_info()


@app.post("/_cache/clear")
def clear_cache(response: Response, key: str = None):
    response.headers["Cache-Control"] = "no-store"
    invalidate_cache(key)
    return {"status": "cleared", "key": key or "all"}
