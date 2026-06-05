"""
Phase 2 — Language Detection
Multilingual classifier for French, Arabic, Darija, Arabizi, English, Mixed.
Rule-based, no external ML dependency required.
"""
from __future__ import annotations

import re
import unicodedata
from collections import Counter, defaultdict
from typing import Dict, List, Optional, Tuple

import pandas as pd

from whatsapp_analysis.config import DEFAULT_CONFIG, Config, ARABIZI_REPLACEMENTS

# ─────────────────────────────────────────────
# LANGUAGE SIGNATURES
# ─────────────────────────────────────────────

# Arabic Unicode block range
ARABIC_RANGE = re.compile(r'[؀-ۿݐ-ݿࢠ-ࣿﭐ-﷿ﹰ-﻿]')

# French function words & finance terms
FRENCH_WORDS: List[str] = [
    'le', 'la', 'les', 'de', 'du', 'des', 'un', 'une', 'et', 'en',
    'est', 'que', 'qui', 'dans', 'sur', 'avec', 'pour', 'par', 'pas',
    'je', 'tu', 'il', 'nous', 'vous', 'ils', 'se', 'ne', 'si', 'mais',
    'ou', 'donc', 'car', 'comme', 'très', 'aussi', 'bien', 'plus', 'tout',
    'achat', 'vente', 'cours', 'action', 'marché', 'hausse', 'baisse',
    'objectif', 'cible', 'potentiel', 'renforcer', 'acheter', 'vendre',
    'attention', 'résultats', 'dividende', 'bilan', 'rapport', 'secteur',
]
FRENCH_RE = re.compile(
    r'\b(' + '|'.join(FRENCH_WORDS) + r')\b',
    re.IGNORECASE,
)

# English function words & finance
ENGLISH_WORDS: List[str] = [
    'the', 'is', 'are', 'was', 'were', 'be', 'been', 'being',
    'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would',
    'could', 'should', 'may', 'might', 'shall', 'can', 'this',
    'that', 'these', 'those', 'it', 'he', 'she', 'we', 'they',
    'buy', 'sell', 'target', 'support', 'resistance', 'bullish',
    'bearish', 'market', 'stock', 'price', 'gain', 'loss',
    'hold', 'entry', 'exit', 'profit', 'strong', 'weak',
]
ENGLISH_RE = re.compile(
    r'\b(' + '|'.join(ENGLISH_WORDS) + r')\b',
    re.IGNORECASE,
)

# Darija tokens (Moroccan Arabic in Latin script)
DARIJA_TOKENS: List[str] = [
    'sba7', 'msa', 'bzaf', 'wlh', 'ra rani', '3ndi', '7na',
    '9bel', 'khoya', 'khouya', 'wach', 'daba', 'bghit', 'mzyan',
    'zwin', 'khayb', 'mesyan', 'la bas', 'labas', 'kayn', 'makayn',
    'htta', 'bhal', 'dial', 'dyali', 'dyalna', 'fin', 'mnin',
    'wahed', 'had', 'hadi', 'hada', 'dyal', 'f', 'men', 'b',
    'shi', 'lli', 'nta', 'nti', 'howa', 'hiya', 'hna', 'ntoma',
    'tshari', 'bi3', 'dkhol', 'khroj', 'trq3', 'nzel',
    'gha', 'ytl3', 'ynzel', 'frsya', 'khsara', 'rbah',
    'soq', 'seham', 'waq', 'taman', '3yat', 'machi', 'wad7',
    'kolchi', 'koulchi', 'mazal', 'msawwab', 'mdrob',
    'smiti', 'smiya', 'ntiya', 'huma', 'kima', 'bhal',
    'f7al', 'khadim', 'khdam', 'nqder', 'tqder', 'yqder',
    'safi', 'mashi', 'walou', 'hta', 'ila', 'wila',
    'ghadi', 'msha', 'ja', 'jab', 'gal', 'qal', 'sme3',
    'shuf', 'chuf', 'nshuf', 'nchuf', 'tfaddal', 'bghit',
    'n7eb', 'y7eb', 'ka', 'ta', 'katkhdem', 'katshri',
    'ssi', '3ammi', '7bit', '3awd', 'khw', 'khouia',
]
DARIJA_RE = re.compile(
    r'\b(' + '|'.join(re.escape(t) for t in sorted(DARIJA_TOKENS, key=len, reverse=True)) + r')\b',
    re.IGNORECASE,
)

