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

# Whitelist exacte des championnats et des équipes autorisées
ALLOWED_TEAMS_BY_COMPETITION = {
    "Premier League": ["Arsenal", "Manchester City", "Manchester United", "Aston Villa"],
    "La Liga": ["FC Barcelone", "Real Madrid", "Villarreal", "Atlético de Madrid"],
    "Bundesliga": ["Bayern Munich", "Borussia Dortmund", "RB Leipzig", "VfB Stuttgart"],
    "Serie A": ["Inter Milan", "Napoli", "AS Roma", "Como 1907"],
    "Ligue 1": ["Paris Saint-Germain", "RC Lens", "LOSC Lille", "Olympique Lyonnais"],
    "Eredivisie": ["PSV Eindhoven", "Feyenoord", "NEC Nimègue", "FC Twente"],
    "Primeira Liga": ["FC Porto", "Sporting CP", "SL Benfica", "SC Braga"],
    "EFL Championship": ["Coventry City", "Ipswich Town", "Millwall", "Southampton"],
    "Campeonato Brasileiro Série A": ["Flamengo", "Palmeiras", "Cruzeiro", "Mirassol"],
    "Ligue des champions UEFA": ["Paris Saint-Germain", "Arsenal", "Bayern Munich", "Atlético de Madrid"]
}

def is_allowed_match(match) -> bool:
    if not match or not match.competition or not match.home_team or not match.away_team:
        return False
    comp_name = match.competition.name
    allowed_teams = ALLOWED_TEAMS_BY_COMPETITION.get(comp_name)
    if not allowed_teams:
        return False
    
    home = match.home_team.name
    away = match.away_team.name
    
    if comp_name == "Ligue des champions UEFA":
        return home in allowed_teams or away in allowed_teams
    else:
        return home in allowed_teams and away in allowed_teams


def _clean_explanation(explanation) -> str | dict:
    """Nettoie et purge toute trace de référence aux bookmakers ou aux cotes du marché."""
    if not explanation:
        return "Calculé par le moteur statistique interne."
    
    expl_str = str(explanation)
    forbidden_words = ["marché", "cote", "implicite", "bookmaker", "implique"]
    
    # Si le texte de la base contient des références externes, on force un texte interne propre
    if any(word in expl_str.lower() for word in forbidden_words):
        return "Probabilité calculée et validée par le moteur statistique interne."
    
    return explanation


@router.get("")
def list_predictions(
    min_probability: float = Query(66.0, ge=0, le=100),
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
    
    filtered_rows = [p for p in rows if is_allowed_match(p.event.match if p.event else None)]
    return [_serialize(p) for p in filtered_rows]


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
def best_predictions(
    limit: int = 30,
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
        match = p.event.match if p.event else None
        if is_allowed_match(match):
            by_match[match.id].append(p)

    selected = []
    for match_id, preds in by_match.items():
        best = max(preds, key=lambda p: p.probability)

        # 1. Si la meilleure prédiction directe dépasse ou égale 66%
        if float(best.probability) >= MAIN_THRESHOLD:
            selected.append(("normal", best, None))
            continue

        # 2. Si elle est entre 55% et 66% sur le marché "resultat", on applique le Double Chance
        resultat_preds = [p for p in preds if p.event.type == "resultat"]
        best_resultat = max(resultat_preds, key=lambda p: p.probability) if resultat_preds else None

        if best_resultat and FALLBACK_MIN <= float(best_resultat.probability) < FALLBACK_MAX:
            dc = _build_double_chance(resultat_preds)
            # Retenu uniquement si la nouvelle probabilité calculée par le système dépasse 66%
            if dc and dc["probability"] > MAIN_THRESHOLD:
                selected.append(("double_chance", dc["source_pred"], dc))

    selected.sort(key=lambda item: item[1].event.match.kickoff_at)

    return [_serialize(p, dc) for _, p, dc in selected[:limit]]


def _serialize(p: Prediction, double_chance: dict = None) -> dict:
    event = p.event
    match = event.match if event else None
    buts_probables = get_expected_goals_line(match) if match else None

    if double_chance:
        human_pourquoi = build_human_summary(event, p, match, buts_probables=buts_probables)
        return {
            "prediction_id": p.id,
            "event_id": event.id if event else None,
            "match": f"{match.home_team.name} vs {match.away_team.name}" if match else None,
            "home_team": match.home_team.name if match else None,
            "away_team": match.away_team.name if match else None,
            "competition": match.competition.name if match and match.competition else None,
            "kickoff_at": match.kickoff_at.isoformat() if match else None,
            "event": double_chance["label"],
            "event_type": "double_chance",
            "probability": double_chance["probability"],
            "confidence_tier": None,
            "odds": double_chance["odds"],
            "buts_probables": buts_probables,
            "pourquoi": human_pourquoi,
            "explanation": "Calculé par le moteur statistique interne (Double Chance).",
        }

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
        "buts_probables": buts_probables,
        "pourquoi": build_human_summary(event, p, match, buts_probables=buts_probables) if match else None,
        "explanation": _clean_explanation(p.explanation),
    }
