#!/usr/bin/env python3
"""
BVC NewsEngine — pipeline/fetch_news.py
Récupère les actualités boursières, économiques, géopolitiques et matières premières.
Tag chaque article par ticker BVC UNIQUEMENT si le nom complet de la société apparaît dans le texte.
"""

import sys, os, json, re, time, hashlib, logging
from datetime import datetime, timezone, timedelta
from pathlib import Path
from xml.etree import ElementTree as ET

try:
    import requests
except ImportError as _e:
    sys.exit(f"Dépendance manquante : {_e}\nInstalle : pip install -r requirements_pipeline.txt")

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent))
try:
    from ticker_aliases import TICKER_ALIASES
except ImportError:
    TICKER_ALIASES = {}
try:
    from bvc_config import SIGLES_AMBIGUS
except ImportError:          # le moteur doit tourner même sans le référentiel
    SIGLES_AMBIGUS = set()

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)-8s | %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger("NewsEngine")

if not TICKER_ALIASES:
    log.warning("ticker_aliases.py introuvable — aucun ticker ne sera tagué")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Cache-Control": "no-cache",
    "Pragma": "no-cache",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
}

OUTPUT_PATH  = Path(__file__).parent.parent / "news.json"
MAX_ARTICLES = 300   # rolling archive étendue (plus de sources)
ARCHIVE_DAYS = 7
TIMEOUT      = 15

# ── Catégorie par source ───────────────────────────────────────────────────────
SOURCE_CATEGORY = {
    "BVC Officiel":          "bvc",
    "AMMC":                  "bvc",
    "Le Boursier":           "bvc",
    "BourseNews":            "bvc",
    "Alpha Bourse":          "bvc",
    "Medias24 Bourse":       "bvc",
    "Medias24":              "bvc",
    "IDBourse":              "bvc",
    "Ilboursa":              "bvc",
    "L'Économiste Bourse":   "bvc",
    "L'Économiste":          "bvc",
    "Casabourse":            "bvc",
    # LeBrief publie de l'actualité générale, pas de la bourse : le classer
    # « bvc » envoyait football et politique dans la catégorie la plus
    # financière du radar.
    "LeBrief":               "economie",
    "BVC Sociétés":          "bvc",
    "FLM":                   "bvc",
    "Investing Maroc":       "bvc",
    "HCP":                   "macro",
    "Bank Al-Maghrib":       "macro",
    "MAP":                   "macro",
    "OilPrice":              "commodites",
    "Mining.com":            "commodites",
    "Kitco Métaux":          "commodites",
    "RFI Économie":          "geopolitique",
    "France24 Éco":          "geopolitique",
    "Le Monde Afrique":      "geopolitique",
    "Jeune Afrique":         "geopolitique",
    "Africa Intelligence":   "geopolitique",
    "Agence Ecofin Maroc":   "geopolitique",
    "Financial Afrik":       "geopolitique",
    "Reuters Maroc":         "geopolitique",
    "Bloomberg Maroc":       "geopolitique",
    "Maroc Diplomatique":    "geopolitique",
}

# ── Mots-clés sentiment ───────────────────────────────────────────────────────
POSITIVE_KW = [
    "hausse", "bénéfice", "benefice", "dividende", "croissance", "progression",
    "record", "résultats positifs", "succès", "signature", "contrat", "expansion",
    "revalorisation", "recommande", "acheter", "achat", "objectif relevé",
    "surperformance", "rebond", "reprise", "nouveau sommet", "distribution",
    "augmentation", "forte", "solide", "robuste", "amélioration",
]
NEGATIVE_KW = [
    "baisse", "perte", "déficit", "recul", "sanction", "amende", "fraude",
    "retrait", "suspension", "restructuration", "alerte", "avertissement",
    "dépréciation", "provision", "risque", "dégradation", "vendre", "éviter",
    "objectif abaissé", "déception", "chute", "effondrement", "difficultés",
    "stagnation", "déprime", "faible",
]

# Motifs compilés une fois : la correspondance doit respecter les limites de
# mots. En simple sous-chaîne, « vendre » matchait « vendredi » — un décès
# survenu un vendredi comptait comme signal négatif. Un suffixe court est
# toléré pour couvrir pluriels et conjugaisons (« baisses », « pertes »).
def _motif(mots):
    return re.compile(
        r"\b(?:" + "|".join(re.escape(m) for m in mots) + r")(?:s|e|es|nt|r|rs)?\b",
        re.IGNORECASE)

_RE_POS = _motif(POSITIVE_KW)
_RE_NEG = _motif(NEGATIVE_KW)


