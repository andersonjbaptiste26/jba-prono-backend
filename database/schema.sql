-- ============================================================
-- JBa Prono — Schéma PostgreSQL
-- ============================================================

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ---------- Utilisateurs ----------
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    display_name VARCHAR(100),
    created_at TIMESTAMPTZ DEFAULT now()
);

-- ---------- Ligues / Compétitions / Saisons ----------
CREATE TABLE leagues (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,             -- Premier League, La Liga, ...
    country VARCHAR(100),
    tier VARCHAR(30),                       -- national, coupe, europeenne
    external_id VARCHAR(50)                 -- id renvoyé par l'API sportive
);

CREATE TABLE competitions (
    id SERIAL PRIMARY KEY,
    league_id INT REFERENCES leagues(id),
    name VARCHAR(100) NOT NULL,             -- Champions League, Coupe nationale...
    type VARCHAR(30),                       -- championnat, coupe, supercoupe, europeenne
    external_id VARCHAR(50)
);

CREATE TABLE seasons (
    id SERIAL PRIMARY KEY,
    league_id INT REFERENCES leagues(id),
    label VARCHAR(20) NOT NULL,             -- "2025/2026"
    start_date DATE,
    end_date DATE
);

-- ---------- Équipes / Joueurs ----------
CREATE TABLE teams (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    short_name VARCHAR(30),
    league_id INT REFERENCES leagues(id),
    country VARCHAR(100),
    logo_url TEXT,
    external_id VARCHAR(50)
);

CREATE TABLE players (
    id SERIAL PRIMARY KEY,
    team_id INT REFERENCES teams(id),
    name VARCHAR(100) NOT NULL,
    position VARCHAR(30),
    is_injured BOOLEAN DEFAULT false,
    is_suspended BOOLEAN DEFAULT false,
    external_id VARCHAR(50)
);

-- ---------- Matchs ----------
CREATE TABLE matches (
    id SERIAL PRIMARY KEY,
    competition_id INT REFERENCES competitions(id),
    season_id INT REFERENCES seasons(id),
    home_team_id INT REFERENCES teams(id),
    away_team_id INT REFERENCES teams(id),
    kickoff_at TIMESTAMPTZ NOT NULL,
    status VARCHAR(20) DEFAULT 'scheduled',  -- scheduled, live, finished, postponed
    home_score INT,
    away_score INT,
    external_id VARCHAR(50),
    UNIQUE(external_id)
);

-- ---------- Cotes ----------
CREATE TABLE odds (
    id SERIAL PRIMARY KEY,
    match_id INT REFERENCES matches(id) ON DELETE CASCADE,
    market VARCHAR(50) NOT NULL,             -- "1X2", "over_under_2.5", "btts"...
    selection VARCHAR(50) NOT NULL,          -- "1", "X", "2", "over", "yes"...
    value NUMERIC(6,2) NOT NULL,
    source VARCHAR(50),
    fetched_at TIMESTAMPTZ DEFAULT now()
);

-- ---------- Statistiques équipe / match ----------
CREATE TABLE team_statistics (
    id SERIAL PRIMARY KEY,
    team_id INT REFERENCES teams(id),
    competition_id INT REFERENCES competitions(id),  -- stats contextualisées par compétition
    season_id INT REFERENCES seasons(id),
    matches_played INT DEFAULT 0,
    wins INT DEFAULT 0,
    draws INT DEFAULT 0,
    losses INT DEFAULT 0,
    goals_for INT DEFAULT 0,
    goals_against INT DEFAULT 0,
    clean_sheets INT DEFAULT 0,
    btts_count INT DEFAULT 0,
    form_last5 VARCHAR(10),                  -- ex: "VVNVD"
    home_wins INT DEFAULT 0,
    away_wins INT DEFAULT 0,
    updated_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE(team_id, competition_id, season_id)
);

CREATE TABLE match_statistics (
    id SERIAL PRIMARY KEY,
    match_id INT REFERENCES matches(id) ON DELETE CASCADE,
    home_possession NUMERIC(5,2),
    away_possession NUMERIC(5,2),
    home_shots INT,
    away_shots INT,
    home_corners INT,
    away_corners INT,
    home_cards INT,
    away_cards INT
);

-- ---------- Team Rating (classement dynamique, phase 6/7) ----------
CREATE TABLE team_ratings (
    id SERIAL PRIMARY KEY,
    team_id INT REFERENCES teams(id),
    league_id INT REFERENCES leagues(id),
    rating NUMERIC(6,3) NOT NULL,            -- score pondéré 0-100
    form_score NUMERIC(5,2),
    attack_score NUMERIC(5,2),
    defense_score NUMERIC(5,2),
    home_away_score NUMERIC(5,2),
    season_score NUMERIC(5,2),
    h2h_score NUMERIC(5,2),
    squad_score NUMERIC(5,2),
    computed_at TIMESTAMPTZ DEFAULT now()
);

-- ---------- Événements & Prédictions ----------
CREATE TABLE events (
    id SERIAL PRIMARY KEY,
    match_id INT REFERENCES matches(id) ON DELETE CASCADE,
    type VARCHAR(30) NOT NULL,               -- resultat, buts, btts, equipe
    label VARCHAR(50) NOT NULL,              -- "1X", "+2.5", "BTTS Oui"...
    odds_value NUMERIC(6,2)
);

CREATE TABLE predictions (
    id SERIAL PRIMARY KEY,
    event_id INT REFERENCES events(id) ON DELETE CASCADE,
    probability NUMERIC(5,2) NOT NULL,       -- 0-100
    confidence_tier VARCHAR(20),             -- tresforte, forte, elevee
    model_version VARCHAR(30),
    explanation JSONB,                       -- facteurs: forme, H2H, domicile/exterieur...
    generated_at TIMESTAMPTZ DEFAULT now()
);

-- ---------- Panier / Historique de paris ----------
CREATE TABLE bets (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(id),
    stake NUMERIC(10,2) NOT NULL,
    total_odds NUMERIC(8,3) NOT NULL,
    potential_gain NUMERIC(10,2) NOT NULL,
    status VARCHAR(20) DEFAULT 'en_cours',   -- en_cours, gagne, perdu
    created_at TIMESTAMPTZ DEFAULT now(),
    settled_at TIMESTAMPTZ
);

CREATE TABLE bet_selections (
    id SERIAL PRIMARY KEY,
    bet_id UUID REFERENCES bets(id) ON DELETE CASCADE,
    event_id INT REFERENCES events(id),
    odds_value NUMERIC(6,2) NOT NULL,
    probability_at_bet NUMERIC(5,2)
);

-- ---------- Index utiles ----------
CREATE INDEX idx_matches_kickoff ON matches(kickoff_at);
CREATE INDEX idx_predictions_probability ON predictions(probability DESC);
CREATE INDEX idx_team_ratings_league ON team_ratings(league_id, rating DESC);
CREATE INDEX idx_bets_user ON bets(user_id, created_at DESC);
