"""
Phase 7 — Stock Scoring & Rankings
Per-ticker analysis: mentions, sentiment, smart money weighting,
conviction, polarization, trending detection, classification.
"""
from __future__ import annotations

import warnings
from collections import defaultdict
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from whatsapp_analysis.config import (
    DEFAULT_CONFIG,
    Config,
    BVC_TICKERS,
)

warnings.filterwarnings('ignore', category=RuntimeWarning)

# ─────────────────────────────────────────────
# TICKER SECTOR MAP
# ─────────────────────────────────────────────

SECTOR_MAP: Dict[str, str] = {
    'IAM': 'Télécoms', 'ATW': 'Banque', 'BCP': 'Banque', 'BOA': 'Banque',
    'CIH': 'Banque', 'CDM': 'Banque', 'WAF': 'Finance',
    'CMT': 'Ciment', 'CIMAR': 'Ciment', 'HPS': 'Tech',
    'MNG': 'Mines', 'MIC': 'Industrie', 'ADH': 'Immobilier',
    'ADI': 'Immobilier', 'AKD': 'Santé', 'CASH': 'Finance',
    'CFGB': 'Banque', 'CMGP': 'Industrie', 'CSR': 'Ciment',
    'MSA': 'Agro', 'RDS': 'Immobilier', 'RIS': 'Hôtellerie',
    'SGTM': 'Infrastructure', 'SMI': 'Mines', 'SNA': 'Chimie',
    'SOT': 'Pharma', 'SRM': 'Services', 'TGCC': 'BTP',
    'VCNE': 'Tech', 'ATL': 'Auto', 'BMCE': 'Banque', 'BMCI': 'Banque',
    'SGMB': 'Banque', 'CAM': 'Banque', 'LBV': 'Distribution',
    'MUT': 'Agro', 'DARI': 'Agro', 'DWY': 'Énergie',
    'IMACID': 'Chimie', 'MINTRA': 'Transport', 'M2M': 'Tech',
    'ZELLIDJA': 'Mines', 'REBAB': 'Industrie', 'TIMAR': 'Transport',
    'UNIMER': 'Agro', 'YNNA': 'Conglomérat',
    'ATLANTA': 'Assurance', 'MAMDA': 'Assurance', 'MFIN': 'Finance',
    'RMA': 'Assurance', 'WAFA': 'Assurance',
    'AFMA': 'Finance', 'CCA': 'Distribution', 'SODEP': 'Port',
    'NEXANS': 'Industrie', 'MSIN': 'Finance',
    'COSUMAR': 'Agro', 'LESIEUR': 'Agro', 'DARI2': 'Agro',
    'SFBT': 'Agro', 'OUL': 'Agro', 'HALIMA': 'Agro',
    'PHARM': 'Pharma', 'SOTHEMA': 'Pharma',
    'S2M': 'Tech', 'NAPS': 'Tech', 'DISWAY': 'Tech',
    'INVOLYS': 'Tech', 'IB_MAROC': 'Tech',
    'ENGIE': 'Énergie', 'TANGER_MED': 'Infrastructure',
    'TOTAL': 'Énergie', 'TIMAR2': 'Transport',
    'DELATTRE': 'Industrie', 'SID': 'Sidérurgie',
}


def get_sector(ticker: str) -> str:
    return SECTOR_MAP.get(ticker, 'Autre')


# ─────────────────────────────────────────────
# TICKER EXTRACTION FROM DATAFRAME
# ─────────────────────────────────────────────

def _explode_tickers(df: pd.DataFrame) -> pd.DataFrame:
    """
    Explode tickers column into one row per (message, ticker).
    Handles both 'nlp_tickers' and 'tickers' columns.
    """
    ticker_col = None
    for col in ['nlp_tickers', 'tickers']:
        if col in df.columns:
            ticker_col = col
            break

    if ticker_col is None:
        return pd.DataFrame()

    df_text = df[df['message_type'] == 'text'].copy()
    df_text[ticker_col] = df_text[ticker_col].apply(
        lambda x: x if isinstance(x, list) else []
    )

    # Filter to messages with at least one ticker
    df_with_tickers = df_text[df_text[ticker_col].apply(len) > 0].copy()
    if df_with_tickers.empty:
        return pd.DataFrame()

    # Explode
    exploded = df_with_tickers.explode(ticker_col).rename(columns={ticker_col: 'ticker'})
    exploded = exploded[exploded['ticker'].notna() & (exploded['ticker'] != '')]
    return exploded


# ─────────────────────────────────────────────
# CORE TICKER METRICS
# ─────────────────────────────────────────────

