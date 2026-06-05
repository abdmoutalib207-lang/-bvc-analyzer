"""
Phase 1 — WhatsApp Chat Parser
Streaming line-by-line parser for 107MB BVC analysis group chat.
Format: [DD/MM/YYYY HH:MM:SS] Author: Message
"""
from __future__ import annotations

import re
import hashlib
import unicodedata
from collections import defaultdict, Counter
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Generator, Iterator, List, Optional, Set, Tuple

import emoji
import pandas as pd

from whatsapp_analysis.config import (
    DEFAULT_CONFIG,
    Config,
    extract_tickers_from_text,
)

# ─────────────────────────────────────────────
# CONSTANTS / REGEX
# ─────────────────────────────────────────────

# Primary line pattern: [DD/MM/YYYY HH:MM:SS] Author: message
LINE_RE = re.compile(
    r'^\[(\d{2}/\d{2}/\d{4} \d{2}:\d{2}:\d{2})\] ([^:]+): (.*)$'
)

# System/event messages (no author colon split — WhatsApp adds ‎ prefix)
SYSTEM_RE = re.compile(
    r'^\[(\d{2}/\d{2}/\d{4} \d{2}:\d{2}:\d{2})\] ([^:]+): ‎(.+)$'
)

# Timestamp-only line (continuation detection)
TIMESTAMP_RE = re.compile(r'^\[\d{2}/\d{2}/\d{4} \d{2}:\d{2}:\d{2}\]')

DATE_FMT = "%d/%m/%Y %H:%M:%S"

# Special message content patterns
DELETED_RE = re.compile(
    r'(Ce message a été supprimé|This message was deleted|'
    r'You deleted this message|Vous avez supprimé ce message)',
    re.IGNORECASE,
)
MEDIA_RE = re.compile(
    r'(image absente|vidéo absente|audio absent|sticker omis|'
    r'<Media omitted>|fichier joint absent|document absent|'
    r'GIF absent|contact partagé)',
    re.IGNORECASE,
)
SYSTEM_EVENT_RE = re.compile(
    r'(a créé ce groupe|a ajouté|a retiré|a quitté|a changé|'
    r'a été ajouté|Messages and calls are end-to-end encrypted|'
    r'Les messages et les appels|Vous avez utilisé un lien|'
    r'a rejoint|administrateur|a épinglé)',
    re.IGNORECASE,
)

URL_RE = re.compile(
    r'https?://[^\s​‬‭‎‏]+', re.IGNORECASE
)
HASHTAG_RE = re.compile(r'#(\w+)')

# Mention patterns
AT_MENTION_RE = re.compile(r'@([\w\.\-]+)')
SI_MENTION_RE = re.compile(r'\b(?:si|ssi|khoya|khouya|3ammi)\s+([\w\.\-]+)', re.IGNORECASE)


# ─────────────────────────────────────────────
# RAW LINE GENERATOR
# ─────────────────────────────────────────────

def _raw_lines(filepath: str) -> Generator[str, None, None]:
    """Yield raw lines from file with UTF-8 handling."""
    with open(filepath, 'r', encoding='utf-8', errors='replace') as fh:
        for line in fh:
            yield line.rstrip('\n')


# ─────────────────────────────────────────────
# MESSAGE ASSEMBLER (multiline)
# ─────────────────────────────────────────────

def _assemble_messages(lines: Iterator[str]) -> Generator[Tuple[str, str, str], None, None]:
    """
    Yield (timestamp_str, author, full_text) tuples.
    Handles multiline messages by accumulating continuation lines.
    """
    current_ts: Optional[str] = None
    current_author: Optional[str] = None
    current_parts: List[str] = []

    for line in lines:
        m = LINE_RE.match(line)
        if m:
            # Flush previous
            if current_ts is not None:
                yield current_ts, current_author, '\n'.join(current_parts)
            current_ts = m.group(1)
            current_author = m.group(2).strip()
            current_parts = [m.group(3)]
        else:
            # Continuation line (no timestamp at start)
            if current_ts is not None and not TIMESTAMP_RE.match(line):
                current_parts.append(line)
            # If line starts with timestamp but doesn't match (malformed), treat as new system
            elif TIMESTAMP_RE.match(line):
                # flush current
                if current_ts is not None:
                    yield current_ts, current_author, '\n'.join(current_parts)
                current_ts = None
                current_author = None
                current_parts = []

    # Final flush
    if current_ts is not None:
        yield current_ts, current_author, '\n'.join(current_parts)