# Arabizi: digit-for-letter substitution patterns
# Must have at least 2 arabizi digits in a word
ARABIZI_DIGIT_RE = re.compile(r'\b\w*[37924568]\w*\b')
ARABIZI_WORD_RE = re.compile(
    r'\b\w*(?:[37924568])\w*[37924568]\w*\b|'  # ≥2 arabizi digits in word
    r'\b(?:3ndi|7na|9bel|7it|3lik|7tta|7tta|9al|7abs|3la|3nd|7al|7san|9wiy|9awi|9dim)\b',
    re.IGNORECASE,
)

# Spanish minimal detection
SPANISH_WORDS = ['que', 'en', 'por', 'para', 'como', 'una', 'del', 'los', 'las', 'con']
SPANISH_RE = re.compile(r'\b(' + '|'.join(SPANISH_WORDS) + r')\b', re.IGNORECASE)

# ─────────────────────────────────────────────
# PER-MESSAGE SCORER
# ─────────────────────────────────────────────

class LanguageScorer:
    """
    Compute normalized language scores for a single message.
    Returns a dict {lang: score} and the dominant language.
    """

    def score(self, text: str) -> Dict[str, float]:
        if not text or len(text.strip()) == 0:
            return {'unknown': 1.0}

        word_count = max(len(text.split()), 1)
        scores: Dict[str, float] = {}

        # Arabic script detection
        arabic_chars = len(ARABIC_RANGE.findall(text))
        total_alpha = max(
            sum(1 for c in text if c.isalpha()), 1
        )
        arabic_ratio = arabic_chars / total_alpha
        if arabic_ratio > 0.4:
            scores['ar'] = arabic_ratio

        # Arabizi detection (digits replacing letters + latin script)
        arabizi_matches = ARABIZI_WORD_RE.findall(text)
        arabizi_score = min(len(arabizi_matches) / word_count * 3, 1.0)
        if arabizi_score > 0.1:
            scores['arabizi'] = arabizi_score

        # Darija detection (latin script)
        darija_matches = DARIJA_RE.findall(text)
        darija_score = min(len(darija_matches) / word_count * 2.5, 1.0)
        if darija_score > 0.05:
            scores['darija'] = darija_score

        # French detection
        fr_matches = FRENCH_RE.findall(text)
        fr_score = min(len(fr_matches) / word_count * 2.0, 1.0)
        if fr_score > 0.05:
            scores['fr'] = fr_score

        # English detection
        en_matches = ENGLISH_RE.findall(text)
        en_score = min(len(en_matches) / word_count * 2.0, 1.0)
        if en_score > 0.05:
            scores['en'] = en_score

        if not scores:
            return {'unknown': 1.0}

        return scores

    def classify(self, text: str) -> Tuple[str, float, Dict[str, float]]:
        """
        Returns (dominant_language, confidence, all_scores).
        If multiple languages have similar scores → 'mixed'.
        """
        scores = self.score(text)
        if not scores or scores == {'unknown': 1.0}:
            return 'unknown', 0.0, scores

        sorted_scores = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        best_lang, best_score = sorted_scores[0]

        # Mixed detection: if second language score > 60% of best
        if len(sorted_scores) >= 2:
            second_lang, second_score = sorted_scores[1]
            if second_score > best_score * 0.6 and best_score < 0.8:
                # Build mixed label
                langs = [l for l, s in sorted_scores if s > best_score * 0.4]
                if len(langs) >= 2:
                    return 'mixed', best_score, scores

        return best_lang, best_score, scores


# ─────────────────────────────────────────────
# BATCH DETECTION
# ─────────────────────────────────────────────

_scorer = LanguageScorer()


def detect_language(text: str) -> Tuple[str, float]:
    """Single message language detection. Returns (language, confidence)."""
    lang, conf, _ = _scorer.classify(text)
    return lang, conf


