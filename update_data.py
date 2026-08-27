#!/usr/bin/env python3
"""
BVC ANALYZER — update_data.py v6.4
═══════════════════════════════════════════════════════════════════════════════
Récupère les cours live BVC (IDBourse → Médias24), recalcule les indicateurs
techniques (RSI, MA20/50, MACD, Bollinger, Stochastique, Fibonacci) et les
scores v5.3, puis met à jour data.json pour le site GitHub Pages.

Usage depuis Colab ou terminal :
    python update_data.py
    python update_data.py --push --token VOTRE_GITHUB_TOKEN
    python update_data.py --dry-run          # aperçu sans écrire

Dépendances : requests, numpy, pandas (auto-installées si absentes)
═══════════════════════════════════════════════════════════════════════════════
"""

import sys, os, json, time, argparse, logging, subprocess, collections
from datetime import datetime, timedelta, timezone
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

from bvc_config import (ISIN_MAP, IDB_NAME_MAP, IDB_TICKER_MAP, TICKERS_ALL,
                        COMPANY_NAMES, COMPANY_SECTORS, est_ferie_fixe)

TICKERS = TICKERS_ALL

# Ticker officiel BVC/IDBourse → le nôtre. La table est déclarée dans l'autre
# sens (le nôtre → IDBourse) ; l'ingestion, elle, part du code renvoyé par la
# source. Sans collision : vérifié à la construction.
IDB_TICKER_INV = {idb: nous for nous, idb in IDB_TICKER_MAP.items()}
assert len(IDB_TICKER_INV) == len(IDB_TICKER_MAP), \
    "IDB_TICKER_MAP : deux tickers pointent sur le même code IDBourse"

# Date de la séance renvoyée par IDBourse (≠ date du run). Renseignée par
# fetch_all_idb() ; sert à n'écrire une bougie que pour une séance réellement
# cotée. Vide tant que la source n'a pas répondu.
IDB_ASOF = ""

# ─────────────────────────────────────────────────────────────────────────────
# MÉTADONNÉES TICKERS (nom complet + secteur)
# Source de vérité : bvc_config.COMPANY_NAMES / COMPANY_SECTORS
# ─────────────────────────────────────────────────────────────────────────────
TICKER_INFO = {
    sym: {
        "name":   COMPANY_NAMES.get(sym, sym),
        "sector": COMPANY_SECTORS.get(sym, "")
    }
    for sym in TICKERS_ALL
}

# Signal communauté BVC (consensus indépendant du score v5.3)
SIG_BVC = {
    # Tickers actifs (19)
    "CMT":"ACHETER","SMI":"ACHETER","CASH":"SURVEILLER","MNG":"ACHETER",
    "AKD":"ACHETER","SOT":"ACHETER","SGTM":"SURVEILLER","MSA":"SURVEILLER",
    "CFGB":"ATTENDRE","RIS":"ATTENDRE","ADI":"ATTENDRE","VCNE":"ATTENDRE",
    "CMGP":"ATTENDRE","CSR":"ATTENDRE","TGCC":"ATTENDRE","ADH":"ATTENDRE",
    "SRM":"ATTENDRE","SNA":"EVITER","RDS":"EVITER",
    # Grandes capitalisations
    "IAM":"ACHETER","ATW":"ACHETER","BCP":"ACHETER","BOA":"SURVEILLER",
    "CIH":"SURVEILLER","CDM":"SURVEILLER","WAF":"SURVEILLER",
    "LHM":"ACHETER","GAZ":"ACHETER","ATL":"ACHETER","HPS":"ACHETER",
    "LBV":"SURVEILLER","LES":"SURVEILLER","TQA":"ACHETER","MRL":"ACHETER","TMA":"SURVEILLER",
    # Moyennes capitalisations
    "ARD":"ACHETER","SAF":"SURVEILLER","OUL":"SURVEILLER","CIM":"ACHETER",
    "CTM":"SURVEILLER","ZLD":"ATTENDRE","ALU":"ATTENDRE","MGL":"ATTENDRE",
    "DAR":"ATTENDRE","IMI":"ACHETER","DTT":"SURVEILLER",
    # Petites capitalisations — défaut ATTENDRE
    "DSW":"ATTENDRE","MOX":"ATTENDRE","STR":"ATTENDRE","TIM":"ATTENDRE",
    "SNP":"ATTENDRE","SLM":"ATTENDRE","JET":"ATTENDRE","M2M":"SURVEILLER",
    "INV":"ATTENDRE","S2M":"ATTENDRE","COL":"ATTENDRE",
}

# ─────────────────────────────────────────────────────────────────────────────
# SCORES FONDAMENTAUX
# Priorité 1 : fondamentaux.json → compute_fond_score() (formule dynamique)
# Priorité 2 : FOND_SCORES ci-dessous (table statique — fallback pour tickers non couverts)
# ─────────────────────────────────────────────────────────────────────────────
try:
    from pipeline.smart_money.fond_score import compute_fond_score as _cfs, score_all as _fond_all
    _FOND_COMPUTED = _fond_all()   # {sym: score} pour tous les tickers dans fondamentaux.json
    logger.info(f"fond_score: {len(_FOND_COMPUTED)} tickers chargés depuis fondamentaux.json")
except Exception as _e:
    _FOND_COMPUTED = {}
    logger.warning(f"fond_score: chargement fondamentaux.json échoué — scores statiques utilisés ({_e})")

FOND_SCORES = {
    # Tickers actifs (19)
    "CMT":7.73,"SMI":7.73,"CASH":7.95,"MNG":4.32,"AKD":7.50,"SOT":7.50,
    "SGTM":8.18,"MSA":6.59,"CFGB":7.73,"RIS":5.23,"ADI":7.05,"VCNE":6.59,
    "CMGP":6.59,"CSR":5.23,"TGCC":8.41,"ADH":4.09,"SRM":4.32,"SNA":4.09,"RDS":2.27,
    # Grandes capitalisations
    "IAM":7.50,"ATW":7.73,"BCP":7.50,"BOA":6.82,"CIH":7.05,"CDM":7.05,
    "WAF":7.27,"LHM":7.73,"GAZ":7.50,"ATL":7.27,"HPS":7.50,"LBV":7.05,
    "LES":7.05,"TQA":7.50,"MRL":7.27,"TMA":7.05,
    # Moyennes capitalisations
    "ARD":6.82,"SAF":6.82,"OUL":6.59,"CIM":7.05,"CTM":6.59,"ZLD":5.68,
    "ALU":6.36,"MGL":5.91,"DAR":5.45,"IMI":6.59,"DTT":6.36,
    # Petites capitalisations
    "DSW":6.14,"MOX":6.14,"STR":5.91,"TIM":5.68,"SNP":5.45,"SLM":6.36,
    "JET":5.91,"M2M":6.36,"INV":5.68,"S2M":5.91,"COL":6.14,
    "AFM":6.36,"AGM":6.36,"FNB":5.91,"BAL":6.14,
}

BVC_SCORES_BASE = {
    # Tickers actifs (19)
    "CMT":7.16,"SMI":6.95,"CASH":6.73,"MNG":6.59,"AKD":6.20,"SOT":6.62,
    "SGTM":5.77,"MSA":6.28,"CFGB":5.44,"RIS":4.71,"ADI":5.00,"VCNE":4.93,
    "CMGP":5.17,"CSR":4.58,"TGCC":5.22,"ADH":4.28,"SRM":4.88,"SNA":4.10,"RDS":3.76,
    # Grandes capitalisations
    "IAM":7.08,"ATW":7.25,"BCP":7.00,"BOA":6.58,"CIH":6.75,"CDM":6.75,
    "WAF":6.92,"LHM":7.10,"GAZ":7.20,"ATL":6.90,"HPS":7.15,"LBV":6.70,
    "LES":6.60,"TQA":7.05,"MRL":6.88,"TMA":6.65,
    # Moyennes capitalisations
    "ARD":6.45,"SAF":6.55,"OUL":6.30,"CIM":6.80,"CTM":6.20,"ZLD":5.40,
    "ALU":6.10,"MGL":5.70,"DAR":5.20,"IMI":6.35,"DTT":6.15,
    # Petites capitalisations
    "DSW":5.90,"MOX":5.85,"STR":5.60,"TIM":5.45,"SNP":5.20,"SLM":6.10,
    "JET":5.65,"M2M":6.10,"INV":5.40,"S2M":5.65,"COL":5.90,
    "AFM":6.10,"AGM":6.05,"FNB":5.60,"BAL":5.85,
}

