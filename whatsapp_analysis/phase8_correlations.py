"""
Phase 8 — Cross-Signal Correlations & Lead-Lag Analysis
Corrèle les signaux NLP avec les mouvements de prix BVC (réels ou simulés)
"""
from __future__ import annotations

import json
import logging
import os
import warnings
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from scipy import stats
from scipy.stats import pearsonr, spearmanr

warnings.filterwarnings("ignore")
logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────────────────────
DATA_ROOT = Path(__file__).parent.parent / "data"
FINANCIAL_DATA_PATH = Path(__file__).parent.parent / "financial_data.json"
DATA_JSON_PATH = Path(__file__).parent.parent / "data.json"

LAG_RANGE = range(-5, 31)   # lags en jours: -5 à +30
MIN_OVERLAP = 30             # observations minimales pour corrélation
RF_ANNUAL = 0.03             # taux sans risque Maroc


# ─────────────────────────────────────────────────────────────
# CHARGEMENT DES DONNÉES DE PRIX
# ─────────────────────────────────────────────────────────────

def load_price_data() -> Dict[str, pd.DataFrame]:
    """
    Charge les données de prix depuis financial_data.json ou data.json.
    Retourne un dict: ticker -> DataFrame(date, price, return).
    """
    price_data: Dict[str, pd.DataFrame] = {}

    # Essaie financial_data.json en premier
    if FINANCIAL_DATA_PATH.exists():
        try:
            with open(FINANCIAL_DATA_PATH, "r", encoding="utf-8") as f:
                fd = json.load(f)
            data_dict = fd.get("data", {})
            if isinstance(data_dict, dict):
                for ticker, info in data_dict.items():
                    if isinstance(info, dict):
                        market = info.get("market", {})
                        price = market.get("price") if isinstance(market, dict) else None
                        if price and price > 0:
                            price_data[ticker] = {"current_price": float(price)}
            logger.info(f"Loaded {len(price_data)} tickers from financial_data.json")
        except Exception as e:
            logger.warning(f"Could not load financial_data.json: {e}")

    # Complète avec data.json
    if DATA_JSON_PATH.exists():
        try:
            with open(DATA_JSON_PATH, "r", encoding="utf-8") as f:
                dj = json.load(f)
            tickers_list = dj.get("tickers", [])
            if isinstance(tickers_list, list):
                for item in tickers_list:
                    ticker = item.get("symbol", "")
                    if ticker and ticker not in price_data:
                        price = item.get("price", 0) or item.get("close", 0)
                        if price and float(price) > 0:
                            price_data[ticker] = {
                                "current_price": float(price),
                                "chg": float(item.get("chg", 0)),
                                "h90": float(item.get("h90", price * 1.1)),
                                "l90": float(item.get("l90", price * 0.9)),
                                "rsi": float(item.get("rsi", 50)),
                                "alpha": float(item.get("alpha", 0)),
                                "win": float(item.get("win", 50)),
                            }
            logger.info(f"Price data now has {len(price_data)} tickers after data.json")
        except Exception as e:
            logger.warning(f"Could not load data.json: {e}")

    return price_data


def generate_synthetic_price_series(
    ticker: str,
    start_date: str,
    end_date: str,
    current_price: float,
    annualized_vol: float = 0.25,
    annualized_drift: float = 0.08,
    seed: Optional[int] = None,
) -> pd.Series:
    """
    Génère une série de prix synthétiques réalistes pour le marché marocain.
    Utilise un mouvement brownien géométrique avec retour à la moyenne.
    """
    if seed is not None:
        rng = np.random.RandomState(seed)
    else:
        rng = np.random.RandomState(hash(ticker) % 2**31)

    dates = pd.date_range(start_date, end_date, freq="B")
    n = len(dates)
    dt = 1 / 252  # fraction d'année par jour de trading

    # Paramètres GBM
    mu = annualized_drift
    sigma = annualized_vol

    # Retour à la moyenne (mean-reversion partiel, modèle Ornstein-Uhlenbeck)
    theta = 0.05  # vitesse de retour

    log_returns = np.zeros(n)
    log_returns[0] = 0.0
    long_run_mean = mu * dt

    for i in range(1, n):
        shock = rng.normal(0, 1)
        # Ornstein-Uhlenbeck sur les log-returns
        log_returns[i] = (
            long_run_mean
            + theta * (long_run_mean - log_returns[i - 1])
            + sigma * np.sqrt(dt) * shock
        )

    # Reconstruit la série de prix en reculant depuis le prix actuel
    cumulative = np.cumsum(log_returns[::-1])
    log_prices_backward = np.log(current_price) - cumulative
    prices = np.exp(log_prices_backward[::-1])

    series = pd.Series(prices, index=dates, name=ticker)
    return series