def compute_ticker_base_metrics(exploded: pd.DataFrame) -> pd.DataFrame:
    """
    Compute base metrics per ticker:
    - total_mentions
    - unique_authors
    - sentiment stats
    - signal counts
    - date range of activity
    """
    sig_cols = [c for c in exploded.columns if c.startswith('signal_')]
    sent_col = 'sentiment' if 'sentiment' in exploded.columns else None

    agg_dict = {
        'total_mentions': ('ticker', 'count'),
        'unique_authors': ('author', 'nunique'),
    }

    if sent_col:
        agg_dict.update({
            'mean_sentiment': ('sentiment', 'mean'),
            'median_sentiment': ('sentiment', 'median'),
            'std_sentiment': ('sentiment', 'std'),
            'min_sentiment': ('sentiment', 'min'),
            'max_sentiment': ('sentiment', 'max'),
        })

    base = exploded.groupby('ticker').agg(**agg_dict).reset_index()

    # Signal ratios
    if sig_cols:
        for sig_col in sig_cols:
            if sig_col in exploded.columns:
                sig_counts = exploded.groupby('ticker')[sig_col].sum().rename(sig_col)
                base = base.merge(sig_counts, on='ticker', how='left')

    # Date range
    if 'timestamp' in exploded.columns:
        date_range = exploded.groupby('ticker')['timestamp'].agg(
            first_mention=('min'),
            last_mention=('max'),
        ).reset_index()
        base = base.merge(date_range, on='ticker', how='left')

    base = base.fillna(0)
    return base


# ─────────────────────────────────────────────
# SMART MONEY WEIGHTED SENTIMENT
# ─────────────────────────────────────────────

def compute_smart_money_sentiment(
    exploded: pd.DataFrame,
    member_scores: Optional[pd.DataFrame] = None,
) -> pd.DataFrame:
    """
    Compute Smart Money weighted sentiment per ticker.
    Weight = smart_money_score / 100.
    Non-SM members get weight = 0.1 (minimum).
    """
    if 'sentiment' not in exploded.columns:
        return pd.DataFrame(columns=['ticker', 'sm_weighted_sentiment', 'sm_message_count'])

    df = exploded.copy()

    if member_scores is not None and not member_scores.empty and 'author' in member_scores.columns:
        score_map = member_scores.set_index('author')['smart_money_score'].to_dict()
        df['author_weight'] = df['author'].map(score_map).fillna(5.0) / 100.0  # default weight 0.05
        df['author_weight'] = df['author_weight'].clip(0.01, 1.0)
        df['weighted_sentiment'] = df['sentiment'] * df['author_weight']

        sm_authors = set(member_scores[member_scores.get('is_smart_money', False)]['author'].tolist()) \
            if 'is_smart_money' in member_scores.columns else set()
    else:
        df['author_weight'] = 0.1
        df['weighted_sentiment'] = df['sentiment'] * 0.1
        sm_authors = set()

    result = df.groupby('ticker').apply(
        lambda g: pd.Series({
            'sm_weighted_sentiment': float(
                g['weighted_sentiment'].sum() / g['author_weight'].sum()
                if g['author_weight'].sum() > 0 else 0.0
            ),
            'sm_message_count': len(g),
            'sm_author_count': g['author'].nunique(),
        })
    ).reset_index()

    return result


# ─────────────────────────────────────────────
# CONVICTION SCORE
# ─────────────────────────────────────────────

def compute_conviction_score(exploded: pd.DataFrame) -> pd.DataFrame:
    """
    Conviction = % of messages with strong signals (ACHAT_FORT or VENTE).
    High conviction = the crowd is decisive (not ambiguous).
    """
    strong_sig_cols = ['signal_ACHAT_FORT', 'signal_VENTE']
    available = [c for c in strong_sig_cols if c in exploded.columns]

    if not available:
        return pd.DataFrame(columns=['ticker', 'conviction_score', 'strong_buy_ratio', 'strong_sell_ratio'])

    df = exploded.copy()

    result = df.groupby('ticker').apply(
        lambda g: pd.Series({
            'conviction_score': float(g[available].any(axis=1).mean()),
            'strong_buy_ratio': float(g['signal_ACHAT_FORT'].mean()) if 'signal_ACHAT_FORT' in g.columns else 0.0,
            'strong_sell_ratio': float(g['signal_VENTE'].mean()) if 'signal_VENTE' in g.columns else 0.0,
            'buy_ratio': float(g['signal_ACHETER'].mean()) if 'signal_ACHETER' in g.columns else 0.0,
            'panic_ratio': float(g['signal_PANIQUE'].mean()) if 'signal_PANIQUE' in g.columns else 0.0,
        })
    ).reset_index()

    return result


