"""
Calcul des cotes "Double Chance" (1X, X2, 12) à partir des cotes
bookmaker du marché 1N2 (Victoire équipe 1 / Nul / Victoire équipe 2).

Formules officielles :
    O_1X = (O_1 × O_X) / (O_1 + O_X)
    O_X2 = (O_X × O_2) / (O_X + O_2)
    O_12 = (O_1 × O_2) / (O_1 + O_2)

Ces formules correspondent à la cote équitable de l'union de deux
événements mutuellement exclusifs. Elles sont équivalentes à :
    cote = 1 / (1/O_a + 1/O_b)

La marge bookmaker (overround) peut être appliquée en multipliant la
cote équitable par un taux < 1 (ex. 0.95 pour une marge de 5 %).
"""
from typing import Optional


def _cote_brute(cote_a: float, cote_b: float) -> float:
    """Cote équitable combinée pour l'union de 2 issues (a OU b)."""
    if cote_a <= 0 or cote_b <= 0:
        raise ValueError("Les cotes doivent être strictement supérieures à 0.")
    return (cote_a * cote_b) / (cote_a + cote_b)


def calculer_double_chance(cote_1: float, cote_x: float, cote_2: float) -> dict:
    """
    Calcule les cotes théoriques brutes des trois doubles chances.

    Retourne un dict :
        { "1X": float, "X2": float, "12": float }

    Exemple (PDF) : c_1, c_x, c_2 = 1.77, 3.85, 3.65
        → {'1X': 1.21, 'X2': 1.87, '12': 1.20}
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
    """
    Applique une marge bookmaker (overround) aux cotes de double chance.

    Le taux est appliqué en MULTIPLIANT la cote équitable, ce qui RÉDUIT
    la cote perçue par le parieur — c'est exactement la marge du bookmaker.

    taux_marge : coefficient dans (0, 1]. Ex. 0.95 = marge de 5 %.
    """
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
    Cote Double Chance pour une paire d'issues quelconques, avec marge.

    Retourne None si les cotes sont invalides.
    Utilisé par le moteur de prédiction pour 1X ou X2.
    """
    try:
        brute = _cote_brute(cote_a, cote_b)
        return round(brute * taux_marge, 2)
    except ValueError:
        return None


if __name__ == "__main__":
    # Test rapide (aligné sur l'exemple du PDF)
    c_1, c_x, c_2 = 1.77, 3.85, 3.65
    print("Cotes brutes       :", calculer_double_chance(c_1, c_x, c_2))
    print("Avec marge 5 %     :", calculer_avec_marge(c_1, c_x, c_2, 0.95))
