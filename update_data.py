#!/usr/bin/env python3
"""
BVC ANALYZER — update_data.py v6.2
═══════════════════════════════════════════════════════════════════════════════
Récupère les cours live BVC (IDBourse → Médias24), recalcule les indicateurs
techniques (RSI, MA20/50, Fibonacci) et les scores v5.3, puis met à jour
data.json pour le site GitHub Pages.

Usage depuis Colab ou terminal :
    python update_data.py
    python update_data.py --push --token VOTRE_GITHUB_TOKEN
    python update_data.py --dry-run          # aperçu sans écrire

Dépendances : requests, numpy, pandas (auto-installées si absentes)
═══════════════════════════════════════════════════════════════════════════════
"""

import sys, os, json, time, argparse, logging, subprocess
from datetime import datetime, timedelta
from pathlib import Path

# Auto-install deps si besoin (Colab)
for pkg in ["requests", "numpy", "pandas"]:
    try:
        __import__(pkg)
    except ImportError:
        subprocess.run([sys.executable, "-m", "pip", "install", pkg, "-q"], check=True)

import requests
import numpy as np
import pandas as pd

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger("BVC_UPDATE")

# ─────────────────────────────────────────────────────────────────────────────
# CONFIGURATION
# ─────────────────────────────────────────────────────────────────────────────

IDB_BASE = "https://www.idbourse.com"
MED_BASE = "https://medias24.com/content/api"
HEADERS  = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
            "Accept-Language": "fr-FR,fr;q=0.9"}

# Chemin vers data.json (à côté de ce script)
try:
    OUTPUT = Path(__file__).parent / "data.json"
except NameError:
    OUTPUT = Path("data.json")  # Colab : dossier courant

from bvc_config import ISIN_MAP, IDB_NAME_MAP

TICKERS = list(ISIN_MAP.keys())

# ─────────────────────────────────────────────────────────────────────────────
# DONNÉES FONDAMENTALES STABLES (source: bilans / rapports d'introduction BVC)
# Mise à jour manuelle lors de nouvelles publications de résultats
# ─────────────────────────────────────────────────────────────────────────────

FOND_SCORES = {
    "CMT":7.73,"SMI":7.73,"CASH":7.95,"MNG":4.32,"AKD":7.50,"SOT":7.50,
    "SGTM":8.18,"MSA":6.59,"CFGB":7.73,"RIS":5.23,"ADI":7.05,"VCNE":6.59,
    "CMGP":6.59,"CSR":5.23,"TGCC":8.41,"ADH":4.09,"SRM":4.32,"SNA":4.09,"RDS":2.27,
}

BVC_SCORES_BASE = {
    "CMT":7.16,"SMI":6.95,"CASH":6.73,"MNG":6.59,"AKD":6.20,"SOT":6.62,
    "SGTM":5.77,"MSA":6.28,"CFGB":5.44,"RIS":4.71,"ADI":5.00,"VCNE":4.93,
    "CMGP":5.17,"CSR":4.58,"TGCC":5.22,"ADH":4.28,"SRM":4.88,"SNA":4.10,"RDS":3.76,
}

