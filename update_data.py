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

import sys, os, json, time, argparse, logging, subprocess
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

from bvc_config import ISIN_MAP, IDB_NAME_MAP, TICKERS_ALL

TICKERS = TICKERS_ALL

# ─────────────────────────────────────────────────────────────────────────────
# MÉTADONNÉES TICKERS (nom complet + secteur)
# ─────────────────────────────────────────────────────────────────────────────

TICKER_INFO = {
    # ── Tickers actifs (19) ───────────────────────────────────────────
    "CMT":  {"name": "Ciments du Maroc",       "sector": "Matériaux"},
    "SMI":  {"name": "S.M. Imiter",             "sector": "Matériaux"},
    "CASH": {"name": "CIH Bank",                "sector": "Finance"},
    "MNG":  {"name": "Managem",                 "sector": "Mines"},
    "AKD":  {"name": "Akdital",                 "sector": "Santé"},
    "SOT":  {"name": "Sothema",                 "sector": "Santé"},
    "SGTM": {"name": "SGTM",                    "sector": "Construction"},
    "MSA":  {"name": "Mutandis",                "sector": "Agro"},
    "CFGB": {"name": "CFG Bank",                "sector": "Finance"},
    "RIS":  {"name": "Résidences Immo.",        "sector": "Immo"},
    "ADI":  {"name": "Alliances Dév.",          "sector": "Immo"},
    "VCNE": {"name": "Vivo Energy",             "sector": "Distribution"},
    "CMGP": {"name": "CMGP Group",              "sector": "Distribution"},
    "CSR":  {"name": "Ciments de l'Atlas",      "sector": "Industrie"},
    "TGCC": {"name": "TGCC",                    "sector": "Construction"},
    "ADH":  {"name": "Addoha",                  "sector": "Distribution"},
    "SRM":  {"name": "Stokvis",                 "sector": "Industrie"},
    "SNA":  {"name": "Sonasid",                 "sector": "Industrie"},
    "RDS":  {"name": "RDSA Maroc",              "sector": "Industrie"},
    # ── Grandes capitalisations ───────────────────────────────────────
    "IAM":  {"name": "Maroc Telecom",           "sector": "Telecom"},
    "ATW":  {"name": "Attijariwafa Bank",        "sector": "Finance"},
    "BCP":  {"name": "Banque Populaire",         "sector": "Finance"},
    "BOA":  {"name": "Bank of Africa",           "sector": "Finance"},
    "CIH":  {"name": "CIH Bank",                 "sector": "Finance"},
    "CDM":  {"name": "Crédit du Maroc",          "sector": "Finance"},
    "WAF":  {"name": "Wafa Assurance",           "sector": "Assurances"},
    "LHM":  {"name": "LafargeHolcim Maroc",      "sector": "Matériaux"},
    "GAZ":  {"name": "Afriquia Gaz",             "sector": "Energie"},
    "ATL":  {"name": "Auto Hall",                "sector": "Distribution"},
    "HPS":  {"name": "HPS",                      "sector": "Tech"},
    "LBV":  {"name": "Label'Vie",                "sector": "Distribution"},
    "LES":  {"name": "Lesieur Cristal",          "sector": "Agro"},
    "TQA":  {"name": "Taqa Morocco",             "sector": "Energie"},
    "MRL":  {"name": "Marsa Maroc",              "sector": "Services"},
    "TMA":  {"name": "TotalEnergies Maroc",      "sector": "Energie"},
    # ── Moyennes capitalisations ─────────────────────────────────────
    "ARD":  {"name": "Aradei Capital",           "sector": "Immo"},
    "SAF":  {"name": "Saham Assurance",          "sector": "Assurances"},
    "OUL":  {"name": "Oulmès",                   "sector": "Agro"},
    "CIM":  {"name": "Cimat",                    "sector": "Matériaux"},
    "CTM":  {"name": "CTM",                      "sector": "Transport"},
    "ZLD":  {"name": "Zellidja",                 "sector": "Mines"},
    "ALU":  {"name": "Aluminium du Maroc",       "sector": "Industrie"},
    "MGL":  {"name": "Maghreb Steel",            "sector": "Industrie"},
    "DAR":  {"name": "Dar Saada",                "sector": "Immo"},
    "IMI":  {"name": "Immorente Invest",         "sector": "Immo"},
    "DTT":  {"name": "Disty Technologies",       "sector": "Tech"},
    # ── Petites capitalisations ──────────────────────────────────────
    "DSW":  {"name": "Disway",                   "sector": "Tech"},
    "MOX":  {"name": "Maghreb Oxygène",          "sector": "Industrie"},
    "STR":  {"name": "Stroc Industrie",          "sector": "Industrie"},
    "TIM":  {"name": "Timar",                    "sector": "Services"},
    "SNP":  {"name": "SNEP",                     "sector": "Industrie"},
    "SLM":  {"name": "Salafin",                  "sector": "Finance"},
    "JET":  {"name": "Jet Contractors",          "sector": "Construction"},
    "M2M":  {"name": "M2M Group",                "sector": "Tech"},
    "INV":  {"name": "Involys",                  "sector": "Tech"},
    "S2M":  {"name": "S2M",                      "sector": "Tech"},
    "COL":  {"name": "Colorado",                 "sector": "Industrie"},
    "AFM":  {"name": "Afma",                     "sector": "Assurances"},
    "AGM":  {"name": "Agma Lahlou-Tazi",         "sector": "Assurances"},
    "FNB":  {"name": "Finance.com",              "sector": "Finance"},
    "BAL":  {"name": "Balima",                   "sector": "Assurances"},
    "NEJ":  {"name": "Nejma",                    "sector": "Distribution"},
    "HAL":  {"name": "Hala",                     "sector": "Agro"},
    "BMC":  {"name": "Brasseries du Maroc",      "sector": "Agro"},
    "CAR":  {"name": "Cartier Saada",            "sector": "Immo"},
    "AFI":  {"name": "Afine",                    "sector": "Immo"},
    "MIC":  {"name": "Microdata",                "sector": "Tech"},
    "MUT":  {"name": "Mutandis SCA",             "sector": "Agro"},
    "ENK":  {"name": "Enkaje",                   "sector": "Services"},
    "EQD":  {"name": "Equity",                   "sector": "Finance"},
    "DHO":  {"name": "Daho",                     "sector": "Holding"},
    "PPM":  {"name": "Papier Industrie",         "sector": "Industrie"},
    "REB":  {"name": "Rebab Company",            "sector": "Immo"},
    "SBS":  {"name": "Super Céréales",           "sector": "Agro"},
    "STK":  {"name": "Stokvis Nord Afrique",     "sector": "Industrie"},
    "UNI":  {"name": "Unimer",                   "sector": "Agro"},
    "IBM":  {"name": "IB Maroc.com",             "sector": "Tech"},
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
# MÉTADONNÉES TICKERS (nom complet + secteur)
# ─────────────────────────────────────────────────────────────────────────────

TICKER_INFO = {
    "CMT":  {"name": "Ciments du Maroc",       "sector": "Matériaux"},
    "SMI":  {"name": "S.M. Imiter",             "sector": "Matériaux"},
    "CASH": {"name": "CIH Bank",                "sector": "Finance"},
    "MNG":  {"name": "Managem",                 "sector": "Mines"},
    "AKD":  {"name": "Akdital",                 "sector": "Santé"},
    "SOT":  {"name": "Sotherma",                "sector": "Agro"},
    "SGTM": {"name": "SGTM",                    "sector": "Construction"},
    "MSA":  {"name": "Mutandis",                "sector": "Agro"},
    "CFGB": {"name": "CFG Bank",                "sector": "Finance"},
    "RIS":  {"name": "Résidences Immo.",        "sector": "Immo"},
    "ADI":  {"name": "Alliances Dév.",          "sector": "Immo"},
    "VCNE": {"name": "Vivo Energy",             "sector": "Distribution"},
    "CMGP": {"name": "CMGP Group",              "sector": "Distribution"},
    "CSR":  {"name": "Ciments de l'Atlas",      "sector": "Industrie"},
    "TGCC": {"name": "TGCC",                    "sector": "Construction"},
    "ADH":  {"name": "Addoha",                  "sector": "Distribution"},
    "SRM":  {"name": "Stokvis",                 "sector": "Industrie"},
    "SNA":  {"name": "Sonasid",                 "sector": "Industrie"},
    "RDS":  {"name": "RDSA Maroc",              "sector": "Industrie"},
}

# Signal communauté BVC (consensus indépendant du score v5.3)
SIG_BVC = {
    "CMT":"ACHETER","SMI":"ACHETER","CASH":"SURVEILLER","MNG":"ACHETER",
    "AKD":"ACHETER","SOT":"ACHETER","SGTM":"SURVEILLER","MSA":"SURVEILLER",
    "CFGB":"ATTENDRE","RIS":"ATTENDRE","ADI":"ATTENDRE","VCNE":"ATTENDRE",
    "CMGP":"ATTENDRE","CSR":"ATTENDRE","TGCC":"ATTENDRE","ADH":"ATTENDRE",
    "SRM":"ATTENDRE","SNA":"EVITER","RDS":"EVITER",
}

# ─────────────────────────────────────────────────────────────────────────────
# DONNÉES FONDAMENTALES STABLES (source: bilans / rapports d'introduction BVC)
# Mise à jour manuelle lors de nouvelles publications de résultats
# ─────────────────────────────────────────────────────────────────────────────

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
    "COL": {"pe":14.5,"pb":2.0,"div":4.0,"cap":1000,  "bear":74,   "base":93,   "bull":116,  "upside":6.0, "flags":0},
    # ── Tickers actifs (19) ──────────────────────────────────────────
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
    # Source: corpus WhatsApp BVC — 882 734 messages · 6 ans · 14 phases NLP
    "CMT": {"smart":0.867,"hype":0.91,"alpha":42.1,"win":0.35,"mentions":4142,  "biais":"ACHAT", "contrarian":False},
    "SMI": {"smart":0.427,"hype":0.91,"alpha":38.5,"win":0.31,"mentions":4279,  "biais":"ACHAT", "contrarian":False},
    "CASH":{"smart":0.067,"hype":0.92,"alpha":10.1,"win":0.29,"mentions":4410,  "biais":"NEUTRE","contrarian":False},
    "MNG": {"smart":0.540,"hype":0.95,"alpha":55.3,"win":0.32,"mentions":6665,  "biais":"ACHAT", "contrarian":False},
    "AKD": {"smart":0.613,"hype":0.87,"alpha":22.8,"win":0.33,"mentions":2888,  "biais":"ACHAT", "contrarian":False},
    "SOT": {"smart":0.200,"hype":0.82,"alpha":5.0, "win":0.30,"mentions":1772,  "biais":"NEUTRE","contrarian":False},
    "SGTM":{"smart":0.360,"hype":0.82,"alpha":15.9,"win":0.31,"mentions":1841,  "biais":"ACHAT", "contrarian":False},
    "MSA": {"smart":-0.060,"hype":0.79,"alpha":21.0,"win":0.28,"mentions":1433, "biais":"NEUTRE","contrarian":False},
    "CFGB":{"smart":0.120,"hype":0.19,"alpha":4.0, "win":0.72,"mentions":900,   "biais":"ACHAT", "contrarian":False},
    "RIS": {"smart":-0.087,"hype":0.88,"alpha":10.3,"win":0.27,"mentions":3096, "biais":"NEUTRE","contrarian":False},
    "ADI": {"smart":0.040,"hype":0.95,"alpha":8.5, "win":0.28,"mentions":22893, "biais":"NEUTRE","contrarian":False},
    "VCNE":{"smart":0.050,"hype":0.21,"alpha":3.0, "win":0.70,"mentions":600,   "biais":"NEUTRE","contrarian":False},
    "CMGP":{"smart":0.160,"hype":0.78,"alpha":11.5,"win":0.29,"mentions":1251,  "biais":"NEUTRE","contrarian":False},
    "CSR": {"smart":-0.007,"hype":0.58,"alpha":19.2,"win":0.28,"mentions":202,  "biais":"NEUTRE","contrarian":True},
    "TGCC":{"smart":0.420,"hype":0.95,"alpha":18.7,"win":0.31,"mentions":9537,  "biais":"ACHAT", "contrarian":False},
    "ADH": {"smart":-0.267,"hype":0.95,"alpha":3.1, "win":0.26,"mentions":18290,"biais":"NEUTRE","contrarian":False},
    "SRM": {"smart":0.253,"hype":0.74,"alpha":9.8, "win":0.30,"mentions":853,   "biais":"NEUTRE","contrarian":False},
    "SNA": {"smart":-0.280,"hype":0.86,"alpha":7.6, "win":0.26,"mentions":2669, "biais":"NEUTRE","contrarian":False},
    "RDS": {"smart":-0.340,"hype":0.95,"alpha":5.2, "win":0.26,"mentions":14692,"biais":"NEUTRE","contrarian":False},
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

def fetch_all_idb():
    """Toutes les cotations IDBourse en un seul appel.

    Champs IDBourse confirmés :
      dernier_cours  — prix (float)
      variation      — % variation (float, 53/86 non-nuls en séance)
      volume_en_titres — nb titres échangés (string "3 726", espaces à supprimer)
      volume         — montant en DH (NE PAS utiliser pour le nb de titres)
      ouverture      — prix d'ouverture (string "181,10", virgule décimale)
      url            — contient le code BVC : .../instruments/CSR → extrait "CSR"
    """
    data = idb_get("/api/proxy/get_all_data")
    if not isinstance(data, list):
        return {}
    out = {}
    for d in data:
        if not d.get("name") or not d.get("dernier_cours"):
            continue
        # Extraire le code BVC depuis l'URL (.../instruments/CODE)
        url = d.get("url", "")
        ticker_from_url = url.split("/instruments/")[-1].upper() if "/instruments/" in url else ""
        # Priorité : code URL → mapping nom → nom brut
        if ticker_from_url and ticker_from_url in ISIN_MAP:
            sym = ticker_from_url
        else:
            n = d["name"].upper()
            sym = IDB_NAME_MAP.get(n, n)
            if sym not in ISIN_MAP:
                continue
        try:
            # volume_en_titres = "3 726" (nombre de titres, espaces à supprimer)
            vol_str = str(d.get("volume_en_titres") or "0").replace(" ", "").replace(" ", "").replace(",", "")
            vol_int = int(float(vol_str)) if vol_str and vol_str not in ("0", "") else 0
            # ouverture = "181,10" (virgule décimale française)
            opn_str = str(d.get("ouverture") or "").replace(",", ".")
            opn_val = float(opn_str) if opn_str else None
            out[sym] = {
                "price": float(d["dernier_cours"]),
                "chg":   float(d.get("variation") or 0),
                "open":  opn_val,
                "vol":   vol_int,
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

    conv = "CONFIRME" if (bvc_bull and nlp_bull) else "DIVERGE"

    return {
        "v53":    final,
        "bvc":    round(bvc_score, 2),
        "delta":  round(final - bvc_score, 2),
        "nlp":    round(sent["smart"], 2),
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
    ts_start = time.time()
    logger.info("═" * 60)
    logger.info("BVC ANALYZER — update_data.py v6.3")
    logger.info("═" * 60)

    # 1. Contexte marché
    now_ca = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(hours=1)  # UTC+1 Casablanca
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
        vol = lp.get("vol", 0)  # volume du jour depuis IDBourse
        macd_val = macd_sig = macd_hist = None
        bb_upper = bb_mid = bb_lower = None
        stoch_k = stoch_d = None
        ma200 = h52w = l52w = None

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
        else:
            # Fallback A : historical_data.json (produit par collect_history_bvcscrap.py)
            _hist_loaded = False
            try:
                hd_path = Path(__file__).parent / "pipeline" / "historical_data.json"
                if hd_path.exists():
                    hd_all = json.loads(hd_path.read_text(encoding="utf-8"))
                    hd_t   = hd_all.get(ticker, {})
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
                        _hist_loaded = True
                        logger.info(f"  {ticker}: indicateurs depuis historical_data.json "
                                    f"(BVCscrap, {hd_t.get('n_candles',0)} bougies)")
            except Exception:
                pass

            if not _hist_loaded:
                # Fallback B : indicateurs depuis data.json existant
                try:
                    existing = json.loads(OUTPUT.read_text()) if OUTPUT.exists() else {}
                    ex_t = next((t for t in existing.get("tickers", []) if t["symbol"] == ticker), {})
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
                    if not vol:
                        vol = ex_t.get("vol", 0)
                except Exception:
                    rsi, ma20, ma50 = 50, price or 0, price or 0
                    h90 = price * 1.15 if price else 0
                    l90 = price * 0.85 if price else 0

        # Fallback 3 : financial_data.json (produit par collect_financial_data.py)
        if not price:
            try:
                fd_path = Path(__file__).parent / "financial_data.json"
                if fd_path.exists():
                    fd_all = json.loads(fd_path.read_text(encoding="utf-8"))
                    fd_t   = fd_all.get("data", {}).get(ticker, {})
                    fd_p   = fd_t.get("market", {}).get("price") or 0
                    if fd_p:
                        price = fd_p
                        tech  = fd_t.get("technical", {})
                        if not ma20: ma20 = tech.get("ma20") or price
                        if not ma50: ma50 = tech.get("ma50") or price
                        if rsi == 50: rsi = tech.get("rsi_14") or 50
                        if not h90:  h90  = tech.get("high_90d") or round(price * 1.15, 2)
                        if not l90:  l90  = tech.get("low_90d")  or round(price * 0.85, 2)
                        logger.info(f"  {ticker}: prix depuis financial_data.json ({price} DH)")
            except Exception:
                pass

        # Fallback 4 : static_fallback.json (prix extraits de index.html — dernier recours)
        if not price:
            try:
                sf_path = Path(__file__).parent / "pipeline" / "static_fallback.json"
                if sf_path.exists():
                    sf_all = json.loads(sf_path.read_text(encoding="utf-8"))
                    sf_t   = sf_all.get(ticker, {})
                    sf_p   = sf_t.get("price") or 0
                    if sf_p:
                        price = sf_p
                        if not ma20: ma20 = sf_t.get("ma20") or price
                        if not ma50: ma50 = sf_t.get("ma50") or price
                        if rsi == 50: rsi = sf_t.get("rsi_14") or 50
                        if not h90:  h90  = sf_t.get("high_90d") or round(price * 1.15, 2)
                        if not l90:  l90  = sf_t.get("low_90d")  or round(price * 0.85, 2)
                        logger.info(f"  {ticker}: prix depuis static_fallback.json ({price} DH) — données statiques")
            except Exception:
                pass

        # Patch Médias24 getStockInfo : prix/chg/vol live si IDB a renvoyé des zéros
        if mkt_status in ("OPEN", "PRE_OPEN") and (not chg or not vol):
            q = fetch_med24_quote(ticker)
            if q:
                if not chg:
                    price = q["price"]
                    chg   = q["chg"]
                if not opn:
                    opn   = q["open"]
                if not vol:
                    vol   = q["vol"]
                time.sleep(0.2)

        if not price:
            logger.warning(f"  {ticker}: ignoré (aucune donnée)")
            continue

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
            "name":   info.get("name", ticker),
            "sector": info.get("sector", ""),
            "price":  round(price, 2),
            "chg":    round(chg, 2),
            "vol":    int(vol) if vol else 0,
            "open":   round(opn, 2),
            "close":  round(price, 2),
            "pe":     fd.get("pe"),
            "pb":     fd.get("pb"),
            "div":    fd.get("div"),
            "cap":    fd.get("cap"),
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
            # Scores v5.3 (INVIOLABLE — ne pas modifier la logique)
            "bvc":    v53["bvc"],
            "v53":    v53["v53"],
            "delta":  v53["delta"],
            "nlp":    v53["nlp"],
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
