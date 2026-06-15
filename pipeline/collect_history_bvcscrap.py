#!/usr/bin/env python3
import sys, json, time, argparse, logging
from datetime import datetime, timedelta, timezone
from pathlib import Path

for pkg in ["bvcscrap", "pandas", "numpy", "openpyxl"]:
    try:
        __import__(pkg if pkg != "bvcscrap" else "BVCscrap")
    except ImportError:
        import subprocess
        subprocess.run([sys.executable, "-m", "pip", "install", pkg, "-q"], check=True)

import pandas as pd
import numpy as np

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("BVCSCRAP_HIST")

MANUAL_MAP: dict[str, str] = {
    "IAM":  "Maroc Telecom",
    "ATW":  "Attijariwafa",
    "BCP":  "BCP",
    "BOA":  "BOA",
    "CIH":  "CIH",
    "CDM":  "CDM",
    "WAF":  "Wafa Assur",
    "LHM":  "LafargeHolcim",
    "GAZ":  "Afriquia Gaz",
    "ATL":  "Auto Hall",
    "HPS":  "HPS",
    "LBV":  "LABEL VIE",
    "LES":  "Lesieur Cristal",
    "TQA":  "TAQA Morocco",
    "MRL":  "SODEP",
    "TMA":  "Total Maroc",
    "CMT":  "CMT",
    "MNG":  "Managem",
    "SMI":  "SMI",
    "AKD":  "Akdital",
    "ARD":  "Aradei Capital",
    "SAF":  "Sanlam Maroc",
    "OUL":  "Oulmes",
    "CIM":  "Ciments du Maroc",
    "CTM":  "CTM",
    "ZLD":  "Zellidja",
    "SOT":  "SOTHEMA",
    "MSA":  "Mutandis",
    "ADI":  "Alliances",
    "ADH":  "Addoha",
    "TGCC": "TGCC",
    "CFGB": "BMCI",
    "SRM":  "SRM",
    "SNA":  "Sonasid",
    "RIS":  "Risma",
    "ALU":  "Aluminium Maroc",
    "DAR":  "Res.Dar Saada",
    "IMI":  "Immr Invest",
    "DTT":  "Disty Technolog",
    "DSW":  "DISWAY",
    "MOX":  "Maghreb Oxygene",
    "STR":  "STROC Indus",
    "TIM":  "Timar",
    "SNP":  "SNEP",
    "SLM":  "SALAFIN",
    "JET":  "Jet Contractors",
    "M2M":  "M2M Group",
    "INV":  "INVOLYS",
    "S2M":  "S2M",
    "COL":  "Colorado",
    "AFM":  "AFMA",
    "AGM":  "Agma",
    "BAL":  "BALIMA",
    "NEJ":  "Auto Nejma",
    "CAR":  "Cartier Saada",
    "AFI":  "Afric Indus",
    "MIC":  "Microdata",
    "MUT":  "Mutandis",
    "EQD":  "EQDOM",
    "REB":  "Rebab Company",
    "SBS":  "Ste Boissons",
    "STK":  "Stokvis Nord Afr",
    "UNI":  "Unimer",
    "IBM":  "IBMaroc",
}

XLSX_DIR = Path(__file__).parent.parent / "data" / "historique"


def load_xlsx(ticker: str) -> pd.DataFrame:
    path = XLSX_DIR / f"{ticker}.xlsx"
    if not path.exists():
        return pd.DataFrame()
    try:
        df = pd.read_excel(path, engine="openpyxl")
        df.columns = [c.lower().strip() for c in df.columns]
        col_map = {}
        for col in df.columns:
            if col == "date":
                col_map[col] = "date"
            elif col in ("close", "clôture", "cloture", "dernier", "cours"):
                col_map[col] = "close"
            elif col in ("open", "ouvert"):
                col_map[col] = "open"
            elif col in ("high", "haut", "max"):
                col_map[col] = "high"
            elif col in ("low", "bas", "min"):
                col_map[col] = "low"
            elif "vol" in col:
                col_map[col] = "volume"
        df = df.rename(columns=col_map)
        if "date" not in df.columns or "close" not in df.columns:
            return pd.DataFrame()
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
        df = df.dropna(subset=["date", "close"])
        df["close"] = pd.to_numeric(df["close"], errors="coerce")
        for c in ["open", "high", "low"]:
            if c not in df.columns:
                df[c] = df["close"]
            else:
                df[c] = pd.to_numeric(df[c], errors="coerce").fillna(df["close"])
        if "volume" not in df.columns:
            df["volume"] = 0
        else:
            df["volume"] = pd.to_numeric(df["volume"], errors="coerce").fillna(0)
        df = df[df["close"] > 0].sort_values("date").reset_index(drop=True)
        return df[["date", "open", "high", "low", "close", "volume"]]
    except Exception as e:
        log.warning(f"Erreur lecture {path}: {e}")
        return pd.DataFrame()


