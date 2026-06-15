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

OUTPUT_PATH  = Path(__file__).parent.parent / "news.json"
MAX_ARTICLES = 200   # articles conservés dans news.json (rolling archive)
ARCHIVE_DAYS = 7     # ancienneté max des articles archivés (jours)
TIMEOUT      = 15

# ── Tickers dont le symbole est un mot commun → ne pas rechercher en brut ─────
# Ces tickers ne seront jamais matchés via leur symbole seul (risque de faux positifs).
# Ils ne sont reconnus QUE via les mots-clés du nom complet ci-dessous.
SKIP_RAW_SYMBOL = {
    "LES",  # "les" = article défini français (présent dans tout texte)
    "CAR",  # "car" = conjonction française + mot anglais générique
    "UNI",  # préfixe courant : université, unique, union…
    "SOT",  # mot français : sot = idiot/fou
    "COL",  # col de montagne, col de chemise, colonel…
    "DAR",  # mot arabe courant (maison)
    "JET",  # jet d'eau, jet privé… trop générique
    "BAL",  # bal populaire, balance…
    "HAL",  # prénom, hal en informatique…
    "MOX",  # trop court / peut apparaître dans mots composés
    "IBM",  # confond avec IBM International (multinationale tech)
    "SMI",  # confond avec Swiss Market Index (indice boursier suisse)
    "ARD",  # chaîne de TV allemande ARD
    "RIS",  # trop court et ambigu
    "MIC",  # prénom, micro, mick…
    "INV",  # "inv" = préfixe investissement trop générique
    "STR",  # "str" préfixe dans string, structure, stratégie…
    "TIM",  # prénom commun
    "SNA",  # trop court
    "SRM",  # trop court
    "SLM",  # trop court
    "MGL",  # trop court
    "FNB",  # trop court
    "ENK",  # trop court
    "PPM",  # ppm = unité de mesure (parts per million)
}

