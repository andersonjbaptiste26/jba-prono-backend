from collections import defaultdict
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import desc, func

from ..database import get_db
from ..models import Prediction, Event, Match

router = APIRouter(prefix="/predictions", tags=["predictions"])

SINGLE_RESULT_MAX_ODDS = 1.35
DOUBLE_CHANCE_MIN_ODDS = 1.09
DOUBLE_CHANCE_MAX_ODDS = 1.35
GLOBAL_MIN_PROBABILITY = 65.0


@router.get("")
def list_predictions(
    min_probability: float = Query(0, ge=0, le=100),
    only_upcoming: bool = Query(True, description="Exclut les matchs déjà commencés/joués."),
    db: Session = Depends(get_db),
):
    query = (
        db.query(Prediction)
        .join(Event, Prediction.event_id == Event.id)
        .join(Match, Event.match_id == Match.id)
        .filter(Prediction.probability >= min_probability)
    )
    if only_upcoming:
        query = query.filter(Match.kickoff_at >= func.now())
    rows = query.order_by(desc(Prediction.probability)).all()
    return [_serialize(p) for p in rows]


def _build_double_chance_candidates(resultat_preds: list[Prediction]) -> list[dict]:
    by_label_prefix = {}
    for p in resultat_preds:
        label = p.event.label
        if label.startswith("1"):
            by_label_prefix["1"] = p
        elif label.startswith("X"):
            by_label_prefix["X"] = p
        elif label.startswith("2"):
            by_label_prefix["2"] = p

    candidates = []
    if "1" in by_label_prefix and "X" in by_label_prefix:
        prob = float(by_label_prefix["1"].probability) + float(by_label_prefix["X"].probability)
        prob = min(prob, 100.0)
        odds = round(100.0 / prob, 2) if prob > 0 else None
        candidates.append({
            "label": "1X — Domicile ou Nul",
            "probability": round(prob, 2),
            "odds": odds,
            "odds_calculee": True,
            "source_event_id": by_label_prefix["1"].event_id,
        })
    if "X" in by_label_prefix and "2" in by_label_prefix:
        prob = float(by_label_prefix["X"].probability) + float(by_label_prefix["2"].probability)
        prob = min(prob, 100.0)
        odds = round(100.0 / prob, 2) if prob > 0 else None
        candidates.append({
            "label": "X2 — Nul ou Extérieur",
            "probability": round(prob, 2),
            "odds": odds,
            "odds_calculee": True,
            "source_event_id": by_label_prefix["2"].event_id,
        })
    return candidates


@router.get("/best")
def best_predictions(
    limit: int = 20,
    db: Session = Depends(get_db),
):
    rows = (
        db.query(Prediction)
        .join(Event, Prediction.event_id == Event.id)
        .join(Match, Event.match_id == Match.id)
        .filter(Match.kickoff_at >= func.now())
        .all()
    )

    by_match = defaultdict(list)
    for p in rows:
        by_match[p.event.match_id].append(p)

    selected = []
    for match_id, preds in by_match.items():
        resultat_preds = [p for p in preds if p.event.type == "resultat"]
        buts_preds = [p for p in preds if p.event.type == "buts"]

        candidates = []

        for p in resultat_preds:
            if p.event.label.startswith("1") or p.event.label.startswith("2"):
                if p.event.odds_value and float(p.event.odds_value) <= SINGLE_RESULT_MAX_ODDS:
                    if float(p.probability) >= GLOBAL_MIN_PROBABILITY:
                        candidates.append({
                            "kind": "prediction", "prediction": p,
                            "probability": float(p.probability),
                        })

        for dc in _build_double_chance_candidates(resultat_preds):
            if dc["odds"] and DOUBLE_CHANCE_MIN_ODDS <= dc["odds"] <= DOUBLE_CHANCE_MAX_ODDS:
                if dc["probability"] >= GLOBAL_MIN_PROBABILITY:
                    candidates.append({
                        "kind": "double_chance", "data": dc,
                        "probability": dc["probability"],
                    })

        for p in buts_preds:
            if float(p.probability) >= GLOBAL_MIN_PROBABILITY:
                candidates.append({
                    "kind": "prediction", "prediction": p,
                    "probability": float(p.probability),
                })

        if not candidates:
            continue

        best = max(candidates, key=lambda c: c["probability"])
        selected.append((best, preds[0].event.match))

    selected.sort(key=lambda item: item[1].kickoff_at)

    results = []
    for candidate, match in selected[:limit]:
        if candidate["kind"] == "prediction":
            results.append(_serialize(candidate["prediction"]))
        else:
            dc = candidate["data"]
            results.append({
                "prediction_id": None,
                "event_id": dc["source_event_id"],
                "match": f"{match.home_team.name} vs {match.away_team.name}",
                "home_team": match.home_team.name,
                "away_team": match.away_team.name,
                "competition": match.competition.name if match.competition else None,
                "kickoff_at": match.kickoff_at.isoformat(),
                "event": dc["label"],
                "event_type": "double_chance",
                "probability": dc["probability"],
                "confidence_tier": None,
                "odds": dc["odds"],
                "explanation": {
                    "type_pronostic": dc["label"],
                    "cote_calculee": True,
                    "note": "Cote estimée à partir des probabilités 1/X/2 — pas une cote directe de bookmaker.",
                },
            })

    return results


def _serialize(p: Prediction) -> dict:
    event = p.event
    match = event.match if event else None
    return {
        "prediction_id": p.id,
        "event_id": event.id if event else None,
        "match": f"{match.home_team.name} vs {match.away_team.name}" if match else None,
        "home_team": match.home_team.name if match else None,
        "away_team": match.away_team.name if match else None,
        "competition": match.competition.name if match and match.competition else None,
        "kickoff_at": match.kickoff_at.isoformat() if match else None,
        "event": event.label if event else None,
        "event_type": event.type if event else None,
        "probability": float(p.probability),
        "confidence_tier": p.confidence_tier,
        "odds": float(event.odds_value) if event and event.odds_value else None,
        "explanation": p.explanation,
    }
