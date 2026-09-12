#!/usr/bin/env python3
"""Recalcule les indicateurs DÉJÀ STOCKÉS, depuis les chandelles déjà stockées.

⚠️ POURQUOI CE PROGRAMME EXISTE
───────────────────────────────
**Corriger une fonction ne met pas à jour les valeurs déjà écrites.**
`pipeline/historical_data.json` porte des indicateurs calculés autrefois, et le
moteur les sert pour 73 titres sur 74. Après le correctif du RSI, le cache
continuerait donc à diffuser les anciennes valeurs — indéfiniment, puisque rien
ne le réécrit tant qu'un import n'a pas lieu.

⚠️ ET IL NE FAUT PAS RELANCER UN IMPORT GÉNÉRAL POUR AUTANT.
Un import réinterroge les sources, réécrit les séries, et rouvre toutes les
questions d'identité et de contamination que ce lot ne traite pas. Ce programme
ne touche à AUCUNE source : il relit les chandelles du dépôt et recalcule.

CE QU'IL PRÉSERVE
─────────────────
  · les entrées des titres NON demandés, à l'octet près ;
  · dans une entrée recalculée, tout champ qui n'est pas un indicateur ;
  · les clés de tête du fichier (`_updated`, `_source`, …).

    python pipeline/recalculer_cache.py --tous --apercu
    python pipeline/recalculer_cache.py CMT --ecrire
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
CACHE = RACINE / "pipeline" / "historical_data.json"
CANDLES = RACINE / "pipeline" / "candles"

# ⚠️ TOUS LES INDICATEURS DE L'ENTRÉE, PAS UNE SÉLECTION.
# Ma première version n'en recalculait que six sur vingt. Résultat sur CMT :
# un `rsi` et des moyennes issus des 681 nouvelles bougies, à côté d'un
# `h52w`, d'un `ma200`, d'un MACD et de bandes de Bollinger encore calculés
# sur l'ancienne série de 514. Une entrée MÉLANGÉE est pire qu'une entrée
# périmée : elle a l'air à jour.
INDICATEURS = ("rsi", "ma20", "ma50", "ma200", "h52w", "l52w", "h90", "l90",
               "macd", "macd_signal", "macd_hist", "bb_upper", "bb_mid",
               "bb_lower", "stoch_k", "stoch_d", "last_close", "last_date",
               "n_candles")


def _calculateur():
    """`compute_indicators` du collecteur — la fonction qui ÉCRIT ce cache.

    ⚠️ On ne réimplémente pas les vingt indicateurs ici. Le cache doit contenir
    ce qu'un import y aurait mis ; le recalculer avec une SECONDE
    implémentation ferait diverger les deux chemins sans que rien ne le dise.
    """
    if str(RACINE) not in sys.path:
        sys.path.insert(0, str(RACINE))
    chemin = RACINE / "pipeline"
    if str(chemin) not in sys.path:
        sys.path.insert(0, str(chemin))
    sys.argv = ["collect_history_bvcscrap.py"]
    spec = importlib.util.spec_from_file_location(
        "col_cache", chemin / "collect_history_bvcscrap.py")
    m = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(m)
    except SystemExit:
        pass
    return m


def recalculer(tickers: list[str] | None = None) -> dict:
    import pandas as pd

    m = _calculateur()
    cache = json.loads(CACHE.read_text(encoding="utf-8"))
    vises = tickers or [k for k in cache if not k.startswith("_")]

    changements, intouches, sans_chandelles, refus = [], [], [], []
    nouveau = dict(cache)

    for t in vises:
        f = CANDLES / f"{t}.json"
        if not f.exists():
            sans_chandelles.append(t)
            continue
        serie = json.loads(f.read_text(encoding="utf-8"))
        if len(serie) < 14:
            refus.append({"ticker": t, "motif": f"{len(serie)} bougies — "
                                                f"profondeur insuffisante"})
            continue
        df = pd.DataFrame([{"date": b["d"], "open": b.get("o"), "high": b.get("h"),
                            "low": b.get("l"), "close": b.get("c"),
                            "volume": b.get("v", 0)} for b in serie])
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
        try:
            calcules = m.compute_indicators(df)
        except Exception as e:                      # noqa: BLE001
            refus.append({"ticker": t, "motif": f"calcul impossible : {e}"})
            continue
        if calcules.get("rsi") is None:
            # ⚠️ On n'écrit pas une absence par-dessus une valeur existante sans
            # le dire : la série ne permet plus de se prononcer, l'ancienne
            # valeur n'en devient pas juste pour autant.
            refus.append({"ticker": t,
                          "motif": "la série ne permet pas de calculer un RSI "
                                   "(profondeur, trou ou valeur non finie)"})
            continue

        entree = dict(cache.get(t) or {})
        avant = {k: entree.get(k) for k in INDICATEURS}
        # ⚠️ `candles` est réécrit aussi : le cache porte une copie tronquée de
        # la série, et la laisser en arrière ferait mentir `n_candles`.
        for k, v in calcules.items():
            entree[k] = v
        apres = {k: entree.get(k) for k in INDICATEURS}
        if avant != apres:
            changements.append({"ticker": t, "avant": avant, "apres": apres})
            nouveau[t] = entree
        else:
            intouches.append(t)

    return {
        "_quoi": "recalcul des indicateurs EN CACHE depuis les chandelles "
                 "stockées — aucune source n'est interrogée",
        "vises": len(vises),
        "modifies": len(changements),
        "inchanges": len(intouches),
        "sans_chandelles": sans_chandelles,
        "refus": refus,
        "entrees_preservees": sorted(k for k in cache
                                     if not k.startswith("_") and k not in vises),
        "changements": changements,
        "_nouveau": nouveau,
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("tickers", nargs="*")
    ap.add_argument("--tous", action="store_true")
    ap.add_argument("--ecrire", action="store_true")
    a = ap.parse_args()
    if not a.tickers and not a.tous:
        ap.error("nommer des tickers, ou --tous")

    r = recalculer(None if a.tous else a.tickers)
    nouveau = r.pop("_nouveau")

    if a.ecrire:
        avant = hashlib.sha256(CACHE.read_bytes()).hexdigest()
        nouveau["_recalcul_indicateurs"] = {
            "le": datetime.now(timezone.utc).isoformat(),
            "portee": "tous" if a.tous else a.tickers,
            "modifies": r["modifies"],
            "_lecture": "indicateurs recalculés depuis les chandelles STOCKÉES. "
                        "Aucune source n'a été interrogée, aucune série "
                        "réécrite.",
        }
        CACHE.write_text(json.dumps(nouveau, ensure_ascii=False, indent=2),
                         encoding="utf-8")
        r["empreinte_avant"] = avant
        r["empreinte_apres"] = hashlib.sha256(CACHE.read_bytes()).hexdigest()

    apercu = dict(r)
    apercu["changements"] = r["changements"][:10]
    print(json.dumps(apercu, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