def build_price_panel(
    df: pd.DataFrame,
    price_data: Dict[str, Any],
) -> pd.DataFrame:
    """
    Construit un panel de prix journaliers pour tous les tickers présents dans df.
    Retourne: DataFrame(date x ticker) avec les prix de clôture.
    """
    if df.empty or "timestamp" not in df.columns:
        logger.warning("DataFrame vide ou sans 'timestamp'")
        return pd.DataFrame()

    start_date = df["timestamp"].min().strftime("%Y-%m-%d")
    end_date = df["timestamp"].max().strftime("%Y-%m-%d")

    # Tickers mentionnés dans le chat
    mentioned_tickers: set = set()
    if "tickers_mentioned" in df.columns:
        for cell in df["tickers_mentioned"].dropna():
            if isinstance(cell, list):
                mentioned_tickers.update(cell)
            elif isinstance(cell, str) and cell:
                mentioned_tickers.add(cell)

    # Garde seulement les tickers avec données de prix
    available = set(price_data.keys()) & mentioned_tickers
    if not available:
        available = set(price_data.keys())

    price_panel: Dict[str, pd.Series] = {}
    for ticker in sorted(available):
        info = price_data.get(ticker, {})
        current_price = info.get("current_price", 100.0) if isinstance(info, dict) else 100.0
        if current_price <= 0:
            current_price = 100.0

        # Vol calibrée sur les données disponibles
        h90 = info.get("h90", current_price * 1.15) if isinstance(info, dict) else current_price * 1.15
        l90 = info.get("l90", current_price * 0.85) if isinstance(info, dict) else current_price * 0.85
        h90 = h90 if h90 and h90 > 0 else current_price * 1.15
        l90 = l90 if l90 and l90 > 0 else current_price * 0.85

        range_90 = (h90 - l90) / max(current_price, 1)
        annualized_vol = min(max(range_90 * np.sqrt(252 / 90), 0.10), 0.60)

        price_series = generate_synthetic_price_series(
            ticker=ticker,
            start_date=start_date,
            end_date=end_date,
            current_price=current_price,
            annualized_vol=annualized_vol,
            seed=hash(ticker) % 2**31,
        )
        price_panel[ticker] = price_series

    if not price_panel:
        return pd.DataFrame()

    panel = pd.DataFrame(price_panel)
    panel.index.name = "date"
    return panel


# ─────────────────────────────────────────────────────────────
# AGRÉGATION DES SIGNAUX NLP PAR JOUR/TICKER
# ─────────────────────────────────────────────────────────────

