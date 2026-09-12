#!/usr/bin/env python3
"""Applique une série ACCEPTÉE aux chandelles publiées — un titre à la fois.

⚠️ CE PROGRAMME ÉCRIT DANS `pipeline/candles/`. C'est le seul de la chaîne à le
faire sur instruction, et il ne le fait que pour les titres nommés en argument,
depuis un fichier de `datasets/series_acceptees/`.

POURQUOI UN FICHIER SÉPARÉ DES PROPOSITIONS
───────────────────────────────────────────
`datasets/historiques_candidats/corrections_*.json` PROPOSE : il signale des
écarts et fournit des valeurs de référence. Ce n'est pas une instruction.
`datasets/series_acceptees/*.json` est l'INSTRUCTION : la série y est celle
qui doit remplacer les chandelles, et elle a été réceptionnée comme telle.

La revue a demandé que la différence soit explicite. Elle l'est par le dossier.

TROIS CONTRÔLES AVANT ÉCRITURE, ET LE REFUS EST LA RÈGLE
────────────────────────────────────────────────────────
  1. la série porte le ticker demandé et son instrument ;
  2. aucune bougie négociée n'est postérieure à une suspension déclarée ;
  3. l'ancien fichier est conservé à côté, horodaté — le retour arrière ne
     dépend d'aucune sauvegarde extérieure.

    python pipeline/appliquer_serie.py CMT
    python pipeline/appliquer_serie.py CMT --verifier-seulement
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
ACCEPTEES = RACINE / "datasets" / "series_acceptees"
CANDLES = RACINE / "pipeline" / "candles"


def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def verifier(ticker: str) -> dict:
    src = ACCEPTEES / f"{ticker}.json"
    if not src.exists():
        return {"ticker": ticker, "refus": f"aucune série acceptée dans {src}"}
    d = json.loads(src.read_text(encoding="utf-8"))

    if d.get("ticker") != ticker:
        return {"ticker": ticker,
                "refus": f"la série porte le ticker « {d.get('ticker')} »"}

    serie = d.get("serie") or []
    if not serie:
        return {"ticker": ticker, "refus": "série vide"}

    # ⚠️ Aucune bougie NÉGOCIÉE après une suspension déclarée. Une séance sans
    # échange ne doit jamais entrer comme bougie : ce serait fabriquer une
    # cotation le jour où le titre a cessé d'en avoir.
    susp = (d.get("_suspension") or {}).get("depuis")
    apres = [b["d"] for b in serie if susp and b["d"] >= susp]
    if apres:
        return {"ticker": ticker,
                "refus": f"{len(apres)} bougie(s) négociée(s) au-delà de la "
                         f"suspension du {susp} : {apres[:5]}"}

    sans_quantite = [b["d"] for b in serie if not b.get("v")]
    dates = [b["d"] for b in serie]
    if dates != sorted(dates):
        return {"ticker": ticker, "refus": "série non triée chronologiquement"}
    if len(set(dates)) != len(dates):
        return {"ticker": ticker, "refus": "séances en double"}

    ancien = CANDLES / f"{ticker}.json"
    return {
        "ticker": ticker,
        "instrument": d.get("instrument"),
        "seances": len(serie),
        "periode": [dates[0], dates[-1]],
        "suspension_depuis": susp,
        "bougies_apres_suspension": 0,
        "bougies_sans_quantite": len(sans_quantite),
        "empreinte_serie_acceptee": _sha(src),
        "ancien_fichier": {
            "existe": ancien.exists(),
            "seances": len(json.loads(ancien.read_text(encoding="utf-8")))
                       if ancien.exists() else 0,
            "empreinte": _sha(ancien) if ancien.exists() else None,
        },
        "_lecture": "aucune écriture n'a eu lieu — ceci est une vérification",
    }


def appliquer(ticker: str) -> dict:
    v = verifier(ticker)
    if "refus" in v:
        return v
    src = ACCEPTEES / f"{ticker}.json"
    d = json.loads(src.read_text(encoding="utf-8"))
    cible = CANDLES / f"{ticker}.json"

    # ⚠️ L'ANCIEN ÉTAT EST CONSERVÉ À CÔTÉ, HORODATÉ.
    horodatage = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    sauvegarde = None
    if cible.exists():
        sauvegarde = CANDLES / f"{ticker}.avant_{horodatage}.json"
        shutil.copy(cible, sauvegarde)

    bougies = [{k: b[k] for k in ("d", "o", "h", "l", "c", "v")} for b in d["serie"]]
    cible.write_text(json.dumps(bougies, ensure_ascii=False), encoding="utf-8")

    v.update({
        "applique": True,
        "seances_ecrites": len(bougies),
        "sauvegarde": str(sauvegarde.relative_to(RACINE)) if sauvegarde else None,
        "empreinte_apres": _sha(cible),
        "_lecture": "les chandelles publiées de ce titre sont remplacées par la "
                    "série acceptée. L'ancien fichier est à côté, horodaté.",
    })
    return v


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("tickers", nargs="+")
    ap.add_argument("--verifier-seulement", action="store_true")
    a = ap.parse_args()
    for t in a.tickers:
        r = verifier(t) if a.verifier_seulement else appliquer(t)
        print(json.dumps(r, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