def fetch_bvcscrap_extension(name: str, from_date: pd.Timestamp) -> pd.DataFrame:
    try:
        import BVCscrap as bvc
        start = (from_date + timedelta(days=1)).strftime("%Y-%m-%d")
        end = datetime.now().strftime("%Y-%m-%d")
        if start >= end:
            return pd.DataFrame()
        df = bvc.loadata(name, start=start, end=end)
        if df is None or df.empty:
            return pd.DataFrame()
        df = df.reset_index()
        col_map = {}
        for col in df.columns:
            cl = col.lower()
            if any(k in cl for k in ["close", "clôture", "cloture", "dernier", "cours", "value"]):
                col_map[col] = "close"
            elif any(k in cl for k in ["open", "ouvert"]):
                col_map[col] = "open"
            elif any(k in cl for k in ["high", "haut", "max"]):
                col_map[col] = "high"
            elif any(k in cl for k in ["low", "bas", "min"]):
                col_map[col] = "low"
            elif any(k in cl for k in ["vol", "volume"]):
                col_map[col] = "volume"
            elif any(k in cl for k in ["date", "index"]):
                col_map[col] = "date"
        df = df.rename(columns=col_map)
        if "date" not in df.columns:
            df["date"] = pd.date_range(end=datetime.now(), periods=len(df), freq="B")
        else:
            df["date"] = pd.to_datetime(df["date"], dayfirst=True, errors="coerce")
        if "close" not in df.columns:
            return pd.DataFrame()
        for c in ["open", "high", "low"]:
            if c not in df.columns:
                df[c] = df["close"]
        if "volume" not in df.columns:
            df["volume"] = 0
        df = df[["date", "open", "high", "low", "close", "volume"]].copy()
        df = df.dropna(subset=["date", "close"])
        df["close"]  = pd.to_numeric(df["close"],  errors="coerce")
        df["high"]   = pd.to_numeric(df["high"],   errors="coerce").fillna(df["close"])
        df["low"]    = pd.to_numeric(df["low"],    errors="coerce").fillna(df["close"])
        df["open"]   = pd.to_numeric(df["open"],   errors="coerce").fillna(df["close"])
        df["volume"] = pd.to_numeric(df["volume"], errors="coerce").fillna(0)
        df = df[df["close"] > 0].sort_values("date").reset_index(drop=True)
        return df
    except Exception as e:
        log.debug(f"loadata({name}): {e}")
        return pd.DataFrame()


def combine(xlsx_df: pd.DataFrame, ext_df: pd.DataFrame) -> pd.DataFrame:
    if ext_df.empty:
        return xlsx_df
    if xlsx_df.empty:
        return ext_df
    combined = pd.concat([xlsx_df, ext_df], ignore_index=True)
    combined = combined.drop_duplicates(subset=["date"]).sort_values("date").reset_index(drop=True)
    return combined


def calc_rsi(closes: pd.Series, period: int = 14) -> float:
    delta    = closes.diff()
    up       = delta.clip(lower=0)
    down     = -delta.clip(upper=0)
    ema_up   = up.ewm(com=period - 1, adjust=False).mean()
    ema_down = down.ewm(com=period - 1, adjust=False).mean()
    rs       = ema_up / ema_down.replace(0, np.nan)
    rsi      = 100 - (100 / (1 + rs))
    return round(float(rsi.iloc[-1]), 1) if not rsi.empty else 50.0


def calc_ma(closes: pd.Series, period: int) -> float:
    if len(closes) < period:
        return round(float(closes.mean()), 2)
    return round(float(closes.tail(period).mean()), 2)