# ─────────────────────────────────────────────────────────────────────────────
# CADRAGE FINANCE DES ÉDITEURS GÉNÉRALISTES
# ─────────────────────────────────────────────────────────────────────────────
# La plupart des relais Google News sont cadrés dans leur requête
# (« site:x.ma +(bourse OR MASI OR entreprise OR résultats OR économie) »).
# Ces sept-là sont pris sur leur flux RSS direct, qui n'a aucun cadrage : ils
# rapatrient tout ce que l'éditeur publie. Comme SOURCE_CATEGORY est par
# source et non par article, le football et les élections héritaient de la
# catégorie de leur média — LeBrief était même classé « bvc », si bien que
# « Patrick Vieira nommé sélectionneur » et « Botola Pro » atterrissaient dans
# la catégorie la plus financière du radar.
SOURCES_GENERALISTES = {
    "LeBrief", "Infomediaire", "Challenge Maroc", "Les Inspirations Éco",
    "La Vie Éco", "Aujourd'hui le Maroc", "EcoActu",
    # Généralistes internationaux : leurs flux couvrent toute l'Afrique et
    # toute l'actualité, pas seulement l'économie.
    "Jeune Afrique", "Le Monde Afrique",
}

# Vocabulaire délibérément FORT : chaque terme désigne une réalité financière
# et rien d'autre. Les mots génériques — secteur, projet, contrat, groupe,
# entreprise, marché — ont été retirés après mesure : ils laissaient passer
# « Botola Pro : le passage à 20 clubs » et « les médecins alertent ».
_FINANCE = re.compile("|".join([
    r"bourse", r"masi\b", r"msi\s?20", r"cotation", r"cot[ée]e?s?\b",
    r"introduction en bourse", r"capitalisation", r"dividende", r"r[ée]sultat net",
    r"chiffre.s? d.affaires", r"b[ée]n[ée]fice", r"ebitda",
    r"marge (nette|op[ée]rationnelle)", r"augmentation de capital", r"obligataire",
    r"emprunt", r"opcvm", r"\bammc\b", r"actionnaire|actionnariat",
    r"lev[ée]e de fonds", r"capital.risque", r"fusion|acquisition",
    r"bank al.?maghrib", r"banque centrale", r"taux directeur", r"\bhcp\b",
    r"\bpib\b", r"inflation", r"balance commerciale", r"d[ée]ficit", r"exc[ée]dent",
    r"budget", r"finances publiques", r"imp[ôo]t|fiscal", r"dirham|devise",
    r"banque|bancaire", r"assurance", r"cr[ée]dit", r"financement",
    r"investissement|investisseur", r"exportation|importation",
    r"[ée]conomie|[ée]conomique", r"conjoncture",
    r"cours de l.or|m[ée]taux pr[ée]cieux", r"p[ée]trole|gaz naturel",
]), re.IGNORECASE)


# La géographie et le sujet sont deux axes distincts. `category` décrit le
# sujet (bourse, macro, matières premières, géopolitique) ; le radar s'en
# servait pour deviner le pays, ce qui ne pouvait pas marcher : « le taux
# d'emprunt des États-Unis au plus haut » était classé « bvc », donc marocain.
# La portée se déduit du texte de l'article, pas de sa source ni de son thème.
_MAROCAIN = re.compile("|".join([
    r"\bmaroc", r"marocain", r"\bmasi\b", r"\bmsi\s?20\b", r"bourse de casablanca",
    r"casablanca", r"\brabat\b", r"tanger|marrakech|agadir|f[èe]s\b|oujda|t[ée]touan",
    r"kenitra|safi\b|essaouira|la[aâ]youne|dakhla|mekn[èe]s|nador|el jadida",
    r"dirham|\bmad\b|\bmdh\b|\bmmdh\b", r"bank al.?maghrib|\bbkam\b",
    r"\bammc\b", r"\bhcp\b", r"\bbvc\b", r"\bcdg\b",
    r"\bocp\b|\bonee\b|\bonda\b|\bcnss\b|\bmre\b|\bram\b",
]), re.IGNORECASE)


def _scope(text: str, tickers: list) -> str:
    """« MAROC » ou « INTL » — la portée géographique de l'article.

    Une société cotée citée tranche immédiatement : c'est du marocain.
    Sinon, on cherche une marque explicite du pays. En son absence l'article
    est international, y compris s'il vient d'un éditeur marocain — Medias24
    couvre le Nigeria, BourseNews les taux américains.
    """
    return "MAROC" if (tickers or _MAROCAIN.search(text)) else "INTL"