FOND_DATA = {
    "CMT":{"pe":15.4,"pb":2.2,"div":4.1,"cap":8500,  "bear":4446,"base":5700, "bull":7125, "upside":14.0,"flags":0},
    "SMI":{"pe":12.1,"pb":1.5,"div":2.0,"cap":4200,  "bear":7695,"base":9865, "bull":12331,"upside":7.0, "flags":0},
    "CASH":{"pe":13.8,"pb":1.8,"div":3.2,"cap":2800, "bear":244, "base":313,  "bull":392,  "upside":12.0,"flags":0},
    "MNG":{"pe":21.3,"pb":3.1,"div":1.5,"cap":15000, "bear":13847,"base":17753,"bull":22191,"upside":2.0,"flags":3},
    "AKD":{"pe":28.4,"pb":4.2,"div":0.8,"cap":6280,  "bear":535, "base":660,  "bull":750,  "upside":18.0,"flags":0},
    "SOT":{"pe":19.5,"pb":2.5,"div":2.8,"cap":1100,  "bear":322, "base":413,  "bull":516,  "upside":12.0,"flags":0},
    "SGTM":{"pe":16.2,"pb":1.9,"div":3.1,"cap":2800, "bear":724, "base":928,  "bull":1160, "upside":27.0,"flags":0},
    "MSA":{"pe":14.7,"pb":1.8,"div":4.2,"cap":3200,  "bear":558, "base":715,  "bull":894,  "upside":-13.0,"flags":0},
    "CFGB":{"pe":11.8,"pb":1.4,"div":2.5,"cap":1800, "bear":187, "base":239,  "bull":299,  "upside":17.0,"flags":1},
    "RIS":{"pe":10.2,"pb":0.9,"div":3.8,"cap":890,   "bear":208, "base":267,  "bull":334,  "upside":-20.0,"flags":2},
    "ADI":{"pe":22,  "pb":0.8,"div":1.2,"cap":8600,  "bear":374, "base":479,  "bull":599,  "upside":17.0,"flags":0},
    "VCNE":{"pe":12.4,"pb":1.6,"div":5.1,"cap":5200, "bear":331, "base":425,  "bull":531,  "upside":9.0, "flags":1},
    "CMGP":{"pe":13.1,"pb":1.3,"div":2.9,"cap":680,  "bear":272, "base":349,  "bull":436,  "upside":-3.0,"flags":1},
    "CSR":{"pe":8.9, "pb":0.7,"div":1.5,"cap":420,   "bear":121, "base":156,  "bull":195,  "upside":-15.0,"flags":2},
    "TGCC":{"pe":17.9,"pb":2.0,"div":2.2,"cap":3800, "bear":738, "base":946,  "bull":1182, "upside":27.0,"flags":0},
    "ADH":{"pe":7.2, "pb":0.6,"div":0.0,"cap":3200,  "bear":25.5,"base":32.8, "bull":41,   "upside":0.0, "flags":3},
    "SRM":{"pe":11.5,"pb":1.1,"div":0.5,"cap":310,   "bear":407, "base":522,  "bull":652,  "upside":8.0, "flags":4},
    "SNA":{"pe":8.2, "pb":0.7,"div":1.0,"cap":1100,  "bear":495, "base":540,  "bull":610,  "upside":-11.0,"flags":3},
    "RDS":{"pe":6.1, "pb":0.5,"div":0.0,"cap":280,   "bear":81,  "base":103,  "bull":129,  "upside":-38.0,"flags":4},
}

# ─────────────────────────────────────────────────────────────────────────────
# CORPUS SENTIMENT NLP (source: bvc_analyzer_v53.py — 896 907 messages / 6 ans)
# ─────────────────────────────────────────────────────────────────────────────

SENTIMENT = {
    "CMT": {"smart":0.51,"hype":0.72,"alpha":8.3, "win":0.92,"mentions":2717, "biais":"ACHAT",     "contrarian":False},
    "SMI": {"smart":0.46,"hype":0.43,"alpha":30.7,"win":1.00,"mentions":3827, "biais":"ACHAT",     "contrarian":False},
    "CASH":{"smart":0.38,"hype":0.31,"alpha":7.0, "win":0.80,"mentions":1100, "biais":"ACHAT",     "contrarian":False},
    "MNG": {"smart":0.50,"hype":0.89,"alpha":55.3,"win":0.93,"mentions":8673, "biais":"ACHAT FORT","contrarian":False},
    "AKD": {"smart":0.25,"hype":0.35,"alpha":15.2,"win":0.78,"mentions":800,  "biais":"ACHAT",     "contrarian":False},
    "SOT": {"smart":0.29,"hype":0.28,"alpha":5.0, "win":0.75,"mentions":800,  "biais":"ACHAT",     "contrarian":False},
    "SGTM":{"smart":0.18,"hype":0.41,"alpha":6.0, "win":0.78,"mentions":1200, "biais":"ACHAT",     "contrarian":False},
    "MSA": {"smart":0.22,"hype":0.35,"alpha":18.5,"win":1.00,"mentions":3355, "biais":"ACHAT",     "contrarian":False},
    "CFGB":{"smart":0.12,"hype":0.19,"alpha":4.0, "win":0.72,"mentions":900,  "biais":"ACHAT",     "contrarian":False},
    "RIS": {"smart":0.08,"hype":0.22,"alpha":11.4,"win":1.00,"mentions":3355, "biais":"ACHAT",     "contrarian":False},
    "ADI": {"smart":-0.05,"hype":0.65,"alpha":8.5,"win":0.69,"mentions":19180,"biais":"DÉBATTU",   "contrarian":False},
    "VCNE":{"smart":0.05,"hype":0.21,"alpha":3.0, "win":0.70,"mentions":600,  "biais":"NEUTRE",    "contrarian":False},
    "CMGP":{"smart":0.05,"hype":0.21,"alpha":3.0, "win":0.70,"mentions":750,  "biais":"NEUTRE",    "contrarian":False},
    "CSR": {"smart":0.02,"hype":0.14,"alpha":2.0, "win":0.60,"mentions":400,  "biais":"NEUTRE",    "contrarian":False},
    "TGCC":{"smart":0.09,"hype":0.38,"alpha":-2.3,"win":0.39,"mentions":10797,"biais":"ACHAT",     "contrarian":True},
    "ADH": {"smart":-0.08,"hype":0.33,"alpha":12.9,"win":0.86,"mentions":16102,"biais":"ACHAT",    "contrarian":False},
    "SRM": {"smart":-0.12,"hype":0.18,"alpha":2.0,"win":0.55,"mentions":500,  "biais":"NÉGATIF",   "contrarian":False},
    "SNA": {"smart":-0.15,"hype":0.14,"alpha":-2.2,"win":0.35,"mentions":300, "biais":"NÉGATIF",   "contrarian":False},
    "RDS": {"smart":-0.31,"hype":0.28,"alpha":11.4,"win":1.00,"mentions":12223,"biais":"ACHAT",    "contrarian":True},
}

