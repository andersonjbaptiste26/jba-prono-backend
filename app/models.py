import uuid
# rebuild trigger
from sqlalchemy import (
    Column, Integer, String, Numeric, Boolean, TIMESTAMP, Date, ForeignKey, JSON, func
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()

class Season(Base):
    __tablename__ = "seasons"
    id = Column(Integer, primary_key=True)
    league_id = Column(Integer, ForeignKey("leagues.id"))
    label = Column(String)
    start_date = Column(Date)
    end_date = Column(Date)
    
class League(Base):
    __tablename__ = "leagues"
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    country = Column(String)
    tier = Column(String)
    external_id = Column(String)


class Competition(Base):
    __tablename__ = "competitions"
    id = Column(Integer, primary_key=True)
    league_id = Column(Integer, ForeignKey("leagues.id"))
    name = Column(String, nullable=False)
    type = Column(String)
    external_id = Column(String)


class Team(Base):
    __tablename__ = "teams"
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    short_name = Column(String)
    league_id = Column(Integer, ForeignKey("leagues.id"))
    country = Column(String)
    logo_url = Column(String)
    external_id = Column(String)


class Match(Base):
    __tablename__ = "matches"
    id = Column(Integer, primary_key=True)
    competition_id = Column(Integer, ForeignKey("competitions.id"))
    season_id = Column(Integer, ForeignKey("seasons.id"))
    home_team_id = Column(Integer, ForeignKey("teams.id"))
    away_team_id = Column(Integer, ForeignKey("teams.id"))
    kickoff_at = Column(TIMESTAMP(timezone=True), nullable=False)
    status = Column(String, default="scheduled")
    home_score = Column(Integer)
    away_score = Column(Integer)
    external_id = Column(String, unique=True)

    home_team = relationship("Team", foreign_keys=[home_team_id])
    away_team = relationship("Team", foreign_keys=[away_team_id])
    events = relationship("Event", back_populates="match")
    competition = relationship("Competition")

class TeamStatistics(Base):
    __tablename__ = "team_statistics"
    id = Column(Integer, primary_key=True)
    team_id = Column(Integer, ForeignKey("teams.id"))
    competition_id = Column(Integer, ForeignKey("competitions.id"), nullable=True)
    season_id = Column(Integer, ForeignKey("seasons.id"), nullable=True)
    matches_played = Column(Integer, default=0)
    wins = Column(Integer, default=0)
    draws = Column(Integer, default=0)
    losses = Column(Integer, default=0)
    goals_for = Column(Integer, default=0)
    goals_against = Column(Integer, default=0)
    clean_sheets = Column(Integer, default=0)
    btts_count = Column(Integer, default=0)
    form_last5 = Column(String)
    home_wins = Column(Integer, default=0)
    away_wins = Column(Integer, default=0)
    updated_at = Column(TIMESTAMP(timezone=True), server_default=func.now())


class Odds(Base):
    __tablename__ = "odds"
    id = Column(Integer, primary_key=True)
    match_id = Column(Integer, ForeignKey("matches.id"))
    market = Column(String, nullable=False)
    selection = Column(String, nullable=False)
    value = Column(Numeric(6, 2), nullable=False)
    source = Column(String)
    fetched_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    
class Event(Base):
    __tablename__ = "events"
    id = Column(Integer, primary_key=True)
    match_id = Column(Integer, ForeignKey("matches.id"))
    type = Column(String, nullable=False)
    label = Column(String, nullable=False)
    odds_value = Column(Numeric(6, 2))

    match = relationship("Match", back_populates="events")
    prediction = relationship("Prediction", back_populates="event", uselist=False)


class Prediction(Base):
    __tablename__ = "predictions"
    id = Column(Integer, primary_key=True)
    event_id = Column(Integer, ForeignKey("events.id"))
    probability = Column(Numeric(5, 2), nullable=False)
    confidence_tier = Column(String)
    model_version = Column(String)
    explanation = Column(JSON)
    generated_at = Column(TIMESTAMP(timezone=True), server_default=func.now())

    event = relationship("Event", back_populates="prediction")


class TeamRating(Base):
    __tablename__ = "team_ratings"
    id = Column(Integer, primary_key=True)
    team_id = Column(Integer, ForeignKey("teams.id"))
    league_id = Column(Integer, ForeignKey("leagues.id"))
    rating = Column(Numeric(6, 3), nullable=False)
    form_score = Column(Numeric(5, 2))
    attack_score = Column(Numeric(5, 2))
    defense_score = Column(Numeric(5, 2))
    home_away_score = Column(Numeric(5, 2))
    season_score = Column(Numeric(5, 2))
    h2h_score = Column(Numeric(5, 2))
    squad_score = Column(Numeric(5, 2))
    computed_at = Column(TIMESTAMP(timezone=True), server_default=func.now())


class User(Base):
    __tablename__ = "users"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String, unique=True, nullable=False)
    password_hash = Column(String, nullable=False)
    display_name = Column(String)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())


class Bet(Base):
    __tablename__ = "bets"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    stake = Column(Numeric(10, 2), nullable=False)
    total_odds = Column(Numeric(8, 3), nullable=False)
    potential_gain = Column(Numeric(10, 2), nullable=False)
    status = Column(String, default="en_cours")
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    settled_at = Column(TIMESTAMP(timezone=True))

    selections = relationship("BetSelection", back_populates="bet")


class BetSelection(Base):
    __tablename__ = "bet_selections"
    id = Column(Integer, primary_key=True)
    bet_id = Column(UUID(as_uuid=True), ForeignKey("bets.id"))
    event_id = Column(Integer, ForeignKey("events.id"))
    odds_value = Column(Numeric(6, 2), nullable=False)
    probability_at_bet = Column(Numeric(5, 2))

    bet = relationship("Bet", back_populates="selections")
