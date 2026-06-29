#!/usr/bin/env python3
"""
BVC ANALYZER DATA PIPELINE v9.0
================================
Collecte les données financières des 19 sociétés MASI 1.
Produit :
  - financial_data.json  : format v9 complet (pour analyses avancées)
  - data.json            : format legacy (pour index.html / GitHub Pages)

Usage :
  python collect_financial_data.py
  python collect_financial_data.py --dry-run
  python collect_financial_data.py --tickers MNG,SMI,ADI
"""
import argparse
import json
import logging
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

# Résolution des imports relatifs
sys.path.insert(0, str(Path(__file__).parent.parent))

from pipeline.scrapers.constants      import TICKERS, IPO_RECENT
from pipeline.scrapers.market         import fetch_market_data
from pipeline.scrapers.fundamentals   import fetch_fundamentals
from pipeline.smart_money.fond_score  import compute_fond_score, reload as fond_reload
from pipeline.technical.indicators  import compute_technical
from pipeline.smart_money.alpha     import get_smart_money
from pipeline.utils.validation      import validate_ticker_data
from pipeline.utils.logging_config  import setup_logging

ROOT       = Path(__file__).parent
FALLBACK_P = ROOT / "fallback_data.json"
OUT_V9     = ROOT.parent / "financial_data.json"
OUT_LEGACY = ROOT.parent / "data.json"


def load_fallback() -> dict:
    try:
        return json.loads(FALLBACK_P.read_text(encoding="utf-8"))
    except Exception as e:
        logging.warning(f"Fallback non chargé: {e}")
        return {}