# ─────────────────────────────────────────────
# POLARIZATION
# ─────────────────────────────────────────────

def compute_polarization(exploded: pd.DataFrame) -> pd.DataFrame:
    """
    Polarization = std of sentiments per ticker.
    High std = controversial (bulls and bears disagree).
    """
    if 'sentiment' not in exploded.columns:
        return pd.DataFrame(columns=['ticker', 'polarization'])

    pol = exploded.groupby('ticker')['sentiment'].std().rename('polarization')
    pol = pol.fillna(0).reset_index()
    return pol


# ─────────────────────────────────────────────
# TRENDING DETECTION
# ─────────────────────────────────────────────

def compute_trending_score(exploded: pd.DataFrame) -> pd.DataFrame:
    """
    For each ticker, compute:
    - 30-day rolling average of daily mentions
    - 90-day baseline average
    - trending_ratio = recent_30d / baseline_90d
    - trending = True if ratio > 1.5
    """
    if 'timestamp' not in exploded.columns:
        return pd.DataFrame(columns=['ticker', 'trending_ratio', 'is_trending'])

    df = exploded.copy()
    df['date'] = pd.to_datetime(df['timestamp']).dt.date

    # Daily counts per ticker
    daily = df.groupby(['ticker', 'date']).size().reset_index(name='daily_mentions')
    daily['date'] = pd.to_datetime(daily['date'])

    results = []
    for ticker, grp in daily.groupby('ticker'):
        # Keep only the daily_mentions series indexed by date
        mentions = grp.set_index('date')['daily_mentions'].sort_index()

        # Fill missing dates with 0
        if len(mentions) > 1:
            date_range = pd.date_range(mentions.index.min(), mentions.index.max(), freq='D')
            mentions = mentions.reindex(date_range, fill_value=0)

        if len(mentions) < 7:
            results.append({
                'ticker': ticker,
                'trending_ratio': 1.0,
                'is_trending': False,
                'recent_30d_avg': float(mentions.mean()),
                'baseline_90d_avg': float(mentions.mean()),
            })
            continue

        recent_30 = float(mentions.tail(30).mean())
        baseline_90 = float(mentions.tail(90).mean())

        if baseline_90 > 0:
            ratio = recent_30 / baseline_90
        else:
            ratio = 1.0 if recent_30 == 0 else 2.0

        results.append({
            'ticker': ticker,
            'trending_ratio': round(ratio, 3),
            'is_trending': ratio > 1.5,
            'recent_30d_avg': round(recent_30, 2),
            'baseline_90d_avg': round(baseline_90, 2),
        })

    return pd.DataFrame(results)


# ─────────────────────────────────────────────
# MENTION VOLUME TIME SERIES
# ─────────────────────────────────────────────

def compute_mention_timeseries(
    exploded: pd.DataFrame,
    freq: str = 'W',
) -> pd.DataFrame:
    """
    Returns pivot table: tickers as columns, time periods as rows, values = mention counts.
    """
    if 'timestamp' not in exploded.columns:
        return pd.DataFrame()

    df = exploded.copy()
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    df = df.set_index('timestamp')

    # Resample per ticker
    tickers = df['ticker'].unique()
    time_dfs = []
    for ticker in tickers:
        sub = df[df['ticker'] == ticker]
        ts = sub.resample(freq).size().rename(ticker)
        time_dfs.append(ts)

    if not time_dfs:
        return pd.DataFrame()

    return pd.concat(time_dfs, axis=1).fillna(0)


# ─────────────────────────────────────────────
# FULL STOCK SCORING
# ─────────────────────────────────────────────

