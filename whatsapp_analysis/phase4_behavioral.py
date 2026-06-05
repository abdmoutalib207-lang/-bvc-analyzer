"""
Phase 4 — Behavioral Analysis: Fear & Greed Index BVC
Rolling psychological regime detection, inflection points,
herd effects, overconfidence, capitulation, fatigue.
"""
from __future__ import annotations

import math
from collections import defaultdict
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from scipy.ndimage import gaussian_filter1d
from scipy.signal import find_peaks

from whatsapp_analysis.config import DEFAULT_CONFIG, Config

# ─────────────────────────────────────────────
# FEAR & GREED LABELS
# ─────────────────────────────────────────────

FG_LABELS = {
    (0, 20): 'Peur Extrême',
    (21, 40): 'Peur',
    (41, 60): 'Neutre',
    (61, 80): 'Avidité',
    (81, 100): 'Avidité Extrême',
}

REGIME_LABELS = [
    'Peur Extrême', 'Peur', 'Neutre', 'Avidité', 'Avidité Extrême',
]


def fg_label(score: float) -> str:
    """Map Fear & Greed score (0-100) to label."""
    score_int = int(round(max(0, min(100, score))))
    for (lo, hi), label in FG_LABELS.items():
        if lo <= score_int <= hi:
            return label
    return 'Neutre'


# ─────────────────────────────────────────────
# COMPONENT COMPUTERS
# ─────────────────────────────────────────────

def _safe_ratio(numerator: float, denominator: float, default: float = 0.0) -> float:
    if denominator == 0:
        return default
    return numerator / denominator


def compute_daily_components(df: pd.DataFrame) -> pd.DataFrame:
    """
    Compute raw daily behavioral components from enriched NLP DataFrame.

    Required columns (from phase3): signal_PANIQUE, signal_EUPHORIE,
    signal_FOMO, signal_DOUTE, signal_ACHETER, signal_ACHAT_FORT, signal_VENTE.

    Returns daily DataFrame indexed by date with component columns.
    """
    df_text = df[df['message_type'] == 'text'].copy()
    df_text['date'] = pd.to_datetime(df_text['timestamp']).dt.date
    df_text['date'] = pd.to_datetime(df_text['date'])

    required_signals = [
        'signal_PANIQUE', 'signal_EUPHORIE', 'signal_FOMO',
        'signal_DOUTE', 'signal_ACHETER', 'signal_ACHAT_FORT', 'signal_VENTE',
    ]
    # Fill missing columns with False
    for col in required_signals:
        if col not in df_text.columns:
            df_text[col] = False

    if 'sentiment' not in df_text.columns:
        df_text['sentiment'] = 0.0

    daily = df_text.groupby('date').agg(
        n_messages=('message_text', 'count'),
        n_panic=('signal_PANIQUE', 'sum'),
        n_euphoria=('signal_EUPHORIE', 'sum'),
        n_fomo=('signal_FOMO', 'sum'),
        n_doubt=('signal_DOUTE', 'sum'),
        n_buy=('signal_ACHETER', 'sum'),
        n_strong_buy=('signal_ACHAT_FORT', 'sum'),
        n_sell=('signal_VENTE', 'sum'),
        mean_sentiment=('sentiment', 'mean'),
        std_sentiment=('sentiment', 'std'),
        n_authors=('author', 'nunique'),
    ).reset_index()

    daily['std_sentiment'] = daily['std_sentiment'].fillna(0)

    n = daily['n_messages'].clip(lower=1)

    daily['panic_ratio'] = daily['n_panic'] / n
    daily['euphoria_ratio'] = daily['n_euphoria'] / n
    daily['fomo_ratio'] = daily['n_fomo'] / n
    daily['uncertainty_ratio'] = daily['n_doubt'] / n
    daily['buy_sell_ratio'] = (daily['n_buy'] + daily['n_strong_buy']) / (daily['n_sell'] + 1)

    # Volume Z-score: z-score of daily message count vs rolling 30-day window
    rolling_mean = daily['n_messages'].rolling(30, min_periods=5).mean()
    rolling_std = daily['n_messages'].rolling(30, min_periods=5).std().clip(lower=1)
    daily['message_volume_zscore'] = (daily['n_messages'] - rolling_mean) / rolling_std
    daily['message_volume_zscore'] = daily['message_volume_zscore'].fillna(0).clip(-3, 3)

    return daily.set_index('date')


# ─────────────────────────────────────────────
# FEAR & GREED COMPUTATION
# ─────────────────────────────────────────────

