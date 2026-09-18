from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from ..database import get_db
from ..prediction.combos import generate_ticket_combos
from ..utils.cache import cache_memory

router = APIRouter(prefix="/tickets", tags=["tickets"])


@router.get("/best-combo")
@cache_memory(ttl_seconds=900, key="tickets_best_combo")  # 🆕 5 min → 15 min
def best_combo_tickets(response: Response, db: Session = Depends(get_db)):
    """GET /tickets/best-combo — jusqu'à 3 combinaisons de 2 à 4 matchs
    (répartis sur deux jours consécutifs), avec une cote combinée entre
    3 et 6, et une somme de probabilités individuelles >= 75%."""

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