# ─────────────────────────────────────────────
# FIELD EXTRACTORS
# ─────────────────────────────────────────────

def _detect_message_type(text: str) -> str:
    """Classify message as: text, media, deleted, system."""
    if DELETED_RE.search(text):
        return 'deleted'
    if MEDIA_RE.search(text):
        return 'media'
    if SYSTEM_EVENT_RE.search(text):
        return 'system'
    return 'text'


def _extract_urls(text: str) -> List[str]:
    return URL_RE.findall(text)


def _extract_emojis(text: str) -> List[str]:
    """Extract all emoji characters from text."""
    return [ch for ch in text if ch in emoji.EMOJI_DATA]


def _extract_hashtags(text: str) -> List[str]:
    return HASHTAG_RE.findall(text)


def _extract_mentions(text: str) -> List[str]:
    """Extract @mentions and 'si Name' style mentions."""
    at = AT_MENTION_RE.findall(text)
    si = SI_MENTION_RE.findall(text)
    return list(set(at + si))


def _message_fingerprint(author: str, text: str) -> str:
    """MD5 fingerprint for exact dedup."""
    payload = f"{author}||{text.strip().lower()}"
    return hashlib.md5(payload.encode('utf-8', errors='replace')).hexdigest()


def _near_fingerprint(text: str, n: int = 6) -> str:
    """
    Shingle-based near-duplicate fingerprint.
    Split text into word n-grams, hash the sorted set.
    """
    words = text.lower().split()
    if len(words) < n:
        shingles = {' '.join(words)}
    else:
        shingles = {' '.join(words[i:i+n]) for i in range(len(words) - n + 1)}
    combined = '|'.join(sorted(shingles))
    return hashlib.md5(combined.encode('utf-8', errors='replace')).hexdigest()


# ─────────────────────────────────────────────
# SPAM / BOT DETECTION
# ─────────────────────────────────────────────

class SpamBotDetector:
    """
    Stateful detector:
    - Spam: same author, same message text > spam_threshold times
    - Bot: author posts >bot_rate_threshold messages/hour consistently
          (we flag per-message during streaming, finalize after full pass)
    """

    def __init__(self, cfg: Config):
        self.spam_threshold = cfg.spam_threshold
        self.bot_rate = cfg.bot_rate_threshold
        # (author, near_fp) -> count
        self._near_counts: Dict[Tuple[str, str], int] = defaultdict(int)
        # author -> list of datetimes (sliding 1h window)
        self._author_ts: Dict[str, List[datetime]] = defaultdict(list)
        # authors confirmed as bots
        self.bot_authors: Set[str] = set()

    def check_spam(self, author: str, near_fp: str) -> bool:
        key = (author, near_fp)
        self._near_counts[key] += 1
        return self._near_counts[key] > self.spam_threshold

    def update_bot(self, author: str, ts: datetime) -> bool:
        """
        Add timestamp for author, prune window older than 1h,
        return True if current rate exceeds threshold.
        """
        window = self._author_ts[author]
        window.append(ts)
        cutoff = ts - timedelta(hours=1)
        # Keep only last hour
        pruned = [t for t in window if t >= cutoff]
        self._author_ts[author] = pruned
        rate = len(pruned)  # messages in last hour
        if rate > self.bot_rate:
            self.bot_authors.add(author)
            return True
        return False


# ─────────────────────────────────────────────
# ACTIVITY STATS ACCUMULATOR
# ─────────────────────────────────────────────

class ActivityStats:
    """
    Accumulate daily/weekly/monthly/yearly counts.
    Keys: 'total', per-author.
    """

    def __init__(self):
        # daily: {'total': Counter{date: n}, 'Author': Counter{date: n}}
        self.daily: Dict[str, Counter] = defaultdict(Counter)
        self.weekly: Dict[str, Counter] = defaultdict(Counter)
        self.monthly: Dict[str, Counter] = defaultdict(Counter)
        self.yearly: Dict[str, Counter] = defaultdict(Counter)
        self.hourly: Dict[str, Counter] = defaultdict(Counter)
        self.author_total: Counter = Counter()

    def record(self, author: str, ts: datetime) -> None:
        day_key = ts.strftime('%Y-%m-%d')
        week_key = ts.strftime('%Y-W%W')
        month_key = ts.strftime('%Y-%m')
        year_key = ts.strftime('%Y')
        hour_key = f"{day_key}T{ts.hour:02d}"

        for bucket in (author, 'total'):
            self.daily[bucket][day_key] += 1
            self.weekly[bucket][week_key] += 1
            self.monthly[bucket][month_key] += 1
            self.yearly[bucket][year_key] += 1
            self.hourly[bucket][hour_key] += 1

        self.author_total[author] += 1

    def to_dict(self) -> dict:
        return {
            'daily': {k: dict(v) for k, v in self.daily.items()},
            'weekly': {k: dict(v) for k, v in self.weekly.items()},
            'monthly': {k: dict(v) for k, v in self.monthly.items()},
            'yearly': {k: dict(v) for k, v in self.yearly.items()},
            'hourly': {k: dict(v) for k, v in self.hourly.items()},
            'author_total': dict(self.author_total),
        }