def build_daily_sentiment(
    df: pd.DataFrame,
    member_scores: Optional[pd.DataFrame] = None,
) -> pd.DataFrame:
    """
    Agrège les sentiments quotidiens depuis le DataFrame principal.
    Retourne: DataFrame(date) avec colonnes de sentiment agrégé.
    """
    if df.empty:
        return pd.DataFrame()

    work = df.copy()
    if "timestamp" not in work.columns:
        logger.error("Colonne 'timestamp' manquante dans df")
        return pd.DataFrame()

    work["date"] = pd.to_datetime(work["timestamp"]).dt.normalize()

    # Sentiment numérique
    if "sentiment" not in work.columns:
        work["sentiment"] = 0.0
    else:
        sentiment_map = {
            "positif": 1.0, "positive": 1.0, "bullish": 1.0,
            "negatif": -1.0, "negative": -1.0, "bearish": -1.0,
            "neutre": 0.0, "neutral": 0.0,
        }
        if work["sentiment"].dtype == object:
            work["sentiment_num"] = work["sentiment"].map(
                lambda x: sentiment_map.get(str(x).lower(), 0.0)
            )
        else:
            work["sentiment_num"] = pd.to_numeric(work["sentiment"], errors="coerce").fillna(0.0)

    if "sentiment_num" not in work.columns:
        work["sentiment_num"] = pd.to_numeric(work["sentiment"], errors="coerce").fillna(0.0)

    # Signal numérique
    signal_map = {
        "ACHAT_FORT": 2.0, "ACHETER": 1.0, "RENFORCEMENT": 0.5,
        "DOUTE": 0.0, "IRONIE": 0.0, "RUMEUR": 0.0,
        "VENTE": -1.0, "PANIQUE": -2.0, "FOMO": 0.5, "EUPHORIE": 1.0,
    }
    if "signal" in work.columns:
        work["signal_num"] = work["signal"].map(
            lambda x: signal_map.get(str(x).upper(), 0.0) if pd.notna(x) else 0.0
        )
    else:
        work["signal_num"] = 0.0

    # Poids Smart Money
    if member_scores is not None and not member_scores.empty and "author" in work.columns:
        sms_col = next(
            (c for c in ["sms_score", "smart_money_score", "score"] if c in member_scores.columns),
            None,
        )
        if sms_col:
            idx_col = member_scores.index.name or "author"
            if idx_col in member_scores.columns:
                sms_map = member_scores.set_index(idx_col)[sms_col].to_dict()
            else:
                sms_map = member_scores[sms_col].to_dict()
            work["sms_weight"] = work["author"].map(sms_map).fillna(1.0)
        else:
            work["sms_weight"] = 1.0
    else:
        work["sms_weight"] = 1.0

    work["sms_weight"] = work["sms_weight"].clip(0.1, 5.0)

    # Agrégation quotidienne globale
    daily = (
        work.groupby("date")
        .agg(
            sentiment_mean=("sentiment_num", "mean"),
            sentiment_std=("sentiment_num", "std"),
            signal_mean=("signal_num", "mean"),
            message_count=("sentiment_num", "count"),
            buy_count=(
                "signal_num",
                lambda x: (x > 0).sum(),
            ),
            sell_count=(
                "signal_num",
                lambda x: (x < 0).sum(),
            ),
            smart_money_sentiment=(
                "sentiment_num",
                lambda x: np.average(x, weights=work.loc[x.index, "sms_weight"]),
            ),
        )
        .reset_index()
    )
    daily["sentiment_std"] = daily["sentiment_std"].fillna(0.0)
    daily["buy_ratio"] = daily["buy_count"] / daily["message_count"].clip(lower=1)
    daily["sell_ratio"] = daily["sell_count"] / daily["message_count"].clip(lower=1)
    daily["net_signal"] = daily["buy_ratio"] - daily["sell_ratio"]

    # Z-score du volume de messages
    vol_mean = daily["message_count"].mean()
    vol_std = daily["message_count"].std()
    daily["volume_zscore"] = (daily["message_count"] - vol_mean) / max(vol_std, 1e-6)

    # Momentum du sentiment (changement sur 5 jours)
    daily = daily.sort_values("date").set_index("date")
    daily["sentiment_momentum_5d"] = daily["sentiment_mean"].diff(5)
    daily["sentiment_momentum_10d"] = daily["sentiment_mean"].diff(10)
    daily["sentiment_momentum_20d"] = daily["sentiment_mean"].diff(20)
    daily = daily.reset_index()

    return daily


