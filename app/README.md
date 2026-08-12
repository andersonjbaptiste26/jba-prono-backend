# JBa Prono — Backend

Squelette Backend (FastAPI + PostgreSQL) correspondant à la roadmap :
étape "Phase 2 — Backend" et "Phase 6 — Top 5 équipes".

## Contenu

```
jba-prono-backend/
├── database/
│   └── schema.sql          # Toutes les tables (users, teams, matches, predictions, bets...)
├── app/
│   ├── main.py              # App FastAPI + routes
│   ├── database.py          # Connexion PostgreSQL
│   ├── models.py            # Modèles SQLAlchemy
│   ├── scoring.py           # Moteur de Team Rating (pondération phase 6)
│   └── routers/
│       ├── matches.py       # GET /matches, GET /matches/:id
│       ├── predictions.py   # GET /predictions, GET /predictions/best
│       ├── teams.py         # GET /teams/top
│       └── bets.py          # POST /bets, GET /bets/history
└── requirements.txt
```

## Étape 1 — Créer la base de données (5 min)

1. Va sur https://neon.tech (ou https://supabase.com) et crée un compte gratuit
2. Crée un nouveau projet PostgreSQL — tu obtiens une URL du type :
   `postgresql://user:password@host/dbname`
3. Ouvre l'éditeur SQL du projet et colle le contenu de `database/schema.sql` — ça crée toutes les tables

## Étape 2 — Déployer le backend sur Railway (10 min)

1. Va sur https://railway.app et crée un compte (gratuit pour démarrer)
2. Crée un dépôt GitHub avec ce dossier `jba-prono-backend/`
   (upload direct sur github.com si tu n'utilises pas encore Git)
3. Dans Railway : "New Project" → "Deploy from GitHub repo" → sélectionne ton dépôt
4. Dans les variables d'environnement du service, ajoute :
   `DATABASE_URL = <l'URL PostgreSQL obtenue à l'étape 1>`
5. Railway détecte `requirements.txt` et déploie automatiquement.
   Commande de démarrage à renseigner si besoin :
   `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
6. Une fois déployé, Railway te donne une URL publique, ex :
   `https://jba-prono-backend-production.up.railway.app`

## Étape 3 — Tester

Ouvre `https://<ton-url-railway>/docs` sur ton téléphone — FastAPI génère
automatiquement une interface de test pour toutes les routes (Swagger UI).

## Étape 4 — Connecter le frontend

Dans le prochain squelette (Next.js), les appels API pointeront vers
cette URL Railway au lieu des données fictives (mock) de la démo actuelle.

## Prochaine étape : l'API sportive

Le backend est prêt à recevoir des données, mais rien ne les alimente encore.
Options courantes pour la phase 3 :

| API | Points forts | Modèle |
|---|---|---|
| API-Football (api-sports.io) | Très complet, bon rapport qualité/prix | Freemium |
| SportMonks | Bonne doc, cotes incluses | Payant, plans souples |
| Opta / StatsPerform | Référence pro | Cher, réservé gros volumes |

Il faudra choisir une API, créer un module `app/ingestion/` qui interroge
cette API et remplit les tables `matches`, `teams`, `team_statistics`, `odds`.