# ─────────────────────────────────────────────
# REPLY DETECTION
# ─────────────────────────────────────────────

def _detect_reply_to(text: str, prev_authors: List[str]) -> Optional[str]:
    """
    Heuristic: check @mentions or 'si Name' patterns vs recent authors.
    Returns author name if detected.
    """
    mentions = _extract_mentions(text)
    for mention in mentions:
        # fuzzy match against recent authors
        ml = mention.lower()
        for auth in prev_authors:
            auth_words = auth.lower().replace('~', '').strip().split()
            for w in auth_words:
                if len(w) > 3 and (ml in w or w in ml):
                    return auth
    return None


# ─────────────────────────────────────────────
# MAIN STREAMING PARSER
# ─────────────────────────────────────────────

def parse_chat(
    filepath: str,
    cfg: Config = DEFAULT_CONFIG,
    max_rows: Optional[int] = None,
) -> Tuple[pd.DataFrame, dict]:
    """
    Stream-parse WhatsApp chat file.

    Returns
    -------
    df : pd.DataFrame
        One row per message with all extracted fields.
    activity_stats : dict
        Nested dict with daily/weekly/monthly/yearly/hourly counts.
    """
    detector = SpamBotDetector(cfg)
    stats = ActivityStats()

    seen_exact: Set[str] = set()
    seen_near: Set[str] = set()

    rows: List[dict] = []

    # Rolling window of last 10 authors for reply detection
    recent_authors: List[str] = []

    raw = _raw_lines(filepath)
    assembled = _assemble_messages(raw)

    for ts_str, author, text in assembled:
        # Parse timestamp
        try:
            ts = datetime.strptime(ts_str, DATE_FMT)
        except ValueError:
            continue

        # Clean author name
        author = author.strip().lstrip('~').strip()
        if not author:
            continue

        # Skip if message too short or too long
        text_stripped = text.strip()
        if len(text_stripped) < cfg.min_message_length:
            continue
        if len(text_stripped) > cfg.max_message_length:
            text_stripped = text_stripped[:cfg.max_message_length]

        # Deduplication — exact
        exact_fp = _message_fingerprint(author, text_stripped)
        is_exact_dup = exact_fp in seen_exact
        if not is_exact_dup:
            seen_exact.add(exact_fp)

        # Near-duplicate (skip very short messages from near-dup)
        near_fp = _near_fingerprint(text_stripped) if len(text_stripped) > 30 else exact_fp
        is_near_dup = (near_fp in seen_near) and not is_exact_dup
        if not is_near_dup and len(text_stripped) > 30:
            seen_near.add(near_fp)

        # Spam check
        is_spam = detector.check_spam(author, near_fp)

        # Bot check
        is_bot = detector.update_bot(author, ts)

        # Message type
        msg_type = _detect_message_type(text_stripped)

        # Field extraction (only for non-system messages)
        urls: List[str] = []
        emojis_list: List[str] = []
        hashtags: List[str] = []
        tickers: List[str] = []
        reply_to: Optional[str] = None
        mentions: List[str] = []

        if msg_type in ('text', 'deleted'):
            urls = _extract_urls(text_stripped)
            emojis_list = _extract_emojis(text_stripped)
            hashtags = _extract_hashtags(text_stripped)
            tickers = extract_tickers_from_text(text_stripped)
            mentions = _extract_mentions(text_stripped)
            reply_to = _detect_reply_to(text_stripped, recent_authors[-20:])

        # Update activity stats (count all, mark dups)
        stats.record(author, ts)

        # Build row
        row = {
            'timestamp': ts,
            'date': ts.date(),
            'hour': ts.hour,
            'weekday': ts.weekday(),  # 0=Monday
            'author': author,
            'message_text': text_stripped,
            'message_type': msg_type,
            'char_count': len(text_stripped),
            'word_count': len(text_stripped.split()),
            'reply_to': reply_to,
            'mentions': mentions,
            'urls': urls,
            'emojis': emojis_list,
            'hashtags': hashtags,
            'tickers': tickers,
            'is_exact_dup': is_exact_dup,
            'is_near_dup': is_near_dup,
            'is_spam': is_spam,
            'is_bot_author': is_bot,
            'exact_fingerprint': exact_fp,
            'near_fingerprint': near_fp,
            'has_url': len(urls) > 0,
            'has_emoji': len(emojis_list) > 0,
            'has_ticker': len(tickers) > 0,
            'emoji_count': len(emojis_list),
            'url_count': len(urls),
            'ticker_count': len(tickers),
        }
        rows.append(row)

        # Fast mode: stop after max_rows
        if max_rows and len(rows) >= max_rows:
            break

        # Update recent authors window
        recent_authors.append(author)
        if len(recent_authors) > 50:
            recent_authors.pop(0)

    # Build DataFrame
    df = pd.DataFrame(rows)

    if df.empty:
        return df, stats.to_dict()

    # Set timestamp as index-friendly, keep column too
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    df = df.sort_values('timestamp').reset_index(drop=True)
    df['message_id'] = df.index

    # Post-process: mark bot authors globally
    global_bots = detector.bot_authors
    if global_bots:
        df['is_bot_author'] = df['author'].isin(global_bots)

    return df, stats.to_dict()