FOND_DATA = {
    # ── Grandes capitalisations (nouvelles) ──────────────────────────
    "IAM": {"pe":18.5,"pb":6.2,"div":5.5,"cap":121000,"bear":120,  "base":145,  "bull":175,  "upside":5.0, "flags":1},
    "ATW": {"pe":13.5,"pb":1.8,"div":3.5,"cap":115000,"bear":420,  "base":530,  "bull":660,  "upside":8.0, "flags":0},
    "BCP": {"pe":11.5,"pb":1.3,"div":3.2,"cap":42000, "bear":205,  "base":260,  "bull":325,  "upside":7.0, "flags":0},
    "BOA": {"pe":12.0,"pb":1.3,"div":3.5,"cap":15000, "bear":170,  "base":215,  "bull":270,  "upside":7.0, "flags":0},
    "CIH": {"pe":12.5,"pb":1.5,"div":4.2,"cap":8000,  "bear":275,  "base":350,  "bull":440,  "upside":6.0, "flags":0},
    "CDM": {"pe":11.0,"pb":1.2,"div":4.5,"cap":5000,  "bear":520,  "base":660,  "bull":825,  "upside":6.0, "flags":0},
    "WAF": {"pe":14.5,"pb":2.2,"div":4.8,"cap":6500,  "bear":3500, "base":4400, "bull":5500, "upside":5.0, "flags":0},
    "LHM": {"pe":14.5,"pb":2.5,"div":4.2,"cap":16000, "bear":1520, "base":1900, "bull":2380, "upside":8.0, "flags":0},
    "GAZ": {"pe":16.5,"pb":3.1,"div":4.8,"cap":7000,  "bear":2940, "base":3700, "bull":4625, "upside":6.0, "flags":0},
    "ATL": {"pe":13.8,"pb":2.0,"div":4.5,"cap":3500,  "bear":65,   "base":82,   "bull":103,  "upside":7.0, "flags":0},
    "HPS": {"pe":24.5,"pb":4.0,"div":2.2,"cap":3800,  "bear":3100, "base":4000, "bull":5000, "upside":2.0, "flags":0},
    "LBV": {"pe":18.0,"pb":2.1,"div":2.8,"cap":4500,  "bear":4200, "base":5300, "bull":6625, "upside":4.0, "flags":0},
    "LES": {"pe":16.5,"pb":2.6,"div":4.8,"cap":3700,  "bear":148,  "base":185,  "bull":230,  "upside":6.0, "flags":0},
    "TQA": {"pe":18.5,"pb":3.8,"div":6.5,"cap":8500,  "bear":900,  "base":1150, "bull":1440, "upside":5.0, "flags":0},
    "MRL": {"pe":16.8,"pb":3.5,"div":4.5,"cap":7500,  "bear":195,  "base":250,  "bull":315,  "upside":6.0, "flags":0},
    "TMA": {"pe":15.5,"pb":3.0,"div":5.0,"cap":5000,  "bear":1450, "base":1850, "bull":2310, "upside":6.0, "flags":0},
    # ── Moyennes capitalisations (nouvelles) ─────────────────────────
    "ARD": {"pe":20.0,"pb":1.5,"div":5.5,"cap":3200,  "bear":365,  "base":465,  "bull":580,  "upside":6.0, "flags":0},
    "SAF": {"pe":13.5,"pb":1.8,"div":4.0,"cap":3000,  "bear":1000, "base":1270, "bull":1590, "upside":6.0, "flags":0},
    "OUL": {"pe":15.0,"pb":2.2,"div":3.0,"cap":2500,  "bear":1150, "base":1460, "bull":1825, "upside":6.0, "flags":0},
    "CIM": {"pe":13.5,"pb":2.0,"div":3.8,"cap":4000,  "bear":1200, "base":1540, "bull":1925, "upside":6.0, "flags":0},
    "CTM": {"pe":16.0,"pb":2.5,"div":3.5,"cap":1900,  "bear":1380, "base":1750, "bull":2190, "upside":6.0, "flags":0},
    "ZLD": {"pe":12.0,"pb":0.9,"div":3.5,"cap":1200,  "bear":350,  "base":445,  "bull":560,  "upside":6.0, "flags":1},
    "ALU": {"pe":13.0,"pb":1.8,"div":4.5,"cap":650,   "bear":880,  "base":1110, "bull":1390, "upside":6.0, "flags":0},
    "MGL": {"pe":11.0,"pb":1.2,"div":3.0,"cap":1500,  "bear":268,  "base":340,  "bull":425,  "upside":6.0, "flags":1},
    "DAR": {"pe":9.0, "pb":0.8,"div":2.0,"cap":2800,  "bear":88,   "base":112,  "bull":140,  "upside":7.0, "flags":2},
    "IMI": {"pe":19.0,"pb":1.4,"div":5.5,"cap":1800,  "bear":133,  "base":170,  "bull":213,  "upside":6.0, "flags":0},
    "DTT": {"pe":20.0,"pb":3.0,"div":2.5,"cap":2200,  "bear":375,  "base":475,  "bull":595,  "upside":6.0, "flags":0},
    # ── Petites capitalisations (nouvelles) ──────────────────────────
    "DSW": {"pe":14.0,"pb":2.0,"div":3.5,"cap":800,   "bear":350,  "base":445,  "bull":555,  "upside":5.0, "flags":0},
    "MOX": {"pe":12.5,"pb":1.6,"div":4.0,"cap":750,   "bear":300,  "base":380,  "bull":475,  "upside":5.0, "flags":0},
    "STR": {"pe":11.0,"pb":1.4,"div":3.5,"cap":600,   "bear":215,  "base":275,  "bull":344,  "upside":5.0, "flags":0},
    "TIM": {"pe":13.0,"pb":1.5,"div":3.0,"cap":500,   "bear":162,  "base":207,  "bull":258,  "upside":5.0, "flags":0},
    "SNP": {"pe":10.5,"pb":1.2,"div":3.5,"cap":1100,  "bear":890,  "base":1130, "bull":1415, "upside":5.0, "flags":1},
    "SLM": {"pe":12.0,"pb":1.8,"div":5.0,"cap":1200,  "bear":445,  "base":565,  "bull":706,  "upside":5.0, "flags":0},
    "JET": {"pe":13.5,"pb":1.5,"div":3.0,"cap":800,   "bear":324,  "base":415,  "bull":519,  "upside":6.0, "flags":0},
    "M2M": {"pe":18.0,"pb":2.5,"div":2.0,"cap":1500,  "bear":253,  "base":323,  "bull":404,  "upside":6.0, "flags":0},
    "INV": {"pe":14.0,"pb":1.8,"div":3.0,"cap":300,   "bear":100,  "base":128,  "bull":160,  "upside":5.0, "flags":0},
    "S2M": {"pe":15.0,"pb":2.0,"div":2.5,"cap":450,   "bear":150,  "base":191,  "bull":239,  "upside":5.0, "flags":0},
    "COL": {"pe":14.5,"pb":2.0,"div":4.0,"cap":1000,  "bear":74,   "base":93,   "bull":116,  "upside":6.0, "flags":0},
    "AFM": {"pe":13.0,"pb":1.7,"div":4.5,"cap":600,   "bear":484,  "base":615,  "bull":769,  "upside":5.0, "flags":0},
    "AGM": {"pe":12.5,"pb":1.5,"div":4.0,"cap":500,   "bear":3000, "base":3820, "bull":4775, "upside":5.0, "flags":0},
    "FNB": {"pe":11.0,"pb":1.3,"div":3.5,"cap":800,   "bear":733,  "base":935,  "bull":1169, "upside":5.0, "flags":0},
    "BAL": {"pe":12.0,"pb":1.5,"div":4.5,"cap":600,   "bear":190,  "base":240,  "bull":300,  "upside":5.0, "flags":0},
    # ── Tickers actifs (19) ──────────────────────────────────────────
    "CMT": {"pe":22.7,"pb":2.0,"div":0.50,"cap":8300,  "bear":4500,"base":5700, "bull":7125, "upside":13.9,"flags":0},
    "SMI": {"pe":24.8,"pb":1.4,"div":1.04,"cap":3550,  "bear":6900,"base":8800, "bull":11000,"upside":14.3,"flags":0},
    "CASH":{"pe":13.8,"pb":1.8,"div":3.2, "cap":2800,  "bear":244, "base":313,  "bull":392,  "upside":12.0,"flags":0},
    "MNG": {"pe":64.0,"pb":3.1,"div":0.27,"cap":178000,"bear":13000,"base":17000,"bull":22000,"upside":13.4,"flags":2},
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
    "ADH": {"smart":0.025,"hype":0.08,"alpha":3.1,"win":0.36,"mentions":18290,"biais":"NEUTRE","contrarian":False},
    "ADI": {"smart":0.034,"hype":0.09,"alpha":8.5,"win":0.39,"mentions":22893,"biais":"NEUTRE","contrarian":False},
    "AFMA": {"smart":0.045,"hype":0.33,"alpha":0.0,"win":0.5,"mentions":24,"biais":"NEUTRE","contrarian":False},
    "AKD": {"smart":0.015,"hype":0.12,"alpha":22.8,"win":0.45,"mentions":2888,"biais":"ACHAT","contrarian":False},
    "ATL": {"smart":0.003,"hype":0.09,"alpha":0.0,"win":0.39,"mentions":243,"biais":"NEUTRE","contrarian":False},
    "ATLANTA": {"smart":0.029,"hype":0.06,"alpha":0.0,"win":0.5,"mentions":612,"biais":"NEUTRE","contrarian":False},
    "ATW": {"smart":0.036,"hype":0.11,"alpha":0.0,"win":0.39,"mentions":2751,"biais":"NEUTRE","contrarian":False},
    "BCP": {"smart":0.014,"hype":0.09,"alpha":0.0,"win":0.39,"mentions":5379,"biais":"NEUTRE","contrarian":False},
    "BMCE": {"smart":-0.01,"hype":0.15,"alpha":0.0,"win":0.5,"mentions":653,"biais":"NEUTRE","contrarian":False},
    "BMCI": {"smart":-0.014,"hype":0.16,"alpha":0.0,"win":0.5,"mentions":835,"biais":"NEUTRE","contrarian":False},
    "BOA": {"smart":-0.007,"hype":0.14,"alpha":0.0,"win":0.39,"mentions":1284,"biais":"NEUTRE","contrarian":False},
    "CAM": {"smart":-0.02,"hype":0.08,"alpha":0.0,"win":0.5,"mentions":12,"biais":"NEUTRE","contrarian":False},
    "CASH": {"smart":0.008,"hype":0.15,"alpha":10.1,"win":0.39,"mentions":4410,"biais":"NEUTRE","contrarian":False},
    "CCA": {"smart":0.085,"hype":0.25,"alpha":0.0,"win":0.5,"mentions":8,"biais":"NEUTRE","contrarian":True},
    "CDM": {"smart":0.023,"hype":0.14,"alpha":0.0,"win":0.39,"mentions":699,"biais":"NEUTRE","contrarian":False},
    "CFGB": {"smart":0.0,"hype":0.5,"alpha":14.6,"win":0.43,"mentions":0,"biais":"ACHAT","contrarian":False},
    "CIH": {"smart":0.027,"hype":0.12,"alpha":0.0,"win":0.38,"mentions":1191,"biais":"NEUTRE","contrarian":False},
    "CIMAR": {"smart":0.012,"hype":0.14,"alpha":0.0,"win":0.5,"mentions":308,"biais":"NEUTRE","contrarian":False},
    "CMGP": {"smart":0.039,"hype":0.11,"alpha":11.5,"win":0.4,"mentions":1251,"biais":"NEUTRE","contrarian":False},
    "CMT": {"smart":0.002,"hype":0.12,"alpha":42.1,"win":0.48,"mentions":4142,"biais":"ACHAT","contrarian":False},
    "COSUMAR": {"smart":0.014,"hype":0.16,"alpha":0.0,"win":0.5,"mentions":889,"biais":"NEUTRE","contrarian":False},
    "CSR": {"smart":-0.036,"hype":0.11,"alpha":19.2,"win":0.38,"mentions":202,"biais":"NEUTRE","contrarian":False},
    "DARI": {"smart":-0.094,"hype":0.3,"alpha":0.0,"win":0.5,"mentions":70,"biais":"NEUTRE","contrarian":False},
    "DELATTRE": {"smart":-0.169,"hype":0.45,"alpha":0.0,"win":0.5,"mentions":42,"biais":"NEUTRE","contrarian":False},
    "DISWAY": {"smart":0.03,"hype":0.1,"alpha":0.0,"win":0.5,"mentions":2450,"biais":"NEUTRE","contrarian":False},
    "DWY": {"smart":-0.012,"hype":0.13,"alpha":0.0,"win":0.5,"mentions":359,"biais":"NEUTRE","contrarian":False},
    "ENGIE": {"smart":-0.143,"hype":0.46,"alpha":0.0,"win":0.5,"mentions":13,"biais":"NEUTRE","contrarian":False},
    "HALIMA": {"smart":0.0,"hype":0.0,"alpha":0.0,"win":0.5,"mentions":3,"biais":"NEUTRE","contrarian":False},
    "HPS": {"smart":0.02,"hype":0.11,"alpha":0.0,"win":0.35,"mentions":2801,"biais":"NEUTRE","contrarian":False},
    "IAM": {"smart":0.001,"hype":0.15,"alpha":0.0,"win":0.36,"mentions":3260,"biais":"NEUTRE","contrarian":False},
    "INVOLYS": {"smart":0.044,"hype":0.08,"alpha":0.0,"win":0.5,"mentions":212,"biais":"NEUTRE","contrarian":False},
    "LBV": {"smart":0.01,"hype":0.08,"alpha":0.0,"win":0.37,"mentions":256,"biais":"NEUTRE","contrarian":False},
    "LESIEUR": {"smart":-0.025,"hype":0.14,"alpha":0.0,"win":0.5,"mentions":652,"biais":"NEUTRE","contrarian":False},
    "M2M": {"smart":-0.025,"hype":0.14,"alpha":0.0,"win":0.37,"mentions":250,"biais":"NEUTRE","contrarian":False},
    "MAMDA": {"smart":-0.005,"hype":0.18,"alpha":0.0,"win":0.5,"mentions":11,"biais":"NEUTRE","contrarian":False},
    "MIC": {"smart":0.016,"hype":0.1,"alpha":0.0,"win":0.34,"mentions":512,"biais":"NEUTRE","contrarian":False},
    "MNG": {"smart":0.023,"hype":0.1,"alpha":55.3,"win":0.44,"mentions":6665,"biais":"ACHAT","contrarian":False},
    "MSA": {"smart":0.041,"hype":0.07,"alpha":21.0,"win":0.38,"mentions":1433,"biais":"NEUTRE","contrarian":False},
    "MSIN": {"smart":-0.082,"hype":0.41,"alpha":0.0,"win":0.5,"mentions":27,"biais":"NEUTRE","contrarian":False},
    "MUT": {"smart":0.057,"hype":0.07,"alpha":0.0,"win":0.35,"mentions":338,"biais":"NEUTRE","contrarian":False},
    "NAPS": {"smart":-0.122,"hype":0.37,"alpha":0.0,"win":0.5,"mentions":41,"biais":"NEUTRE","contrarian":False},
    "NEXANS": {"smart":-0.033,"hype":0.21,"alpha":0.0,"win":0.5,"mentions":34,"biais":"NEUTRE","contrarian":False},
    "OUL": {"smart":-0.032,"hype":0.14,"alpha":0.0,"win":0.38,"mentions":98,"biais":"NEUTRE","contrarian":False},
    "PHARM": {"smart":-0.36,"hype":1.0,"alpha":0.0,"win":0.5,"mentions":2,"biais":"NEUTRE","contrarian":False},
    "RDS": {"smart":0.033,"hype":0.07,"alpha":5.2,"win":0.35,"mentions":14692,"biais":"NEUTRE","contrarian":False},
    "REBAB": {"smart":-0.013,"hype":0.08,"alpha":0.0,"win":0.5,"mentions":66,"biais":"NEUTRE","contrarian":False},
    "RIS": {"smart":0.028,"hype":0.09,"alpha":10.3,"win":0.38,"mentions":3096,"biais":"NEUTRE","contrarian":False},
    "RMA": {"smart":0.01,"hype":0.08,"alpha":0.0,"win":0.5,"mentions":48,"biais":"NEUTRE","contrarian":False},
    "S2M": {"smart":0.049,"hype":0.08,"alpha":0.0,"win":0.36,"mentions":792,"biais":"NEUTRE","contrarian":False},
    "SGMB": {"smart":0.016,"hype":0.09,"alpha":0.0,"win":0.5,"mentions":107,"biais":"NEUTRE","contrarian":False},
    "SGTM": {"smart":0.006,"hype":0.14,"alpha":15.9,"win":0.42,"mentions":1841,"biais":"ACHAT","contrarian":False},
    "SMI": {"smart":0.021,"hype":0.09,"alpha":38.5,"win":0.43,"mentions":4279,"biais":"ACHAT","contrarian":False},
    "SNA": {"smart":0.021,"hype":0.06,"alpha":7.6,"win":0.36,"mentions":2669,"biais":"NEUTRE","contrarian":False},
    "SODEP": {"smart":0.071,"hype":0.07,"alpha":0.0,"win":0.5,"mentions":104,"biais":"NEUTRE","contrarian":False},
    "SOT": {"smart":0.025,"hype":0.11,"alpha":5.0,"win":0.41,"mentions":1772,"biais":"NEUTRE","contrarian":False},
    "SOTHEMA": {"smart":0.022,"hype":0.11,"alpha":0.0,"win":0.5,"mentions":1517,"biais":"NEUTRE","contrarian":False},
    "SRM": {"smart":0.014,"hype":0.08,"alpha":9.8,"win":0.41,"mentions":853,"biais":"NEUTRE","contrarian":False},
    "TGCC": {"smart":0.031,"hype":0.1,"alpha":18.7,"win":0.43,"mentions":9537,"biais":"ACHAT","contrarian":False},
    "TIMAR": {"smart":-0.032,"hype":0.14,"alpha":0.0,"win":0.5,"mentions":85,"biais":"NEUTRE","contrarian":False},
    "TOTAL": {"smart":0.003,"hype":0.16,"alpha":0.0,"win":0.5,"mentions":1444,"biais":"NEUTRE","contrarian":False},
    "UNIMER": {"smart":-0.036,"hype":0.12,"alpha":0.0,"win":0.5,"mentions":40,"biais":"NEUTRE","contrarian":False},
    "VCNE": {"smart":0.0,"hype":0.5,"alpha":5.5,"win":0.38,"mentions":0,"biais":"NEUTRE","contrarian":False},
    "WAF": {"smart":-0.022,"hype":0.12,"alpha":0.0,"win":0.38,"mentions":425,"biais":"NEUTRE","contrarian":False},
    "WAFA": {"smart":-0.024,"hype":0.12,"alpha":0.0,"win":0.5,"mentions":418,"biais":"NEUTRE","contrarian":False},
    "YNNA": {"smart":0.017,"hype":0.42,"alpha":0.0,"win":0.5,"mentions":12,"biais":"NEUTRE","contrarian":False},
    "ZELLIDJA": {"smart":-0.004,"hype":0.03,"alpha":0.0,"win":0.5,"mentions":40,"biais":"NEUTRE","contrarian":False},
}

