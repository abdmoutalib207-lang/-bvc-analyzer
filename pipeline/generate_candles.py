#!/usr/bin/env python3
"""
BVC Candle Generator — pipeline/generate_candles.py
Convertit data/historique/*.xlsx → pipeline/candles/{sym}.json
Format: [{d:"YYYY-MM-DD", o:float, h:float, l:float, c:float, v:int}]
"""
import sys, os, json, logging
from pathlib import Path
from datetime import datetime, timedelta

for pkg in ["pandas", "openpyxl", "requests", "numpy"]:
    try: __import__(pkg)
    except ImportError:
        import subprocess; subprocess.run([sys.executable,"-m","pip","install",pkg,"-q"],check=True)

import pandas as pd, numpy as np, requests

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)-8s | %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger("CandleGen")

ROOT        = Path(__file__).parent.parent
XLSX_DIR    = ROOT / "data" / "historique"
CANDLES_DIR = Path(__file__).parent / "candles"
MED_BASE    = "https://www.medias24.com/bourse/api_bourse.php"
HEADERS     = {"User-Agent":"Mozilla/5.0","Accept-Language":"fr-FR,fr;q=0.9"}
TIMEOUT     = 15

XLSX_ALIAS = {"TGC": "TGCC"}

try:
    sys.path.insert(0, str(ROOT))
    from bvc_config import ISIN_MAP, TICKERS_ALL
except Exception:
    ISIN_MAP = {}
    TICKERS_ALL = []


def _med_history(isin: str, days: int = 400) -> pd.DataFrame:
    to  = datetime.now()
    frm = to - timedelta(days=days + 30)
    try:
        r = requests.get(MED_BASE, params={
            "method": "getPriceHistory",
            "ISIN":   isin,
            "from":   frm.strftime("%Y-%m-%d"),
            "to":     to.strftime("%Y-%m-%d"),
            "format": "json"
        }, headers=HEADERS, timeout=TIMEOUT)
        if r.status_code != 200 or len(r.text) < 20:
            return pd.DataFrame()
        recs = r.json().get("result", [])
        if not isinstance(recs, list) or len(recs) < 5:
            return pd.DataFrame()
    except Exception:
        return pd.DataFrame()

    rows = []
    for rec in recs:
        try:
            raw = rec.get("date","")
            if "/" in raw:
                d, m, y = raw.split("/")
                dt = f"{y}-{m.zfill(2)}-{d.zfill(2)}"
            else:
                dt = raw[:10]
            c = float(rec.get("value") or 0)
            if c <= 0:
                continue
            rows.append({
                "d": dt,
                "c": round(c, 2),
                "h": round(float(rec.get("max")    or c), 2),
                "l": round(float(rec.get("min")    or c), 2),
                "v": int(float(rec.get("volume")   or 0)),
            })
        except Exception:
            continue

    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows).sort_values("d").reset_index(drop=True)
    df["o"] = df["c"].shift(1).fillna(df["c"]).round(2)
    return df


def _xlsx_to_candles(path: Path) -> list:
    df = pd.read_excel(path)
    df.columns = [c.lower().strip() for c in df.columns]
    if "date" not in df.columns:
        return []
    df["d"] = pd.to_datetime(df["date"]).dt.strftime("%Y-%m-%d")
    df["c"] = pd.to_numeric(df.get("close", df.get("clôture", 0)), errors="coerce").fillna(0)
    df["h"] = pd.to_numeric(df.get("high",  df.get("haut",    df["c"])), errors="coerce").fillna(df["c"])
    df["l"] = pd.to_numeric(df.get("low",   df.get("bas",     df["c"])), errors="coerce").fillna(df["c"])
    df["v"] = pd.to_numeric(df.get("volume",df.get("vol",     0)),       errors="coerce").fillna(0).astype(int)
    df["o"] = pd.to_numeric(df.get("open",  df.get("ouvert",  df["c"])), errors="coerce").fillna(df["c"])
    df = df[df["c"] > 0].sort_values("d").reset_index(drop=True)
    return [
        {"d": row["d"], "o": round(float(row["o"]),2),
         "h": round(float(row["h"]),2), "l": round(float(row["l"]),2),
         "c": round(float(row["c"]),2), "v": int(row["v"])}
        for _, row in df.iterrows()
    ]