def build_ticker_daily_sentiment(df: pd.DataFrame) -> pd.DataFrame:
    """
    Agrège les sentiments par jour ET par ticker.
    Retourne: DataFrame(date, ticker, sentiment_mean, mention_count, sentiment_velocity)
    """
    if df.empty or "tickers_mentioned" not in df.columns:
        return pd.DataFrame()

    work = df.copy()
    work["date"] = pd.to_datetime(work["timestamp"]).dt.normalize()

    sentiment_map = {
        "positif": 1.0, "positive": 1.0, "bullish": 1.0,
        "negatif": -1.0, "negative": -1.0, "bearish": -1.0,
        "neutre": 0.0, "neutral": 0.0,
    }
    if work["sentiment"].dtype == object:
        work["sentiment_num"] = work["sentiment"].map(
            lambda x: sentiment_map.get(str(x).lower(), 0.0)
        )
    else:
        work["sentiment_num"] = pd.to_numeric(work["sentiment"], errors="coerce").fillna(0.0)

    # Explode tickers
    rows = []
    for _, row in work.iterrows():
        tickers = row.get("tickers_mentioned", [])
        if not isinstance(tickers, list):
            continue
        for t in tickers:
            rows.append({
                "date": row["date"],
                "ticker": t,
                "sentiment_num": row["sentiment_num"],
            })

    if not rows:
        return pd.DataFrame()

    exploded = pd.DataFrame(rows)
    ticker_daily = (
        exploded.groupby(["date", "ticker"])
        .agg(
            sentiment_mean=("sentiment_num", "mean"),
            mention_count=("sentiment_num", "count"),
        )
        .reset_index()
    )

    # Velocity = changement de sentiment sur 3 jours par ticker
    ticker_daily = ticker_daily.sort_values(["ticker", "date"])
    ticker_daily["sentiment_velocity"] = ticker_daily.groupby("ticker")[
        "sentiment_mean"
    ].diff(3)

    return ticker_daily


# ─────────────────────────────────────────────────────────────
# ANALYSE LEAD-LAG
# ─────────────────────────────────────────────────────────────

def compute_lead_lag_correlation(
    sentiment_series: pd.Series,
    return_series: pd.Series,
    lags: range = LAG_RANGE,
    min_obs: int = MIN_OVERLAP,
) -> pd.DataFrame:
    """
    Calcule la corrélation de Pearson entre le sentiment et les rendements à chaque lag.
    Un lag positif signifie que le sentiment précède le rendement.

    Returns: DataFrame(lag, pearson_r, p_value, n_obs)
    """
    results = []
    sent = sentiment_series.dropna()
    ret = return_series.dropna()

    # Aligne sur l'index commun
    common_idx = sent.index.intersection(ret.index)
    if len(common_idx) < min_obs:
        logger.warning(f"Insufficient overlap: {len(common_idx)} < {min_obs}")
        return pd.DataFrame(columns=["lag", "pearson_r", "p_value", "n_obs", "significant"])

    sent_aligned = sent.reindex(common_idx)
    ret_aligned = ret.reindex(common_idx)

    for lag in lags:
        if lag > 0:
            # Sentiment leads return: shift sentiment backward
            s_shifted = sent_aligned.shift(-lag)
        elif lag < 0:
            # Return leads sentiment: shift return backward
            s_shifted = sent_aligned
            ret_aligned_shifted = ret_aligned.shift(lag)
            s_shifted = s_shifted
        else:
            s_shifted = sent_aligned

        if lag < 0:
            paired = pd.DataFrame({
                "s": sent_aligned,
                "r": ret_aligned.shift(-abs(lag)),
            }).dropna()
        elif lag > 0:
            paired = pd.DataFrame({
                "s": sent_aligned.shift(-lag),
                "r": ret_aligned,
            }).dropna()
        else:
            paired = pd.DataFrame({
                "s": sent_aligned,
                "r": ret_aligned,
            }).dropna()

        if len(paired) < min_obs:
            results.append({
                "lag": lag,
                "pearson_r": np.nan,
                "p_value": np.nan,
                "n_obs": len(paired),
                "significant": False,
            })
            continue

        r, p = pearsonr(paired["s"], paired["r"])
        results.append({
            "lag": lag,
            "pearson_r": r,
            "p_value": p,
            "n_obs": len(paired),
            "significant": p < 0.05,
        })

    return pd.DataFrame(results)