# ── Mapping ticker → noms complets pour le tagging ───────────────────────────
# Règle : uniquement des noms de sociétés complets ou suffisamment distinctifs.
# Ne jamais mettre le symbole court seul (3 lettres) ici — il y a la boucle
# de détection brute ci-dessous pour ça.
TICKER_KEYWORDS = {
    "IAM":  ["maroc telecom", "itissalat al maghrib"],
    "ATW":  ["attijariwafa", "attijari wafa bank"],
    "BCP":  ["banque centrale populaire", "banques populaires", "crédit populaire du maroc"],
    "BOA":  ["bank of africa", "bmce bank of africa"],
    "CIH":  ["cih bank", "crédit immobilier et hôtelier"],
    "CDM":  ["crédit du maroc"],
    "WAF":  ["wafa assurance"],
    "LHM":  ["lafargeholcim maroc", "lafarge holcim maroc", "lafarge maroc"],
    "GAZ":  ["afriquia gaz"],
    "ATL":  ["auto hall", "autohall"],
    "HPS":  ["hightech payment systems", "hightech payment"],
    "LBV":  ["label'vie", "labelvie", "groupe label vie"],
    "LES":  ["lesieur cristal"],
    "TQA":  ["taqa morocco", "jlec", "taqa maroc"],
    "MRL":  ["marsa maroc", "sodep maroc"],
    "TMA":  ["totalenergies marketing maroc", "total energies maroc", "total maroc"],
    "CMT":  ["ciments du maroc", "asment tanger"],
    "MNG":  ["managem", "groupe managem"],
    "SMI":  ["s.m. imiter", "sm imiter", "société métallurgique imiter"],
    "AKD":  ["akdital", "groupe akdital"],
    "ARD":  ["aradei capital"],
    "SAF":  ["saham assurance", "sanlam maroc"],
    "OUL":  ["oulmès", "eaux minérales d'oulmès"],
    "CIM":  ["cimat", "ciments de l'atlas"],
    "CTM":  ["compagnie de transports au maroc", "ctm voyages"],
    "ZLD":  ["zalagh"],
    "SOT":  ["sothema"],
    "MSA":  ["mutandis"],
    "ADI":  ["alliances développement", "alliance développement immobilier", "alliances immobilier"],
    "ADH":  ["addoha", "groupe addoha"],
    "TGCC": ["tgcc", "travaux généraux de construction de casablanca"],
    "CFGB": ["cfg bank"],
    "CASH": ["cash plus"],
    "SGTM": ["sgtm", "société générale de travaux du maroc"],
    "CMGP": ["cmgp group"],
    "VCNE": ["vivo energy maroc"],
    "RIS":  ["risma", "résidences touristiques"],
    "CSR":  ["cosumar"],
    "SNA":  ["sonasid"],
    "SRM":  ["stokvis maroc"],
    "RDS":  ["résidences dar saada"],
    "ALU":  ["aluminium du maroc"],
    "MGL":  ["maghrebail"],
    "DAR":  ["dari couspate"],
    "IMI":  ["immorente invest"],
    "DTT":  ["disty technologies"],
    "DSW":  ["delattre levivier maroc"],
    "MOX":  ["maghreb oxygene"],
    "STR":  ["stradim"],
    "TIM":  ["timar"],
    "SNP":  ["snep maroc"],
    "SLM":  ["salafin"],
    "JET":  ["jet contractors"],
    "M2M":  ["m2m group"],
    "INV":  ["involys"],
    "S2M":  ["s2m group", "soft mobile maroc"],
    "COL":  ["colorado peintures", "colorado maroc"],
    "AFM":  ["africa middle east resources"],
    "AGM":  ["afric industries"],
    "FNB":  ["fenié brossette"],
    "BAL":  ["balima"],
    "NEJ":  ["nejma"],
    "HAL":  ["haliopolis"],
    "BMC":  ["brasseries du maroc"],
    "CAR":  ["cartier saada"],
    "AFI":  ["afriquia immobilier"],
    "MIC":  ["microdata maroc"],
    "MUT":  ["mutuelle centrale maroc"],
    "ENK":  ["encg maroc"],
    "EQD":  ["eqdom"],
    "DHO":  ["douja prom"],
    "PPM":  ["papelera de tetuan", "papelera maroc"],
    "REB":  ["rebab company"],
    "SBS":  ["société de brasseries du maroc"],
    "STK":  ["stroc industrie"],
    "UNI":  ["unimer"],
    "IBM":  ["industrie biologique maroc"],
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
    # 1. Noms complets — source fiable, pas d'ambiguïté
    for ticker, kws in TICKER_KEYWORDS.items():
        if any(kw in t for kw in kws):
            found.append(ticker)
    # 2. Symboles bruts (ex: "ATW", "MNG") avec frontière de mot \b
    #    Exclus : tickers dont le symbole est un mot français/anglais courant
    for ticker in TICKER_KEYWORDS:
        if ticker in SKIP_RAW_SYMBOL:
            continue
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
    # ── BVC / Marchés ────────────────────────────────────────────────────────
    ("https://www.casablanca-bourse.com/bourseweb/Rss-Actualite.aspx",     "BVC Officiel"),
    ("https://www.ammc.ma/fr/rss.xml",                                      "AMMC"),
    ("https://www.leboursier.ma/feed",                                      "Le Boursier"),
    ("https://www.boursenews.ma/rss",                                       "BourseNews"),
    # ── Presse économique marocaine ──────────────────────────────────────────
    ("https://www.medias24.com/rss/bourse.xml",                             "Medias24 Bourse"),
    ("https://www.medias24.com/rss/economie.xml",                           "Medias24 Éco"),
    ("https://www.leconomiste.com/flux-rss/bourse",                         "L'Économiste Bourse"),
    ("https://www.leconomiste.com/flux-rss/actualite",                      "L'Économiste Actu"),
    ("https://fnh.ma/rss",                                                  "Finances News"),
    ("https://lavieeco.com/feed/",                                           "La Vie Éco"),
    ("https://www.challenge.ma/feed/",                                      "Challenge Maroc"),
    ("https://telquel.ma/feed/?cat=economie",                               "Telquel Éco"),
    ("https://lematin.ma/feed/",                                            "Le Matin"),
    ("https://aujourdhui.ma/feed/",                                         "Aujourd'hui le Maroc"),
    ("https://www.lopinion.ma/feed/",                                       "L'Opinion Maroc"),
    ("https://ledesk.ma/feed/",                                             "Le Desk"),
    ("https://ecoactu.ma/feed/",                                            "EcoActu"),
    ("https://maroc-hebdo.press.ma/feed/",                                  "Maroc Hebdo"),
    ("https://fr.hespress.com/category/economie/feed/",                     "Hespress Éco"),
    ("https://www.infomediaire.net/feed/",                                  "Infomediaire"),
    ("https://www.usinenouvelle.com/rss/maroc.xml",                        "Usine Nouvelle Maroc"),
    # ── Finance islamique / HCP / BAM ────────────────────────────────────────
    ("https://www.hcp.ma/rss.xml",                                          "HCP"),
    ("https://www.bkam.ma/rss.xml",                                         "Bank Al-Maghrib"),
    # ── Afrique / Marchés émergents ──────────────────────────────────────────
    ("https://www.agenceecofin.com/flux-rss/maroc",                        "Agence Ecofin Maroc"),
    ("https://www.financialafrik.com/feed/",                                "Financial Afrik"),
    ("https://www.africaintelligence.fr/rss",                              "Africa Intelligence"),
]

def _load_archive() -> tuple[list, set]:
    """Charge les articles existants depuis news.json (rolling archive)."""
    if not OUTPUT_PATH.exists():
        return [], set()
    try:
        data = json.loads(OUTPUT_PATH.read_text(encoding="utf-8"))
        articles = data.get("articles", [])
        cutoff = (datetime.now(timezone.utc) - timedelta(days=ARCHIVE_DAYS)).isoformat()
        fresh = [a for a in articles if a.get("date", "") >= cutoff]
        ids = {a["id"] for a in fresh}
        log.info(f"Archive chargée : {len(fresh)}/{len(articles)} articles (< {ARCHIVE_DAYS}j)")
        return fresh, ids
    except Exception as e:
        log.warning(f"Impossible de charger l'archive : {e}")
        return [], set()


def run():
    from collections import Counter

    # 0. Charger archive existante (rolling)
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

    # Tri par date (plus récent en premier) + troncature rolling
    def _sort_key(a):
        try: return a.get("date", "")
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
    log.info(f"news.json écrit → {OUTPUT_PATH} ({len(all_articles)} articles, rolling {ARCHIVE_DAYS}j)")

    srcs = Counter(a["source"] for a in all_articles)
    for src, n in srcs.most_common(10):
        log.info(f"  {src}: {n}")

    tagged = [a for a in all_articles if a["tickers"]]
    log.info(f"Articles taggés: {len(tagged)}/{len(all_articles)}")

    return output


if __name__ == "__main__":
    run()