# Overlay dynamique depuis whatsapp_analysis/output/ si les fichiers existent
# (met à jour alpha, win, mentions, biais sans toucher smart/hype — INVIOLABLE)
def _load_nlp_csv_overlay():
    try:
        import csv
        base = Path(__file__).parent / "whatsapp_analysis" / "output"
        final_path  = base / "final_rankings.csv"
        scores_path = base / "stock_scores.csv"
        if not final_path.exists() or not scores_path.exists():
            return

        # final_rankings: alpha_12m, p_outperform_12m, signal
        with open(final_path, encoding="utf-8") as f:
            for row in csv.DictReader(f):
                t = row.get("ticker", "").strip()
                if t not in SENTIMENT:
                    continue
                try:
                    if row.get("alpha_12m"):
                        SENTIMENT[t]["alpha"] = float(row["alpha_12m"])
                    if row.get("p_outperform_12m"):
                        SENTIMENT[t]["win"]   = float(row["p_outperform_12m"])
                    sig = row.get("signal", "").strip().upper()
                    if sig in ("ACHAT", "VENTE", "NEUTRE"):
                        SENTIMENT[t]["biais"] = sig
                except (ValueError, KeyError):
                    pass

        # stock_scores: total_mentions
        with open(scores_path, encoding="utf-8") as f:
            for row in csv.DictReader(f):
                t = row.get("ticker", "").strip()
                if t not in SENTIMENT:
                    continue
                try:
                    if row.get("total_mentions"):
                        SENTIMENT[t]["mentions"] = int(float(row["total_mentions"]))
                except (ValueError, KeyError):
                    pass
    except Exception:
        pass  # fallback silencieux sur le dict statique

_load_nlp_csv_overlay()


# ─────────────────────────────────────────────────────────────────────────────
# FONDAMENTAUX PRÉVISIONNELS — IDBourse DATA+
# ─────────────────────────────────────────────────────────────────────────────
# Bornes de vraisemblance. Elles ne « corrigent » rien : elles écartent ce qui
# ne peut pas être une estimation d'analyste, plutôt que de l'afficher.
#
# Le seuil du PER vient de la distribution mesurée sur l'export : médiane 18,
# troisième quartile 23, puis 40, 46, 50 — et ensuite un saut à 102, 204, 404.
# Un seuil à 100 tombe dans ce vide. Il n'écarte que Lesieur et Unimer, dont
# les valeurs ne sont pas des prévisions mais des artefacts de l'export.
#
# Un PER négatif est écarté de même : une société en perte n'a pas de PER,
# elle a un ratio dépourvu de sens qu'il vaut mieux ne pas afficher. Idem pour
# un price-to-book négatif, qui signale des capitaux propres négatifs.
_DP_BORNES = {
    "per_26e":        (0.1, 100),
    "per_27e":        (0.1, 100),
    "dy_26e":         (0,    25),
    "dy_27e":         (0,    25),
    "roe_25":         (-100, 100),
    "roa_25":         (-100, 100),
    "pb_25":          (0.01,  50),
    "marge_nette_25": (-100, 100),
}


def _load_dataplus():
    """Fondamentaux prévisionnels de l'export IDBourse DATA+.

    ⚠️ Ces valeurs ne rejoignent JAMAIS `pe`, `pb` ou `div`. DATA+ publie du
    prévisionnel — un PER calculé sur le bénéfice attendu 2026 — là où nos
    champs portent du réalisé. Managem à 7,3 réalisé et 29,0 attendu n'est pas
    une contradiction à arbitrer : ce sont deux mesures différentes. Les fondre
    fausserait les ratios publiés et, par ricochet, le score v5.3 (règle R8).
    Elles vivent donc dans un espace de noms à part, `fwd`, où la confusion est
    structurellement impossible.

    `cap_mad` est volontairement ignoré : la capitalisation de l'export est
    calculée sur les cours du 1er juillet. Nous la recalculons à chaque run sur
    le cours du jour, ce qui vaut mieux qu'un chiffre vieux de sept semaines.

    Renvoie {symbole: {champs retenus, "asof": date d'export}}, vide si le
    fichier manque — le terminal affiche alors simplement moins de choses.
    """
    chemin = Path(__file__).parent / "pipeline" / "idbourse_dataplus.json"
    if not chemin.exists():
        logger.info("DATA+ : fichier absent — fondamentaux prévisionnels non publiés")
        return {}
    try:
        brut = json.loads(chemin.read_text(encoding="utf-8"))
    except Exception as e:
        logger.warning(f"DATA+ illisible ({e}) — fondamentaux prévisionnels ignorés")
        return {}

    export_asof = str(brut.get("_export_date") or "")[:10] or None
    out, ecartes = {}, []
    for sym, ligne in (brut.get("tickers") or {}).items():
        champs = {}
        for cle, (bas, haut) in _DP_BORNES.items():
            val = ligne.get(cle)
            if not isinstance(val, (int, float)):
                continue
            if bas <= val <= haut:
                champs[cle] = round(float(val), 2)
            else:
                ecartes.append(f"{sym}.{cle}={val}")
        if champs:
            champs["asof"] = export_asof
            out[sym] = champs

    if ecartes:
        logger.warning(f"DATA+ : {len(ecartes)} valeur(s) hors bornes, nullifiées — "
                       f"{', '.join(ecartes[:6])}")
    logger.info(f"DATA+ : {len(out)} sociétés chargées (export du {export_asof})")
    return out


DATAPLUS = _load_dataplus()

# ─────────────────────────────────────────────────────────────────────────────
# CONNECTEUR IDBOURSE / MÉDIAS24
# ─────────────────────────────────────────────────────────────────────────────

def idb_get(endpoint, timeout=10):
    # Depuis le 05/08/2026 (~12h Casablanca), IDBourse contrôle la provenance :
    # sans Referer, /api/proxy/* renvoie HTTP 403 {"error":"Forbidden"} — d'où
    # "IDBourse: 0/77 tickers reçus" et le basculement de tout le moteur sur les
    # fallbacks. Le Referer de la page publique suffit à rétablir l'accès.
    hdrs = {**HEADERS, "Referer": f"{IDB_BASE}/masi", "Origin": IDB_BASE,
            "Accept": "application/json, text/plain, */*"}
    try:
        r = requests.get(f"{IDB_BASE}{endpoint}", headers=hdrs, timeout=timeout)
        if r.status_code == 200:
            return r.json()
        logger.warning(f"IDBourse {endpoint}: HTTP {r.status_code} — {r.text[:80]}")
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

def fetch_med24_quote(ticker):
    """Cours individuel Médias24 via getStockInfo (prix live + volume du jour)."""
    isin = ISIN_MAP.get(ticker)
    if not isin:
        return None
    data = med_get({"method": "getStockInfo", "ISIN": isin})
    r = (data or {}).get("result")
    if not r:
        return None
    try:
        price = float(r.get("cours") or 0)
        if price <= 0:
            return None
        return {
            "price": price,
            "chg":   float(r.get("variation") or 0),
            "vol":   int(float(r.get("volume") or r.get("volumeEchange") or 0)),
            "open":  float(r.get("ouverture") or price),
        }
    except Exception:
        return None