def compute_stock_scores(
    df: pd.DataFrame,
    member_scores: Optional[pd.DataFrame] = None,
    cfg: Config = DEFAULT_CONFIG,
) -> pd.DataFrame:
    """
    Compute comprehensive stock scores for all tickers.

    Returns DataFrame with all metrics and final classifications.
    """
    print("Exploding tickers from messages...")
    exploded = _explode_tickers(df)
    if exploded.empty:
        print("No ticker mentions found.")
        return pd.DataFrame()

    ticker_count = exploded['ticker'].nunique()
    mention_count = len(exploded)
    print(f"  {ticker_count} unique tickers, {mention_count:,} total mentions.")

    print("Computing base metrics...")
    base = compute_ticker_base_metrics(exploded)

    print("Computing Smart Money sentiment...")
    sm_sent = compute_smart_money_sentiment(exploded, member_scores)

    print("Computing conviction scores...")
    conviction = compute_conviction_score(exploded)

    print("Computing polarization...")
    polarization = compute_polarization(exploded)

    print("Computing trending scores...")
    trending = compute_trending_score(exploded)

    # Merge all metrics
    scores = base.copy()
    for df_merge in [sm_sent, conviction, polarization, trending]:
        if not df_merge.empty:
            scores = scores.merge(df_merge, on='ticker', how='left')

    scores = scores.fillna(0)

    # Add sector
    scores['sector'] = scores['ticker'].map(get_sector)

    # Composite Rankings
    # Normalize key metrics to 0-100
    def norm(s: pd.Series) -> pd.Series:
        mn, mx = s.min(), s.max()
        if mx == mn:
            return pd.Series(50.0, index=s.index)
        return (s - mn) / (mx - mn) * 100

    if 'sm_weighted_sentiment' in scores.columns:
        sm_sent_norm = norm(scores['sm_weighted_sentiment'])
    else:
        sm_sent_norm = pd.Series(50.0, index=scores.index)

    conviction_col = scores['conviction_score'] if 'conviction_score' in scores.columns else pd.Series(0.0, index=scores.index)
    conviction_norm = norm(conviction_col)

    # General score: smart sentiment × conviction
    scores['general_score'] = (0.6 * sm_sent_norm + 0.4 * conviction_norm).round(1)

    # Predictive score: include trending + timeliness bonus
    trending_bonus = scores['trending_ratio'] if 'trending_ratio' in scores.columns else pd.Series(1.0, index=scores.index)
    trending_norm = norm(trending_bonus.clip(0, 5))
    scores['predictive_score'] = (
        0.5 * sm_sent_norm +
        0.3 * conviction_norm +
        0.2 * trending_norm
    ).round(1)

    # Rankings
    scores['general_rank'] = scores['general_score'].rank(ascending=False).astype(int)
    scores['predictive_rank'] = scores['predictive_score'].rank(ascending=False).astype(int)

    # Sector rank
    scores['sector_rank'] = scores.groupby('sector')['general_score'].rank(ascending=False).astype(int)

    # Classification
    def _classify(row: pd.Series) -> str:
        n_mentions = row.get('total_mentions', 0)
        if n_mentions < 5:
            return 'Ignoré'
        general = row.get('general_score', 50)
        polar = row.get('polarization', 0)
        conv = row.get('conviction_score', 0)

        if polar > 0.6:
            return 'Controversé'
        if general >= 60 and conv > 0.1:
            return 'Meilleur pari'
        if general <= 35 or row.get('panic_ratio', 0) > 0.05:
            return 'À éviter'
        return 'Neutre'

    scores['classification'] = scores.apply(_classify, axis=1)

    # Sort by general_score descending
    scores = scores.sort_values('general_score', ascending=False).reset_index(drop=True)

    print(f"Stock scoring complete. {len(scores)} tickers scored.")
    return scores


# ─────────────────────────────────────────────
# SECTOR RANKINGS
# ─────────────────────────────────────────────

def compute_sector_rankings(scores: pd.DataFrame) -> pd.DataFrame:
    """
    Aggregate per-sector: mean general_score, mean sentiment, top ticker.
    """
    if 'sector' not in scores.columns or scores.empty:
        return pd.DataFrame()

    agg = scores.groupby('sector').agg(
        n_tickers=('ticker', 'count'),
        mean_general_score=('general_score', 'mean'),
        total_mentions=('total_mentions', 'sum'),
        mean_sentiment=('mean_sentiment', 'mean') if 'mean_sentiment' in scores.columns else ('general_score', 'mean'),
        top_ticker=('general_score', lambda x: scores.loc[x.idxmax(), 'ticker']),
    ).reset_index()

    agg = agg.sort_values('mean_general_score', ascending=False)
    agg['sector_rank'] = range(1, len(agg) + 1)
    return agg


# ─────────────────────────────────────────────
# SUMMARY
# ─────────────────────────────────────────────

