"""
Génère des explications en langage naturel pour "Pourquoi ce pronostic ?",
à partir des données techniques déjà calculées par le moteur de prédiction.
"""
import re


def build_human_summary(event, prediction, match) -> str:
    explanation = prediction.explanation or {}
    pct = round(float(prediction.probability))

    if event.type == "resultat":
        if event.label.startswith("1"):
            favori = match.home_team.name
        elif event.label.startswith("2"):
            favori = match.away_team.name
        else:
            favori = None

        if explanation.get("rating_disponible"):
            th = explanation.get("team_rating_domicile")
            ta = explanation.get("team_rating_exterieur")
            if th is not None and ta is not None:
                if th > ta:
                    plus_fort = match.home_team.name
                elif ta > th:
                    plus_fort = match.away_team.name
                else:
                    plus_fort = None

                if favori and plus_fort == favori:
                    return (
                        f"{favori} se présente en position de force : nos statistiques "
                        f"d'équipe et les cotes des bookmakers pointent dans la même direction. "
                        f"On estime {pct}% de chances que ce scénario se réalise."
                    )
                elif favori:
                    return (
                        f"Le marché des paris favorise nettement {favori} ({pct}% de chances "
                        f"estimées), même si l'écart de niveau entre les deux équipes reste modéré "
                        f"sur le papier."
                    )
                else:
                    return (
                        f"Un match plutôt équilibré entre les deux équipes, où le match nul "
                        f"ressort comme l'issue la plus probable ({pct}%)."
                    )
        if favori:
            return (
                f"Les bookmakers placent {favori} largement favori pour ce match, "
                f"avec une probabilité implicite de {pct}%. Les statistiques d'équipe "
                f"détaillées ne sont pas encore disponibles pour ce championnat."
            )
        return (
            f"Le marché des paris considère le match nul comme l'issue la plus probable "
            f"({pct}% de chances estimées)."
        )

    if event.type == "buts":
        going_over = event.label.startswith("+")
        line_match = re.search(r"([\d.]+)", event.label)
        line = line_match.group(1) if line_match else "?"
        if going_over:
            return (
                f"Les bookmakers anticipent un match plutôt ouvert, avec de nombreuses occasions "
                f"de but. Il y a {pct}% de chances que les deux équipes marquent plus de {line} "
                f"buts au total."
            )
        return (
            f"Les bookmakers anticipent un match plutôt fermé, avec peu d'occasions franches. "
            f"Il y a {pct}% de chances que le total de buts reste sous la barre des {line}."
        )

    if event.type == "double_chance":
        return (
            f"Ce match ne se dégage pas assez nettement pour miser sur une victoire sèche, "
            f"mais en couvrant deux issues sur trois (victoire ou match nul), la probabilité "
            f"de réussite grimpe à {pct}% — un pari plus sûr, pour une cote plus modeste."
        )

    return f"Probabilité estimée : {pct}%."


def get_expected_goals_line(match) -> float | None:
    for e in match.events:
        if e.type == "buts":
            m = re.search(r"([\d.]+)", e.label)
            if m:
                return float(m.group(1))
    return None