def _cloture_precedente(df, asof):
    """Dernière clôture STRICTEMENT antérieure à la séance `asof`.

    `.iloc[-1]` ne convient pas : l'étape 6c écrit la bougie de la séance en
    cours à la fin de chaque run, si bien que dès le second run du jour la
    dernière bougie EST la séance cotée. Comparer le prix à elle-même donnait
    une variation de 0,00% sur tout le marché.
    """
    if df is None or "c" not in df:
        return None
    serie = df["c"]
    if asof and "d" in df:
        serie = df.loc[df["d"].astype(str) < asof, "c"]
    elif len(df) > 1:
        serie = df["c"].iloc[:-1]
    serie = pd.to_numeric(serie, errors="coerce").dropna()
    return float(serie.iloc[-1]) if len(serie) else None


def fetch_all_idb():
    """Toutes les cotations IDBourse en un seul appel.

    Champs IDBourse confirmés :
      dernier_cours  — prix (float)
      variation      — % variation (float, 53/86 non-nuls en séance)
      volume_en_titres — nb titres échangés (string "3 726", espaces à supprimer)
      volume         — montant en DH (NE PAS utiliser pour le nb de titres)
      ouverture      — prix d'ouverture (string "181,10", virgule décimale)
      url            — contient le code BVC : .../instruments/CSR → extrait "CSR"
      updated_at     — date de la séance cotée (≠ date du run)

    Renseigne au passage IDB_ASOF, la date de séance de la source. Sans elle
    on ne peut pas distinguer « le marché a coté aujourd'hui » de « la source
    ressert la dernière clôture », les deux renvoyant exactement le même prix.
    """
    global IDB_ASOF
    data = idb_get("/api/proxy/get_all_data")
    if not isinstance(data, list):
        return {}
    dates = sorted({str(d["updated_at"])[:10] for d in data if d.get("updated_at")})
    IDB_ASOF = dates[-1] if dates else ""
    # IDBourse sert plusieurs lignes pour un même instrument, sous des raisons
    # sociales successives et avec des dates de séance différentes :
    #   AGMA   → 6860 (07/08)  et  6700 (05/08)
    #   LHM    → « Holcim Maroc S.A » 1750 (05/08) et « LAFARGEHOLCIM MAROC »
    #            1800 (03/06)
    # Le code gardait la dernière ligne rencontrée, soit une fois sur deux la
    # plus ancienne. On trie par date de séance pour que la plus récente écrase.
    data = sorted(data, key=lambda d: str(d.get("updated_at") or ""))
    out = {}
    for d in data:
        if not d.get("name") or not d.get("dernier_cours"):
            continue
        # La date de séance de la ligne est conservée telle quelle. Une ligne
        # antérieure à IDB_ASOF n'est pas la cotation du jour mais un reliquat
        # non rafraîchi : elle ne doit pas primer sur les chandelles (Holcim
        # restait à 1750 du 05/08 alors que la clôture du 07/08 valait 1800).
        # On ne la jette plus pour autant — c'est le dernier cours réellement
        # coté, et il vaut mieux que le statique pour un titre peu liquide
        # comme Diac Salaf. Le consommateur arbitre, et marque `stale`.
        # Extraire le code BVC depuis l'URL (.../instruments/CODE)
        # `or ""` volontaire : IDBourse renvoie url:null sur certains titres
        # (DIAC SALAF, STROC, HOLCIM) — .get("url","") laisserait passer None.
        url = d.get("url") or ""
        ticker_from_url = url.split("/instruments/")[-1].upper() if "/instruments/" in url else ""
        # Le code de l'URL est le ticker OFFICIEL BVC, qui n'est pas toujours
        # le nôtre. Le traduire AVANT de le chercher dans ISIN_MAP, sinon :
        #   — un code inconnu de nous fait rejeter la ligne (SID=Sonasid,
        #     SBM=Bs.Maroc, ZDJ=Zellidja… 29 titres perdus silencieusement) ;
        #   — pire, un code qui existe chez nous mais désigne une AUTRE société
        #     écrase la bonne. C'est le cas de SNA : BVC l'attribue à Stokvis,
        #     nous à Sonasid. Sonasid affichait donc 74 DH au lieu de 2000.
        # IDB_TICKER_MAP est déjà la table de correspondance officielle (02/07).
        sym = IDB_TICKER_INV.get(ticker_from_url, ticker_from_url)
        if not (sym and sym in ISIN_MAP):
            n = d["name"].upper()
            sym = IDB_NAME_MAP.get(n, n)
            if sym not in ISIN_MAP:
                continue
        try:
            # volume_en_titres = "3 726" (nombre de titres, espaces à supprimer)
            vol_str = str(d.get("volume_en_titres") or "0").replace(" ", "").replace(" ", "").replace(",", "")
            vol_int = int(float(vol_str)) if vol_str and vol_str not in ("0", "-", "") else 0
            # ouverture : "181,10", mais aussi "1 742,00" au-delà du millier et
            # "-" quand la séance n'a pas ouvert. Ne pas retirer l'espace des
            # milliers faisait lever ValueError, et l'except emportait TOUTE la
            # ligne : Holcim disparaissait du batch pour un séparateur.
            opn_str = (str(d.get("ouverture") or "")
                       .replace(" ", "").replace(" ", "").replace(",", "."))
            opn_val = float(opn_str) if opn_str and opn_str != "-" else None
            # capitalisation_boursiere est en DH ; le terminal l'affiche en
            # millions. C'est la seule capitalisation calculée sur le cours du
            # jour — celle de FOND_DATA est figée depuis des mois.
            cap_str = (str(d.get("capitalisation_boursiere") or "")
                       .replace(" ", "").replace(" ", "").replace(",", "."))
            try:
                cap_mdh = round(float(cap_str) / 1e6) if cap_str and cap_str != "-" else None
            except ValueError:
                cap_mdh = None
            out[sym] = {
                "price": float(d["dernier_cours"]),
                "chg":   float(d.get("variation") or 0),
                "open":  opn_val,
                "vol":   vol_int,
                "cap":   cap_mdh,
                "asof":  str(d.get("updated_at") or "")[:10],
            }
        except (ValueError, TypeError):
            continue
    if out:
        mapping_str = "  ".join(
            f"{s}={v['price']}(chg={v['chg']:+.2f}%,vol={v['vol']})"
            for s, v in list(out.items())[:8]
        )
        logger.info(f"IDBourse [{len(out)} tickers]: {mapping_str}")
    return out

def _recaler_seance_fantome(live_prices):
    """Ramène IDB_ASOF à la séance réelle quand la source date un jour fermé.

    Le 14/08/2026 — férié au Maroc — IDBourse a rediffusé les cours du 13/08 en
    les estampillant du 14. `updated_at` étant notre seule autorité sur la date
    de séance, tout le pipeline a suivi : 77 tickers étiquetés d'une séance qui
    n'a pas eu lieu, et 71 bougies dupliquant le 13/08.

    La règle R9 (chg=0 ET vol=0) ne détecte pas ce cas : la source rediffuse
    aussi la variation de la veille, si bien que 67 titres sur 77 portaient un
    chg non nul. Le signal n'existe qu'à l'échelle du marché — une séance réelle
    ne reproduit jamais toutes les clôtures au centime près. Mesuré sur les deux
    cas : 71/71 identiques le 14/08 (férié), 6/44 le 13/08 (séance cotée).

    Ne dégrade pas les prix : ils restent la dernière clôture, exacte. Seule
    l'étiquette de date est corrigée, pour ne pas annoncer comme fraîche une
    séance fictive. Aucun calendrier de jours fériés n'est nécessaire.
    """
    global IDB_ASOF
    if not IDB_ASOF or not live_prices:
        return None
    candles_dir = Path(__file__).parent / "pipeline" / "candles"
    if not candles_dir.exists():
        return None
    ident = total = 0
    veille = ""
    for sym, row in live_prices.items():
        if str(row.get("asof") or "")[:10] != IDB_ASOF:
            continue  # ligne non rafraîchie : elle ne dit rien sur la séance
        prix = row.get("price") or 0
        cfp = candles_dir / f"{sym}.json"
        if prix <= 0 or not cfp.exists():
            continue
        try:
            serie = json.loads(cfp.read_text(encoding="utf-8"))
        except Exception:
            continue
        if not serie or serie[-1].get("d") >= IDB_ASOF:
            continue  # séance déjà enregistrée : hors du test
        total += 1
        veille = max(veille, serie[-1].get("d") or "")
        if round(float(prix), 2) == round(float(serie[-1].get("c") or 0), 2):
            ident += 1
    # Un férié connu abaisse le seuil sans se substituer à la mesure : le
    # calendrier relève la présomption, la donnée tranche. Si la Bourse cotait
    # malgré tout un jour férié, les clôtures différeraient et rien ne serait
    # purgé.
    ferie = est_ferie_fixe(IDB_ASOF)
    seuil = 0.70 if ferie else 0.95
    if ferie:
        logger.warning(f"{IDB_ASOF} est un jour férié à date fixe — "
                       f"seuil de détection abaissé à {seuil:.0%}")
    if total >= 20 and ident / total >= seuil and veille:
        logger.warning(
            f"Séance fantôme : la source date ses cours du {IDB_ASOF}, mais "
            f"{ident}/{total} clôtures sont identiques au {veille}. Marché "
            f"fermé{' — férié confirmé' if ferie else ' (férié ?)'} — "
            f"séance ramenée au {veille}.")
        # Recaler aussi la date portée par chaque ligne : c'est elle qui
        # alimente `_meta.prix_asof`. La laisser au 14/08 afficherait sur le
        # terminal une séance fictive comme dernière cotation connue.
        for row in live_prices.values():
            if str(row.get("asof") or "")[:10] == IDB_ASOF:
                row["asof"] = veille
        annoncee = IDB_ASOF
        IDB_ASOF = veille
        return annoncee   # la date que la source annonçait à tort
    return None


CDG_API = "https://www.cdgcapitalbourse.ma/api/"


def fetch_all_cdg():
    """Cotations de la séance depuis CDG Capital Bourse, différées de 15 min.

    Deuxième maillon réel de la chaîne de repli. Le premier repli déclaré,
    Médias24, ne fonctionne plus : son API répond HTTP 403 derrière un
    contrôle Cloudflare (« Just a moment… »), vérifié le 27/08/2026. La
    chaîne n'avait donc qu'un seul maillon vivant — le jour où IDBourse
    prend du retard, comme ce 27/08 où elle servait encore le 26, plus rien
    ne rattrapait la séance.

    Cette source est meilleure qu'IDBourse sur un point : elle livre un
    chandelier complet (ouverture, plus-haut, plus-bas, clôture, quantité)
    plus le cours de référence, là où IDBourse ne donne que le dernier cours.

    ⚠️ Les codes renvoyés sont les tickers OFFICIELS BVC — le `SNA` de CDG
    est Stokvis, pas Sonasid. La traduction par IDB_TICKER_INV est obligatoire,
    comme pour IDBourse et pour le bulletin PDF.

    Renvoie {notre_symbole: {price, chg, open, high, low, vol, asof}}.
    """
    corps = {"ACTIONS": [{
        "ACTION": {"NAME": "MARKET-RESUME", "TYPE": "SELECT", "VALUE": "MARKET-RESUME"},
        "PARAMS": [{"NAME": "Lang_", "TYPE": "S", "VALUE": "fr"},
                   {"NAME": "Espace_", "TYPE": "I", "VALUE": "1"},
                   {"NAME": "IdPartener_", "TYPE": "I", "VALUE": "1"},
                   {"NAME": "TypeStocks_", "TYPE": "S", "VALUE": "1"},
                   {"NAME": "TypeCotation_", "TYPE": "S", "VALUE": "1"}]}]}
    try:
        r = requests.post(CDG_API, json=corps, timeout=30, headers={
            **HEADERS,
            "Content-Type": "application/json",
            "Referer": "https://www.cdgcapitalbourse.ma/Bourse/market",
            "Origin":  "https://www.cdgcapitalbourse.ma"})
        if r.status_code != 200:
            logger.warning(f"CDG Capital Bourse : HTTP {r.status_code}")
            return {}
        bloc = r.json()[0]["MARKET-RESUME"]
        if not bloc.get("Valid"):
            logger.warning(f"CDG : réponse invalide — {str(bloc.get('Data'))[:80]}")
            return {}
        lignes = bloc["Data"]
        if lignes and isinstance(lignes[0], list):
            lignes = lignes[0]
    except Exception as e:
        logger.warning(f"CDG Capital Bourse injoignable : {e}")
        return {}

    def _f(v):
        try:
            return float(v)
        except (TypeError, ValueError):
            return None

    out = {}
    for d in lignes:
        sym = IDB_TICKER_INV.get(str(d.get("Symbol") or "").upper())
        prix = _f(d.get("Cours"))
        if not sym or not prix or prix <= 0:
            continue
        # « 27/08/2026 » → « 2026-08-27 ». Une ligne sans date est écartée :
        # sans elle on ne peut pas juger la fraîcheur, et c'est précisément
        # ce qui manquait le 14/08 pour repérer la séance fantôme.
        brut = str(d.get("DateDernierCours") or "")
        asof = ""
        if "/" in brut:
            j, m, a = brut[:10].split("/")
            asof = f"{a}-{m}-{j}"
        if not asof:
            continue
        out[sym] = {
            "price": round(prix, 2),
            "chg":   round(_f(d.get("Variation")) or 0, 2),
            "open":  _f(d.get("Ouverture")),
            "high":  _f(d.get("PlusHaut")),
            "low":   _f(d.get("PlusBas")),
            "vol":   int(_f(d.get("QteEchangee")) or 0),
            "asof":  asof,
        }
    if out:
        dates = collections.Counter(v["asof"] for v in out.values())
        logger.info(f"CDG Capital Bourse : {len(out)} titres · séances {dict(dates)}")
    return out