def _est_financier(source: str, text: str, tickers: list) -> bool:
    """L'article a-t-il sa place dans un radar financier ?

    Ne s'applique qu'aux éditeurs généralistes : les flux spécialisés (AMMC,
    BourseNews, Hespress Éco, matières premières…) sont financiers par
    construction et passent sans contrôle.

    Une société cotée citée suffit — c'est le signal le plus fort dont on
    dispose, et il précède le vocabulaire.
    """
    if source not in SOURCES_GENERALISTES:
        return True
    return bool(tickers) or bool(_FINANCE.search(text))


def _sentiment(text: str) -> str:
    """Tonalité d'un article, d'après le vocabulaire employé.

    On compte les mots-clés DISTINCTS présents, pas leurs occurrences : un
    titre répétant « hausse » trois fois n'est pas trois fois plus positif.

    Majorité simple. L'ancien seuil exigeait deux mots d'écart, si bien qu'un
    article ne portant qu'un seul terme négatif — « légère baisse des
    livraisons de ciment » — restait classé neutre. Résultat mesuré le
    10/08/2026 : 1 seul négatif sur 300 articles, ce qui n'a aucun sens pour
    de l'actualité financière.
    """
    pos = len(set(m.lower() for m in _RE_POS.findall(text)))
    neg = len(set(m.lower() for m in _RE_NEG.findall(text)))
    if pos > neg: return "POSITIF"
    if neg > pos: return "NEGATIF"
    return "NEUTRE"


def _tag_tickers(text: str) -> list:
    """Associe un article aux sociétés cotées qu'il mentionne nommément.

    Deux passes : les alias — correspondance exacte de sous-chaîne, insensible
    à la casse — puis les sigles en majuscules (cf. _sigles plus bas).

    Une passe floue (rapidfuzz, token_set_ratio ≥ 85) a existé ici : elle est
    retirée. Mesurée le 09/08/2026, elle taggue 40 sociétés sur un article
    traitant du taux de chômage — token_set_ratio ignore les mots en trop, si
    bien que « maroc leasing » matche toute phrase contenant « Maroc ». Elle
    n'avait jamais tourné en production (rapidfuzz n'est pas installé par la
    CI), ce qui a évité le pire ; la laisser en place aurait été une mine.
    """
    t = text.lower()
    trouves = set()
    for ticker, aliases in TICKER_ALIASES.items():
        for alias in aliases:
            if alias in ALIAS_AMBIGUS:
                # Nom commun français : n'accepter que la forme capitalisée du
                # texte d'origine. Sans ça « les milices forment des alliances
                # fragiles » taggait Alliances Développement Immobilier, et
                # l'article remontait dans le fil marocain comme actualité
                # d'une société cotée.
                if re.search(r"\b" + re.escape(alias.capitalize()) + r"\b", text):
                    trouves.add(ticker); break
            elif alias in t:
                trouves.add(ticker); break
    return sorted(trouves | _sigles(text))


# Aucun alias ne fait moins de 5 caractères — garde-fou posé le 09/08 contre la
# correspondance floue. Conséquence : les sigles employés partout par la presse
# marocaine (« BCP décroche l'ISO 45001 », « TGCC remporte le marché ») n'étaient
# jamais reconnus, et le taux de rattachement plafonnait à 7 %.
#
# On ajoute donc une passe par sigle, sur trois conditions strictes :
#   — MAJUSCULES exactes : c'est ainsi que la presse écrit un ticker ;
#   — frontières de mot, pour ne pas mordre à l'intérieur d'un autre mot ;
#   — sigle absent de SIGLES_AMBIGUS (bvc_config), qui écarte ceux qui sont
#     aussi des mots courants — « une DAR à Marrakech », « paiement CASH ».
#
# Un titre écrit tout en capitales ne porte plus d'information de casse : la
# passe s'y désactive, sans quoi « LE GAZ ET LE PÉTROLE EN BAISSE » taggerait
# Afriquia Gaz.
# Alias qui sont aussi des noms communs français. Même problème que
# SIGLES_AMBIGUS, mais sur la passe alias : ils ne comptent que capitalisés.
ALIAS_AMBIGUS = {"alliances"}

_SIGLES = {t: re.compile(r'\b' + t + r'\b')
           for t in TICKER_ALIASES if t not in SIGLES_AMBIGUS}


def _sigles(text: str) -> set:
    lettres = [c for c in text if c.isalpha()]
    if lettres and sum(c.isupper() for c in lettres) / len(lettres) > 0.6:
        return set()
    return {t for t, motif in _SIGLES.items() if motif.search(text)}


def _article_id(url: str, title: str) -> str:
    return hashlib.md5(f"{url}{title}".encode()).hexdigest()[:12]

