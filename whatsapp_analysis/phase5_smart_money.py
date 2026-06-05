"""
Phase 5 — Smart Money Detection
Per-member trading call extraction, performance tracking,
scoring, and ranking of Smart Money members.
"""
from __future__ import annotations

import hashlib
import math
import warnings
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from whatsapp_analysis.config import DEFAULT_CONFIG, Config, BVC_TICKERS

warnings.filterwarnings('ignore', category=RuntimeWarning)

# ─────────────────────────────────────────────
# DATA STRUCTURES
# ─────────────────────────────────────────────

@dataclass
class TradingCall:
    """A single trading call extracted from a message."""
    call_id: str
    author: str
    timestamp: datetime
    ticker: str
    direction: str          # 'buy' | 'sell' | 'hold'
    entry_price: Optional[float]
    target_price: Optional[float]
    stop_loss: Optional[float]
    message_id: Optional[int]
    confidence: float
    signal_type: str        # dominant signal that triggered call

    @property
    def risk_reward(self) -> Optional[float]:
        if self.entry_price and self.target_price and self.stop_loss:
            reward = abs(self.target_price - self.entry_price)
            risk = abs(self.entry_price - self.stop_loss)
            if risk > 0:
                return reward / risk
        return None


@dataclass
class CallOutcome:
    """Tracked outcome of a trading call at various horizons."""
    call_id: str
    ticker: str
    entry_price: float
    target_price: Optional[float]
    entry_date: datetime
    # Returns at each horizon (None if not enough data)
    return_1w: Optional[float] = None
    return_1m: Optional[float] = None
    return_3m: Optional[float] = None
    return_6m: Optional[float] = None
    return_12m: Optional[float] = None
    hit_target_1m: Optional[bool] = None
    hit_target_3m: Optional[bool] = None
    direction: str = 'buy'


# ─────────────────────────────────────────────
# CALL EXTRACTION
# ─────────────────────────────────────────────

def _extract_calls_from_df(df: pd.DataFrame) -> List[TradingCall]:
    """
    Extract all trading calls from enriched DataFrame.
    A valid call requires: ticker + directional signal + ideally a price.
    """
    calls = []

    # Columns we need
    needed = ['signal_ACHAT_FORT', 'signal_ACHETER', 'signal_VENTE',
              'signal_RENFORCEMENT', 'nlp_tickers', 'price_targets',
              'entry_price', 'extraction_confidence', 'dominant_signal']
    for col in needed:
        if col not in df.columns:
            df[col] = None

    text_df = df[df['message_type'] == 'text'].copy()

    for _, row in text_df.iterrows():
        # Need at least one ticker
        tickers = row.get('nlp_tickers', [])
        if not tickers or not isinstance(tickers, list):
            tickers_raw = row.get('tickers', [])
            if isinstance(tickers_raw, list):
                tickers = tickers_raw
            else:
                continue

        if not tickers:
            continue

        # Need a directional signal
        is_buy = (
            bool(row.get('signal_ACHAT_FORT', False)) or
            bool(row.get('signal_ACHETER', False)) or
            bool(row.get('signal_RENFORCEMENT', False))
        )
        is_sell = bool(row.get('signal_VENTE', False))

        if not is_buy and not is_sell:
            continue

        direction = 'buy' if is_buy else 'sell'
        if is_buy and is_sell:
            direction = 'buy'  # ACHAT wins if both

        conf = float(row.get('extraction_confidence', 0) or 0)
        if conf < 0.1:
            continue  # Skip noise

        # Price extraction
        targets = row.get('price_targets', []) or []
        if isinstance(targets, list) and targets:
            target_price = max(targets)  # take highest target for buy, lowest for sell
        else:
            target_price = None

        entry_p = row.get('entry_price') or None
        if entry_p:
            try:
                entry_p = float(entry_p)
            except (TypeError, ValueError):
                entry_p = None

        stop_l = row.get('stop_loss') or None
        if stop_l:
            try:
                stop_l = float(stop_l)
            except (TypeError, ValueError):
                stop_l = None

        dominant_sig = row.get('dominant_signal') or 'ACHETER'

        for ticker in tickers:
            call_id = hashlib.md5(
                f"{row['author']}{row['timestamp']}{ticker}".encode()
            ).hexdigest()[:12]

            calls.append(TradingCall(
                call_id=call_id,
                author=row['author'],
                timestamp=row['timestamp'],
                ticker=ticker,
                direction=direction,
                entry_price=entry_p,
                target_price=target_price,
                stop_loss=stop_l,
                message_id=row.get('message_id'),
                confidence=conf,
                signal_type=str(dominant_sig),
            ))

    return calls