def fetch_masi():
    """Indice MASI (variation % pour contexte marché)."""
    # 45 s et non les 10 s par défaut : mesuré le 12/08, cet endpoint répond en
    # 33 secondes. Il échouait donc à chaque run et l'indice restait à zéro dans
    # l'en-tête du terminal — sans que rien ne le signale, `fetch_masi` renvoyant
    # silencieusement {value: 0} en cas d'échec.
    m = idb_get("/api/proxy/masi-data", timeout=45)
    if m and m.get("value"):
        # La charge utile porte sa propre date, qu'on ne lisait pas. Relevé le
        # 14/08 : l'endpoint servait encore la valeur du 10/08 et l'en-tête
        # l'affichait comme l'indice du jour. Quatre jours d'un chiffre faux.
        #
        # ⚠️ Le drapeau `stale` de la source ne dit PAS « donnée périmée » : il
        # dit « pas en direct », et il vaut true dès la clôture. S'y fier
        # allumait l'alerte en permanence hors séance — donc en permanence pour
        # un produit J+1 publié avant l'ouverture. Une alerte toujours allumée
        # n'alerte plus. Seule la date fait foi, et elle suffit : au 14/08 la
        # charge utile était datée du 10, la comparaison l'aurait attrapée.
        asof = str(m.get("date") or "")[:10]
        # Repère de séance. IDB_ASOF vient de la cotation des titres ; quand
        # IDBourse est muette — panne, ou jour férié où son API renvoie 500 —
        # il est vide, et plus rien ne contredit une charge utile qui se date
        # elle-même du jour. Relevé le 21/08, férié : l'indice valait la
        # clôture du 19 et s'affichait « à jour au 21 ». On retombe alors sur
        # la dernière séance présente dans les chandelles.
        try:
            sys.path.insert(0, str(Path(__file__).parent / "pipeline"))
            from seance import derniere_seance_connue
            reference = IDB_ASOF or derniere_seance_connue()
        except Exception:
            reference = IDB_ASOF
        # Un férié à date fixe tranche à lui seul : la Bourse n'a pas coté,
        # donc l'indice ne peut pas être celui du jour.
        impossible = est_ferie_fixe(asof)
        perime = (bool(reference) and bool(asof) and asof < reference) or impossible
        # Quand la source se date d'un jour sans cotation, sa date est fausse
        # et l'afficher telle quelle ferait mentir le badge (« ⚠ 21/08 » pour
        # une valeur du 19). On retient alors la dernière séance réelle : c'est
        # la date la plus tardive à laquelle cette valeur a pu être produite.
        if impossible and reference:
            logger.warning(f"MASI : la source le date du {asof}, jour férié — "
                           f"ramené à la séance du {reference}")
            asof = reference
        elif perime:
            logger.warning(f"MASI périmé — valeur de la séance {asof or 'inconnue'}")
        return {"value": float(m["value"]), "chg": float(m.get("variation", 0) or 0),
                "asof": asof or None, "stale": perime}
    logger.warning("MASI indisponible — l'en-tête affichera 0")
    return {"value": 0, "chg": 0, "asof": None, "stale": True}

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

def calc_macd(closes: pd.Series, fast=12, slow=26, signal=9) -> tuple:
    """MACD(12,26,9) — retourne (macd, signal, histogram) ou (None,None,None)."""
    if len(closes) < slow + signal:
        return None, None, None
    ema_fast   = closes.ewm(span=fast, adjust=False).mean()
    ema_slow   = closes.ewm(span=slow, adjust=False).mean()
    macd_line  = ema_fast - ema_slow
    sig_line   = macd_line.ewm(span=signal, adjust=False).mean()
    histogram  = macd_line - sig_line
    return (
        round(float(macd_line.iloc[-1]), 4),
        round(float(sig_line.iloc[-1]),  4),
        round(float(histogram.iloc[-1]), 4),
    )

def calc_bollinger(closes: pd.Series, period=20, n_std=2.0) -> tuple:
    """Bollinger Bands(20,2) — retourne (upper, middle, lower) ou (None,None,None)."""
    if len(closes) < period:
        return None, None, None
    tail    = closes.tail(period)
    middle  = tail.mean()
    std     = tail.std(ddof=1)
    return (
        round(float(middle + n_std * std), 2),
        round(float(middle), 2),
        round(float(middle - n_std * std), 2),
    )

def calc_stoch(closes: pd.Series, highs: pd.Series, lows: pd.Series,
               k_period=14, d_period=3) -> tuple:
    """Stochastique(14,3) — retourne (%K, %D) ou (None, None)."""
    if len(closes) < k_period:
        return None, None
    k_values = []
    for i in range(d_period):
        idx   = len(closes) - 1 - i
        if idx < k_period - 1:
            break
        c     = float(closes.iloc[idx])
        hh    = float(highs.iloc[idx - k_period + 1: idx + 1].max())
        ll    = float(lows.iloc[idx  - k_period + 1: idx + 1].min())
        denom = hh - ll
        k_values.append(100 * (c - ll) / denom if denom > 0 else 50.0)
    if not k_values:
        return None, None
    k_now = round(k_values[0], 2)
    d_now = round(float(np.mean(k_values)), 2)
    return k_now, d_now

def calc_obv(closes: pd.Series, volumes: pd.Series) -> int:
    """On-Balance Volume — pression acheteur cumulée."""
    if len(closes) < 2:
        return 0
    obv = 0
    prev = float(closes.iloc[0])
    for i in range(1, len(closes)):
        c   = float(closes.iloc[i])
        vol = float(volumes.iloc[i]) if i < len(volumes) else 0
        if c > prev:
            obv += vol
        elif c < prev:
            obv -= vol
        prev = c
    return int(obv)


def calc_adx(highs: pd.Series, lows: pd.Series, closes: pd.Series,
             period: int = 14) -> tuple:
    """ADX de Wilder (14) — retourne (adx, +DI, -DI) ou (None, None, None)."""
    n = len(closes)
    if n < period * 2 + 1:
        return None, None, None
    try:
        h = highs.values.astype(float)
        l = lows.values.astype(float)
        c = closes.values.astype(float)
        tr   = np.maximum(h[1:] - l[1:], np.maximum(np.abs(h[1:] - c[:-1]), np.abs(l[1:] - c[:-1])))
        pdm  = np.where((h[1:] - h[:-1]) > (l[:-1] - l[1:]), np.maximum(h[1:] - h[:-1], 0), 0)
        mdm  = np.where((l[:-1] - l[1:]) > (h[1:] - h[:-1]), np.maximum(l[:-1] - l[1:], 0), 0)
        # Wilder smoothing
        def wilder(arr, p):
            s = np.zeros(len(arr))
            s[p - 1] = arr[:p].sum()
            for i in range(p, len(arr)):
                s[i] = s[i - 1] - s[i - 1] / p + arr[i]
            return s
        atr  = wilder(tr,  period)
        pdi_ = wilder(pdm, period)
        mdi_ = wilder(mdm, period)
        with np.errstate(divide="ignore", invalid="ignore"):
            pdi = np.where(atr > 0, 100 * pdi_ / atr, 0)
            mdi = np.where(atr > 0, 100 * mdi_ / atr, 0)
            dx  = np.where((pdi + mdi) > 0, 100 * np.abs(pdi - mdi) / (pdi + mdi), 0)
        adx = wilder(dx[period:], period)
        if len(adx) == 0 or adx[-1] == 0:
            return None, None, None
        return (round(float(adx[-1]), 1),
                round(float(pdi[-1]), 1),
                round(float(mdi[-1]), 1))
    except Exception:
        return None, None, None


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
        elif pos < 0.10:          # proche du bas = rebond potentiel (BVC peu liquide)
            score += 0.3

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

def _meta_ticker(ticker, src_prix, prix_asof, sent, df_candles) -> dict:
    """Provenance du prix et score de confiance 0–5.

    Le score suit la spécification du CLAUDE.md, un point par garantie :
      1. prix de la dernière séance cotée (ni périmé, ni statique)
      2. fondamentaux réels — présents dans fondamentaux.json, pas la table figée
      3. RSI calculable — au moins 14 chandelles réelles
      4. corpus NLP significatif — plus de 10 mentions
      5. smart money disponible — win rate renseigné

    Un score ≤ 1 signifie que la note repose sur des données de repli : le
    frontend grise alors le signal plutôt que d'afficher un ACHETER trompeur.
    """
    # Une source sans date propre est périmée par construction : elle recopie
    # un run antérieur et se reconduirait indéfiniment sans jamais le signaler.
    stale = (src_prix in ("static", "financial", "data_json_precedent", "")
             or not prix_asof
             or bool(IDB_ASOF and prix_asof < IDB_ASOF))

    n_bougies = 0
    if df_candles is not None:
        try:
            n_bougies = len(df_candles)
        except TypeError:
            n_bougies = 0

    confiance = sum((
        0 if stale else 1,
        1 if ticker in _FOND_COMPUTED else 0,
        1 if n_bougies >= 14 else 0,
        1 if (sent.get("mentions") or 0) > 10 else 0,
        1 if sent.get("win") is not None else 0,
    ))

    return {
        "source_prix":  src_prix or "inconnu",
        "source_fond":  "fondamentaux_json" if ticker in _FOND_COMPUTED else "table_statique",
        "prix_asof":    prix_asof or None,
        "stale":        stale,
        "confidence":   confiance,
        "n_candles":    n_bougies,
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
    }