def calc_macd(closes: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9):
    if len(closes) < slow + signal:
        return None, None, None
    ema_f = closes.ewm(span=fast, adjust=False).mean()
    ema_s = closes.ewm(span=slow, adjust=False).mean()
    macd  = ema_f - ema_s
    sig   = macd.ewm(span=signal, adjust=False).mean()
    hist  = macd - sig
    return (
        round(float(macd.iloc[-1]), 4),
        round(float(sig.iloc[-1]),  4),
        round(float(hist.iloc[-1]), 4),
    )


def calc_bollinger(closes: pd.Series, period: int = 20, n_std: float = 2.0):
    if len(closes) < period:
        return None, None, None
    tail = closes.tail(period)
    mid  = tail.mean()
    std  = tail.std(ddof=1)
    return (
        round(float(mid + n_std * std), 2),
        round(float(mid), 2),
        round(float(mid - n_std * std), 2),
    )


def calc_stoch(closes: pd.Series, highs: pd.Series, lows: pd.Series,
               k_period: int = 14, d_period: int = 3):
    if len(closes) < k_period:
        return None, None
    k_vals = []
    for i in range(d_period):
        idx = len(closes) - 1 - i
        if idx < k_period - 1:
            break
        c  = float(closes.iloc[idx])
        hh = float(highs.iloc[idx - k_period + 1: idx + 1].max())
        ll = float(lows.iloc[idx  - k_period + 1: idx + 1].min())
        d  = hh - ll
        k_vals.append(100 * (c - ll) / d if d > 0 else 50.0)
    if not k_vals:
        return None, None
    return round(k_vals[0], 2), round(float(np.mean(k_vals)), 2)


