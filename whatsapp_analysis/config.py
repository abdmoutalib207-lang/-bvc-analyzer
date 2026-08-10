"""
Configuration centrale — BVC WhatsApp Analysis System
Constantes, dictionnaires, tickers, signaux multilingues
"""
from __future__ import annotations
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Set

# Référentiel unique des sociétés cotées. Le module NLP entretenait autrefois
# sa propre table, qui a divergé — d'où l'import plutôt que la recopie.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from bvc_config import COMPANY_NAMES  # noqa: E402

# ─────────────────────────────────────────────
# TICKERS BVC — dérivés de bvc_config, source unique
# ─────────────────────────────────────────────
# Cette table était auparavant saisie à la main, et fausse sur 11 sociétés :
# SNA y valait « Snep », MSA « Mutandis » (la confusion que le CLAUDE.md
# interdit nommément), CMT « Ciments du Maroc » alors que c'est une minière.
# Comme le NLP pèse 28 % du score, un message sur SNEP remontait dans la note
# de Sonasid. Elle contenait aussi une quarantaine de codes inexistants à la
# BVC — CIMAR, YNNA, MAMDA, SFBT (société tunisienne), DOHA WATER…
#
# Il n'y a désormais qu'un référentiel : bvc_config.COMPANY_NAMES.
BVC_TICKERS: Dict[str, str] = dict(COMPANY_NAMES)

# Surnoms réellement employés dans les groupes : anciennes raisons sociales,
# formes courtes, fautes de frappe fréquentes. Le nom officiel est ajouté
# automatiquement plus bas — inutile de le répéter ici.
#
# Règle : un surnom doit désigner UNE société. Les termes de secteur en sont
# exclus — l'ancienne table associait « ciments|holcim|lafarge » à Minière
# Touissit, « clinique » à Akdital, « hotel » à Risma, « pharma » à Sothema,
# « sucre » à Cosumar. Un message sur le prix du sucre n'est pas un avis sur
# Cosumar.
SURNOMS: Dict[str, List[str]] = {
    "IAM":  ["maroc telecom", "maroctelecom", "itissalat", "ittissalat"],
    "ATW":  ["attijari", "attijariwafa", "attijariwafabank"],
    "BCP":  ["banque populaire", "banque centrale populaire", "chaabi"],
    "BOA":  ["bank of africa", "bmce", "bmce bank"],
    "CIH":  ["cih bank", "credit immobilier"],
    "CDM":  ["credit du maroc"],
    "BMC":  ["bmci"],
    "CFGB": ["cfg bank", "cfg"],
    "WAF":  ["wafa assurance", "wafa assurances"],
    "SAF":  ["sanlam", "sanlam maroc"],
    "ATL":  ["atlantasanad", "atlanta sanad", "atlanta"],
    "MGL":  ["maghrebail"],
    "MRL":  ["maroc leasing"],
    "SLM":  ["salafin"],
    "EQD":  ["eqdom", "credit eqdom"],
    "CASH": ["cash plus", "cashplus"],
    "MNG":  ["managem", "mangem", "manageme"],
    "CMT":  ["miniere touissit", "touissit", "cmt maroc"],
    "SMI":  ["smi imiter", "societe metallurgique imiter"],
    "ZLD":  ["zellidja"],
    "SNA":  ["sonasid"],
    "SNP":  ["snep"],
    "ALU":  ["aluminium du maroc", "alu maroc"],
    "STK":  ["stokvis", "stockvis", "stokvis nord afrique"],
    "STR":  ["stroc", "stroc industrie"],
    "SRM":  ["realisations mecaniques", "srm maroc"],
    "LHM":  ["holcim", "lafarge", "lafargeholcim", "holcim maroc"],
    "CIM":  ["ciments du maroc", "cimar"],
    "AFI":  ["afric industries"],
    "TGCC": ["tgcc", "travaux generaux de construction"],
    "SGTM": ["sgtm", "societe generale des travaux du maroc"],
    "JET":  ["jet contractors", "jet alu"],
    "ADH":  ["addoha", "douja", "douja prom"],
    "ADI":  ["alliances", "alliances developpement"],
    "RDS":  ["dar saada", "residences dar saada"],
    "ARD":  ["aradei", "aradei capital"],
    "IMI":  ["immorente", "immorente invest"],
    "BAL":  ["balima"],
    "AKD":  ["akdital"],
    "SOT":  ["sothema"],
    "PPM":  ["promopharm"],
    "VCNE": ["vicenne"],
    "CSR":  ["cosumar"],
    "LES":  ["lesieur", "lesieur cristal"],
    "DAR":  ["dari couspate", "couspate"],
    "UNI":  ["unimer"],
    "MUT":  ["mutandis"],
    "CAR":  ["cartier saada", "cartier"],
    "OUL":  ["oulmes", "eaux minerales oulmes", "sidi ali"],
    "SBS":  ["boissons du maroc", "brasseries du maroc", "societe des boissons"],
    "LBV":  ["label vie", "labelvie", "carrefour maroc"],
    "FNB":  ["fenie brossette", "fenie"],
    "HAL":  ["auto hall"],
    "NEJ":  ["auto nejma", "nejma"],
    "ENK":  ["ennakl", "ennakl automobiles"],
    "CMGP": ["cmgp group"],
    "MSA":  ["marsa maroc", "sodep", "sodep marsa"],
    "CTM":  ["ctm", "compagnie de transports"],
    "TIM":  ["timar"],
    "TQA":  ["taqa morocco", "taqa"],
    "GAZ":  ["afriquia gaz", "afriquia"],
    "TMA":  ["totalenergies", "total maroc", "totalenergies marketing"],
    "MOX":  ["maghreb oxygene"],
    "COL":  ["colorado"],
    "HPS":  ["hps", "hightech payment", "highteh payment"],
    "M2M":  ["m2m group"],
    "MIC":  ["microdata"],
    "INV":  ["involys"],
    "IBM":  ["ib maroc", "ibmaroc"],
    "S2M":  ["s2m", "sm monetique", "societe maroc monetique"],
    "DSW":  ["disway"],
    "DTT":  ["disty", "disty technologies"],
    "DHO":  ["delta holding"],
    "REB":  ["rebab", "rebab company"],
    "AFM":  ["afma"],
    "AGM":  ["agma"],
    "RIS":  ["risma", "accor maroc"],
}