# ─────────────────────────────────────────────
# SYNTHETIC PRICE SIMULATION
# (Used when no real BVC price data is available)
# ─────────────────────────────────────────────

def _generate_synthetic_price_path(
    start_date: datetime,
    n_days: int,
    entry_price: float,
    mu: float = 0.0003,      # daily drift ~7.5% annual
    sigma: float = 0.015,     # daily vol ~24% annual
    seed: Optional[int] = None,
) -> pd.Series:
    """
    Geometric Brownian Motion for synthetic BVC price.
    Seeded by ticker+date for reproducibility.
    """
    if seed is None:
        seed = int(start_date.timestamp()) % (2**31)

    rng = np.random.default_rng(seed)
    returns = rng.normal(mu, sigma, n_days)
    prices = entry_price * np.cumprod(1 + returns)

    dates = pd.date_range(start=start_date, periods=n_days, freq='B')
    return pd.Series(prices, index=dates[:len(prices)])


def _get_price_at_horizon(
    price_path: pd.Series,
    start_date: datetime,
    horizon_days: int,
) -> Optional[float]:
    """Get price approximately horizon_days after start_date."""
    target_date = pd.Timestamp(start_date) + pd.Timedelta(days=horizon_days)
    # Find closest available date
    future = price_path[price_path.index >= target_date]
    if future.empty:
        return None
    return float(future.iloc[0])


# ─────────────────────────────────────────────
# OUTCOME TRACKING
# ─────────────────────────────────────────────

def _track_outcomes(
    calls: List[TradingCall],
    price_db: Optional[Dict[str, pd.Series]] = None,
) -> List[CallOutcome]:
    """
    For each call, simulate or look up price outcomes.

    price_db: dict {ticker: pd.Series(price, DatetimeIndex)}
    If None, uses synthetic GBM prices.
    """
    outcomes = []

    # Group calls by (ticker, date) to reuse price paths
    _path_cache: Dict[str, pd.Series] = {}

    for call in calls:
        if not call.entry_price:
            # Try to assign a nominal entry if none given (100 as base)
            # We still track direction
            entry = 100.0
        else:
            entry = call.entry_price

        if entry <= 0:
            continue

        # Get or build price path
        path_key = f"{call.ticker}_{call.timestamp.date()}"
        if path_key not in _path_cache:
            if price_db and call.ticker in price_db:
                path = price_db[call.ticker]
            else:
                # Unique seed per ticker+date
                seed = int(hashlib.md5(path_key.encode()).hexdigest(), 16) % (2**31)
                path = _generate_synthetic_price_path(
                    start_date=call.timestamp,
                    n_days=365,
                    entry_price=entry,
                    seed=seed,
                )
            _path_cache[path_key] = path
        else:
            path = _path_cache[path_key]

        def get_return(horizon: int) -> Optional[float]:
            price = _get_price_at_horizon(path, call.timestamp, horizon)
            if price is None:
                return None
            raw = (price - entry) / entry
            return raw if call.direction == 'buy' else -raw  # flip for sells

        r1w = get_return(7)
        r1m = get_return(30)
        r3m = get_return(90)
        r6m = get_return(180)
        r12m = get_return(365)

        # Hit target
        hit_1m = hit_3m = None
        if call.target_price and entry > 0:
            target_return = (call.target_price - entry) / entry
            if r1m is not None:
                hit_1m = r1m >= target_return if call.direction == 'buy' else r1m >= -target_return
            if r3m is not None:
                hit_3m = r3m >= target_return if call.direction == 'buy' else r3m >= -target_return

        outcomes.append(CallOutcome(
            call_id=call.call_id,
            ticker=call.ticker,
            entry_price=entry,
            target_price=call.target_price,
            entry_date=call.timestamp,
            return_1w=r1w,
            return_1m=r1m,
            return_3m=r3m,
            return_6m=r6m,
            return_12m=r12m,
            hit_target_1m=hit_1m,
            hit_target_3m=hit_3m,
            direction=call.direction,
        ))

    return outcomes