def find_optimal_lead(lead_lag_df: pd.DataFrame) -> Dict[str, Any]:
    """
    Trouve le lag optimal (où la corrélation est maximale en valeur absolue).
    """
    if lead_lag_df.empty or lead_lag_df["pearson_r"].isna().all():
        return {"optimal_lag": 0, "max_correlation": 0.0, "p_value": 1.0}

    valid = lead_lag_df.dropna(subset=["pearson_r"])
    if valid.empty:
        return {"optimal_lag": 0, "max_correlation": 0.0, "p_value": 1.0}

    # Cherche le maximum de la corrélation absolue parmi les lags positifs (sentiment -> prix)
    positive_lags = valid[valid["lag"] > 0]
    if positive_lags.empty:
        positive_lags = valid

    idx = positive_lags["pearson_r"].abs().idxmax()
    best = positive_lags.loc[idx]

    return {
        "optimal_lag": int(best["lag"]),
        "max_correlation": float(best["pearson_r"]),
        "p_value": float(best["p_value"]),
        "significant": bool(best["significant"]),
    }


# ─────────────────────────────────────────────────────────────
# TEST DE CAUSALITÉ DE GRANGER (simplifié)
# ─────────────────────────────────────────────────────────────

def granger_causality_ols(
    sentiment: pd.Series,
    returns: pd.Series,
    max_lag: int = 5,
    min_obs: int = 50,
) -> Dict[str, Any]:
    """
    Test de causalité de Granger simplifié via régression OLS.
    H0: le sentiment NE cause PAS les rendements au sens de Granger.

    Modèle complet:  r_t = a + sum(b_i * r_{t-i}) + sum(c_j * s_{t-j}) + e
    Modèle réduit:   r_t = a + sum(b_i * r_{t-i}) + e

    F-test sur les coefficients c_j.
    """
    try:
        from sklearn.linear_model import LinearRegression
        from scipy.stats import f as f_dist
    except ImportError:
        return {"error": "sklearn/scipy non disponible"}

    common_idx = sentiment.dropna().index.intersection(returns.dropna().index)
    if len(common_idx) < min_obs + max_lag:
        return {"error": f"Insufficient data: {len(common_idx)} observations"}

    s = sentiment.reindex(common_idx).values
    r = returns.reindex(common_idx).values
    n = len(r)

    # Construit les matrices de features
    X_restricted = np.ones((n - max_lag, 1 + max_lag))  # intercept + lags de r
    X_full = np.ones((n - max_lag, 1 + 2 * max_lag))    # + lags de s

    y = r[max_lag:]

    for i in range(n - max_lag):
        for k in range(max_lag):
            X_restricted[i, 1 + k] = r[max_lag + i - k - 1]
            X_full[i, 1 + k] = r[max_lag + i - k - 1]
            X_full[i, 1 + max_lag + k] = s[max_lag + i - k - 1]

    n_obs = len(y)

    # Modèle restreint
    reg_r = LinearRegression(fit_intercept=False).fit(X_restricted, y)
    resid_r = y - reg_r.predict(X_restricted)
    rss_r = np.sum(resid_r**2)

    # Modèle complet
    reg_f = LinearRegression(fit_intercept=False).fit(X_full, y)
    resid_f = y - reg_f.predict(X_full)
    rss_f = np.sum(resid_f**2)

    k1 = max_lag  # nb contraintes (lags de s supprimés)
    k2 = X_full.shape[1]  # nb params modèle complet
    df1 = k1
    df2 = n_obs - k2

    if df2 <= 0 or rss_f <= 0:
        return {"error": "Degrees of freedom error"}

    f_stat = ((rss_r - rss_f) / df1) / (rss_f / df2)
    p_value = 1.0 - f_dist.cdf(f_stat, df1, df2)

    return {
        "f_statistic": float(f_stat),
        "p_value": float(p_value),
        "df1": df1,
        "df2": df2,
        "granger_causes": bool(p_value < 0.05),
        "max_lag_tested": max_lag,
        "n_observations": n_obs,
        "interpretation": (
            "Le sentiment NLP précède causalement les rendements (p<0.05)"
            if p_value < 0.05
            else "Pas de causalité de Granger détectée (p>=0.05)"
        ),
    }


# ─────────────────────────────────────────────────────────────
# CORRÉLATION SMART MONEY vs MASI
# ─────────────────────────────────────────────────────────────

