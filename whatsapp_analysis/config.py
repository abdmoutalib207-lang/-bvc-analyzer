"""
Configuration centrale — BVC WhatsApp Analysis System
Constantes, dictionnaires, tickers, signaux multilingues
"""
from __future__ import annotations
import re
from dataclasses import dataclass, field
from typing import Dict, List, Set

# ─────────────────────────────────────────────
# TICKERS BVC (77 valeurs, tous marchés)
# ─────────────────────────────────────────────
BVC_TICKERS: Dict[str, str] = {
    # Large Cap
    "IAM": "Maroc Telecom", "ATW": "Attijariwafa Bank",
    "BCP": "Banque Centrale Populaire", "BOA": "Bank of Africa",
    "CIH": "CIH Bank", "CDM": "Crédit du Maroc", "WAF": "Wafasalaf",
    # Ciment & Matériaux
    "CMT": "Ciments du Maroc", "CIMAR": "Ciments du Maroc",
    "HPS": "HPS", "MNG": "Managem", "MIC": "Maghreb Industries",
    "ADH": "Douja Prom Addoha", "ADI": "Alliances Développement",
    "AKD": "Akdital", "CASH": "CashPlus",
    "CFGB": "CFG Bank", "CMGP": "CMGP Group",
    "CSR": "Ciments du Maroc", "MSA": "Mutandis",
    "RDS": "Residences Dar Saada", "RIS": "Risma",
    "SGTM": "Société Générale Tanger Med", "SMI": "SMI",
    "SNA": "Snep", "SOT": "Sothema", "SRM": "SRM",
    "TGCC": "Travaux Généraux de Construction de Casablanca",
    "VCNE": "Vecteur Commun Nouvelle Economie",
    # Banques & Finance
    "ATL": "Auto Hall", "BMCE": "Bank of Africa", "BMCI": "BMCI",
    "SGMB": "Société Générale Maroc", "CAM": "Crédit Agricole du Maroc",
    "LBV": "Label Vie", "MUT": "Mutandis", "DARI": "Dari Couspate",
    # Industrie
    "DWY": "Doha Water & Energy", "IMACID": "Imacid",
    "MINTRA": "Mintraoui", "M2M": "M2M Group",
    "ZELLIDJA": "Zellidja", "REBAB": "Rebab Company",
    "TIMAR": "Timar", "UNIMER": "Unimer", "YNNA": "Ynna Holding",
    # Assurance
    "ATLANTA": "Atlanta", "MAMDA": "MAMDA", "MFIN": "Maroc Factoring",
    "RMA": "RMA Watanya", "WAFA": "Wafa Assurance",
    # Immobilier
    "AFMA": "AFMA", "CCA": "Colorado", "SODEP": "Marsa Maroc",
    "NEXANS": "Nexans Maroc", "MSIN": "M Sin",
    # Agro & Services
    "COSUMAR": "Cosumar", "LESIEUR": "Lesieur Cristal",
    "DARI2": "Dari Couspate", "SFBT": "Brasseries du Maroc",
    "OUL": "Oulmès", "HALIMA": "Les Eaux Minérales d'Oulmès",
    # Pharmacie
    "PHARM": "Promopharm", "SOTHEMA": "Sothema",
    # Télécoms & Tech
    "S2M": "S2M", "NAPS": "NAPS", "DISWAY": "Disway",
    "INVOLYS": "Involys", "IB_MAROC": "IB Maroc",
    # Énergie
    "ENGIE": "Engie Maroc", "TANGER_MED": "Tanger Med",
    # Divers
    "TOTAL": "TotalEnergies Maroc", "TIMAR2": "Timar",
    "DELATTRE": "Delattre Levivier Maroc",
}

# Surnoms/abréviations utilisés dans les groupes WhatsApp
TICKER_ALIASES: Dict[str, str] = {
    "IAM": "Maroc Telecom|maroctelecom|iam|telecom|itissalat",
    "ATW": "attijari|attijariwafa|atw|wafa banque",
    "BCP": "bcp|populaire|banque populaire|bp|cpbp",
    "MNG": "managem|mng|mangem",
    "CMT": "ciments|cmt|cimar|holcim|lafarge",
    "ADH": "addoha|adh|douja",
    "ADI": "alliances|adi|alliance",
    "HPS": "hps",
    "AKD": "akdital|akd|clinique",
    "TGCC": "tgcc|travaux généraux|tgc",
    "SOT": "sothema|sot|pharma",
    "MIC": "maghreb industries|mic|mic maroc",
    "RIS": "risma|ris|hotel|hôtel",
    "COSUMAR": "cosumar|sucre|sugar",
    "LESIEUR": "lesieur|huile|cristal",
    "OUL": "oulmès|oulmes|eau minérale",
    "TOTAL": "total|totalenergies",
    "BOA": "bank of africa|boa|bmce",
    "CIH": "cih|cih bank",
    "SGMB": "sg|société générale|sgmb",
    "BMCI": "bmci|bnp|paribas",
    "WAF": "wafasalaf|wafa",
}

