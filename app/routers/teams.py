"""
Liste de référence fixe des 4 meilleures équipes par championnat,
saison 2025-2026.

Les équipes sont classées selon leur position finale :
1er, 2e, 3e et 4e.
"""

from fastapi import APIRouter, Response
from sqlalchemy import desc

from ..utils.cache import cache_memory


router = APIRouter(prefix="/teams", tags=["teams"])


# ============================================================
# TOP 4 ÉQUIPES — SAISON 2025-2026
# ============================================================

CURATED_TOP_TEAMS = {
    "Espagne (La Liga)": [
        "FC Barcelone",
        "Real Madrid",
        "Villarreal CF",
        "Atlético de Madrid",
    ],

    "Allemagne (Bundesliga)": [
        "Bayern Munich",
        "Borussia Dortmund",
        "RB Leipzig",
        "VfB Stuttgart",
    ],

    "Italie (Serie A)": [
        "Inter Milan",
        "Napoli",
        "AS Roma",
        "Como 1907",
    ],

    "France (Ligue 1)": [
        "Paris Saint-Germain",
        "RC Lens",
        "LOSC Lille",
        "Olympique Lyonnais",
    ],

    "Pays-Bas (Eredivisie)": [
        "PSV Eindhoven",
        "Feyenoord Rotterdam",
        "NEC Nijmegen",
        "FC Twente",
    ],

    "Belgique (Jupiler Pro League)": [
        "Club Bruges",
        "Union Saint-Gilloise",
        "Sint-Truiden",
        "RSC Anderlecht",
    ],

    "Norvège (Eliteserien)": [
        "Viking FK",
        "Bodø/Glimt",
        "Tromsø IL",
        "SK Brann",
    ],

    "Danemark (Superliga)": [
        "AGF Aarhus",
        "FC Midtjylland",
        "FC Nordsjælland",
        "Brøndby IF",
    ],

    "Suisse (Swiss Super League)": [
        "FC Thun",
        "FC St. Gallen",
        "FC Lugano",
        "FC Sion",
    ],

    "Pologne (Ekstraklasa)": [
        "Lech Poznań",
        "Górnik Zabrze",
        "Jagiellonia Białystok",
        "Raków Częstochowa",
    ],

    "Russie (Premier League)": [
        "Zenit Saint-Pétersbourg",
        "FK Krasnodar",
        "Lokomotiv Moscou",
        "Spartak Moscou",
    ],

    "Tchéquie (Czech First League)": [
        "Slavia Prague",
        "Sparta Prague",
        "Viktoria Plzeň",
        "Hradec Králové",
    ],

    "MLS (États-Unis)": [
        "Philadelphia Union",
        "FC Cincinnati",
        "Inter Miami CF",
        "San Diego FC",
    ],

    "Brésil (Brasileirão)": [
        "Flamengo",
        "Palmeiras",
        "Cruzeiro",
        "Mirassol",
    ],

    "Argentine (Liga Profesional)": [
        "Rosario Central",
        "Boca Juniors",
        "Argentinos Juniors",
        "River Plate",
    ],

    "Chili (Primera División)": [
        "Coquimbo Unido",
        "Universidad Católica",
        "O'Higgins",
        "Universidad de Chile",
    ],
}


# ============================================================
# GET /teams/curated-top
# ============================================================

@router.get("/curated-top")
@cache_memory(
    ttl_seconds=86400,
    key="teams_curated_top",
)
def curated_top_teams(response: Response):
    """
    GET /teams/curated-top

    Retourne les 4 premières équipes de chaque championnat
    pour la saison 2025-2026.

    Exemple de réponse :

    [
        {
            "championnat": "Espagne (La Liga)",
            "equipes": [
                {"rang": 1, "nom": "FC Barcelone"},
                {"rang": 2, "nom": "Real Madrid"},
                {"rang": 3, "nom": "Villarreal CF"},
                {"rang": 4, "nom": "Atlético de Madrid"}
            ]
        }
    ]
    """

    # Cache HTTP : 24 heures
    response.headers["Cache-Control"] = (
        "public, max-age=86400, s-maxage=86400"
    )

    return [
        {
            "championnat": league,
            "equipes": [
                {
                    "rang": i + 1,
                    "nom": team,
                }
                for i, team in enumerate(teams)
            ],
        }
        for league, teams in CURATED_TOP_TEAMS.items()
    ]


# ============================================================
# GET /teams/top
# ============================================================

@router.get("/top")
def top_teams_dynamic(
    league_id: int,
    response: Response,
    limit: int = 5,
):
    """
    GET /teams/top

    Classement dynamique des équipes selon leur rating
    enregistré dans la base de données.

    Paramètres :
        league_id : ID du championnat
        limit     : nombre maximum d'équipes retournées

    Exemple :
        GET /teams/top?league_id=1&limit=5
    """

    # Cache navigateur/CDN : 15 minutes
    response.headers["Cache-Control"] = (
        "public, max-age=900, "
        "s-maxage=900, "
        "stale-while-revalidate=1800"
    )

    from ..database import SessionLocal
    from ..models import TeamRating, Team

    db = SessionLocal()

    try:
        # Sécurité : éviter un limit négatif ou excessivement élevé
        limit = max(1, min(limit, 100))

        rows = (
            db.query(TeamRating)
            .filter(TeamRating.league_id == league_id)
            .order_by(desc(TeamRating.rating))
            .limit(limit)
            .all()
        )

        result = []

        for r in rows:
            team = db.get(Team, r.team_id)

            # Si l'équipe n'existe plus dans la base,
            # on ignore cette ligne.
            if team is None:
                continue

            result.append(
                {
                    "team_id": r.team_id,
                    "team_name": team.name,
                    "rating": float(r.rating),
                }
            )

        return result

    finally:
        db.close()