def analyze_smart_money_lead(
    daily_sentiment: pd.DataFrame,
    price_panel: pd.DataFrame,
    lags: range = range(0, 16),
) -> Dict[str, Any]:
    """
    Mesure si le sentiment Smart Money précède l'indice MASI par N jours.
    """
    results = {}

    if "smart_money_sentiment" not in daily_sentiment.columns:
        return {"error": "smart_money_sentiment non disponible"}

    sms = daily_sentiment.set_index("date")["smart_money_sentiment"]

    # Proxy MASI: moyenne des rendements du panel de prix
    if not price_panel.empty:
        masi_proxy = price_panel.pct_change().mean(axis=1)
    else:
        # Génère un proxy MASI synthétique
        idx = sms.index
        rng = np.random.RandomState(42)
        masi_proxy = pd.Series(
            rng.normal(0.0003, 0.008, len(idx)), index=idx, name="masi_proxy"
        )

    ll_df = compute_lead_lag_correlation(sms, masi_proxy, lags=lags)
    optimal = find_optimal_lead(ll_df)

    results["smart_money_vs_masi"] = ll_df
    results["optimal_lead_days"] = optimal["optimal_lag"]
    results["lead_correlation"] = optimal["max_correlation"]
    results["lead_significant"] = optimal.get("significant", False)

    # Granger
    granger = granger_causality_ols(sms, masi_proxy, max_lag=5)
    results["granger_smart_money_masi"] = granger

    return results


# ─────────────────────────────────────────────────────────────
# SENTIMENT MOMENTUM COMME PRÉDICTEUR
# ─────────────────────────────────────────────────────────────

def compute_sentiment_momentum_predictive_power(
    daily_sentiment: pd.DataFrame,
    price_panel: pd.DataFrame,
) -> pd.DataFrame:
    """
    Teste si le momentum du sentiment (changement sur N jours) prédit les rendements futurs.
    """
    records = []
    if price_panel.empty or daily_sentiment.empty:
        return pd.DataFrame()

    sent_idx = pd.to_datetime(daily_sentiment.set_index("date").index)
    price_returns = price_panel.pct_change()

    for window in [5, 10, 20]:
        mom_col = f"sentiment_momentum_{window}d"
        if mom_col not in daily_sentiment.columns:
            continue

        momentum = daily_sentiment.set_index("date")[mom_col].dropna()
        momentum.index = pd.to_datetime(momentum.index)

        for horizon in [5, 10, 20, 30]:
            future_ret = price_returns.mean(axis=1).shift(-horizon)
            future_ret.index = pd.to_datetime(future_ret.index)
            common = momentum.index.intersection(future_ret.index)

            if len(common) < 20:
                continue

            r, p = pearsonr(momentum.reindex(common), future_ret.reindex(common).fillna(0))
            records.append({
                "momentum_window": window,
                "return_horizon": horizon,
                "pearson_r": r,
                "p_value": p,
                "significant": p < 0.05,
                "n_obs": len(common),
            })

    return pd.DataFrame(records)


# ─────────────────────────────────────────────────────────────
# MATRICE DE CORRÉLATION COMPLÈTE
# ─────────────────────────────────────────────────────────────

def build_correlation_matrix(
    daily_sentiment: pd.DataFrame,
    price_panel: pd.DataFrame,
    fear_greed_series: Optional[pd.Series] = None,
) -> pd.DataFrame:
    """
    Construit la matrice de corrélation complète entre tous les signaux.
    """
    if daily_sentiment.empty:
        return pd.DataFrame()

    signals = daily_sentiment.set_index("date").copy()
    signals.index = pd.to_datetime(signals.index)

    if fear_greed_series is not None and not fear_greed_series.empty:
        fg = fear_greed_series.copy()
        fg.index = pd.to_datetime(fg.index)
        signals["fear_greed"] = fg.reindex(signals.index)

    if not price_panel.empty:
        avg_ret = price_panel.pct_change().mean(axis=1)
        avg_ret.index = pd.to_datetime(avg_ret.index)
        signals["avg_market_return"] = avg_ret.reindex(signals.index)

    numeric_cols = signals.select_dtypes(include=[np.number]).columns.tolist()
    if not numeric_cols:
        return pd.DataFrame()

    corr_matrix = signals[numeric_cols].corr(method="pearson")
    return corr_matrix


# ─────────────────────────────────────────────────────────────
# CORRÉLATIONS PAR TICKER
# ─────────────────────────────────────────────────────────────