def collect_ticker(sym: str, fallback: dict, dry_run: bool = False) -> tuple[str, dict]:
    log = logging.getLogger(sym)
    fb  = fallback.get(sym, {})

    result = {
        "market":                {},
        "technical":             {},
        "fundamentals":          {},
        "financials_performance":{},
        "smart_money":           {},
        "flags": {
            "stale":        False,
            "partial_data": sym in IPO_RECENT,
            "ipo_recent":   sym in IPO_RECENT,
        },
        "_sources": {},
    }

    if dry_run:
        log.info("DRY-RUN — utilisation fallback uniquement")
        result["market"]       = {k: fb.get(k) for k in ["price","open","high","low","volume","variation_pct"] if fb.get(k) is not None}
        result["technical"]    = {k: fb.get(k) for k in ["rsi_14","ma20","ma50","high_90d","low_90d"]          if fb.get(k) is not None}
        result["fundamentals"] = {k: fb.get(k) for k in ["pe_ratio_ttm","pe_ratio_2026e","pb_ratio","eps_ttm","dividend_per_share","dividend_yield","market_cap_mdh"] if fb.get(k) is not None}
        result["flags"]["stale"] = True
        result["_sources"] = {"all": "fallback (dry-run)"}
        result["smart_money"] = get_smart_money(sym)
        return sym, result

    # ── 1. Données de marché ─────────────────────────────────────────────────
    try:
        market = fetch_market_data(sym)
        if market and market.get("price"):
            result["_sources"]["price"] = market.pop("_source", "live")
            result["market"] = market
        else:
            raise ValueError("no price")
    except Exception as e:
        log.warning(f"market FAIL: {e} → fallback")
        result["market"] = {k: fb.get(k) for k in ["price","open","high","low","volume","variation_pct"] if fb.get(k) is not None}
        result["flags"]["stale"] = True
        result["_sources"]["price"] = "fallback"

    # ── 2. Indicateurs techniques (RSI calculé) ──────────────────────────────
    try:
        tech = compute_technical(sym)
        if tech and tech.get("rsi_14") is not None:
            result["_sources"]["technical"] = tech.pop("_source", "calculated")
            result["_sources"]["rsi"]       = "calculated_wilder_ema"
            result["technical"] = tech
        else:
            raise ValueError("RSI non calculé")
    except Exception as e:
        log.warning(f"technical FAIL: {e} → fallback")
        result["technical"] = {k: fb.get(k) for k in ["rsi_14","ma20","ma50","high_90d","low_90d"] if fb.get(k) is not None}
        result["flags"]["stale"] = True
        result["_sources"]["rsi"] = "fallback"

    # ── 3. Fondamentaux ──────────────────────────────────────────────────────
    try:
        fund = fetch_fundamentals(sym)
        if fund:
            result["_sources"]["fundamentals"] = fund.pop("_source", "scraped")
            result["fundamentals"] = fund
        else:
            raise ValueError("no fundamentals")
    except Exception as e:
        log.warning(f"fundamentals FAIL: {e} → fallback")
        fund_keys = ["pe_ratio_ttm","pe_ratio_2026e","pb_ratio","eps_ttm",
                     "dividend_per_share","dividend_yield","market_cap_mdh"]
        result["fundamentals"] = {k: fb.get(k) for k in fund_keys if fb.get(k) is not None}
        result["_sources"]["fundamentals"] = "fallback"

    # ── 4. Performance financière ── désactivé
    #    fetch_financials scrape des articles de presse Médias24 (jusqu'à 20 req/ticker)
    #    et n'a jamais retourné de données (CA={}, RN={} sur tous les tickers).
    #    Non consommé par to_legacy_format() ni par fond_score.py.
    #    Cause principale du timeout à 20 min — à réactiver avec une source API structurée.

    # ── 5. Smart Money ────────────────────────────────────────────────────────
    result["smart_money"] = get_smart_money(sym)

    # ── 6. Flags ──────────────────────────────────────────────────────────────
    has_price  = bool(result["market"].get("price"))
    has_rsi    = bool(result["technical"].get("rsi_14"))
    has_per    = bool(result["fundamentals"].get("pe_ratio_ttm"))
    if not all([has_price, has_rsi, has_per]) or sym in IPO_RECENT:
        result["flags"]["partial_data"] = True

    result = validate_ticker_data(result, sym)

    log.info(
        f"✓ price={result['market'].get('price')} "
        f"RSI={result['technical'].get('rsi_14')} "
        f"PER={result['fundamentals'].get('pe_ratio_ttm')} "
        f"stale={result['flags']['stale']} partial={result['flags']['partial_data']}"
    )
    return sym, result


# ── Conversion format legacy (data.json pour index.html) ─────────────────────

