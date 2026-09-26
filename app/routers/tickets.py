from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..database import get_db
from ..prediction.combos import generate_ticket_combos
from ..cache import cached, match_still_visible

router = APIRouter(prefix="/tickets", tags=["tickets"])


@router.get("/best-combo")
@cached(ttl_seconds=3000, prefix="tickets_best_combo")  # 50 min
def best_combo_tickets(db: Session = Depends(get_db)):
    combos = generate_ticket_combos(db)

    # Filtre : retire les combos dont au moins une sélection porte sur un match obsolète
    combos = [
        c for c in combos
        if all(match_still_visible(p.event.match) for p in c["selections"])
    ]

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
