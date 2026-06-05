#!/usr/bin/env python3
"""
BVC WhatsApp NLP Analysis — 14 Phases
Analyse 1.2M+ messages du groupe investisseurs BVC (6 ans)
"""

import re
import os
import sys
import json
import math
import zipfile
import logging
import warnings
import argparse
from pathlib import Path
from datetime import datetime, timedelta
from collections import defaultdict, Counter
from typing import Optional

import numpy as np
import pandas as pd
from scipy import stats
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import TimeSeriesSplit, cross_val_score
from sklearn.metrics import classification_report
import networkx as nx

warnings.filterwarnings("ignore")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("BVC_NLP")

# ═══════════════════════════════════════════════════════════════
# CONFIGURATION
# ═══════════════════════════════════════════════════════════════

TICKERS_NLP = [
    "CMT","SMI","CASH","MNG","AKD","SOT","SGTM","MSA","CFGB","RIS",
    "ADI","VCNE","CMGP","CSR","TGCC","ADH","SRM","SNA","RDS"
]

TICKER_ALIASES = {
    # Ticker → liste de patterns reconnus dans les messages
    "CMT":  ["CMT","ciment maroc","cimenterie"],
    "SMI":  ["SMI","sonasid","acier"],
    "CASH": ["CASH","casablanca finance","CFG Bank"],
    "MNG":  ["MNG","managem","mines"],
    "AKD":  ["AKD","akdital","clinique","hôpital"],
    "SOT":  ["SOT","sothema","pharma","médicament"],
    "SGTM": ["SGTM","gestion","travaux"],
    "MSA":  ["MSA","marsa","port","tanger"],
    "CFGB": ["CFGB","CFG","banque"],
    "RIS":  ["RIS","risma","hôtel","accor"],
    "ADI":  ["ADI","addoha","immobilier","promoteur"],
    "VCNE": ["VCNE","valuecom","vente","distribution"],
    "CMGP": ["CMGP","groupe","mutualiste"],
    "CSR":  ["CSR","crédit","crédit du maroc"],
    "TGCC": ["TGCC","TGCC","construction"],
    "ADH":  ["ADH","alliances","développement"],
    "SRM":  ["SRM","sanlam","assurance"],
    "SNA":  ["SNA","sna","câble"],
    "RDS":  ["RDS","residences","dar"],
}

# Lexique BUY/SELL — FR + AR + Darija + Arabizi
BUY_SIGNALS = [
    # Français
    "acheter","achat","à l'achat","rentrer","entrée","prendre","position longue",
    "hausse","rebond","potentiel","cible","objectif prix","tp","target","bull",
    "haussier","momentum positif","signal d'achat","recommande","investir",
    "accumul","renforcer","DCA","point d'entrée","cassure haussière","gap up",
    "dépassement","franchissement","support tenu","rebond technique",
    # Arabe standard
    "شراء","اشتري","فرصة","صعود","ارتفاع","توصية شراء","هدف سعري",
    # Darija / Arabizi
    "chri","chri had","dkhl","dakhl","frsah","forsa","zid","kolchi mezyan",
    "mzyan","buy","long","bullish","moon","rocket","pump","hodl",
]

SELL_SIGNALS = [
    # Français
    "vendre","vente","sortir","clôturer","couper","stop loss","sl","baisse",
    "chute","recul","risque","prudence","attendre","éviter","short","bear",
    "baissier","pression vendeuse","signal de vente","résistance","sortie",
    "correction","consolidation","gap down","cassure baissière",
    # Arabe
    "بيع","بيع الآن","تراجع","انخفاض","احذر","مخاطرة",
    # Darija
    "bi3","khrj","khouj","khas tsali","dir stop","dump","sell","short","bearish",
]

UNCERTAINTY_SIGNALS = [
    "peut-être","si","attends","wait","nchallah","inshallah","wallah",
    "je sais pas","chkun yarf","?","sais pas","à surveiller",
]

CHAT_PATH = Path("/home/user/-bvc-analyzer/data/_chat.txt")
CHAT_ZIP  = Path("/home/user/-bvc-analyzer/data/chat.zip")
OUT_DIR   = Path("/home/user/-bvc-analyzer/data/nlp_output")
OUT_DIR.mkdir(parents=True, exist_ok=True)

# ═══════════════════════════════════════════════════════════════
# PHASE 1 — DATA ENGINEERING
# ═══════════════════════════════════════════════════════════════

def load_chat_file() -> list[str]:
    """Load raw lines from _chat.txt or chat.zip."""
    if CHAT_PATH.exists() and CHAT_PATH.stat().st_size > 1000:
        log.info(f"Lecture {CHAT_PATH} ({CHAT_PATH.stat().st_size/1e6:.1f} MB)")
        with open(CHAT_PATH, encoding="utf-8", errors="replace") as f:
            return f.readlines()

    if CHAT_ZIP.exists() and CHAT_ZIP.stat().st_size > 1000:
        log.info(f"Décompression {CHAT_ZIP} ({CHAT_ZIP.stat().st_size/1e6:.1f} MB)")
        with zipfile.ZipFile(CHAT_ZIP, "r") as z:
            names = z.namelist()
            txt_files = [n for n in names if n.endswith(".txt")]
            if not txt_files:
                raise FileNotFoundError("Pas de .txt dans le zip")
            target = txt_files[0]
            log.info(f"  → {target}")
            with z.open(target) as f:
                return f.read().decode("utf-8", errors="replace").splitlines(keepends=True)

    raise FileNotFoundError(
        "Fichier chat introuvable.\n"
        "Veuillez placer _chat.txt ou chat.zip dans /home/user/-bvc-analyzer/data/"
    )


# WhatsApp export format patterns
# iOS:  DD/MM/YYYY HH:MM:SS — Nom: message
# Android: DD/MM/YYYY, HH:MM - Nom: message
# Android v2: [DD/MM/YYYY, HH:MM:SS] Nom: message
WHATSAPP_PATTERNS = [
    # iOS
    re.compile(r"^(\d{1,2}/\d{1,2}/\d{2,4}),?\s+(\d{1,2}:\d{2}(?::\d{2})?)\s*[-–]\s*(.+?):\s*(.*)$"),
    # Android bracket
    re.compile(r"^\[(\d{1,2}/\d{1,2}/\d{2,4}),?\s+(\d{1,2}:\d{2}(?::\d{2})?)\]\s*(.+?):\s*(.*)$"),
]


