"""
Combine des pronostics sur une fenêtre de 2 à 7 jours consécutifs
en tickets multiples, selon les critères :
- cote combinée entre 3 et 9
- somme des probabilités individuelles >= 75%
- 2 à 6 matchs par ticket
- répartis sur 2 à 7 jours consécutifs

⚡ ALGORITHME OPTIMISÉ (DFS + élagage) :
- Pool réduit : top 12 par jour
- Tri par cote ASC dans chaque fenêtre
- DFS avec double élagage :
  1) cote courante > MAX → stop de la branche (et toutes les suivantes grâce au tri)
  2) proba_sum + suffixe < 75% → stop (aucun espoir)
- Limite globale de sécurité

Résultat : ~1-3 s au lieu de plusieurs minutes.
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

# ─── Optimisations de performance ───
MAX_POOL_PER_DAY = 12          # TOP 12 par jour max
MAX_DFS_RESULTS = 2000         # limite de sécurité par fenêtre
MAX_CANDIDATES_TOTAL = 50000   # limite globale


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


def _dfs_search(pool, min_size, max_size, min_odds, max_odds, min_proba_sum,
                max_results=MAX_DFS_RESULTS):
    """
    DFS avec élagage fort. Le pool DOIT être trié par cote ASC.

    Retourne une liste de tuples :
      (indices, total_odds, proba_sum, real_proba)
    """
    results = []
    n = len(pool)

    # Précalcul des cotes et probas
    odds_list = [float(p.event.odds_value) for p in pool]
    proba_list = [float(p.probability) for p in pool]

    # Suffixe : somme des probas de i jusqu'à la fin
    # Utilisé pour élaguer si même en prenant tout le reste on n'atteint pas 75%
    suffix_proba = [0.0] * (n + 1)
    for i in range(n - 1, -1, -1):
        suffix_proba[i] = suffix_proba[i + 1] + proba_list[i]

    def dfs(start, current_indices, current_odds, proba_sum, real_proba):
        if len(results) >= max_results:
            return

        # Critère validé → ajouter aux résultats
        if len(current_indices) >= min_size:
            if min_odds <= current_odds <= max_odds and proba_sum >= min_proba_sum:
                results.append((
                    current_indices.copy(),
                    current_odds,
                    proba_sum,
                    real_proba,
                ))

        # Taille max atteinte → stop
        if len(current_indices) >= max_size:
            return

        # Explorer les éléments suivants
        for i in range(start, n):
            new_odds = current_odds * odds_list[i]

            # 🛑 Élagage 1 : cote max dépassée
            # Comme le pool est trié par cote ASC, tous les suivants
            # auront une cote >= → on peut arrêter la boucle
            if new_odds > max_odds:
                break

            # 🛑 Élagage 2 : impossible d'atteindre la proba sum minimum
            # Même en prenant TOUS les matchs restants
            if proba_sum + suffix_proba[i] < min_proba_sum:
                break

            # Récursion
            current_indices.append(i)
            dfs(
                i + 1,
                current_indices,
                new_odds,
                proba_sum + proba_list[i],
                real_proba * (proba_list[i] / 100.0),
            )
            current_indices.pop()

            if len(results) >= max_results:
                return

    dfs(0, [], 1.0, 0.0, 1.0)
    return results


def generate_ticket_combos(db: Session) -> list[dict]:
    """
    Génère jusqu'à TOP_N_RESULTS combinaisons optimales.
    """
    t0 = time.time()

    predictions = _eligible_predictions(db)
    by_date = _group_by_date(predictions)

    # ⚡ On ne garde que les TOP N par jour (tri par proba DESC)
    for d in by_date:
        by_date[d].sort(key=lambda p: float(p.probability), reverse=True)
        by_date[d] = by_date[d][:MAX_POOL_PER_DAY]

    dates_sorted = sorted(by_date.keys())

    candidates = []
    seen_keys = set()

    # ─── Boucle sur les fenêtres ───
    for window_size in range(MIN_DAYS_WINDOW, MAX_DAYS_WINDOW + 1):
        for i in range(len(dates_sorted) - window_size + 1):
            window_dates = dates_sorted[i:i + window_size]

            # Vérifier que les jours sont bien consécutifs
            if any((window_dates[j + 1] - window_dates[j]).days != 1
                   for j in range(len(window_dates) - 1)):
                continue

            # Construire le pool de la fenêtre
            pool = []
            for d in window_dates:
                pool.extend(by_date[d])

            if len(pool) < MIN_COMBO_SIZE:
                continue

            # ⚡ TRI CRUCIAL : par cote ASC (permet l'élagage 1)
            pool.sort(key=lambda p: float(p.event.odds_value) if p.event.odds_value else 999.0)

            # DFS avec élagage
            results = _dfs_search(
                pool,
                MIN_COMBO_SIZE,
                MAX_COMBO_SIZE,
                MIN_TOTAL_ODDS,
                MAX_TOTAL_ODDS,
                MIN_PROB_SUM,
                max_results=MAX_DFS_RESULTS,
            )

            # Convertir en candidats
            for indices, total_odds, proba_sum, real_proba in results:
                combo = [pool[idx] for idx in indices]

                # Déduplication globale
                combo_key = frozenset(p.event.id for p in combo)
                if combo_key in seen_keys:
                    continue
                seen_keys.add(combo_key)

                # Vérifier que tous les matchs sont distincts
                match_ids = {p.event.match_id for p in combo}
                if len(match_ids) != len(combo):
                    continue

                # Dates réellement utilisées
                used_dates = sorted({p.event.match.kickoff_at.date() for p in combo})

                candidates.append({
                    "selections": combo,
                    "dates": [d.isoformat() for d in used_dates],
                    "total_odds": round(total_odds, 3),
                    "probability_sum": round(proba_sum, 2),
                    "real_combined_probability": round(real_proba * 100, 2),
                })

            # Sécurité : arrêt global si trop de candidats
            if len(candidates) >= MAX_CANDIDATES_TOTAL:
                break
        if len(candidates) >= MAX_CANDIDATES_TOTAL:
            break

    # Tri final par probabilité réelle décroissante
    candidates.sort(key=lambda c: c["real_combined_probability"], reverse=True)

    elapsed = time.time() - t0
    print(f"🎯 generate_ticket_combos : {len(candidates)} candidats en {elapsed:.2f}s "
          f"({len(dates_sorted)} jours, {sum(len(v) for v in by_date.values())} prédictions)")

    return candidates[:TOP_N_RESULTS]
