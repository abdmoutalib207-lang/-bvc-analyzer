"""
Phase 3 — NLP: Signal Detection, NER, Sentiment, Sarcasm, Rumors
Multilingual (FR / AR / Darija / Arabizi / EN).
"""
from __future__ import annotations

import math
import re
from collections import defaultdict
from typing import Dict, List, Optional, Set, Tuple

import numpy as np
import pandas as pd

from whatsapp_analysis.config import (
    DEFAULT_CONFIG,
    Config,
    SIGNAL_KEYWORDS,
    PRICE_TARGET_PATTERNS,
    BVC_TICKERS,
    DARIJA_FINANCE_DICT,
    TICKER_ALIASES,
    extract_tickers_from_text,
)

# ─────────────────────────────────────────────
# COMPILED SIGNAL PATTERNS
# ─────────────────────────────────────────────

def _compile_signal_patterns() -> Dict[str, re.Pattern]:
    """Build one compiled regex per signal type covering all languages."""
    compiled = {}
    for signal, lang_dict in SIGNAL_KEYWORDS.items():
        all_phrases: List[str] = []
        for phrases in lang_dict.values():
            all_phrases.extend(phrases)
        # Sort by length desc so longer phrases match first
        all_phrases.sort(key=len, reverse=True)
        pattern_str = '|'.join(re.escape(p) for p in all_phrases)
        compiled[signal] = re.compile(pattern_str, re.IGNORECASE)
    return compiled


SIGNAL_PATTERNS: Dict[str, re.Pattern] = _compile_signal_patterns()

# Compiled price target patterns
_PRICE_PATTERNS: List[re.Pattern] = [
    re.compile(p, re.IGNORECASE) for p in PRICE_TARGET_PATTERNS
]

# Stop-loss pattern
SL_RE = re.compile(
    r'(?:stop|SL|sl|stop[-\s]loss|stoploss)\s*[:\s=]+\s*(\d+(?:[.,]\d+)?)',
    re.IGNORECASE,
)

# Entry price pattern
ENTRY_RE = re.compile(
    r'(?:entrée|entree|entry|PE|pe|point d\'entrée|prix d\'entrée)\s*[:\s=]+\s*(\d+(?:[.,]\d+)?)',
    re.IGNORECASE,
)

# ─────────────────────────────────────────────
# SIGNAL DETECTION
# ─────────────────────────────────────────────

def detect_signals(text: str) -> Dict[str, bool]:
    """
    Detect which SIGNAL_KEYWORDS categories are present.
    Returns dict {signal_name: True/False}.
    """
    result = {}
    for signal, pattern in SIGNAL_PATTERNS.items():
        result[signal] = bool(pattern.search(text))
    return result


def detect_signals_with_positions(text: str) -> Dict[str, List[Tuple[int, int, str]]]:
    """
    Returns matched spans for each signal: {signal: [(start, end, matched_text)]}.
    """
    result = {}
    for signal, pattern in SIGNAL_PATTERNS.items():
        matches = [(m.start(), m.end(), m.group()) for m in pattern.finditer(text)]
        if matches:
            result[signal] = matches
    return result


def get_dominant_signal(signals: Dict[str, bool]) -> Optional[str]:
    """
    Given a {signal: bool} dict, return the highest-priority signal.
    Priority: PANIQUE > VENTE > ACHAT_FORT > ACHETER > RENFORCEMENT > FOMO > EUPHORIE > DOUTE > RUMEUR > IRONIE
    """
    priority_order = [
        'PANIQUE', 'VENTE', 'ACHAT_FORT', 'ACHETER',
        'RENFORCEMENT', 'FOMO', 'EUPHORIE', 'DOUTE', 'RUMEUR', 'IRONIE',
    ]
    for sig in priority_order:
        if signals.get(sig, False):
            return sig
    return None


# ─────────────────────────────────────────────
# NAMED ENTITY RECOGNITION (rule-based)
# ─────────────────────────────────────────────

