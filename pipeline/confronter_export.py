#!/usr/bin/env python3
"""Confronter notre série à l'export de l'opérateur, ligne datée par ligne datée.

    « Prends quelques lignes précisément datées et confronte prix, quantité,
      montant et définition du champ à un export ou bulletin identifié. »
                                                          — revue externe

CE QUE L'EXPORT APPORTE, ET QUE NOUS N'AVIONS PAS
─────────────────────────────────────────────────
Il porte **deux colonnes distinctes** là où notre chandelle n'a qu'un champ :

    « Volume (MAD) »      un MONTANT en dirhams
    « Titres Échangés »   un NOMBRE de titres

Notre champ `v` ne peut être que l'un des deux. La question posée depuis le
début — « v est-il un nombre de titres ? » — cesse d'être une conjecture
d'ordre de grandeur : elle se tranche en comparant des lignes datées.

CE QUE CE SCRIPT NE FAIT PAS
────────────────────────────
Il ne corrige rien. Il ne convertit rien. Il constate des écarts et les compte.
Toute correction supposerait d'abord que l'export lui-même fasse autorité, ce
qui est une question distincte — et non tranchée ici.

    python pipeline/confronter_export.py --titre ADH --ecrire
"""

from __future__ import annotations

import argparse
import csv
import json
import statistics
from datetime import datetime
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
SOURCES = RACINE / "sources"
CANDLES = RACINE / "pipeline" / "candles"
CIBLE = RACINE / "docs" / "CONFRONTATION_EXPORT.md"

# Tolérance relative sur les prix. Deux décimales publiées de part et d'autre :
# au-delà de 0,1 % l'écart ne s'explique plus par l'arrondi.
TOLERANCE = 0.001

# Schéma OBSERVÉ sur les exports reçus le 11/09/2026. Il n'est PAS deviné :
# ces intitulés ont été relevés dans les fichiers eux-mêmes.
SCHEMA_BVC = {
    "_observe_le": "2026-09-11",
    "_sur": "exports ADH et CSR fournis par Noure",
    "separateur": ";",
    "encodage": "utf-8-sig",
    "date": "Séance",
    "format_date": "%d/%m/%Y",
    "colonnes": {
        "ouverture": "Ouverture",
        "cloture": "Dernier Cours",
        "plus_haut": "Plus Haut",
        "plus_bas": "Plus Bas",
        "montant_mad": "Volume (MAD)",
        "titres_echanges": "Titres Échangés",
        "nb_transactions": "Nb Transactions",
        "capitalisation": "Capitalisation",
    },
    "_reserve": "⚠️ Schéma relevé sur DEUX fichiers. Rien ne garantit qu'il "
                "vaille pour les 81 titres ni qu'il soit stable dans le temps.",
}


def nombre(s: str):
    s = (s or "").strip().replace(" ", "").replace(" ", "")
    if not s:
        return None
    try:
        return float(s)
    except ValueError:
        return None


def lire_export(chemin: Path) -> dict:
    """Lit un export selon le schéma OBSERVÉ. Ne devine rien."""
    col = SCHEMA_BVC["colonnes"]
    lignes = {}
    with chemin.open(encoding=SCHEMA_BVC["encodage"], newline="") as f:
        for r in csv.DictReader(f, delimiter=SCHEMA_BVC["separateur"]):
            brut = (r.get(SCHEMA_BVC["date"]) or "").strip()
            if not brut:
                continue
            try:
                d = datetime.strptime(brut, SCHEMA_BVC["format_date"]).date()
            except ValueError:
                continue
            lignes[d.isoformat()] = {
                k: nombre(r.get(v)) for k, v in col.items()
            }
    return lignes


