"""
Indicateurs techniques : RSI(14), MA20, MA50, high/low 90j
RSI calculé obligatoirement depuis l'historique de prix — JAMAIS scrapé.

Sources historique : Médias24 getPriceHistory (ISIN) → yfinance (.CS) → yfinance (.MA)
Calcul : pandas (Wilder EMA) — TA-Lib utilisé si installé (plus précis)
"""
import logging
import random
import time
from datetime import datetime, timedelta

import numpy as np
import pandas as pd
import requests

from ..scrapers.constants import HEADERS_LIST, ISIN_MAP, YF_MAP, PROXY, timeout_session

log = logging.getLogger(__name__)

MED_BASE = "https://medias24.com/content/api"


# ── RSI (Wilder EMA — méthode standard) ──────────────────────────────────────

def _rsi_pandas(closes: pd.Series, period: int = 14) -> float | None:
    """Calcul RSI via Wilder Smoothed Moving Average (méthode standard)."""
    if len(closes) < period + 1:
        return None
    delta = closes.diff().dropna()
    gain  = delta.clip(lower=0)
    loss  = (-delta).clip(lower=0)

    # Wilder EMA (pas de SMA initiale — rolling puis EWM)
    avg_gain = gain.ewm(alpha=1/period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1/period, min_periods=period, adjust=False).mean()

    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    last = rsi.dropna().iloc[-1]
    return round(float(last), 2) if not np.isnan(last) else None


def _rsi_talib(closes: np.ndarray, period: int = 14) -> float | None:
    """Calcul RSI via TA-Lib (si disponible)."""
    try:
        import talib
        rsi = talib.RSI(closes.astype(float), timeperiod=period)
        val = rsi[~np.isnan(rsi)]
        return round(float(val[-1]), 2) if len(val) > 0 else None
    except ImportError:
        return None


def compute_rsi(closes: np.ndarray | pd.Series, period: int = 14) -> float | None:
    """
    RSI calculé — essaie TA-Lib d'abord, pandas en fallback.
    Valide que la valeur est dans [0, 100].
    """
    if len(closes) < period + 2:
        return None
    arr = np.array(closes, dtype=float)
    arr = arr[~np.isnan(arr)]

    # TA-Lib si disponible
    val = _rsi_talib(arr, period)
    if val is None:
        val = _rsi_pandas(pd.Series(arr), period)

    if val is not None and not (0 <= val <= 100):
        log.warning(f"RSI hors plage: {val}")
        return None
    return val


# ── Fetch historique ──────────────────────────────────────────────────────────

def _fetch_medias24_history(sym: str, days: int = 120) -> pd.DataFrame | None:
    """Récupère l'historique OHLCV depuis Médias24 API."""
    isin = ISIN_MAP.get(sym)
    if not isin:
        return None

    to_  = datetime.today()
    from_= to_ - timedelta(days=days)
    fmt  = lambda d: d.strftime("%Y-%m-%d")

    sess = timeout_session()
    for url in [
        f"{MED_BASE}?method=getPriceHistory&ISIN={isin}&from={fmt(from_)}&to={fmt(to_)}&format=json",
        f"{PROXY}{MED_BASE}?method=getPriceHistory&ISIN={isin}&from={fmt(from_)}&to={fmt(to_)}&format=json",
    ]:
        try:
            r = sess.get(url, headers=random.choice(HEADERS_LIST), timeout=15)
            r.raise_for_status()
            recs = r.json().get("result", [])
            if not isinstance(recs, list) or len(recs) < 10:
                continue

            rows = []
            for rec in recs:
                raw = rec.get("date", "")
                try:
                    if "/" in raw:
                        d, m, y = raw.split("/")
                        dt = datetime(int(y), int(m), int(d))
                    else:
                        dt = datetime.fromisoformat(raw[:10])
                except Exception:
                    continue
                close  = float(rec.get("value") or 0)
                high   = float(rec.get("max")   or close)
                low    = float(rec.get("min")   or close)
                volume = float(rec.get("volume") or 0)
                if close <= 0:
                    continue
                rows.append({"date": dt, "close": close, "high": high,
                              "low": low, "volume": volume})

            if len(rows) >= 10:
                df = pd.DataFrame(rows).sort_values("date").reset_index(drop=True)
                log.debug(f"{sym} history ← Médias24 ({len(df)} jours)")
                return df

        except Exception as e:
            log.debug(f"Médias24 hist {sym}: {e}")
        time.sleep(1 + random.random())

    return None


def _fetch_yfinance_history(sym: str, period: str = "6mo") -> pd.DataFrame | None:
    """Récupère l'historique via yfinance (.CS ou .MA)."""
    try:
        import yfinance as yf
        for suffix in [YF_MAP.get(sym), f"{sym}.MA", f"{sym}.CS"]:
            if not suffix:
                continue
            try:
                df = yf.download(suffix, period=period, progress=False, auto_adjust=True)
                if df is not None and len(df) >= 10:
                    df = df.rename(columns=str.lower)
                    df.index.name = "date"
                    df = df.reset_index()
                    df["date"] = pd.to_datetime(df["date"])
                    log.debug(f"{sym} history ← yfinance {suffix} ({len(df)} jours)")
                    return df[["date", "close", "high", "low", "volume"]].copy()
            except Exception:
                continue
    except ImportError:
        pass
    return None