def _objectifs(ticker, price, fd) -> dict:
    """Objectifs bear/base/bull, écartés s'ils ne sont plus à l'échelle du cours.

    Ils viennent de FOND_DATA, une table codée en dur qui n'a pas suivi les
    opérations sur titres : HPS y vise 3 100 DH après un split 1:10 qui a
    ramené le cours à 634, Managem 13 000 après le sien. Un objectif quatre
    fois éloigné du cours n'est pas une prévision, c'est un vestige.

    Seuil : un facteur 2 dans un sens ou dans l'autre. Un objectif qui double
    le cours ou le divise par deux n'est plus une prévision.

    ⚠️ Ce filtre n'attrape que l'absurde. La table est périmée bien au-delà —
    les deux tiers des objectifs sont sous le cours du jour. Entre « cible
    obsolète » et « titre jugé surévalué », rien ne permet de trancher depuis
    une valeur figée : il faut recalculer les objectifs, pas les filtrer.

    Règle LOI N°3 : origine incertaine → nullifier, ne pas inventer. On ne
    les rééchelonne pas — le ratio de split ne suffirait pas à valider une
    cible dont on ignore la date et la méthode.
    """
    base = fd.get("base")
    if price and isinstance(base, (int, float)) and base > 0 and not (0.5 < base / price < 2):
        logger.warning(f"  {ticker}: objectifs périmés (base={base} vs cours={price}) — nullifiés")
        return {"bear": None, "base": None, "bull": None, "upside": None}
    return {"bear": fd.get("bear"), "base": fd.get("base"),
            "bull": fd.get("bull"), "upside": fd.get("upside")}


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
    if (upside or 0) < -10 and bvc_bull:
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

    conv = "CONFIRME" if (bvc_bull and nlp_bull) else "DIVERGE"

    return {
        "v53":       final,
        "bvc":       round(bvc_score, 2),
        "delta":     round(final - bvc_score, 2),
        "nlp":       round(sent["smart"], 2),
        "score_tech": round(score_tech, 2),
        "score_nlp": round(score_nlp, 2),
        "alpha":  sent.get("alpha", 0),
        "win":    round(sent["win"] * 100),
        "sig":    sig,
        "biais":  sent.get("biais", "NEUTRE"),
        "conv":   conv,
        "bonus":  bonus_log,
        "poids":  {"f": round(w["fondamental"]*100), "n": round(w["comportemental"]*100), "t": round(w["technique"]*100)},
        "warn":   warn,
        "warnMsg": warn_msg,
    }

# ─────────────────────────────────────────────────────────────────────────────
# PIPELINE PRINCIPAL
# ─────────────────────────────────────────────────────────────────────────────