# ─────────────────────────────────────────────────────────────────────────────
# CONNECTEUR IDBOURSE / MÉDIAS24
# ─────────────────────────────────────────────────────────────────────────────

def idb_get(endpoint, timeout=10):
    try:
        r = requests.get(f"{IDB_BASE}{endpoint}", headers=HEADERS, timeout=timeout)
        if r.status_code == 200:
            return r.json()
    except Exception as e:
        logger.debug(f"IDBourse {endpoint}: {e}")
    return None

def med_get(params, timeout=12):
    try:
        r = requests.get(MED_BASE, params={**params, "format": "json"},
                         headers=HEADERS, timeout=timeout)
        if r.status_code == 200 and len(r.text) > 20:
            return r.json()
    except Exception as e:
        logger.debug(f"Médias24 {params.get('method')}: {e}")
    return None

def fetch_all_idb():
    """Toutes les cotations IDBourse en un seul appel."""
    data = idb_get("/api/proxy/get_all_data")
    if not isinstance(data, list):
        return {}
    out = {}
    for d in data:
        if not d.get("name") or not d.get("dernier_cours"):
            continue
        n = d["name"].upper()
        sym = IDB_NAME_MAP.get(n, n)
        if sym not in ISIN_MAP:
            continue
        try:
            out[sym] = {
                "price": float(d["dernier_cours"]),
                "chg":   float(d.get("variation", 0) or 0),
                "open":  float(d["ouverture"]) if d.get("ouverture") else None,
            }
        except (ValueError, TypeError):
            continue
    return out

def fetch_masi():
    """Indice MASI (variation % pour contexte marché)."""
    m = idb_get("/api/proxy/masi-data")
    if m and m.get("value"):
        return {"value": float(m["value"]), "chg": float(m.get("variation", 0) or 0)}
    return {"value": 0, "chg": 0}

def fetch_history(ticker, days=90):
    """Historique OHLCV Médias24 → DataFrame."""
    isin = ISIN_MAP.get(ticker)
    if not isin:
        return pd.DataFrame()
    to   = datetime.now()
    frm  = to - timedelta(days=days + 30)  # marge pour weekends/jours fériés
    data = med_get({
        "method": "getPriceHistory",
        "ISIN":   isin,
        "from":   frm.strftime("%Y-%m-%d"),
        "to":     to.strftime("%Y-%m-%d"),
    })
    recs = data.get("result") if data else None
    if not isinstance(recs, list) or len(recs) < 5:
        return pd.DataFrame()

    rows = []
    for r in recs:
        try:
            raw = r.get("date", "")
            if "/" in raw:
                d, m, y = raw.split("/")
                dt = datetime(int(y), int(m), int(d))
            else:
                dt = datetime.fromisoformat(raw[:10])
            rows.append({
                "date":  dt,
                "close": float(r.get("value") or 0),
                "high":  float(r.get("max")   or r.get("value") or 0),
                "low":   float(r.get("min")   or r.get("value") or 0),
                "vol":   float(r.get("volume") or 0),
            })
        except Exception:
            continue

    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows).sort_values("date").reset_index(drop=True)
    df = df[df["close"] > 0]
    df["open"] = df["close"].shift(1).fillna(df["close"])
    return df.tail(days)

