"""
Liste de référence fixe des 4 meilleures équipes par championnat (saison 2025-2026).
"""
from fastapi import APIRouter
from ..cache import cached

router = APIRouter(prefix="/teams", tags=["teams"])

CURATED_TOP_TEAMS = {
    "Espagne (La Liga)": ["Real Madrid", "FC Barcelone", "Atlético de Madrid", "Athletic Bilbao"],
    "Allemagne (Bundesliga)": ["Bayern Munich", "Bayer Leverkusen", "Borussia Dortmund", "RB Leipzig"],
    "Italie (Serie A)": ["Inter Milan", "AC Milan", "Juventus", "Atalanta Bergame"],
    "France (Ligue 1)": ["Paris Saint-Germain", "AS Monaco", "Olympique de Marseille", "LOSC Lille"],
    "Pays-Bas (Eredivisie)": ["PSV Eindhoven", "Feyenoord Rotterdam", "Ajax Amsterdam", "FC Twente"],
    "Belgique (Jupiler Pro League)": ["Club Bruges", "Union Saint-Gilloise", "RSC Anderlecht", "KRC Genk"],
    "Norvège (Eliteserien)": ["Bodø/Glimt", "SK Brann", "Viking FK", "Rosenborg BK"],
    "Danemark (Superliga)": ["FC Copenhague", "FC Midtjylland", "Brøndby IF", "AGF Aarhus"],
    "Suisse (Swiss Super League)": ["Young Boys Berne", "Servette FC", "FC Lugano", "FC Bâle"],
    "Pologne (Ekstraklasa)": ["Jagiellonia Białystok", "Śląsk Wrocław", "Lech Poznań", "Legia Varsovie"],
    "Russie (Premier League)": ["Zenit Saint-Pétersbourg", "FK Krasnodar", "Dynamo Moscou", "Spartak Moscou"],
    "Tchéquie (Czech First League)": ["Sparta Prague", "Slavia Prague", "Viktoria Plzeň", "Baník Ostrava"],
    "MLS (États-Unis)": ["Inter Miami", "Columbus Crew", "Los Angeles FC", "FC Cincinnati"],
    "Brésil (Brasileirão)": ["Botafogo", "Palmeiras", "Flamengo", "Fortaleza"],
    "Argentine (Liga Profesional)": ["River Plate", "Talleres", "Boca Juniors", "Vélez Sarsfield"],
    "Chili (Primera División)": ["Colo-Colo", "Universidad de Chile", "Universidad Católica", "Palestino"],
}


@router.get("/curated-top")
@cached(ttl_seconds=7200, prefix="teams_curated")  # 2 h
def curated_top_teams():
    return [
        {"championnat": league, "equipes": [
            {"rang": i + 1, "nom": team} for i, team in enumerate(teams)
        ]}
        for league, teams in CURATED_TOP_TEAMS.items()
    ]


@router.get("/top")
@cached(ttl_seconds=3000, prefix="teams_top")  # 50 min
def top_teams_dynamic(league_id: int, limit: int = 5):
    from ..database import SessionLocal
    from ..models import TeamRating, Team
    from sqlalchemy import desc

    db = SessionLocal()
    try:
        rows = (
            db.query(TeamRating)
            .filter(TeamRating.league_id == league_id)
            .order_by(desc(TeamRating.rating))
            .limit(limit)
            .all()
        )
        return [
            {
                "team_id": r.team_id,
                "team_name": db.query(Team).get(r.team_id).name,
                "rating": float(r.rating),
            }
            for r in rows
        ]
    finally:
        db.close()