def _normalize_to_100(series: pd.Series, invert: bool = False) -> pd.Series:
    """Min-max normalize series to 0-100, optionally invert."""
    mn = series.min()
    mx = series.max()
    if mx == mn:
        return pd.Series(50.0, index=series.index)
    normalized = (series - mn) / (mx - mn) * 100
    if invert:
        normalized = 100 - normalized
    return normalized


def compute_fear_greed(
    daily: pd.DataFrame,
    window: int = 7,
) -> pd.Series:
    """
    Compute rolling Fear & Greed Index (0-100).

    Components and weights:
      40% sentiment_score  (mean_sentiment normalized, greed = positive)
      20% buy_sell_ratio   (high ratio = greed)
      15% panic_ratio      (high = fear, inverted)
      10% euphoria_ratio   (high = greed)
      10% fomo_ratio       (high = greed)
       5% volume_zscore    (high volume = extreme, here greed-leaning)

    Apply rolling window to smooth.
    """
    d = daily.copy()

    # Component: sentiment → 0-100 (50 = neutral)
    # Map sentiment (-1 to +1) to 0-100 linearly
    if 'mean_sentiment' in d.columns:
        sentiment_score = ((d['mean_sentiment'] + 1) / 2 * 100).clip(0, 100)
    else:
        sentiment_score = pd.Series(50.0, index=d.index)

    # buy_sell_ratio: cap at 5, normalize
    bsr = d['buy_sell_ratio'].clip(0, 5)
    bsr_norm = _normalize_to_100(bsr)

    # panic: invert (high panic = fear = low score)
    panic_norm = _normalize_to_100(d['panic_ratio'], invert=True)

    # euphoria: high = greed
    euphoria_norm = _normalize_to_100(d['euphoria_ratio'])

    # fomo: high = greed
    fomo_norm = _normalize_to_100(d['fomo_ratio'])

    # volume zscore: extreme positive volume = greed
    vol_norm = _normalize_to_100(d['message_volume_zscore'].clip(-3, 3))

    # Composite
    fg_raw = (
        0.40 * sentiment_score +
        0.20 * bsr_norm +
        0.15 * panic_norm +
        0.10 * euphoria_norm +
        0.10 * fomo_norm +
        0.05 * vol_norm
    )

    # Rolling average smoothing
    fg_smooth = fg_raw.rolling(window=window, min_periods=1).mean()

    return fg_smooth.clip(0, 100).rename('fear_greed_index')


# ─────────────────────────────────────────────
# REGIME DETECTION
# ─────────────────────────────────────────────

def detect_regime_changes(fg_series: pd.Series) -> List[Dict]:
    """
    Detect transitions between Fear & Greed regimes.
    Returns list of {date, from_regime, to_regime, fg_value}.
    """
    regime_boundaries = [20, 40, 60, 80]

    def get_regime(score: float) -> int:
        """Returns regime index 0-4."""
        score = max(0, min(100, score))
        if score <= 20:
            return 0
        elif score <= 40:
            return 1
        elif score <= 60:
            return 2
        elif score <= 80:
            return 3
        else:
            return 4

    changes = []
    prev_regime = None
    for date, score in fg_series.items():
        regime = get_regime(score)
        if prev_regime is not None and regime != prev_regime:
            changes.append({
                'date': date,
                'from_regime': REGIME_LABELS[prev_regime],
                'to_regime': REGIME_LABELS[regime],
                'from_regime_idx': prev_regime,
                'to_regime_idx': regime,
                'fg_value': round(float(score), 1),
                'direction': 'bullish' if regime > prev_regime else 'bearish',
                'magnitude': abs(regime - prev_regime),
            })
        prev_regime = regime

    return changes


# ─────────────────────────────────────────────
# INFLECTION POINTS
# ─────────────────────────────────────────────