def compute_indicators(df: pd.DataFrame) -> dict:
    closes = df["close"]
    highs  = df["high"]
    lows   = df["low"]

    now = pd.Timestamp.now()
    w52_start = now - pd.Timedelta(weeks=52)
    w90_start = now - pd.Timedelta(days=90)

    df_52w = df[df["date"] >= w52_start]
    df_90  = df[df["date"] >= w90_start]

    h52w = round(float(df_52w["high"].max()), 2) if not df_52w.empty else round(float(highs.max()), 2)
    l52w = round(float(df_52w["low"].min()),  2) if not df_52w.empty else round(float(lows.min()),  2)
    h90  = round(float(df_90["high"].max()),  2) if not df_90.empty  else round(float(highs.max()), 2)
    l90  = round(float(df_90["low"].min(),   2) if not df_90.empty  else round(float(lows.min()),  2)

    rsi           = calc_rsi(closes)
    ma20          = calc_ma(closes, 20)
    ma50          = calc_ma(closes, 50)
    ma200         = calc_ma(closes, 200)
    macd, ms, mh  = calc_macd(closes)
    bbu, bbm, bbl = calc_bollinger(closes)
    sk, sd        = calc_stoch(closes, highs, lows)

    candles_250 = df.tail(250).copy()
    candles = [
        {
            "d": str(row["date"])[:10],
            "o": round(float(row["open"]),  2),
            "h": round(float(row["high"]),  2),
            "l": round(float(row["low"]),   2),
            "c": round(float(row["close"]), 2),
            "v": int(row["volume"]),
        }
        for _, row in candles_250.iterrows()
    ]

    return {
        "rsi":         rsi,
        "ma20":        ma20,
        "ma50":        ma50,
        "ma200":       ma200,
        "h90":         h90,
        "l90":         l90,
        "h52w":        h52w,
        "l52w":        l52w,
        "macd":        macd,
        "macd_signal": ms,
        "macd_hist":   mh,
        "bb_upper":    bbu,
        "bb_mid":      bbm,
        "bb_lower":    bbl,
        "stoch_k":     sk,
        "stoch_d":     sd,
        "last_close":  round(float(closes.iloc[-1]), 2),
        "last_date":   str(df["date"].iloc[-1])[:10],
        "n_candles":   len(df),
        "candles":     candles,
    }


def save_candle_file(ticker: str, df: pd.DataFrame, candles_dir: Path) -> None:
    candles_dir.mkdir(parents=True, exist_ok=True)
    candles = [
        {
            "d": str(row["date"])[:10],
            "o": round(float(row["open"]),  2),
            "h": round(float(row["high"]),  2),
            "l": round(float(row["low"]),   2),
            "c": round(float(row["close"]), 2),
            "v": int(row["volume"]),
        }
        for _, row in df.iterrows()
    ]
    out = candles_dir / f"{ticker}.json"
    out.write_text(json.dumps(candles, ensure_ascii=False), encoding="utf-8")


def run(tickers_filter: list[str] | None = None) -> dict:
    try:
        import BVCscrap  # noqa: F401
        bvcscrap_ok = True
    except ImportError:
        log.warning("BVCscrap non disponible — extension BVCscrap désactivée")
        bvcscrap_ok = False

    xlsx_tickers = {f.stem for f in XLSX_DIR.glob("*.xlsx")} if XLSX_DIR.exists() else set()
    all_tickers = sorted(xlsx_tickers | set(MANUAL_MAP.keys()))

    if tickers_filter:
        all_tickers = [t for t in all_tickers if t in tickers_filter]

    log.info(f"{len(all_tickers)} tickers à traiter")

    candles_dir = Path(__file__).parent / "candles"
    results: dict = {}

    for i, ticker in enumerate(all_tickers, 1):
        log.info(f"[{i}/{len(all_tickers)}] {ticker}")

        xlsx_df = load_xlsx(ticker)

        if bvcscrap_ok and ticker in MANUAL_MAP:
            name = MANUAL_MAP[ticker]
            if not xlsx_df.empty:
                last_date = xlsx_df["date"].iloc[-1]
            else:
                last_date = pd.Timestamp(datetime.now() - timedelta(days=31))
            ext_df = fetch_bvcscrap_extension(name, last_date)
            df = combine(xlsx_df, ext_df)
            if not ext_df.empty:
                log.info(f"  +{len(ext_df)} bougies BVCscrap ajoutées")
        else:
            df = xlsx_df

        if df.empty or len(df) < 14:
            log.warning(f"  {ticker}: historique insuffisant ({len(df)} bougies) — ignoré")
            continue

        try:
            ind = compute_indicators(df)
            results[ticker] = ind
            log.info(
                f"  {len(df)} bougies → RSI={ind['rsi']} "
                f"MA20={ind['ma20']} MA50={ind['ma50']} "
                f"H52w={ind['h52w']} L52w={ind['l52w']}"
            )
            save_candle_file(ticker, df, candles_dir)
        except Exception as e:
            log.warning(f"  {ticker}: calcul indicateurs échoué: {e}")

        time.sleep(0.2)

    return results


def save(results: dict, out_path: Path) -> None:
    output = {
        "_updated": datetime.now(timezone.utc).isoformat(),
        "_source":  "xlsx 3ans + BVCscrap extension",
        "_tickers": len(results),
        **results,
    }
    out_path.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    log.info(f"Sauvegardé : {out_path} ({len(results)} tickers)")


def main() -> None:
    parser = argparse.ArgumentParser(description="Collecte historique BVCscrap")
    parser.add_argument("--tickers", type=str, default="",
                        help="Liste CSV de tickers (défaut: tous)")
    parser.add_argument("--dry-run", action="store_true",
                        help="N'écrit pas le fichier de sortie")
    args = parser.parse_args()

    tickers_filter = [t.strip().upper() for t in args.tickers.split(",") if t.strip()] or None

    results = run(tickers_filter=tickers_filter)

    if not results:
        log.error("Aucun résultat")
        sys.exit(1)

    log.info(f"Résultats : {len(results)} tickers traités")
    missing = [t for t in MANUAL_MAP if t not in results]
    if missing:
        log.info(f"Manquants MANUAL_MAP : {missing}")

    if not args.dry_run:
        try:
            out = Path(__file__).parent / "historical_data.json"
        except NameError:
            out = Path("pipeline/historical_data.json")
        save(results, out)
        print(f"\nFichier : {out}")
    else:
        log.info("[dry-run] Aucune écriture")
        for t, v in sorted(results.items()):
            print(f"  {t:6s}: RSI={v['rsi']:5.1f} MA20={v['ma20']:8.2f} MA50={v['ma50']:8.2f} "
                  f"n={v['n_candles']}")


if __name__ == "__main__":
    main()