"""
Moteur de Team Rating — JBa Prono
Calcule un score pondéré par équipe pour classer automatiquement
les 5 meilleures équipes de chaque championnat, sans rien coder en dur.

Pondération (issue du document projet) :
  forme 20% | attaque 20% | défense 20% | domicile/exterieur 10%
  performance saison 15% | H2H 5% | effectif 10%
"""

from dataclasses import dataclass

WEIGHTS = {
    "form": 0.20,
    "attack": 0.20,
    "defense": 0.20,
    "home_away": 0.10,
    "season": 0.15,
    "h2h": 0.05,
    "squad": 0.10,
}


@dataclass
class TeamStats:
    """Entrée brute — vient de la table team_statistics + players."""
    matches_played: int
    wins: int
    draws: int
    losses: int
    goals_for: int
    goals_against: int
    clean_sheets: int
    form_last5: str          # ex: "VVNVD" (V=victoire, N=nul, D=défaite)
    home_wins: int
    away_wins: int
    h2h_win_rate: float       # 0-1, calculé sur les confrontations directes
    squad_availability: float  # 0-1, part de l'effectif dispo (hors blessés/suspendus)


def _score_form(stats: TeamStats) -> float:
    """Score de forme sur les 5 derniers matchs (0-100)."""
    points = {"V": 3, "N": 1, "D": 0}
    total = sum(points.get(r, 0) for r in stats.form_last5[-5:])
    return (total / 15) * 100 if stats.form_last5 else 50.0


def _score_attack(stats: TeamStats) -> float:
    """Buts marqués par match, normalisé (référence: 2.5 buts/match = 100)."""
    if stats.matches_played == 0:
        return 50.0
    avg = stats.goals_for / stats.matches_played
    return min(100.0, (avg / 2.5) * 100)


def _score_defense(stats: TeamStats) -> float:
    """Moins on encaisse, plus le score est haut (référence: 0.8 but encaissé/match = 100)."""
    if stats.matches_played == 0:
        return 50.0
    avg_conceded = stats.goals_against / stats.matches_played
    clean_sheet_rate = stats.clean_sheets / stats.matches_played
    base = max(0.0, 100 - (avg_conceded / 2.0) * 100)
    return min(100.0, base * 0.7 + clean_sheet_rate * 100 * 0.3)


def _score_home_away(stats: TeamStats) -> float:
    if stats.matches_played == 0:
        return 50.0
    total_wins = stats.home_wins + stats.away_wins
    return min(100.0, (total_wins / stats.matches_played) * 150)


def _score_season(stats: TeamStats) -> float:
    """Performance globale saison (points par match, sur 3 max)."""
    if stats.matches_played == 0:
        return 50.0
    points = stats.wins * 3 + stats.draws
    ppm = points / stats.matches_played
    return min(100.0, (ppm / 3) * 100)


def _score_h2h(stats: TeamStats) -> float:
    return stats.h2h_win_rate * 100


def _score_squad(stats: TeamStats) -> float:
    return stats.squad_availability * 100


def compute_team_rating(stats: TeamStats) -> dict:
    """Retourne le détail des sous-scores + le rating final pondéré (0-100)."""
    sub_scores = {
        "form": _score_form(stats),
        "attack": _score_attack(stats),
        "defense": _score_defense(stats),
        "home_away": _score_home_away(stats),
        "season": _score_season(stats),
        "h2h": _score_h2h(stats),
        "squad": _score_squad(stats),
    }
    rating = sum(sub_scores[k] * WEIGHTS[k] for k in WEIGHTS)
    return {"rating": round(rating, 2), "sub_scores": {k: round(v, 2) for k, v in sub_scores.items()}}


def rank_top_teams(team_ratings: dict[str, float], top_n: int = 5) -> list[tuple[str, float]]:
    """team_ratings: {team_name: rating}. Retourne le top N trié, pour Best Picks / Top Teams."""
    return sorted(team_ratings.items(), key=lambda x: x[1], reverse=True)[:top_n]


def confidence_tier(probability: float) -> str:
    """Catégorise la confiance selon les seuils du document (section 2)."""
    if probability >= 90:
        return "tresforte"
    if probability >= 85:
        return "forte"
    if probability >= 80:
        return "elevee"
    return "faible"
