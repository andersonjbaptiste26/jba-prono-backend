from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from .routers import matches, predictions, teams, bets, admin, notes, auth, json_loader

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
app.include_router(json_loader.router)


@app.get("/")
def root():
    return {"status": "ok", "service": "JBa Prono API"}


@app.get("/health")
def health():
    return {"status": "healthy"}