def parse_whatsapp(lines: list[str]) -> pd.DataFrame:
    """Parse WhatsApp export → DataFrame."""
    log.info(f"Phase 1 — Parsing {len(lines):,} lignes brutes…")

    records = []
    current = None
    n_cont = 0  # continuation lines

    for line in lines:
        line = line.rstrip("\n\r")
        matched = False
        for pat in WHATSAPP_PATTERNS:
            m = pat.match(line)
            if m:
                if current:
                    records.append(current)
                date_str, time_str, sender, text = m.groups()
                # Parse date
                try:
                    ts = datetime.strptime(f"{date_str} {time_str}", "%d/%m/%Y %H:%M:%S")
                except ValueError:
                    try:
                        ts = datetime.strptime(f"{date_str} {time_str}", "%d/%m/%Y %H:%M")
                    except ValueError:
                        try:
                            ts = datetime.strptime(f"{date_str} {time_str}", "%d/%m/%y %H:%M")
                        except ValueError:
                            ts = None
                current = {
                    "ts": ts,
                    "sender": sender.strip(),
                    "text": text.strip(),
                }
                matched = True
                break

        if not matched and current and line.strip():
            # Continuation of previous message
            current["text"] += " " + line.strip()
            n_cont += 1

    if current:
        records.append(current)

    df = pd.DataFrame(records)
    if df.empty:
        raise ValueError("Aucun message parsé — vérifier le format du fichier")

    df = df.dropna(subset=["ts"])
    df["ts"] = pd.to_datetime(df["ts"])
    df = df.sort_values("ts").reset_index(drop=True)

    # Remove system messages
    system_keywords = ["a ajouté","a quitté","a été ajouté","Messages chiffrés","image omise",
                       "vidéo omise","audio omis","GIF omis","document omis","<Media omitted>",
                       "Messages and calls are end-to-end","changed the subject","added","left",
                       "joined using","security code changed"]
    mask_system = df["sender"].str.contains("|".join(system_keywords[:3]), case=False, na=False) | \
                  df["text"].str.contains("|".join(system_keywords[3:]), case=False, na=False)
    n_sys = mask_system.sum()
    df = df[~mask_system].reset_index(drop=True)

    # Add derived columns
    df["date"] = df["ts"].dt.date
    df["hour"] = df["ts"].dt.hour
    df["dow"]  = df["ts"].dt.dayofweek  # 0=Mon
    df["year"] = df["ts"].dt.year
    df["month"] = df["ts"].dt.to_period("M")
    df["text_lower"] = df["text"].str.lower().fillna("")
    df["msg_len"] = df["text"].str.len()

    log.info(f"  ✓ {len(df):,} messages valides ({n_sys} system, {n_cont} continuation lines)")
    log.info(f"  ✓ Période: {df['ts'].min().date()} → {df['ts'].max().date()}")
    log.info(f"  ✓ Membres uniques: {df['sender'].nunique()}")

    return df


# ═══════════════════════════════════════════════════════════════
# PHASE 2 — DÉTECTION MULTILINGUISTIQUE
# ═══════════════════════════════════════════════════════════════

ARABIC_RE  = re.compile(r"[؀-ۿݐ-ݿ]")
FRENCH_RE  = re.compile(r"\b(le|la|les|de|du|des|un|une|et|je|tu|il|nous|vous|ils|est|sont|avoir|être|avec|pour|dans|par|sur|qui|que|je|si|mais|ou|donc|car|ni|or)\b", re.I)
ENGLISH_RE = re.compile(r"\b(the|and|is|are|was|were|be|been|have|has|had|do|does|did|will|would|could|should|may|might|can|this|that|with|for|from|not|but|what|when|where|how)\b", re.I)
DARIJA_RE  = re.compile(r"\b(wach|ola|daba|hna|nta|ana|huwa|mashi|zwine|bghit|dir|gal|khas|nchallah|wallah|bzaf|shwiya|kayn|fiha|taman|blah)\b", re.I)
ARABIZI_RE = re.compile(r"\b(lol|haha|7|3|5|9|2|chri|bi3|khrj|fiha|mzyan|sahha|tbark|allah|walit)\b", re.I)


def detect_language(text: str) -> str:
    t = text.lower()
    ar = len(ARABIC_RE.findall(t))
    fr = len(FRENCH_RE.findall(t))
    en = len(ENGLISH_RE.findall(t))
    da = len(DARIJA_RE.findall(t))
    az = len(ARABIZI_RE.findall(t))

    scores = {"arabic": ar*2, "french": fr, "english": en, "darija": da*1.5, "arabizi": az}
    best = max(scores, key=scores.get)
    if scores[best] == 0:
        return "other"
    return best


def phase2_language(df: pd.DataFrame) -> pd.DataFrame:
    log.info("Phase 2 — Détection linguistique…")
    df["lang"] = df["text"].apply(detect_language)

    dist = df["lang"].value_counts(normalize=True).mul(100).round(1)
    log.info(f"  Distribution linguistique:\n{dist.to_string()}")

    return df


# ═══════════════════════════════════════════════════════════════
# PHASE 3 — NLP : SIGNALS, NER, PRICE TARGETS
# ═══════════════════════════════════════════════════════════════

PRICE_RE   = re.compile(r"\b(\d{2,4}(?:[.,]\d{1,2})?)\s*(dh|mad|dhs|dirham|pts|point)?\b", re.I)
TARGET_RE  = re.compile(r"(?:cible|objectif|tp|target|vise|atteindre|direction)\s+(?:à|de|:|=)?\s*(\d{2,4}(?:[.,]\d{1,2})?)", re.I)
PCTCHG_RE  = re.compile(r"([+-]?\d{1,3}(?:[.,]\d{1,2})?)\s*%")


