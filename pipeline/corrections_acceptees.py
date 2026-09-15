#!/usr/bin/env python3
"""Des séances corrigées, réimposées après chaque import.

⚠️ POURQUOI CETTE COUCHE EXISTE — MESURÉ, PAS SUPPOSÉ
─────────────────────────────────────────────────────
Corriger `pipeline/candles/MSA.json` ne suffit pas : l'import quotidien le
réécrit. Le 15/09/2026, la mesure a été faite avant d'appliquer quoi que ce
soit :

    data/historique/MSA.xlsx  s'arrête au 12/05/2026
    première séance contaminée   13/05/2026

Les 22 séances en cause ne viennent donc PAS du fichier figé : elles viennent
de l'extension BVCscrap, qui identifie les sociétés par NOM — la voie même par
laquelle les cours de Mutandis sont entrés. Et dans `_run()`, les chandelles
stockées ne sont reprises que pour les dates POSTÉRIEURES à ce qui vient d'être
téléchargé. Une correction posée à la main aurait donc vécu moins d'une
journée, et personne ne s'en serait aperçu — la valeur fausse serait revenue
silencieusement.

⚠️ CE QUE CETTE COUCHE N'EST PAS
────────────────────────────────
Ce n'est pas `datasets/series_acceptees/`, qui REMPLACE une série entière et
FIGE le titre. Cela convient à CMT, suspendu depuis le 17/07. MSA cote tous les
jours : le figer lui interdirait toute séance nouvelle.

Ici, seules les séances NOMMÉES sont réécrites. Tout le reste de l'import
passe intact, y compris la séance du jour.

⚠️ ET CE N'EST PAS UN CONTRÔLE D'IDENTITÉ.
Elle ne vérifie rien sur les 73 autres titres, ni sur les autres séances de
celui-ci. Elle impose ce qui a été réceptionné, et rien d'autre.

TROIS REFUS
───────────
  1. une correction dont la séance est absente de la série est SIGNALÉE, pas
     ajoutée — fabriquer une cotation serait pire que le défaut corrigé ;
  2. une correction qui n'a pas le ticker du fichier est refusée ;
  3. une correction dont l'état actuel ne correspond ni à `remplace` ni à
     `corrige` est refusée : la série a changé depuis la réception, et
     l'appliquer à l'aveugle écraserait un travail inconnu.
"""

from __future__ import annotations

import json
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
CORRECTIONS = RACINE / "datasets" / "corrections_acceptees"
CHAMPS = ("o", "h", "l", "c", "v")


def charger(ticker: str, dossier: Path | None = None) -> dict | None:
    """Le document réceptionné pour ce titre, ou None."""
    f = (dossier or CORRECTIONS) / f"{ticker}.json"
    if not f.exists():
        return None
    d = json.loads(f.read_text(encoding="utf-8"))
    if d.get("ticker") != ticker:
        raise ValueError(
            f"{f.name} porte le ticker « {d.get('ticker')} » : refus")
    return d


def appliquer(ticker: str, bougies: list[dict],
              dossier: Path | None = None) -> tuple[list[dict], dict]:
    """Réimpose les séances corrigées. Renvoie (bougies, compte rendu).

    `bougies` n'est pas muté : une copie est renvoyée.
    """
    doc = charger(ticker, dossier)
    if doc is None:
        return bougies, {"ticker": ticker, "corrections": 0,
                         "_lecture": "aucune correction réceptionnée"}

    par_date = {b.get("d"): b for b in bougies}
    imposees, deja, absentes, refus = [], [], [], []

    for ligne in doc.get("lignes", []):
        d = ligne["d"]
        courante = par_date.get(d)
        if courante is None:
            # ⚠️ On n'AJOUTE pas la séance. Une correction dit « cette bougie
            # est fausse », pas « cette bougie devrait exister ».
            absentes.append(d)
            continue
        etat = {k: courante.get(k) for k in CHAMPS}
        if etat == ligne["corrige"]:
            deja.append(d)
            continue
        if etat != ligne["remplace"]:
            refus.append({"seance": d, "motif": "l'état actuel n'est ni "
                          "l'ancien ni le corrigé — la série a changé depuis "
                          "la réception", "actuel": etat})
            continue
        courante = dict(courante)
        courante.update(ligne["corrige"])
        par_date[d] = courante
        imposees.append(d)

    out = [par_date.get(b.get("d"), b) for b in bougies]
    return out, {
        "ticker": ticker,
        "instrument": doc.get("instrument"),
        "corrections": len(imposees),
        "deja_conformes": len(deja),
        "seances_absentes": absentes,
        "refus": refus,
        "_lecture": "seules les séances nommées sont réécrites ; le reste de "
                    "la série, séance du jour comprise, passe intact",
    }


def main() -> None:
    import argparse
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("tickers", nargs="+")
    ap.add_argument("--ecrire", action="store_true")
    a = ap.parse_args()
    for t in a.tickers:
        f = RACINE / "pipeline" / "candles" / f"{t}.json"
        bougies = json.loads(f.read_text(encoding="utf-8"))
        out, rapport = appliquer(t, bougies)
        if a.ecrire and rapport["corrections"]:
            f.write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")
            rapport["_ecrit"] = str(f.relative_to(RACINE))
        print(json.dumps(rapport, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