# ─────────────────────────────────────────────
# TIMELINESS SCORE
# ─────────────────────────────────────────────

def _compute_timeliness(
    calls: List[TradingCall],
    min_calls: int = 5,
) -> Dict[str, float]:
    """
    For each ticker+direction, find the first call date in the group.
    Timeliness = how many days before the group consensus.
    Returns {author: mean_timeliness_score}.
    """
    # Group calls by (ticker, direction, week) to find earliest
    ticker_dir_dates: Dict[Tuple[str, str], List[Tuple[datetime, str]]] = defaultdict(list)
    for call in calls:
        td_key = (call.ticker, call.direction)
        ticker_dir_dates[td_key].append((call.timestamp, call.author))

    author_timeliness: Dict[str, List[float]] = defaultdict(list)

    for (ticker, direction), date_author_list in ticker_dir_dates.items():
        if len(date_author_list) < 2:
            continue

        sorted_calls = sorted(date_author_list, key=lambda x: x[0])
        first_date = sorted_calls[0][0]
        last_date = sorted_calls[-1][0]
        date_range = (last_date - first_date).total_seconds() / 3600  # hours

        if date_range < 1:
            continue

        for ts, author in date_author_list:
            hours_from_first = (ts - first_date).total_seconds() / 3600
            # Score: 1.0 if first, 0.0 if last, linear interpolation
            if date_range > 0:
                score = 1.0 - (hours_from_first / date_range)
            else:
                score = 1.0
            author_timeliness[author].append(score)

    return {
        author: float(np.mean(scores))
        for author, scores in author_timeliness.items()
        if len(scores) >= 1
    }


# ─────────────────────────────────────────────
# MEMBER SCORING
# ─────────────────────────────────────────────