def run(dry_run=False, push=False, token=""):
    # IDB_ASOF est réécrit ici quand CDG Capital Bourse fournit une séance
    # plus fraîche qu'IDBourse.
    global IDB_ASOF
    ts_start = time.time()
    logger.info("═" * 60)
    logger.info("BVC ANALYZER — update_data.py v6.3")
    logger.info("═" * 60)

    # 0. Chargement BPA (PE dynamique)
    bpa_path = Path(__file__).parent / "bpa.json"
    BPA_DATA = json.loads(bpa_path.read_text(encoding="utf-8")) if bpa_path.exists() else {}
    logger.info(f"BPA chargé : {len(BPA_DATA)} tickers")
    now_ca = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(hours=1)  # UTC+1 Casablanca
    h, mn = now_ca.hour, now_ca.minute
    tot = h * 60 + mn
    day = now_ca.weekday()  # 0=lun, 5=sam, 6=dim
    # Un férié à date fixe ferme la Bourse aussi sûrement qu'un dimanche. Sans
    # ce test, le statut annonçait OPEN de 9h30 à 15h30 les 20 et 21/08, deux
    # jours fériés : l'en-tête du terminal affichait un marché ouvert, et le
    # disjoncteur « marché fermé + source en panne » ne protégeait pas.
    if day >= 5 or est_ferie_fixe(now_ca.strftime("%Y-%m-%d")):
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
    # ── Repli CDG Capital Bourse, quand IDBourse a une séance de retard ──
    # Le 27/08, IDBourse servait encore les cours du 26 alors que la Bourse
    # cotait : 63 titres échangés, 73 M MAD de volume. Le repli déclaré,
    # Médias24, répond HTTP 403 derrière Cloudflare — la chaîne n'avait donc
    # plus qu'un seul maillon vivant, et la séance était perdue.
    #
    # On ne remplace pas IDBourse : on la complète quand elle est en retard.
    # Le juge est la date, pas la préférence — si CDG n'est pas plus fraîche,
    # rien ne bouge.
    cdg = fetch_all_cdg()
    if cdg:
        cdg_asof = max(v["asof"] for v in cdg.values())
        if not IDB_ASOF or cdg_asof > IDB_ASOF:
            logger.warning(f"IDBourse en retard (séance {IDB_ASOF or 'inconnue'}) — "
                           f"CDG Capital Bourse fournit le {cdg_asof} : "
                           f"{len(cdg)} titres repris")
            for sym, v in cdg.items():
                live_prices[sym] = {**v, "src": "cdg"}
            IDB_ASOF = cdg_asof
        else:
            logger.info(f"CDG Capital Bourse au {cdg_asof} — pas plus fraîche "
                        f"qu'IDBourse ({IDB_ASOF}), ignorée")

    seance_fictive = _recaler_seance_fantome(live_prices)
    if seance_fictive:
        # La Bourse n'a pas coté : ni le calendrier des fériés à date fixe ni
        # l'horaire ne le savaient — le Mawlid suit le calendrier lunaire et
        # n'est confirmé par décret que quelques jours avant. C'est la donnée
        # du marché qui l'établit, et elle doit primer sur les deux.
        if mkt_status != "CLOSED":
            logger.warning(f"Statut marché corrigé : {mkt_status} → CLOSED "
                           f"(aucune cotation le {seance_fictive})")
            mkt_status = "CLOSED"
        # Le MASI est récupéré AVANT la cotation des titres, donc avant que le
        # détecteur ait pu s'exprimer : il portait encore la date annoncée par
        # la source. Relevé le 25/08 — l'indice valait la clôture du 24 et
        # s'affichait « à jour au 25 », non périmé.
        if masi.get("asof") == seance_fictive:
            logger.warning(f"MASI : la source le date du {seance_fictive}, jour "
                           f"sans cotation — ramené à la séance du {IDB_ASOF}")
            masi["asof"], masi["stale"] = IDB_ASOF, True

    # Circuit breaker : ne pas écraser data.json avec des zéros si toutes les sources sont down
    idb_ok = len(live_prices) > 0
    if not idb_ok and mkt_status == "CLOSED" and not dry_run:
        logger.info("Circuit breaker : marché fermé + IDBourse down — data.json inchangé")
        return None


    # Contexte marché global
    mkt_ctx_base = {
        "market_status":    mkt_status,
        "has_results":      False,
        "masi_ytd":         masi["chg"],
    }

    # Pré-chargement des candles OHLCV (pipeline/candles/*.json) pour OBV / ADX
    _candles_cache: dict = {}
    try:
        _candles_dir = Path(__file__).parent / "pipeline" / "candles"
        if _candles_dir.exists():
            for _jf in _candles_dir.glob("*.json"):
                _sym = _jf.stem.upper()
                _raw = json.loads(_jf.read_text(encoding="utf-8"))
                if isinstance(_raw, list) and len(_raw) >= 20:
                    _candles_cache[_sym] = pd.DataFrame(_raw)
        if _candles_cache:
            logger.info(f"  Candles OHLCV chargées : {len(_candles_cache)} tickers")
    except Exception as _e:
        logger.warning(f"  Candles cache : {_e}")

    # Pré-chargement des fichiers JSON statiques (une seule lecture pour tous les tickers)
    _hd_all  = {}
    _fd_all  = {}
    _sf_all  = {}
    _ex_all  = {}
    _ex_raw  = {}
    try:
        _p = Path(__file__).parent / "pipeline" / "historical_data.json"
        if _p.exists():
            _hd_all = json.loads(_p.read_text(encoding="utf-8"))
            logger.info(f"  historical_data.json préchargé : {len(_hd_all)} tickers")
    except Exception as _e:
        logger.warning(f"  historical_data.json : {_e}")
    try:
        _p = Path(__file__).parent / "financial_data.json"
        if _p.exists():
            _fd_all = json.loads(_p.read_text(encoding="utf-8")).get("data", {})
    except Exception:
        pass
    try:
        _p = Path(__file__).parent / "pipeline" / "static_fallback.json"
        if _p.exists():
            _sf_all = json.loads(_p.read_text(encoding="utf-8"))
    except Exception:
        pass
    try:
        if OUTPUT.exists():
            _ex_raw = json.loads(OUTPUT.read_text(encoding="utf-8"))
            _ex_all = {t["symbol"]: t for t in _ex_raw.get("tickers", []) if "symbol" in t}
    except Exception:
        pass

    # Déterminer si on est sur une nouvelle session (date changée depuis dernier data.json)
    _tz_ca = timezone(timedelta(hours=1))
    _today_str = datetime.now(_tz_ca).strftime("%Y-%m-%d")
    _prev_date_str = ""
    try:
        _prev_upd = _ex_raw.get("updated", "") if _ex_raw else ""
        if _prev_upd:
            _prev_date_str = datetime.fromisoformat(_prev_upd).astimezone(_tz_ca).strftime("%Y-%m-%d")
    except Exception:
        pass
    _new_session = _today_str != _prev_date_str
    if _new_session:
        logger.info(f"Nouvelle session détectée ({_prev_date_str} → {_today_str}) — recalcul chg depuis clôtures")

    # 4. Traitement par ticker
    tickers_out = []
    for ticker in TICKERS:
        fd = FOND_DATA.get(ticker, {})
        lp = live_prices.get(ticker, {})

        # Prix — on trace d'où il vient et de quelle séance, pour le bloc
        # _meta émis plus bas : sans ça le frontend ne peut pas distinguer un
        # cours du jour d'une valeur figée dans un fichier statique.
        lp_asof   = lp.get("asof") or ""
        lp_perime = bool(IDB_ASOF and lp_asof and lp_asof < IDB_ASOF)
        price = 0 if lp_perime else (lp.get("price") or 0)
        chg   = 0.0 if lp_perime else lp.get("chg", 0)
        opn   = None if lp_perime else lp.get("open")
        src_prix  = (lp.get("src") or "idbourse") if price else ""
        prix_asof = (lp_asof or IDB_ASOF) if price else ""

        # Correction données IDBourse : toujours recalculer vs vraie clôture j-1 (candle)
        # IDBourse peut référencer une mauvaise date de référence, surtout sur 2e run intraday
        if price:
            _df_c = _candles_cache.get(ticker)
            if _df_c is not None and len(_df_c) >= 1:
                try:
                    last_close = _cloture_precedente(_df_c, IDB_ASOF) or 0
                    if last_close > 0:
                        if abs(price - last_close) < 0.01:
                            chg = 0.0
                        else:
                            chg = round((price - last_close) / last_close * 100, 2)
                except Exception:
                    pass

        # Détection données stales IDBourse : prix = cours de référence J-1
        # Se produit pour les titres peu liquides ou en début de séance
        _idb_vol = lp.get("vol", 0)
        if price > 0 and chg == 0 and _idb_vol == 0:
            logger.warning(f"  {ticker}: IDBourse suspect — chg=0%, vol=0 → vérification Médias24")

        # Safety cap : BVC limite réglementaire stricte ±10%/j
        # Toute variation > 10% est une erreur source (mauvais cours de référence IDBourse)
        if abs(chg) > 10:
            chg = 0.0  # sera recalculé par Médias24 puis recalcul final depuis candles

        # Historique Médias24 pour indicateurs techniques
        df = pd.DataFrame()
        if price > 0:
            logger.info(f"  {ticker}: {price} DH ({chg:+.2f}%) — historique...")
            df = fetch_history(ticker, days=95)
            time.sleep(0.3)  # éviter rate limiting Médias24
        else:
            logger.warning(f"  {ticker}: prix non disponible — données statiques")

        # Indicateurs techniques
        vol = lp.get("vol", 0)  # volume du jour depuis IDBourse
        macd_val = macd_sig = macd_hist = None
        bb_upper = bb_mid = bb_lower = None
        stoch_k = stoch_d = None
        ma200 = h52w = l52w = None
        obv_val = None
        adx_val = pdi_val = mdi_val = None

        # OBV + ADX depuis les candles OHLCV longues (pipeline/candles/)
        _df_c = _candles_cache.get(ticker)
        if _df_c is not None and len(_df_c) >= 20:
            try:
                _cc = pd.to_numeric(_df_c["c"], errors="coerce").dropna()
                _hh = pd.to_numeric(_df_c["h"], errors="coerce").dropna()
                _ll = pd.to_numeric(_df_c["l"], errors="coerce").dropna()
                _vv = pd.to_numeric(_df_c["v"], errors="coerce").fillna(0)
                if len(_cc) >= 20:
                    obv_val = calc_obv(_cc, _vv)
                if len(_cc) >= 30:
                    adx_val, pdi_val, mdi_val = calc_adx(_hh, _ll, _cc)
            except Exception:
                pass

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
                src_prix, prix_asof = "medias24_hist", str(df["date"].iloc[-1])[:10]
            # Variation = prix live vs dernière clôture historique
            if not chg and price and len(closes) >= 1:
                prev = float(closes.iloc[-1])
                if prev > 0:
                    chg = round((price - prev) / prev * 100, 2)
            if not opn and len(df) >= 1:
                opn = round(float(df["open"].iloc[-1]), 2)
            # Volume de la dernière séance Médias24 si IDBourse n'en a pas
            if not vol and "vol" in df.columns:
                vol = int(df["vol"].iloc[-1])
            # Indicateurs avancés (besoin d'historique suffisant)
            if len(closes) >= 35:
                macd_val, macd_sig, macd_hist = calc_macd(closes)
            if len(closes) >= 20:
                bb_upper, bb_mid, bb_lower = calc_bollinger(closes)
            if len(closes) >= 14:
                stoch_k, stoch_d = calc_stoch(closes, highs, lows)
            # MA200 / H52w / L52w depuis le cache préchargé
            hd_t  = _hd_all.get(ticker, {})
            ma200 = hd_t.get("ma200")
            h52w  = hd_t.get("h52w")
            l52w  = hd_t.get("l52w")
        else:
            # Repli prix : dernière clôture des chandelles, avant tout le reste.
            # pipeline/candles/*.json est le fichier OHLCV tenu à jour à chaque
            # run ; historical_data.json n'en est qu'un instantané dérivé,
            # régénéré bien moins souvent, dont last_close peut donc être en
            # retard de plusieurs séances. Holcim y restait à 1736 alors que la
            # clôture du 07/08 valait 1800.
            if not price:
                _df_p = _candles_cache.get(ticker)
                if _df_p is not None and "c" in _df_p and len(_df_p):
                    try:
                        _s = pd.to_numeric(_df_p["c"], errors="coerce").dropna()
                        if len(_s) and float(_s.iloc[-1]) > 0:
                            price = round(float(_s.iloc[-1]), 2)
                            src_prix = "candles"
                            _d_col = _df_p["d"] if "d" in _df_p else None
                            prix_asof = str(_d_col.iloc[-1])[:10] if _d_col is not None else IDB_ASOF
                            logger.info(f"  {ticker}: prix depuis les chandelles ({price} DH)")
                    except Exception:
                        pass

            # Une cotation réelle, même d'une séance antérieure, prime sur
            # toute valeur dérivée : historical_data.json et le data.json du
            # run précédent sont des copies sans date propre, qui se
            # reconduisent d'un run à l'autre. Diac Salaf n'a pas coté depuis
            # le 05/08 — mieux vaut ce cours daté, marqué `stale`.
            if not price and lp_perime and lp.get("price"):
                price = lp["price"]
                src_prix, prix_asof = "idbourse_perime", lp_asof
                logger.info(f"  {ticker}: dernière cotation connue {price} DH "
                            f"(séance {lp_asof})")

            # Fallback A : historical_data.json (cache préchargé)
            _hist_loaded = False
            hd_t = _hd_all.get(ticker, {})
            if hd_t.get("rsi") and hd_t.get("ma20"):
                rsi       = hd_t["rsi"]
                ma20      = hd_t["ma20"]
                ma50      = hd_t.get("ma50", ma20)
                h90       = hd_t.get("h90",  price * 1.15 if price else 0)
                l90       = hd_t.get("l90",  price * 0.85 if price else 0)
                macd_val  = hd_t.get("macd")
                macd_sig  = hd_t.get("macd_signal")
                macd_hist = hd_t.get("macd_hist")
                bb_upper  = hd_t.get("bb_upper")
                bb_mid    = hd_t.get("bb_mid")
                bb_lower  = hd_t.get("bb_lower")
                stoch_k   = hd_t.get("stoch_k")
                stoch_d   = hd_t.get("stoch_d")
                ma200     = hd_t.get("ma200")
                h52w      = hd_t.get("h52w")
                l52w      = hd_t.get("l52w")
                if not price:
                    price = hd_t.get("last_close", 0)
                    if price:
                        src_prix  = "historical"
                        prix_asof = str(hd_t.get("last_date") or "")[:10]
                _hist_loaded = True
                logger.info(f"  {ticker}: indicateurs depuis historical_data.json "
                            f"(BVCscrap, {hd_t.get('n_candles',0)} bougies)")

            if not _hist_loaded:
                # Fallback B : indicateurs depuis data.json (cache préchargé)
                ex_t = _ex_all.get(ticker, {})
                if ex_t:
                    rsi  = ex_t.get("rsi", 50)
                    ma20 = ex_t.get("ma20", price or 0)
                    ma50 = ex_t.get("ma50", price or 0)
                    h90  = ex_t.get("h90",  price * 1.15 if price else 0)
                    l90  = ex_t.get("l90",  price * 0.85 if price else 0)
                    macd_val  = ex_t.get("macd")
                    macd_sig  = ex_t.get("macd_signal")
                    macd_hist = ex_t.get("macd_hist")
                    bb_upper  = ex_t.get("bb_upper")
                    bb_mid    = ex_t.get("bb_mid")
                    bb_lower  = ex_t.get("bb_lower")
                    stoch_k   = ex_t.get("stoch_k")
                    stoch_d   = ex_t.get("stoch_d")
                    if not price:
                        price = ex_t.get("price", 0)
                        if price:
                            src_prix, prix_asof = "data_json_precedent", ""
                    if not vol:
                        vol = ex_t.get("vol", 0)
                else:
                    rsi, ma20, ma50 = 50, price or 0, price or 0
                    h90 = price * 1.15 if price else 0
                    l90 = price * 0.85 if price else 0

        # Fallback 3 : financial_data.json (cache préchargé)
        if not price:
            fd_t = _fd_all.get(ticker, {})
            fd_p = fd_t.get("market", {}).get("price") or 0
            if fd_p:
                price = fd_p
                tech  = fd_t.get("technical", {})
                if not ma20: ma20 = tech.get("ma20") or price
                if not ma50: ma50 = tech.get("ma50") or price
                if rsi == 50: rsi = tech.get("rsi_14") or 50
                if not h90:  h90  = tech.get("high_90d") or round(price * 1.15, 2)
                if not l90:  l90  = tech.get("low_90d")  or round(price * 0.85, 2)
                src_prix, prix_asof = "financial", ""
                logger.info(f"  {ticker}: prix depuis financial_data.json ({price} DH)")

        # Fallback 4 : static_fallback.json (cache préchargé)
        if not price:
            sf_t = _sf_all.get(ticker, {})
            sf_p = sf_t.get("price") or 0
            if sf_p:
                price = sf_p
                if not ma20: ma20 = sf_t.get("ma20") or price
                if not ma50: ma50 = sf_t.get("ma50") or price
                if rsi == 50: rsi = sf_t.get("rsi_14") or 50
                if not h90:  h90  = sf_t.get("high_90d") or round(price * 1.15, 2)
                if not l90:  l90  = sf_t.get("low_90d")  or round(price * 0.85, 2)
                src_prix, prix_asof = "static", ""
                logger.info(f"  {ticker}: prix depuis static_fallback.json ({price} DH) — données statiques")

        # Médias24 getStockInfo — source primaire pour prix et variation
        # IDBourse retourne parfois la session précédente pour les titres peu échangés
        # → Médias24 garantit des données fraîches de la session en cours
        q = fetch_med24_quote(ticker)
        if q:
            price = q["price"]          # Médias24 prioritaire
            chg   = q["chg"]
            src_prix, prix_asof = "medias24", IDB_ASOF
            if not opn: opn = q.get("open")
            if not vol: vol = q.get("vol") or lp.get("vol", 0)
            logger.info(f"  {ticker}: Médias24 → {price} DH (chg={chg:+.2f}%, vol={vol})")
            time.sleep(0.2)
        elif not price:
            logger.warning(f"  {ticker}: Médias24 et IDBourse indisponibles — données statiques")

        if not price:
            logger.warning(f"  {ticker}: ignoré (aucune donnée)")
            continue

        # ── Recalcul final chg depuis candles ─────────────────────────────────
        # IDBourse ET Médias24 peuvent retourner variation=0 alors que le prix a bougé
        # (IDBourse retourne parfois le cours de référence J-1 comme cours actuel).
        # On recalcule toujours la variation depuis la dernière clôture connue (candles).
        # Si le résultat dépasse ±10% → anomalie de données → on garde 0 et on alerte.
        _df_c_final = _candles_cache.get(ticker)
        if _df_c_final is not None and len(_df_c_final) >= 1 and price > 0:
            try:
                _last_c = _cloture_precedente(_df_c_final, IDB_ASOF) or 0
                if _last_c > 0 and abs(price - _last_c) > 0.01:
                    _chg_calc = round((price - _last_c) / _last_c * 100, 2)
                    if abs(_chg_calc) <= 10.0:
                        if _chg_calc != chg:
                            logger.info(
                                f"  {ticker}: chg corrigé {chg:+.2f}% → {_chg_calc:+.2f}%"
                                f" (prix={price}, clôture_j-1={_last_c})"
                            )
                        chg = _chg_calc
                    else:
                        logger.warning(
                            f"  {ticker}: variation calculée {_chg_calc:+.2f}% > ±10%"
                            f" — cours de référence IDBourse suspect (prix={price}, ref={_last_c})"
                        )
                        chg = 0.0
            except Exception:
                pass

        if not opn:
            opn = round(price / (1 + chg / 100), 2) if chg else price

        # Sanity check ISIN : si MA20 diffère du prix de plus de 3x → ISIN probablement erroné
        # (ex: SOT — IDBourse retourne ~369 DH mais Médias24 ISIN donne ~1666 MA20 = mauvais ISIN)
        if price > 0 and ma20 > 0 and (ma20 > 3.0 * price or price > 3.0 * ma20):
            logger.warning(
                f"  {ticker}: ANOMALIE ISIN — MA20={ma20} vs prix={price} "
                f"(ratio {max(ma20,price)/min(ma20,price):.1f}x) — indicateurs resetés à neutres"
            )
            rsi  = 50.0
            ma20 = round(price, 2)
            ma50 = round(price, 2)
            h90  = round(price * 1.15, 2)
            l90  = round(price * 0.85, 2)

        # Score technique
        score_tech = calc_score_tech(rsi, price, ma20, ma50, h90, l90)
        # Score fondamental : fondamentaux.json en priorité, table statique en fallback
        score_fond = _FOND_COMPUTED.get(ticker) or FOND_SCORES.get(ticker, 5.0)
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
                          fd.get("flags", 0), fd.get("upside") or 0, ctx)

        # Setup technique (déduit du score et des MAs)
        v53_final = v53["v53"]
        if v53_final >= 7.0 and price > ma20 > ma50:
            setup = "MOMENTUM CONFIRME"
        elif v53_final >= 5.5 and price < ma20 and price >= ma50:
            setup = "PULLBACK HAUSSIER"
        elif v53_final >= 5.0 and price < ma50:
            setup = "CONTRARIEN"
        elif v53_final < 4.5:
            setup = "FAIBLESSE"
        else:
            setup = "NEUTRE"

        info = TICKER_INFO.get(ticker, {})
        tickers_out.append({
            "symbol": ticker,
            # ── Bloc _meta (spécification CLAUDE.md) ─────────────────────────
            # Sans lui, rien ne distingue à l'écran un cours coté ce jour d'une
            # valeur figée depuis des semaines dans static_fallback.json. Le
            # frontend doit supposer stale=true en son absence.
            "_meta": _meta_ticker(ticker, src_prix, prix_asof, sent,
                                  _candles_cache.get(ticker)),
            # Code officiel BVC, pour l'affichage seulement. Nos symboles
            # internes sont la clé primaire d'ISIN_MAP, des chandelles et de
            # six ans de corpus WhatsApp : on ne les renomme pas. Mais un
            # investisseur marocain lit « SNA » comme Stokvis, pas comme
            # Sonasid — afficher notre code à l'écran désoriente face à
            # n'importe quelle autre source.
            "code_bvc": IDB_TICKER_MAP.get(ticker, ticker),
            # Fondamentaux PRÉVISIONNELS (IDBourse DATA+), dans leur propre
            # espace de noms. Ils ne se mélangent pas à `pe`/`pb`/`div`, qui
            # sont du réalisé, et n'entrent pas dans le score v5.3 : modifier
            # la pondération exigerait un backtest (R8). Ils enrichissent la
            # fiche, ils ne la notent pas.
            "fwd": DATAPLUS.get(ticker) or None,
            "name":   info.get("name", ticker),
            "sector": info.get("sector", ""),
            "price":  round(price, 2),
            "chg":    round(chg, 2),
            "vol":    int(vol) if vol else 0,
            "open":   round(opn, 2),
            "close":  round(price, 2),
            "pe":     round(price / BPA_DATA[ticker]["bpa"], 1) if (ticker in BPA_DATA and BPA_DATA[ticker].get("bpa") and price > 0) else fd.get("pe"),
            "bpa":    BPA_DATA[ticker]["bpa"] if ticker in BPA_DATA else None,
            "pb":     fd.get("pb"),
            "div":    round(BPA_DATA[ticker]["div_dh"] / price * 100, 2) if (ticker in BPA_DATA and BPA_DATA[ticker].get("div_dh") and price > 0) else fd.get("div"),
            "div_dh": BPA_DATA[ticker].get("div_dh") if ticker in BPA_DATA else None,
            # Capitalisation : celle d'IDBourse, calculée sur le cours du jour,
            # prime sur FOND_DATA — table codée en dur qui n'a suivi ni les
            # splits ni les corrections d'ISIN (Sonasid y valait 1 100 MDHS
            # pour une capitalisation réelle de 7 800).
            "cap":    lp.get("cap") or fd.get("cap"),
            "h90":    round(h90, 2),
            "l90":    round(l90, 2),
            "ma200":  round(ma200, 2) if ma200 else None,
            "h52w":   round(h52w, 2) if h52w else None,
            "l52w":   round(l52w, 2) if l52w else None,
            "rsi":    rsi,
            "ma20":   ma20,
            "ma50":   ma50,
            # Indicateurs avancés
            "macd":        macd_val,
            "macd_signal": macd_sig,
            "macd_hist":   macd_hist,
            "bb_upper":    bb_upper,
            "bb_mid":      bb_mid,
            "bb_lower":    bb_lower,
            "stoch_k":     stoch_k,
            "stoch_d":     stoch_d,
            "obv":         obv_val,
            "adx":         adx_val,
            "adx_pdi":     pdi_val,
            "adx_mdi":     mdi_val,
            # Scores v5.3 (INVIOLABLE — ne pas modifier la logique)
            "bvc":        v53["bvc"],
            "v53":        v53["v53"],
            "delta":      v53["delta"],
            "nlp":        v53["nlp"],
            "score_tech": v53.get("score_tech", 5.0),
            "alpha":  v53["alpha"],
            "win":    v53["win"],
            "sig":    v53["sig"],
            "sigBvc": SIG_BVC.get(ticker, "ATTENDRE"),
            "biais":  v53["biais"],
            "conv":   v53["conv"],
            "setup":  setup,
            "bonus":  v53["bonus"],
            "poids":  v53["poids"],
            "warn":   v53["warn"],
            "warnMsg":v53["warnMsg"],
            # Alerte variation extrême (≥ ±8% approche limite BVC ±10%)
            "chg_alert": abs(round(chg, 2)) >= 8.0,
            # Fondamentaux
            **_objectifs(ticker, price, fd),
            "flags":  fd.get("flags", 0),
        })

        logger.info(f"  ✓ {ticker}: {price} DH | RSI {rsi} | Score v5.3: {bvc_score} → {v53['v53']} | {v53['sig']}")

    # 5. Construction data.json
    output = {
        # ⚠️ L'offset +01:00 était écrit en dur sur un `datetime.now()` naïf.
        # Les runners GitHub sont en UTC : l'heure produite était donc celle
        # d'UTC, étiquetée Casablanca — soit une heure de retard affichée en
        # permanence dans l'en-tête du terminal. Le message de commit, lui,
        # utilise `TZ=Africa/Casablanca date` et donnait l'heure juste : d'où
        # un data.json marqué 11h31 dans un commit intitulé 12h31.
        "updated": datetime.now(timezone(timedelta(hours=1))).strftime("%Y-%m-%dT%H:%M:%S%z"),
        "source":  "IDBourse / Médias24",
        "market_status": mkt_status,
        "masi": {
            "value":      masi["value"],
            "change_pct": masi["chg"],
            "asof":       masi.get("asof"),
            "stale":      masi.get("stale", True),
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

    # 6b. Snapshot post-clôture — sauvegarde les vrais cours de fermeture
    # Permet de recalculer la variation J+1 même si IDBourse retourne des prix stales
    try:
        snap_path = Path(__file__).parent / "snapshot_cloture.json"
        today_str = datetime.now().strftime("%Y-%m-%d")
        snap_closes = {e["symbol"]: e["price"] for e in tickers_out if e.get("price", 0) > 0}
        snap_data = {"date": today_str, "closes": snap_closes, "generated": datetime.now().isoformat()}
        # Charger snapshot existant pour garder historique J-1
        if snap_path.exists():
            prev = json.loads(snap_path.read_text(encoding="utf-8"))
            snap_data["prev"] = {"date": prev.get("date"), "closes": prev.get("closes", {})}
        snap_path.write_text(json.dumps(snap_data, ensure_ascii=False, indent=2), encoding="utf-8")
        logger.info(f"  📸 snapshot_cloture.json sauvegardé ({len(snap_closes)} tickers)")
    except Exception as _e:
        logger.warning(f"  snapshot_cloture : {_e}")

    # 6c. Bougie de la séance cotée (pour que le graphique affiche le jour même)
    try:
        # La date à écrire est celle de la SÉANCE, donnée par la source, pas
        # celle du run. Les deux diffèrent dès qu'on tourne hors séance : un run
        # lancé lundi 00h16 reçoit les cours de la clôture de vendredi et les
        # écrivait comme une séance du lundi — 73 bougies fantômes dupliquant
        # vendredi, avant même l'ouverture (9h30). Le week-end, même effet.
        # Se fier à updated_at ne suffit pas quand la source elle-même date un
        # jour fermé : le 14/08 (férié) elle a estampillé du 14 les cours du 13,
        # et 71 bougies ont dupliqué le 13. C'est _recaler_seance_fantome() qui
        # ramène alors IDB_ASOF à la séance réelle, en amont — ce test devient
        # « la séance cotée n'est pas aujourd'hui » et refuse d'écrire.
        candles_dir = Path(__file__).parent / "pipeline" / "candles"
        today_str = IDB_ASOF
        if not today_str:
            logger.info("  Candles J : date de séance inconnue (IDBourse muet) — ignoré")
        elif today_str != datetime.now().strftime("%Y-%m-%d"):
            logger.info(f"  Candles J : dernière séance cotée = {today_str}, "
                        f"pas aujourd'hui — aucune bougie ajoutée")
        elif candles_dir.exists():
            updated_count = 0
            for entry in tickers_out:
                sym  = entry["symbol"]
                cfp  = candles_dir / f"{sym}.json"
                if not cfp.exists():
                    continue
                c_price = entry.get("price", 0)
                if c_price <= 0:
                    continue
                # N'écrire une bougie que si le prix vient bien d'une cotation
                # de la séance. Sans cette garde, un titre non rafraîchi par la
                # source se confirmait lui-même : le prix retombait sur la
                # dernière chandelle, qu'on réécrivait ensuite à la date du
                # jour — Holcim se voyait ainsi attribuer une clôture au 10/08
                # alors qu'IDBourse ne l'avait plus cotée depuis le 05/08.
                _m = entry.get("_meta") or {}
                # `cdg` est une cotation réelle et datée, au même titre
                # qu'IDBourse ou Médias24 — elle a même l'avantage de porter
                # un chandelier complet. L'omettre de cette liste revenait à
                # refuser d'écrire la moindre bougie les jours où elle est la
                # seule source fraîche, ce qui est précisément son rôle.
                if _m.get("stale") or _m.get("source_prix") not in ("idbourse", "medias24", "cdg"):
                    continue
                try:
                    existing = json.loads(cfp.read_text(encoding="utf-8"))
                    # La bougie du jour se RAFRAÎCHIT à chaque run, elle ne se
                    # fige pas au premier. L'ancien code passait son tour dès
                    # qu'un point du jour existait : le premier run de la
                    # journée — souvent en pleine séance — gravait un cours de
                    # milieu de séance comme clôture définitive. Relevé du
                    # 10/08 : la bougie disait IAM 100,70 et Managem 1 660,
                    # là où la clôture réelle valait 99,85 et 1 624.
                    c_price = round(float(c_price), 2)
                    veille = existing[-1] if existing else None
                    jour = veille if veille and veille.get("d") == today_str else None
                    if jour:
                        # l'ouverture reste celle du premier point ; les
                        # extrêmes s'étendent, la clôture suit le dernier cours
                        today_candle = {
                            "d": today_str,
                            "o": jour.get("o", c_price),
                            "h": round(max(jour.get("h", c_price), c_price), 2),
                            "l": round(min(jour.get("l", c_price), c_price), 2),
                            "c": c_price,
                            "v": max(int(entry.get("vol") or 0), int(jour.get("v") or 0)),
                        }
                        existing[-1] = today_candle
                    else:
                        prev_close = veille["c"] if veille else c_price
                        today_candle = {
                            "d": today_str,
                            "o": round(float(entry.get("open") or prev_close), 2),
                            "h": c_price, "l": c_price, "c": c_price,
                            "v": int(entry.get("vol") or 0),
                        }
                        existing.append(today_candle)
                    cfp.write_text(json.dumps(existing, separators=(",", ":")), encoding="utf-8")
                    updated_count += 1
                except Exception:
                    pass
            if updated_count:
                logger.info(f"  Candles J mis à jour : {updated_count} tickers → {today_str}")
        # Filet : les chandelles sont aussi écrites par generate_candles.py et
        # collect_history_bvcscrap.py, qui tiennent leur date de leurs propres
        # sources. Le recalage ci-dessus ne protège que ce run — ce balayage
        # rattrape ce qu'un autre a pu déposer.
        sys.path.insert(0, str(Path(__file__).parent / "pipeline"))
        from seance import purger_seance_fantome
        _dj, _nj = purger_seance_fantome()
        if _dj:
            logger.warning(f"  Séance fantôme {_dj} purgée : {_nj} bougies retirées")
    except Exception as _e:
        logger.warning(f"  Candles J update : {_e}")

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