# Regex compilés pour extraction de tickers depuis le texte
_alias_patterns: Dict[str, re.Pattern] = {
    ticker: re.compile(r'\b(' + aliases + r')\b', re.IGNORECASE)
    for ticker, aliases in TICKER_ALIASES.items()
}

def extract_tickers_from_text(text: str) -> List[str]:
    """Extrait les tickers BVC mentionnés dans un message."""
    found = []
    text_lower = text.lower()
    # Recherche directe par ticker
    for ticker in BVC_TICKERS:
        if re.search(r'\b' + ticker + r'\b', text, re.IGNORECASE):
            found.append(ticker)
    # Recherche par alias
    for ticker, pattern in _alias_patterns.items():
        if ticker not in found and pattern.search(text_lower):
            found.append(ticker)
    return list(set(found))


# ─────────────────────────────────────────────
# DICTIONNAIRE FINANCIER MULTILINGUE
# ─────────────────────────────────────────────

SIGNAL_KEYWORDS: Dict[str, Dict[str, List[str]]] = {
    "ACHAT_FORT": {
        "fr": ["achat fort", "fort achat", "buy fort", "très bullish", "conviction maximale",
               "accumuler", "renforcer", "strong buy", "coup de maître", "opportunité rare"],
        "ar": ["شراء قوي", "فرصة ذهبية", "اشترِ", "توصية بالشراء"],
        "darija": ["chri b9wa", "frsya", "3nd buy", "wach tshari", "gha ytrq3"],
        "arabizi": ["chri", "buy fort", "3ndi buy", "wach tshari", "srk zwin"],
        "en": ["strong buy", "all in", "back up the truck", "screaming buy", "max conviction"],
    },
    "ACHETER": {
        "fr": ["acheter", "achat", "buy", "bullish", "je rentre", "je renforce", "bon point",
               "potentiel", "recommandé", "prendre position", "positif", "hausse attendue"],
        "ar": ["اشترِ", "توصية بالشراء", "صعود متوقع", "فرصة"],
        "darija": ["tshari", "dkhol", "buy", "mezyan", "gha ytl3"],
        "arabizi": ["tshari", "dkhol", "buy", "mzyan", "gha ytl3"],
        "en": ["buy", "bullish", "long", "upside", "opportunity"],
    },
    "RENFORCEMENT": {
        "fr": ["renforcer", "renforcement", "rajouter", "moyenner", "average down",
               "compléter position", "ajouter", "MRF", "je prends plus"],
        "ar": ["تعزيز", "إضافة", "زيادة"],
        "darija": ["zid chri", "zed men3ndhom", "renforci"],
        "arabizi": ["zid chri", "average", "rajouta"],
        "en": ["add more", "average down", "accumulate", "add to position"],
    },
    "VENTE": {
        "fr": ["vendre", "vente", "sell", "sortir", "couper", "stop", "alléger",
               "prendre profit", "TP", "take profit", "liquider", "je sors", "coupe",
               "bearish", "baisse", "risque élevé"],
        "ar": ["بيع", "خروج", "تصفية", "أخذ الربح"],
        "darija": ["bi3", "khroj", "3yat", "ta9der tbi3"],
        "arabizi": ["bi3", "khroj", "sell", "3ayat"],
        "en": ["sell", "exit", "short", "bearish", "take profit", "get out"],
    },
    "PANIQUE": {
        "fr": ["panique", "crash", "catastrophe", "effondrement", "s'effondre",
               "danger", "alerte rouge", "fuite", "fuyez", "urgent", "attention danger",
               "pertes massives", "krach"],
        "ar": ["هلع", "انهيار", "كارثة", "تراجع حاد"],
        "darija": ["khof", "crash", "nzel bsha3", "wili", "ghadi ytl3 lfoq"],
        "arabizi": ["khof", "crash", "nzel", "wili", "danger"],
        "en": ["panic", "crash", "disaster", "collapse", "run", "danger"],
    },
    "EUPHORIE": {
        "fr": ["incroyable", "historique", "exceptionnel", "jackpot", "on va tout rafler",
               "le marché monte tout", "feu d'artifice", "record", "tous gagnants",
               "machine à billets", "tout monte"],
        "ar": ["رائع", "تاريخي", "استثنائي", "جميل"],
        "darija": ["hh rah zwin", "yallah", "kolchi ka ytl3", "machi 3adi"],
        "arabizi": ["wow", "3jib", "machi 3adi", "kollchi yatl3"],
        "en": ["amazing", "incredible", "to the moon", "moonshot", "everything is up"],
    },
    "DOUTE": {
        "fr": ["je sais pas", "incertain", "difficile à dire", "hésitation", "risqué",
               "attention", "prudence", "pas évident", "difficile", "compliqué",
               "wait and see", "observer"],
        "ar": ["غير متأكد", "صعب", "انتظار"],
        "darija": ["ma3raftch", "machi wad7", "hder m3aya", "khlli nchuf"],
        "arabizi": ["ma3raftch", "machi wad7", "nshofu", "wait"],
        "en": ["uncertain", "not sure", "risky", "wait and see", "unclear"],
    },
    "RUMEUR": {
        "fr": ["on dit que", "j'ai entendu dire", "rumeur", "bruit de couloir",
               "source confidentielle", "off the record", "info non confirmée",
               "on m'a dit", "exclusif", "insider"],
        "ar": ["يقال", "شائعة", "معلومة غير رسمية"],
        "darija": ["sme3t bli", "9alu", "rah gal liya", "khabar kayn"],
        "arabizi": ["sme3t", "9alu", "gal liya", "insider"],
        "en": ["rumor", "heard that", "source says", "insider", "whisper"],
    },
    "IRONIE": {
        "fr": ["bien sûr", "évidemment", "comme d'habitude", "encore une fois",
               "quelle surprise", "on n'a pas vu venir", "chapeau bas"],
        "darija": ["bghina hak", "machi ghrib", "wach ghrib hada"],
        "arabizi": ["bien sur", "wach ghrib", "haha"],
        "en": ["sure", "obviously", "what a surprise", "shocking", "who knew"],
    },
    "FOMO": {
        "fr": ["tout le monde achète", "je veux pas rater", "il faut rentrer", "le train part",
               "c'est le bon moment", "ça monte encore", "last chance"],
        "darija": ["kolchi kaychri", "ra fawwitni", "lazem ndkhol"],
        "arabizi": ["kolchi kaychri", "fawwitni", "dkhol daba"],
        "en": ["everyone is buying", "don't miss out", "last chance", "train leaving"],
    },
}