def find_inflection_points(
    fg_series: pd.Series,
    smoothing_sigma: float = 1.5,
    prominence: float = 5.0,
) -> List[Dict]:
    """
    Find local maxima and minima in Fear & Greed series.
    Uses scipy peak detection on smoothed series.
    Returns list of {date, fg_value, type: 'peak'|'trough', prominence}.
    """
    values = fg_series.values.astype(float)
    dates = fg_series.index.tolist()

    # Smooth for robust peak detection
    smoothed = gaussian_filter1d(values, sigma=smoothing_sigma)

    # Find peaks (greed maxima) and troughs (fear minima)
    peaks, peak_props = find_peaks(smoothed, prominence=prominence)
    troughs, trough_props = find_peaks(-smoothed, prominence=prominence)

    inflections = []
    for idx, prom in zip(peaks, peak_props.get('prominences', [5.0] * len(peaks))):
        if idx < len(dates):
            inflections.append({
                'date': dates[idx],
                'fg_value': round(float(values[idx]), 1),
                'type': 'peak',
                'prominence': round(float(prom), 1),
                'label': fg_label(values[idx]),
            })
    for idx, prom in zip(troughs, trough_props.get('prominences', [5.0] * len(troughs))):
        if idx < len(dates):
            inflections.append({
                'date': dates[idx],
                'fg_value': round(float(values[idx]), 1),
                'type': 'trough',
                'prominence': round(float(prom), 1),
                'label': fg_label(values[idx]),
            })

    inflections.sort(key=lambda x: x['date'])
    return inflections


# ─────────────────────────────────────────────
# HERD EFFECT MEASUREMENT
# ─────────────────────────────────────────────

def compute_herd_effect(df: pd.DataFrame) -> pd.Series:
    """
    Daily herd effect: average pairwise correlation of author sentiments.
    High correlation on a given day = herd behavior.

    Returns daily Series named 'herd_effect' (0-1).
    """
    if 'sentiment' not in df.columns:
        return pd.Series(dtype=float)

    df_text = df[df['message_type'] == 'text'].copy()
    df_text['date'] = pd.to_datetime(df_text['timestamp']).dt.date

    herd_by_day = {}
    for date, group in df_text.groupby('date'):
        # Need multiple authors
        authors = group['author'].unique()
        if len(authors) < 3:
            herd_by_day[date] = 0.0
            continue

        # Pivot: authors × (not needed, just look at variance)
        # Herd effect = 1 - normalized std of mean sentiments per author
        author_sentiments = group.groupby('author')['sentiment'].mean()
        if len(author_sentiments) < 2:
            herd_by_day[date] = 0.0
            continue

        std = author_sentiments.std()
        mean_abs = author_sentiments.abs().mean()
        if mean_abs == 0:
            herd_by_day[date] = 0.0
            continue

        # Low std relative to mean absolute value = high herding
        cv = std / (mean_abs + 0.01)  # coefficient of variation
        herd = max(0.0, 1.0 - min(cv, 1.0))
        herd_by_day[date] = round(herd, 3)

    if not herd_by_day:
        return pd.Series(dtype=float)

    return pd.Series(herd_by_day, name='herd_effect')


# ─────────────────────────────────────────────
# CAPITULATION SIGNALS
# ─────────────────────────────────────────────

def detect_capitulation_signals(
    fg_series: pd.Series,
    daily: pd.DataFrame,
) -> List[Dict]:
    """
    Detect potential capitulation events:
    - FG drops to Peur Extrême (≤20) after sustained Peur or worse
    - Accompanied by spike in message volume
    - High panic_ratio
    """
    capitulations = []
    fg_values = fg_series.values
    fg_dates = fg_series.index.tolist()
    n = len(fg_values)

    if n < 10:
        return capitulations

    for i in range(7, n):
        current_fg = fg_values[i]
        if current_fg > 25:
            continue  # Must be near extreme fear

        # Was previously less fearful (7-day lookback)?
        prior_avg = float(np.mean(fg_values[max(0, i-7):i]))
        if prior_avg - current_fg < 10:
            continue  # Not a significant drop

        date = fg_dates[i]
        # Check volume spike
        if date in daily.index:
            row = daily.loc[date]
            vol_z = row.get('message_volume_zscore', 0)
            panic_r = row.get('panic_ratio', 0)
            if vol_z > 1.0 or panic_r > 0.1:
                capitulations.append({
                    'date': date,
                    'fg_value': round(float(current_fg), 1),
                    'prior_fg_avg': round(float(prior_avg), 1),
                    'fg_drop': round(float(prior_avg - current_fg), 1),
                    'volume_zscore': round(float(vol_z), 2),
                    'panic_ratio': round(float(panic_r), 3),
                    'type': 'capitulation',
                })

    return capitulations


# ─────────────────────────────────────────────
# OVERCONFIDENCE DETECTION
# ─────────────────────────────────────────────

