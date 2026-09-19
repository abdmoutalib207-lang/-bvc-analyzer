#!/usr/bin/env python3
"""Recalcule/synchronise des indicateurs DÉJÀ STOCKÉS, sans collecte réseau.

Trois opérations volontairement séparées :

    --complet TICKER
        Tous les indicateurs. Réservé aux titres dont la SÉRIE a été remplacée
        et réceptionnée : les anciennes valeurs décrivent alors une autre série.

    --rsi-seul TICKER / --rsi-seul --tous
        Le seul champ ``rsi`` sur des chandelles inchangées.

    --sync-ajouts TICKER...
        Synchronisation quotidienne après ajout/remplacement de la dernière
        bougie. Ce mode fait avancer les champs dont l'ancien cache est
        reproductible, mais PRÉSERVE tout champ déjà corrigé/divergent.

Pourquoi ``--sync-ajouts`` n'est PAS un alias de ``--complet`` : une série brute
peut encore porter une anomalie historique qu'une correction réceptionnée a
déjà neutralisée dans le cache. Exemple documenté : SOT avait une bougie mêlant
deux bases de prix (haut 1700, clôture 369) ; rejouer toute la série remontait
``h52w`` de 380 à 1700. Une mise à jour quotidienne ne doit jamais annuler une
correction historique par effet de bord.
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
INDICATEUR_RSI = ("rsi",)
_CHAMPS_STRUCTURE = {"last_close", "last_date", "n_candles"}


def _collecteur():
    """Charge uniquement le calculateur qui écrit ce cache, sans lancer run()."""
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


def _df(serie):
    import pandas as pd

    df = pd.DataFrame([
        {"date": b["d"], "open": b.get("o"), "high": b.get("h"),
         "low": b.get("l"), "close": b.get("c"), "volume": b.get("v", 0)}
        for b in serie
    ])
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    return df


def _bougie_cache(entree: dict, date: str):
    for b in reversed(entree.get("candles") or []):
        if str(b.get("d") or "")[:10] == date:
            return dict(b)
    return None


def _fusion_candles_cache(candles_cache: list, candles_calculees: list,
                           pivot: str, remplacer_pivot: bool) -> list:
    """Préserve le passé corrigé du cache et ne fusionne que la queue utile.

    Pour un APPEND (nouvelle séance > pivot), la dernière bougie déjà livrée
    fait partie du passé réceptionné et doit être conservée telle quelle : le
    brut peut encore contenir une anomalie que le cache avait corrigée.

    Pour un REMPLACEMENT de la dernière séance (intraday), le pivot lui-même
    est au contraire remplacé par le nouveau calcul.
    """
    if remplacer_pivot:
        base = [dict(b) for b in (candles_cache or [])
                if str(b.get("d") or "")[:10] < pivot]
        queue = [dict(b) for b in (candles_calculees or [])
                 if str(b.get("d") or "")[:10] >= pivot]
    else:
        base = [dict(b) for b in (candles_cache or [])
                if str(b.get("d") or "")[:10] <= pivot]
        queue = [dict(b) for b in (candles_calculees or [])
                 if str(b.get("d") or "")[:10] > pivot]
    par_date = {str(b.get("d") or "")[:10]: b for b in base + queue
                if b.get("d")}
    return [par_date[d] for d in sorted(par_date)][-250:]


def _synchroniser_un_ajout(t: str, entree: dict, serie: list, m):
    """Synchronise un append ou le remplacement de la dernière bougie.

    On reconstruit l'état PRÉCÉDENT à partir des chandelles brutes antérieures
    et de la dernière bougie déjà mémorisée dans le cache. Chaque indicateur est
    alors classé :
      * ancien cache == ancien calcul -> reproductible -> peut avancer ;
      * ancien cache != ancien calcul -> correction/divergence historique ->
        reste strictement inchangé.

    Les champs structurels avancent seulement si la série garde exactement le
    même préfixe en nombre de séances jusqu'à l'ancienne date.
    """
    if not entree:
        return None, {"ticker": t, "motif": "aucune entrée de cache existante"}
    ancienne_date = str(entree.get("last_date") or "")[:10]
    if not ancienne_date:
        return None, {"ticker": t, "motif": "cache sans last_date"}

    dates = [str(b.get("d") or "")[:10] for b in serie]
    if not dates or dates != sorted(dates) or len(dates) != len(set(dates)):
        return None, {"ticker": t, "motif": "série non triée ou dates dupliquées"}
    if ancienne_date not in dates:
        return None, {"ticker": t, "motif": f"ancienne date {ancienne_date} absente"}

    avant = [b for b in serie if str(b.get("d") or "")[:10] < ancienne_date]
    anciens_n = entree.get("n_candles")
    if not isinstance(anciens_n, int) or len(avant) != anciens_n - 1:
        return None, {
            "ticker": t,
            "motif": (f"préfixe modifié avant {ancienne_date}: "
                      f"{len(avant)} séances au lieu de {anciens_n - 1}"),
        }

    bougie_precedente = _bougie_cache(entree, ancienne_date)
    if bougie_precedente is None:
        return None, {"ticker": t,
                      "motif": f"bougie {ancienne_date} absente de la copie cache"}

    serie_precedente = avant + [bougie_precedente]
    try:
        calc_avant = m.compute_indicators(_df(serie_precedente))
        calc_apres = m.compute_indicators(_df(serie))
    except Exception as e:  # noqa: BLE001
        return None, {"ticker": t, "motif": f"calcul impossible : {e}"}

    derniere_date = str(calc_apres.get("last_date") or "")[:10]
    if derniere_date < ancienne_date:
        return None, {"ticker": t, "motif": "la série recule dans le temps"}

    entree_nouvelle = dict(entree)
    reproductibles, preserves = [], []
    for champ in INDICATEURS_COMPLETS:
        if champ in _CHAMPS_STRUCTURE or champ == "candles":
            continue
        if entree.get(champ) == calc_avant.get(champ):
            entree_nouvelle[champ] = calc_apres.get(champ)
            reproductibles.append(champ)
        else:
            preserves.append(champ)

    # La structure décrit toujours la série complète effectivement stockée.
    entree_nouvelle["last_close"] = calc_apres.get("last_close")
    entree_nouvelle["last_date"] = calc_apres.get("last_date")
    entree_nouvelle["n_candles"] = calc_apres.get("n_candles")

    # La copie de 250 bougies est mise à jour par la queue seulement. Ainsi une
    # correction historique déjà présente dans le cache ne peut pas être
    # écrasée par une anomalie plus ancienne encore présente dans le brut.
    entree_nouvelle["candles"] = _fusion_candles_cache(
        entree.get("candles") or [], calc_apres.get("candles") or [], ancienne_date,
        remplacer_pivot=(derniere_date == ancienne_date))

    change = entree_nouvelle != entree
    return entree_nouvelle, {
        "ticker": t,
        "date_avant": ancienne_date,
        "date_apres": entree_nouvelle.get("last_date"),
        "modifie": change,
        "champs_recalcules": reproductibles,
        "champs_preserves": preserves,
    }


def recalculer(complets: list[str], rsi_seul: list[str],
               sync_ajouts: list[str] | None = None) -> dict:
    import pandas as pd

    sync_ajouts = sync_ajouts or []
    m = _collecteur()
    cache = json.loads(CACHE.read_text(encoding="utf-8"))
    nouveau = dict(cache)
    chg_complet, chg_rsi, intouches, refus, absents, chg_sync = [], [], [], [], [], []

    # ── 1. RECALCUL COMPLET — série explicitement remplacée ────────────────
    for t in complets:
        serie = _serie(t)
        if serie is None:
            absents.append(t)
            continue
        try:
            calcules = m.compute_indicators(_df(serie))
        except Exception as e:  # noqa: BLE001
            refus.append({"ticker": t, "motif": f"calcul impossible : {e}"})
            continue
        if calcules.get("rsi") is None:
            refus.append({"ticker": t,
                          "motif": "la série ne permet pas de calculer un RSI"})
            continue
        entree = dict(cache.get(t) or {})
        avant = {k: entree.get(k) for k in INDICATEURS_COMPLETS if k != "candles"}
        entree.update(calcules)
        apres = {k: entree.get(k) for k in INDICATEURS_COMPLETS if k != "candles"}
        nouveau[t] = entree
        chg_complet.append({"ticker": t, "avant": avant, "apres": apres})

    # ── 2. SYNCHRONISATION QUOTIDIENNE — append / dernière bougie ──────────
    for t in sync_ajouts:
        if t in complets:
            continue
        serie = _serie(t)
        if serie is None:
            absents.append(t)
            continue
        entree, rapport = _synchroniser_un_ajout(t, dict(cache.get(t) or {}), serie, m)
        if entree is None:
            refus.append(rapport)
            continue
        nouveau[t] = entree
        chg_sync.append(rapport)

    # ── 3. RECALCUL RSI SEUL — chandelles inchangées ───────────────────────
    for t in rsi_seul:
        if t in complets or t in sync_ajouts:
            continue
        serie = _serie(t)
        if serie is None:
            absents.append(t)
            continue
        cl = pd.Series([b.get("c") for b in serie], dtype=object)
        rsi = m.calc_rsi(cl)
        if rsi is None:
            refus.append({"ticker": t,
                          "motif": "la série ne permet pas de calculer un RSI"})
            continue
        entree = dict(cache.get(t) or {})
        ancien = entree.get("rsi")
        if ancien == rsi:
            intouches.append(t)
            continue
        entree["rsi"] = rsi
        nouveau[t] = entree
        chg_rsi.append({"ticker": t, "rsi_avant": ancien, "rsi_apres": rsi})

    vises = set(complets) | set(rsi_seul) | set(sync_ajouts)
    return {
        "_quoi": "mise à jour du cache depuis les chandelles stockées — aucune source interrogée",
        "recalcul_complet": {
            "tickers": complets, "modifies": len(chg_complet),
            "_motif": "série remplacée : les anciennes valeurs décrivaient une autre série",
        },
        "synchronisation_ajouts": {
            "tickers": sync_ajouts,
            "traites": len(chg_sync),
            "modifies": sum(1 for x in chg_sync if x.get("modifie")),
            "_garantie": ("seuls les champs reproductibles avancent ; les divergences "
                          "historiques et les anciennes bougies corrigées sont préservées"),
        },
        "recalcul_rsi_seul": {
            "vises": len([t for t in rsi_seul if t not in complets and t not in sync_ajouts]),
            "modifies": len(chg_rsi), "inchanges": len(intouches),
        },
        "refus": refus,
        "sans_chandelles": absents,
        "entrees_preservees": sorted(k for k in cache
                                     if not k.startswith("_") and k not in vises),
        "changements_complets": chg_complet,
        "changements_sync": chg_sync,
        "changements_rsi": chg_rsi,
        "_nouveau": nouveau,
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--complet", nargs="*", default=[],
                    help="titres dont la SÉRIE a été remplacée")
    ap.add_argument("--sync-ajouts", nargs="*", default=[],
                    help="titres avec ajout/remplacement de la dernière bougie")
    ap.add_argument("--rsi-seul", nargs="*", default=None,
                    help="titres dont seul le RSI est recalculé")
    ap.add_argument("--tous", action="store_true",
                    help="applique --rsi-seul à toutes les entrées du cache")
    ap.add_argument("--ecrire", action="store_true")
    a = ap.parse_args()

    cache = json.loads(CACHE.read_text(encoding="utf-8"))
    tous = [k for k in cache if not k.startswith("_")]
    rsi_seul = tous if a.tous else (a.rsi_seul or [])
    if not a.complet and not a.sync_ajouts and not rsi_seul:
        ap.error("nommer --complet, --sync-ajouts et/ou --rsi-seul (ou --tous)")

    chevauchements = ((set(a.complet) & set(a.sync_ajouts)) |
                      (set(a.complet) & set(rsi_seul)) |
                      (set(a.sync_ajouts) & set(rsi_seul)))
    if chevauchements:
        ap.error("un ticker ne peut viser plusieurs modes : " + ", ".join(sorted(chevauchements)))

    r = recalculer(a.complet, rsi_seul, a.sync_ajouts)
    nouveau = r.pop("_nouveau")
    if r["refus"] or r["sans_chandelles"]:
        print(json.dumps(r, ensure_ascii=False, indent=2))
        raise SystemExit(2)

    if a.ecrire:
        avant = hashlib.sha256(CACHE.read_bytes()).hexdigest()
        nouveau["_recalcul_indicateurs"] = {
            "le": datetime.now(timezone.utc).isoformat(),
            "recalcul_complet": a.complet,
            "synchronisation_ajouts": a.sync_ajouts,
            "recalcul_rsi_seul": "tous" if a.tous else rsi_seul,
            "_lecture": ("recalculé depuis les chandelles STOCKÉES. Aucune source "
                         "interrogée, aucune série réécrite. En mode sync-ajouts, "
                         "les divergences historiques sont préservées."),
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