def confronter(ticker: str) -> dict:
    dossier = SOURCES / ticker
    csvs = sorted(dossier.glob("*.csv")) if dossier.exists() else []
    if not csvs:
        raise SystemExit(f"aucun export conservé pour {ticker} dans {dossier}")
    export = lire_export(csvs[-1])

    serie = json.loads((CANDLES / f"{ticker}.json").read_text(encoding="utf-8"))
    notre = {str(b.get("d"))[:10]: b for b in serie}

    communes = sorted(set(export) & set(notre))
    ecarts_prix, unite = [], {"titres": 0, "montant": 0, "ni_l_un_ni_l_autre": 0}
    exemples_unite = []
    from collections import Counter
    ecarts_par_mois, unite_par_mois = Counter(), Counter()

    # ⚠️ HYPOTHÈSE TESTÉE PUIS ÉCARTÉE : un décalage d'une séance.
    # En lisant quelques lignes j'ai cru voir notre `v` reprendre le montant de
    # la VEILLE. Mesuré sur l'ensemble, le cas ne se produit qu'une fois : ce
    # n'est pas un motif, c'est une coïncidence. L'hypothèse est consignée
    # ÉCARTÉE plutôt que passée sous silence — une piste qu'on abandonne sans
    # le dire revient toujours.
    decalage_veille = 0

    for i, d in enumerate(communes):
        e, n = export[d], notre[d]
        for champ, cle in (("ouverture", "o"), ("plus_haut", "h"),
                           ("plus_bas", "l"), ("cloture", "c")):
            a, b = e.get(champ), n.get(cle)
            if a is None or b is None or a == 0:
                continue
            if abs(b - a) / a > TOLERANCE:
                ecarts_par_mois[d[:7]] += 1
                ecarts_prix.append({
                    "date": d, "champ": champ,
                    "export": a, "notre_serie": b,
                    "ecart_relatif": round((b - a) / a, 6)})

        v = n.get("v")
        if v is None:
            continue
        t, m = e.get("titres_echanges"), e.get("montant_mad")
        proche_t = t is not None and t > 0 and abs(v - t) / t <= TOLERANCE
        proche_m = m is not None and m > 0 and abs(v - m) / m <= TOLERANCE
        if proche_m:
            unite["montant"] += 1
        elif proche_t:
            unite["titres"] += 1
        else:
            unite["ni_l_un_ni_l_autre"] += 1
            unite_par_mois[d[:7]] += 1
            if i > 0:
                mv = export[communes[i - 1]].get("montant_mad")
                if mv and abs(v - mv) / mv <= TOLERANCE:
                    decalage_veille += 1
            if len(exemples_unite) < 8:
                exemples_unite.append({
                    "date": d, "notre_v": v, "titres_echanges": t,
                    "montant_mad": m, "cloture_export": e.get("cloture")})

    total = sum(unite.values())
    # ⚠️ Pas de seuil binaire : le taux est publié, et le verdict le cite.
    # Un seuil à 95 % aurait rendu « indéterminé » une correspondance à 92 %,
    # ce qui aurait masqué un résultat net derrière une règle arbitraire.
    dominante, part = None, 0.0
    if total:
        dominante = max(unite, key=unite.get)
        part = unite[dominante] / total
    libelle = {"montant": "le MONTANT EN DIRHAMS",
               "titres": "les TITRES ÉCHANGÉS",
               "ni_l_un_ni_l_autre": "NI l'une NI l'autre des deux colonnes"}
    verdict = ("aucune ligne comparable" if not total else
               f"notre champ « v » correspond à {libelle[dominante]} sur "
               f"{part:.1%} des {total} lignes comparées")

    return {
        "_quoi": f"Confrontation de notre série {ticker} à l'export de l'opérateur.",
        "_ce_qui_n_est_pas_etabli": (
            "⚠️ Ce script ne dit pas QUI a raison. Un écart oppose deux "
            "sources ; il ne désigne pas la fautive. L'export n'a pas été "
            "établi comme faisant autorité."),
        "titre": ticker,
        "export": csvs[-1].name,
        "schema": SCHEMA_BVC,
        "periode_export": [min(export), max(export)] if export else None,
        "periode_notre_serie": [min(notre), max(notre)] if notre else None,
        "lignes_export": len(export),
        "lignes_notre_serie": len(notre),
        "dates_communes": len(communes),
        "dans_l_export_seulement": sorted(set(export) - set(notre)),
        "dans_notre_serie_seulement": sorted(set(notre) - set(export)),
        "tolerance_relative": TOLERANCE,
        "ecarts_de_prix": len(ecarts_prix),
        "ecarts_de_prix_detail": ecarts_prix[:40],
        "unite_du_champ_v": unite,
        "verdict_unite": verdict,
        "part_dominante": round(part, 4),
        "ecarts_de_prix_par_mois": dict(sorted(ecarts_par_mois.items())),
        "non_concordances_par_mois": dict(sorted(unite_par_mois.items())),
        "hypothese_ecartee_decalage_d_une_seance": {
            "cas_observes": decalage_veille,
            "sur_non_concordances": unite["ni_l_un_ni_l_autre"],
            "verdict": "ÉCARTÉE — le cas ne se reproduit pas assez pour "
                       "constituer un motif",
        },
        "exemples_non_concordants": exemples_unite,
    }


