from datetime import datetime
from sqlalchemy.orm import Session

from ..models import League, Competition, Team, Match, Odds, Event
from .odds_api_client import fetch_odds, LEAGUE_KEYS, OddsApiError


def _get_or_create_league(db: Session, name: str) -> League:
    league = db.query(League).filter(League.name == name).first()
    if not league:
        league = League(name=name, country="Europe", tier="national")
        db.add(league)
        db.flush()
    return league


def _get_or_create_competition(db: Session, league: League) -> Competition:
    comp = db.query(Competition).filter(Competition.league_id == league.id).first()
    if not comp:
        comp = Competition(league_id=league.id, name=league.name, type="championnat")
        db.add(comp)
        db.flush()
    return comp


def _get_or_create_team(db: Session, name: str, league_id: int) -> Team:
    team = db.query(Team).filter(Team.name == name, Team.league_id == league_id).first()
    if not team:
        team = Team(name=name, short_name=name[:30], league_id=league_id)
        db.add(team)
        db.flush()
    return team


def sync_league(db: Session, sport_key: str, league_name: str) -> dict:
    games = fetch_odds(sport_key)
    league = _get_or_create_league(db, league_name)
    competition