# ─────────────────────────────────────────────
# CHUNKED GENERATOR (for downstream memory-efficient processing)
# ─────────────────────────────────────────────

def parse_chat_chunked(
    filepath: str,
    chunk_size: int = 50_000,
    cfg: Config = DEFAULT_CONFIG,
) -> Generator[pd.DataFrame, None, None]:
    """
    Yield DataFrames of ~chunk_size rows for memory-efficient downstream processing.
    Shares a single SpamBotDetector across chunks.
    """
    detector = SpamBotDetector(cfg)
    stats = ActivityStats()
    seen_exact: Set[str] = set()
    seen_near: Set[str] = set()
    recent_authors: List[str] = []
    buffer: List[dict] = []

    raw = _raw_lines(filepath)
    assembled = _assemble_messages(raw)

    for ts_str, author, text in assembled:
        try:
            ts = datetime.strptime(ts_str, DATE_FMT)
        except ValueError:
            continue

        author = author.strip().lstrip('~').strip()
        if not author:
            continue

        text_stripped = text.strip()
        if len(text_stripped) < cfg.min_message_length:
            continue
        if len(text_stripped) > cfg.max_message_length:
            text_stripped = text_stripped[:cfg.max_message_length]

        exact_fp = _message_fingerprint(author, text_stripped)
        is_exact_dup = exact_fp in seen_exact
        if not is_exact_dup:
            seen_exact.add(exact_fp)

        near_fp = _near_fingerprint(text_stripped) if len(text_stripped) > 30 else exact_fp
        is_near_dup = (near_fp in seen_near) and not is_exact_dup
        if not is_near_dup and len(text_stripped) > 30:
            seen_near.add(near_fp)

        is_spam = detector.check_spam(author, near_fp)
        is_bot = detector.update_bot(author, ts)
        msg_type = _detect_message_type(text_stripped)

        urls = _extract_urls(text_stripped) if msg_type == 'text' else []
        emojis_list = _extract_emojis(text_stripped) if msg_type == 'text' else []
        hashtags = _extract_hashtags(text_stripped) if msg_type == 'text' else []
        tickers = extract_tickers_from_text(text_stripped) if msg_type == 'text' else []
        mentions = _extract_mentions(text_stripped) if msg_type == 'text' else []
        reply_to = _detect_reply_to(text_stripped, recent_authors[-20:]) if msg_type == 'text' else None

        stats.record(author, ts)

        row = {
            'timestamp': ts,
            'date': ts.date(),
            'hour': ts.hour,
            'weekday': ts.weekday(),
            'author': author,
            'message_text': text_stripped,
            'message_type': msg_type,
            'char_count': len(text_stripped),
            'word_count': len(text_stripped.split()),
            'reply_to': reply_to,
            'mentions': mentions,
            'urls': urls,
            'emojis': emojis_list,
            'hashtags': hashtags,
            'tickers': tickers,
            'is_exact_dup': is_exact_dup,
            'is_near_dup': is_near_dup,
            'is_spam': is_spam,
            'is_bot_author': is_bot,
            'exact_fingerprint': exact_fp,
            'near_fingerprint': near_fp,
            'has_url': len(urls) > 0,
            'has_emoji': len(emojis_list) > 0,
            'has_ticker': len(tickers) > 0,
            'emoji_count': len(emojis_list),
            'url_count': len(urls),
            'ticker_count': len(tickers),
        }
        buffer.append(row)

        recent_authors.append(author)
        if len(recent_authors) > 50:
            recent_authors.pop(0)

        if len(buffer) >= chunk_size:
            chunk_df = pd.DataFrame(buffer)
            chunk_df['timestamp'] = pd.to_datetime(chunk_df['timestamp'])
            chunk_df = chunk_df.sort_values('timestamp').reset_index(drop=True)
            global_bots = detector.bot_authors
            if global_bots:
                chunk_df['is_bot_author'] = chunk_df['author'].isin(global_bots)
            yield chunk_df
            buffer.clear()

    if buffer:
        chunk_df = pd.DataFrame(buffer)
        chunk_df['timestamp'] = pd.to_datetime(chunk_df['timestamp'])
        chunk_df = chunk_df.sort_values('timestamp').reset_index(drop=True)
        global_bots = detector.bot_authors
        if global_bots:
            chunk_df['is_bot_author'] = chunk_df['author'].isin(global_bots)
        yield chunk_df


