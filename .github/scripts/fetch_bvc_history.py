"""
Script GitHub Actions — Récupération historique BVC 6 ans
Utilise BVCscrap + casabourse + yfinance avec fallback en cascade
"""
import os
import sys
import time
import json
import requests
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime

REPO_ROOT  = Path(__file__).parent.parent.parent
HIST_DIR   = REPO_ROOT / "data" / "historique"
HIST_DIR.mkdir(parents=True, exist_ok=True)

START_DATE     = os.environ.get("START_DATE", "2019-01-01")
TICKERS_FILTER = os.environ.get("TICKERS_FILTER", "").strip()
END_DATE       = datetime.now().strftime("%Y-%m-%d")

# ─────────────────────────────────────────────
# ISIN MAP (depuis bvc_config)
# ─────────────────────────────────────────────
sys.path.insert(0, str(REPO_ROOT))
try:
    from bvc_config import ISIN_MAP, TICKERS_ALL
except ImportError:
    ISIN_MAP = {
        "IAM": "MA0000011884", "ATW": "MA0000011900", "BCP": "MA0000011876",
        "MNG": "MA0000011868", "ADH": "MA0000011942", "ADI": "MA0000012213",
        "HPS": "MA0000012254", "AKD": "MA0000012288", "TGCC": "MA0000011983",
        "SOT": "MA0000011959", "MIC": "MA0000011827", "RIS": "MA0000011991",
        "SMI": "MA0000011975", "CMT": "MA0000011835", "SNA": "MA0000012007",
        "CSR": "MA0000011843", "MSA": "MA0000012023", "RDS": "MA0000012031",
        "BOA": "MA0000011918", "CIH": "MA0000011926", "CDM": "MA0000011934",
        "WAF": "MA0000011850", "LHM": "MA0000011892", "ATL": "MA0000011801",
        "LBV": "MA0000011967", "SRM": "MA0000012039", "CMGP": "MA0000012262",
        "CFGB": "MA0000012270", "VCNE": "MA0000012296", "CASH": "MA0000012304",
        "SGTM": "MA0000012312",
    }
    TICKERS_ALL = list(ISIN_MAP.keys())

if TICKERS_FILTER:
    TICKERS = [t.strip() for t in TICKERS_FILTER.split(",") if t.strip()]
else:
    TICKERS = TICKERS_ALL

print(f"Récupération historique BVC")
print(f"Période : {START_DATE} → {END_DATE}")
print(f"Tickers : {len(TICKERS)} tickers")


# ─────────────────────────────────────────────
# SOURCE 1 — Médias24 getPriceHistory (directe)
# ─────────────────────────────────────────────

def fetch_medias24(ticker: str, isin: str) -> pd.DataFrame:
    """Récupère via API Médias24 avec code ISIN."""
    url = (
        f"https://medias24.com/content/api"
        f"?method=getPriceHistory&ISIN={isin}"
        f"&format=json&from={START_DATE}&to={END_DATE}"
    )
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
        "Accept": "application/json",
        "Referer": "https://medias24.com/",
    }
    try:
        r = requests.get(url, headers=headers, timeout=15)
        if r.status_code != 200:
            return pd.DataFrame()
        data = r.json()
        if not data or "data" not in data:
            return pd.DataFrame()
        df = pd.DataFrame(data["data"])
        if df.empty:
            return pd.DataFrame()
        # Colonnes: date, close, high, low, open, volume (formats varient)
        col_map = {}
        for c in df.columns:
            cl = c.lower()
            if "date" in cl:     col_map[c] = "date"
            elif "close" in cl or "dernier" in cl or "last" in cl: col_map[c] = "close"
            elif "high" in cl or "haut" in cl:   col_map[c] = "high"
            elif "low" in cl or "bas" in cl:     col_map[c] = "low"
            elif "open" in cl or "ouv" in cl:    col_map[c] = "open"
            elif "vol" in cl:    col_map[c] = "volume"
        df = df.rename(columns=col_map)
        if "date" not in df.columns or "close" not in df.columns:
            return pd.DataFrame()
        df["date"] = pd.to_datetime(df["date"])
        df["close"] = pd.to_numeric(df["close"], errors="coerce")
        for col in ["high", "low", "open", "volume"]:
            if col not in df.columns:
                df[col] = df["close"]
            df[col] = pd.to_numeric(df[col], errors="coerce")
        df = df.dropna(subset=["date", "close"]).sort_values("date")
        return df[["date", "close", "high", "low", "open", "volume"]]
    except Exception as e:
        print(f"    Médias24 {ticker}: {e}")
        return pd.DataFrame()