# ─────────────────────────────────────────────────────────────────────────────
# INDICATEURS TECHNIQUES
# ─────────────────────────────────────────────────────────────────────────────

def calc_rsi(closes: pd.Series, period=14) -> float:
    """RSI(14) — méthode Wilder EMA."""
    delta = closes.diff()
    up    = delta.clip(lower=0)
    down  = -delta.clip(upper=0)
    ema_up   = up.ewm(com=period - 1, adjust=False).mean()
    ema_down = down.ewm(com=period - 1, adjust=False).mean()
    rs = ema_up / ema_down.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    return round(float(rsi.iloc[-1]), 1) if not rsi.empty else 50.0

def calc_ma(closes: pd.Series, period: int) -> float:
    """Moyenne mobile simple."""
    if len(closes) < period:
        return round(float(closes.mean()), 2)
    return round(float(closes.tail(period).mean()), 2)

def calc_score_tech(rsi, price, ma20, ma50, h90, l90) -> float:
    """
    Score technique simplifié [0-10].
    Basé sur RSI, alignement des MAs, position dans la range 90 jours.
    """
    score = 5.0

    # RSI (zone idéale 40-65 pour BVC, peu liquide)
    if 40 <= rsi <= 65:
        score += 1.0
    elif rsi > 75:       # suracheté
        score -= 1.0
    elif rsi < 30:       # survendu → rebond potentiel
        score += 0.5
    elif rsi < 40:
        score -= 0.3

    # Alignement des moyennes mobiles
    if price > ma20 > ma50:     # tendance haussière confirmée
        score += 1.5
    elif price > ma20:           # au-dessus MA20 seulement
        score += 0.8
    elif price > ma50:           # entre MA20 et MA50
        score += 0.3
    elif price < ma50:           # sous les deux MAs → faiblesse
        score -= 1.2

    # Position dans la range 90 jours
    if h90 > l90:
        pos = (price - l90) / (h90 - l90)
        if 0.25 <= pos <= 0.70:  # zone médiane = saine
            score += 0.4
        elif pos > 0.90:          # proche du sommet = risque retournement
            score -= 0.6
        elif pos < 0.10:          # proche du bas = risque support
            score -= 0.3

    return round(min(max(score, 0), 10), 2)

# ─────────────────────────────────────────────────────────────────────────────
# MOTEUR DE SCORE v5.3 (port depuis bvc_analyzer_v53.py)
# ─────────────────────────────────────────────────────────────────────────────

def get_weights(context: dict) -> dict:
    """WeightEngine.get_weights() — pondération dynamique selon contexte."""
    w = {"technique": 0.25, "fondamental": 0.47, "comportemental": 0.28}

    if context.get("market_status") in ["CLOSED", "PRE_MARKET"]:
        w["fondamental"] += 0.05; w["technique"] -= 0.05
    if context.get("has_results"):
        w["fondamental"] += 0.10; w["technique"] -= 0.07; w["comportemental"] -= 0.03
    if context.get("hype_spike"):
        w["comportemental"] += 0.08; w["fondamental"] -= 0.05; w["technique"] -= 0.03
    if context.get("smart_money_active"):
        w["comportemental"] += 0.07; w["technique"] -= 0.04; w["fondamental"] -= 0.03

    masi_ytd = context.get("masi_ytd", 0)
    if masi_ytd < -5:
        w["fondamental"] += 0.08; w["comportemental"] -= 0.05; w["technique"] -= 0.03
    elif masi_ytd > 10:
        w["technique"] += 0.03; w["fondamental"] -= 0.03

    if context.get("ticker_coverage", 100) < 50:
        w["comportemental"] -= 0.10; w["fondamental"] += 0.07; w["technique"] += 0.03

    total = sum(w.values())
    return {k: round(v / total, 4) for k, v in w.items()}

