"""
Modèles SQLAlchemy 2.0 — JBa Prono
"""
from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Float, DateTime, Boolean,
    ForeignKey, Text, Index, UniqueConstraint
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


# ============================================================
# ÉQUIPES
# ============================================================
class Team(Base):
    __tablename__ = "teams"

    id = Column(Integer, primary_key=True, index=True)
    external_id = Column(Integer, unique=True, index=True)  # ID football-data.org
    name = Column(String(120), nullable=False, index=True)
    short_name = Column(String(60))
    tla = Column(String(5))  # ex: 'PSG', 'FRA'
    country = Column(String(80))
    logo_url = Column(String(500))
    is_national_team = Column(Boolean, default=False, index=True)  # ← utile pour UNL
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relations
    home_matches = relationship("Match", foreign_keys="Match.home_team_id", back_populates="home_team")
    away_matches = relationship("Match", foreign_keys="Match.away_team_id", back_populates="away_team")


# ============================================================
# MATCHS
# ============================================================
class Match(Base):
    __tablename__ = "matches"

    id = Column(Integer, primary_key=True, index=True)
    external_id = Column(Integer, unique=True, index=True)  # ID football-data.org
    competition = Column(String(10), index=True)  # 'PL', 'UNL', 'CL'...
    competition_name = Column(String(120))
    competition_type = Column(String(20), default="club", index=True)  # ← AJOUT : 'club', 'cup', 'national_team'
    season = Column(Integer, index=True)
    matchday = Column(Integer, nullable=True)
    stage = Column(String(60), nullable=True)  # ex: 'GROUP_STAGE', 'FINAL'

    home_team_id = Column(Integer, ForeignKey("teams.id"), index=True)
    away_team_id = Column(Integer, ForeignKey("teams.id"), index=True)
    home_team_name = Column(String(120))
    away_team_name = Column(String(120))

    utc_date = Column(DateTime, index=True)
    status = Column(String(30), default="SCHEDULED")  # SCHEDULED, LIVE, FINISHED, POSTPONED
    matchday_label = Column(String(40), nullable=True)

    home_score = Column(Integer, nullable=True)
    away_score = Column(Integer, nullable=True)
    winner = Column(String(10), nullable=True)  # 'HOME_TEAM', 'AWAY_TEAM', 'DRAW'

    # Cotes (stockées pour historique)
    odd_home = Column(Float, nullable=True)   # 1
    odd_draw = Column(Float, nullable=True)   # X
    odd_away = Column(Float, nullable=True)   # 2
    odd_1x = Column(Float, nullable=True)     # 1X (calculé)
    odd_2x = Column(Float, nullable=True)     # 2X (calculé)
    bookmaker = Column(String(80), nullable=True)

    # Probabilités calculées
    prob_home = Column(Float, nullable=True)
    prob_draw = Column(Float, nullable=True)
    prob_away = Column(Float, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relations
    home_team = relationship("Team", foreign_keys=[home_team_id], back_populates="home_matches")
    away_team = relationship("Team", foreign_keys=[away_team_id], back_populates="away_matches")

    __table_args__ = (
        Index("ix_matches_comp_date", "competition", "utc_date"),
        Index("ix_matches_status_date", "status", "utc_date"),
    )


# ============================================================
# RATINGS ÉQUIPES (moteur de prédiction)
# ============================================================
class TeamRating(Base):
    __tablename__ = "team_ratings"

    id = Column(Integer, primary_key=True, index=True)
    team_id = Column(Integer, ForeignKey("teams.id"), index=True)
    competition = Column(String(10), index=True)
    rating = Column(Float, default=50.0)          # 0-100
    form_score = Column(Float, default=50.0)
    attack_score = Column(Float, default=50.0)
    defense_score = Column(Float, default=50.0)
    home_score = Column(Float, default=50.0)
    away_score = Column(Float, default=50.0)
    h2h_score = Column(Float, default=50.0)
    squad_score = Column(Float, default=50.0)
    matches_played = Column(Integer, default=0)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("team_id", "competition", name="uq_team_competition"),
    )


# ============================================================
# PRÉDICTIONS
# ============================================================
class Prediction(Base):
    __tablename__ = "predictions"

    id = Column(Integer, primary_key=True, index=True)
    match_id = Column(Integer, ForeignKey("matches.id"), index=True)
    pick = Column(String(20))        # '1', 'X', '2', '1X', '2X', 'BTTS', 'OVER'
    probability = Column(Float)      # 0-1
    confidence = Column(String(20))  # 'low', 'medium', 'high'
    odd = Column(Float, nullable=True)
    value = Column(Float, nullable=True)  # (prob * odd) - 1
    created_at = Column(DateTime, default=datetime.utcnow)


# ============================================================
# TICKETS SUGGÉRÉS (admin)
# ============================================================
class SuggestedTicket(Base):
    __tablename__ = "suggested_tickets"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(200))
    description = Column(Text, nullable=True)
    total_odd = Column(Float)
    status = Column(String(20), default="pending")  # pending, won, lost, void
    picks_json = Column(Text)  # JSON des picks
    published_at = Column(DateTime, default=datetime.utcnow)
    settled_at = Column(DateTime, nullable=True)


# ============================================================
# SESSIONS ANALYTICS (dashboard admin)
# ============================================================
class AnalyticsSession(Base):
    __tablename__ = "analytics_sessions"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String(80), index=True)
    user_code = Column(String(40), nullable=True, index=True)
    lang = Column(String(5), default="fr")
    event = Column(String(60), index=True)  # 'view_pick', 'add_panier', etc.
    payload = Column(Text, nullable=True)   # JSON libre
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