# ─────────────────────────────────────────────
# SOURCE 2 — BVCscrap
# ─────────────────────────────────────────────

def fetch_bvcscrap(ticker: str) -> pd.DataFrame:
    try:
        import BVCscrap as bvc
        # BVCscrap utilise le code ISIN via un mapping interne
        df = bvc.loadata(ticker, start=START_DATE, end=END_DATE)
        if df is None or df.empty:
            return pd.DataFrame()
        df = df.reset_index()
        col_map = {}
        for c in df.columns:
            cl = c.lower()
            if "date" in cl or cl == "index": col_map[c] = "date"
            elif "value" in cl or "close" in cl: col_map[c] = "close"
            elif "max" in cl or "high" in cl:  col_map[c] = "high"
            elif "min" in cl or "low" in cl:   col_map[c] = "low"
            elif "vol" in cl:  col_map[c] = "volume"
        df = df.rename(columns=col_map)
        if "close" not in df.columns:
            return pd.DataFrame()
        if "date" not in df.columns:
            df["date"] = pd.date_range(START_DATE, periods=len(df), freq="B")
        df["date"] = pd.to_datetime(df["date"])
        for col in ["high", "low", "open", "volume"]:
            if col not in df.columns:
                df[col] = df["close"]
        return df[["date", "close", "high", "low", "open", "volume"]].dropna(subset=["close"])
    except Exception as e:
        print(f"    BVCscrap {ticker}: {e}")
        return pd.DataFrame()


# ─────────────────────────────────────────────
# SOURCE 3 — yfinance (.CS suffix)
# ─────────────────────────────────────────────

YF_SUFFIX_MAP = {
    "TGCC": "TGC", "SNA": "SNA", "CSR": "CSR",
}

def fetch_yfinance(ticker: str) -> pd.DataFrame:
    try:
        import yfinance as yf
        yf_ticker = YF_SUFFIX_MAP.get(ticker, ticker) + ".CS"
        df = yf.download(yf_ticker, start=START_DATE, end=END_DATE, progress=False)
        if df is None or df.empty:
            return pd.DataFrame()
        df = df.reset_index()
        df.columns = [c.lower() if isinstance(c, str) else c[0].lower() for c in df.columns]
        # Handle multi-level columns
        if hasattr(df.columns, 'levels'):
            df.columns = [c[0].lower() if isinstance(c, tuple) else c.lower() for c in df.columns]
        rename = {"adj close": "close", "adj_close": "close"}
        df = df.rename(columns=rename)
        if "close" not in df.columns and "close" not in df.columns:
            return pd.DataFrame()
        for col in ["high", "low", "open", "volume"]:
            if col not in df.columns:
                df[col] = df.get("close", 0)
        df["date"] = pd.to_datetime(df.get("date", df.index))
        return df[["date", "close", "high", "low", "open", "volume"]].dropna(subset=["close"])
    except Exception as e:
        print(f"    yfinance {ticker}: {e}")
        return pd.DataFrame()


# ─────────────────────────────────────────────
# SOURCE 4 — casabourse
# ─────────────────────────────────────────────

def fetch_casabourse(ticker: str) -> pd.DataFrame:
    try:
        import casabourse as cb
        df = cb.get_historical_data_auto(ticker, START_DATE, END_DATE)
        if df is None or df.empty:
            return pd.DataFrame()
        df = df.reset_index()
        df.columns = [c.lower() for c in df.columns]
        for col in ["high", "low", "open", "volume"]:
            if col not in df.columns:
                df[col] = df.get("close", df.get("price", 0))
        if "date" not in df.columns:
            df["date"] = df.index
        df["date"] = pd.to_datetime(df["date"])
        return df[["date", "close", "high", "low", "open", "volume"]].dropna(subset=["close"])
    except Exception as e:
        print(f"    casabourse {ticker}: {e}")
        return pd.DataFrame()


# ─────────────────────────────────────────────
# ORCHESTRATEUR AVEC FALLBACK
# ─────────────────────────────────────────────