def summarize_stock_scores(scores: pd.DataFrame) -> None:
    print(f"\n{'='*60}")
    print("STOCK SCORING SUMMARY")
    print(f"{'='*60}")

    if scores.empty:
        print("No scores computed.")
        return

    print(f"Total tickers: {len(scores)}")
    print(f"\nClassification breakdown:")
    for cls, cnt in scores['classification'].value_counts().items():
        print(f"  {cls:<20}: {cnt}")

    print(f"\nTop 10 Best Bets:")
    top = scores[scores['classification'] == 'Meilleur pari'].head(10)
    if top.empty:
        top = scores.head(10)
    cols_to_show = ['ticker', 'sector', 'total_mentions', 'general_score', 'predictive_score', 'classification']
    cols_available = [c for c in cols_to_show if c in scores.columns]
    print(top[cols_available].to_string(index=False))

    print(f"\nTo Avoid:")
    avoid = scores[scores['classification'] == 'À éviter'].head(5)
    if not avoid.empty:
        print(avoid[cols_available].to_string(index=False))

    print(f"\nControversial:")
    controv = scores[scores['classification'] == 'Controversé'].head(5)
    if not controv.empty:
        print(controv[cols_available].to_string(index=False))

    print(f"{'='*60}\n")


# ─────────────────────────────────────────────
# MENTION HEATMAP (top tickers × time)
# ─────────────────────────────────────────────

def compute_mention_heatmap(
    df: pd.DataFrame,
    top_n: int = 20,
    freq: str = 'M',
) -> pd.DataFrame:
    """
    Returns heatmap DataFrame: top_n tickers × time periods.
    """
    exploded = _explode_tickers(df)
    if exploded.empty:
        return pd.DataFrame()

    # Get top tickers by total mentions
    top_tickers = (
        exploded.groupby('ticker').size()
        .nlargest(top_n)
        .index
        .tolist()
    )

    filtered = exploded[exploded['ticker'].isin(top_tickers)]
    ts = compute_mention_timeseries(filtered, freq=freq)
    return ts[top_tickers] if all(t in ts.columns for t in top_tickers) else ts


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────

if __name__ == "__main__":
    import time
    from pathlib import Path

    OUT_DIR = Path("/home/user/-bvc-analyzer/whatsapp_analysis/output")
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    # Load data
    for fname in ["phase3_messages.parquet", "phase2_messages.parquet", "phase1_messages.parquet"]:
        p = OUT_DIR / fname
        if p.exists():
            print(f"Loading {fname}...")
            df = pd.read_parquet(p)
            break
    else:
        raise FileNotFoundError("No phase parquet found.")

    # Load member scores if available
    member_scores = None
    ms_path = OUT_DIR / "phase5_member_scores.parquet"
    if ms_path.exists():
        member_scores = pd.read_parquet(ms_path)
        print(f"Loaded {len(member_scores)} member scores.")

    print(f"Loaded {len(df):,} messages.")
    t0 = time.time()

    scores = compute_stock_scores(df, member_scores=member_scores)
    elapsed = time.time() - t0

    print(f"\nStock scoring complete in {elapsed:.1f}s")
    summarize_stock_scores(scores)

    # Sector rankings
    sector_ranks = compute_sector_rankings(scores)
    print("\nSector Rankings:")
    if not sector_ranks.empty:
        print(sector_ranks.to_string(index=False))

    # Mention heatmap
    print("\nComputing mention heatmap (top 20 tickers, monthly)...")
    heatmap = compute_mention_heatmap(df, top_n=20, freq='M')
    if not heatmap.empty:
        heatmap.to_csv(OUT_DIR / "phase7_mention_heatmap.csv")
        print(f"Saved mention heatmap.")

    # Save outputs
    if not scores.empty:
        scores.to_parquet(OUT_DIR / "phase7_stock_scores.parquet", index=False)
        scores.to_csv(OUT_DIR / "phase7_stock_scores.csv", index=False)
        print(f"Saved stock_scores.parquet and .csv")

    if not sector_ranks.empty:
        sector_ranks.to_csv(OUT_DIR / "phase7_sector_rankings.csv", index=False)
        print(f"Saved sector_rankings.csv")

    # Per-ticker time series for top 10
    exploded = _explode_tickers(df)
    if not exploded.empty:
        ts = compute_mention_timeseries(exploded, freq='W')
        top_tickers = scores.head(10)['ticker'].tolist() if not scores.empty else []
        if top_tickers:
            top_ts = ts[[t for t in top_tickers if t in ts.columns]]
            if not top_ts.empty:
                top_ts.to_csv(OUT_DIR / "phase7_top10_timeseries.csv")
                print(f"Saved top 10 ticker time series (weekly).")

    # Quick stats
    print(f"\nTop 5 most mentioned tickers:")
    if not scores.empty:
        cols = ['ticker', 'total_mentions', 'sector', 'mean_sentiment', 'classification']
        avail = [c for c in cols if c in scores.columns]
        top5 = scores.nlargest(5, 'total_mentions')[avail] if 'total_mentions' in scores.columns else scores.head(5)[avail]
        print(top5.to_string(index=False))