def _parse_date(raw: str) -> str:
    if not raw: return datetime.now(timezone.utc).isoformat()
    for fmt in [
        "%a, %d %b %Y %H:%M:%S %z",
        "%a, %d %b %Y %H:%M:%S GMT",
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%d %H:%M:%S",
        "%d/%m/%Y %H:%M",
        "%d/%m/%Y",
    ]:
        try: return datetime.strptime(raw.strip(), fmt).isoformat()
        except: pass
    return raw.strip()

# ── Sources RSS ───────────────────────────────────────────────────────────────

def fetch_rss(url: str, source_name: str, max_items=30) -> list:
    articles = []
    category = SOURCE_CATEGORY.get(source_name, "economie")
    try:
        from urllib.parse import urlparse
        domain = f"{urlparse(url).scheme}://{urlparse(url).netloc}"
        hdrs = {**HEADERS, "Referer": domain, "Origin": domain}
        r = requests.get(url, headers=hdrs, timeout=TIMEOUT, allow_redirects=True)
        hdrs2 = {
            "User-Agent": HEADERS["User-Agent"],
            "Accept": "application/rss+xml, application/xml, text/xml, */*",
            "Accept-Language": "fr-FR,fr;q=0.9",
        }
        # Repli sans Referer/Origin. Le 403 ne suffit pas : certains éditeurs
        # (WordPress derrière un CDN) répondent 200 avec un flux VIDE mais valide
        # quand un Referer est présent, l'interprétant comme un hotlink. Constaté
        # le 07/08/2026 sur casabourse.ma et leseco.ma — 0 article au lieu de 4 et 50.
        if r.status_code == 403 or (
            r.ok and b"<item" not in r.content and b"<entry" not in r.content
        ):
            r = requests.get(url, headers=hdrs2, timeout=TIMEOUT, allow_redirects=True)
        r.raise_for_status()
        root = ET.fromstring(r.content)
        ns = {"atom": "http://www.w3.org/2005/Atom"}

        # RSS 2.0
        for item in root.iter("item"):
            title = (item.findtext("title") or "").strip()
            # Google News suffixe chaque titre du nom de l'éditeur, tantôt un
            # domaine ("… - boursenews.ma"), tantôt un nom ("… - L'Economiste").
            # On retire ce qui suit le dernier " - " si c'est court et sans
            # ponctuation finale — un vrai bout de titre en contiendrait.
            if "news.google.com" in url and " - " in title:
                tete, _, queue = title.rpartition(" - ")
                if tete and len(queue) <= 40 and not queue.rstrip().endswith((".", "!", "?", ":")):
                    title = tete.rstrip()
            link  = (item.findtext("link")  or "").strip()
            desc  = (item.findtext("description") or "").strip()
            date  = (item.findtext("pubDate") or item.findtext("dc:date") or "").strip()
            if not title: continue
            text = f"{title} {desc}"
            tickers = _tag_tickers(text)
            # Éditeur généraliste : l'article doit prouver qu'il est financier.
            if not _est_financier(source_name, text, tickers):
                continue
            articles.append({
                "id":        _article_id(link, title),
                "title":     title,
                "summary":   re.sub(r"<[^>]+>", "", desc)[:200],
                "url":       link,
                "source":    source_name,
                "category":  category,
                "date":      _parse_date(date),
                "tickers":   tickers,
                "scope":     _scope(text, tickers),
                "sentiment": _sentiment(text),
            })
            if len(articles) >= max_items: break

        # Atom
        if not articles:
            for entry in root.findall("atom:entry", ns) or root.findall("{http://www.w3.org/2005/Atom}entry"):
                title = (entry.findtext("{http://www.w3.org/2005/Atom}title") or "").strip()
                link  = ""
                for ln in entry.findall("{http://www.w3.org/2005/Atom}link"):
                    link = ln.get("href", "")
                    break
                date  = entry.findtext("{http://www.w3.org/2005/Atom}updated") or \
                        entry.findtext("{http://www.w3.org/2005/Atom}published") or ""
                desc  = entry.findtext("{http://www.w3.org/2005/Atom}summary") or \
                        entry.findtext("{http://www.w3.org/2005/Atom}content") or ""
                desc  = re.sub(r"<[^>]+>", "", desc)[:200]
                if not title: continue
                text  = f"{title} {desc}"
                articles.append({
                    "id":        _article_id(link, title),
                    "title":     title,
                    "summary":   desc,
                    "url":       link,
                    "source":    source_name,
                    "category":  category,
                    "date":      _parse_date(date),
                    "tickers":   _tag_tickers(text),
                    "scope":     _scope(text, _tag_tickers(text)),
                    "sentiment": _sentiment(text),
                })
                if len(articles) >= max_items: break

        log.info(f"{source_name}: {len(articles)} articles")
    except Exception as e:
        log.warning(f"{source_name} RSS erreur: {e}")
    return articles


