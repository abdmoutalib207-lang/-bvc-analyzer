#!/usr/bin/env python3
"""Suivi HORS ÉCHANTILLON des fréquences publiées.

Pour chaque signal publié (datasets/frequences_publiees.json), on relève les
occurrences dont le RÉSULTAT à 60 séances n'était pas connu à la fin de la
période de calibrage (2026-10-02) et l'est devenu depuis. Le % de gagnants
observé est comparé à la fréquence annoncée : tombe-t-il dans l'IC de Wilson ?

Deux dénombrements, qu'il ne faut pas confondre :
  - « signal APRÈS la fin du calibrage » (strict) : date du signal > fin ;
    avec un horizon de 60 séances, aucun n'est mûr avant ~fin décembre 2026 ;
  - « résultat tombé APRÈS la fin du calibrage » : signal antérieur à la fin
    mais dont l'issue manquait au calibrage (horizon non écoulé). Ces cas ne
    figuraient pas dans l'effectif publié ; ils sont donc réellement neufs.

⚠️ R12 : en dessous de 30 cas, AUCUNE conclusion — le fichier le dit en toutes
lettres. Observations chevauchantes : un IC qui « contient » le résultat ne
valide rien, un IC qui l'exclut n'invalide rien tant que l'effectif est faible.

Usage : python3 pipeline/suivi_frequences.py [--sortie FICHIER.json]
Sans réseau. Écrit datasets/suivi_frequences/suivi_AAAA-MM-JJ.json (date de la
dernière séance des chandelles).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))
sys.path.insert(0, str(RACINE / "pipeline"))

import frequences as fq  # noqa: E402

SEUIL_CONCLUSION = 30
DOSSIER = RACINE / "datasets" / "suivi_frequences"


def derniere_seance() -> str:
    m = json.loads((RACINE / "pipeline" / "masi_history.json").read_text(encoding="utf-8"))
    return max(m["seances"])


def jugement(n: int, k: int, ic: list[float]) -> dict:
    if n == 0:
        return {"conclusion": "aucun cas hors échantillon : rien à comparer", "dans_ic": None}
    pct = 100 * k / n
    dans = ic[0] <= pct <= ic[1]
    if n < SEUIL_CONCLUSION:
        return {"dans_ic": dans,
                "conclusion": f"{n} cas seulement (< {SEUIL_CONCLUSION}) : aucune conclusion"}
    return {"dans_ic": dans,
            "conclusion": ("compatible avec la fréquence annoncée (observations chevauchantes : "
                           "ne la valide pas pour autant)" if dans else
                           "hors de l'IC annoncé : la fréquence publiée est à réexaminer")}


def construire(publie: dict | None = None) -> dict:
    publie = publie or json.loads(fq.SORTIE.read_text(encoding="utf-8"))
    fin = publie["fin_calibrage"]
    complet = fq.collecter(None)
    connu = fq.collecter(fin)["_resolus"]
    h = f"a{fq.HORIZON}"
    suivi = {}
    for cle, (sig, etat, _l, _c) in fq.DEFS.items():
        e = complet[sig]
        e = e[e["tendance"] == etat]
        cles = list(zip(e["t"], e["date"]))
        neuf = e[[c not in connu for c in cles]]
        mur = neuf.dropna(subset=[h])
        strict = e[e["date"] > pd.Timestamp(fin)]
        r = fq.resume(mur[h], mur[f"r{fq.HORIZON}"])
        n, k = r.get("n", 0), r.get("gagnants_k", 0)
        ic = publie["frequences"][cle]["ic95_gagnants"]
        annonce = publie["frequences"][cle]
        suivi[cle] = {
            "libelle": annonce["libelle"], "condition": annonce["condition"],
            "annonce": {"n": annonce["n"], "pct_gagnants": annonce["pct_gagnants"], "ic95": ic},
            "hors_echantillon": {
                "resultats_tombes_apres_fin_calibrage": r if n else {"n": 0},
                "signaux_apres_fin_calibrage_total": int(len(strict)),
                "signaux_apres_fin_calibrage_mures": int(strict[h].notna().sum()),
                "signaux_en_attente_d_horizon": int(e[h].isna().sum()),
            },
            **jugement(n, k, ic),
        }
    return {"_quoi": "Suivi hors échantillon des fréquences publiées",
            "_avertissement": (f"Effectif hors échantillon faible ou nul : en dessous de {SEUIL_CONCLUSION} cas "
                               "le fichier ne conclut rien (R12). Observations chevauchantes."),
            "fin_calibrage": fin, "derniere_seance_donnees": derniere_seance(),
            "horizon_seances": fq.HORIZON,
            "frequences": suivi,
            "utilite_dans_l_echantillon": publie["utilite"]}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sortie", default="")
    arg = ap.parse_args()
    res = construire()
    chemin = Path(arg.sortie) if arg.sortie else DOSSIER / f"suivi_{res['derniere_seance_donnees']}.json"
    chemin.parent.mkdir(parents=True, exist_ok=True)
    chemin.write_text(json.dumps(res, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    for k, s in res["frequences"].items():
        ho = s["hors_echantillon"]
        print(k, ho["resultats_tombes_apres_fin_calibrage"].get("n", 0), "hors éch. |",
              "signaux après fin :", ho["signaux_apres_fin_calibrage_total"],
              "mûrs", ho["signaux_apres_fin_calibrage_mures"], "|", s["conclusion"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