# Reconnaissance des sociétés citées par leur nom.
#
# Cette table était saisie à la main et produisait des codes qui n'existent
# pas dans notre univers : 'cosumar' → COSUMAR au lieu de CSR, 'disway' →
# DISWAY au lieu de DSW, 'sonasid' → SID (le ticker officiel BVC, pas le
# nôtre). Pire, 'ciments du maroc' et 'cimar' pointaient sur CMT — Minière
# Touissit — au lieu de CIM.
#
# On la dérive maintenant de TICKER_ALIASES, déjà construit depuis
# bvc_config : un seul référentiel, et les codes produits sont les nôtres.
COMPANY_NAMES: Dict[str, str] = {
    alias: ticker
    for ticker, alias_list in TICKER_ALIASES.items()
    for alias in alias_list
}

_COMPANY_RE = re.compile(
    r'\b(' + '|'.join(re.escape(k) for k in
                      sorted(COMPANY_NAMES, key=len, reverse=True)) + r')\b',
    re.IGNORECASE,
)

# Minister / officials (Moroccan context)
OFFICIALS_RE = re.compile(
    r'\b(Jouahri|Bank Al-Maghrib|BAM|CDG|AMMC|CDVM|HCP|CMR|CMAR|ministre|'
    r'gouvernement|ministère|parlement|sénat|chambre)\b',
    re.IGNORECASE,
)

# Banks
BANKS_RE = re.compile(
    r'\b(Attijariwafa|BCP|CIH|BMCI|SGMB|BOA|BMCE|CAM|CDM|CFG|'
    r'Bank Al-Maghrib|BAM|CDG)\b',
    re.IGNORECASE,
)


def extract_entities(text: str) -> Dict[str, List[str]]:
    """
    Extract: tickers (via config), companies, officials, banks.
    Returns {entity_type: [entity_strings]}.
    """
    tickers = extract_tickers_from_text(text)

    companies = list(set(
        COMPANY_NAMES.get(m.lower(), m) for m in _COMPANY_RE.findall(text)
    ))

    officials = list(set(OFFICIALS_RE.findall(text)))
    banks = list(set(BANKS_RE.findall(text)))

    return {
        'tickers': tickers,
        'companies': companies,
        'officials': officials,
        'banks': banks,
    }


# ─────────────────────────────────────────────
# PRICE EXTRACTION
# ─────────────────────────────────────────────

def _parse_price(s: str) -> Optional[float]:
    """Convert price string (may use comma as decimal) to float."""
    try:
        return float(s.replace(',', '.'))
    except (ValueError, AttributeError):
        return None


def extract_price_targets(text: str) -> List[float]:
    """Extract all price targets mentioned in text."""
    prices = []
    for pattern in _PRICE_PATTERNS:
        for m in pattern.finditer(text):
            price = _parse_price(m.group(1))
            if price is not None and 1.0 < price < 100_000:  # sanity range for BVC
                prices.append(price)
    return list(set(prices))


def extract_stop_loss(text: str) -> Optional[float]:
    m = SL_RE.search(text)
    if m:
        return _parse_price(m.group(1))
    return None


def extract_entry_price(text: str) -> Optional[float]:
    m = ENTRY_RE.search(text)
    if m:
        return _parse_price(m.group(1))
    return None


def extract_all_prices(text: str) -> Dict[str, object]:
    """
    Returns {targets: [float], stop_loss: float|None, entry: float|None}.
    """
    return {
        'targets': extract_price_targets(text),
        'stop_loss': extract_stop_loss(text),
        'entry': extract_entry_price(text),
    }


# ─────────────────────────────────────────────
# SENTIMENT SCORING
# ─────────────────────────────────────────────

# Positive / negative word lexicons (FR + AR + Darija + EN)
POSITIVE_WORDS: List[str] = [
    # French
    'bien', 'bon', 'excellent', 'super', 'bravo', 'parfait', 'formidable',
    'croissance', 'progression', 'hausse', 'gain', 'profit', 'opportunité',
    'recommandé', 'potentiel', 'positif', 'bullish', 'solide', 'fort',
    'record', 'historique', 'leader', 'performant', 'confiance',
    # Darija/Arabizi
    'zwin', 'mzyan', '3jib', 'msawwab', 'frsya', '9awi', 'wad7',
    'rbah', 'gha ytl3', 'ytl3', 'trq3',
    # Arabic
    'جيد', 'ممتاز', 'رائع', 'قوي', 'فرصة', 'ارتفاع', 'ربح', 'نمو',
    # English
    'good', 'great', 'excellent', 'bullish', 'strong', 'buy', 'profit',
    'growth', 'up', 'gain', 'opportunity', 'positive', 'solid',
]

