#!/usr/bin/env python3
"""Quatre indicateurs corrélés ne valent pas quatre votes.

⚠️ LA CRITIQUE, ET CE QU'ELLE A DE JUSTE
────────────────────────────────────────
D'une lecture extérieure du terminal, le 24/09/2026 :

    « MACD à -3,12 (baissier), RSI à 29, stochastique neutre, ADX à 19. Quatre
      indicateurs qui disent tous "baissier et survendu" ne valent pas quatre
      votes indépendants, ils valent un seul vote répété quatre fois. La
      technique pèse donc en réalité bien plus que les 25 % annoncés, parce que
      sa variance interne est quasi nulle. »

Le raisonnement est exact **en général** : agréger des mesures corrélées
surestime la confiance qu'on peut leur accorder. C'est le défaut classique d'un
score composite.

⚠️ MAIS IL FAUT LE MESURER, PAS LE SUPPOSER
« Corrélés à 0,9 » est une hypothèse, pas un relevé. Et tous ne le sont pas de
la même façon :

  · RSI et stochastique mesurent tous deux la position dans une plage récente —
    ils devraient être très liés ;
  · le MACD mesure l'écart entre deux moyennes — proche, mais pas identique ;
  · **l'ADX ne mesure pas la direction, il mesure la FORCE d'une tendance.**
    Un ADX élevé accompagne aussi bien une hausse franche qu'une baisse
    franche. Le compter comme redondant avec les trois autres serait une faute
    symétrique de celle qu'on corrige.

Ce module calcule donc les corrélations réelles sur nos propres séries, et
publie le nombre d'indicateurs **effectivement indépendants**.

⚠️ CE QU'IL NE FAIT PAS — R8
Il ne change aucun score. Corriger la redondance dans le calcul déplacerait la
note de tous les titres, ce qui exige un backtesting et un accord explicite.
Ce module mesure et publie ; la décision reste à prendre, avec le chiffre sous
les yeux plutôt qu'une intuition.
"""

from __future__ import annotations

import json
from pathlib import Path
from statistics import mean, pstdev

RACINE = Path(__file__).resolve().parent.parent

# Les quatre indicateurs mis en cause, plus les dérivés du MACD qui en sont
# des transformations directes — les inclure montre à quoi ressemble une
# redondance quasi parfaite, et donne l'échelle de lecture.
INDICATEURS = ("rsi", "stoch_k", "stoch_d", "macd", "macd_hist", "adx")

# Au-delà, deux séries disent la même chose. Le seuil est haut À DESSEIN :
# 0,8 laisse de la place à des mesures parentes sans les confondre, là où 0,5
# déclarerait redondants des indicateurs qui se complètent.
SEUIL_REDONDANCE = 0.8

# En dessous, une corrélation n'est pas établie — elle est tirée d'un
# échantillon trop mince pour distinguer un lien du hasard.
MIN_TITRES = 20


def correlation(xs: list[float], ys: list[float]) -> float | None:
    """Coefficient de Pearson, ou None si l'une des séries est constante.

    ⚠️ Une série constante n'a pas de corrélation « nulle » : elle n'en a
    aucune, la division serait par zéro. Rendre 0.0 ferait passer une absence
    de mesure pour une indépendance mesurée.
    """
    n = len(xs)
    if n < 3 or len(ys) != n:
        return None
    sx, sy = pstdev(xs), pstdev(ys)
    if sx == 0 or sy == 0:
        return None
    mx, my = mean(xs), mean(ys)
    cov = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / n
    return round(cov / (sx * sy), 3)


def _colonnes(tickers: list[dict]) -> dict[str, list[float]]:
    """Les séries alignées : un titre n'entre que s'il porte TOUS les champs.

    L'alignement est la condition d'une corrélation lisible — comparer des
    échantillons différents pour chaque paire rendrait les coefficients
    incomparables entre eux.
    """
    lignes = []
    for t in tickers or []:
        if not isinstance(t, dict):
            continue
        vals = {}
        for k in INDICATEURS:
            v = t.get(k)
            if isinstance(v, bool) or v is None:
                break
            try:
                vals[k] = float(v)
            except (TypeError, ValueError):
                break
        else:
            lignes.append(vals)
    return {k: [l[k] for l in lignes] for k in INDICATEURS} if lignes else {}


def mesurer(tickers: list[dict]) -> dict:
    """Les corrélations observées, et ce qu'elles impliquent.

    ⚠️ C'est une corrélation EN COUPE — entre titres à un instant donné — et
    non dans le temps. Elle répond à « ces indicateurs classent-ils les titres
    dans le même ordre », qui est précisément la question posée quand on les
    agrège en une note. Une corrélation temporelle répondrait à autre chose.
    """
    cols = _colonnes(tickers)
    n = len(next(iter(cols.values()), []))
    if n < MIN_TITRES:
        return {"mesurable": False, "titres_complets": n,
                "min_titres": MIN_TITRES,
                "_lecture": (f"{n} titres portent les six indicateurs — il en "
                             f"faut {MIN_TITRES} pour qu'une corrélation "
                             f"distingue un lien du hasard.")}

    paires, redondantes = {}, []
    noms = list(INDICATEURS)
    for i, a in enumerate(noms):
        for b in noms[i + 1:]:
            c = correlation(cols[a], cols[b])
            if c is None:
                continue
            paires[f"{a}~{b}"] = c
            if abs(c) >= SEUIL_REDONDANCE:
                redondantes.append({"paire": f"{a}~{b}", "r": c})

    # Le nombre d'indicateurs effectivement distincts : on regroupe ceux qui se
    # répètent, et chaque groupe ne compte que pour un.
    groupes: list[set] = []
    for x in redondantes:
        a, b = x["paire"].split("~")
        cible = next((g for g in groupes if a in g or b in g), None)
        if cible is None:
            groupes.append({a, b})
        else:
            cible |= {a, b}
    groupés = set().union(*groupes) if groupes else set()
    distincts = len(groupes) + len([k for k in noms if k not in groupés])

    return {
        "mesurable": True,
        "titres_complets": n,
        "seuil": SEUIL_REDONDANCE,
        "correlations": dict(sorted(paires.items(), key=lambda kv: -abs(kv[1]))),
        "paires_redondantes": sorted(redondantes, key=lambda x: -abs(x["r"])),
        "groupes_redondants": [sorted(g) for g in groupes],
        "indicateurs_declares": len(noms),
        "indicateurs_distincts": distincts,
        "_lecture": (
            f"{len(noms)} indicateurs publiés, {distincts} réellement distincts "
            f"au seuil de {SEUIL_REDONDANCE}. Le pilier technique porte donc "
            f"moins d'information qu'il n'affiche de lignes — sans que cela "
            f"dise lesquelles retirer : c'est une mesure, pas une décision."),
    }


def main() -> int:
    import sys
    chemin = Path(sys.argv[1] if len(sys.argv) > 1 else RACINE / "data.json")
    flux = json.loads(chemin.read_text(encoding="utf-8"))
    print(json.dumps(mesurer(flux.get("tickers") or []),
                     ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
