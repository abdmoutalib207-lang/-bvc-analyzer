#!/usr/bin/env python3
"""Le bilan du lot, LU dans les artefacts — jamais recopié à la main.

POURQUOI CE SCRIPT EXISTE
─────────────────────────
J'ai écrit « cinq titres sur sept n'autorisent aucun indicateur » alors que les
fichiers livrés en montraient SIX. J'ai aussi écrit que SOT était écarté « sur
l'historique antérieur à l'opération » alors que le contrat l'écartait de
l'analyse des prix sur TOUTE sa série.

Ces deux erreurs ont la même cause : un chiffre énoncé de mémoire à côté d'un
fichier qui dit autre chose. La revue externe a demandé que le bilan soit
généré depuis les artefacts. Il l'est.

    python pipeline/bilan_lot.py            affiche
    python pipeline/bilan_lot.py --ecrire   met à jour docs/BILAN_LOT1B.md
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
LOT1B = RACINE / "datasets" / "lot1b"
CIBLE = RACINE / "docs" / "BILAN_LOT1B.md"

USAGES = ["prix_analyse", "volume", "indicateur", "indicateur_exploratoire",
          "execution_simulee"]


def mesurer() -> dict:
    series = {}
    for f in sorted(LOT1B.glob("*.json")):
        if f.stem == "MANIFESTE":
            continue
        d = json.loads(f.read_text(encoding="utf-8"))
        obs = d["observations"]
        compte = Counter(u for o in obs for u in o["admissible_pour"])
        combinaisons = Counter(
            " + ".join(o["admissible_pour"]) or "aucun" for o in obs)
        series[f.stem] = {
            "lignes": len(obs),
            "base_prix": d["diagnostic_base_prix"]["niveau"],
            "base_quantites": d["diagnostic_quantites"]["niveau"],
            "usages": {u: compte.get(u, 0) for u in USAGES},
            "sans_aucun_usage": sum(1 for o in obs if not o["admissible_pour"]),
            "combinaisons": dict(combinaisons.most_common()),
            "alertes_amplitude": sum(
                1 for o in obs
                if o.get("amplitude", {}).get("statut", "").startswith("hors enveloppe")),
        }

    total = sum(s["lignes"] for s in series.values())
    return {
        "series": series,
        "titres": len(series),
        "observations": total,
        "titres_sans_indicateur_publiable":
            sum(1 for s in series.values() if s["usages"]["indicateur"] == 0),
        "titres_avec_exploratoire":
            sum(1 for s in series.values()
                if s["usages"]["indicateur_exploratoire"] > 0),
        "titres_sans_execution":
            sum(1 for s in series.values() if s["usages"]["execution_simulee"] == 0),
        "observations_sans_aucun_usage":
            sum(s["sans_aucun_usage"] for s in series.values()),
        "observations_prix_analyse":
            sum(s["usages"]["prix_analyse"] for s in series.values()),
    }


def rendre(m: dict) -> str:
    L = ["# Bilan du lot — mesuré dans les artefacts",
         "",
         "> ⚠️ Ce fichier est **généré** par `pipeline/bilan_lot.py`, qui LIT "
         "`datasets/lot1b/`.",
         "> Ne pas le modifier à la main : un chiffre recopié finit par "
         "contredire le fichier qu'il décrit.",
         "",
         f"**{m['titres']} titres · {m['observations']} observations**",
         "",
         "| Titre | Lignes | Base prix | Base quantités | prix | volume | indic. | explor. | exéc. | sans usage |",
         "|---|--:|---|---|--:|--:|--:|--:|--:|--:|"]
    for t, s in m["series"].items():
        u = s["usages"]
        L.append(f"| {t} | {s['lignes']} | {s['base_prix']} | "
                 f"{s['base_quantites']} | {u['prix_analyse']} | {u['volume']} | "
                 f"{u['indicateur']} | {u['indicateur_exploratoire']} | "
                 f"{u['execution_simulee']} | {s['sans_aucun_usage']} |")

    L += ["",
          "## Ce que ces chiffres disent",
          "",
          f"- **{m['titres_sans_indicateur_publiable']} titres sur "
          f"{m['titres']}** n'autorisent aucun indicateur **publiable**.",
          f"- **{m['titres_avec_exploratoire']} titres sur {m['titres']}** "
          f"autorisent un calcul **exploratoire**, qui n'alimente ni le signal "
          f"officiel, ni une probabilité, ni une performance validée.",
          f"- **{m['titres_sans_execution']} titres sur {m['titres']}** "
          f"n'autorisent aucune exécution simulée.",
          f"- **{m['observations_sans_aucun_usage']} observations** sur "
          f"{m['observations']} n'autorisent **aucun** usage.",
          ""]

    sot = m["series"].get("SOT")
    if sot:
        L += ["## SOT — portée exacte de la mise à l'écart",
              "",
              "⚠️ La mise à l'écart porte sur **toute la série**, pas seulement "
              "sur l'historique antérieur à l'opération. Une formulation "
              "antérieure disait le contraire.",
              "",
              f"- `prix_analyse` accordé sur **{sot['usages']['prix_analyse']}** "
              f"observation(s) sur {sot['lignes']}",
              f"- `indicateur` et `indicateur_exploratoire` : "
              f"**{sot['usages']['indicateur']}** et "
              f"**{sot['usages']['indicateur_exploratoire']}**",
              "", "Répartition des combinaisons d'usages :", ""]
        for combi, n in sot["combinaisons"].items():
            L.append(f"- `{combi}` — {n} observation(s)")
        L.append("")
        L.append("⚠️ Ce constat ne justifie **aucune correction automatique** "
                 "des prix de SOT.")
        L.append("")
    return "\n".join(L)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--ecrire", action="store_true")
    a = ap.parse_args()
    m = mesurer()
    texte = rendre(m)
    if a.ecrire:
        CIBLE.parent.mkdir(parents=True, exist_ok=True)
        CIBLE.write_text(texte + "\n", encoding="utf-8")
        print(f"→ {CIBLE.relative_to(RACINE)}")
    print(texte)


if __name__ == "__main__":
    main()