NEGATIVE_WORDS: List[str] = [
    # French
    'mauvais', 'catastrophe', 'chute', 'effondrement', 'perte', 'danger',
    'risque', 'bearish', 'baisse', 'crash', 'krach', 'faible', 'inquiétant',
    'décevant', 'problème', 'alerte', 'attention', 'difficile', 'dégringolade',
    # Darija/Arabizi
    'khayb', 'khsara', 'machi bnin', 'danger', 'nzel', 'gha ynzel',
    'wili', 'd3f', 'mdrob',
    # Arabic
    'سيء', 'كارثة', 'هبوط', 'خسارة', 'خطر', 'انهيار', 'ضعيف', 'مشكلة',
    # English
    'bad', 'terrible', 'bearish', 'crash', 'loss', 'risk', 'danger',
    'decline', 'drop', 'weak', 'problem', 'alert', 'warning',
]

_POS_RE = re.compile(
    r'\b(' + '|'.join(re.escape(w) for w in sorted(POSITIVE_WORDS, key=len, reverse=True)) + r')\b',
    re.IGNORECASE,
)
_NEG_RE = re.compile(
    r'\b(' + '|'.join(re.escape(w) for w in sorted(NEGATIVE_WORDS, key=len, reverse=True)) + r')\b',
    re.IGNORECASE,
)

# Intensifiers
INTENSIFIER_RE = re.compile(
    r'\b(très|super|hyper|vraiment|tellement|encore plus|bzaf|beaucoup|'
    r'extrêmement|fortement|strong|very|highly|extremely)\b',
    re.IGNORECASE,
)

# Negation words that flip sentiment
NEGATION_RE = re.compile(
    r'\b(pas|ne|non|jamais|sans|ni|aucun|nullement|not|no|never|'
    r'makayn|machi|walo|walou|la)\b',
    re.IGNORECASE,
)


def compute_sentiment(text: str) -> Tuple[float, float]:
    """
    Returns (sentiment_score, confidence).
    sentiment_score: -1.0 (very negative) to +1.0 (very positive).
    confidence: 0.0 to 1.0.
    """
    pos_matches = _POS_RE.findall(text)
    neg_matches = _NEG_RE.findall(text)
    intensifiers = len(INTENSIFIER_RE.findall(text))
    negations = len(NEGATION_RE.findall(text))

    pos_count = len(pos_matches)
    neg_count = len(neg_matches)

    # Apply intensifier boost
    if intensifiers > 0:
        boost = 1.0 + (intensifiers * 0.2)
        pos_count = int(pos_count * boost)
        neg_count = int(neg_count * boost)

    # Apply negation (flip minority signal, reduce confidence)
    negation_flip = negations % 2 == 1  # odd negations flip
    if negation_flip and pos_count > neg_count:
        pos_count, neg_count = neg_count, pos_count + neg_count // 2
    elif negation_flip and neg_count > pos_count:
        pos_count, neg_count = neg_count, pos_count

    # Signal-based override
    signal_scores = {
        'ACHAT_FORT': 0.9,
        'ACHETER': 0.6,
        'RENFORCEMENT': 0.5,
        'EUPHORIE': 0.8,
        'FOMO': 0.4,
        'VENTE': -0.6,
        'PANIQUE': -0.9,
        'DOUTE': -0.2,
        'RUMEUR': 0.0,
        'IRONIE': -0.1,
    }
    signal_contribution = 0.0
    signals_found = 0
    for signal, pattern in SIGNAL_PATTERNS.items():
        if pattern.search(text) and signal in signal_scores:
            signal_contribution += signal_scores[signal]
            signals_found += 1

    total = pos_count + neg_count
    if total == 0 and signals_found == 0:
        return 0.0, 0.1  # neutral, low confidence

    # Blend lexical and signal scores
    if total > 0:
        lexical_score = (pos_count - neg_count) / total
    else:
        lexical_score = 0.0

    if signals_found > 0:
        signal_avg = signal_contribution / signals_found
        # Weight: 40% lexical, 60% signal if signals present
        final_score = 0.4 * lexical_score + 0.6 * signal_avg
    else:
        final_score = lexical_score

    # Clip to [-1, 1]
    final_score = max(-1.0, min(1.0, final_score))

    # Confidence: based on amount of evidence
    evidence = total + signals_found * 3
    confidence = min(1.0, evidence / 15.0)

    return round(final_score, 3), round(confidence, 3)


