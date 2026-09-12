#!/usr/bin/env python3
"""Un remplacement documenté : l'ancien état conservé, le nouvel état proposé,
et le journal CHAMP PAR CHAMP de ce qui change.

⚠️ POURQUOI CHAMP PAR CHAMP
───────────────────────────
Annoncer « 22 séances remplacées » ne dit pas ce qui bouge. Une clôture peut
changer sans que le volume bouge ; une ouverture peut passer d'une valeur à une
absence. Un remplacement qui ne se relit pas ligne par ligne, champ par champ,
n'est pas vérifiable — et ce projet a déjà réécrit un historique en croyant
l'améliorer.

⚠️ TROIS SÉRIES, NOMMÉES SÉPARÉMENT
───────────────────────────────────
Quand une opération sur titres coupe l'historique, trois séries coexistent et
les confondre produit des conclusions fausses :

    cours_brut_operateur   ce que l'opérateur publie, non ajusté
    cours_sur_base_retenue le même, ramené à la base de comparaison
    notre_cours            ce que nos chandelles portent

Le RAPPORT entre séries est affiché sur les deux bases. Un facteur observé
n'est pas une cause : il n'autorise aucun coefficient appliqué en bloc.

⚠️ CE PROGRAMME N'ÉCRIT JAMAIS DANS `pipeline/candles/`.

    python pipeline/journal_remplacement.py MSA --du 2026-05-13 --au 2026-06-16
    python pipeline/journal_remplacement.py SOT --du 2024-05-14 --au 2026-05-04
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
if str(RACINE) not in sys.path:
    sys.path.insert(0, str(RACINE))
SORTIE = RACINE / "datasets" / "historiques_candidats"

CHAMPS = [("o", "ouverture"), ("h", "plus_haut"), ("l", "plus_bas"),
          ("c", "cloture"), ("v", "titres_echanges")]


def _nos(t, ref="origin/main"):
    s = subprocess.check_output(["git", "show", f"{ref}:pipeline/candles/{t}.json"],
                                text=True, cwd=RACINE)
    return {b["d"]: b for b in json.loads(s)}


def journal(ticker: str, du: str, au: str, ref: str = "origin/main") -> dict:
    from confronter_historique import lire_export, ajuster_splits
    from identite_source import identite_de_l_export
    from identites import autoriser_ecriture

    chemin = sorted((RACINE / "sources" / ticker).glob("*.csv"))[-1]
    lu = identite_de_l_export(chemin)
    aut = autoriser_ecriture(ticker, lu.get("instrument") or "")
    if not (lu["identite_portee"] and aut["autorise"]):
        return {"ticker": ticker, "_arret": "identité non établie — aucun journal"}

    brut = lire_export(chemin)["seances"]
    aju = ajuster_splits(ticker, brut)
    retenu, splits = aju["seances"], aju["splits_appliques"]
    nous = _nos(ticker, ref)

    lignes, change = [], {k: 0 for k, _ in CHAMPS}
    absences = {k: 0 for k, _ in CHAMPS}
    for d in sorted(retenu):
        if not (du <= d <= au):
            continue
        anc, br, re_ = nous.get(d), brut.get(d, {}), retenu.get(d, {})
        l = {"seance": d,
             "cours_brut_operateur": br.get("cloture"),
             "cours_sur_base_retenue": re_.get("cloture"),
             "notre_cours": (anc or {}).get("c"),
             "champs": {}}
        for k, col in CHAMPS:
            a = (anc or {}).get(k)
            n = re_.get(col) if col != "titres_echanges" else re_.get("titres_echanges")
            if n is None:
                absences[k] += 1
            etat = ("inchangé" if a == n else
                    "absent_des_deux_cotes" if a is None and n is None else
                    "devient_absent" if n is None else
                    "apparait" if a is None else "modifié")
            if etat == "modifié":
                change[k] += 1
            l["champs"][k] = {"ancien": a, "propose": n, "etat": etat}
        for base, cours in (("brut", br.get("cloture")),
                            ("retenue", re_.get("cloture"))):
            nc = (anc or {}).get("c")
            l[f"rapport_sur_base_{base}"] = round(nc / cours, 4) if (nc and cours) else None
        lignes.append(l)

    return {
        "_quoi": f"journal de remplacement {ticker} · {du} → {au}",
        "ticker": ticker, "fenetre": [du, au], "seances": len(lignes),
        "identite": {"instrument": lu["instrument"], "preuve": aut["preuve"]},
        "base_retenue": {
            "splits_appliques_a_l_export": splits,
            "_lecture": "les prix de l'export sont ramenés à la base de nos "
                        "chandelles ; les QUANTITÉS ne sont pas converties et "
                        "leur base est déclarée ligne par ligne."
                        if splits else
                        "aucune opération sur titres : brut et base retenue "
                        "sont la même série",
        },
        "champs_modifies": change,
        "champs_absents_dans_l_export": absences,
        "_ce_qui_n_est_pas_etabli":
            "⚠️ Un RAPPORT entre séries n'est pas une CAUSE. Un facteur constant "
            "montre qu'un coefficient manque ou est de trop ; il ne dit pas "
            "lequel, ni pourquoi. Aucun coefficient n'est appliqué en bloc ici.",
        "_ancien_etat_conserve":
            "chaque ligne porte `ancien` à côté de `propose`. Rien n'est écrit "
            "dans pipeline/candles/ : la restitution de l'ancien état ne dépend "
            "d'aucune sauvegarde extérieure.",
        "lignes": lignes,
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("ticker")
    ap.add_argument("--du", required=True)
    ap.add_argument("--au", required=True)
    ap.add_argument("--ref", default="origin/main")
    ap.add_argument("--ecrire", action="store_true")
    a = ap.parse_args()
    r = journal(a.ticker, a.du, a.au, a.ref)
    if a.ecrire:
        SORTIE.mkdir(parents=True, exist_ok=True)
        f = SORTIE / f"journal_{a.ticker}_{a.du}_{a.au}.json"
        f.write_text(json.dumps(r, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"→ {f.relative_to(RACINE)}")
    print(json.dumps({k: v for k, v in r.items() if k != "lignes"},
                     ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
