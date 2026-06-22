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

try:
    from rapidfuzz import fuzz as _fuzz
    _RAPIDFUZZ_OK = True
except ImportError:
    _RAPIDFUZZ_OK = False

sys.path.insert(0, str(Path(__file__).parent))
try:
    from ticker_aliases import TICKER_ALIASES
except ImportError:
    TICKER_ALIASES = {}

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)-8s | %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger("NewsEngine")

if not _RAPIDFUZZ_OK:
    log.debug("rapidfuzz absent — fuzzy matching désactivé (pip install rapidfuzz)")
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
    "HCP":                   "macro",
    "Bank Al-Maghrib":       "macro",
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
}

FUZZY_THRESHOLD = 85

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
    """Tag tickers via substring exact (rapide) + fuzzy fallback (rapidfuzz si dispo).
    Ne détecte jamais par symbole court — trop de faux positifs.
    """
    t = text.lower()
    found: set[str] = set()

    # Pass 1 : substring exact (O(n_tickers × n_aliases))
    for ticker, aliases in TICKER_ALIASES.items():
        if any(alias in t for alias in aliases):
            found.add(ticker)

    # Pass 2 : fuzzy matching par phrase (uniquement si rapidfuzz disponible)
    if _RAPIDFUZZ_OK and len(t) > 30:
        sentences = re.split(r"[.!?;:\n]", t)
        for ticker, aliases in TICKER_ALIASES.items():
            if ticker in found:
                continue
            for alias in aliases:
                if len(alias) < 6:
                    continue
                for sent in sentences:
                    if len(sent) < max(len(alias) - 8, 4):
                        continue
                    if _fuzz.token_set_ratio(alias, sent) >= FUZZY_THRESHOLD:
                        found.add(ticker)
                        break
                if ticker in found:
                    break

    return list(found)

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
        if r.status_code == 403:
            hdrs2 = {
                "User-Agent": HEADERS["User-Agent"],
                "Accept": "application/rss+xml, application/xml, text/xml, */*",
                "Accept-Language": "fr-FR,fr;q=0.9",
            }
            r = requests.get(url, headers=hdrs2, timeout=TIMEOUT, allow_redirects=True)
        r.raise_for_status()
        root = ET.fromstring(r.content)
        ns = {"atom": "http://www.w3.org/2005/Atom"}

        # RSS 2.0
        for item in root.iter("item"):
            title = (item.findtext("title") or "").strip()
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

SOURCES_RSS = [
    # ── BVC / Marchés ────────────────────────────────────────────────────────
    ("https://www.casablanca-bourse.com/bourseweb/Rss-Actualite.aspx", "BVC Officiel"),
    ("https://www.ammc.ma/fr/rss.xml",                                  "AMMC"),
    ("https://www.leboursier.ma/feed",                                  "Le Boursier"),
    ("https://www.boursenews.ma/rss",                                   "BourseNews"),
    ("https://www.ilboursa.com/actualites/rss",                        "Ilboursa"),
    ("https://www.alphabourse.com/feed/",                               "Alpha Bourse"),
    # ── Presse économique marocaine ──────────────────────────────────────────
    ("https://www.medias24.com/rss/bourse.xml",                         "Medias24 Bourse"),
    ("https://www.medias24.com/rss/economie.xml",                       "Medias24 Éco"),
    ("https://www.leconomiste.com/flux-rss/bourse",                     "L'Économiste Bourse"),
    ("https://www.leconomiste.com/flux-rss/actualite",                  "L'Économiste Actu"),
    ("https://fnh.ma/rss",                                              "Finances News"),
    ("https://lavieeco.com/feed/",                                       "La Vie Éco"),
    ("https://www.challenge.ma/feed/",                                  "Challenge Maroc"),
    ("https://telquel.ma/feed/?cat=economie",                           "Telquel Éco"),
    ("https://lematin.ma/feed/",                                        "Le Matin"),
    ("https://aujourdhui.ma/feed/",                                     "Aujourd'hui le Maroc"),
    ("https://www.lopinion.ma/feed/",                                   "L'Opinion Maroc"),
    ("https://ledesk.ma/feed/",                                         "Le Desk"),
    ("https://ecoactu.ma/feed/",                                        "EcoActu"),
    ("https://maroc-hebdo.press.ma/feed/",                              "Maroc Hebdo"),
    ("https://fr.hespress.com/category/economie/feed/",                 "Hespress Éco"),
    ("https://www.infomediaire.net/feed/",                              "Infomediaire"),
    ("https://www.usinenouvelle.com/rss/maroc.xml",                    "Usine Nouvelle Maroc"),
    # ── Finance islamique / Banque centrale / HCP ────────────────────────────
    ("https://www.hcp.ma/rss.xml",                                      "HCP"),
    ("https://www.bkam.ma/rss.xml",                                     "Bank Al-Maghrib"),
    # ── Afrique / Marchés émergents ──────────────────────────────────────────
    ("https://www.agenceecofin.com/flux-rss/maroc",                    "Agence Ecofin Maroc"),
    ("https://www.financialafrik.com/feed/",                            "Financial Afrik"),
    ("https://www.africaintelligence.fr/rss",                          "Africa Intelligence"),
    ("https://www.jeuneafrique.com/feed/",                             "Jeune Afrique"),
    # ── Géopolitique / International ──────────────────────────────────────────
    ("https://www.rfi.fr/fr/rss-economie.xml",                         "RFI Économie"),
    ("https://www.france24.com/fr/economie/rss",                       "France24 Éco"),
    ("https://www.lemonde.fr/afrique/rss_full.xml",                    "Le Monde Afrique"),
    # ── Matières premières (pétrole, métaux, mines, phosphates) ─────────────
    ("https://oilprice.com/rss/main",                                   "OilPrice"),
    ("https://www.mining.com/rss/",                                     "Mining.com"),
    ("https://www.kitco.com/rss/",                                      "Kitco Métaux"),
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
    for url, name in SOURCES_RSS:
        arts = fetch_rss(url, name, max_items=25)
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