# ─────────────────────────────────────────────
# SARCASM / IRONY DETECTION
# ─────────────────────────────────────────────

SARCASM_MARKERS_RE = re.compile(
    r'\b(bien sûr|évidemment|comme d\'habitude|quelle surprise|'
    r'encore une fois|chapeau bas|wach ghrib|machi ghrib|'
    r'obviously|sure|what a surprise|shocking|'
    r'bghina hak|haha|lol|😂|🙄|😏)\b',
    re.IGNORECASE,
)

# Contradiction: positive word + negative context marker
POSITIVE_WITH_NEGATIVE_CONTEXT_RE = re.compile(
    r'(?:excellent|super|bien|bon|parfait)\s+\w{0,20}\s*(?:mais|however|sauf|except|pourtant|'
    r'malgré|despite|malheureusement|unfortunately)',
    re.IGNORECASE,
)


def detect_sarcasm(text: str, sentiment: float) -> Tuple[bool, float]:
    """
    Returns (is_sarcastic, confidence).
    Heuristics:
    1. Sarcasm markers present
    2. Positive words + negative context
    3. High positive words in message overall flagged very negative by signals
    """
    score = 0.0

    # Marker detection
    markers = SARCASM_MARKERS_RE.findall(text)
    if markers:
        score += 0.4 + len(markers) * 0.1

    # Contradiction pattern
    if POSITIVE_WITH_NEGATIVE_CONTEXT_RE.search(text):
        score += 0.3

    # Sentiment contradiction: signals say very negative but words are positive
    # (e.g. "incroyable résultats" when market is crashing)
    pos_count = len(_POS_RE.findall(text))
    neg_count = len(_NEG_RE.findall(text))
    if pos_count > neg_count * 2 and sentiment < -0.3:
        score += 0.25
    if neg_count > pos_count * 2 and sentiment > 0.3:
        score += 0.15

    # Emoji ambiguity: 😂 or 🙄 with "positive" statement
    if re.search(r'[😂🙄😏😒]', text) and pos_count > 0:
        score += 0.15

    confidence = min(1.0, score)
    return confidence > 0.3, round(confidence, 3)


# ─────────────────────────────────────────────
# RUMOR VS FACTUAL DISTINCTION
# ─────────────────────────────────────────────

RUMOR_INDICATORS_RE = re.compile(
    r'\b(on dit|j\'ai entendu|rumeur|bruit de couloir|source|off the record|'
    r'non confirmé|info|insider|sme3t|9alu|gal liya|khabar|'
    r'heard that|allegedly|reportedly|source says|whisper|unconfirmed)\b',
    re.IGNORECASE,
)

FACTUAL_INDICATORS_RE = re.compile(
    r'\b(rapport|résultats|bilan|publication|annonce officielle|communiqué|'
    r'selon|d\'après|source officielle|AMMC|BAM|bourse de casablanca|'
    r'declares|reports|announces|official|confirmed|press release|bilan financier)\b',
    re.IGNORECASE,
)


