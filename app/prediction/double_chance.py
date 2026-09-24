"""
Calcul des cotes "Double Chance" (1X, X2, 12).

Deux modes de calcul disponibles :

1. **Normalisé (RECOMMANDÉ)** — `cote_double_chance_normalisee()` :
   Reproduit exactement ce que fait un bookmaker. Prend les 3 cotes (1, X, 2),
   retire l'overround (marge intégrée aux cotes), puis applique une marge
   commerciale.
   → Utilisé en priorité par le moteur de prédiction.

2. **Simple (fallback)** — `cote_double_chance()` :
   Formule brute O_AB = (O_A × O_B) / (O_A + O_B), utile quand on n'a
   que 2 cotes sur 3.
"""
from typing import Optional


# ---------------------------------------------------------------------------
# Mode 1 — Normalisé (le plus précis, reproduit les bookmakers)
# ---------------------------------------------------------------------------

def _pair_labels(pair: str) -> tuple[str, str]:
    """Retourne les 2 labels concernés par la paire DC."""
    p = pair.upper()
    if p == "1X":
        return ("1", "X")
    if p == "X2":
        return ("X", "2")
    if p == "12":
        return ("1", "2")
    raise ValueError(f"Paire invalide : {pair}")


def cote_double_chance_normalisee(
    cote_1: float,
    cote_x: float,
    cote_2: float,
    pair: str,
    taux_marge: float = 0.95,
) -> Optional[float]:
    """
    Cote Double Chance calculée comme un vrai bookmaker.

    Étapes :
      1. Probabilités implicites : p = 1 / cote
      2. Normalisation : p_norm = p / (p1 + pX + p2)   ← retire l'overround
      3. Somme des 2 probas de la paire visée
      4. Cote équitable = 1 / p_somme
      5. Application de la marge : cote × taux_marge

    Exemples vérifiés (cotes Paryaj Lakay) :
      Arsenal  (1.37, 4.60, 7.00) → 1X = 1.09
      Lille    (1.43, 4.30, 6.00) → 1X = 1.12
      Dortmund (1.35, 5.20, 6.40) → 1X = 1.11
    """
    # Validation des entrées
    if not (cote_1 and cote_x and cote_2):
        return None
    if cote_1 <= 1 or cote_x <= 1 or cote_2 <= 1:
        return None
    if not (0 < taux_marge <= 1):
        return None

    try:
        lbl_a, lbl_b = _pair_labels(pair)
    except ValueError:
        return None

    # Étape 1 — probabilités implicites
    p1 = 1.0 / cote_1
    pX = 1.0 / cote_x
    p2 = 1.0 / cote_2
    total = p1 + pX + p2

    if total <= 0:
        return None

    # Étape 2 — normalisation
    p1_n = p1 / total
    pX_n = pX / total
    p2_n = p2 / total

    # Étape 3 — somme pour la paire visée
    mapping = {"1": p1_n, "X": pX_n, "2": p2_n}
    p_pair = mapping[lbl_a] + mapping[lbl_b]

    if p_pair <= 0:
        return None

    # Étape 4 — cote équitable
    cote_equitable = 1.0 / p_pair

    # Étape 5 — marge
    return round(cote_equitable * taux_marge, 2)


# ---------------------------------------------------------------------------
# Mode 2 — Simple (fallback quand on n'a que 2 cotes sur 3)
# ---------------------------------------------------------------------------

def _cote_brute(cote_a: float, cote_b: float) -> float:
    """Cote équitable brute pour l'union de 2 issues (a OU b)."""
    if cote_a <= 0 or cote_b <= 0:
        raise ValueError("Les cotes doivent être strictement supérieures à 0.")
    return (cote_a * cote_b) / (cote_a + cote_b)


def calculer_double_chance(cote_1: float, cote_x: float, cote_2: float) -> dict:
    """
    Cotes théoriques brutes (formule du PDF) pour les 3 DC.
    Retourne {'1X': …, 'X2': …, '12': …}
    """
    if cote_1 <= 0 or cote_x <= 0 or cote_2 <= 0:
        raise ValueError("Les cotes doivent être strictement supérieures à 0.")
    return {
        "1X": round(_cote_brute(cote_1, cote_x), 2),
        "X2": round(_cote_brute(cote_x, cote_2), 2),
        "12": round(_cote_brute(cote_1, cote_2), 2),
    }


def calculer_avec_marge(
    cote_1: float,
    cote_x: float,
    cote_2: float,
    taux_marge: float = 0.95,
) -> dict:
    """Cotes brutes × marge (marge simple, sans normalisation)."""
    if taux_marge <= 0 or taux_marge > 1:
        raise ValueError("taux_marge doit être dans (0, 1].")
    brutes = calculer_double_chance(cote_1, cote_x, cote_2)
    return {k: round(v * taux_marge, 2) for k, v in brutes.items()}


def cote_double_chance(
    cote_a: float,
    cote_b: float,
    taux_marge: float = 0.95,
) -> Optional[float]:
    """
    Fallback quand on n'a que 2 cotes sur 3.
    Retourne None si les cotes sont invalides.
    """
    try:
        brute = _cote_brute(cote_a, cote_b)
        return round(brute * taux_marge, 2)
    except ValueError:
        return None


if __name__ == "__main__":
    # Test rapide sur des cotes réelles Paryaj Lakay
    print("=" * 60)
    print("TESTS DE VALIDATION — Cotes Paryaj Lakay")
    print("=" * 60)
    tests = [
        ("Arsenal",  1.37, 4.60, 7.00, "1X", 1.09),
        ("Lille",    1.43, 4.30, 6.00, "1X", 1.12),
        ("Dortmund", 1.35, 5.20, 6.40, "1X", 1.11),
    ]
    for name, c1, cx, c2, pair, attendu in tests:
        calc = cote_double_chance_normalisee(c1, cx, c2, pair, 0.95)
        ecart = abs(calc - attendu) if calc else None
        status = "✅" if ecart is not None and ecart < 0.02 else "❌"
        print(f"{status} {name:10s} {pair} | calc={calc} | book={attendu}")
