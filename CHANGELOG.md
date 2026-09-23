# Changelog — JBa Prono

## [1.0.0] — 2026

### Ajouté
- Endpoint `/health` enrichi : statut PostgreSQL + version API
- Lifespan FastAPI avec test de connexion DB au démarrage
- Contraintes d'unicité : `Prediction.event_id`, `Event(match_id, type, label)`,
  `TeamRating.team_id`, `TeamStatistics(team_id, competition_id)`,
  `Competition(league_id, name)`, `Team(name, league_id)`
- `BetSelection.probability_at_bet` désormais rempli à la création du pari
- Chargement `.env` via `python-dotenv` (dev local)
- SSL forcé automatiquement pour les bases distantes

### Corrigé
- **Whitelist équipes/compétitions** : normalisation (accents, casse, préfixes)
  → les prédictions remontent à nouveau correctement
- **`bets.py`** : null-safety sur `odds_value`, rejet des sélections dupliquées
  et des matchs déjà commencés
- **`settlement.py`** : parsing robuste des labels buts via regex
- **`combos.py`** : homogénéisation sur événements `resultat` uniquement
- **`narrative.py`** : gestion explicite du type `double_chance`
- `Predictions.py` : construction correcte du résumé pour les doubles chances

### Supprimé
- `app/match_sync.py` (intégration Groq LLM sur tables inexistantes)
- `app/window_manager.py` (incompatible avec `models.py`)
- Dépendance `psycopg2-binary` (redondante avec `psycopg[binary]`)

## [0.3.0] — versions antérieures
- Voir historique Git.