def classify_rumor_factual(text: str) -> Tuple[str, float]:
    """
    Returns ('rumor'|'factual'|'opinion'|'unknown', confidence).
    """
    rumor_hits = len(RUMOR_INDICATORS_RE.findall(text))
    factual_hits = len(FACTUAL_INDICATORS_RE.findall(text))
    has_rumor_signal = SIGNAL_PATTERNS['RUMEUR'].search(text) is not None

    if rumor_hits > 0 or has_rumor_signal:
        conf = min(1.0, 0.5 + rumor_hits * 0.2 + (0.3 if has_rumor_signal else 0))
        return 'rumor', round(conf, 3)
    elif factual_hits > 0:
        conf = min(1.0, 0.5 + factual_hits * 0.2)
        return 'factual', round(conf, 3)
    elif len(text.split()) > 5:
        return 'opinion', 0.4
    return 'unknown', 0.1


# ─────────────────────────────────────────────
# EXTRACTION CONFIDENCE SCORING
# ─────────────────────────────────────────────

def compute_extraction_confidence(
    text: str,
    signals: Dict[str, bool],
    sentiment: float,
    has_tickers: bool,
    has_price_targets: bool,
) -> float:
    """
    Overall confidence that this message contains a meaningful trading signal.
    0.0 = noise, 1.0 = high-quality signal.
    """
    score = 0.0
    n_signals = sum(1 for v in signals.values() if v)

    # More signals = more confidence
    score += min(n_signals * 0.15, 0.45)

    # Strong directional signals
    if signals.get('ACHAT_FORT') or signals.get('PANIQUE'):
        score += 0.2
    if signals.get('ACHETER') or signals.get('VENTE'):
        score += 0.15

    # Has tickers
    if has_tickers:
        score += 0.15

    # Has price targets (very actionable)
    if has_price_targets:
        score += 0.2

    # High absolute sentiment
    score += abs(sentiment) * 0.1

    # Message length bonus (longer = more context)
    word_count = len(text.split())
    if word_count > 20:
        score += 0.05
    if word_count > 50:
        score += 0.05

    return round(min(1.0, score), 3)


# ─────────────────────────────────────────────
# FULL NLP PROCESSING FOR A SINGLE MESSAGE
# ─────────────────────────────────────────────

def process_message(text: str) -> Dict[str, object]:
    """
    Full NLP pipeline for a single message text.
    Returns dict with all extracted fields.
    """
    # Signals
    signals = detect_signals(text)
    dominant_signal = get_dominant_signal(signals)

    # Entities
    entities = extract_entities(text)

    # Prices
    prices = extract_all_prices(text)

    # Sentiment
    sentiment, sent_confidence = compute_sentiment(text)

    # Sarcasm
    is_sarcastic, sarcasm_confidence = detect_sarcasm(text, sentiment)

    # Adjust sentiment for sarcasm
    if is_sarcastic and sarcasm_confidence > 0.5:
        sentiment = -sentiment  # flip

    # Rumor/factual
    info_type, info_confidence = classify_rumor_factual(text)

    # Extraction confidence
    has_targets = len(prices['targets']) > 0
    extraction_conf = compute_extraction_confidence(
        text, signals, sentiment,
        has_tickers=len(entities['tickers']) > 0,
        has_price_targets=has_targets,
    )

    return {
        # Signals
        'signal_ACHAT_FORT': signals.get('ACHAT_FORT', False),
        'signal_ACHETER': signals.get('ACHETER', False),
        'signal_RENFORCEMENT': signals.get('RENFORCEMENT', False),
        'signal_VENTE': signals.get('VENTE', False),
        'signal_PANIQUE': signals.get('PANIQUE', False),
        'signal_EUPHORIE': signals.get('EUPHORIE', False),
        'signal_DOUTE': signals.get('DOUTE', False),
        'signal_RUMEUR': signals.get('RUMEUR', False),
        'signal_IRONIE': signals.get('IRONIE', False),
        'signal_FOMO': signals.get('FOMO', False),
        'dominant_signal': dominant_signal,
        # Entities
        'nlp_tickers': entities['tickers'],
        'nlp_companies': entities['companies'],
        'nlp_officials': entities['officials'],
        'nlp_banks': entities['banks'],
        # Prices
        'price_targets': prices['targets'],
        'stop_loss': prices['stop_loss'],
        'entry_price': prices['entry'],
        'has_price_target': has_targets,
        # Sentiment
        'sentiment': sentiment,
        'sentiment_confidence': sent_confidence,
        'sentiment_label': _sentiment_label(sentiment),
        # Sarcasm
        'is_sarcastic': is_sarcastic,
        'sarcasm_confidence': sarcasm_confidence,
        # Information type
        'info_type': info_type,
        'info_type_confidence': info_confidence,
        # Overall quality
        'extraction_confidence': extraction_conf,
    }


