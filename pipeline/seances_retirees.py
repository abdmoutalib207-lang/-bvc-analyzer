#!/usr/bin/env python3
"""Retirer des séances qu'aucune source ne peut corriger — sur instruction.

⚠️ POURQUOI RETIRER PLUTÔT QUE CORRIGER
───────────────────────────────────────
`corrections_acceptees/` RÉÉCRIT des séances nommées : il faut donc connaître la
bonne valeur. Ici on ne la connaît pas, et personne ne peut la fournir.

Le 16/09/2026, deux titres portaient les cours d'un autre émetteur :

    ATL (AtlantaSanad, ≈130 DH)   7 séances aux cours d'Auto Hall  (66–69 DH)
    MRL (Maroc Leasing, ≈367 DH)  22 séances aux cours de Marsa Maroc (800–869)

L'export de l'opérateur pour ATL s'arrête au 05/06 et la contamination commence
au 08/06 — la séance suivante. Maroc Leasing n'a aucun export du tout. Aucun
bulletin archivé ne remonte avant septembre.

**Un trou se voit ; une valeur inventée ne se voit pas.** Le graphique montrera
une interruption, les indicateurs compteront une séance de moins, et personne ne
lira un cours faux.

⚠️ CE QUE CE PROGRAMME NE FAIT PAS
──────────────────────────────────
Il ne cherche pas les séances à retirer : il applique une liste écrite à la
main, séance par séance, chacune avec la bougie exacte qu'elle prétend retirer.

TROIS REFUS, ET LE REFUS EST LA RÈGLE
─────────────────────────────────────
  1. une instruction qui ne porte pas le ticker du fichier est refusée ;
  2. une séance dont la bougie sur disque DIFFÈRE de celle qui est inscrite est
     refusée — la série a changé depuis la rédaction, et retirer à l'aveugle
     effacerait un travail inconnu ;
  3. une séance absente de la série est SIGNALÉE, pas comptée comme retirée.

⚠️ LE CONTRÔLE N°2 EST TOUT L'INTÉRÊT DU FICHIER. Sans lui, ce programme serait
une liste de dates à supprimer — c'est-à-dire une arme. Avec lui, il ne peut
retirer que ce qui a été constaté, et il s'arrête dès que le terrain a bougé.

    python pipeline/seances_retirees.py --verifier-seulement
    python pipeline/seances_retirees.py ATL MRL --ecrire
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
RETIREES = RACINE / "datasets" / "seances_retirees"
CANDLES = RACINE / "pipeline" / "candles"
CHAMPS = ("o", "h", "l", "c", "v")


def charger(ticker: str, dossier: Path | None = None) -> dict | None:
    """L'instruction écrite pour ce titre, ou None."""
    f = (dossier or RETIREES) / f"{ticker}.json"
    if not f.exists():
        return None
    d = json.loads(f.read_text(encoding="utf-8"))
    if d.get("ticker") != ticker:
        raise ValueError(
            f"{f.name} porte le ticker « {d.get('ticker')} » : instruction refusée")
    return d


def appliquer(ticker: str, bougies: list[dict],
              dossier: Path | None = None) -> tuple[list[dict], dict]:
    """Retire les séances nommées. Renvoie (bougies, compte rendu).

    `bougies` n'est pas muté : une nouvelle liste est renvoyée.
    """
    doc = charger(ticker, dossier)
    if doc is None:
        return bougies, {"ticker": ticker, "retirees": 0,
                         "_lecture": "aucun retrait réceptionné"}

    par_date = {b.get("d"): b for b in bougies}
    retirees, absentes, refus = [], [], []

    for ligne in doc.get("lignes", []):
        d = ligne["d"]
        courante = par_date.get(d)
        if courante is None:
            # Déjà retirée, ou jamais entrée. On ne compte pas un retrait qui
            # n'a pas eu lieu.
            absentes.append(d)
            continue
        attendue = ligne["retiree"]
        etat = {k: courante.get(k) for k in CHAMPS}
        if etat != {k: attendue.get(k) for k in CHAMPS}:
            refus.append({"seance": d,
                          "motif": "la bougie sur disque n'est pas celle que "
                                   "l'instruction prétend retirer — la série a "
                                   "changé depuis la réception",
                          "actuel": etat, "attendu": attendue})
            continue
        del par_date[d]
        retirees.append(d)

    out = [b for b in bougies if b.get("d") in par_date]
    return out, {
        "ticker": ticker,
        "instrument": doc.get("instrument"),
        "retirees": len(retirees),
        "seances_retirees": retirees,
        "deja_absentes": absentes,
        "refus": refus,
        "_lecture": "seules les séances nommées sont retirées ; tout le reste de "
                    "la série, séance du jour comprise, passe intact",
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("tickers", nargs="*")
    ap.add_argument("--ecrire", action="store_true")
    ap.add_argument("--verifier-seulement", action="store_true")
    a = ap.parse_args()

    tickers = a.tickers or sorted(f.stem for f in RETIREES.glob("*.json"))
    for t in tickers:
        cible = CANDLES / f"{t}.json"
        if not cible.exists():
            print(json.dumps({"ticker": t, "refus": "aucune série publiée"},
                             ensure_ascii=False))
            continue
        avant = json.loads(cible.read_text(encoding="utf-8"))
        apres, rapport = appliquer(t, avant)
        rapport["seances_avant"] = len(avant)
        rapport["seances_apres"] = len(apres)
        if a.ecrire and not a.verifier_seulement and not rapport.get("refus"):
            cible.write_text(json.dumps(apres, separators=(",", ":")),
                             encoding="utf-8")
            rapport["_ecrit"] = True
        print(json.dumps(rapport, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