# ── Indicateurs avancés ──────────────────────────────────────────────────────

def _macd(closes: pd.Series, fast=12, slow=26, signal=9) -> tuple:
    """MACD(12,26,9) → (macd, signal, histogram) ou (None, None, None)."""
    if len(closes) < slow + signal:
        return None, None, None
    ema_fast  = closes.ewm(span=fast, adjust=False).mean()
    ema_slow  = closes.ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    sig_line  = macd_line.ewm(span=signal, adjust=False).mean()
    hist      = macd_line - sig_line
    return (
        round(float(macd_line.iloc[-1]), 4),
        round(float(sig_line.iloc[-1]),  4),
        round(float(hist.iloc[-1]),      4),
    )


def _bollinger(closes: pd.Series, period=20, n_std=2.0) -> tuple:
    """Bollinger Bands(20,2) → (upper, middle, lower) ou (None, None, None)."""
    if len(closes) < period:
        return None, None, None
    tail   = closes.tail(period)
    mid    = float(tail.mean())
    std    = float(tail.std(ddof=1))
    return (
        round(mid + n_std * std, 2),
        round(mid,               2),
        round(mid - n_std * std, 2),
    )


def _stochastic(closes: pd.Series, highs: pd.Series, lows: pd.Series,
                k_period=14, d_period=3) -> tuple:
    """Stochastique(14,3) → (%K, %D) ou (None, None)."""
    if len(closes) < k_period:
        return None, None
    k_vals = []
    for i in range(d_period):
        idx = len(closes) - 1 - i
        if idx < k_period - 1:
            break
        c   = float(closes.iloc[idx])
        hh  = float(highs.iloc[idx - k_period + 1: idx + 1].max())
        ll  = float(lows.iloc[idx  - k_period + 1: idx + 1].min())
        denom = hh - ll
        k_vals.append(100 * (c - ll) / denom if denom > 0 else 50.0)
    if not k_vals:
        return None, None
    return round(k_vals[0], 2), round(float(np.mean(k_vals)), 2)


# ── Calcul global des indicateurs techniques ─────────────────────────────────

def compute_technical(sym: str, rsi_period: int = 14,
                      ma_short: int = 20, ma_long: int = 50,
                      history_days: int = 130) -> dict | None:
    """
    Calcule RSI(14), MA20, MA50, MACD(12,26,9), Bollinger(20,2),
    Stochastique(14,3) et high/low 90j depuis l'historique réel.
    Retourne None si impossible de calculer.
    """
    # Récupération de l'historique
    df = _fetch_medias24_history(sym, days=history_days)
    source = "Médias24"

    if df is None or len(df) < rsi_period + 5:
        time.sleep(1)
        df = _fetch_yfinance_history(sym)
        source = "yfinance"

    if df is None or len(df) < rsi_period + 5:
        log.warning(f"{sym} technical: historique insuffisant")
        return None

    closes = df["close"].astype(float)
    highs  = df["high"].astype(float)
    lows   = df["low"].astype(float)

    # RSI (jamais scrapé — calculé obligatoirement)
    rsi = compute_rsi(closes.values, rsi_period)

    # Moyennes mobiles simples
    def sma(series, n):
        if len(series) < n:
            return None
        return round(float(series.iloc[-n:].mean()), 2)

    ma20 = sma(closes, ma_short)
    ma50 = sma(closes, ma_long)

    # High/Low sur 90 jours glissants
    last_90  = df.tail(90)
    high_90d = round(float(last_90["high"].max()), 2) if len(last_90) > 5 else None
    low_90d  = round(float(last_90["low"].min()),  2) if len(last_90) > 5 else None

    # MACD(12,26,9)
    macd_val, macd_sig, macd_hist = _macd(closes) if len(closes) >= 35 else (None, None, None)

    # Bollinger Bands(20,2)
    bb_upper, bb_mid, bb_lower = _bollinger(closes) if len(closes) >= 20 else (None, None, None)

    # Stochastique(14,3)
    stoch_k, stoch_d = _stochastic(closes, highs, lows) if len(closes) >= 14 else (None, None)

    result = {
        "rsi_14":      rsi,
        "ma20":        ma20,
        "ma50":        ma50,
        "high_90d":    high_90d,
        "low_90d":     low_90d,
        "macd":        macd_val,
        "macd_signal": macd_sig,
        "macd_hist":   macd_hist,
        "bb_upper":    bb_upper,
        "bb_mid":      bb_mid,
        "bb_lower":    bb_lower,
        "stoch_k":     stoch_k,
        "stoch_d":     stoch_d,
        "_source":     source,
        "_nb_candles": len(df),
    }

    log.debug(
        f"{sym} RSI={rsi} MA20={ma20} MA50={ma50} "
        f"MACD={macd_val} BB={bb_upper}/{bb_lower} src={source}"
    )
    return result