def _sentiment_label(score: float) -> str:
    if score >= 0.6:
        return 'très_positif'
    elif score >= 0.2:
        return 'positif'
    elif score > -0.2:
        return 'neutre'
    elif score > -0.6:
        return 'négatif'
    else:
        return 'très_négatif'


# ─────────────────────────────────────────────
# DATAFRAME PROCESSING
# ─────────────────────────────────────────────

def enrich_dataframe(
    df: pd.DataFrame,
    text_col: str = 'message_text',
    cfg: Config = DEFAULT_CONFIG,
) -> pd.DataFrame:
    """
    Apply full NLP pipeline to every message in the DataFrame.
    Only processes 'text' message_type rows; others get neutral defaults.
    Returns enriched DataFrame.
    """
    df = df.copy()
    print(f"Running NLP on {len(df):,} messages...")

    # Default NLP columns — list columns need object dtype with None
    scalar_defaults = {
        'signal_ACHAT_FORT': False, 'signal_ACHETER': False,
        'signal_RENFORCEMENT': False, 'signal_VENTE': False,
        'signal_PANIQUE': False, 'signal_EUPHORIE': False,
        'signal_DOUTE': False, 'signal_RUMEUR': False,
        'signal_IRONIE': False, 'signal_FOMO': False,
        'dominant_signal': None,
        'stop_loss': None, 'entry_price': None,
        'has_price_target': False,
        'sentiment': 0.0, 'sentiment_confidence': 0.0,
        'sentiment_label': 'neutre',
        'is_sarcastic': False, 'sarcasm_confidence': 0.0,
        'info_type': 'unknown', 'info_type_confidence': 0.0,
        'extraction_confidence': 0.0,
    }
    list_cols = ['nlp_tickers', 'nlp_companies', 'nlp_officials', 'nlp_banks', 'price_targets']

    for col, default in scalar_defaults.items():
        df[col] = default

    # List columns: initialize as object series of empty lists
    for col in list_cols:
        df[col] = pd.array([[] for _ in range(len(df))], dtype=object)

    # Process text messages only
    text_mask = df['message_type'] == 'text'
    text_df = df[text_mask]
    total = len(text_df)
    print(f"  Processing {total:,} text messages...")

    # ⚠️ Le découpage en lots ci-dessous n'était que décoratif : la boucle
    # accumulait `results`, une liste de 792 828 dictionnaires d'une trentaine
    # de clés (dont des listes), puis en construisait un DataFrame — les deux
    # vivants en même temps au pic. Sur le corpus complet, le processus était
    # tué par le système à ~760 000 messages, systématiquement au même point.
    #
    # Chaque lot est désormais converti en DataFrame tout de suite : pandas
    # range les colonnes en tableaux typés là où la liste gardait un objet
    # Python par cellule. Le lot brut est libéré aussitôt, et seuls les
    # DataFrames compacts s'accumulent jusqu'à la concaténation finale.
    batch_size = 10_000
    morceaux = []
    for i in range(0, total, batch_size):
        batch = text_df.iloc[i:i + batch_size]
        batch_results = batch[text_col].apply(process_message)
        morceaux.append(pd.DataFrame(batch_results.tolist(), index=batch.index))
        del batch_results
        if (i // batch_size) % 5 == 0:
            print(f"  Progress: {min(i+batch_size, total):,}/{total:,}")

    # Assign results back
    result_df = pd.concat(morceaux) if morceaux else pd.DataFrame(index=text_df.index)
    del morceaux
    for col in result_df.columns:
        df.loc[text_mask, col] = result_df[col]
    del result_df

    print("NLP enrichment complete.")
    return df


# ─────────────────────────────────────────────
# AGGREGATE SIGNAL STATS
# ─────────────────────────────────────────────

def compute_signal_stats(df: pd.DataFrame) -> pd.DataFrame:
    """
    Daily signal counts + sentiment aggregates.
    Returns a DataFrame indexed by date.
    """
    sig_cols = [c for c in df.columns if c.startswith('signal_')]
    if not sig_cols:
        return pd.DataFrame()

    df_copy = df.copy()
    df_copy['date'] = pd.to_datetime(df_copy['timestamp']).dt.date
    df_copy = df_copy[df_copy['message_type'] == 'text']

    daily = df_copy.groupby('date').agg(
        n_messages=('message_text', 'count'),
        mean_sentiment=('sentiment', 'mean'),
        median_sentiment=('sentiment', 'median'),
        std_sentiment=('sentiment', 'std'),
        n_buy_signals=('signal_ACHETER', 'sum'),
        n_strong_buy=('signal_ACHAT_FORT', 'sum'),
        n_sell_signals=('signal_VENTE', 'sum'),
        n_panic=('signal_PANIQUE', 'sum'),
        n_euphoria=('signal_EUPHORIE', 'sum'),
        n_fomo=('signal_FOMO', 'sum'),
        n_doubt=('signal_DOUTE', 'sum'),
        n_rumor=('signal_RUMEUR', 'sum'),
        n_sarcasm=('is_sarcastic', 'sum'),
        n_with_target=('has_price_target', 'sum'),
    )

    daily['buy_sell_ratio'] = (
        (daily['n_buy_signals'] + daily['n_strong_buy']) /
        (daily['n_sell_signals'] + 1)
    )
    return daily


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────

if __name__ == "__main__":
    import time
    from pathlib import Path

    OUT_DIR = Path("/home/user/-bvc-analyzer/whatsapp_analysis/output")
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    # Load from phase2 if exists, else phase1, else parse
    p2 = OUT_DIR / "phase2_messages.parquet"
    p1 = OUT_DIR / "phase1_messages.parquet"

    if p2.exists():
        print(f"Loading phase2 parquet...")
        df = pd.read_parquet(p2)
    elif p1.exists():
        print(f"Loading phase1 parquet...")
        df = pd.read_parquet(p1)
    else:
        print("No parquet found, parsing from scratch...")
        from whatsapp_analysis.phase1_parser import parse_chat
        df, _ = parse_chat("/home/user/-bvc-analyzer/data/_chat.txt")

    print(f"Loaded {len(df):,} messages.")
    t0 = time.time()
    df = enrich_dataframe(df)
    print(f"Enrichment done in {time.time()-t0:.1f}s")

    # Stats
    text_df = df[df['message_type'] == 'text']
    print(f"\nSignal distribution (text messages: {len(text_df):,}):")
    for sig in ['ACHAT_FORT', 'ACHETER', 'RENFORCEMENT', 'VENTE', 'PANIQUE', 'EUPHORIE', 'FOMO', 'DOUTE', 'RUMEUR', 'IRONIE']:
        col = f'signal_{sig}'
        if col in df.columns:
            n = df[col].sum()
            pct = n / len(text_df) * 100
            print(f"  {sig:<15}: {n:>6,}  ({pct:.1f}%)")

    print(f"\nSentiment distribution:")
    print(df['sentiment_label'].value_counts().to_string())

    print(f"\nSarcasm detected: {df['is_sarcastic'].sum():,}")
    print(f"Messages with price targets: {df['has_price_target'].sum():,}")
    print(f"Messages with tickers (NLP): {df['nlp_tickers'].apply(len).gt(0).sum():,}")

    # Daily stats
    daily_stats = compute_signal_stats(df)
    daily_stats.to_csv(OUT_DIR / "phase3_daily_signals.csv")

    # Save
    df.to_parquet(OUT_DIR / "phase3_messages.parquet", index=False)
    print(f"\nSaved phase3_messages.parquet and phase3_daily_signals.csv")