def detect_language_detailed(text: str) -> Dict[str, object]:
    """
    Returns detailed language detection result.
    Keys: language, confidence, scores, is_mixed, has_arabic_script, has_arabizi.
    """
    lang, conf, scores = _scorer.classify(text)
    arabic_chars = len(ARABIC_RANGE.findall(text))
    arabizi_hits = ARABIZI_WORD_RE.findall(text)
    return {
        'language': lang,
        'confidence': round(conf, 3),
        'scores': {k: round(v, 3) for k, v in scores.items()},
        'is_mixed': lang == 'mixed',
        'has_arabic_script': arabic_chars > 0,
        'has_arabizi': len(arabizi_hits) > 0,
        'has_darija': 'darija' in scores,
    }


# ─────────────────────────────────────────────
# DATAFRAME-LEVEL PROCESSING
# ─────────────────────────────────────────────

def add_language_to_df(
    df: pd.DataFrame,
    text_col: str = 'message_text',
    cfg: Config = DEFAULT_CONFIG,
) -> pd.DataFrame:
    """
    Add language detection columns to existing DataFrame.
    Returns enriched DataFrame with new columns:
      - language: dominant language string
      - lang_confidence: float 0-1
      - lang_scores: dict of all language scores
      - is_mixed_language: bool
      - has_arabic_script: bool
      - has_arabizi: bool
      - has_darija: bool
    """
    df = df.copy()

    # Apply detection (vectorized via apply for memory efficiency)
    print(f"Detecting language for {len(df):,} messages...")
    results = df[text_col].fillna('').apply(detect_language_detailed)

    df['language'] = results.apply(lambda x: x['language'])
    df['lang_confidence'] = results.apply(lambda x: x['confidence'])
    df['lang_scores'] = results.apply(lambda x: x['scores'])
    df['is_mixed_language'] = results.apply(lambda x: x['is_mixed'])
    df['has_arabic_script'] = results.apply(lambda x: x['has_arabic_script'])
    df['has_arabizi'] = results.apply(lambda x: x['has_arabizi'])
    df['has_darija'] = results.apply(lambda x: x['has_darija'])

    print(f"Language detection complete.")
    return df


# ─────────────────────────────────────────────
# MEMBER LANGUAGE PROFILES
# ─────────────────────────────────────────────

def build_member_language_profiles(
    df: pd.DataFrame,
    author_col: str = 'author',
    lang_col: str = 'language',
) -> pd.DataFrame:
    """
    For each member, compute:
    - dominant_language: most frequent language
    - language_entropy: diversity of languages used
    - language_distribution: Counter dict
    - is_multilingual: uses >=2 languages significantly
    """
    if lang_col not in df.columns:
        raise ValueError(f"Column '{lang_col}' not found. Run add_language_to_df first.")

    profiles = []
    for author, group in df.groupby(author_col):
        lang_counts = Counter(group[lang_col].tolist())
        total = max(sum(lang_counts.values()), 1)

        # Dominant language
        dominant = lang_counts.most_common(1)[0][0]

        # Shannon entropy
        import math
        entropy = 0.0
        for cnt in lang_counts.values():
            p = cnt / total
            if p > 0:
                entropy -= p * math.log2(p)

        # Is multilingual: >=2 languages each > 15% of messages
        lang_fracs = {l: c / total for l, c in lang_counts.items()}
        multilingual = sum(1 for v in lang_fracs.values() if v > 0.15) >= 2

        profiles.append({
            'author': author,
            'dominant_language': dominant,
            'language_entropy': round(entropy, 3),
            'language_distribution': dict(lang_counts),
            'is_multilingual': multilingual,
            'total_messages': total,
            'lang_fr_ratio': round(lang_fracs.get('fr', 0), 3),
            'lang_ar_ratio': round(lang_fracs.get('ar', 0), 3),
            'lang_darija_ratio': round(lang_fracs.get('darija', 0), 3),
            'lang_arabizi_ratio': round(lang_fracs.get('arabizi', 0), 3),
            'lang_en_ratio': round(lang_fracs.get('en', 0), 3),
            'lang_mixed_ratio': round(lang_fracs.get('mixed', 0), 3),
        })

    return pd.DataFrame(profiles).set_index('author')


# ─────────────────────────────────────────────
# TEMPORAL LANGUAGE ANALYSIS
# ─────────────────────────────────────────────

