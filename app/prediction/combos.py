"""
Combine des pronostics sur une fenêtre de 2 à 7 jours consécutifs
en tickets multiples.

⚡ VERSION OPTIMISÉE POUR PRODUCTION :
- Pool strict : 6 items max par jour, 18 par fenêtre
- DFS avec élagage triple + budget temps (5s max)
- Timeout de sécurité absolu
"""
import time
from collections import defaultdict
from sqlalchemy.orm import Session
from sqlalchemy import func

from ..models import Prediction, Event, Match

# ─── Critères métier ───
MIN_INDIVIDUAL_PROB = 50.0
MIN_COMBO_SIZE = 2
MAX_COMBO_SIZE = 6
MIN_TOTAL_ODDS = 3.0
MAX_TOTAL_ODDS = 9.0
MIN_PROB_SUM = 75.0
MIN_DAYS_WINDOW = 2
MAX_DAYS_WINDOW = 7
TOP_N_RESULTS = 7

# ─── Budgets STRICTS (essentiels pour Render) ───
MAX_POOL_PER_DAY = 6            # 6 items/jour max
MAX_POOL_PER_WINDOW = 18        # 18 items max par fenêtre
MAX_DFS_RESULTS = 300           # résultats max par fenêtre
TIME_BUDGET_SECONDS = 5.0       # ⏱️ STOP après 5 secondes


def _eligible_predictions(db: Session) -> list[Prediction]:
    return (
        db.query(Prediction)
        .join(Event, Prediction.event_id == Event.id)
        .join(Match, Event.match_id == Match.id)
        .filter(Prediction.probability >= MIN_INDIVIDUAL_PROB)
        .filter(Match.kickoff_at >= func.now())
        .all()
    )


def _group_by_date(predictions: list[Prediction]) -> dict:
    by_date = defaultdict(list)
    for p in predictions:
        d = p.event.match.kickoff_at.date()
        by_date[d].append(p)
    return by_date


def _dfs_search(pool, min_size, max_size, min_odds, max_odds, min_proba_sum,
                max_results=MAX_DFS_RESULTS, deadline=None):
    """
    DFS avec triple élagage + budget temps.
    Le pool DOIT être trié par cote ASC.
    """
    results = []
    n = len(pool)

    odds_list = [float(p.event.odds_value) for p in pool]
    proba_list = [float(p.probability) for p in pool]

    # Suffixe des probas (pour l'élagage 2)
    suffix_proba = [0.0] * (n + 1)
    for i in range(n - 1, -1, -1):
        suffix_proba[i] = suffix_proba[i + 1] + proba_list[i]

    def dfs(start, current_indices, current_odds, proba_sum, real_proba):
        # ⏱️ Budget temps écoulé → stop immédiat
        if deadline and time.time() > deadline:
            return
        if len(results) >= max_results:
            return

        # Critère validé
        if len(current_indices) >= min_size:
            if min_odds <= current_odds <= max_odds and proba_sum >= min_proba_sum:
                results.append((
                    current_indices.copy(),
                    current_odds,
                    proba_sum,
                    real_proba,
                ))

        # Taille max atteinte
        if len(current_indices) >= max_size:
            return

        for i in range(start, n):
            new_odds = current_odds * odds_list[i]

            # 🛑 Élagage 1 : cote max dépassée (tri ASC → stop définitif)
            if new_odds > max_odds:
                break

            # 🛑 Élagage 2 : impossible d'atteindre la proba sum
            if proba_sum + suffix_proba[i] < min_proba_sum:
                break

            current_indices.append(i)
            dfs(i + 1, current_indices, new_odds,
                proba_sum + proba_list[i],
                real_proba * (proba_list[i] / 100.0))
            current_indices.pop()

            if len(results) >= max_results:
                return

    dfs(0, [], 1.0, 0.0, 1.0)
    return results


def generate_ticket_combos(db: Session) -> list[dict]:
    t0 = time.time()
    deadline = t0 + TIME_BUDGET_SECONDS  # ⏱️ Hard deadline

    predictions = _eligible_predictions(db)
    by_date = _group_by_date(predictions)

    # ⚡ On garde les TOP N par jour (proba DESC)
    for d in by_date:
        by_date[d].sort(key=lambda p: float(p.probability), reverse=True)
        by_date[d] = by_date[d][:MAX_POOL_PER_DAY]

    dates_sorted = sorted(by_date.keys())
    candidates = []
    seen_keys = set()

    for window_size in range(MIN_DAYS_WINDOW, MAX_DAYS_WINDOW + 1):
        # ⏱️ Vérif budget temps à chaque fenêtre
        if time.time() > deadline:
            print(f"⏱️ Budget temps atteint ({TIME_BUDGET_SECONDS}s) — arrêt anticipé")
            break

        for i in range(len(dates_sorted) - window_size + 1):
            if time.time() > deadline:
                break

            window_dates = dates_sorted[i:i + window_size]

            # Vérifier la continuité
            if any((window_dates[j + 1] - window_dates[j]).days != 1
                   for j in range(len(window_dates) - 1)):
                continue

            # Construire le pool
            pool = []
            for d in window_dates:
                pool.extend(by_date[d])

            # ⚡ Cap dur sur la taille du pool
            if len(pool) > MAX_POOL_PER_WINDOW:
                pool.sort(key=lambda p: float(p.probability), reverse=True)
                pool = pool[:MAX_POOL_PER_WINDOW]

            if len(pool) < MIN_COMBO_SIZE:
                continue

            # Tri par cote ASC (crucial pour l'élagage)
            pool.sort(key=lambda p: float(p.event.odds_value) if p.event.odds_value else 999.0)

            results = _dfs_search(
                pool, MIN_COMBO_SIZE, MAX_COMBO_SIZE,
                MIN_TOTAL_ODDS, MAX_TOTAL_ODDS, MIN_PROB_SUM,
                max_results=MAX_DFS_RESULTS,
                deadline=deadline,
            )

            for indices, total_odds, proba_sum, real_proba in results:
                combo = [pool[idx] for idx in indices]
                combo_key = frozenset(p.event.id for p in combo)
                if combo_key in seen_keys:
                    continue
                seen_keys.add(combo_key)

                match_ids = {p.event.match_id for p in combo}
                if len(match_ids) != len(combo):
                    continue

                used_dates = sorted({p.event.match.kickoff_at.date() for p in combo})

                candidates.append({
                    "selections": combo,
                    "dates": [d.isoformat() for d in used_dates],
                    "total_odds": round(total_odds, 3),
                    "probability_sum": round(proba_sum, 2),
                    "real_combined_probability": round(real_proba * 100, 2),
                })

    candidates.sort(key=lambda c: c["real_combined_probability"], reverse=True)

    elapsed = time.time() - t0
    print(f"🎯 generate_ticket_combos : {len(candidates)} candidats en {elapsed:.2f}s "
          f"({len(dates_sorted)} jours, {sum(len(v) for v in by_date.values())} prédictions)")

    return candidates[:TOP_N_RESULTS]
