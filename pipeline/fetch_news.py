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

for pkg in ["requests"]:
    try: __import__(pkg)
    except ImportError:
        import subprocess; subprocess.run([sys.executable, "-m", "pip", "install", pkg, "-q"], check=True)

import requests

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)-8s | %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger("NewsEngine")

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

# ── Noms complets des sociétés cotées BVC ─────────────────────────────────────
# Règle stricte : un ticker n'est tagué QUE si l'un de ces noms complets
# apparaît dans le texte de l'article. Aucune détection par symbole court (3 lettres).
TICKER_KEYWORDS = {
    "IAM":  ["maroc telecom", "itissalat al maghrib", "itissalat al-maghrib"],
    "ATW":  ["attijariwafa", "attijari wafa bank", "attijariwafa bank"],
    "BCP":  ["banque centrale populaire", "banques populaires", "crédit populaire du maroc", "groupe banque populaire"],
    "BOA":  ["bank of africa", "bmce bank of africa", "banque of africa"],
    "CIH":  ["cih bank", "crédit immobilier et hôtelier", "cih banque"],
    "CDM":  ["crédit du maroc", "credit du maroc"],
    "WAF":  ["wafa assurance", "wafa insurance"],
    "LHM":  ["lafargeholcim maroc", "lafarge holcim maroc", "lafarge maroc", "holcim maroc"],
    "GAZ":  ["afriquia gaz", "afriquia gazs"],
    "ATL":  ["auto hall", "autohall", "groupe auto hall"],
    "HPS":  ["hightech payment systems", "hightech payment", "hps worldwide"],
    "LBV":  ["label'vie", "labelvie", "groupe label vie", "label vie"],
    "LES":  ["lesieur cristal", "lesieur-cristal"],
    "TQA":  ["taqa morocco", "jlec", "taqa maroc", "jordanie low electricity"],
    "MRL":  ["marsa maroc", "sodep maroc", "marsa maroc sa"],
    "TMA":  ["totalenergies marketing maroc", "total energies maroc", "total maroc", "total marketing maroc"],
    "CMT":  ["minière de touissit", "compagnie minière de touissit", "touissit", "cmt touissit"],
    "MNG":  ["managem", "groupe managem", "managem group"],
    "SMI":  ["s.m. imiter", "sm imiter", "société métallurgique imiter", "smiter"],
    "AKD":  ["akdital", "groupe akdital", "cliniques akdital"],
    "ARD":  ["aradei capital", "aradei"],
    "SAF":  ["saham assurance", "sanlam maroc", "saham finances"],
    "OUL":  ["oulmès", "eaux minérales d'oulmès", "brasseries du maroc oulmès"],
    "CIM":  ["cimat", "ciments de l'atlas", "cimat maroc"],
    "CTM":  ["compagnie de transports au maroc", "ctm voyages", "ctm transport"],
    "ZLD":  ["zalagh", "groupe zalagh", "zalagh holding"],
    "SOT":  ["sothema", "laboratoires sothema"],
    "MSA":  ["mutandis", "mutandis sca"],
    "ADI":  ["alliances développement", "alliance développement immobilier", "alliances immobilier", "alliances dév"],
    "ADH":  ["addoha", "groupe addoha", "douja promotion addoha"],
    "TGCC": ["tgcc", "travaux généraux de construction de casablanca"],
    "CFGB": ["cfg bank", "cfg banks"],
    "CASH": ["cash plus", "cash plus maroc"],
    "SGTM": ["sgtm", "société générale de travaux du maroc"],
    "CMGP": ["cmgp group", "cmgp"],
    "VCNE": ["vivo energy maroc", "vivo energy"],
    "RIS":  ["risma", "résidences touristiques de montagne et d'affaires"],
    "CSR":  ["cosumar", "cosumar sa", "compagnie sucrière marocaine"],
    "SNA":  ["sonasid", "société nationale de sidérurgie"],
    "SRM":  ["stokvis maroc", "stokvis"],
    "RDS":  ["résidences dar saada", "dar saada"],
    "ALU":  ["aluminium du maroc", "aluminium maroc"],
    "MGL":  ["maghrebail", "maroc leasing"],
    "DAR":  ["dari couspate", "dar couspate"],
    "IMI":  ["immorente invest", "immorente"],
    "DTT":  ["disty technologies", "disty tech"],
    "DSW":  ["delattre levivier maroc", "delattre levivier"],
    "MOX":  ["maghreb oxygene", "maghreb oxygène"],
    "STR":  ["stradim", "stradim immobilier"],
    "TIM":  ["timar", "timar maroc"],
    "SNP":  ["snep maroc", "société nationale d'électrolyse et de pétrochimie"],
    "SLM":  ["salafin", "salafin maroc"],
    "JET":  ["jet contractors", "jet contractor"],
    "M2M":  ["m2m group", "m2m maroc"],
    "INV":  ["involys", "involys maroc"],
    "S2M":  ["s2m group", "soft mobile maroc", "s2m maroc"],
    "COL":  ["colorado peintures", "colorado maroc", "colorado paints"],
    "AFM":  ["africa middle east resources", "africa middle east"],
    "AGM":  ["afric industries", "afric industries sa"],
    "FNB":  ["fenié brossette", "fenie brossette"],
    "BAL":  ["balima", "société balima"],
    "NEJ":  ["nejma", "groupe nejma"],
    "HAL":  ["haliopolis", "groupe haliopolis"],
    "BMC":  ["brasseries du maroc", "brasseries marocaines"],
    "CAR":  ["cartier saada", "cartier saâda"],
    "AFI":  ["afriquia immobilier", "afriquia immo"],
    "MIC":  ["microdata maroc", "microdata"],
    "MUT":  ["mutuelle centrale maroc", "mutuelle centrale"],
    "ENK":  ["encg maroc", "école nationale de commerce"],
    "EQD":  ["eqdom", "eqdom maroc"],
    "DHO":  ["douja prom", "douja promotion"],
    "PPM":  ["papelera de tetuan", "papelera maroc", "papelera de tétouan"],
    "REB":  ["rebab company", "rebab"],
    "SBS":  ["société de brasseries du maroc"],
    "STK":  ["stroc industrie", "stroc"],
    "UNI":  ["unimer", "unimer maroc"],
    "IBM":  ["industrie biologique maroc", "industrie biologique du maroc"],
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
    """Tag uniquement si le NOM COMPLET de la société apparaît dans le texte.
    Aucune détection par symbole court (3 lettres) — trop de faux positifs."""
    t = text.lower()
    found = []
    for ticker, kws in TICKER_KEYWORDS.items():
        if any(kw in t for kw in kws):
            found.append(ticker)
    return found

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
