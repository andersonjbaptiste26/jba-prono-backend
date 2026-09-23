## [0.1.0] — Update journal + Double Chance

### Ajouté
- **Onglet Journal** (front) : notes de match locales, isolées par `user_id`,
  avec boutons flottants (+) pour ajouter et (💬) pour consulter.
  Chaque note contient : date, pays, équipe, données du match.
  Plusieurs notes possibles pour le même jour, triées par date décroissante.
- **Module `app/prediction/double_chance.py`** : calcul officiel des cotes
  Double Chance (1X / X2 / 12) via la formule bookmaker
  `O_AB = (O_A × O_B) / (O_A + O_B)`, avec application d'une marge
  (overround) configurable via `taux_marge` (défaut 0.95 = marge 5 %).

### Modifié
- **Cotes Double Chance** dans `/predictions/best` : passent de la cote
  probabiliste (`100 / prob`) à la **cote bookmaker réaliste**
  `cote_double_chance(O_A, O_B, marge=0.95)`.
  L'`explanation` expose désormais `formule`, `odd_source_a` et
  `odd_source_b` pour la traçabilité.
- **Panier (front)** : rafraîchit cotes et probabilités au moment de
  la validation (`validerPari`) avant envoi au backend.
- **Historique (front)** : affiche le `%` de probabilité au moment du
  pari à côté de chaque sélection.

### Supprimé
- **Onglet "Tickets"** (front) — remplacé par Journal.
  L'endpoint `/tickets/best-combo` reste disponible côté API pour
  un usage futur.

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
