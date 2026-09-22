import re
import unicodedata
from collections import defaultdict
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import desc, func

from ..database import get_db
from ..models import Prediction, Event, Match
from ..prediction.narrative import build_human_summary, get_expected_goals_line

router = APIRouter(prefix="/predictions", tags=["predictions"])

MAIN_THRESHOLD = 66.0
FALLBACK_MIN = 55.0
FALLBACK_MAX = 66.0

# Noms tels que renvoyés par The Odds API / football-data.org
ALLOWED_TEAMS = [
    "Arsenal", "Manchester City", "Manchester United", "Aston Villa",
    "Barcelona", "Real Madrid", "Villarreal", "Atletico Madrid",
    "Bayern Munich", "Borussia Dortmund", "RB Leipzig", "VfB Stuttgart",
    "Inter", "Inter Milan", "Napoli", "Roma", "Como",
    "Paris Saint-Germain", "Paris SG", "Lens", "Lille", "Lyon",
    "PSV", "PSV Eindhoven", "Feyenoord", "NEC Nijmegen", "Twente",
    "Porto", "FC Porto", "Sporting CP", "Benfica", "Braga",
    "Coventry", "Ipswich", "Millwall", "Southampton",
    "Flamengo", "Palmeiras", "Cruzeiro", "Mirassol",
]

ALLOWED_COMPETITIONS = [
    "Premier League", "La Liga", "Bundesliga", "Serie A", "Ligue 1",
    "Eredivisie", "Primeira Liga", "EFL Championship",
    "Brasileirao", "Champions League",
]


def _normalize(s: str) -> str:
    if not s:
        return ""
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = s.lower()
    s = re.sub(r"[^a-z0-9]", "", s)
    return s


_ALLOWED_TEAMS_NORM = {_normalize(t) for t in ALLOWED_TEAMS}
_ALLOWED_COMPS_NORM = {_normalize(c) for c in ALLOWED_COMPETITIONS}


def _team_allowed(name: str) -> bool:
    n = _normalize(name)
    if not n:
        return False
    for allowed in _ALLOWED_TEAMS_NORM:
        if allowed and (allowed in n or n in allowed):
            return True
    return False


def _match_allowed(match: Match) -> bool:
    if match is None:
        return False
    if match.competition and _normalize(match.competition.name) in _ALLOWED_COMPS_NORM:
        return True
    home = match.home_team.name if match.home_team else ""
    away = match.away_team.name if match.away_team else ""
    return _team_allowed(home) or _team_allowed(away)


@router.get("")
def list_predictions(
    min_probability: float = Query(0, ge=0, le=100),
    only_upcoming: bool = Query(True),
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
    rows = [p for p in rows if _match_allowed(p.event.match)]
    return [_serialize(p) for p in rows]


def _build_double_chance(resultat_preds: list[Prediction]) -> dict | None:
    by_prefix = {}
    for p in resultat_preds:
        label = p.event.label
        if label.startswith("1"):
            by_prefix["1"] = p
        elif label.startswith("X"):
            by_prefix["X"] = p
        elif label.startswith("2"):
            by_prefix["2"] = p

    if "X" not in by_prefix:
        return None

    options = []
    if "1" in by_prefix:
        prob = min(float(by_prefix["1"].probability) + float(by_prefix["X"].probability), 100.0)
        options.append(("1X — Domicile ou Nul", prob, by_prefix["1"]))
    if "2" in by_prefix:
        prob = min(float(by_prefix["2"].probability) + float(by_prefix["X"].probability), 100.0)
        options.append(("X2 — Nul ou Extérieur", prob, by_prefix["2"]))

    if not options:
        return None

    label, prob, source_pred = max(options, key=lambda o: o[1])
    odds = round(100.0 / prob, 2) if prob > 0 else None
    return {"label": label, "probability": round(prob, 2), "odds": odds, "source_pred": source_pred}


@router.get("/best")
def best_predictions(limit: int = 30, db: Session = Depends(get_db)):
    query = (
        db.query(Prediction)
        .join(Event, Prediction.event_id == Event.id)
        .join(Match, Event.match_id == Match.id)
        .filter(Match.kickoff_at >= func.now())
    )
    rows = [p for p in query.all() if _match_allowed(p.event.match)]

    by_match = defaultdict(list)
    for p in rows:
        by_match[p.event.match_id].append(p)

    selected = []
    for match_id, preds in by_match.items():
        best = max(preds, key=lambda p: p.probability)

        if float(best.probability) >= MAIN_THRESHOLD:
            selected.append(("normal", best, None))
            continue

        resultat_preds = [p for p in preds if p.event.type == "resultat"]
        best_resultat = max(resultat_preds, key=lambda p: p.probability) if resultat_preds else None

        if best_resultat and FALLBACK_MIN <= float(best_resultat.probability) < FALLBACK_MAX:
            dc = _build_double_chance(resultat_preds)
            if dc and float(dc["probability"]) >= MAIN_THRESHOLD:
                selected.append(("double_chance", dc["source_pred"], dc))
                continue

    selected.sort(key=lambda item: item[1].event.match.kickoff_at)
    return [_serialize(p, dc) for _, p, dc in selected[:limit]]


class _FakeEvent:
    def __init__(self, type_: str, label: str):
        self.type = type_
        self.label = label


def _serialize(p: Prediction, double_chance: dict = None) -> dict:
    event = p.event
    match = event.match if event else None
    buts_probables = get_expected_goals_line(match) if match else None

    base = {
        "prediction_id": p.id,
        "event_id": event.id if event else None,
        "match": f"{match.home_team.name} vs {match.away_team.name}" if match else None,
        "home_team": match.home_team.name if match else None,
        "away_team": match.away_team.name if match else None,
        "competition": match.competition.name if match and match.competition else None,
        "kickoff_at": match.kickoff_at.isoformat() if match else None,
        "buts_probables": buts_probables,
    }

    if double_chance:
        dc_event = _FakeEvent("double_chance", double_chance["label"])
        human_pourquoi = build_human_summary(dc_event, p, match, buts_probables=buts_probables)
        base.update({
            "event": double_chance["label"],
            "event_type": "double_chance",
            "probability": double_chance["probability"],
            "confidence_tier": None,
            "odds": double_chance["odds"],
            "pourquoi": human_pourquoi,
            "explanation": {"cote_calculee": True, "note": "Cote estimée, pas une cote bookmaker."},
        })
        return base

    base.update({
        "event": event.label if event else None,
        "event_type": event.type if event else None,
        "probability": float(p.probability),
        "confidence_tier": p.confidence_tier,
        "odds": float(event.odds_value) if event and event.odds_value else None,
        "pourquoi": build_human_summary(event, p, match, buts_probables=buts_probables) if match else None,
        "explanation": p.explanation,
    })
    return base