def compute_v53(ticker, score_tech, score_fond, bvc_score, red_flags, upside, context) -> dict:
    """ScoreEngineV53.compute() — score enrichi avec bonus/malus."""
    sent = SENTIMENT.get(ticker, {
        "smart": 0, "hype": 0, "alpha": 0, "win": 0.5,
        "mentions": 0, "biais": "N/A", "contrarian": False
    })

    w = get_weights(context)
    score_nlp = (sent["smart"] + 1) * 5   # [-1,+1] → [0,10]

    base = (score_tech   * w["technique"]
            + score_fond * w["fondamental"]
            + score_nlp  * w["comportemental"])

    bonus = 0.0
    bonus_log = []

    # Convergence BVC + NLP
    bvc_bull = bvc_score >= 5.5
    nlp_bull = sent["smart"] > 0.15
    if bvc_bull and nlp_bull:
        bonus += 0.30; bonus_log.append("+Conv BVC+NLP +0.30")
    elif not bvc_bull and not nlp_bull:
        bonus += 0.15; bonus_log.append("+Conv baissière +0.15")
    if bvc_bull and sent["smart"] < -0.20:
        bonus -= 0.50; bonus_log.append("-Divergence BVC/NLP -0.50")

    # Smart Money actif
    if context.get("smart_money_active") and sent["win"] >= 0.80:
        bonus += 0.40; bonus_log.append(f"+Smart Money ({sent['win']*100:.0f}%) +0.40")

    # Signal contrarian validé
    if sent.get("contrarian") and bvc_score < 5.0:
        bonus += 0.25; bonus_log.append("+Contrarian +0.25")

    # Hype spike
    if context.get("hype_spike") and sent["hype"] > 0.70:
        bonus += 0.20; bonus_log.append("+Hype spike +0.20")

    # Red flags pénalité
    if red_flags >= 3:
        pen = -0.30 * (red_flags - 2)
        bonus += pen; bonus_log.append(f"-Red flags ({red_flags}) {pen:.2f}")

    # Alpha historique négatif
    if sent.get("alpha", 0) < -1:
        bonus -= 0.60; bonus_log.append(f"-Alpha négatif ({sent['alpha']}%) -0.60")

    # Upside négatif avec signal positif
    if upside < -10 and bvc_bull:
        bonus -= 0.20; bonus_log.append("-Upside négatif -0.20")

    final = round(min(max(base + bonus, 0), 10), 2)

    # Signal enrichi
    if final >= 7.5 and sent["win"] >= 0.80:
        sig = "ACHAT FORT ★★★"
    elif final >= 6.5:
        sig = "ACHETER ★★"
    elif final >= 5.5:
        sig = "SURVEILLER ★"
    elif final >= 4.5:
        sig = "ATTENDRE"
    elif final >= 3.5:
        sig = "ÉVITER"
    else:
        sig = "ÉVITER FORT"

    # Alerte si alpha négatif
    warn = sent.get("alpha", 0) < -1
    warn_msg = (f"Alpha historique NÉGATIF ({sent['alpha']}%) · "
                f"Win rate {sent['win']*100:.0f}% · Signal enrichi = ÉVITER") if warn else ""

    return {
        "v53":    final,
        "bvc":    round(bvc_score, 2),
        "delta":  round(final - bvc_score, 2),
        "nlp":    round(sent["smart"], 2),
        "alpha":  sent.get("alpha", 0),
        "win":    round(sent["win"] * 100),
        "sig":    sig,
        "biais":  sent.get("biais", "NEUTRE"),
        "bonus":  bonus_log,
        "poids":  {"f": round(w["fondamental"]*100), "n": round(w["comportemental"]*100), "t": round(w["technique"]*100)},
        "warn":   warn,
        "warnMsg": warn_msg,
    }

# ─────────────────────────────────────────────────────────────────────────────
# PIPELINE PRINCIPAL
# ─────────────────────────────────────────────────────────────────────────────