def fetch_medias24_api(max_items=20) -> list:
    articles = []
    endpoints = [
        "https://medias24.com/content/api?method=getLatestNews&category=bourse&format=json",
        "https://medias24.com/content/api?method=getArticles&rubrique=bourse&format=json",
        "https://medias24.com/content/api?method=getNews&format=json&count=30",
    ]
    for ep in endpoints:
        try:
            r = requests.get(ep, headers=HEADERS, timeout=TIMEOUT)
            if r.status_code == 200 and len(r.text) > 100:
                data = r.json()
                items = data if isinstance(data, list) else data.get("result", data.get("articles", []))
                for item in (items or [])[:max_items]:
                    title   = str(item.get("title", item.get("titre", ""))).strip()
                    link    = str(item.get("url",   item.get("link",  ""))).strip()
                    desc    = str(item.get("summary", item.get("description", item.get("content", "")))).strip()
                    date    = str(item.get("date", item.get("pubDate", ""))).strip()
                    if not title: continue
                    text = f"{title} {desc}"
                    articles.append({
                        "id":        _article_id(link, title),
                        "title":     title,
                        "summary":   re.sub(r"<[^>]+>", "", desc)[:200],
                        "url":       link,
                        "source":    "Medias24",
                        "category":  "bvc",
                        "date":      _parse_date(date),
                        "tickers":   _tag_tickers(text),
                        "scope":     _scope(text, _tag_tickers(text)),
                        "sentiment": _sentiment(text),
                    })
                if articles:
                    log.info(f"Medias24 API: {len(articles)} articles via {ep.split('?')[1][:40]}")
                    return articles
        except Exception as e:
            log.debug(f"Medias24 endpoint {ep}: {e}")
    return articles


def fetch_idb_news(max_items=15) -> list:
    articles = []
    try:
        r = requests.get("https://www.idbourse.com/api/proxy/actualites",
                         headers={**HEADERS, "Referer": "https://www.idbourse.com"},
                         timeout=TIMEOUT)
        if r.status_code == 200:
            data = r.json()
            items = data if isinstance(data, list) else data.get("data", [])
            for item in (items or [])[:max_items]:
                title = str(item.get("titre", item.get("title", ""))).strip()
                link  = str(item.get("url",   item.get("link",  ""))).strip()
                desc  = str(item.get("resume", item.get("description", ""))).strip()
                date  = str(item.get("date",  "")).strip()
                if not title: continue
                text = f"{title} {desc}"
                articles.append({
                    "id":        _article_id(link, title),
                    "title":     title,
                    "summary":   re.sub(r"<[^>]+>", "", desc)[:200],
                    "url":       link,
                    "source":    "IDBourse",
                    "category":  "bvc",
                    "date":      _parse_date(date),
                    "tickers":   _tag_tickers(text),
                    "scope":     _scope(text, _tag_tickers(text)),
                    "sentiment": _sentiment(text),
                })
            log.info(f"IDBourse news: {len(articles)} articles")
    except Exception as e:
        log.warning(f"IDBourse news erreur: {e}")
    return articles


# ── Liste des sources RSS ─────────────────────────────────────────────────────

# Relais Google News : certains éditeurs marocains ne publient aucun flux RSS.
# Restreindre la requête au domaine (site:...) donne un flux propre à l'éditeur,
# sans scraper son HTML. `q` doit être encodé pour une URL.
# Éditeurs généralistes : la requête est cadrée sur la finance. Sans ce
# filtre, le relais rapatriait sport et culture, qui héritaient ensuite de la
# catégorie de leur source (SOURCE_CATEGORY est par source, pas par article).
GNEWS = "https://news.google.com/rss/search?q={q}&hl=fr&gl=MA&ceid=MA:fr"