# Dictionnaire Darija Finance spécialisé
DARIJA_FINANCE_DICT: Dict[str, str] = {
    "tshari": "acheter", "bi3": "vendre", "dkhol": "entrer",
    "khroj": "sortir", "trq3": "monter", "nzel": "baisser",
    "frsya": "opportunité", "khsara": "perte", "rbah": "profit",
    "soq": "marché", "bourse": "bourse", "seham": "actions",
    "waq": "cours", "taman": "prix", "stop": "stop-loss",
    "target": "objectif", "7issab": "compte", "d3f": "faible",
    "9awi": "fort", "wad7": "clair", "machi wad7": "incertain",
    "gha ytl3": "va monter", "gha ynzel": "va baisser",
    "3yat": "fatigué (vendeurs épuisés)", "machi bnin": "pas bon",
    "3jib": "excellent", "zwin": "bien", "khayb": "mauvais",
    "b9wa": "avec force", "mdrob": "bloqué", "msawwab": "bien positionné",
}

# Arabizi patterns (chiffres remplaçant lettres arabes)
ARABIZI_REPLACEMENTS = {
    "3": "ع", "7": "ح", "9": "ق", "2": "ء",
    "5": "خ", "8": "غ", "6": "ط", "4": "ظ",
}

# Prix target patterns
PRICE_TARGET_PATTERNS = [
    r'(?:objectif|cible|target|TP|tp|tp1|tp2|tp3)\s*:?\s*(\d+(?:[.,]\d+)?)\s*(?:dh|mad|MAD)?',
    r'(?:cours objectif|prix cible|prix objectif)\s*:?\s*(\d+(?:[.,]\d+)?)',
    r'(?:stop|SL|sl|stop.loss)\s*:?\s*(\d+(?:[.,]\d+)?)',
    r'(?:entrée|entry|PE|pe)\s*:?\s*(\d+(?:[.,]\d+)?)',
    r'(\d+(?:[.,]\d+)?)\s*(?:dh|MAD|mad)(?:\s+(?:cible|objectif|target))?',
    r'viser\s+(\d+(?:[.,]\d+)?)',
    r'(?:jusqu\'à|jusqu a|jusqu\'à)\s+(\d+(?:[.,]\d+)?)',
]

# ─────────────────────────────────────────────
# CONFIGURATION SYSTÈME
# ─────────────────────────────────────────────

@dataclass
class Config:
    """Configuration globale du pipeline d'analyse."""
    input_file: str = "chat.txt"
    output_dir: str = "output"
    chunk_size: int = 50_000          # lignes par chunk pour le streaming
    min_message_length: int = 3       # min chars pour message valide
    max_message_length: int = 4096    # max chars
    spam_threshold: int = 5           # messages identiques = spam
    bot_rate_threshold: float = 60.0  # messages/heure = bot probable
    min_messages_for_ranking: int = 20 # min messages pour classer membre
    backtest_start: str = "2019-01-01"
    backtest_end: str = "2025-12-31"
    ml_test_size: float = 0.2
    ml_random_state: int = 42
    n_topics: int = 20                # pour LDA
    confidence_threshold: float = 0.6
    smart_money_min_win_rate: float = 0.55  # >55% = smart money
    fear_greed_window: int = 7        # jours pour Fear & Greed rolling
    network_min_interactions: int = 3  # min interactions pour lien graphe
    report_format: str = "html"       # html | pdf | json
    languages: List[str] = field(default_factory=lambda: [
        "fr", "ar", "darija", "arabizi", "en", "es", "mixed"
    ])
    bvc_tickers: Dict[str, str] = field(default_factory=lambda: BVC_TICKERS)

DEFAULT_CONFIG = Config()