def run(dry_run=False, push=False, token=""):
    ts_start = time.time()
    logger.info("═" * 60)
    logger.info("BVC ANALYZER — update_data.py v6.2")
    logger.info("═" * 60)

    # 1. Contexte marché
    now_ca = datetime.utcnow() + timedelta(hours=1)  # UTC+1 Casablanca
    h, mn = now_ca.hour, now_ca.minute
    tot = h * 60 + mn
    day = now_ca.weekday()  # 0=lun, 5=sam, 6=dim
    if day >= 5:
        mkt_status = "CLOSED"
    elif 9*60+20 <= tot < 9*60+30:
        mkt_status = "PRE_MARKET"
    elif 9*60+30 <= tot < 15*60+30:
        mkt_status = "OPEN"
    else:
        mkt_status = "CLOSED"
    logger.info(f"Statut marché BVC : {mkt_status} ({now_ca.strftime('%H:%M')} CAS)")

    # 2. MASI
    masi = fetch_masi()
    logger.info(f"MASI: {masi['value']:,.2f} pts ({masi['chg']:+.2f}%)")

    # 3. Cours live IDBourse
    logger.info("Récupération IDBourse (batch)...")
    live_prices = fetch_all_idb()
    logger.info(f"IDBourse: {len(live_prices)}/{len(TICKERS)} tickers reçus")

    # Skip si marché fermé ET aucune donnée live — évite les commits inutiles
    if mkt_status == "CLOSED" and len(live_prices) == 0 and not dry_run:
        logger.info("Marché fermé et aucune donnée live — skip (data.json inchangé)")
        return None

    # Contexte marché global
    mkt_ctx_base = {
        "market_status":    mkt_status,
        "has_results":      False,
        "masi_ytd":         masi["chg"],
    }

    # 4. Traitement par ticker
    tickers_out = []
    for ticker in TICKERS:
        fd = FOND_DATA.get(ticker, {})
        lp = live_prices.get(ticker, {})

        # Prix
        price = lp.get("price") or 0
        chg   = lp.get("chg", 0)
        opn   = lp.get("open")

        # Historique Médias24 pour indicateurs techniques
        df = pd.DataFrame()
        if price > 0:
            logger.info(f"  {ticker}: {price} DH ({chg:+.2f}%) — historique...")
            df = fetch_history(ticker, days=95)
            time.sleep(0.3)  # éviter rate limiting Médias24
        else:
            logger.warning(f"  {ticker}: prix non disponible — données statiques")

        # Indicateurs techniques
        if not df.empty and len(df) >= 14:
            closes = df["close"]
            highs  = df["high"]
            lows   = df["low"]
            rsi    = calc_rsi(closes)
            ma20   = calc_ma(closes, 20)
            ma50   = calc_ma(closes, 50)
            h90    = round(float(highs.max()), 2)
            l90    = round(float(lows.min()), 2)
            if not price:
                price = round(float(closes.iloc[-1]), 2)
            if not chg and len(closes) >= 2:
                chg = round((closes.iloc[-1] - closes.iloc[-2]) / closes.iloc[-2] * 100, 2)
            if not opn and len(df) >= 1:
                opn = round(float(df["open"].iloc[-1]), 2)
        else:
            # Fallback indicateurs depuis data.json existant
            try:
                existing = json.loads(OUTPUT.read_text()) if OUTPUT.exists() else {}
                ex_t = next((t for t in existing.get("tickers", []) if t["symbol"] == ticker), {})
                rsi  = ex_t.get("rsi", 50)
                ma20 = ex_t.get("ma20", price or 0)
                ma50 = ex_t.get("ma50", price or 0)
                h90  = ex_t.get("h90",  price * 1.15 if price else 0)
                l90  = ex_t.get("l90",  price * 0.85 if price else 0)
                if not price:
                    price = ex_t.get("price", 0)
            except Exception:
                rsi, ma20, ma50 = 50, price or 0, price or 0
                h90 = price * 1.15 if price else 0
                l90 = price * 0.85 if price else 0

        if not price:
            logger.warning(f"  {ticker}: ignoré (aucune donnée)")
            continue

        if not opn:
            opn = round(price / (1 + chg / 100), 2) if chg else price

        # Score technique
        score_tech = calc_score_tech(rsi, price, ma20, ma50, h90, l90)
        score_fond = FOND_SCORES.get(ticker, 5.0)
        bvc_score  = BVC_SCORES_BASE.get(ticker, 5.0)

        # Contexte spécifique ticker
        sent = SENTIMENT.get(ticker, {})
        ctx = {
            **mkt_ctx_base,
            "ticker_coverage":    sent.get("mentions", 100),
            "smart_money_active": sent.get("win", 0) >= 0.80,
            "hype_spike":         sent.get("hype", 0) > 0.75,
        }

        # Score enrichi v5.3
        v53 = compute_v53(ticker, score_tech, score_fond, bvc_score,
                          fd.get("flags", 0), fd.get("upside", 0), ctx)

        tickers_out.append({
            "symbol": ticker,
            "price":  round(price, 2),
            "chg":    round(chg, 2),
            "open":   round(opn, 2),
            "close":  round(price, 2),
            "pe":     fd.get("pe"),
            "pb":     fd.get("pb"),
            "div":    fd.get("div"),
            "cap":    fd.get("cap"),
            "h90":    round(h90, 2),
            "l90":    round(l90, 2),
            "rsi":    rsi,
            "ma20":   ma20,
            "ma50":   ma50,
            # Scores v5.3
            "bvc":    v53["bvc"],
            "v53":    v53["v53"],
            "delta":  v53["delta"],
            "nlp":    v53["nlp"],
            "alpha":  v53["alpha"],
            "win":    v53["win"],
            "sig":    v53["sig"],
            "biais":  v53["biais"],
            "bonus":  v53["bonus"],
            "poids":  v53["poids"],
            "warn":   v53["warn"],
            "warnMsg":v53["warnMsg"],
            # Fondamentaux
            "bear":   fd.get("bear"),
            "base":   fd.get("base"),
            "bull":   fd.get("bull"),
            "upside": fd.get("upside"),
            "flags":  fd.get("flags", 0),
        })

        logger.info(f"  ✓ {ticker}: {price} DH | RSI {rsi} | Score v5.3: {bvc_score} → {v53['v53']} | {v53['sig']}")

    # 5. Construction data.json
    output = {
        "updated": datetime.now().strftime("%Y-%m-%dT%H:%M:%S+01:00"),
        "source":  "IDBourse / Médias24",
        "market_status": mkt_status,
        "masi": {
            "value":      masi["value"],
            "change_pct": masi["chg"],
        },
        "tickers": tickers_out,
    }

    elapsed = round(time.time() - ts_start, 1)
    logger.info(f"\n{'═'*60}")
    logger.info(f"Résumé: {len(tickers_out)}/{len(TICKERS)} tickers traités en {elapsed}s")

    if dry_run:
        logger.info("[DRY RUN] Aperçu data.json :")
        print(json.dumps(output, ensure_ascii=False, indent=2)[:3000] + "\n...")
        return output

    # 6. Écriture data.json
    OUTPUT.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info(f"✅ data.json écrit → {OUTPUT}")

    # 7. Git commit + push (optionnel)
    if push:
        _git_push(OUTPUT, token)

    return output