def score_signal(text: str, ticker: str | None = None) -> dict:
    tl = text.lower()

    buy_hits  = sum(1 for w in BUY_SIGNALS if w.lower() in tl)
    sell_hits = sum(1 for w in SELL_SIGNALS if w.lower() in tl)
    unc_hits  = sum(1 for w in UNCERTAINTY_SIGNALS if w.lower() in tl)

    # Price targets
    targets = [float(m.replace(",",".")) for m in TARGET_RE.findall(text) if m]
    prices_mentioned = [float(m[0].replace(",",".")) for m in PRICE_RE.findall(text)
                        if 10 <= float(m[0].replace(",",".")) <= 50000]
    pct_changes = [float(m.replace(",",".")) for m in PCTCHG_RE.findall(text)]

    raw = buy_hits - sell_hits - 0.5 * unc_hits
    if buy_hits == 0 and sell_hits == 0:
        sentiment = "neutral"
        score = 0.0
    elif raw > 0:
        sentiment = "buy"
        score = min(raw / 3, 1.0)
    elif raw < 0:
        sentiment = "sell"
        score = max(raw / 3, -1.0)
    else:
        sentiment = "neutral"
        score = 0.0

    return {
        "sentiment": sentiment,
        "score": round(score, 3),
        "buy_hits": buy_hits,
        "sell_hits": sell_hits,
        "uncertainty": unc_hits > 0,
        "price_targets": targets[:3],
        "prices_mentioned": prices_mentioned[:5],
        "pct_changes": pct_changes[:3],
    }


def find_tickers_in_message(text: str) -> list[str]:
    tl = text.lower()
    found = []
    for ticker, aliases in TICKER_ALIASES.items():
        for alias in aliases:
            if alias.lower() in tl:
                found.append(ticker)
                break
    return list(set(found))


def phase3_nlp(df: pd.DataFrame) -> pd.DataFrame:
    log.info("Phase 3 — NLP signals + NER…")

    signals = df["text"].apply(score_signal)
    df["sentiment"]    = signals.apply(lambda x: x["sentiment"])
    df["nlp_score"]    = signals.apply(lambda x: x["score"])
    df["buy_hits"]     = signals.apply(lambda x: x["buy_hits"])
    df["sell_hits"]    = signals.apply(lambda x: x["sell_hits"])
    df["uncertain"]    = signals.apply(lambda x: x["uncertainty"])
    df["price_targets"] = signals.apply(lambda x: x["price_targets"])
    df["prices_mentioned"] = signals.apply(lambda x: x["prices_mentioned"])
    df["pct_changes"]  = signals.apply(lambda x: x["pct_changes"])

    df["tickers_mentioned"] = df["text"].apply(find_tickers_in_message)
    df["n_tickers"] = df["tickers_mentioned"].apply(len)

    n_buy  = (df["sentiment"]=="buy").sum()
    n_sell = (df["sentiment"]=="sell").sum()
    n_neu  = (df["sentiment"]=="neutral").sum()
    log.info(f"  Signaux: BUY={n_buy:,} SELL={n_sell:,} NEUTRAL={n_neu:,}")
    log.info(f"  Mentions ticker: {df['n_tickers'].sum():,} ({df['n_tickers'].gt(0).sum():,} messages)")

    return df


# ═══════════════════════════════════════════════════════════════
# PHASE 4 — BEHAVIORAL FINANCE : FEAR & GREED INDEX BVC
# ═══════════════════════════════════════════════════════════════

def compute_fear_greed_index(df: pd.DataFrame) -> pd.DataFrame:
    log.info("Phase 4 — Fear & Greed Index BVC…")

    daily = df.groupby("date").agg(
        n_msgs=("text","count"),
        buy_sum=("buy_hits","sum"),
        sell_sum=("sell_hits","sum"),
        avg_nlp=("nlp_score","mean"),
        n_buy=("sentiment", lambda x: (x=="buy").sum()),
        n_sell=("sentiment", lambda x: (x=="sell").sum()),
    ).reset_index()

    daily["bull_ratio"] = daily["n_buy"] / (daily["n_buy"] + daily["n_sell"] + 1)
    daily["activity"]   = np.log1p(daily["n_msgs"])

    # Normalise 0-100
    def norm(s):
        mn, mx = s.min(), s.max()
        if mx == mn:
            return pd.Series(50, index=s.index)
        return (s - mn) / (mx - mn) * 100

    daily["fg_sentiment"] = norm(daily["bull_ratio"])
    daily["fg_activity"]  = norm(daily["activity"])
    daily["fg_raw"]       = norm(daily["avg_nlp"].clip(-1,1))

    daily["fear_greed"] = (
        0.50 * daily["fg_sentiment"] +
        0.30 * daily["fg_raw"] +
        0.20 * daily["fg_activity"]
    ).round(1)

    daily["fg_label"] = pd.cut(
        daily["fear_greed"],
        bins=[0, 20, 40, 60, 80, 100],
        labels=["Extrême Peur","Peur","Neutre","Greed","Extrême Greed"],
        include_lowest=True
    )

    log.info(f"  Fear&Greed moyen: {daily['fear_greed'].mean():.1f}")
    log.info(f"  Distribution:\n{daily['fg_label'].value_counts().to_string()}")

    daily.to_csv(OUT_DIR / "fear_greed_daily.csv", index=False)
    return daily


# ═══════════════════════════════════════════════════════════════
# PHASE 5 — SMART MONEY IDENTIFICATION
# ═══════════════════════════════════════════════════════════════

