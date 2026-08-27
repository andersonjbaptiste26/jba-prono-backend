import re

def build_human_summary(event, prediction, match, buts_probables: float = None) -> str:
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
                    text = (
                        f"{favori} se présente en position de force selon notre modèle statistique "
                        f"et l'évaluation des performances d'équipe. "
                        f"Notre système estime à {pct}% la probabilité de réalisation de ce scénario."
                    )
                elif favori:
                    text = (
                        f"Notre moteur de prédiction favorise {favori} ({pct}% de probabilité calculée), "
                        f"malgré un écart de niveau modéré entre les deux formations."
                    )
                else:
                    text = (
                        f"Rencontre très équilibrée selon nos analyses internes, où le match nul "
                        f"ressort comme l'issue la plus probable ({pct}%)."
                    )
            else:
                text = f"Probabilité calculée par notre système pour ce résultat : {pct}%."
        elif favori:
            text = (
                f"Notre modèle statistique place {favori} en tête pour cette rencontre, "
                f"avec une probabilité interne de {pct}%."
            )
        else:
            text = f"Notre modèle statistique considère le match nul comme l'issue la plus probable ({pct}%)."

    elif event.type == "buts":
        going_over = event.label.startswith("+")
        line_match = re.search(r"([\d.]+)", event.label)
        line = line_match.group(1) if line_match else "?"
        if going_over:
            text = (
                f"Notre modèle anticipe une rencontre ouverte d'après l'historique des équipes. "
                f"Il y a {pct}% de probabilité que le total dépasse {line} buts."
            )
        else:
            text = (
                f"Notre modèle anticipe une rencontre fermée d'après l'historique des équipes. "
                f"Il y a {pct}% de probabilité que le total reste sous la barre des {line} buts."
            )

    elif event.type == "double_chance":
        text = (
            f"L'analyse de notre système ne dégage pas un vainqueur net pour une victoire sèche, "
            f"mais en combinant deux issues (victoire ou match nul), la probabilité calculée "
            f"par notre algorithme atteint {pct}% — offrant une option plus sécurisée."
        )
    else:
        text = f"Probabilité estimée par le système : {pct}%."

    if buts_probables is not None:
        text += f" Nombre de buts probable estimé : {buts_probables}."

    return text


def get_expected_goals_line(match) -> float | None:
    for e in match.events:
        if e.type == "buts":
            m = re.search(r"([\d.]+)", e.label)
            if m:
                return float(m.group(1))
    return None