SOURCES_RSS = [
    # ── BVC / Marchés ────────────────────────────────────────────────────────
    (GNEWS.format(q="site:casablanca-bourse.com"),              "BVC Officiel", 25),
    ("https://www.ammc.ma/fr/rss.xml",                                  "AMMC", 25),
    # ("https://www.leboursier.ma/feed", "Le Boursier"),  # domaine injoignable
    # depuis le 07/08/2026 et absent de l'index Google News. Son contenu est
    # désormais couvert par Medias24 (même groupe).
    (GNEWS.format(q="site:boursenews.ma"),                      "BourseNews", 25),
    (GNEWS.format(q="site:ilboursa.com"),                       "Ilboursa", 25),
    # Sites sans flux RSS propre → relais Google News restreint au domaine.
    # Vérifié le 07/08/2026 : alphabourse.com ET .ma ne servent aucun flux
    # (l'ancienne entrée alphabourse.com/feed/ était morte et ne remontait rien).
    # ── Sociétés cotées — le levier du tagging ───────────────────────────────
    # Les flux thématiques remontent surtout du macro et du marché ; seuls 9
    # articles sur 300 mentionnaient une société cotée, ce qui plafonnait le
    # tagging quelle que soit la qualité des alias. Ces requêtes nomment
    # directement les valeurs : ce qu'elles rapportent est taggable par
    # construction (résultats, contrats, opérations sur capital).
    (GNEWS.format(q='%22Attijariwafa%22+OR+%22Maroc+Telecom%22+OR+%22Bank+of+Africa%22'
                    '+OR+%22BCP%22+OR+%22CIH+Bank%22+OR+%22Cr%C3%A9dit+du+Maroc%22'
                    '+OR+%22Wafa+Assurance%22+OR+%22Sanlam+Maroc%22+OR+%22CFG+Bank%22'),
     "BVC Sociétés", 12),
    (GNEWS.format(q='%22Managem%22+OR+%22Mini%C3%A8re+Touissit%22+OR+%22Taqa+Morocco%22'
                    '+OR+%22Afriquia+Gaz%22+OR+%22TotalEnergies+Maroc%22+OR+%22Ciments+du+Maroc%22'
                    '+OR+%22Holcim+Maroc%22+OR+%22Sonasid%22+OR+%22Aluminium+du+Maroc%22'),
     "BVC Sociétés", 12),
    (GNEWS.format(q='%22Cosumar%22+OR+%22Label+Vie%22+OR+%22Lesieur+Cristal%22+OR+%22Marsa+Maroc%22'
                    '+OR+%22Akdital%22+OR+%22TGCC%22+OR+%22Alliances%22+OR+%22Addoha%22'
                    '+OR+%22R%C3%A9sidences+Dar+Saada%22+OR+%22Risma%22+OR+%22Vicenne%22'),
     "BVC Sociétés", 12),
    (GNEWS.format(q="site:alphabourse.ma"),                             "Alpha Bourse", 20),
    (GNEWS.format(q="site:flm.ma"),                                     "FLM", 15),
    # ── Presse économique marocaine ──────────────────────────────────────────
    (GNEWS.format(q="site:medias24.com+(bourse+OR+MASI+OR+entreprise+OR+r%C3%A9sultats+OR+%C3%A9conomie)"),                       "Medias24", 25),
    # ('https://www.medias24.com/rss/economie.xml', 'Medias24 Éco'),  # 403 ; le
    # domaine medias24.com est couvert en entier par le relais ci-dessus.
    (GNEWS.format(q="site:leconomiste.com+(bourse+OR+MASI+OR+entreprise+OR+r%C3%A9sultats+OR+%C3%A9conomie)"),                    "L'Économiste", 20),
    # ('https://www.leconomiste.com/flux-rss/actualite', "L'Économiste Actu"),  # 403 ;
    # leconomiste.com est couvert en entier par le relais ci-dessus.
    (GNEWS.format(q="site:fnh.ma"),                             "Finances News", 20),
    ("https://lavieeco.com/feed/",                                       "La Vie Éco", 12),
    ("https://www.challenge.ma/feed/",                                  "Challenge Maroc", 12),
    (GNEWS.format(q="site:telquel.ma+(bourse+OR+MASI+OR+entreprise+OR+r%C3%A9sultats+OR+%C3%A9conomie)"),                         "Telquel Éco", 8),
    (GNEWS.format(q="site:lematin.ma+(bourse+OR+MASI+OR+entreprise+OR+r%C3%A9sultats+OR+%C3%A9conomie)"),                         "Le Matin", 10),
    ("https://aujourdhui.ma/feed/",                                     "Aujourd'hui le Maroc", 10),
    (GNEWS.format(q="site:lopinion.ma+(bourse+OR+MASI+OR+entreprise+OR+r%C3%A9sultats+OR+%C3%A9conomie)"),                        "L'Opinion Maroc", 8),
    (GNEWS.format(q="site:ledesk.ma+(bourse+OR+MASI+OR+entreprise+OR+r%C3%A9sultats+OR+%C3%A9conomie)"),                          "Le Desk", 8),
    ("https://ecoactu.ma/feed/",                                        "EcoActu", 12),
    (GNEWS.format(q="site:maroc-hebdo.com+(bourse+OR+MASI+OR+entreprise+OR+r%C3%A9sultats+OR+%C3%A9conomie)"),                    "Maroc Hebdo", 8),
    ("https://fr.hespress.com/category/economie/feed/",                 "Hespress Éco", 10),
    ("https://www.infomediaire.net/feed/",                              "Infomediaire", 10),
    ("https://lebrief.ma/feed/",                                         "LeBrief", 12),
    (GNEWS.format(q="site:le360.ma+(bourse+OR+MASI+OR+entreprise+OR+r%C3%A9sultats+OR+%C3%A9conomie)"),
     "Le360", 10),
    ("https://leseco.ma/feed/",                                          "Les Inspirations Éco", 12),
    # Le flux /rss/maroc.xml a disparu ; /rss existe mais il est GLOBAL —
    # il remontait du champagne et des podcasts historiques. Relais cadré Maroc.
    (GNEWS.format(q="site:usinenouvelle.com+Maroc"),                    "Usine Nouvelle Maroc", 6),
    (GNEWS.format(q="site:mapnews.ma+(bourse+OR+MASI+OR+entreprise+OR+r%C3%A9sultats+OR+%C3%A9conomie)"),                                 "MAP", 12),
    (GNEWS.format(q="site:laquotidienne.ma+(bourse+OR+MASI+OR+entreprise+OR+r%C3%A9sultats+OR+%C3%A9conomie)"),                           "La Quotidienne", 10),
    (GNEWS.format(q="site:maroc-diplomatique.net+(bourse+OR+MASI+OR+entreprise+OR+r%C3%A9sultats+OR+%C3%A9conomie)"),                     "Maroc Diplomatique", 6),
    # ── Finance islamique / Banque centrale / HCP ────────────────────────────
    (GNEWS.format(q="site:hcp.ma"),                             "HCP", 8),
    (GNEWS.format(q="site:bkam.ma"),                            "Bank Al-Maghrib", 10),
    # ── Afrique / Marchés émergents ──────────────────────────────────────────
    (GNEWS.format(q="site:agenceecofin.com"),                   "Agence Ecofin Maroc", 8),
    ("https://www.financialafrik.com/feed/",                            "Financial Afrik", 8),
    (GNEWS.format(q="site:africaintelligence.fr"),              "Africa Intelligence", 6),
    ("https://www.jeuneafrique.com/feed/",                             "Jeune Afrique", 6),
    # ── International — cadré sur le Maroc ────────────────────────────────────
    # Les flux globaux de ces éditeurs noieraient l'actualité BVC (des milliers
    # d'articles sans rapport). On les restreint donc au Maroc via Google News.
    # Reuters a fermé ses flux RSS publics ; Bloomberg n'expose que du global.
    (GNEWS.format(q="site:reuters.com+Morocco"),                        "Reuters Maroc", 8),
    (GNEWS.format(q="site:bloomberg.com+Morocco"),                      "Bloomberg Maroc", 8),
    # ── Géopolitique / International ──────────────────────────────────────────
    ("https://www.rfi.fr/fr/economie/rss",                             "RFI Économie", 6),
    ("https://www.france24.com/fr/economie/rss",                       "France24 Éco", 6),
    ("https://www.lemonde.fr/afrique/rss_full.xml",                    "Le Monde Afrique", 6),
    # ── Matières premières (pétrole, métaux, mines, phosphates) ─────────────
    ("https://oilprice.com/rss/main",                                   "OilPrice", 8),
    ("https://www.mining.com/rss/",                                     "Mining.com", 8),
    # Kitco a supprimé ses flux RSS publics (404). Un relais site:kitco.com ne
    # rend que 7 articles ; une requête thématique couvre bien mieux le besoin
    # réel — le cours des métaux précieux, qui pèse sur MNG, SMI et CMT.
    (GNEWS.format(q="cours+de+l%27or+m%C3%A9taux+pr%C3%A9cieux"),        "Kitco Métaux", 6),
]