def detect_overconfidence(
    fg_series: pd.Series,
    min_days_above: int = 10,
    greed_threshold: float = 80.0,
    reversal_threshold: float = 15.0,
) -> List[Dict]:
    """
    Detect overconfidence patterns:
    Extended periods of FG > greed_threshold followed by sharp reversal.
    """
    results = []
    values = fg_series.values
    dates = fg_series.index.tolist()
    n = len(values)

    i = 0
    while i < n:
        if values[i] >= greed_threshold:
            # Find end of overconfidence window
            j = i
            while j < n and values[j] >= greed_threshold:
                j += 1

            duration = j - i
            if duration >= min_days_above:
                # Check for reversal in next 14 days
                max_reversal_check = min(j + 14, n)
                post_values = values[j:max_reversal_check]
                if len(post_values) > 0:
                    peak = float(np.mean(values[i:j]))
                    trough = float(np.min(post_values)) if len(post_values) > 0 else peak
                    drop = peak - trough
                    if drop >= reversal_threshold:
                        results.append({
                            'start_date': dates[i],
                            'end_date': dates[j-1] if j > i else dates[i],
                            'duration_days': duration,
                            'peak_fg': round(peak, 1),
                            'post_trough_fg': round(trough, 1),
                            'reversal_magnitude': round(drop, 1),
                            'type': 'overconfidence_reversal',
                        })
            i = max(i + 1, j)
        else:
            i += 1

    return results


# ─────────────────────────────────────────────
# FATIGUE PATTERNS
# ─────────────────────────────────────────────

def detect_fatigue(daily: pd.DataFrame, window: int = 30) -> pd.Series:
    """
    Message volume trend: declining volume in bull market context = fatigue.
    Returns a daily Series 'fatigue_score' 0-1.
    """
    if 'n_messages' not in daily.columns:
        return pd.Series(dtype=float)

    vol = daily['n_messages'].rolling(7, min_periods=1).mean()
    trend_30 = vol.rolling(window, min_periods=7).apply(
        lambda x: float(np.polyfit(range(len(x)), x, 1)[0]) if len(x) > 1 else 0.0,
        raw=True,
    )

    # Normalize: negative slope (declining volume) = high fatigue
    max_abs = trend_30.abs().max()
    if max_abs > 0:
        fatigue = (-trend_30 / max_abs).clip(0, 1)
    else:
        fatigue = pd.Series(0.0, index=daily.index)

    return fatigue.rename('fatigue_score')


# ─────────────────────────────────────────────
# FULL BEHAVIORAL PIPELINE
# ─────────────────────────────────────────────

def run_behavioral_analysis(
    df: pd.DataFrame,
    cfg: Config = DEFAULT_CONFIG,
) -> Tuple[pd.Series, List[Dict], List[Dict], pd.DataFrame, Dict]:
    """
    Full behavioral analysis pipeline.

    Returns
    -------
    fear_greed_series : pd.Series (DatetimeIndex, 0-100)
    regime_changes : List[Dict]
    inflection_points : List[Dict]
    behavioral_daily : pd.DataFrame (daily metrics)
    extras : Dict with capitulations, overconfidence, herd, fatigue
    """
    print("Computing daily behavioral components...")
    daily = compute_daily_components(df)

    print("Computing Fear & Greed Index...")
    fg_series = compute_fear_greed(daily, window=cfg.fear_greed_window)
    fg_series.index = pd.to_datetime(fg_series.index)

    print("Detecting regime changes...")
    regime_changes = detect_regime_changes(fg_series)
    print(f"  Found {len(regime_changes)} regime changes.")

    print("Finding inflection points...")
    try:
        inflection_points = find_inflection_points(fg_series, prominence=5.0)
        print(f"  Found {len(inflection_points)} inflection points.")
    except Exception as e:
        print(f"  Warning: inflection point detection failed: {e}")
        inflection_points = []

    print("Computing herd effect...")
    herd = compute_herd_effect(df)

    print("Detecting capitulation signals...")
    capitulations = detect_capitulation_signals(fg_series, daily)
    print(f"  Found {len(capitulations)} capitulation events.")

    print("Detecting overconfidence patterns...")
    overconfidence = detect_overconfidence(fg_series)
    print(f"  Found {len(overconfidence)} overconfidence periods.")

    print("Computing fatigue score...")
    fatigue = detect_fatigue(daily)

    # Build complete daily behavioral DataFrame
    behavioral_daily = daily.copy()
    behavioral_daily['fear_greed'] = fg_series.reindex(behavioral_daily.index)
    behavioral_daily['fg_label'] = behavioral_daily['fear_greed'].apply(fg_label)
    behavioral_daily['herd_effect'] = herd.reindex(behavioral_daily.index)
    behavioral_daily['fatigue_score'] = fatigue.reindex(behavioral_daily.index)

    # Fill NaN
    behavioral_daily = behavioral_daily.fillna(0)

    extras = {
        'capitulations': capitulations,
        'overconfidence': overconfidence,
        'herd': herd,
        'fatigue': fatigue,
    }

    return fg_series, regime_changes, inflection_points, behavioral_daily, extras