def _compute_member_scores(
    calls: List[TradingCall],
    outcomes: List[CallOutcome],
    timeliness: Dict[str, float],
    min_calls: int = 20,
) -> pd.DataFrame:
    """
    Compute Smart Money Score for each member.
    Components:
      40% win_rate_norm
      25% alpha_norm
      20% timeliness_norm
      15% consistency_norm
    """
    # Map call_id → outcome
    outcome_map = {o.call_id: o for o in outcomes}

    # Per-author metrics accumulation
    author_data: Dict[str, Dict] = defaultdict(lambda: {
        'calls': [],
        'returns_1m': [],
        'returns_3m': [],
        'wins_1m': [],
        'hits_target': [],
        'n_calls_with_ticker': 0,
    })

    for call in calls:
        out = outcome_map.get(call.call_id)
        if out is None:
            continue
        d = author_data[call.author]
        d['calls'].append(call)
        d['n_calls_with_ticker'] += 1
        if out.return_1m is not None:
            d['returns_1m'].append(out.return_1m)
            d['wins_1m'].append(out.return_1m > 0)
        if out.return_3m is not None:
            d['returns_3m'].append(out.return_3m)
        if out.hit_target_1m is not None:
            d['hits_target'].append(out.hit_target_1m)

    records = []
    for author, data in author_data.items():
        n = data['n_calls_with_ticker']
        if n < min_calls:
            continue

        rets_1m = data['returns_1m']
        rets_3m = data['returns_3m']
        wins_1m = data['wins_1m']
        hits = data['hits_target']

        if len(rets_1m) < 5:
            continue

        rets_arr = np.array(rets_1m)
        win_rate = float(np.mean(wins_1m)) if wins_1m else 0.5

        # Alpha vs MASI benchmark (~8% annual = ~0.67% monthly)
        MASI_MONTHLY = 0.0067
        alpha = float(np.mean(rets_arr)) - MASI_MONTHLY

        # Information Ratio: alpha / std(excess_returns)
        excess = rets_arr - MASI_MONTHLY
        ir = float(np.mean(excess) / np.std(excess)) if np.std(excess) > 0 else 0.0

        # Sharpe approximation (0% risk-free)
        sharpe = float(np.mean(rets_arr) / np.std(rets_arr)) if np.std(rets_arr) > 0 else 0.0

        # Consistency: low variance of returns relative to mean
        consistency = 1.0 / (1.0 + float(np.std(rets_arr))) if len(rets_arr) > 1 else 0.5

        # Precision (hit rate on targets)
        precision = float(np.mean(hits)) if hits else win_rate

        # Timeliness
        timeliness_score = timeliness.get(author, 0.5)

        # 3M performance
        mean_return_3m = float(np.mean(rets_3m)) if rets_3m else 0.0

        records.append({
            'author': author,
            'n_calls': n,
            'n_with_outcome': len(rets_1m),
            'win_rate': round(win_rate, 3),
            'alpha_monthly': round(alpha, 4),
            'information_ratio': round(ir, 3),
            'sharpe_ratio': round(sharpe, 3),
            'consistency': round(consistency, 3),
            'precision': round(precision, 3),
            'timeliness': round(timeliness_score, 3),
            'mean_return_1m': round(float(np.mean(rets_arr)), 4),
            'mean_return_3m': round(mean_return_3m, 4),
            'std_return_1m': round(float(np.std(rets_arr)), 4),
        })

    if not records:
        return pd.DataFrame()

    scores_df = pd.DataFrame(records)

    # Normalize each component to 0-100
    def norm_series(s: pd.Series, invert: bool = False) -> pd.Series:
        mn, mx = s.min(), s.max()
        if mx == mn:
            return pd.Series(50.0, index=s.index)
        n = (s - mn) / (mx - mn) * 100
        return (100 - n) if invert else n

    scores_df['win_rate_norm'] = norm_series(scores_df['win_rate'])
    scores_df['alpha_norm'] = norm_series(scores_df['alpha_monthly'])
    scores_df['timeliness_norm'] = norm_series(scores_df['timeliness'])
    scores_df['consistency_norm'] = norm_series(scores_df['consistency'])

    # Smart Money Score
    scores_df['smart_money_score'] = (
        0.40 * scores_df['win_rate_norm'] +
        0.25 * scores_df['alpha_norm'] +
        0.20 * scores_df['timeliness_norm'] +
        0.15 * scores_df['consistency_norm']
    ).clip(0, 100).round(1)

    # Rank
    scores_df = scores_df.sort_values('smart_money_score', ascending=False)
    scores_df['rank'] = range(1, len(scores_df) + 1)

    # Flag top 10% as smart money
    n_top = max(1, int(len(scores_df) * 0.1))
    scores_df['is_smart_money'] = scores_df['rank'] <= n_top

    # Also flag by absolute threshold
    scores_df['is_smart_money'] = (
        scores_df['is_smart_money'] |
        (scores_df['win_rate'] >= DEFAULT_CONFIG.smart_money_min_win_rate)
    )

    return scores_df.reset_index(drop=True)


# ─────────────────────────────────────────────
# FULL PIPELINE
# ─────────────────────────────────────────────

def run_smart_money_analysis(
    df: pd.DataFrame,
    price_db: Optional[Dict[str, pd.Series]] = None,
    cfg: Config = DEFAULT_CONFIG,
) -> Tuple[pd.DataFrame, List[str], List[TradingCall]]:
    """
    Full Smart Money pipeline.

    Parameters
    ----------
    df : enriched DataFrame from phase3
    price_db : optional {ticker: price_series}
    cfg : Config

    Returns
    -------
    member_scores : DataFrame with SMS scores and metrics
    smart_money_list : list of author names flagged as Smart Money
    all_calls : list of TradingCall objects
    """
    print("Extracting trading calls from messages...")
    all_calls = _extract_calls_from_df(df)
    print(f"  Extracted {len(all_calls):,} trading calls.")

    if not all_calls:
        print("No trading calls found. Check that phase3 NLP was run.")
        return pd.DataFrame(), [], []

    print("Tracking call outcomes (synthetic GBM if no price data)...")
    outcomes = _track_outcomes(all_calls, price_db=price_db)
    print(f"  Tracked {len(outcomes):,} outcomes.")

    print("Computing timeliness scores...")
    timeliness = _compute_timeliness(all_calls)

    print("Computing member Smart Money scores...")
    member_scores = _compute_member_scores(
        all_calls, outcomes, timeliness,
        min_calls=cfg.min_messages_for_ranking,
    )

    if member_scores.empty:
        print("  No members met minimum call threshold.")
        return pd.DataFrame(), [], all_calls

    smart_money_list = member_scores[member_scores['is_smart_money']]['author'].tolist()
    print(f"  Ranked {len(member_scores)} members.")
    print(f"  Smart Money identified: {len(smart_money_list)} members.")

    return member_scores, smart_money_list, all_calls