def compute_smart_money(df: pd.DataFrame, fg_daily: pd.DataFrame) -> pd.DataFrame:
    log.info("Phase 5 — Smart Money identification…")

    # Per-member stats
    members = df.groupby("sender").agg(
        n_msgs=("text","count"),
        n_buy=("sentiment", lambda x: (x=="buy").sum()),
        n_sell=("sentiment", lambda x: (x=="sell").sum()),
        n_neutral=("sentiment", lambda x: (x=="neutral").sum()),
        avg_score=("nlp_score","mean"),
        n_with_ticker=("n_tickers", lambda x: (x>0).sum()),
        unique_tickers=("tickers_mentioned", lambda x: len(set(t for ts in x for t in ts))),
        avg_msg_len=("msg_len","mean"),
        first_seen=("ts","min"),
        last_seen=("ts","max"),
    ).reset_index()

    members["activity_days"] = (members["last_seen"] - members["first_seen"]).dt.days + 1
    members["msgs_per_day"] = (members["n_msgs"] / members["activity_days"]).round(2)
    members["signal_rate"] = (
        (members["n_buy"] + members["n_sell"]) / (members["n_msgs"] + 1)
    ).round(3)
    members["buy_rate"] = (members["n_buy"] / (members["n_buy"] + members["n_sell"] + 1)).round(3)

    # Confidence score (proxy for alpha — needs price correlation in Phase 8)
    members["influence_score"] = (
        0.3 * (members["n_msgs"] / members["n_msgs"].max()) +
        0.2 * members["signal_rate"] +
        0.2 * (members["unique_tickers"] / (TICKERS_NLP.__len__() + 1)) +
        0.15 * (members["avg_msg_len"] / members["avg_msg_len"].max()).clip(0,1) +
        0.15 * (members["activity_days"] / members["activity_days"].max())
    ).round(3)

    members = members.sort_values("influence_score", ascending=False)
    top_smart = members.head(10)

    log.info(f"  Top 5 Smart Money (par influence_score):")
    for _, r in top_smart.head(5).iterrows():
        log.info(f"    {r['sender'][:20]:20s} msgs={r['n_msgs']:4d} buy_rate={r['buy_rate']:.2f} influence={r['influence_score']:.3f}")

    members.to_csv(OUT_DIR / "smart_money.csv", index=False)
    return members


# ═══════════════════════════════════════════════════════════════
# PHASE 6 — NETWORK ANALYSIS
# ═══════════════════════════════════════════════════════════════

def phase6_network(df: pd.DataFrame) -> dict:
    log.info("Phase 6 — Analyse réseau (graphe de mentions)…")

    # Build co-activity graph: edge between two senders if they both sent in same 10-min window
    df_sorted = df.sort_values("ts")
    edges = defaultdict(int)

    window = timedelta(minutes=10)
    idx_list = list(range(len(df_sorted)))
    senders  = df_sorted["sender"].values
    times    = df_sorted["ts"].values

    for i, (t_i, s_i) in enumerate(zip(times, senders)):
        for j in range(i+1, min(i+50, len(times))):
            t_j = times[j]
            if pd.Timestamp(t_j) - pd.Timestamp(t_i) > window:
                break
            s_j = senders[j]
            if s_i != s_j:
                key = tuple(sorted([s_i, s_j]))
                edges[key] += 1

    G = nx.Graph()
    for (a, b), w in edges.items():
        if w >= 3:  # minimum interaction threshold
            G.add_edge(a, b, weight=w)

    centrality = nx.degree_centrality(G)
    betweenness = nx.betweenness_centrality(G, normalized=True, k=min(100, len(G)))
    communities = list(nx.community.greedy_modularity_communities(G))

    net_stats = {
        "nodes": G.number_of_nodes(),
        "edges": G.number_of_edges(),
        "density": round(nx.density(G), 4),
        "n_communities": len(communities),
        "top_central": sorted(centrality.items(), key=lambda x: -x[1])[:5],
        "top_betweenness": sorted(betweenness.items(), key=lambda x: -x[1])[:5],
    }

    log.info(f"  Graphe: {net_stats['nodes']} noeuds, {net_stats['edges']} arêtes")
    log.info(f"  Densité: {net_stats['density']:.4f}")
    log.info(f"  {net_stats['n_communities']} communautés détectées")

    # Save
    with open(OUT_DIR / "network_stats.json", "w") as f:
        json.dump({k: v for k,v in net_stats.items() if k != "top_central"}, f, indent=2)

    return net_stats


# ═══════════════════════════════════════════════════════════════
# PHASE 7 — STOCK PICKING SCORES
# ═══════════════════════════════════════════════════════════════

def phase7_stock_picking(df: pd.DataFrame) -> pd.DataFrame:
    log.info("Phase 7 — Stock Picking scores par ticker…")

    msgs_with_ticker = df[df["n_tickers"] > 0].copy()

    rows = []
    for ticker in TICKERS_NLP:
        mask = msgs_with_ticker["tickers_mentioned"].apply(lambda ts: ticker in ts)
        sub = msgs_with_ticker[mask]
        if len(sub) == 0:
            continue

        n_total  = len(sub)
        n_buy    = (sub["sentiment"] == "buy").sum()
        n_sell   = (sub["sentiment"] == "sell").sum()
        n_neu    = (sub["sentiment"] == "neutral").sum()
        avg_score = sub["nlp_score"].mean()
        n_targets = sub["price_targets"].apply(len).sum()
        unique_authors = sub["sender"].nunique()
        n_months = sub["month"].nunique()

        # Conviction = ratio BUY / (BUY+SELL)
        conviction = n_buy / (n_buy + n_sell + 1)
        # Diversité = auteurs uniques (évite le biais d'un seul influenceur)
        diversity  = min(unique_authors / 10, 1.0)
        # Persistence = activité sur plusieurs mois
        persistence = min(n_months / 24, 1.0)
        # Signal strength = moyenne nlp_score
        strength = (avg_score + 1) / 2  # normalise -1..1 → 0..1

        nlp_score_final = (
            0.40 * conviction +
            0.25 * strength +
            0.20 * diversity +
            0.15 * persistence
        ) * 100

        rows.append({
            "ticker": ticker,
            "n_msgs": n_total,
            "n_buy": n_buy,
            "n_sell": n_sell,
            "n_neutral": n_neu,
            "avg_nlp": round(avg_score, 3),
            "n_price_targets": int(n_targets),
            "unique_authors": unique_authors,
            "n_months_active": n_months,
            "conviction": round(conviction, 3),
            "diversity_score": round(diversity, 3),
            "persistence_score": round(persistence, 3),
            "nlp_score": round(nlp_score_final, 1),
            "signal": "BUY" if conviction > 0.6 else ("SELL" if conviction < 0.4 else "HOLD"),
        })

    stock_df = pd.DataFrame(rows).sort_values("nlp_score", ascending=False)
    log.info(f"  Résultats stock picking ({len(stock_df)} tickers):")
    for _, r in stock_df.iterrows():
        bar = "█" * int(r["nlp_score"] / 5)
        log.info(f"  {r['ticker']:6s} [{r['signal']:4s}] {bar:20s} {r['nlp_score']:.1f} (n={r['n_msgs']})")

    stock_df.to_csv(OUT_DIR / "stock_picking.csv", index=False)
    return stock_df


