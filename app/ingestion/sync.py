"""
Synchronise les matchs et cotes de The Odds API vers la base PostgreSQL.
"""
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
    competition = _get_or_create_competition(db, league)

    created, updated = 0, 0

    for game in games:
        home = _get_or_create_team(db, game["home_team"], league.id)
        away = _get_or_create_team(db, game["away_team"], league.id)

        kickoff = datetime.fromisoformat(game["commence_time"].replace("Z", "+00:00"))

        match = db.query(Match).filter(Match.external_id == game["id"]).first()
        if not match:
            match = Match(
                competition_id=competition.id,
                home_team_id=home.id,
                away_team_id=away.id,
                kickoff_at=kickoff,
                status="scheduled",
                external_id=game["id"],
            )
            db.add(match)
            db.flush()
            created += 1
        else:
            match.kickoff_at = kickoff
            updated += 1

        if game.get("bookmakers"):
            bookmaker = game["bookmakers"][0]
            h2h_market = next((m for m in bookmaker["markets"] if m["key"] == "h2h"), None)
            if h2h_market:
                for outcome in h2h_market["outcomes"]:
                    db.add(Odds(
                        match_id=match.id,
                        market="h2h",
                        selection=outcome["name"],
                        value=outcome["price"],
                        source=bookmaker["key"],
                    ))
                    if outcome["name"] == game["home_team"]:
                        label = "1 — Victoire domicile"
                    elif outcome["name"] == game["away_team"]:
                        label = "2 — Victoire extérieur"
                    else:
                        label = "X — Match nul"

                    event = db.query(Event).filter(
                        Event.match_id == match.id, Event.label == label
                    ).first()
                    if event:
                        event.odds_value = outcome["price"]
                    else:
                        db.add(Event(
                            match_id=match.id,
                            type="resultat",
                            label=label,
                            odds_value=outcome["price"],
                        ))

    db.commit()
    return {"league": league_name, "matches_created": created, "matches_updated": updated, "total_fetched": len(games)}


def sync_all_leagues(db: Session) -> list[dict]:
    results = []
    for sport_key, league_name in LEAGUE_KEYS.items():
        try:
            result = sync_league(db, sport_key, league_name)
            results.append(result)
        except OddsApiError as e:
            results.append({"league": league_name, "error": str(e)})
    return results
