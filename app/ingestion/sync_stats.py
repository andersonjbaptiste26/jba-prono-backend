"""
Synchronise les statistiques d'équipe depuis API-Football, puis calcule
le Team Rating pour chaque équipe déjà connue en base.
"""
import re
from sqlalchemy.orm import Session

from ..models import Team, League, TeamStatistics, TeamRating
from ..scoring import compute_team_rating, TeamStats
from .api_football_client import get_teams, get_team_statistics, LEAGUE_IDS, ApiFootballError


def _normalize(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", name.lower())


def _match_api_football_id(team_name: str, af_teams: list[dict]) -> int | None:
    target = _normalize(team_name)
    for entry in af_teams:
        af_name = entry["team"]["name"]
        if _normalize(af_name) == target or target in _normalize(af_name) or _normalize(af_name) in target:
            return entry["team"]["id"]
    return None


def _parse_form(form_str: str | None) -> str:
    if not form_str:
        return ""
    mapping = {"W": "V", "D": "N", "L": "D"}
    return "".join(mapping.get(c, "") for c in form_str[-5:])


def sync_team_stats_for_league(db: Session, league_name: str) -> dict:
    league = db.query(League).filter(League.name == league_name).first()
    if not league:
        return {"league": league_name, "error": "Championnat introuvable en base (synchronise d'abord les matchs)."}

    af_league_id = LEAGUE_IDS.get(league_name)
    if not af_league_id:
        return {"league": league_name, "error": "Championnat non mappé côté API-Football."}

    known_teams = db.query(Team).filter(Team.league_id == league.id).all()
    if not known_teams:
        return {"league": league_name, "error": "Aucune équipe en base pour ce championnat."}

    af_teams = get_teams(af_league_id)
    processed, skipped = 0, 0

    for team in known_teams:
        af_team_id = _match_api_football_id(team.name, af_teams)
        if not af_team_id:
            skipped += 1
            continue

        stats_raw = get_team_statistics(af_league_id, af_team_id)
        if not stats_raw:
            skipped += 1
            continue

        fixtures = stats_raw.get("fixtures", {})
        goals = stats_raw.get("goals", {})
        clean_sheet = stats_raw.get("clean_sheet", {})

        played = fixtures.get("played", {}).get("total", 0) or 0
        wins = fixtures.get("wins", {}).get("total", 0) or 0
        draws = fixtures.get("draws", {}).get("total", 0) or 0
        losses = fixtures.get("loses", {}).get("total", 0) or 0
        goals_for = goals.get("for", {}).get("total", {}).get("total", 0) or 0
        goals_against = goals.get("against", {}).get("total", {}).get("total", 0) or 0
        clean_sheets = clean_sheet.get("total", 0) or 0
        home_wins = fixtures.get("wins", {}).get("home", 0) or 0
        away_wins = fixtures.get("wins", {}).get("away", 0) or 0
        form_last5 = _parse_form(stats_raw.get("form"))

        ts = db.query(TeamStatistics).filter(
            TeamStatistics.team_id == team.id, TeamStatistics.competition_id.is_(None)
        ).first()
        if not ts:
            ts = TeamStatistics(team_id=team.id)
            db.add(ts)
        ts.matches_played = played
        ts.wins = wins
        ts.draws = draws
        ts.losses = losses
        ts.goals_for = goals_for
        ts.goals_against = goals_against
        ts.clean_sheets = clean_sheets
        ts.form_last5 = form_last5
        ts.home_wins = home_wins
        ts.away_wins = away_wins
        db.flush()

        team_stats = TeamStats(
            matches_played=played, wins=wins, draws=draws, losses=losses,
            goals_for=goals_for, goals_against=goals_against, clean_sheets=clean_sheets,
            form_last5=form_last5, home_wins=home_wins, away_wins=away_wins,
            h2h_win_rate=0.5, squad_availability=0.9,
        )
        rating_result = compute_team_rating(team_stats)

        rating_row = db.query(TeamRating).filter(TeamRating.team_id == team.id).first()
        if not rating_row:
            rating_row = TeamRating(team_id=team.id, league_id=league.id)
            db.add(rating_row)
        rating_row.rating = rating_result["rating"]
        rating_row.form_score = rating_result["sub_scores"]["form"]
        rating_row.attack_score = rating_result["sub_scores"]["attack"]
        rating_row.defense_score = rating_result["sub_scores"]["defense"]
        rating_row.home_away_score = rating_result["sub_scores"]["home_away"]
        rating_row.season_score = rating_result["sub_scores"]["season"]
        rating_row.h2h_score = rating_result["sub_scores"]["h2h"]
        rating_row.squad_score = rating_result["sub_scores"]["squad"]

        processed += 1

    db.commit()
    return {"league": league_name, "teams_processed": processed, "teams_skipped": skipped}


def sync_all_team_stats(db: Session) -> list[dict]:
    results = []
    for league_name in LEAGUE_IDS:
        try:
            results.append(sync_team_stats_for_league(db, league_name))
        except ApiFootballError as e:
            results.append({"league": league_name, "error": str(e)})
    return results