# ═══════════════════════════════════════════════════════════════
# PHASE 8 — CORRÉLATION AVEC PRIX BVC
# ═══════════════════════════════════════════════════════════════

def load_financial_data() -> dict:
    fp = Path("/home/user/-bvc-analyzer/financial_data.json")
    if fp.exists():
        with open(fp) as f:
            return json.load(f)
    return {}


def phase8_market_correlation(df: pd.DataFrame, stock_df: pd.DataFrame) -> dict:
    log.info("Phase 8 — Corrélation NLP ↔ Marché BVC…")

    fin = load_financial_data()
    correlations = {}

    for ticker in TICKERS_NLP:
        # Get price history from financial_data.json
        tdata = fin.get("data", {}).get(ticker, {})
        history = tdata.get("history", [])
        if len(history) < 30:
            continue

        prices = pd.DataFrame(history)
        if "date" not in prices.columns or "close" not in prices.columns:
            continue

        prices["date"] = pd.to_datetime(prices["date"]).dt.date
        prices = prices.set_index("date").sort_index()
        prices["ret"] = prices["close"].pct_change()

        # Daily NLP signal for this ticker
        mask = df["tickers_mentioned"].apply(lambda ts: ticker in ts)
        sub = df[mask].copy()
        if len(sub) < 10:
            continue

        daily_nlp = sub.groupby("date")["nlp_score"].mean()

        # Align
        common = prices.index.intersection(daily_nlp.index)
        if len(common) < 10:
            continue

        px = prices.loc[common, "ret"].fillna(0)
        nl = daily_nlp.loc[common]

        # Contemporaneous correlation
        corr_0, pval_0 = stats.pearsonr(nl.values, px.values)

        # Lead-lag: does NLP predict next-day return?
        nlp_series = nl.values[:-1]
        ret_series = px.values[1:]
        if len(nlp_series) >= 5:
            corr_1, pval_1 = stats.pearsonr(nlp_series, ret_series)
        else:
            corr_1, pval_1 = 0, 1

        correlations[ticker] = {
            "corr_same_day": round(corr_0, 3),
            "pval_same_day": round(pval_0, 4),
            "corr_lead_1d": round(corr_1, 3),
            "pval_lead_1d": round(pval_1, 4),
            "n_obs": len(common),
            "predictive": abs(corr_1) > 0.15 and pval_1 < 0.1,
        }
        log.info(f"  {ticker}: corr_0={corr_0:+.3f} corr_lead1={corr_1:+.3f} (p={pval_1:.3f}) {'✓ predictif' if correlations[ticker]['predictive'] else ''}")

    with open(OUT_DIR / "correlations.json", "w") as f:
        json.dump(correlations, f, indent=2)

    predictive_count = sum(1 for v in correlations.values() if v.get("predictive"))
    log.info(f"  {predictive_count}/{len(correlations)} tickers avec signal NLP prédictif")
    return correlations


# ═══════════════════════════════════════════════════════════════
# PHASE 9 — ML MODELS (RF + GBM + LOGIT)
# ═══════════════════════════════════════════════════════════════

def build_ml_features(df: pd.DataFrame) -> pd.DataFrame:
    """Aggregate daily NLP features for ML."""
    feats = df.groupby("date").agg(
        n_msgs=("text","count"),
        n_buy=("sentiment", lambda x: (x=="buy").sum()),
        n_sell=("sentiment", lambda x: (x=="sell").sum()),
        avg_score=("nlp_score","mean"),
        std_score=("nlp_score","std"),
        n_with_ticker=("n_tickers", lambda x: (x>0).sum()),
        unique_senders=("sender","nunique"),
        avg_len=("msg_len","mean"),
        n_uncertain=("uncertain","sum"),
    ).fillna(0)

    feats["bull_ratio"] = feats["n_buy"] / (feats["n_buy"] + feats["n_sell"] + 1)
    feats["activity_log"] = np.log1p(feats["n_msgs"])
    feats["ticker_density"] = feats["n_with_ticker"] / (feats["n_msgs"] + 1)
    feats["uncertainty_ratio"] = feats["n_uncertain"] / (feats["n_msgs"] + 1)
    # Rolling features
    for col in ["bull_ratio","avg_score","activity_log"]:
        feats[f"{col}_ma5"] = feats[col].rolling(5, min_periods=1).mean()
        feats[f"{col}_ma20"] = feats[col].rolling(20, min_periods=1).mean()

    return feats


def phase9_ml_models(df: pd.DataFrame, correlations: dict) -> dict:
    log.info("Phase 9 — ML Models…")

    feats = build_ml_features(df)
    fin   = load_financial_data()

    results = {}
    feature_cols = [c for c in feats.columns if c not in ["n_msgs","n_buy","n_sell"]]

    for ticker in TICKERS_NLP:
        tdata = fin.get("data", {}).get(ticker, {})
        history = tdata.get("history", [])
        if len(history) < 60:
            continue

        prices = pd.DataFrame(history)
        if "date" not in prices.columns or "close" not in prices.columns:
            continue

        prices["date"] = pd.to_datetime(prices["date"]).dt.date
        prices = prices.set_index("date").sort_index()
        prices["ret"] = prices["close"].pct_change()
        prices["target"] = (prices["ret"].shift(-1) > 0).astype(int)  # next-day up/down

        # Align
        common = feats.index.intersection(prices.index)
        if len(common) < 50:
            continue

        X = feats.loc[common, feature_cols].values
        y = prices.loc[common, "target"].values

        # Remove NaN
        mask = ~(np.isnan(X).any(axis=1) | np.isnan(y))
        X, y = X[mask], y[mask]
        if len(X) < 40:
            continue

        scaler = StandardScaler()
        X_sc = scaler.fit_transform(X)

        # Time-series CV (no future leakage)
        tscv = TimeSeriesSplit(n_splits=5)

        models = {
            "RandomForest": RandomForestClassifier(n_estimators=100, max_depth=5, random_state=42),
            "GBM":          GradientBoostingClassifier(n_estimators=100, max_depth=3, random_state=42),
            "Logistic":     LogisticRegression(max_iter=500, random_state=42),
        }

        ticker_results = {}
        for name, model in models.items():
            X_in = X_sc if name == "Logistic" else X
            cv_scores = cross_val_score(model, X_in, y, cv=tscv, scoring="accuracy")
            ticker_results[name] = {
                "cv_mean": round(cv_scores.mean(), 3),
                "cv_std":  round(cv_scores.std(), 3),
            }

        best_model = max(ticker_results, key=lambda k: ticker_results[k]["cv_mean"])
        best_acc   = ticker_results[best_model]["cv_mean"]

        results[ticker] = {
            "models": ticker_results,
            "best_model": best_model,
            "best_accuracy": best_acc,
            "n_samples": len(X),
        }
        log.info(f"  {ticker}: {best_model} acc={best_acc:.3f} (n={len(X)})")

    with open(OUT_DIR / "ml_results.json", "w") as f:
        json.dump(results, f, indent=2)

    return results