def to_legacy_format(pipeline_out: dict) -> dict:
    """Convertit le format v9 → format data.json consommé par index.html."""
    from pipeline.smart_money.alpha import SENTIMENT_CORPUS

    tickers = []
    for sym, d in pipeline_out.get("data", {}).items():
        m  = d.get("market", {})
        t  = d.get("technical", {})
        f  = d.get("fundamentals", {})
        sm = d.get("smart_money", {})
        sc = SENTIMENT_CORPUS.get(sym, {})

        # Score v5.3 simplifié (recalcul complet possible via update_data.py)
        rsi    = t.get("rsi_14") or 50
        price  = m.get("price") or 0
        ma20   = t.get("ma20") or price
        ma50   = t.get("ma50") or price

        score_tech = 5.0
        if 40 <= rsi <= 65:    score_tech += 1.0
        elif rsi > 75:         score_tech -= 1.0
        elif rsi < 30:         score_tech += 0.5
        if price > ma20 > ma50:score_tech += 1.5
        elif price > ma20:     score_tech += 0.8
        elif price < ma50:     score_tech -= 1.2
        score_tech = round(min(max(score_tech, 0), 10), 2)

        fond_score = compute_fond_score(sym)  # fondamentaux.json → 5.0 si absent
        nlp_score  = round((sc.get("smart", 0) + 1) * 5, 2)
        v53        = round(score_tech * 0.25 + fond_score * 0.47 + nlp_score * 0.28, 2)

        def sig(s):
            if s >= 7.5: return "ACHAT FORT ★★★"
            if s >= 6.5: return "ACHETER ★★"
            if s >= 5.5: return "SURVEILLER ★"
            if s >= 4.5: return "ATTENDRE"
            if s >= 3.5: return "ÉVITER"
            return "ÉVITER FORT"

        tickers.append({
            "symbol":   sym,
            "price":    m.get("price"),
            "open":     m.get("open"),
            "close":    m.get("price"),
            "chg":      m.get("variation_pct") or 0,
            "volume":   m.get("volume"),
            "pe":       f.get("pe_ratio_ttm"),
            "pb":       f.get("pb_ratio"),
            "div":      f.get("dividend_yield"),
            "cap":      f.get("market_cap_mdh"),
            "h90":      t.get("high_90d"),
            "l90":      t.get("low_90d"),
            "rsi":      rsi,
            "ma20":     t.get("ma20"),
            "ma50":     t.get("ma50"),
            "v53":      v53,
            "bvc":      round(fond_score, 2),
            "nlp":      nlp_score,
            "sig":      sig(v53),
            "alpha":    sm.get("alpha_12m"),
            "win_rate": sm.get("win_rate_6m"),
            "stale":    d["flags"]["stale"],
            "partial":  d["flags"]["partial_data"],
        })

    # Tri par score v53 décroissant
    tickers.sort(key=lambda x: x.get("v53") or 0, reverse=True)
    return {
        "updated": pipeline_out["timestamp"],
        "version": "v9.0",
        "source":  "BVC Pipeline v9.0",
        "tickers": tickers,
    }


# ── Main ──────────────────────────────────────────────────────────────────────

def run(tickers=None, dry_run=False, max_workers=3):
    setup_logging()
    log = logging.getLogger("pipeline")
    log.info("=" * 60)
    log.info(f"BVC DATA PIPELINE v9.0 — {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    log.info("=" * 60)

    fallback = load_fallback()
    selected = tickers or TICKERS

    output = {
        "timestamp":   datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "version":     "v9.0_unified",
        "sources_used": {},
        "data":        {},
    }

    t0 = time.time()
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {pool.submit(collect_ticker, sym, fallback, dry_run): sym for sym in selected}
        for fut in as_completed(futures):
            sym = futures[fut]
            try:
                s, data = fut.result(timeout=120)
                output["data"][s]          = data
                output["sources_used"][s]  = data.pop("_sources", {})
                log.info(f"[{s}] ✓")
            except Exception as e:
                log.error(f"[{sym}] FATAL: {e}")

    elapsed = round(time.time() - t0, 1)
    nb_ok   = len(output["data"])
    nb_stale= sum(1 for d in output["data"].values() if d["flags"].get("stale"))
    log.info(f"Pipeline terminé: {nb_ok}/{len(selected)} tickers, {nb_stale} stale, {elapsed}s")

    # Écriture financial_data.json (format v9)
    OUT_V9.write_text(json.dumps(output, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    log.info(f"→ {OUT_V9}")

    # Écriture data.json (format legacy index.html)
    legacy = to_legacy_format(output)
    OUT_LEGACY.write_text(json.dumps(legacy, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    log.info(f"→ {OUT_LEGACY}")

    return output


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="BVC Financial Data Pipeline v9.0")
    parser.add_argument("--dry-run",  action="store_true", help="Utilise uniquement le fallback")
    parser.add_argument("--tickers",  type=str,  help="Tickers séparés par virgule, ex: MNG,SMI")
    parser.add_argument("--workers",  type=int,  default=3, help="Nb threads parallèles (défaut: 3)")
    args = parser.parse_args()

    tickers = [t.strip().upper() for t in args.tickers.split(",")] if args.tickers else None
    run(tickers=tickers, dry_run=args.dry_run, max_workers=args.workers)