# Symboles qui sont aussi des mots courants en français ou en darija. Écrits
# en minuscules ils ne désignent pas la société : « les » (article), « dar »
# (maison), « car » (conjonction), « adi » (ordinaire), « gaz », « bal »,
# « sot », « col », « uni », « cash », « ris », « mic ». On exige donc la
# forme MAJUSCULE exacte pour ceux-là — c'est ainsi que les tickers
# s'écrivent dans les groupes.
#
# Liste établie en mesurant, sur un corpus français réel (les 300 articles de
# news.json), combien de fois chaque ticker apparaît en minuscules comme mot
# isolé : « les » sortait 140 fois. Les formes darija ont été ajoutées à la
# main, le corpus de presse ne les contenant pas.
#
# Ne pas l'allonger par précaution : chaque entrée coûte du rappel, puisqu'un
# message écrivant le ticker en minuscules ne sera plus reconnu.
SYMBOLES_AMBIGUS: Set[str] = {
    "LES", "CAR", "DAR", "GAZ", "BAL", "SOT", "COL", "UNI",
    "CASH", "RIS", "SAF", "TIM", "MIC", "MUT", "ADI", "NEJ",
}


def _sans_accent(s: str) -> str:
    import unicodedata
    return "".join(c for c in unicodedata.normalize("NFD", s)
                   if unicodedata.category(c) != "Mn")


def _construire_alias() -> Dict[str, List[str]]:
    """Nom officiel + surnoms, en formes accentuée et non accentuée."""
    out: Dict[str, List[str]] = {}
    for t, nom in BVC_TICKERS.items():
        formes = {nom.lower(), _sans_accent(nom.lower())}
        for s in SURNOMS.get(t, []):
            formes.add(s.lower())
            formes.add(_sans_accent(s.lower()))
        # trop court = trop de faux positifs sur du texte libre
        out[t] = sorted(f for f in formes if len(f) >= 4)
    return out


TICKER_ALIASES: Dict[str, List[str]] = _construire_alias()

# Un alias ne doit jamais désigner deux sociétés : sans ce contrôle,
# « maroc leasing » figurait dans les alias de Maghrebail.
_collisions = {}
for _t, _als in TICKER_ALIASES.items():
    for _a in _als:
        _collisions.setdefault(_a, []).append(_t)
_ambigus = {a: ts for a, ts in _collisions.items() if len(ts) > 1}
if _ambigus:  # pragma: no cover — garde-fou de développement
    raise ValueError(f"alias partagés par plusieurs tickers : {_ambigus}")

# Regex compilés pour extraction de tickers depuis le texte
_alias_patterns: Dict[str, re.Pattern] = {
    ticker: re.compile(r'\b(' + "|".join(re.escape(a) for a in aliases) + r')\b',
                       re.IGNORECASE)
    for ticker, aliases in TICKER_ALIASES.items() if aliases
}
_symbole_patterns: Dict[str, re.Pattern] = {
    t: re.compile(r'\b' + t + r'\b',
                  0 if t in SYMBOLES_AMBIGUS else re.IGNORECASE)
    for t in BVC_TICKERS
}


def extract_tickers_from_text(text: str) -> List[str]:
    """Tickers BVC mentionnés dans un message.

    Deux passes : le symbole lui-même, puis les alias. Les symboles qui sont
    aussi des mots courants ne comptent qu'en majuscules (cf. SYMBOLES_AMBIGUS),
    sans quoi « la dar » ou « car il monte » taggueraient Dari Couspate et
    Cartier Saada.
    """
    trouves = []
    for ticker, motif in _symbole_patterns.items():
        if motif.search(text):
            trouves.append(ticker)
    for ticker, motif in _alias_patterns.items():
        if ticker not in trouves and motif.search(text):
            trouves.append(ticker)
    return sorted(set(trouves))


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
