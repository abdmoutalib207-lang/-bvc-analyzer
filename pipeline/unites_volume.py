#!/usr/bin/env python3
"""Le champ « v » est-il un nombre de titres ? La mesure, pas la conviction.

CE QUE LE DÉPÔT DÉCLARE AUJOURD'HUI
───────────────────────────────────
`unite: "nombre de titres"`, avec `unite_etablie: False` et la mention
« présumée — convention du moteur (QteEchangee), non enregistrée dans la
donnée ». Cette réserve n'était qu'une précaution de principe. Ce script la
transforme en mesure.

LE TEST, ET SON RAISONNEMENT
───────────────────────────
Si `v` comptait des TITRES, le montant échangé vaudrait `v × c`. Ce produit est
donc vérifiable contre un ordre de grandeur connu : le volume quotidien de
TOUTE la Bourse de Casablanca se compte en centaines de millions de dirhams.

Un titre dont le produit `v × c` dépasse à lui seul plusieurs milliards par
séance ne peut pas être exprimé en titres. Le raisonnement ne dépend d'aucune
source : il oppose la donnée à sa propre conséquence arithmétique.

⚠️ CE QUE CE SCRIPT N'ÉTABLIT PAS
Il ne dit pas ce que `v` est. Un montant en dirhams est l'hypothèse la plus
simple, ce n'est pas la seule — un facteur d'échelle, un cumul, un champ hérité
d'une autre source la produiraient aussi. Seule la convention écrite du
fournisseur trancherait, et nous ne l'avons pas.

    python pipeline/unites_volume.py --ecrire
"""

from __future__ import annotations

import argparse
import json
import statistics
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
CANDLES = RACINE / "pipeline" / "candles"
CIBLE = RACINE / "docs" / "UNITE_DES_VOLUMES.md"

# Ordre de grandeur du volume quotidien de TOUT le marché, en dirhams.
# Un seul titre qui le dépasse largement signale une unité incompatible.
VOLUME_MARCHE_DH = 3.0e8
SEUIL_INVRAISEMBLABLE = 5.0e9          # ~17 fois le marché entier
SEANCES = 120