def run_ticker_correlations(
    ticker_daily_sentiment: pd.DataFrame,
    price_panel: pd.DataFrame,
) -> Dict[str, Any]:
    """
    Pour chaque ticker: corrélation sentiment-prix à différents lags.
    """
    results: Dict[str, Any] = {}

    if ticker_daily_sentiment.empty or price_panel.empty:
        return results

    tickers = ticker_daily_sentiment["ticker"].unique()

    for ticker in tickers:
        if ticker not in price_panel.columns:
            continue

        t_df = ticker_daily_sentiment[ticker_daily_sentiment["ticker"] == ticker].copy()
        t_df = t_df.set_index("date").sort_index()
        t_df.index = pd.to_datetime(t_df.index)

        price_series = price_panel[ticker].dropna()
        price_series.index = pd.to_datetime(price_series.index)
        returns = price_series.pct_change().dropna()

        sentiment = t_df["sentiment_mean"].dropna()

        if len(sentiment) < MIN_OVERLAP or len(returns) < MIN_OVERLAP:
            continue

        # Lead-lag
        ll_df = compute_lead_lag_correlation(sentiment, returns, lags=LAG_RANGE)
        optimal = find_optimal_lead(ll_df)

        # Granger
        granger = granger_causality_ols(sentiment, returns, max_lag=3, min_obs=30)

        results[ticker] = {
            "lead_lag_df": ll_df,
            "optimal_lead": optimal,
            "granger": granger,
            "n_days_sentiment": len(sentiment),
            "n_days_prices": len(returns),
        }

    return results


# ─────────────────────────────────────────────────────────────
# POINT D'ENTRÉE PRINCIPAL
# ─────────────────────────────────────────────────────────────

