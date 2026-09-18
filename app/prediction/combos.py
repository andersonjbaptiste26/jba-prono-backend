"""
Combine des pronostics sur une fenêtre de 2 à 7 jours consécutifs
en tickets multiples, selon les critères :
- cote combinée entre 3 et 9
- somme des probabilités individuelles >= 75%
- 2 à 6 matchs par ticket
- répartis sur 2 à 7 jours consécutifs

Affiche aussi la VRAIE probabilité combinée (produit des probabilités,
pas la somme) pour rester honnête — la somme demandée sert de filtre,
mais ne représente pas la chance réelle de gagner le ticket entier.

⚡ Optimisations pour éviter l'explosion combinatoire :
- tri des prédictions par probabilité DESC dans chaque jour
- limite adaptative du nombre de combinaisons testées par (fenêtre, taille)
- déduplication par set d'event_id
"""
import time
from math import comb
from itertools import combinations
from collections import defaultdict
from sqlalchemy.orm import Session
from sqlalchemy import func

from ..models import Prediction, Event, Match

# ─── Critères métier ───
MIN_INDIVIDUAL_PROB = 50.0
MIN_COMBO_SIZE = 2
MAX_COMBO_SIZE = 6            # 🆕 4 → 6
MIN_TOTAL_ODDS = 3.0
MAX_TOTAL_ODDS = 9.0          # 🆕 6 → 9
MIN_PROB_SUM = 75.0
MIN_DAYS_WINDOW = 2           # 🆕 fenêtre minimale (jours consécutifs)
MAX_DAYS_WINDOW = 7           # 🆕 fenêtre maximale
TOP_N_RESULTS = 7             # 🆕 3 → 7

# ─── Optimisations de performance ───
MAX_COMBOS_PER_CALL = 20_000  # par (fenêtre, taille)
MAX_POOL_HARD_CAP = 30        # taille max du pool par fenêtre


def _eligible_predictions(db: Session) -> list[Prediction]:
    """Récupère les prédictions éligibles (proba >= 50%, matchs à venir)."""
    return (
        db.query(Prediction)
        .join(Event, Prediction.event_id == Event.id)
        .join(Match, Event.match_id == Match.id)
        .filter(Prediction.probability >= MIN_INDIVIDUAL_PROB)
        .filter(Match.kickoff_at >= func.now())
        .all()
    )


def _group_by_date(predictions: list[Prediction]) -> dict:
    """Regroupe les prédictions par date de match."""
    by_date = defaultdict(list)
    for p in predictions:
        d = p.event.match.kickoff_at.date()
        by_date[d].append(p)
    return by_date


def _max_pool_size(max_combos: int, size: int, hard_cap: int = MAX_POOL_HARD_CAP) -> int:
    """Trouve le plus grand n tel que C(n, size) <= max_combos."""
    for n in range(hard_cap, size - 1, -1):
        if comb(n, size) <= max_combos:
            return n
    return size


def compute_combo(selections: list[Prediction]) -> dict | None:
    """Calcule les métriques d'une combinaison (cote totale, somme probas, vraie proba)."""
    total_odds = 1.0
    prob_sum = 0.0
    real_prob = 1.0
    for p in selections:
        odds = float(p.event.odds_value) if p.event.odds_value else None
        if not odds:
            return None
        total_odds *= odds
        prob_sum += float(p.probability)
        real_prob *= (float(p.probability) / 100.0)
    return {
        "total_odds": round(total_odds, 3),
        "probability_sum": round(prob_sum, 2),
        "real_combined_probability": round(real_prob * 100, 2),
    }


def generate_ticket_combos(db: Session) -> list[dict]:
    """
    Génère jusqu'à TOP_N_RESULTS combinaisons optimales.

    Parcourt toutes les fenêtres de 2 à 7 jours consécutifs, et pour
    chacune teste les combinaisons de 2 à 6 matchs.
    """
    t0 = time.time()

    predictions = _eligible_predictions(db)
    by_date = _group_by_date(predictions)
    dates_sorted = sorted(by_date.keys())

    # ⚡ Tri par probabilité DESC dans chaque jour (meilleures d'abord)
    for d in by_date:
        by_date[d].sort(key=lambda p: float(p.probability), reverse=True)

    candidates = []
    seen_combos = set()

    # ─── Boucle sur les fenêtres de 2 à 7 jours ───
    for window_size in range(MIN_DAYS_WINDOW, MAX_DAYS_WINDOW + 1):
        for i in range(len(dates_sorted) - window_size + 1):
            window_dates = dates_sorted[i:i + window_size]

            # Vérifier que les jours sont bien consécutifs
            if any((window_dates[j + 1] - window_dates[j]).days != 1
                   for j in range(len(window_dates) - 1)):
                continue

            # Pool : toutes les prédictions des jours de la fenêtre
            full_pool = []
            for d in window_dates:
                full_pool.extend(by_date[d])

            if len(full_pool) < MIN_COMBO_SIZE:
                continue

            # ⚡ Tri global par probabilité DESC
            full_pool.sort(key=lambda p: float(p.probability), reverse=True)

            # ─── Tester chaque taille de combinaison ───
            for size in range(MIN_COMBO_SIZE, MAX_COMBO_SIZE + 1):
                if size > len(full_pool):
                    continue

                # ⚡ Limite adaptative pour éviter l'explosion combinatoire
                max_pool = _max_pool_size(MAX_COMBOS_PER_CALL, size)
                pool = full_pool[:max_pool]

                for combo in combinations(pool, size):
                    # Déduplication (évite les doublons entre fenêtres)
                    combo_key = frozenset(p.event.id for p in combo)
                    if combo_key in seen_combos:
                        continue

                    # Vérifier que tous les matchs sont différents
                    match_ids = {p.event.match_id for p in combo}
                    if len(match_ids) != size:
                        continue

                    metrics = compute_combo(list(combo))
                    if not metrics:
                        continue

                    if (MIN_TOTAL_ODDS <= metrics["total_odds"] <= MAX_TOTAL_ODDS
                            and metrics["probability_sum"] >= MIN_PROB_SUM):
                        seen_combos.add(combo_key)

                        # Dates réellement utilisées par ce combo
                        used_dates = sorted({p.event.match.kickoff_at.date() for p in combo})

                        candidates.append({
                            "selections": combo,
                            "dates": [d.isoformat() for d in used_dates],
                            **metrics,
                        })

    # Tri final : meilleure probabilité réelle en premier
    candidates.sort(key=lambda c: c["real_combined_probability"], reverse=True)

    elapsed = time.time() - t0
    print(f"🎯 generate_ticket_combos : {len(candidates)} candidats en {elapsed:.2f}s "
          f"({len(dates_sorted)} jours, {sum(len(v) for v in by_date.values())} prédictions)")

    return candidates[:TOP_N_RESULTS]