# ═══════════════════════════════════════════════════════════════
# PHASE 10 — TOPIC MODELING (LDA light)
# ═══════════════════════════════════════════════════════════════

def simple_lda_topics(texts: list[str], n_topics: int = 8) -> list[list[str]]:
    """Lightweight keyword-based topic extraction (no transformers required)."""
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.decomposition import NMF

    vectorizer = TfidfVectorizer(
        max_features=500,
        min_df=5,
        max_df=0.95,
        ngram_range=(1,2),
        token_pattern=r"(?u)\b[a-zA-Z؀-ۿ]{3,}\b"
    )
    try:
        X = vectorizer.fit_transform(texts)
    except Exception:
        return []

    nmf = NMF(n_components=n_topics, random_state=42, max_iter=200)
    nmf.fit(X)

    feat_names = vectorizer.get_feature_names_out()
    topics = []
    for comp in nmf.components_:
        top_idx = comp.argsort()[-10:][::-1]
        topics.append([feat_names[i] for i in top_idx])

    return topics


def phase10_topics(df: pd.DataFrame) -> list:
    log.info("Phase 10 — Topic Modeling (NMF)…")

    texts = df["text"].dropna().tolist()
    topics = simple_lda_topics(texts, n_topics=10)

    for i, t in enumerate(topics[:10]):
        log.info(f"  Topic {i+1}: {', '.join(t[:7])}")

    with open(OUT_DIR / "topics.json", "w") as f:
        json.dump({"topics": topics}, f, ensure_ascii=False, indent=2)

    return topics


# ═══════════════════════════════════════════════════════════════
# PHASE 11 — BACKTESTING QUANTITATIF
# ═══════════════════════════════════════════════════════════════

def phase11_backtest(stock_df: pd.DataFrame, correlations: dict) -> dict:
    log.info("Phase 11 — Backtesting quantitatif…")

    fin = load_financial_data()
    bt_results = {}

    for _, row in stock_df.iterrows():
        ticker = row["ticker"]
        corr_data = correlations.get(ticker, {})
        if not corr_data.get("predictive"):
            continue

        tdata = fin.get("data", {}).get(ticker, {})
        history = tdata.get("history", [])
        if len(history) < 30:
            continue

        prices = pd.DataFrame(history)
        if "date" not in prices.columns or "close" not in prices.columns:
            continue

        prices["date"] = pd.to_datetime(prices["date"]).dt.date
        prices = prices.sort_values("date").set_index("date")
        prices["ret"] = prices["close"].pct_change()

        # Simulate: BUY signal when NLP score > 0.3 for 3 consecutive days
        # Using conviction from stock_df as fixed signal (simplified backtest)
        conviction = row["conviction"]
        signal = 1 if conviction > 0.6 else (-1 if conviction < 0.4 else 0)

        if signal == 0:
            continue

        rets = prices["ret"].dropna()
        if len(rets) < 20:
            continue

        # Sharpe ratio (annualized, 252 trading days)
        mean_ret = rets.mean()
        std_ret  = rets.std()
        sharpe   = (mean_ret / (std_ret + 1e-9)) * math.sqrt(252)

        # Max drawdown
        cum = (1 + rets).cumprod()
        roll_max = cum.cummax()
        dd = (cum - roll_max) / roll_max
        max_dd = dd.min()

        # Win rate
        win_rate = (rets > 0).mean()

        bt_results[ticker] = {
            "signal": "BUY" if signal==1 else "SELL",
            "sharpe": round(sharpe, 2),
            "max_drawdown": round(max_dd, 3),
            "win_rate": round(win_rate, 3),
            "n_periods": len(rets),
        }
        log.info(f"  {ticker}: Sharpe={sharpe:.2f} MaxDD={max_dd:.1%} WinRate={win_rate:.1%}")

    with open(OUT_DIR / "backtest.json", "w") as f:
        json.dump(bt_results, f, indent=2)

    return bt_results


# ═══════════════════════════════════════════════════════════════
# PHASE 12 — TESTS STATISTIQUES DE ROBUSTESSE
# ═══════════════════════════════════════════════════════════════