# ─────────────────────────────────────────────
# SUMMARY HELPERS
# ─────────────────────────────────────────────

def print_parse_summary(df: pd.DataFrame, activity_stats: dict) -> None:
    """Print a human-readable summary of parsing results."""
    print(f"\n{'='*60}")
    print(f"PARSE SUMMARY")
    print(f"{'='*60}")
    print(f"Total rows parsed      : {len(df):,}")
    print(f"Date range             : {df['timestamp'].min()} → {df['timestamp'].max()}")
    print(f"Unique authors         : {df['author'].nunique():,}")
    print(f"Message types:")
    for mtype, cnt in df['message_type'].value_counts().items():
        print(f"  {mtype:<12}: {cnt:,}")
    print(f"Exact duplicates       : {df['is_exact_dup'].sum():,}")
    print(f"Near duplicates        : {df['is_near_dup'].sum():,}")
    print(f"Spam messages          : {df['is_spam'].sum():,}")
    bot_authors = df[df['is_bot_author']]['author'].nunique()
    print(f"Bot authors detected   : {bot_authors}")
    print(f"Messages with tickers  : {df['has_ticker'].sum():,}")
    print(f"Messages with URLs     : {df['has_url'].sum():,}")
    top_authors = activity_stats['author_total']
    top5 = sorted(top_authors.items(), key=lambda x: x[1], reverse=True)[:5]
    print(f"\nTop 5 authors by volume:")
    for auth, cnt in top5:
        print(f"  {auth[:40]:<40}: {cnt:,}")
    print(f"{'='*60}\n")


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    import time

    CHAT_FILE = "/home/user/-bvc-analyzer/data/_chat.txt"

    print(f"Parsing: {CHAT_FILE}")
    t0 = time.time()
    df, activity_stats = parse_chat(CHAT_FILE)
    elapsed = time.time() - t0
    print(f"Parsed {len(df):,} messages in {elapsed:.1f}s")

    print_parse_summary(df, activity_stats)

    # Save sample output
    out_dir = Path("/home/user/-bvc-analyzer/whatsapp_analysis/output")
    out_dir.mkdir(parents=True, exist_ok=True)

    df.to_parquet(out_dir / "phase1_messages.parquet", index=False)
    print(f"Saved parquet: {out_dir / 'phase1_messages.parquet'}")

    import json
    with open(out_dir / "phase1_activity_stats.json", 'w', encoding='utf-8') as f:
        json.dump(activity_stats, f, ensure_ascii=False, indent=2)
    print(f"Saved activity stats: {out_dir / 'phase1_activity_stats.json'}")

    # Show sample rows
    print("\nSample rows (first 3 text messages with tickers):")
    sample = df[(df['message_type'] == 'text') & (df['has_ticker'])].head(3)
    for _, row in sample.iterrows():
        print(f"  [{row['timestamp']}] {row['author'][:30]}: {row['message_text'][:80]}...")
        print(f"    Tickers: {row['tickers']}")