def _merge_candles(existing: list, new_candles: list) -> list:
    combined = {c["d"]: c for c in existing}
    combined.update({c["d"]: c for c in new_candles})
    return sorted(combined.values(), key=lambda x: x["d"])


def generate_from_xlsx() -> dict:
    CANDLES_DIR.mkdir(exist_ok=True)
    results = {}

    for xlsx in sorted(XLSX_DIR.glob("*.xlsx")):
        ticker = XLSX_ALIAS.get(xlsx.stem.upper(), xlsx.stem.upper())
        try:
            candles = _xlsx_to_candles(xlsx)
            if not candles:
                log.warning(f"  {ticker}: XLSX vide")
                continue

            out = CANDLES_DIR / f"{ticker}.json"
            if out.exists():
                try:
                    existing = json.loads(out.read_text())
                    candles  = _merge_candles(existing, candles)
                except Exception:
                    pass

            out.write_text(json.dumps(candles, separators=(",",":")))
            log.info(f"  ✓ {ticker}: {len(candles)} bougies (XLSX)")
            results[ticker] = len(candles)
        except Exception as e:
            log.warning(f"  ✗ {ticker}: {e}")

    return results


def generate_from_med24(skip_existing_tickers: set = None, days: int = 400) -> dict:
    import time
    CANDLES_DIR.mkdir(exist_ok=True)
    if skip_existing_tickers is None:
        skip_existing_tickers = set()
    results = {}

    for ticker in TICKERS_ALL:
        canon = ticker
        if (CANDLES_DIR / f"{canon}.json").exists() and canon in skip_existing_tickers:
            log.info(f"  → {ticker}: candles XLSX déjà présentes, skip Médias24")
            continue

        isin = ISIN_MAP.get(ticker)
        if not isin:
            log.warning(f"  ✗ {ticker}: ISIN inconnu — skip")
            continue

        try:
            df = _med_history(isin, days=days)
            if df.empty or len(df) < 5:
                log.warning(f"  ✗ {ticker}: Médias24 vide ({len(df)} points)")
                time.sleep(0.3)
                continue

            candles = [
                {"d": row["d"], "o": float(row["o"]), "h": float(row["h"]),
                 "l": float(row["l"]), "c": float(row["c"]),   "v": int(row["v"])}
                for _, row in df.iterrows()
            ]

            out = CANDLES_DIR / f"{ticker}.json"
            if out.exists():
                try:
                    existing = json.loads(out.read_text())
                    candles  = _merge_candles(existing, candles)
                except Exception:
                    pass

            out.write_text(json.dumps(candles, separators=(",",":")))
            log.info(f"  ✓ {ticker}: {len(candles)} bougies (Médias24)")
            results[ticker] = len(candles)
            time.sleep(0.4)
        except Exception as e:
            log.warning(f"  ✗ {ticker}: {e}")
            time.sleep(0.3)

    return results


def run(xlsx_only: bool = False):
    log.info("═" * 60)
    log.info("BVC Candle Generator")
    log.info("═" * 60)

    log.info("\n[1/2] Génération depuis XLSX historique...")
    xlsx_results = generate_from_xlsx()
    log.info(f"  → {len(xlsx_results)} fichiers générés depuis XLSX")

    if xlsx_only:
        log.info("\nMode xlsx_only — fin.")
        return

    xlsx_tickers = set(xlsx_results.keys())
    log.info(f"\n[2/2] Récupération Médias24 pour les tickers sans XLSX ({len(TICKERS_ALL)-len(xlsx_tickers)} tickers)...")
    med24_results = generate_from_med24(skip_existing_tickers=xlsx_tickers)
    log.info(f"  → {len(med24_results)} fichiers générés depuis Médias24")

    total = len(xlsx_results) + len(med24_results)
    log.info(f"\n✅ Total: {total} fichiers candles générés dans pipeline/candles/")

    all_results = {**xlsx_results, **med24_results}
    log.info(f"   Tickers couverts: {', '.join(sorted(all_results.keys()))}")
    missing = [t for t in TICKERS_ALL if t not in all_results]
    if missing:
        log.warning(f"   Tickers sans candles: {', '.join(missing)}")


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--xlsx-only", action="store_true", help="Ne générer que depuis les XLSX")
    args = p.parse_args()
    run(xlsx_only=args.xlsx_only)