def _load_archive() -> tuple:
    if not OUTPUT_PATH.exists():
        return [], set()
    try:
        data = json.loads(OUTPUT_PATH.read_text(encoding="utf-8"))
        articles = data.get("articles", [])
        cutoff = (datetime.now(timezone.utc) - timedelta(days=ARCHIVE_DAYS)).isoformat()
        fresh = [a for a in articles if a.get("date", "") >= cutoff]
        # Re-tagger avec les règles actuelles + ajouter champ category si absent.
        # Le sentiment est recalculé lui aussi : sans ça, une correction des
        # règles ne s'appliquerait qu'aux articles neufs et l'archive
        # continuerait d'afficher des étiquettes produites par l'ancien code.
        retenus = []
        for a in fresh:
            text = f"{a.get('title','')} {a.get('summary','')}"
            a["tickers"] = _tag_tickers(text)
            a["sentiment"] = _sentiment(text)
            a["category"] = SOURCE_CATEGORY.get(a.get("source", ""), "economie")
            a["scope"] = _scope(text, a["tickers"])
            # Le cadrage finance s'applique aussi à l'archive : sans ça, les
            # articles déjà stockés continueraient de polluer le fil jusqu'à
            # leur expiration, soit une semaine.
            if _est_financier(a.get("source", ""), text, a["tickers"]):
                retenus.append(a)
        ecartes = len(fresh) - len(retenus)
        fresh = retenus
        ids = {a["id"] for a in fresh}
        log.info(f"Archive chargée : {len(fresh)}/{len(articles)} articles (< {ARCHIVE_DAYS}j), re-taggés · {ecartes} écartés comme non financiers")
        return fresh, ids
    except Exception as e:
        log.warning(f"Impossible de charger l'archive : {e}")
        return [], set()


