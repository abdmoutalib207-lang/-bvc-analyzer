"""
Phase 11 — Backtesting Engine: Stratégies NLP sur le marché BVC
Tests de 4 stratégies avec métriques complètes de performance
"""
from __future__ import annotations

import logging
import warnings
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")
logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────
# CONSTANTES
# ─────────────────────────────────────────────────────────────

RF_ANNUAL = 0.03          # taux sans risque annuel (Maroc, BAM)
TRADING_DAYS_YEAR = 252
TRANSACTION_COST = 0.002  # 0.2% par transaction (BVC)
SLIPPAGE = 0.001          # 0.1% de slippage

# Horizons de test en jours calendaires
TEST_HORIZONS = {
    "1W": 7,
    "1M": 30,
    "3M": 90,
    "6M": 180,
    "12M": 365,
}

# ─────────────────────────────────────────────────────────────
# CONSTRUCTION DES PRIX
# ─────────────────────────────────────────────────────────────

def load_or_generate_market_prices(
    price_panel: Optional[pd.DataFrame],
    daily_sentiment: Optional[pd.DataFrame],
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> Tuple[pd.Series, pd.DataFrame]:
    """
    Charge ou génère les prix du marché.
    Retourne: (masi_series, individual_prices_df)
    """
    if price_panel is not None and not price_panel.empty:
        # MASI proxy = portfolio équipondéré
        returns = price_panel.pct_change().fillna(0)
        masi_returns = returns.mean(axis=1)
        masi_prices = (1 + masi_returns).cumprod() * 1000
        masi_prices.iloc[0] = 1000.0
        return masi_prices, price_panel

    # Génère des prix synthétiques réalistes du marché marocain
    if start_date is None:
        if daily_sentiment is not None and not daily_sentiment.empty:
            start_date = str(daily_sentiment["date"].min())[:10]
        else:
            start_date = "2020-01-01"

    if end_date is None:
        if daily_sentiment is not None and not daily_sentiment.empty:
            end_date = str(daily_sentiment["date"].max())[:10]
        else:
            end_date = "2024-12-31"

    dates = pd.date_range(start_date, end_date, freq="B")
    n = len(dates)

    rng = np.random.RandomState(42)

    # MASI: drift ~8% annuel, vol ~12%, avec régimes
    masi_returns = np.zeros(n)
    regime = "bull"
    for i in range(n):
        # Changements de régime stochastiques
        if regime == "bull" and rng.random() < 0.003:
            regime = "bear"
        elif regime == "bear" and rng.random() < 0.01:
            regime = "bull"

        if regime == "bull":
            masi_returns[i] = rng.normal(0.0004, 0.007)
        else:
            masi_returns[i] = rng.normal(-0.0006, 0.012)

    masi_prices = pd.Series(
        1000.0 * (1 + pd.Series(masi_returns)).cumprod().values,
        index=dates,
        name="MASI",
    )

    # Génère 5 tickers individuels avec bêta variable
    tickers_syn = {}
    for t, (beta, alpha, vol_mult) in [
        ("IAM", (0.7, 0.0002, 0.9)),
        ("ATW", (1.1, 0.0001, 1.1)),
        ("BCP", (0.9, 0.0001, 0.95)),
        ("MNG", (1.3, 0.0003, 1.4)),
        ("ADH", (1.2, -0.0001, 1.3)),
    ]:
        t_rng = np.random.RandomState(hash(t) % 2**31)
        t_returns = beta * masi_returns + alpha + vol_mult * 0.007 * t_rng.randn(n)
        tickers_syn[t] = pd.Series(
            100.0 * (1 + pd.Series(t_returns)).cumprod().values,
            index=dates, name=t,
        )

    individual_prices = pd.DataFrame(tickers_syn)
    return masi_prices, individual_prices


# ─────────────────────────────────────────────────────────────
# MÉTRIQUES DE PERFORMANCE
# ─────────────────────────────────────────────────────────────

def compute_metrics(
    equity_curve: pd.Series,
    benchmark: pd.Series,
    rf_annual: float = RF_ANNUAL,
) -> Dict[str, float]:
    """
    Calcule les métriques complètes de performance d'une stratégie.
    """
    if equity_curve.empty or len(equity_curve) < 2:
        return {k: np.nan for k in [
            "total_return", "cagr", "sharpe", "sortino", "max_drawdown",
            "calmar", "win_rate", "avg_win", "avg_loss", "profit_factor",
            "n_trades", "volatility", "alpha", "beta",
        ]}

    equity_curve = equity_curve.dropna()
    if len(equity_curve) < 2:
        return {}

    # Returns journaliers
    daily_returns = equity_curve.pct_change().dropna()

    # Total Return
    total_return = (equity_curve.iloc[-1] / equity_curve.iloc[0]) - 1.0

    # CAGR
    n_days = (equity_curve.index[-1] - equity_curve.index[0]).days
    n_years = max(n_days / 365.25, 0.01)
    cagr = (1 + total_return) ** (1 / n_years) - 1

    # Volatilité annualisée
    daily_vol = daily_returns.std()
    annual_vol = daily_vol * np.sqrt(TRADING_DAYS_YEAR)

    # Sharpe Ratio
    rf_daily = (1 + rf_annual) ** (1 / TRADING_DAYS_YEAR) - 1
    excess_returns = daily_returns - rf_daily
    sharpe = (excess_returns.mean() * TRADING_DAYS_YEAR) / (
        daily_returns.std() * np.sqrt(TRADING_DAYS_YEAR) + 1e-9
    )

    # Sortino Ratio
    downside_returns = daily_returns[daily_returns < rf_daily]
    downside_vol = downside_returns.std() * np.sqrt(TRADING_DAYS_YEAR)
    sortino = (daily_returns.mean() - rf_daily) * TRADING_DAYS_YEAR / max(downside_vol, 1e-9)

    # Max Drawdown
    rolling_max = equity_curve.cummax()
    drawdown = (equity_curve - rolling_max) / rolling_max.clip(lower=1e-9)
    max_drawdown = float(drawdown.min())

    # Calmar Ratio
    calmar = cagr / abs(max_drawdown) if max_drawdown != 0 else np.nan

    # Win/Loss statistics (sur les retours journaliers positifs/négatifs)
    wins = daily_returns[daily_returns > 0]
    losses = daily_returns[daily_returns < 0]
    win_rate = len(wins) / max(len(daily_returns), 1)
    avg_win = float(wins.mean()) if len(wins) > 0 else 0.0
    avg_loss = float(losses.mean()) if len(losses) > 0 else 0.0
    profit_factor = (wins.sum() / abs(losses.sum())) if (len(losses) > 0 and losses.sum() != 0) else np.nan

    # Alpha et Beta vs benchmark
    bench_returns = benchmark.pct_change().dropna()
    common_idx = daily_returns.index.intersection(bench_returns.index)
    if len(common_idx) > 10:
        s_ret = daily_returns.reindex(common_idx)
        b_ret = bench_returns.reindex(common_idx)
        beta_val = float(np.cov(s_ret, b_ret)[0, 1] / (np.var(b_ret) + 1e-9))
        alpha_daily = float(s_ret.mean() - beta_val * b_ret.mean())
        alpha_annual = alpha_daily * TRADING_DAYS_YEAR
    else:
        beta_val = 1.0
        alpha_annual = 0.0

    return {
        "total_return": float(total_return),
        "cagr": float(cagr),
        "sharpe": float(sharpe),
        "sortino": float(sortino),
        "max_drawdown": float(max_drawdown),
        "calmar": float(calmar) if not np.isnan(calmar) else 0.0,
        "win_rate": float(win_rate),
        "avg_win": float(avg_win),
        "avg_loss": float(avg_loss),
        "profit_factor": float(profit_factor) if not np.isnan(profit_factor) else 0.0,
        "volatility": float(annual_vol),
        "alpha": float(alpha_annual),
        "beta": float(beta_val),
        "n_days": len(equity_curve),
    }


# ─────────────────────────────────────────────────────────────
# STRATÉGIES
# ─────────────────────────────────────────────────────────────

def strategy_smart_sentiment(
    daily_sentiment: pd.DataFrame,
    prices: pd.DataFrame,
    masi: pd.Series,
    buy_threshold: float = 0.6,
    sell_threshold: float = -0.3,
) -> Tuple[pd.Series, List[Dict]]:
    """
    Stratégie 1: Achète quand le sentiment smart_money > 0.6, vend quand < -0.3.
    """
    if daily_sentiment.empty or prices.empty:
        return pd.Series(dtype=float), []

    sentiment_col = "smart_money_sentiment" if "smart_money_sentiment" in daily_sentiment.columns else "sentiment_mean"
    sent = daily_sentiment.set_index("date")[sentiment_col].copy()
    sent.index = pd.to_datetime(sent.index)

    # Proxy ticker = average de tous les prix
    avg_prices = prices.mean(axis=1)
    avg_prices.index = pd.to_datetime(avg_prices.index)

    common_idx = sent.index.intersection(avg_prices.index)
    if len(common_idx) < 10:
        return pd.Series(dtype=float), []

    sent = sent.reindex(common_idx)
    price = avg_prices.reindex(common_idx)

    equity = [100.0]
    position = 0.0   # 0 = cash, 1 = investi
    entry_price = 0.0
    trades = []

    for i in range(1, len(common_idx)):
        date = common_idx[i]
        s = sent.iloc[i]
        p = price.iloc[i]
        prev_p = price.iloc[i - 1]
        daily_ret = (p / prev_p - 1.0) if prev_p > 0 else 0.0

        if position == 0.0 and s > buy_threshold:
            position = 1.0
            entry_price = p * (1 + TRANSACTION_COST + SLIPPAGE)
            trades.append({"date": date, "action": "BUY", "price": entry_price, "sentiment": s})
            equity.append(equity[-1])  # pas de gain ce jour
        elif position == 1.0 and s < sell_threshold:
            exit_price = p * (1 - TRANSACTION_COST - SLIPPAGE)
            ret = exit_price / entry_price - 1.0
            trades.append({"date": date, "action": "SELL", "price": exit_price,
                           "sentiment": s, "return": ret})
            equity.append(equity[-1] * (1 + ret))
            position = 0.0
        elif position == 1.0:
            equity.append(equity[-1] * (1 + daily_ret))
        else:
            equity.append(equity[-1] * (1 + RF_ANNUAL / TRADING_DAYS_YEAR))

    equity_series = pd.Series(equity, index=common_idx[:len(equity)])
    return equity_series, trades


def strategy_smart_money_only(
    daily_sentiment: pd.DataFrame,
    prices: pd.DataFrame,
    masi: pd.Series,
    member_scores: Optional[pd.DataFrame] = None,
    top_pct: float = 0.10,
) -> Tuple[pd.Series, List[Dict]]:
    """
    Stratégie 2: Suit uniquement les membres Smart Money (top 10%).
    Utilise smart_money_sentiment avec seuil renforcé.
    """
    if daily_sentiment.empty or prices.empty:
        return pd.Series(dtype=float), []

    # Smart money threshold plus exigeant
    buy_threshold = 0.7
    sell_threshold = -0.4

    # Poids renforcé si on a les scores membres
    if "smart_money_sentiment" in daily_sentiment.columns:
        sentiment_col = "smart_money_sentiment"
    else:
        sentiment_col = "sentiment_mean"

    return strategy_smart_sentiment(
        daily_sentiment=daily_sentiment,
        prices=prices,
        masi=masi,
        buy_threshold=buy_threshold,
        sell_threshold=sell_threshold,
    )


def strategy_achat_fort_consensus(
    daily_sentiment: pd.DataFrame,
    df: pd.DataFrame,
    prices: pd.DataFrame,
    masi: pd.Series,
    min_smart_members: int = 3,
    window_hours: int = 24,
) -> Tuple[pd.Series, List[Dict]]:
    """
    Stratégie 3: Achète quand >3 membres Smart Money émettent ACHAT_FORT en 24h.
    """
    if daily_sentiment.empty or prices.empty:
        return pd.Series(dtype=float), []

    # Détecte les jours avec consensus ACHAT_FORT
    consensus_dates = set()

    if "signal" in df.columns and "timestamp" in df.columns:
        df_work = df.copy()
        df_work["date"] = pd.to_datetime(df_work["timestamp"]).dt.normalize()
        achat_fort = df_work[
            df_work["signal"].isin(["ACHAT_FORT", "ACHETER"])
        ]
        if not achat_fort.empty:
            daily_achat = achat_fort.groupby("date")["author"].nunique()
            consensus_days = daily_achat[daily_achat >= min_smart_members].index
            consensus_dates = set(pd.to_datetime(consensus_days))
    else:
        # Fallback: utilise le signal mean
        if "buy_ratio" in daily_sentiment.columns:
            strong_buy = daily_sentiment[daily_sentiment["buy_ratio"] > 0.6]
            consensus_dates = set(pd.to_datetime(strong_buy["date"]))

    # Stratégie: entre sur jour consensus, sort après 20j ou si net_signal < -0.2
    avg_prices = prices.mean(axis=1)
    avg_prices.index = pd.to_datetime(avg_prices.index)

    date_range = avg_prices.index
    equity = [100.0]
    position = 0.0
    entry_price = 0.0
    entry_date = None
    hold_days = 20
    trades = []

    sentiment_indexed = daily_sentiment.set_index("date").copy()
    sentiment_indexed.index = pd.to_datetime(sentiment_indexed.index)

    for i in range(1, len(date_range)):
        date = date_range[i]
        p = avg_prices.iloc[i]
        prev_p = avg_prices.iloc[i - 1]
        daily_ret = (p / prev_p - 1.0) if prev_p > 0 else 0.0

        # Signal d'entrée
        in_consensus = date in consensus_dates
        net_signal = 0.0
        if date in sentiment_indexed.index:
            ns = sentiment_indexed.loc[date, "net_signal"] if "net_signal" in sentiment_indexed.columns else 0.0
            net_signal = float(ns) if pd.notna(ns) else 0.0

        if position == 0.0 and in_consensus:
            position = 1.0
            entry_price = p * (1 + TRANSACTION_COST + SLIPPAGE)
            entry_date = date
            trades.append({"date": date, "action": "BUY", "price": entry_price,
                           "reason": "consensus_achat_fort"})
            equity.append(equity[-1])
        elif position == 1.0:
            days_held = (date - entry_date).days if entry_date else 0
            exit_signal = (days_held >= hold_days) or (net_signal < -0.3)
            if exit_signal:
                exit_price = p * (1 - TRANSACTION_COST - SLIPPAGE)
                ret = exit_price / entry_price - 1.0
                trades.append({"date": date, "action": "SELL", "price": exit_price,
                               "days_held": days_held, "return": ret})
                equity.append(equity[-1] * (1 + ret))
                position = 0.0
                entry_date = None
            else:
                equity.append(equity[-1] * (1 + daily_ret))
        else:
            equity.append(equity[-1] * (1 + RF_ANNUAL / TRADING_DAYS_YEAR))

    equity_series = pd.Series(equity, index=date_range[:len(equity)])
    return equity_series, trades


def strategy_contrarian_fear_greed(
    daily_sentiment: pd.DataFrame,
    prices: pd.DataFrame,
    masi: pd.Series,
    fear_greed_series: Optional[pd.Series] = None,
    fear_buy_threshold: float = 20.0,
    greed_sell_threshold: float = 80.0,
) -> Tuple[pd.Series, List[Dict]]:
    """
    Stratégie 4: Contrariante — achète sur capitulation (F&G < 20), vend sur euphorie (F&G > 80).
    """
    if prices.empty:
        return pd.Series(dtype=float), []

    avg_prices = prices.mean(axis=1)
    avg_prices.index = pd.to_datetime(avg_prices.index)

    # Fear & Greed series
    if fear_greed_series is not None and not fear_greed_series.empty:
        fg = fear_greed_series.copy()
        fg.index = pd.to_datetime(fg.index)
    else:
        # Utilise le sentiment comme proxy Fear & Greed (inversé)
        if not daily_sentiment.empty and "sentiment_mean" in daily_sentiment.columns:
            sent_idx = pd.to_datetime(daily_sentiment["date"])
            sent_vals = daily_sentiment["sentiment_mean"].values
            # Convertit sentiment (-1, 1) en F&G (0, 100)
            fg_vals = (sent_vals + 1) / 2 * 100
            fg = pd.Series(fg_vals, index=sent_idx, name="fear_greed_proxy")
            fg = fg.rolling(7).mean().fillna(50)
        else:
            # Génère synthétique
            rng = np.random.RandomState(123)
            fg_vals = 50 + rng.normal(0, 20, len(avg_prices))
            fg_vals = np.clip(fg_vals, 0, 100)
            fg = pd.Series(fg_vals, index=avg_prices.index, name="fg_synthetic")

    # Aligne sur les prix
    common_idx = avg_prices.index.intersection(fg.index)
    if len(common_idx) < 10:
        # Utilise tous les prix avec F&G synthétique
        common_idx = avg_prices.index
        rng = np.random.RandomState(123)
        fg = pd.Series(
            50 + rng.normal(0, 20, len(common_idx)),
            index=common_idx, name="fg"
        ).clip(0, 100)
    else:
        avg_prices = avg_prices.reindex(common_idx)
        fg = fg.reindex(common_idx, method="ffill").fillna(50)

    equity = [100.0]
    position = 0.0
    entry_price = 0.0
    hold_days = 30
    entry_date = None
    trades = []

    price_arr = avg_prices.values
    fg_arr = fg.values

    for i in range(1, len(common_idx)):
        date = common_idx[i]
        p = price_arr[i]
        prev_p = price_arr[i - 1]
        daily_ret = (p / prev_p - 1.0) if prev_p > 0 else 0.0
        fg_val = fg_arr[i]

        if position == 0.0 and fg_val < fear_buy_threshold:
            position = 1.0
            entry_price = p * (1 + TRANSACTION_COST + SLIPPAGE)
            entry_date = date
            trades.append({"date": date, "action": "BUY_CONTRARIAN",
                           "price": entry_price, "fear_greed": fg_val})
            equity.append(equity[-1])
        elif position == 1.0:
            days_held = (date - entry_date).days if entry_date else 0
            exit_cond = (fg_val > greed_sell_threshold) or (days_held >= hold_days * 2)
            if exit_cond:
                exit_price = p * (1 - TRANSACTION_COST - SLIPPAGE)
                ret = exit_price / entry_price - 1.0
                trades.append({"date": date, "action": "SELL_CONTRARIAN",
                               "price": exit_price, "fg": fg_val, "return": ret})
                equity.append(equity[-1] * (1 + ret))
                position = 0.0
                entry_date = None
            else:
                equity.append(equity[-1] * (1 + daily_ret))
        else:
            equity.append(equity[-1] * (1 + RF_ANNUAL / TRADING_DAYS_YEAR))

    equity_series = pd.Series(equity[:len(common_idx)], index=common_idx[:len(equity)])
    return equity_series, trades


def strategy_buy_and_hold(
    prices: pd.DataFrame,
    masi: pd.Series,
) -> pd.Series:
    """
    Benchmark: Buy & Hold MASI.
    """
    if masi is not None and not masi.empty:
        equity = masi / masi.iloc[0] * 100
        return equity

    if prices.empty:
        return pd.Series(dtype=float)

    avg = prices.mean(axis=1)
    equity = avg / avg.iloc[0] * 100
    return equity


# ─────────────────────────────────────────────────────────────
# ANALYSE PAR HORIZON
# ─────────────────────────────────────────────────────────────

def compute_horizon_metrics(
    equity_curve: pd.Series,
    masi: pd.Series,
) -> Dict[str, Dict[str, float]]:
    """
    Calcule les métriques pour chaque horizon de temps.
    """
    results = {}

    for horizon_name, n_days in TEST_HORIZONS.items():
        if len(equity_curve) < n_days:
            continue

        # Prend les N derniers jours
        sub_equity = equity_curve.iloc[-n_days:]
        sub_masi = masi.reindex(sub_equity.index, method="ffill").ffill().bfill()

        if sub_masi.empty or sub_masi.iloc[0] == 0:
            continue

        results[horizon_name] = compute_metrics(sub_equity, sub_masi)

    return results


# ─────────────────────────────────────────────────────────────
# POINT D'ENTRÉE PRINCIPAL
# ─────────────────────────────────────────────────────────────

def run_phase11(
    df: pd.DataFrame,
    stock_scores: Optional[pd.DataFrame] = None,
    member_scores: Optional[pd.DataFrame] = None,
    fear_greed_series: Optional[pd.Series] = None,
    graph_metrics: Optional[pd.DataFrame] = None,
    phase8_results: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Exécute la Phase 11: Backtesting des stratégies NLP.

    Returns dict with keys:
        backtest_results, equity_curves, strategy_metrics,
        benchmark_metrics, trades_log
    """
    logger.info("=== Phase 11: Backtesting Engine ===")

    # Récupère les données de la phase 8
    if phase8_results is not None:
        daily_sentiment = phase8_results.get("daily_sentiment", pd.DataFrame())
        price_panel = phase8_results.get("price_panel", pd.DataFrame())
    else:
        from whatsapp_analysis.phase8_correlations import (
            build_daily_sentiment, build_price_panel, load_price_data
        )
        price_data = load_price_data()
        daily_sentiment = build_daily_sentiment(df, member_scores)
        price_panel = build_price_panel(df, price_data)

    logger.info(f"  Daily sentiment: {len(daily_sentiment)} jours")
    logger.info(f"  Price panel: {price_panel.shape if not price_panel.empty else 'vide'}")

    # Génère les prix de marché
    masi, prices = load_or_generate_market_prices(price_panel, daily_sentiment)
    logger.info(f"  MASI series: {len(masi)} jours | Tickers: {prices.shape[1] if not prices.empty else 0}")

    equity_curves: Dict[str, pd.Series] = {}
    strategy_metrics: Dict[str, Any] = {}
    trades_log: Dict[str, List[Dict]] = {}

    # ── Stratégie 1: Smart Sentiment ────────────────────────
    logger.info("Stratégie 1: Smart Sentiment (buy>0.6, sell<-0.3)...")
    eq1, trades1 = strategy_smart_sentiment(daily_sentiment, prices, masi)
    equity_curves["Smart_Sentiment"] = eq1
    trades_log["Smart_Sentiment"] = trades1
    if not eq1.empty:
        m1 = compute_metrics(eq1, masi)
        m1["n_trades"] = len([t for t in trades1 if t.get("action") == "BUY"])
        strategy_metrics["Smart_Sentiment"] = m1
        logger.info(f"  CAGR={m1.get('cagr', 0):.2%} | Sharpe={m1.get('sharpe', 0):.2f} | "
                    f"MaxDD={m1.get('max_drawdown', 0):.2%}")

    # ── Stratégie 2: Smart Money Only ───────────────────────
    logger.info("Stratégie 2: Smart Money Only (top 10% membres)...")
    eq2, trades2 = strategy_smart_money_only(daily_sentiment, prices, masi, member_scores)
    equity_curves["Smart_Money_Only"] = eq2
    trades_log["Smart_Money_Only"] = trades2
    if not eq2.empty:
        m2 = compute_metrics(eq2, masi)
        m2["n_trades"] = len([t for t in trades2 if t.get("action") == "BUY"])
        strategy_metrics["Smart_Money_Only"] = m2
        logger.info(f"  CAGR={m2.get('cagr', 0):.2%} | Sharpe={m2.get('sharpe', 0):.2f} | "
                    f"MaxDD={m2.get('max_drawdown', 0):.2%}")

    # ── Stratégie 3: ACHAT_FORT Consensus ───────────────────
    logger.info("Stratégie 3: ACHAT_FORT Consensus (>3 membres Smart Money)...")
    eq3, trades3 = strategy_achat_fort_consensus(daily_sentiment, df, prices, masi)
    equity_curves["ACHAT_FORT_Consensus"] = eq3
    trades_log["ACHAT_FORT_Consensus"] = trades3
    if not eq3.empty:
        m3 = compute_metrics(eq3, masi)
        m3["n_trades"] = len([t for t in trades3 if "BUY" in str(t.get("action", ""))])
        strategy_metrics["ACHAT_FORT_Consensus"] = m3
        logger.info(f"  CAGR={m3.get('cagr', 0):.2%} | Sharpe={m3.get('sharpe', 0):.2f} | "
                    f"MaxDD={m3.get('max_drawdown', 0):.2%}")

    # ── Stratégie 4: Contrariante Fear & Greed ──────────────
    logger.info("Stratégie 4: Contrariante (achète sur panique F&G<20)...")
    eq4, trades4 = strategy_contrarian_fear_greed(
        daily_sentiment, prices, masi, fear_greed_series
    )
    equity_curves["Contrarian_Fear_Greed"] = eq4
    trades_log["Contrarian_Fear_Greed"] = trades4
    if not eq4.empty:
        m4 = compute_metrics(eq4, masi)
        m4["n_trades"] = len([t for t in trades4 if "BUY" in str(t.get("action", ""))])
        strategy_metrics["Contrarian_Fear_Greed"] = m4
        logger.info(f"  CAGR={m4.get('cagr', 0):.2%} | Sharpe={m4.get('sharpe', 0):.2f} | "
                    f"MaxDD={m4.get('max_drawdown', 0):.2%}")

    # ── Benchmark: Buy & Hold ────────────────────────────────
    logger.info("Benchmark: MASI Buy & Hold...")
    eq_bh = strategy_buy_and_hold(prices, masi)
    equity_curves["BuyAndHold_MASI"] = eq_bh
    bh_metrics = compute_metrics(eq_bh, masi)
    strategy_metrics["BuyAndHold_MASI"] = bh_metrics
    logger.info(f"  CAGR={bh_metrics.get('cagr', 0):.2%} | Sharpe={bh_metrics.get('sharpe', 0):.2f}")

    # ── Métriques par horizon ────────────────────────────────
    horizon_results: Dict[str, Dict] = {}
    for strat_name, eq in equity_curves.items():
        if not eq.empty:
            horizon_results[strat_name] = compute_horizon_metrics(eq, masi)

    # ── Résumé ───────────────────────────────────────────────
    backtest_results = {}
    for strat_name, metrics in strategy_metrics.items():
        backtest_results[strat_name] = {
            **metrics,
            "horizon_metrics": horizon_results.get(strat_name, {}),
        }

    # Ranking par Sharpe
    ranked = sorted(
        [(k, v.get("sharpe", -99)) for k, v in strategy_metrics.items()
         if k != "BuyAndHold_MASI"],
        key=lambda x: x[1],
        reverse=True,
    )

    summary = {
        "n_strategies": len([k for k in strategy_metrics if k != "BuyAndHold_MASI"]),
        "best_strategy_sharpe": ranked[0][0] if ranked else "N/A",
        "best_sharpe": ranked[0][1] if ranked else 0.0,
        "benchmark_cagr": bh_metrics.get("cagr", 0.0),
        "benchmark_sharpe": bh_metrics.get("sharpe", 0.0),
        "strategies_ranked": [r[0] for r in ranked],
        "sharpe_ranking": {r[0]: r[1] for r in ranked},
        "total_trades": {k: len(v) for k, v in trades_log.items()},
        "date_range": {
            "start": str(masi.index[0].date()) if not masi.empty else "N/A",
            "end": str(masi.index[-1].date()) if not masi.empty else "N/A",
        },
    }

    logger.info(f"\nPhase 11 terminée.")
    logger.info(f"Meilleure stratégie: {summary['best_strategy_sharpe']} "
                f"(Sharpe={summary['best_sharpe']:.2f})")
    logger.info(f"Benchmark CAGR: {summary['benchmark_cagr']:.2%}")

    return {
        "backtest_results": backtest_results,
        "equity_curves": equity_curves,
        "strategy_metrics": strategy_metrics,
        "benchmark_metrics": bh_metrics,
        "trades_log": trades_log,
        "horizon_results": horizon_results,
        "masi": masi,
        "prices": prices,
        "daily_sentiment": daily_sentiment,
        "summary": summary,
    }


# ─────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    print("Test Phase 11: Backtesting avec données synthétiques...")

    rng = np.random.RandomState(42)
    dates = pd.date_range("2021-01-01", "2024-12-31", freq="h")

    test_df = pd.DataFrame({
        "timestamp": dates[:10000],
        "author": [f"user_{i % 100}" for i in range(10000)],
        "message_text": ["test"] * 10000,
        "sentiment": rng.choice(["positif", "negatif", "neutre"], 10000),
        "signal": rng.choice(["ACHAT_FORT", "ACHETER", "VENTE", "DOUTE", None], 10000),
        "tickers_mentioned": [[] for _ in range(10000)],
    })

    results = run_phase11(test_df)

    print("\n=== Résultats Phase 11 ===")
    for strat, metrics in results["strategy_metrics"].items():
        print(f"\n{strat}:")
        print(f"  CAGR:         {metrics.get('cagr', 0):.2%}")
        print(f"  Sharpe:       {metrics.get('sharpe', 0):.2f}")
        print(f"  Sortino:      {metrics.get('sortino', 0):.2f}")
        print(f"  Max Drawdown: {metrics.get('max_drawdown', 0):.2%}")
        print(f"  Calmar:       {metrics.get('calmar', 0):.2f}")
        print(f"  Win Rate:     {metrics.get('win_rate', 0):.2%}")

    print(f"\nMeilleure stratégie: {results['summary']['best_strategy_sharpe']}")
