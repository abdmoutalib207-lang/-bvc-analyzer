#!/usr/bin/env python3
"""
BVC NewsEngine — pipeline/fetch_news.py
Récupère les actualités boursières (BVC, AMMC, Medias24, IDBourse),
tag chaque article par ticker BVC, calcule un sentiment simple,
et écrit news.json pour le terminal React.
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
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8",
}

OUTPUT_PATH = Path(__file__).parent.parent / "news.json"
MAX_ARTICLES = 80
TIMEOUT = 15

# ── Mapping ticker → mots-clés de tagging ────────────────────────────────────
TICKER_KEYWORDS = {
    "IAM":  ["maroc telecom", "iam", "itissalat"],
    "ATW":  ["attijariwafa", "attijari"],
    "BCP":  ["banque populaire", "bcp", "groupe banques populaires"],
    "BOA":  ["bank of africa", "bmce", "boa"],
    "CIH":  ["cih bank", "cih"],
    "CDM":  ["crédit du maroc", "credit du maroc", "cdm"],
    "WAF":  ["wafa assurance", "wafa"],
    "LHM":  ["lafargeholcim", "lafarge holcim", "lhm"],
    "GAZ":  ["afriquia gaz", "afriquia"],
    "ATL":  ["auto hall", "autohall"],
    "HPS":  ["hps", "hightech payment"],
    "LBV":  ["label'vie", "labelvie", "label vie", "lbv"],
    "LES":  ["lesieur cristal", "lesieur"],
    "TQA":  ["taqa morocco", "taqa", "jlec"],
    "MRL":  ["marsa maroc", "mrl"],
    "TMA":  ["totalenergies maroc", "total maroc", "tma"],
    "CMT":  ["ciments du maroc", "asment", "cmt"],
    "MNG":  ["managem", "mng"],
    "SMI":  ["s.m. imiter", "sm imiter", "imiter", "smi"],
    "AKD":  ["akdital", "akd"],
    "ARD":  ["aradei capital", "aradei"],
    "SAF":  ["saham assurance", "saham"],
    "OUL":  ["oulmès", "oulmes"],
    "CIM":  ["cimat", "ciment de l'atlas", "ciments atlas"],
    "CTM":  ["ctm", "compagnie transport maroc"],
    "ZLD":  ["zalagh", "zld"],
    "SOT":  ["sothema", "sot"],
    "MSA":  ["mutandis", "msa"],
    "ADI":  ["alliances développement", "alliances dev", "adi"],
    "ADH":  ["addoha", "adh"],
    "TGCC": ["tgcc", "total gaou côte", "tgc"],
    "CFGB": ["cfg bank", "cfg"],
    "CASH": ["cash plus", "cash+"],
    "SGTM": ["sgtm"],
    "CMGP": ["cmgp group", "cmgp"],
    "VCNE": ["vivo energy", "vicenne", "vcne"],
    "RIS":  ["résidences immobilières", "ris"],
    "CSR":  ["cosumar", "csr"],
    "SNA":  ["sonasid", "sna"],
    "SRM":  ["stokvis", "srm"],
    "RDS":  ["rdsa", "rds"],
    "ALU":  ["aluminium du maroc", "alum"],
    "MGL":  ["maghrebail", "mgl"],
    "DAR":  ["dari couspate", "dari"],
    "IMI":  ["imi", "immobilière"],
    "DTT":  ["disty technologies", "dtt"],
    "DSW":  ["delattre levivier", "dsw"],
    "MOX":  ["maghreb oxygene", "mox"],
    "STR":  ["stradim", "str"],
    "TIM":  ["timar", "tim"],
    "SNP":  ["snep", "snp"],
    "SLM":  ["salafin", "slm"],
    "JET":  ["jet contractors", "jet"],
    "M2M":  ["m2m group", "m2m"],
    "INV":  ["involys", "inv"],
    "S2M":  ["s2m", "soft mobile"],
    "COL":  ["colorado", "col"],
    "AFM":  ["afm", "agro farma"],
    "AGM":  ["afric industries", "agm"],
    "FNB":  ["fenié brossette", "fnb"],
    "BAL":  ["balima", "bal"],
    "NEJ":  ["nejma", "nejmah"],
    "HAL":  ["haliopolis", "hal"],
    "BMC":  ["bmc", "brasseries maroc"],
    "CAR":  ["cartier saada", "car"],
    "AFI":  ["afi", "afriquia"],
    "MIC":  ["microdata", "mic"],
    "MUT":  ["mutuelle centrale", "mut"],
    "ENK":  ["encg", "enk"],
    "EQD":  ["eqdom", "eqd"],
    "DHO":  ["douja prom", "dhom", "dho"],
    "PPM":  ["papelera", "ppm"],
    "REB":  ["rebab company", "reb"],
    "SBS":  ["sbs", "société de brasseries"],
    "STK":  ["stroc industrie", "stk"],
    "UNI":  ["unimer", "uni"],
    "IBM":  ["ibm", "industrie biologique"],
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
    t = text.lower()
    found = []
    for ticker, kws in TICKER_KEYWORDS.items():
        if any(kw in t for kw in kws):
            found.append(ticker)
    # aussi chercher les symboles directement (ex: "ATW", "MNG")
    for ticker in TICKER_KEYWORDS:
        pattern = r'\b' + re.escape(ticker) + r'\b'
        if re.search(pattern, text, re.IGNORECASE) and ticker not in found:
            found.append(ticker)
    return found

def _article_id(url: str, title: str) -> str:
    return hashlib.md5(f"{url}{title}".encode()).hexdigest()[:12]

def _parse_date(raw: str) -> str:
    """Normalise une date RSS vers ISO8601."""
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
    try:
        r = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
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
                "id":      _article_id(link, title),
                "title":   title,
                "summary": re.sub(r"<[^>]+>", "", desc)[:200],
                "url":     link,
                "source":  source_name,
                "date":    _parse_date(date),
                "tickers": _tag_tickers(text),
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
    """Tente plusieurs endpoints Medias24 pour les news."""
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
    """Actualités IDBourse (section news)."""
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
                    "date":      _parse_date(date),
                    "tickers":   _tag_tickers(text),
                    "sentiment": _sentiment(text),
                })
            log.info(f"IDBourse news: {len(articles)} articles")
    except Exception as e:
        log.warning(f"IDBourse news erreur: {e}")
    return articles


# ── Orchestration ─────────────────────────────────────────────────────────────

SOURCES_RSS = [
    ("https://www.casablanca-bourse.com/bourseweb/Rss-Actualite.aspx",     "BVC Officiel"),
    ("https://www.ammc.ma/fr/rss.xml",                                      "AMMC"),
    ("https://www.leboursier.ma/feed",                                      "Le Boursier"),
    ("https://leboursier.ma/feed/",                                         "Le Boursier"),
    ("https://www.medias24.com/rss/bourse.xml",                             "Medias24"),
    ("https://medias24.com/rss/bourse.xml",                                 "Medias24"),
    ("https://www.medias24.com/feed/bourse",                                "Medias24"),
    ("https://www.leconomiste.com/flux-rss/bourse",                         "L'Économiste"),
    ("https://telquel.ma/feed/?cat=economie",                               "Telquel Eco"),
]

def run():
    all_articles = []
    seen_ids = set()

    # 1. RSS feeds
    for url, name in SOURCES_RSS:
        arts = fetch_rss(url, name, max_items=25)
        for a in arts:
            if a["id"] not in seen_ids:
                all_articles.append(a)
                seen_ids.add(a["id"])
        if arts: time.sleep(0.5)

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

    # Tri par date (plus récent en premier) + troncature
    def _sort_key(a):
        try: return a["date"]
        except: return ""
    all_articles.sort(key=_sort_key, reverse=True)
    all_articles = all_articles[:MAX_ARTICLES]

    now = datetime.now(timezone.utc)
    output = {
        "updated":  now.isoformat(),
        "count":    len(all_articles),
        "articles": all_articles,
    }

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    log.info(f"news.json écrit → {OUTPUT_PATH} ({len(all_articles)} articles)")

    # Stats par source
    from collections import Counter
    srcs = Counter(a["source"] for a in all_articles)
    for src, n in srcs.most_common():
        log.info(f"  {src}: {n}")

    tagged = [a for a in all_articles if a["tickers"]]
    log.info(f"Articles taggés: {len(tagged)}/{len(all_articles)}")

    return output


if __name__ == "__main__":
    run()
