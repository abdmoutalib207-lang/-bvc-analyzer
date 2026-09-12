#!/usr/bin/env python3
"""Recalcule des indicateurs DÉJÀ STOCKÉS — deux opérations, jamais mêlées.

⚠️ POURQUOI CE PROGRAMME EXISTE
───────────────────────────────
**Corriger une fonction ne met pas à jour les valeurs déjà écrites.**
`pipeline/historical_data.json` porte des indicateurs calculés autrefois, et le
moteur les sert pour 73 titres sur 74. Après le correctif du RSI, le cache
continuerait à diffuser les anciennes valeurs — indéfiniment, puisque rien ne le
réécrit tant qu'un import n'a pas lieu.

⚠️ ET IL NE FAUT PAS RELANCER UN IMPORT GÉNÉRAL POUR AUTANT.
Un import réinterroge les sources, réécrit les séries, et rouvre toutes les
questions d'identité et de contamination que ce lot ne traite pas. Ce programme
ne touche à AUCUNE source : il relit les chandelles du dépôt.

DEUX OPÉRATIONS, ET LES CONFONDRE A DES CONSÉQUENCES
────────────────────────────────────────────────────
    --complet TICKER    tous les indicateurs. Réservé aux titres dont la SÉRIE
                        a été remplacée : leurs anciennes valeurs décrivent une
                        autre série, les garder serait mentir.

    --rsi-seul          le seul champ `rsi`, sur des chandelles INCHANGÉES.
                        Aucun autre champ n'est touché.

⚠️ POURQUOI CETTE SÉPARATION EXISTE — UNE ERREUR DE MA PART, ET SON PRIX.
J'ai d'abord recalculé SIX indicateurs sur vingt ; la revue a montré que
l'entrée devenait MÉLANGÉE. J'ai alors recalculé les vingt — pour TOUS les
titres. Deuxième erreur, plus grave : sur des chandelles inchangées, recalculer
un extremum ne corrige rien, il **rejoue les anomalies déjà présentes**.

    SOT, chandelle du 05/05/2026 : o = h = 1700, l = c = 369.
    Cette bougie mêle deux bases de prix — avant et après le split 1:5.
    Le cache portait `h52w = 380` ; mon recalcul complet le passait à **1700**.

Rien dans le correctif du RSI ne justifiait de toucher à `h52w`. Un recalcul
n'assainit pas une donnée : il la relit. L'assainissement de Sothema est un lot
distinct, et ce programme ne doit pas l'anticiper par accident.

    python pipeline/recalculer_cache.py --complet CMT --rsi-seul --tous
    python pipeline/recalculer_cache.py --rsi-seul --tous --apercu
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

# Recalcul COMPLET — uniquement pour un titre dont la série a été remplacée.
INDICATEURS_COMPLETS = (
    "rsi", "ma20", "ma50", "ma200", "h52w", "l52w", "h90", "l90",
    "macd", "macd_signal", "macd_hist", "bb_upper", "bb_mid", "bb_lower",
    "stoch_k", "stoch_d", "last_close", "last_date", "n_candles", "candles",
)
# Recalcul RSI SEUL — et rien d'autre, jamais.
INDICATEUR_RSI = ("rsi",)


def _collecteur():
    """Le module qui ÉCRIT ce cache — `compute_indicators` et `calc_rsi`.

    ⚠️ On ne réimplémente rien ici. Le cache doit contenir ce qu'un import y
    aurait mis ; le recalculer avec une seconde implémentation ferait diverger
    les deux chemins sans que rien ne le dise.
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


def _serie(ticker: str):
    f = CANDLES / f"{ticker}.json"
    if not f.exists():
        return None
    return json.loads(f.read_text(encoding="utf-8"))