def phase12_statistical_tests(df: pd.DataFrame, correlations: dict) -> dict:
    log.info("Phase 12 — Tests statistiques de robustesse…")

    test_results = {}
    fin = load_financial_data()

    for ticker, corr in correlations.items():
        if not corr.get("predictive"):
            continue

        tdata = fin.get("data", {}).get(ticker, {})
        history = tdata.get("history", [])
        if len(history) < 30:
            continue

        prices = pd.DataFrame(history)
        if "close" not in prices.columns:
            continue
        prices["ret"] = prices["close"].pct_change().dropna()
        rets = prices["ret"].dropna()

        tests = {}

        # 1. Normalité (Shapiro-Wilk sur échantillon)
        sample = rets.values[:min(5000, len(rets))]
        if len(sample) >= 8:
            _, pval = stats.shapiro(sample[:min(5000, len(sample))])
            tests["shapiro_pval"] = round(pval, 4)
            tests["is_normal"] = pval > 0.05

        # 2. Stationnarité (ADF test — Augmented Dickey-Fuller approximation)
        if len(rets) >= 20:
            # Simple variance ratio test as ADF proxy
            vr = np.var(rets[:len(rets)//2]) / np.var(rets[len(rets)//2:]) if np.var(rets[len(rets)//2:]) > 0 else 1
            tests["variance_ratio"] = round(vr, 3)
            tests["likely_stationary"] = 0.5 < vr < 2.0

        # 3. Autocorrelation test (Ljung-Box approximation)
        if len(rets) >= 10:
            lag1_corr = rets.autocorr(lag=1)
            tests["autocorr_lag1"] = round(lag1_corr, 4) if not math.isnan(lag1_corr) else 0

        test_results[ticker] = tests

    with open(OUT_DIR / "statistical_tests.json", "w") as f:
        json.dump(test_results, f, indent=2)

    log.info(f"  Tests effectués pour {len(test_results)} tickers")
    return test_results


# ═══════════════════════════════════════════════════════════════
# PHASE 13 — MOTEUR DE PRÉDICTION FINAL (score 0-100)
# ═══════════════════════════════════════════════════════════════

def phase13_prediction_engine(
    stock_df: pd.DataFrame,
    correlations: dict,
    ml_results: dict,
    bt_results: dict,
    stat_tests: dict,
) -> pd.DataFrame:
    log.info("Phase 13 — Moteur de prédiction final…")

    rows = []
    for _, row in stock_df.iterrows():
        ticker = row["ticker"]

        # Component 1: NLP stock picking score (Phase 7) — 40%
        nlp_raw = row["nlp_score"] / 100  # 0..1

        # Component 2: Predictive correlation (Phase 8) — 20%
        corr_data = correlations.get(ticker, {})
        corr_score = abs(corr_data.get("corr_lead_1d", 0))
        corr_direction = np.sign(corr_data.get("corr_lead_1d", 0))
        corr_component = corr_score * (1 if corr_direction > 0 else 0.3)

        # Component 3: ML accuracy (Phase 9) — 25%
        ml_data = ml_results.get(ticker, {})
        ml_acc  = ml_data.get("best_accuracy", 0.5)
        ml_component = max(0, (ml_acc - 0.5) * 2)  # 0.5 baseline → 0..1

        # Component 4: Backtest quality (Phase 11) — 15%
        bt_data  = bt_results.get(ticker, {})
        sharpe   = bt_data.get("sharpe", 0)
        win_rate = bt_data.get("win_rate", 0.5)
        bt_component = min(1, max(0, (sharpe / 2 + (win_rate - 0.5) * 2) / 2))

        final_score = (
            0.40 * nlp_raw +
            0.20 * corr_component +
            0.25 * ml_component +
            0.15 * bt_component
        ) * 100

        # Direction signal
        conviction = row["conviction"]
        direction  = "BUY" if conviction > 0.6 and corr_direction >= 0 else \
                     "SELL" if conviction < 0.4 and corr_direction < 0 else "HOLD"

        # Confidence based on data richness
        confidence = "HIGH" if (
            row["n_msgs"] > 100 and
            row["unique_authors"] > 5 and
            corr_data.get("n_obs", 0) > 20 and
            ml_data.get("n_samples", 0) > 40
        ) else "MEDIUM" if row["n_msgs"] > 30 else "LOW"

        rows.append({
            "ticker": ticker,
            "final_score": round(final_score, 1),
            "direction": direction,
            "confidence": confidence,
            "nlp_raw": round(row["nlp_score"], 1),
            "corr_lead": round(corr_data.get("corr_lead_1d", 0), 3),
            "ml_accuracy": round(ml_acc, 3),
            "sharpe": round(sharpe, 2),
            "n_msgs": int(row["n_msgs"]),
            "unique_authors": int(row["unique_authors"]),
            "signal": row["signal"],
        })

    pred_df = pd.DataFrame(rows).sort_values("final_score", ascending=False)

    log.info(f"\n{'='*60}")
    log.info(f"{'TICKER':6s} {'SCORE':6s} {'DIR':5s} {'CONF':8s} {'NLP':6s} {'CORR':7s} {'ML':6s}")
    log.info(f"{'-'*60}")
    for _, r in pred_df.iterrows():
        log.info(f"{r['ticker']:6s} {r['final_score']:6.1f} {r['direction']:5s} {r['confidence']:8s} "
                 f"{r['nlp_raw']:6.1f} {r['corr_lead']:+7.3f} {r['ml_accuracy']:6.3f}")

    pred_df.to_csv(OUT_DIR / "predictions.csv", index=False)
    return pred_df


# ═══════════════════════════════════════════════════════════════
# PHASE 14 — RAPPORT INSTITUTIONNEL
# ═══════════════════════════════════════════════════════════════

def phase14_report(
    df: pd.DataFrame,
    fg_daily: pd.DataFrame,
    members_df: pd.DataFrame,
    stock_df: pd.DataFrame,
    pred_df: pd.DataFrame,
    net_stats: dict,
    topics: list,
) -> dict:
    log.info("Phase 14 — Rapport institutionnel…")

    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    period_start = str(df["ts"].min().date())
    period_end   = str(df["ts"].max().date())
    n_days = (df["ts"].max() - df["ts"].min()).days

    avg_fg = fg_daily["fear_greed"].mean()
    fg_label_now = fg_daily.iloc[-1]["fg_label"] if len(fg_daily) else "N/A"

    top_tickers = pred_df[pred_df["direction"]=="BUY"].head(5)[["ticker","final_score","confidence"]].to_dict("records")
    risk_tickers = pred_df[pred_df["direction"]=="SELL"].head(3)[["ticker","final_score"]].to_dict("records")

    # Build corpus update for SENTIMENT_CORPUS
    corpus_update = {}
    for _, r in stock_df.iterrows():
        ticker = r["ticker"]
        # Map to -1..+1 signal
        nlp_val = (r["nlp_score"] - 50) / 50  # 0..100 → -1..+1
        corpus_update[ticker] = {
            "signal": round(nlp_val, 3),
            "conviction": r["conviction"],
            "n_msgs": int(r["n_msgs"]),
            "trend": r["signal"],
        }

    report = {
        "generated_at": now,
        "analysis_period": {"start": period_start, "end": period_end, "n_days": n_days},
        "corpus_stats": {
            "total_messages": len(df),
            "unique_members": int(df["sender"].nunique()),
            "messages_with_ticker": int(df["n_tickers"].gt(0).sum()),
            "languages": df["lang"].value_counts().to_dict(),
        },
        "market_sentiment": {
            "avg_fear_greed": round(avg_fg, 1),
            "current_label": str(fg_label_now),
            "buy_ratio": round((df["sentiment"]=="buy").mean(), 3),
            "sell_ratio": round((df["sentiment"]=="sell").mean(), 3),
        },
        "network": {
            "n_nodes": net_stats.get("nodes", 0),
            "n_edges": net_stats.get("edges", 0),
            "density": net_stats.get("density", 0),
            "n_communities": net_stats.get("n_communities", 0),
        },
        "top_opportunities": top_tickers,
        "risk_tickers": risk_tickers,
        "topics_summary": [" · ".join(t[:5]) for t in topics[:5]],
        "corpus_update": corpus_update,
    }

    with open(OUT_DIR / "report.json", "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    # Print summary
    log.info(f"\n{'═'*60}")
    log.info(f"  RAPPORT BVC NLP ANALYSIS — {now}")
    log.info(f"{'═'*60}")
    log.info(f"  Période    : {period_start} → {period_end} ({n_days} jours)")
    log.info(f"  Messages   : {len(df):,} | Membres: {df['sender'].nunique()}")
    log.info(f"  Fear&Greed : {avg_fg:.1f} ({fg_label_now})")
    log.info(f"\n  TOP OPPORTUNITÉS:")
    for t in top_tickers:
        log.info(f"    {t['ticker']} — score {t['final_score']} ({t['confidence']})")
    log.info(f"\n  RISQUES:")
    for t in risk_tickers:
        log.info(f"    {t['ticker']} — score {t['final_score']}")
    log.info(f"\n  Fichiers générés dans: {OUT_DIR}")
    log.info(f"{'═'*60}")

    return report


# ═══════════════════════════════════════════════════════════════
# UPDATE index.html SENTIMENT_CORPUS
# ═══════════════════════════════════════════════════════════════

def update_sentiment_corpus(corpus_update: dict) -> None:
    """Patch SENTIMENT_CORPUS in update_data.py with new NLP results."""
    log.info("Mise à jour SENTIMENT_CORPUS dans update_data.py…")

    script = Path("/home/user/-bvc-analyzer/update_data.py")
    if not script.exists():
        log.warning("update_data.py introuvable")
        return

    content = script.read_text()

    # Build new corpus dict string
    lines = []
    for ticker, data in corpus_update.items():
        signal  = data["signal"]
        trend   = data["trend"]
        n_msgs  = data["n_msgs"]
        lines.append(f'    "{ticker}": {{"signal": {signal:.3f}, "trend": "{trend}", "n_msgs": {n_msgs}}},')

    new_corpus = "SENTIMENT_CORPUS = {\n" + "\n".join(lines) + "\n}"

    # Replace existing corpus
    import re as _re
    pattern = r"SENTIMENT_CORPUS\s*=\s*\{[^}]*\}"
    if _re.search(pattern, content, _re.DOTALL):
        new_content = _re.sub(pattern, new_corpus, content, flags=_re.DOTALL)
        script.write_text(new_content)
        log.info(f"  ✓ SENTIMENT_CORPUS mis à jour ({len(corpus_update)} tickers)")
    else:
        log.warning("  Pattern SENTIMENT_CORPUS non trouvé dans update_data.py")


# ═══════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════

def main(args) -> None:
    log.info("╔══════════════════════════════════════════════════════╗")
    log.info("║  BVC WhatsApp NLP Analysis — 14 Phases              ║")
    log.info("╚══════════════════════════════════════════════════════╝")

    # Phase 1 — Data Engineering
    raw_lines = load_chat_file()
    df = parse_whatsapp(raw_lines)

    if args.sample:
        n = min(args.sample, len(df))
        log.info(f"Mode sample: {n:,} messages")
        df = df.sample(n, random_state=42).sort_values("ts").reset_index(drop=True)

    # Phase 2 — Languages
    df = phase2_language(df)

    # Phase 3 — NLP
    df = phase3_nlp(df)

    # Save enriched DataFrame
    df_save = df.drop(columns=["text_lower","price_targets","prices_mentioned","pct_changes","tickers_mentioned"], errors="ignore")
    df_save.to_csv(OUT_DIR / "messages_enriched.csv", index=False)

    # Phase 4 — Fear & Greed
    fg_daily = compute_fear_greed_index(df)

    # Phase 5 — Smart Money
    members_df = compute_smart_money(df, fg_daily)

    # Phase 6 — Network
    net_stats = phase6_network(df)

    # Phase 7 — Stock Picking
    stock_df = phase7_stock_picking(df)

    # Phase 8 — Correlations
    correlations = phase8_market_correlation(df, stock_df)

    # Phase 9 — ML
    ml_results = phase9_ml_models(df, correlations)

    # Phase 10 — Topics
    topics = phase10_topics(df)

    # Phase 11 — Backtest
    bt_results = phase11_backtest(stock_df, correlations)

    # Phase 12 — Statistical tests
    stat_tests = phase12_statistical_tests(df, correlations)

    # Phase 13 — Prediction engine
    pred_df = phase13_prediction_engine(stock_df, correlations, ml_results, bt_results, stat_tests)

    # Phase 14 — Institutional report
    report = phase14_report(df, fg_daily, members_df, stock_df, pred_df, net_stats, topics)

    # Update SENTIMENT_CORPUS
    if not args.dry_run:
        update_sentiment_corpus(report["corpus_update"])

    log.info("✅ Analyse complète terminée")
    log.info(f"   Résultats: {OUT_DIR}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="BVC WhatsApp NLP Analysis")
    parser.add_argument("--sample", type=int, default=0, help="Limit to N messages (0=all)")
    parser.add_argument("--dry-run", action="store_true", help="Ne pas modifier update_data.py")
    args = parser.parse_args()
    main(args)