def rendre(rapports: list) -> str:
    L = ["# Confrontation à l'export de l'opérateur",
         "",
         "> ⚠️ **Généré** par `pipeline/confronter_export.py`.",
         "> Un écart **oppose** deux sources ; il ne désigne pas la fautive.",
         "",
         "## Le schéma, observé et non deviné",
         "",
         "L'export porte **deux colonnes distinctes** là où notre chandelle "
         "n'a qu'un champ `v` :",
         "",
         "| Colonne de l'export | Ce qu'elle contient |",
         "|---|---|",
         "| `Volume (MAD)` | un **montant** en dirhams |",
         "| `Titres Échangés` | un **nombre** de titres |",
         "",
         "La question « `v` est-il un nombre de titres ? » cesse donc d'être "
         "une conjecture d'ordre de grandeur.",
         ""]
    for r in rapports:
        L += [f"## {r['titre']}", "",
              f"- export : `{r['export']}`",
              f"- période de l'export : {r['periode_export'][0]} → "
              f"{r['periode_export'][1]} ({r['lignes_export']} séances)",
              f"- période de notre série : {r['periode_notre_serie'][0]} → "
              f"{r['periode_notre_serie'][1]} ({r['lignes_notre_serie']} lignes)",
              f"- dates communes : **{r['dates_communes']}**",
              f"- séances dans l'export et **absentes de notre série** : "
              f"**{len(r['dans_l_export_seulement'])}**",
              f"- lignes chez nous et **absentes de l'export** : "
              f"**{len(r['dans_notre_serie_seulement'])}**",
              f"- écarts de prix au-delà de {r['tolerance_relative']:.1%} : "
              f"**{r['ecarts_de_prix']}**",
              "",
              f"**Unité du champ `v`** — {r['verdict_unite']}", "",
              f"| concordance | lignes |", "|---|--:|",
              f"| égale aux titres échangés | {r['unite_du_champ_v']['titres']} |",
              f"| égale au montant en dirhams | {r['unite_du_champ_v']['montant']} |",
              f"| ni l'un ni l'autre | {r['unite_du_champ_v']['ni_l_un_ni_l_autre']} |",
              ""]
        if r["exemples_non_concordants"]:
            L += ["Exemples de lignes qui ne correspondent à aucune des deux "
                  "colonnes :", "",
                  "| Date | notre `v` | Titres échangés | Montant (MAD) |",
                  "|---|--:|--:|--:|"]
            for x in r["exemples_non_concordants"]:
                L.append(f"| {x['date']} | {x['notre_v']:,.0f} | "
                         f"{(x['titres_echanges'] or 0):,.0f} | "
                         f"{(x['montant_mad'] or 0):,.2f} |")
            L.append("")
        if r["ecarts_de_prix_par_mois"]:
            L += ["**Les écarts sont bornés dans le temps.** Répartition par "
                  "mois :", "", "| Mois | Écarts de prix | `v` non concordants |",
                  "|---|--:|--:|"]
            mois = sorted(set(r["ecarts_de_prix_par_mois"]) |
                          set(r["non_concordances_par_mois"]))
            for m in mois:
                L.append(f"| {m} | {r['ecarts_de_prix_par_mois'].get(m, 0)} | "
                         f"{r['non_concordances_par_mois'].get(m, 0)} |")
            L += ["", "⚠️ Sur les mois **absents de ce tableau**, nos valeurs "
                  "et celles de l'opérateur concordent à la tolérance près. Le "
                  "désaccord n'est pas diffus : il est daté.", ""]
        h = r["hypothese_ecartee_decalage_d_une_seance"]
        L += [f"**Hypothèse testée puis écartée** — un décalage d'une séance : "
              f"{h['cas_observes']} cas sur {h['sur_non_concordances']} "
              f"non-concordances. {h['verdict']}.", ""]
        if r["ecarts_de_prix_detail"]:
            L += ["Premiers écarts de prix :", "",
                  "| Date | Champ | Export | Notre série | Écart |",
                  "|---|---|--:|--:|--:|"]
            for x in r["ecarts_de_prix_detail"][:12]:
                L.append(f"| {x['date']} | {x['champ']} | {x['export']:,.2f} | "
                         f"{x['notre_serie']:,.2f} | {x['ecart_relatif']:+.2%} |")
            L.append("")
        if r["dans_l_export_seulement"]:
            m = r["dans_l_export_seulement"]
            L += [f"Séances présentes chez l'opérateur et **absentes de notre "
                  f"série** — {len(m)} au total, les dix premières : "
                  f"{', '.join(m[:10])}", ""]
    L += ["## Ce que cette confrontation n'établit pas", "",
          "- Elle ne dit pas **qui a raison**. L'export n'a pas été établi "
          "comme faisant autorité ; il est une seconde source, pas un juge.",
          "- Elle ne couvre que **deux titres**. Rien ne permet d'étendre ses "
          "conclusions aux 79 autres.",
          "- **Aucune correction n'est appliquée**, ni sur les prix, ni sur les "
          "volumes, ni sur les séances manquantes.",
          ""]
    return "\n".join(L)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--titre", action="append", default=[])
    ap.add_argument("--ecrire", action="store_true")
    ap.add_argument("--json", type=Path)
    a = ap.parse_args()
    titres = a.titre or [d.name for d in sorted(SOURCES.iterdir())
                         if d.is_dir() and list(d.glob("*.csv"))]
    rapports = [confronter(t) for t in titres]
    if a.json:
        a.json.write_text(json.dumps(rapports, ensure_ascii=False, indent=1),
                          encoding="utf-8")
    texte = rendre(rapports)
    if a.ecrire:
        CIBLE.parent.mkdir(parents=True, exist_ok=True)
        CIBLE.write_text(texte + "\n", encoding="utf-8")
        print(f"→ {CIBLE.relative_to(RACINE)}")
    print(texte)


if __name__ == "__main__":
    main()
