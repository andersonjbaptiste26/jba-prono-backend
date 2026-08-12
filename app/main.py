from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routers import matches, predictions, teams, bets

app = FastAPI(
    title="JBa Prono API",
    description="Backend d'analyse statistique et prédictive des matchs de football.",
    version="0.1.0",
)

# CORS ouvert pour le développement — à restreindre au domaine du frontend en production.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(matches.router)
app.include_router(predictions.router)
app.include_router(teams.router)
app.include_router(bets.router)


@app.get("/")
def root():
    return {"status": "ok", "service": "JBa Prono API"}


@app.get("/health")
def health():
    return {"status": "healthy"}