# ─────────────────────────────────────────────
# REPORTING HELPERS
# ─────────────────────────────────────────────

def summarize_behavioral(
    fg_series: pd.Series,
    regime_changes: List[Dict],
    inflection_points: List[Dict],
    extras: Dict,
) -> None:
    """Print a summary of behavioral analysis results."""
    print(f"\n{'='*60}")
    print("BEHAVIORAL ANALYSIS SUMMARY")
    print(f"{'='*60}")

    if len(fg_series) > 0:
        print(f"Date range: {fg_series.index.min().date()} → {fg_series.index.max().date()}")
        print(f"FG range: {fg_series.min():.1f} – {fg_series.max():.1f}")
        print(f"FG mean: {fg_series.mean():.1f} → {fg_label(fg_series.mean())}")
        current = fg_series.iloc[-1]
        print(f"FG last: {current:.1f} → {fg_label(current)}")

    print(f"\nRegime changes: {len(regime_changes)}")
    for rc in regime_changes[-5:]:  # last 5
        print(f"  {rc['date'].date() if hasattr(rc['date'], 'date') else rc['date']} : "
              f"{rc['from_regime']} → {rc['to_regime']} ({rc['direction']})")

    print(f"\nInflection points: {len(inflection_points)}")
    peaks = [x for x in inflection_points if x['type'] == 'peak']
    troughs = [x for x in inflection_points if x['type'] == 'trough']
    print(f"  Peaks (greed): {len(peaks)}, Troughs (fear): {len(troughs)}")

    caps = extras.get('capitulations', [])
    print(f"\nCapitulation events: {len(caps)}")

    oc = extras.get('overconfidence', [])
    print(f"Overconfidence periods: {len(oc)}")

    print(f"{'='*60}\n")


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────

if __name__ == "__main__":
    import time
    from pathlib import Path

    OUT_DIR = Path("/home/user/-bvc-analyzer/whatsapp_analysis/output")
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    # Try loading enriched parquet
    p3 = OUT_DIR / "phase3_messages.parquet"
    p2 = OUT_DIR / "phase2_messages.parquet"
    p1 = OUT_DIR / "phase1_messages.parquet"

    for path in [p3, p2, p1]:
        if path.exists():
            print(f"Loading {path.name}...")
            df = pd.read_parquet(path)
            break
    else:
        raise FileNotFoundError("No phase parquet found. Run earlier phases first.")

    print(f"Loaded {len(df):,} messages.")
    t0 = time.time()

    fg, regime_changes, inflections, behavioral_daily, extras = run_behavioral_analysis(df)

    print(f"\nBehavioral analysis complete in {time.time()-t0:.1f}s")
    summarize_behavioral(fg, regime_changes, inflections, extras)

    # Save
    fg_df = fg.reset_index()
    fg_df.columns = ['date', 'fear_greed_index']
    fg_df['fg_label'] = fg_df['fear_greed_index'].apply(fg_label)
    fg_df.to_csv(OUT_DIR / "phase4_fear_greed.csv", index=False)
    print(f"Saved fear_greed.csv")

    behavioral_daily.to_parquet(OUT_DIR / "phase4_behavioral_daily.parquet")
    print(f"Saved behavioral_daily.parquet")

    import json
    def _serialize(obj):
        if isinstance(obj, (pd.Timestamp, pd.DatetimeTZDtype)):
            return str(obj)
        if hasattr(obj, 'date'):
            return str(obj)
        return str(obj)

    with open(OUT_DIR / "phase4_regime_changes.json", 'w', encoding='utf-8') as f:
        json.dump(
            [{k: _serialize(v) if not isinstance(v, (int, float, str, bool)) else v
              for k, v in rc.items()} for rc in regime_changes],
            f, ensure_ascii=False, indent=2
        )
    with open(OUT_DIR / "phase4_inflection_points.json", 'w', encoding='utf-8') as f:
        json.dump(
            [{k: _serialize(v) if not isinstance(v, (int, float, str, bool)) else v
              for k, v in ip.items()} for ip in inflections],
            f, ensure_ascii=False, indent=2
        )
    print(f"Saved regime_changes.json and inflection_points.json")

    # Print recent FG values
    print("\nRecent Fear & Greed values:")
    for date, val in fg.tail(10).items():
        print(f"  {date.date()}: {val:.1f} — {fg_label(val)}")
