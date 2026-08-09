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
try:
    from ticker_aliases import TICKER_ALIASES
except ImportError:
    TICKER_ALIASES = {}

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

def _sentiment(text: str) -> str:
    t = text.lower()
    pos = sum(1 for w in POSITIVE_KW if w in t)
    neg = sum(1 for w in NEGATIVE_KW if w in t)
    if pos > neg + 1: return "POSITIF"
    if neg > pos + 1: return "NEGATIF"
    return "NEUTRE"

def _tag_tickers(text: str) -> list:
    """Associe un article aux sociétés cotées qu'il mentionne nommément.

    Correspondance exacte sur les alias uniquement. Jamais par symbole court
    (« CAR », « MSA »… produiraient des faux positifs en pagaille).

    Une passe floue (rapidfuzz, token_set_ratio ≥ 85) a existé ici : elle est
    retirée. Mesurée le 09/08/2026, elle taggue 40 sociétés sur un article
    traitant du taux de chômage — token_set_ratio ignore les mots en trop, si
    bien que « maroc leasing » matche toute phrase contenant « Maroc ». Elle
    n'avait jamais tourné en production (rapidfuzz n'est pas installé par la
    CI), ce qui a évité le pire ; la laisser en place aurait été une mine.
    """
    t = text.lower()
    return [ticker for ticker, aliases in TICKER_ALIASES.items()
            if any(alias in t for alias in aliases)]


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
            articles.append({
                "id":        _article_id(link, title),
                "title":     title,
                "summary":   re.sub(r"<[^>]+>", "", desc)[:200],
                "url":       link,
                "source":    source_name,
                "category":  category,
                "date":      _parse_date(date),
                "tickers":   _tag_tickers(text),
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
    ("https://casabourse.ma/feed/",                                      "Casabourse", 25),
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
    (GNEWS.format(q="site:investing.com+Morocco+bourse"),               "Investing Maroc", 15),
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
        # Re-tagger avec les règles actuelles + ajouter champ category si absent
        for a in fresh:
            text = f"{a.get('title','')} {a.get('summary','')}"
            a["tickers"] = _tag_tickers(text)
            if "category" not in a:
                a["category"] = SOURCE_CATEGORY.get(a.get("source", ""), "economie")
        ids = {a["id"] for a in fresh}
        log.info(f"Archive chargée : {len(fresh)}/{len(articles)} articles (< {ARCHIVE_DAYS}j), re-taggés")
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

    all_articles.sort(key=lambda a: a.get("date", ""), reverse=True)
    all_articles = all_articles[:MAX_ARTICLES]

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