def run():
    from collections import Counter

    # 0. Archive existante (rolling) + re-tag
    archived, seen_ids = _load_archive()
    all_articles = list(archived)

    # 1. RSS feeds
    for entry in SOURCES_RSS:
        # 3e élément facultatif : plafond d'articles propre à la source.
        # Les relais Google News renvoient 100 articles chacun ; sans plafond
        # réduit ils satureraient MAX_ARTICLES et évinceraient les flux natifs,
        # dont les liens pointent directement sur l'article.
        url, name = entry[0], entry[1]
        cap = entry[2] if len(entry) > 2 else 25
        arts = fetch_rss(url, name, max_items=cap)
        new_count = 0
        for a in arts:
            if a["id"] not in seen_ids:
                all_articles.append(a)
                seen_ids.add(a["id"])
                new_count += 1
        if arts: time.sleep(0.4)

    # 2. Medias24 API
    for a in fetch_medias24_api(20):
        if a["id"] not in seen_ids:
            all_articles.append(a)
            seen_ids.add(a["id"])

    # 3. IDBourse news
    for a in fetch_idb_news(15):
        if a["id"] not in seen_ids:
            all_articles.append(a)
            seen_ids.add(a["id"])

    # Fenêtre glissante appliquée à TOUT, pas seulement à l'archive rechargée.
    # Les articles fraîchement collectés n'étaient jamais filtrés par âge : un
    # flux mal réglé pouvait injecter des dépêches de 2017 — c'était le cas du
    # relais « site:investing.com », dont le plus récent article datait de
    # 237 jours. Le fichier annonce « rolling 7j », il doit le tenir.
    _limite = (datetime.now(timezone.utc) - timedelta(days=ARCHIVE_DAYS)).isoformat()
    _avant = len(all_articles)
    all_articles = [a for a in all_articles if (a.get("date") or "") >= _limite]
    if _avant != len(all_articles):
        log.info(f"Hors fenêtre {ARCHIVE_DAYS}j écartés : {_avant - len(all_articles)}")

    all_articles.sort(key=lambda a: a.get("date", ""), reverse=True)

    # Coupe à MAX_ARTICLES, mais en réservant d'abord les plus récents de CHAQUE
    # source. Sans cette réserve, un éditeur qui publie peu disparaît totalement
    # du fichier : trié par date sur sept jours et 44 sources, il n'atteint
    # jamais les 300 premières places. Mesuré le 11/08 — Le Matin sortait
    # 10 articles de moins d'un jour et aucun n'était retenu, Bank Al-Maghrib
    # non plus. Un flux institutionnel publie rarement mais rarement pour rien.
    RESERVE_PAR_SOURCE = 2
    vus_source, reserves, reste = {}, [], []
    for a in all_articles:
        src = a.get("source", "?")
        if vus_source.get(src, 0) < RESERVE_PAR_SOURCE:
            vus_source[src] = vus_source.get(src, 0) + 1
            reserves.append(a)
        else:
            reste.append(a)
    all_articles = (reserves + reste)[:MAX_ARTICLES]
    all_articles.sort(key=lambda a: a.get("date", ""), reverse=True)

    now = datetime.now(timezone.utc)
    output = {
        "updated":  now.isoformat(),
        "count":    len(all_articles),
        "articles": all_articles,
    }

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    log.info(f"news.json → {OUTPUT_PATH} ({len(all_articles)} articles, rolling {ARCHIVE_DAYS}j)")

    srcs = Counter(a["source"] for a in all_articles)
    for src, n in srcs.most_common(12):
        log.info(f"  {src}: {n}")

    tagged = [a for a in all_articles if a.get("tickers")]
    cats   = Counter(a.get("category","?") for a in all_articles)
    log.info(f"Articles taggés ticker: {len(tagged)}/{len(all_articles)}")
    for cat, n in cats.most_common():
        log.info(f"  Catégorie [{cat}]: {n}")

    return output


if __name__ == "__main__":
    run()