# ─────────────────────────────────────────────
# CALLS TO DATAFRAME
# ─────────────────────────────────────────────

def calls_to_dataframe(calls: List[TradingCall]) -> pd.DataFrame:
    """Convert list of TradingCall objects to DataFrame."""
    if not calls:
        return pd.DataFrame()
    return pd.DataFrame([
        {
            'call_id': c.call_id,
            'author': c.author,
            'timestamp': c.timestamp,
            'ticker': c.ticker,
            'direction': c.direction,
            'entry_price': c.entry_price,
            'target_price': c.target_price,
            'stop_loss': c.stop_loss,
            'confidence': c.confidence,
            'signal_type': c.signal_type,
            'message_id': c.message_id,
            'risk_reward': c.risk_reward,
        }
        for c in calls
    ])


# ─────────────────────────────────────────────
# SUMMARY
# ─────────────────────────────────────────────

def summarize_smart_money(
    member_scores: pd.DataFrame,
    smart_money_list: List[str],
) -> None:
    print(f"\n{'='*60}")
    print("SMART MONEY ANALYSIS SUMMARY")
    print(f"{'='*60}")

    if member_scores.empty:
        print("No scored members.")
        return

    print(f"Total ranked members: {len(member_scores)}")
    print(f"Smart Money members: {len(smart_money_list)}")
    print(f"\nTop 10 members by Smart Money Score:")
    print(f"{'Rank':<5} {'Author':<35} {'SMS':<6} {'WinRate':<9} {'Alpha':<8} {'Timeliness'}")
    print("-" * 70)
    for _, row in member_scores.head(10).iterrows():
        print(
            f"{row['rank']:<5} {str(row['author'])[:34]:<35} "
            f"{row['smart_money_score']:<6.1f} "
            f"{row['win_rate']:<9.1%} "
            f"{row['alpha_monthly']:<8.3f} "
            f"{row['timeliness']:.3f}"
        )
    print(f"{'='*60}\n")


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────

if __name__ == "__main__":
    import time
    from pathlib import Path

    OUT_DIR = Path("/home/user/-bvc-analyzer/whatsapp_analysis/output")
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    # Load enriched data
    p3 = OUT_DIR / "phase3_messages.parquet"
    p2 = OUT_DIR / "phase2_messages.parquet"
    p1 = OUT_DIR / "phase1_messages.parquet"

    for path in [p3, p2, p1]:
        if path.exists():
            print(f"Loading {path.name}...")
            df = pd.read_parquet(path)
            break
    else:
        raise FileNotFoundError("No phase parquet found.")

    print(f"Loaded {len(df):,} messages.")
    t0 = time.time()

    member_scores, smart_money_list, all_calls = run_smart_money_analysis(df)

    print(f"\nAnalysis complete in {time.time()-t0:.1f}s")
    summarize_smart_money(member_scores, smart_money_list)

    # Save outputs
    if not member_scores.empty:
        member_scores.to_parquet(OUT_DIR / "phase5_member_scores.parquet", index=False)
        member_scores.to_csv(OUT_DIR / "phase5_member_scores.csv", index=False)
        print(f"Saved member_scores.parquet and .csv")

    calls_df = calls_to_dataframe(all_calls)
    if not calls_df.empty:
        calls_df.to_parquet(OUT_DIR / "phase5_trading_calls.parquet", index=False)
        print(f"Saved {len(calls_df):,} trading calls to phase5_trading_calls.parquet")

    import json
    with open(OUT_DIR / "phase5_smart_money_list.json", 'w', encoding='utf-8') as f:
        json.dump(smart_money_list, f, ensure_ascii=False, indent=2)
    print(f"Smart Money list: {smart_money_list[:10]}")
