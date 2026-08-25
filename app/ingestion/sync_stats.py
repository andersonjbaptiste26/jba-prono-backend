import re
from sqlalchemy.orm import Session

from ..models import Team, League, TeamStatistics, TeamRating
from ..scoring import compute_team_rating, TeamStats
from .football_data_client import get_standings, COMPETITION_CODES, FootballDataError


def _normalize(name: str) -> str:
    name = re.sub(r"\b(FC|CF|AFC|SC|AC)\b", "", name, flags=re.IGNORECASE)
    return re.sub(r"[^a-z0-9]", "", name.lower())


def _match_team(team_name: str, table: list[dict]) -> dict | None:
    target = _normalize(team_name)
    for entry in table:
        fd_name = entry["team"]["name"]
        fd_short = entry["team"].get("shortName", "")
        if _normalize(fd_name) == target or _normalize(fd_short) == target:
            return entry
        if target in _normalize(fd_name) or _normalize(fd_name) in target:
            return entry
    return None


def _parse_form(form_str: str | None) -> str:
    if not form_str:
        return ""
    mapping = {"W": "V", "D": "N", "L": "D"}
    return "".join(mapping.get(p.strip(), "") for p in form_str.split(",")[-5:])


def sync_team_stats_for_league(db: Session, league_name: str) -> dict:
    league = db.query(League).filter(League.name == league_name).first()
    if not league:
        return {"league": league_name, "error": "Championnat introuvable en base."}

    code = COMPETITION_CODES.get(league_name)
    known_teams = db.query(Team).filter(Team.league_id == league.id).all()
    if not known_teams:
        return {"league": league_name, "error": "Aucune équipe en base pour ce championnat."}

    data = get_standings(code)
    standings_list = data.get("standings", [])
    total_table = next((s["table"] for s in standings_list if s.get("type") == "TOTAL"), [])
    home_table = next((s["table"] for s in standings_list if s.get("type") == "HOME"), [])
    away_table = next((s["table"] for s in standings_list if s.get("type") == "AWAY"), [])

    processed, skipped = 0, 0
    for team in known_teams:
        entry = _match_team(team.name, total_table)
        if not entry:
            skipped += 1
            continue

        played = entry.get("playedGames", 0) or 0
        wins = entry.get("won", 0) or 0
        draws = entry.get("draw", 0) or 0
        losses = entry.get("lost", 0) or 0
        goals_for = entry.get("goalsFor", 0) or 0
        goals_against = entry.get("goalsAgainst", 0) or 0
        form_last5 = _parse_form(entry.get("form"))

        home_entry = _match_team(team.name, home_table)
        away_entry = _match_team(team.name, away_table)
        home_wins = home_entry.get("won", 0) if home_entry else 0
        away_wins = away_entry.get("won", 0) if away_entry else 0

        ts = db.query(TeamStatistics).filter(
            TeamStatistics.team_id == team.id, TeamStatistics.competition_id.is_(None)
        ).first()
        if not ts:
            ts = TeamStatistics(team_id=team.id)
            db.add(ts)
        ts.matches_played, ts.wins, ts.draws, ts.losses = played, wins, draws, losses
        ts.goals_for, ts.goals_against = goals_for, goals_against
        ts.form_last5, ts.home_wins, ts.away_wins = form_last5, home_wins, away_wins
        db.flush()

        team_stats = TeamStats(
            matches_played=played, wins=wins, draws=draws, losses=losses,
            goals_for=goals_for, goals_against=goals_against, clean_sheets=0,
            form_last5=form_last5, home_wins=home_wins, away_wins=away_wins,
            h2h_win_rate=0.5, squad_availability=0.9,
        )
        rating_result = compute_team_rating(team_stats)

        rating_row = db.query(TeamRating).filter(TeamRating.team_id == team.id).first()
        if not rating_row:
            rating_row = TeamRating(team_id=team.id, league_id=league.id)
            db.add(rating_row)
        rating_row.rating = rating_result["rating"]
        for key, val in rating_result["sub_scores"].items():
            col = {"form": "form_score", "attack": "attack_score", "defense": "defense_score",
                   "home_away": "home_away_score", "season": "season_score",
                   "h2h": "h2h_score", "squad": "squad_score"}[key]
            setattr(rating_row, col, val)

        processed += 1

    db.commit()
    return {"league": league_name, "teams_processed": processed, "teams_skipped": skipped}


def sync_all_team_stats(db: Session) -> list[dict]:
    results = []
    for league_name in COMPETITION_CODES:
        try:
            results.append(sync_team_stats_for_league(db, league_name))
        except FootballDataError as e:
            results.append({"league": league_name, "error": str(e)})
    return results
