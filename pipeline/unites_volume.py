#!/usr/bin/env python3
"""Le champ « v » est-il un nombre de titres ? La mesure, pas la conviction.

CE QUE LE DÉPÔT DÉCLARE AUJOURD'HUI
───────────────────────────────────
`unite: "nombre de titres"`, avec `unite_etablie: False` et la mention
« présumée — convention du moteur (QteEchangee), non enregistrée dans la
donnée ». Cette réserve n'était qu'une précaution de principe. Ce script la
transforme en mesure.

CE QUE CE TEST EST — ET CE QU'IL N'EST PAS
──────────────────────────────────────────
C'est une ALERTE D'ORDRE DE GRANDEUR, pas une réfutation.

Si `v` comptait des TITRES, le montant échangé vaudrait approximativement
`v × c`. Le produit est confronté à un ordre de grandeur du marché.

⚠️ TROIS LIMITES, RELEVÉES PAR LA REVUE, QUI RESTREIGNENT LA PORTÉE :

1. `VOLUME_MARCHE_DH` et `SEUIL_INVRAISEMBLABLE` sont des **hypothèses écrites
   dans le programme**. Le contrôle ne confronte PAS les observations à des
   totaux officiels du marché aux mêmes dates. J'avais écrit qu'il « ne dépend
   d'aucune source extérieure » : c'était faux — il dépend de deux constantes
   que j'ai posées.

2. `quantité × clôture` est une **approximation** du montant échangé, pas sa
   mesure. Les transactions de la séance ne se font pas toutes à la clôture.

3. Un grand écart entre titres **ne prouve pas** des unités différentes. Des
   prix erronés, un ajustement incompatible ou un cumul produiraient le même
   effet.

VERDICT QUE CE SCRIPT PEUT RENDRE
─────────────────────────────────
« Ordre de grandeur suspect sous l'hypothèse de quantités en titres. »
Rien de plus.

CE QUI A RÉELLEMENT TRANCHÉ, ET COMMENT
───────────────────────────────────────
Pas ce script : l'export de l'opérateur. Il porte DEUX colonnes distinctes —
« Volume (MAD) » et « Titres Échangés » — et la comparaison ligne datée par
ligne datée montre que notre `v` suit le MONTANT EN DIRHAMS sur 92 % des
730 séances communes d'ADH. Voir `pipeline/confronter_export.py`.

⚠️ Cela vaut pour DEUX titres. Rien ne permet de l'étendre aux 79 autres.

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

# ⚠️ CES DEUX VALEURS SONT DES HYPOTHÈSES, PAS DES MESURES.
# Elles sont posées ici, dans le programme, et ne proviennent d'aucun relevé
# officiel daté. Un contrôle rigoureux confronterait chaque séance au total
# réellement échangé ce jour-là — nous ne disposons pas de cette série.
# Tant qu'elle manque, ce script ALERTE, il ne conclut pas.
VOLUME_MARCHE_DH = 3.0e8               # hypothèse : ordre de grandeur du marché
SEUIL_INVRAISEMBLABLE = 5.0e9          # hypothèse : ~17 fois cet ordre

# ⚠️ CE SEUIL EST ARBITRAIRE, ET ON L'A VU BOUGER.
# Un test affirmait « au moins une série le dépasse ». Trois jours de cotations
# plus tard, MNG est passé de 8,05 à 4,92 milliards et l'assertion est tombée,
# bloquant une livraison. Le nombre de séries signalées est un CONSTAT du jour,
# jamais une propriété du projet : ne jamais l'exiger dans un test.
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
            "ordre_de_grandeur_suspect":
                statistics.median(vc) > SEUIL_INVRAISEMBLABLE,
        })
    lignes.sort(key=lambda r: -r["montant_implique_median"])
    suspects = [r for r in lignes if r["ordre_de_grandeur_suspect"]]
    montants = [r["montant_implique_median"] for r in lignes]
    return {
        "_quoi": "Le champ « v » est-il un nombre de titres ? Mesure.",
        "_verdict_possible": "ordre de grandeur suspect sous l'hypothèse de "
                             "quantités en titres",
        "_ce_qui_n_est_pas_etabli": (
            "⚠️ Ce script ne RÉFUTE aucune unité. Ses deux seuils sont des "
            "hypothèses inscrites dans le programme, « quantité × clôture » "
            "n'est qu'une approximation du montant, et un grand écart entre "
            "titres ne prouve pas des unités différentes. Ce qui a tranché, "
            "pour ADH et CSR seulement, est la confrontation à l'export de "
            "l'opérateur — voir pipeline/confronter_export.py."),
        "_les_seuils_sont_des_hypotheses": {
            "volume_marche_dh": VOLUME_MARCHE_DH,
            "seuil_invraisemblable": SEUIL_INVRAISEMBLABLE,
            "origine": "posés dans le programme, sans relevé officiel daté",
            "ce_qui_manque": "le total réellement échangé sur le marché, "
                             "séance par séance",
        },
        "seances_par_titre": SEANCES,
        "seuil_invraisemblable_dh": SEUIL_INVRAISEMBLABLE,
        "volume_quotidien_du_marche_dh": VOLUME_MARCHE_DH,
        "series_mesurees": len(lignes),
        "series_a_ordre_de_grandeur_suspect": len(suspects),
        "titres_a_ordre_de_grandeur_suspect": [r["titre"] for r in suspects],
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
    L = ["# Ordre de grandeur des volumes — une alerte, pas une réfutation",
         "",
         "> ⚠️ **Généré** par `pipeline/unites_volume.py`. Ne pas modifier à la main.",
         "",
         "## Ce que ce contrôle peut dire",
         "",
         "**Verdict possible : « ordre de grandeur suspect sous l'hypothèse de "
         "quantités en titres ». Rien de plus.**",
         "",
         "Si `v` comptait des **titres**, le montant échangé vaudrait "
         "approximativement `v × c`.",
         "",
         "⚠️ **Trois limites restreignent la portée de ce contrôle.**",
         "",
         f"1. `VOLUME_MARCHE_DH` ({VOLUME_MARCHE_DH:,.0f}) et "
         f"`SEUIL_INVRAISEMBLABLE` ({SEUIL_INVRAISEMBLABLE:,.0f}) sont des "
         f"**hypothèses écrites dans le programme**. Aucune confrontation à des "
         f"totaux officiels datés n'a lieu. Une version antérieure affirmait "
         f"que le raisonnement « ne dépend d'aucune source extérieure » : "
         f"**c'était faux**.",
         "2. `quantité × clôture` **approxime** le montant échangé — les "
         "transactions ne se font pas toutes à la clôture.",
         "3. Un grand écart entre titres **ne prouve pas** des unités "
         "différentes : des prix erronés, un ajustement incompatible ou un "
         "cumul produiraient le même effet.",
         "",
         "## Ce qui a réellement tranché",
         "",
         "Pas ce contrôle — **l'export de l'opérateur**. Il porte deux colonnes "
         "distinctes, `Volume (MAD)` et `Titres Échangés`, et la comparaison "
         "ligne datée par ligne datée montre que notre `v` suit le **montant en "
         "dirhams** sur **92 %** des 730 séances communes d'ADH. Voir "
         "`docs/CONFRONTATION_EXPORT.md`.",
         "",
         "⚠️ Cela vaut pour **deux titres**. Rien ne permet de l'étendre aux "
         "79 autres.",
         "",
         "## Ce que la mesure donne",
         "",
         f"- **{m['series_mesurees']} séries** mesurées sur leurs "
         f"{m['seances_par_titre']} dernières séances",
         f"- **{m['series_a_ordre_de_grandeur_suspect']}** dépassent le seuil "
         f"posé de {SEUIL_INVRAISEMBLABLE:,.0f} DH par séance : "
         f"{', '.join(m['titres_a_ordre_de_grandeur_suspect']) or '—'}",
         f"- les montants impliqués s'étalent sur un facteur "
         f"**{a['facteur']:,.0f}** entre le plus petit et le plus grand",
         "",
         "| Titre | Volume médian | Cours médian | Montant impliqué (DH) | Ordre de grandeur |",
         "|---|--:|--:|--:|---|"]
    for r in m["series"][:12]:
        verdict = "**suspect**" if r["ordre_de_grandeur_suspect"] else "non signalé"
        L.append(f"| {r['titre']} | {r['volume_median']:,.0f} | "
                 f"{r['cours_median']:,.1f} | "
                 f"{r['montant_implique_median']:,.0f} | {verdict} |")
    L += ["| … | | | | |"]
    for r in m["series"][-4:]:
        L.append(f"| {r['titre']} | {r['volume_median']:,.0f} | "
                 f"{r['cours_median']:,.1f} | "
                 f"{r['montant_implique_median']:,.0f} | non signalé |")
    L += ["",
          "## Ce qui est établi, et ce qui ne l'est pas",
          "",
          "**Établi par ce contrôle** : rien de plus qu'une alerte d'ordre de "
          "grandeur, sous des seuils que nous avons posés nous-mêmes.",
          "",
          "**Établi par l'export, et pour deux titres seulement** : notre `v` "
          "suit le montant en dirhams.",
          "",
          "**Non établi** : la convention du champ pour les 79 autres titres.",
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
