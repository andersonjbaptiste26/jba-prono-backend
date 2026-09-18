from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from ..database import get_db
from ..prediction.combos import generate_ticket_combos
from ..utils.cache import cache_memory

router = APIRouter(prefix="/tickets", tags=["tickets"])


@router.get("/best-combo")
@cache_memory(ttl_seconds=900, key="tickets_best_combo")  # 🎯 15 minutes
def best_combo_tickets(response: Response, db: Session = Depends(get_db)):
    """GET /tickets/best-combo — jusqu'à 7 combinaisons de 2 à 6 matchs
    répartis sur 2 à 7 jours consécutifs, avec une cote combinée entre
    3 et 9, et une somme de probabilités individuelles >= 75%.

    Chaque ticket affiche deux chiffres différents :
    - probability_sum : la somme des probabilités individuelles (le
      critère de filtre demandé)
    - real_combined_probability : la VRAIE chance que tout le ticket se
      réalise (produit des probabilités) — toujours plus basse, c'est
      la valeur honnête à regarder avant de parier.
    """

    # ⚡ Cache navigateur (15 min frais, 30 min stale) + CDN Render
    response.headers["Cache-Control"] = "public, max-age=900, s-maxage=900, stale-while-revalidate=1800"

    combos = generate_ticket_combos(db)

    results = []
    for c in combos:
        selections = []
        for p in c["selections"]:
            event = p.event
            match = event.match
            selections.append({
                "event_id": event.id,
                "match": f"{match.home_team.name} vs {match.away_team.name}",
                "competition": match.competition.name if match.competition else None,
                "kickoff_at": match.kickoff_at.isoformat(),
                "event": event.label,
                "probability": float(p.probability),
                "odds": float(event.odds_value),
            })
        results.append({
            "selections": selections,
            "total_odds": c["total_odds"],
            "probability_sum": c["probability_sum"],
            "real_combined_probability": c["real_combined_probability"],
            "dates": c["dates"],
        })
    return results