def fetch_ticker(ticker: str) -> pd.DataFrame:
    isin = ISIN_MAP.get(ticker, "")

    # Cascade de sources
    for source_name, fetch_fn, arg in [
        ("Médias24",   fetch_medias24,  (ticker, isin)),
        ("BVCscrap",   fetch_bvcscrap,  (ticker,)),
        ("casabourse", fetch_casabourse,(ticker,)),
        ("yfinance",   fetch_yfinance,  (ticker,)),
    ]:
        if source_name == "Médias24" and not isin:
            continue
        try:
            df = fetch_fn(*arg)
            if df is not None and not df.empty and len(df) > 10:
                print(f"  ✓ {ticker} via {source_name}: {len(df)} observations")
                return df
        except Exception:
            pass
        time.sleep(0.5)

    print(f"  ✗ {ticker}: aucune source disponible")
    return pd.DataFrame()


# ─────────────────────────────────────────────
# MASI HISTORIQUE
# ─────────────────────────────────────────────

def fetch_masi() -> pd.DataFrame:
    print("\nTentative MASI historique...")
    # Essai 1: yfinance (^MASI)
    try:
        import yfinance as yf
        df = yf.download("^MASI", start=START_DATE, end=END_DATE, progress=False)
        if df is not None and not df.empty:
            df = df.reset_index()
            df.columns = [c[0].lower() if isinstance(c, tuple) else c.lower() for c in df.columns]
            df["date"] = pd.to_datetime(df["date"])
            print(f"  ✓ MASI via yfinance: {len(df)} observations")
            return df[["date", "close"]].rename(columns={"close": "masi"})
    except Exception as e:
        print(f"  yfinance MASI: {e}")

    # Essai 2: Médias24 MASI (ISIN fictif)
    masi_isin = "MA0000000020"
    df = fetch_medias24("MASI", masi_isin)
    if not df.empty:
        return df[["date", "close"]].rename(columns={"close": "masi"})

    print("  ✗ MASI: aucune donnée disponible")
    return pd.DataFrame()


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────

results = {}
failed  = []

print(f"\n{'─'*50}")
print(f"Téléchargement {len(TICKERS)} tickers...")
print(f"{'─'*50}")

for i, ticker in enumerate(TICKERS, 1):
    print(f"[{i:02d}/{len(TICKERS)}] {ticker}...")
    existing = HIST_DIR / f"{ticker}.xlsx"

    # Vérifier si déjà à jour
    if existing.exists():
        try:
            old = pd.read_excel(existing, engine="openpyxl")
            old["date"] = pd.to_datetime(old["date"])
            old_start = old["date"].min().strftime("%Y-%m-%d")
            if old_start <= START_DATE and len(old) > 100:
                print(f"  → Déjà présent depuis {old_start} ({len(old)} obs)")
                results[ticker] = old
                continue
        except Exception:
            pass

    df = fetch_ticker(ticker)
    if df.empty:
        failed.append(ticker)
    else:
        df.to_excel(existing, index=False, engine="openpyxl")
        results[ticker] = df

    time.sleep(0.3)  # Rate limiting

# MASI
masi_df = fetch_masi()
if not masi_df.empty:
    masi_df.to_csv(REPO_ROOT / "data" / "masi_history.csv", index=False)
    print(f"MASI sauvegardé: {len(masi_df)} observations")
else:
    # Construire proxy MASI depuis les tickers disponibles
    if results:
        close_dfs = {}
        for t, df in results.items():
            if "close" in df.columns and "date" in df.columns:
                d = df.set_index("date")["close"]
                close_dfs[t] = d
        if close_dfs:
            close_panel = pd.DataFrame(close_dfs)
            normalized  = close_panel.divide(close_panel.iloc[0], axis=1) * 100
            masi_proxy  = normalized.mean(axis=1).rename("masi")
            masi_df = masi_proxy.reset_index()
            masi_df.columns = ["date", "masi"]
            masi_df.to_csv(REPO_ROOT / "data" / "masi_history.csv", index=False)
            print(f"Proxy MASI construit: {len(masi_df)} observations")

# Rapport final
print(f"\n{'═'*50}")
print(f"RÉSULTAT FINAL")
print(f"{'═'*50}")
print(f"✓ Réussi  : {len(results)} / {len(TICKERS)} tickers")
print(f"✗ Échoué  : {len(failed)} — {failed}")
print(f"Fichiers sauvegardés dans data/historique/")

# Statistiques
if results:
    counts = [(t, len(df)) for t, df in results.items()]
    counts.sort(key=lambda x: x[1], reverse=True)
    print("\nTop 10 par nombre d'observations:")
    for t, n in counts[:10]:
        print(f"  {t:<6}: {n} obs")