def recalculer(complets: list[str], rsi_seul: list[str]) -> dict:
    import pandas as pd

    m = _collecteur()
    cache = json.loads(CACHE.read_text(encoding="utf-8"))
    nouveau = dict(cache)
    chg_complet, chg_rsi, intouches, refus, absents = [], [], [], [], []

    # ── 1. RECALCUL COMPLET — série remplacée ──────────────────────────────
    for t in complets:
        serie = _serie(t)
        if serie is None:
            absents.append(t)
            continue
        df = pd.DataFrame([{"date": b["d"], "open": b.get("o"), "high": b.get("h"),
                            "low": b.get("l"), "close": b.get("c"),
                            "volume": b.get("v", 0)} for b in serie])
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
        try:
            calcules = m.compute_indicators(df)
        except Exception as e:                       # noqa: BLE001
            refus.append({"ticker": t, "motif": f"calcul impossible : {e}"})
            continue
        if calcules.get("rsi") is None:
            refus.append({"ticker": t, "motif": "la série ne permet pas de "
                                                "calculer un RSI"})
            continue
        entree = dict(cache.get(t) or {})
        avant = {k: entree.get(k) for k in INDICATEURS_COMPLETS if k != "candles"}
        entree.update(calcules)
        apres = {k: entree.get(k) for k in INDICATEURS_COMPLETS if k != "candles"}
        nouveau[t] = entree
        chg_complet.append({"ticker": t, "avant": avant, "apres": apres})

    # ── 2. RECALCUL RSI SEUL — chandelles inchangées ───────────────────────
    for t in rsi_seul:
        if t in complets:
            continue                                  # déjà traité en complet
        serie = _serie(t)
        if serie is None:
            absents.append(t)
            continue
        cl = pd.Series([b.get("c") for b in serie], dtype=object)
        rsi = m.calc_rsi(cl)
        if rsi is None:
            # ⚠️ On n'écrit pas une absence par-dessus une valeur existante :
            # la série ne permet plus de se prononcer, l'ancienne valeur n'en
            # devient pas juste pour autant. On le dit, on ne l'efface pas.
            refus.append({"ticker": t, "motif": "la série ne permet pas de "
                                                "calculer un RSI"})
            continue
        entree = dict(cache.get(t) or {})
        ancien = entree.get("rsi")
        if ancien == rsi:
            intouches.append(t)
            continue
        # ⚠️ UN SEUL CHAMP EST ÉCRIT. Tout le reste de l'entrée — extrema,
        # moyennes longues, MACD, bandes, ET la copie de chandelles — est
        # conservé tel quel. Un recalcul n'assainit pas : il relit.
        entree["rsi"] = rsi
        nouveau[t] = entree
        chg_rsi.append({"ticker": t, "rsi_avant": ancien, "rsi_apres": rsi})

    vises = set(complets) | set(rsi_seul)
    return {
        "_quoi": "recalcul d'indicateurs EN CACHE depuis les chandelles "
                 "stockées — aucune source n'est interrogée",
        "recalcul_complet": {
            "tickers": complets, "modifies": len(chg_complet),
            "_motif": "série remplacée : les anciennes valeurs décrivaient une "
                      "autre série",
        },
        "recalcul_rsi_seul": {
            "vises": len([t for t in rsi_seul if t not in complets]),
            "modifies": len(chg_rsi), "inchanges": len(intouches),
            "_garantie": "le champ `rsi` et lui seul. Les extrema, les moyennes "
                         "longues, le MACD, les bandes et la copie de "
                         "chandelles sont conservés — recalculer un extremum "
                         "sur des bougies inchangées ne corrigerait rien et "
                         "rejouerait les anomalies déjà présentes.",
        },
        "refus": refus,
        "sans_chandelles": absents,
        "entrees_preservees": sorted(k for k in cache
                                     if not k.startswith("_") and k not in vises),
        "changements_complets": chg_complet,
        "changements_rsi": chg_rsi,
        "_nouveau": nouveau,
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--complet", nargs="*", default=[],
                    help="titres dont la SÉRIE a été remplacée")
    ap.add_argument("--rsi-seul", nargs="*", default=None,
                    help="titres dont seul le RSI est recalculé")
    ap.add_argument("--tous", action="store_true",
                    help="applique --rsi-seul à toutes les entrées du cache")
    ap.add_argument("--ecrire", action="store_true")
    a = ap.parse_args()

    cache = json.loads(CACHE.read_text(encoding="utf-8"))
    tous = [k for k in cache if not k.startswith("_")]
    rsi_seul = tous if a.tous else (a.rsi_seul or [])
    if not a.complet and not rsi_seul:
        ap.error("nommer --complet et/ou --rsi-seul (ou --tous)")

    r = recalculer(a.complet, rsi_seul)
    nouveau = r.pop("_nouveau")

    if a.ecrire:
        avant = hashlib.sha256(CACHE.read_bytes()).hexdigest()
        nouveau["_recalcul_indicateurs"] = {
            "le": datetime.now(timezone.utc).isoformat(),
            "recalcul_complet": a.complet,
            "recalcul_rsi_seul": "tous" if a.tous else rsi_seul,
            "_lecture": "recalculé depuis les chandelles STOCKÉES. Aucune "
                        "source interrogée, aucune série réécrite. Hors des "
                        "titres en recalcul complet, SEUL le champ `rsi` a "
                        "été écrit.",
        }
        CACHE.write_text(json.dumps(nouveau, ensure_ascii=False, indent=2),
                         encoding="utf-8")
        r["empreinte_avant"] = avant
        r["empreinte_apres"] = hashlib.sha256(CACHE.read_bytes()).hexdigest()

    apercu = dict(r)
    apercu["changements_rsi"] = r["changements_rsi"][:8]
    print(json.dumps(apercu, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