def run_phase8(
    df: pd.DataFrame,
    stock_scores: Optional[pd.DataFrame] = None,
    member_scores: Optional[pd.DataFrame] = None,
    fear_greed_series: Optional[pd.Series] = None,
    graph_metrics: Optional[pd.DataFrame] = None,
) -> Dict[str, Any]:
    """
    Exécute la Phase 8: analyse des corrélations cross-signaux.

    Returns dict with keys:
        correlation_matrix, lead_lag_results, granger_results,
        ticker_correlations, smart_money_lead, momentum_predictive_power
    """
    logger.info("=== Phase 8: Corrélations & Lead-Lag Analysis ===")

    # 1. Chargement des données de prix
    logger.info("Chargement des données de prix...")
    price_data = load_price_data()
    logger.info(f"  {len(price_data)} tickers avec données de prix")

    # 2. Construction du panel de prix
    logger.info("Construction du panel de prix journaliers...")
    price_panel = build_price_panel(df, price_data)
    logger.info(f"  Panel: {price_panel.shape if not price_panel.empty else '(vide)'}")

    # 3. Agrégation des sentiments quotidiens
    logger.info("Agrégation des sentiments quotidiens...")
    daily_sentiment = build_daily_sentiment(df, member_scores)
    logger.info(f"  {len(daily_sentiment)} jours de données de sentiment")

    # 4. Sentiment par ticker
    logger.info("Agrégation sentiment par ticker...")
    ticker_daily = build_ticker_daily_sentiment(df)
    logger.info(f"  {len(ticker_daily)} lignes (ticker, date)")

    # 5. Matrice de corrélation globale
    logger.info("Calcul de la matrice de corrélation globale...")
    corr_matrix = build_correlation_matrix(daily_sentiment, price_panel, fear_greed_series)

    # 6. Lead-lag global (sentiment moyen vs rendement moyen du marché)
    logger.info("Analyse lead-lag globale...")
    if not daily_sentiment.empty and not price_panel.empty:
        global_sentiment = daily_sentiment.set_index("date")["sentiment_mean"]
        global_sentiment.index = pd.to_datetime(global_sentiment.index)
        market_returns = price_panel.pct_change().mean(axis=1)
        market_returns.index = pd.to_datetime(market_returns.index)
        global_ll = compute_lead_lag_correlation(global_sentiment, market_returns)
        global_optimal = find_optimal_lead(global_ll)
        global_granger = granger_causality_ols(global_sentiment, market_returns)
    else:
        global_ll = pd.DataFrame()
        global_optimal = {}
        global_granger = {"error": "Données insuffisantes"}

    # 7. Corrélations par ticker
    logger.info("Corrélations par ticker...")
    ticker_correlations = run_ticker_correlations(ticker_daily, price_panel)
    logger.info(f"  {len(ticker_correlations)} tickers analysés")

    # 8. Smart Money lead analysis
    logger.info("Analyse lead Smart Money vs MASI...")
    smart_money_lead = analyze_smart_money_lead(daily_sentiment, price_panel)

    # 9. Momentum du sentiment comme prédicteur
    logger.info("Momentum du sentiment comme prédicteur...")
    momentum_power = compute_sentiment_momentum_predictive_power(daily_sentiment, price_panel)

    # 10. Résumé des résultats Granger par ticker
    granger_results: Dict[str, Any] = {"global": global_granger}
    lead_lag_results: Dict[str, Any] = {
        "global_lead_lag": global_ll,
        "global_optimal": global_optimal,
    }

    significant_tickers = []
    for ticker, res in ticker_correlations.items():
        granger_results[ticker] = res.get("granger", {})
        lead_lag_results[ticker] = {
            "lead_lag_df": res.get("lead_lag_df", pd.DataFrame()),
            "optimal": res.get("optimal_lead", {}),
        }
        if res.get("granger", {}).get("granger_causes", False):
            significant_tickers.append(ticker)

    logger.info(f"  {len(significant_tickers)} tickers avec causalité de Granger significative")

    # Résumé
    summary = {
        "n_tickers_analyzed": len(ticker_correlations),
        "n_tickers_granger_significant": len(significant_tickers),
        "significant_tickers": significant_tickers,
        "global_optimal_lag_days": global_optimal.get("optimal_lag", 0),
        "global_max_correlation": global_optimal.get("max_correlation", 0.0),
        "smart_money_lead_days": smart_money_lead.get("optimal_lead_days", 0),
        "smart_money_lead_significant": smart_money_lead.get("lead_significant", False),
        "price_data_source": "financial_data.json + synthetic GBM",
        "total_trading_days": len(price_panel),
    }

    logger.info(f"Phase 8 terminée. Lag optimal global: {summary['global_optimal_lag_days']} jours")

    return {
        "correlation_matrix": corr_matrix,
        "lead_lag_results": lead_lag_results,
        "granger_results": granger_results,
        "ticker_correlations": ticker_correlations,
        "smart_money_lead": smart_money_lead,
        "momentum_predictive_power": momentum_power,
        "daily_sentiment": daily_sentiment,
        "ticker_daily_sentiment": ticker_daily,
        "price_panel": price_panel,
        "summary": summary,
    }


# ─────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    print("Test Phase 8: génération de données synthétiques...")

    # Données de test minimalistes
    rng = np.random.RandomState(42)
    dates = pd.date_range("2022-01-01", "2024-12-31", freq="h")
    n = len(dates)

    test_df = pd.DataFrame({
        "timestamp": dates[:5000],
        "author": [f"user_{i % 50}" for i in range(5000)],
        "message_text": ["test message"] * 5000,
        "sentiment": rng.choice(["positif", "negatif", "neutre"], 5000),
        "signal": rng.choice(["ACHETER", "VENTE", "DOUTE", None], 5000),
        "tickers_mentioned": [
            rng.choice([["IAM"], ["ATW"], ["BCP"], [], ["MNG"]], replace=True)
            for _ in range(5000)
        ],
        "message_type": ["text"] * 5000,
    })

    results = run_phase8(test_df)

    print("\n=== Résultats Phase 8 ===")
    print(f"Matrice corrélation: {results['correlation_matrix'].shape}")
    print(f"Tickers analysés: {results['summary']['n_tickers_analyzed']}")
    print(f"Lag optimal global: {results['summary']['global_optimal_lag_days']} jours")
    print(f"Corrélation max: {results['summary']['global_max_correlation']:.4f}")
    print(f"Smart Money lead: {results['summary']['smart_money_lead_days']} jours")
    if not results["momentum_predictive_power"].empty:
        print(f"Momentum power:\n{results['momentum_predictive_power'].head()}")