def _git_push(json_path: Path, token=""):
    """Commit et push data.json vers GitHub."""
    repo = json_path.parent
    ts   = datetime.now().strftime("%d/%m/%Y %H:%M")
    try:
        subprocess.run(["git", "-C", str(repo), "config", "user.email", "noreply@anthropic.com"], check=True)
        subprocess.run(["git", "-C", str(repo), "config", "user.name",  "BVC-Bot"], check=True)
        subprocess.run(["git", "-C", str(repo), "add", "data.json"], check=True)
        result = subprocess.run(
            ["git", "-C", str(repo), "diff", "--cached", "--stat"],
            capture_output=True, text=True
        )
        if not result.stdout.strip():
            logger.info("Git: aucun changement à committer")
            return
        subprocess.run(
            ["git", "-C", str(repo), "commit", "-m", f"data: mise à jour automatique {ts}"],
            check=True
        )
        remote = f"https://{token}@github.com/abdmoutalib207-lang/-bvc-analyzer.git" if token else "origin"
        subprocess.run(["git", "-C", str(repo), "push", remote, "main"], check=True)
        logger.info("✅ data.json poussé vers GitHub")
    except subprocess.CalledProcessError as e:
        logger.error(f"Git push échoué : {e}")


# ─────────────────────────────────────────────────────────────────────────────
# POINT D'ENTRÉE
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="BVC Analyzer — Mise à jour data.json")
    parser.add_argument("--dry-run", action="store_true", help="Aperçu sans écrire ni pousser")
    parser.add_argument("--push",    action="store_true", help="Git commit + push après écriture")
    parser.add_argument("--token",   default="",          help="GitHub token pour le push")
    args = parser.parse_args()

    run(dry_run=args.dry_run, push=args.push, token=args.token)