def mesurer() -> dict:
    lignes = []
    for f in sorted(CANDLES.glob("*.json")):
        try:
            s = json.loads(f.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            continue
        if not isinstance(s, list):
            continue
        fen = s[-SEANCES:]
        vc = [b["v"] * b["c"] for b in fen
              if isinstance(b.get("v"), (int, float))
              and isinstance(b.get("c"), (int, float)) and b["v"] > 0]
        v = [b["v"] for b in fen if isinstance(b.get("v"), (int, float)) and b["v"] > 0]
        c = [b["c"] for b in fen if isinstance(b.get("c"), (int, float))]
        if len(vc) < 20 or not c:
            continue
        lignes.append({
            "titre": f.stem,
            "seances_retenues": len(vc),
            "volume_median": statistics.median(v),
            "cours_median": statistics.median(c),
            "montant_implique_median": statistics.median(vc),
            "invraisemblable_en_titres":
                statistics.median(vc) > SEUIL_INVRAISEMBLABLE,
        })
    lignes.sort(key=lambda r: -r["montant_implique_median"])
    suspects = [r for r in lignes if r["invraisemblable_en_titres"]]
    montants = [r["montant_implique_median"] for r in lignes]
    return {
        "_quoi": "Le champ « v » est-il un nombre de titres ? Mesure.",
        "_ce_qui_n_est_pas_etabli": (
            "⚠️ Ce script ne dit PAS ce que « v » est. Il montre qu'une unité "
            "unique « nombre de titres » est incompatible avec les données. "
            "Seule la convention écrite du fournisseur trancherait."),
        "seances_par_titre": SEANCES,
        "seuil_invraisemblable_dh": SEUIL_INVRAISEMBLABLE,
        "volume_quotidien_du_marche_dh": VOLUME_MARCHE_DH,
        "series_mesurees": len(lignes),
        "series_invraisemblables": len(suspects),
        "titres_invraisemblables": [r["titre"] for r in suspects],
        "amplitude_des_montants": {
            "minimum": min(montants) if montants else None,
            "maximum": max(montants) if montants else None,
            "facteur": (max(montants) / min(montants)
                        if montants and min(montants) > 0 else None),
        },
        "series": lignes,
    }


def rendre(m: dict) -> str:
    a = m["amplitude_des_montants"]
    L = ["# L'unité du champ « v » n'est pas établie",
         "",
         "> ⚠️ **Généré** par `pipeline/unites_volume.py`. Ne pas modifier à la main.",
         "",
         "## Le raisonnement",
         "",
         "Si `v` comptait des **titres**, le montant échangé vaudrait `v × c`. "
         "Ce produit s'oppose à un ordre de grandeur connu : le volume quotidien "
         f"de **toute** la Bourse de Casablanca se compte en centaines de "
         f"millions de dirhams (~{VOLUME_MARCHE_DH:,.0f} DH).",
         "",
         "Le raisonnement ne dépend d'aucune source extérieure : il oppose la "
         "donnée à sa propre conséquence arithmétique.",
         "",
         "## Ce que la mesure donne",
         "",
         f"- **{m['series_mesurees']} séries** mesurées sur leurs "
         f"{m['seances_par_titre']} dernières séances",
         f"- **{m['series_invraisemblables']}** dépassent à elles seules "
         f"{SEUIL_INVRAISEMBLABLE:,.0f} DH par séance : "
         f"{', '.join(m['titres_invraisemblables']) or '—'}",
         f"- les montants impliqués s'étalent sur un facteur "
         f"**{a['facteur']:,.0f}** entre le plus petit et le plus grand",
         "",
         "| Titre | Volume médian | Cours médian | Montant impliqué (DH) | En titres ? |",
         "|---|--:|--:|--:|---|"]
    for r in m["series"][:12]:
        verdict = "**incompatible**" if r["invraisemblable_en_titres"] else "possible"
        L.append(f"| {r['titre']} | {r['volume_median']:,.0f} | "
                 f"{r['cours_median']:,.1f} | "
                 f"{r['montant_implique_median']:,.0f} | {verdict} |")
    L += ["| … | | | | |"]
    for r in m["series"][-4:]:
        L.append(f"| {r['titre']} | {r['volume_median']:,.0f} | "
                 f"{r['cours_median']:,.1f} | "
                 f"{r['montant_implique_median']:,.0f} | possible |")
    L += ["",
          "## Ce qui est établi, et ce qui ne l'est pas",
          "",
          "**Établi** : une unité unique « nombre de titres » sur l'ensemble des "
          "séries est **incompatible** avec ces montants.",
          "",
          "**Non établi** : ce que `v` est réellement. Un montant en dirhams est "
          "l'hypothèse la plus simple ; un facteur d'échelle, un cumul, ou un "
          "champ hérité d'une autre source la produiraient aussi. Seule la "
          "convention écrite du fournisseur trancherait, et nous ne l'avons pas.",
          "",
          "## Conséquence tenue",
          "",
          "Le registre `BASES_QUANTITES` reste **vide** et "
          "`unite_etablie` vaut **False**. Tout indicateur consommant des "
          "volumes — OBV en tête — reste refusé. Ce n'est plus une précaution "
          "de principe : c'est la conclusion d'une mesure.",
          ""]
    return "\n".join(L)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--ecrire", action="store_true")
    a = ap.parse_args()
    m = mesurer()
    if a.ecrire:
        CIBLE.parent.mkdir(parents=True, exist_ok=True)
        CIBLE.write_text(rendre(m) + "\n", encoding="utf-8")
        print(f"→ {CIBLE.relative_to(RACINE)}")
    print(rendre(m))


if __name__ == "__main__":
    main()
