"""
Migration 002 — Ajout du champ competition_type sur matches
+ is_national_team sur teams + création index.
À exécuter UNE SEULE FOIS après déploiement du nouveau models.py.
"""
import os
from sqlalchemy import create_engine, text

DATABASE_URL = os.getenv("DATABASE_URL", "")
if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL manquante dans les variables d'environnement.")

# psycopg3 : on force le driver explicite
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql+psycopg://", 1)
elif DATABASE_URL.startswith("postgresql://") and "+psycopg" not in DATABASE_URL:
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+psycopg://", 1)

engine = create_engine(DATABASE_URL, future=True)


MIGRATION_SQL = """
-- 1. Ajout competition_type sur matches
ALTER TABLE matches
ADD COLUMN IF NOT EXISTS competition_type VARCHAR(20) DEFAULT 'club';

CREATE INDEX IF NOT EXISTS ix_matches_competition_type
ON matches(competition_type);

-- 2. Ajout is_national_team sur teams
ALTER TABLE teams
ADD COLUMN IF NOT EXISTS is_national_team BOOLEAN DEFAULT FALSE;

CREATE INDEX IF NOT EXISTS ix_teams_is_national
ON teams(is_national_team);

-- 3. Mise à jour des matchs existants
UPDATE matches
SET competition_type = 'national_team'
WHERE competition IN ('UNL', 'EC', 'WC')
  AND (competition_type IS NULL OR competition_type = 'club');

UPDATE matches
SET competition_type = 'cup'
WHERE competition IN ('CL', 'EL', 'ECL')
  AND (competition_type IS NULL OR competition_type = 'club');

-- 4. Marquer les équipes nationales
UPDATE teams
SET is_national_team = TRUE
WHERE id IN (
    SELECT DISTINCT home_team_id FROM matches WHERE competition IN ('UNL', 'EC', 'WC')
    UNION
    SELECT DISTINCT away_team_id FROM matches WHERE competition IN ('UNL', 'EC', 'WC')
);

-- 5. Index composés utiles pour le moteur
CREATE INDEX IF NOT EXISTS ix_matches_comp_date
ON matches(competition, utc_date);

CREATE INDEX IF NOT EXISTS ix_matches_status_date
ON matches(status, utc_date);
"""


def run():
    print(f"→ Connexion à la DB...")
    with engine.begin() as conn:
        for statement in MIGRATION_SQL.split(";"):
            stmt = statement.strip()
            if stmt:
                try:
                    conn.execute(text(stmt))
                except Exception as e:
                    print(f"⚠️ Erreur sur : {stmt[:80]}... → {e}")
    print("✅ Migration 002 appliquée avec succès.")


if __name__ == "__main__":
    run()