def compute_language_frequency_over_time(
    df: pd.DataFrame,
    freq: str = 'M',
    lang_col: str = 'language',
    date_col: str = 'timestamp',
) -> pd.DataFrame:
    """
    Returns a DataFrame with columns = language labels,
    rows = time periods (freq), values = message count.
    """
    if lang_col not in df.columns:
        raise ValueError(f"Column '{lang_col}' not found.")

    tmp = df[[date_col, lang_col]].copy()
    tmp[date_col] = pd.to_datetime(tmp[date_col])
    tmp = tmp.set_index(date_col)

    # One-hot encode language
    dummies = pd.get_dummies(tmp[lang_col])
    # Resample
    resampled = dummies.resample(freq).sum()
    return resampled


def compute_language_by_author_time(
    df: pd.DataFrame,
    author_col: str = 'author',
    lang_col: str = 'language',
    date_col: str = 'timestamp',
    freq: str = 'Q',
) -> pd.DataFrame:
    """
    Returns pivot: authors × periods, value = dominant language fraction.
    Useful for tracking language shift over time.
    """
    tmp = df[[date_col, author_col, lang_col]].copy()
    tmp[date_col] = pd.to_datetime(tmp[date_col])
    tmp['period'] = tmp[date_col].dt.to_period(freq).astype(str)

    # For each (author, period), compute dominant lang and its ratio
    records = []
    for (author, period), grp in tmp.groupby([author_col, 'period']):
        counts = Counter(grp[lang_col].tolist())
        total = sum(counts.values())
        dom_lang, dom_cnt = counts.most_common(1)[0]
        records.append({
            'author': author,
            'period': period,
            'dominant_language': dom_lang,
            'dominant_ratio': round(dom_cnt / total, 3),
            'n_messages': total,
        })

    return pd.DataFrame(records)


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────

if __name__ == "__main__":
    import time
    from pathlib import Path
    from whatsapp_analysis.phase1_parser import parse_chat, print_parse_summary

    CHAT_FILE = "/home/user/-bvc-analyzer/data/_chat.txt"
    OUT_DIR = Path("/home/user/-bvc-analyzer/whatsapp_analysis/output")
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    # Try loading from parquet first (fast), else re-parse
    parquet_path = OUT_DIR / "phase1_messages.parquet"
    if parquet_path.exists():
        print(f"Loading from parquet: {parquet_path}")
        df = pd.read_parquet(parquet_path)
        activity_stats = {}
    else:
        print(f"Parsing chat file: {CHAT_FILE}")
        t0 = time.time()
        df, activity_stats = parse_chat(CHAT_FILE)
        print(f"Parsed {len(df):,} messages in {time.time()-t0:.1f}s")

    print(f"\nRunning language detection on {len(df):,} messages...")
    t0 = time.time()
    df = add_language_to_df(df)
    print(f"Detection done in {time.time()-t0:.1f}s")

    # Language distribution
    print("\nLanguage distribution:")
    lang_dist = df['language'].value_counts()
    for lang, cnt in lang_dist.items():
        pct = cnt / len(df) * 100
        print(f"  {lang:<12}: {cnt:>7,}  ({pct:.1f}%)")

    # Member profiles
    print("\nBuilding member language profiles...")
    profiles = build_member_language_profiles(df)
    print(f"  {len(profiles)} member profiles built.")
    print(f"  Multilingual members: {profiles['is_multilingual'].sum()}")

    # Save
    df.to_parquet(OUT_DIR / "phase2_messages.parquet", index=False)
    profiles.to_parquet(OUT_DIR / "phase2_member_lang_profiles.parquet")
    print(f"\nSaved phase2_messages.parquet and phase2_member_lang_profiles.parquet")

    # Temporal
    time_freq = compute_language_frequency_over_time(df, freq='M')
    time_freq.to_csv(OUT_DIR / "phase2_language_over_time.csv")
    print(f"Saved language frequency over time (monthly).")

    # Sample
    print("\nSample messages by language:")
    for lang in ['fr', 'ar', 'darija', 'arabizi', 'mixed', 'en']:
        sample = df[df['language'] == lang].head(1)
        if not sample.empty:
            row = sample.iloc[0]
            print(f"  [{lang}] {row['message_text'][:80]}")
