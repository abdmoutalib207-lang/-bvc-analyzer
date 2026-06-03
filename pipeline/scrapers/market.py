"""
Collecte des données de marché BVC — cours, volume, variation
Sources : IDBourse (batch) → Médias24 API → casablanca-bourse.com
"""
import logging
import random
import re
import time

import requests
from bs4 import BeautifulSoup

from .constants import HEADERS_LIST, ISIN_MAP, IDB_NAME_MAP, PROXY, timeout_session

log = logging.getLogger(__name__)

IDB_API   = "https://www.idbourse.com/api/proxy/get_all_data"
MED_BASE  = "https://medias24.com/content/api"
CSB_BASE  = "https://www.casabourse.ma"


# ── Cache global IDBourse (une seule requête pour tous les tickers) ────────────
_IDB_CACHE: dict = {}
_IDB_TS: float = 0.0
_IDB_TTL: float = 120.0  # 2 min


def _get_idb_batch() -> dict:
    """Récupère tous les cours IDBourse en une requête, avec cache."""
    global _IDB_CACHE, _IDB_TS
    if time.time() - _IDB_TS < _IDB_TTL and _IDB_CACHE:
        return _IDB_CACHE

    sess = timeout_session()
    for url in [IDB_API, f"{PROXY}{IDB_API}"]:
        try:
            r = sess.get(url, headers=random.choice(HEADERS_LIST), timeout=15)
            r.raise_for_status()
            data = r.json()
            if isinstance(data, list) and len(data) > 5:
                out = {}
                for d in data:
                    if not d.get("name") or not d.get("dernier_cours"):
                        continue
                    name = d["name"].upper()
                    sym = IDB_NAME_MAP.get(name, name)
                    out[sym] = {
                        "price":      float(d["dernier_cours"]),
                        "open":       float(d["ouverture"])    if d.get("ouverture")    else None,
                        "high":       float(d["plus_haut"])    if d.get("plus_haut")    else None,
                        "low":        float(d["plus_bas"])     if d.get("plus_bas")     else None,
                        "volume":     float(d["volume"])       if d.get("volume")       else None,
                        "variation_pct": float(d["variation"]) if d.get("variation") is not None else 0.0,
                        "market_cap_mdh": float(d["capitalisation"]) / 1e6 if d.get("capitalisation") else None,
                        "_source": "IDBourse",
                    }
                _IDB_CACHE = out
                _IDB_TS = time.time()
                log.info(f"IDBourse batch: {len(out)} tickers chargés")
                return out
        except Exception as e:
            log.debug(f"IDBourse {url[:50]}: {e}")
        time.sleep(1 + random.random())

    return {}


def _fetch_medias24_quote(sym: str) -> dict | None:
    """Quote individuelle via Médias24 API."""
    isin = ISIN_MAP.get(sym)
    if not isin:
        return None
    sess = timeout_session()
    for url in [
        f"{MED_BASE}?method=getStockInfo&ISIN={isin}",
        f"{PROXY}{MED_BASE}?method=getStockInfo&ISIN={isin}",
    ]:
        try:
            r = sess.get(url, headers=random.choice(HEADERS_LIST), timeout=15)
            r.raise_for_status()
            info = r.json().get("result", {})
            if not info:
                continue
            return {
                "price":      float(info.get("currentPrice") or info.get("cours") or 0) or None,
                "open":       float(info.get("open") or 0) or None,
                "high":       float(info.get("high") or 0) or None,
                "low":        float(info.get("low") or 0) or None,
                "volume":     float(info.get("volume") or 0) or None,
                "variation_pct": float(info.get("variation") or 0),
                "market_cap_mdh": float(info.get("marketCap") or 0) / 1e6 or None,
                "_source": "Médias24",
            }
        except Exception as e:
            log.debug(f"Médias24 quote {sym}: {e}")
        time.sleep(0.5 + random.random())
    return None


def _fetch_casabourse(sym: str) -> dict | None:
    """Scraping fiche valeur casabourse.ma."""
    sess = timeout_session()
    urls = [
        f"{CSB_BASE}/valeurs/{sym.lower()}",
        f"{CSB_BASE}/Societe/cours/{sym}",
    ]
    for url in urls:
        try:
            r = sess.get(url, headers=random.choice(HEADERS_LIST), timeout=15)
            r.raise_for_status()
            soup = BeautifulSoup(r.text, "lxml")
            text = soup.get_text(separator=" ")

            price = _extract_number(text, r"(?:dernier\s+cours|cours)[^\d]*(\d[\d\s,.]+)")
            chg   = _extract_number(text, r"(?:variation)[^\d\-]*([+-]?\d[\d,.]+)\s*%")
            vol   = _extract_number(text, r"(?:volume)[^\d]*(\d[\d\s,.]+)")
            cap   = _extract_number(text, r"(?:capitalisation)[^\d]*(\d[\d\s,.]+)\s*(?:MDH|Mds)?")

            if price and price > 0:
                return {
                    "price": price, "open": None, "high": None, "low": None,
                    "volume": vol, "variation_pct": chg or 0.0,
                    "market_cap_mdh": cap,
                    "_source": "casabourse.ma",
                }
        except Exception as e:
            log.debug(f"casabourse.ma {sym}: {e}")
        time.sleep(1 + random.random())
    return None


def _extract_number(text: str, pattern: str) -> float | None:
    m = re.search(pattern, text, re.IGNORECASE)
    if not m:
        return None
    raw = m.group(1).replace(" ", "").replace(",", ".")
    try:
        return float(raw)
    except ValueError:
        return None


def fetch_market_data(sym: str) -> dict | None:
    """
    Chaîne de fallback pour les données de marché :
    IDBourse (batch) → Médias24 → casabourse.ma
    """
    # 1. IDBourse (batch — le plus rapide)
    batch = _get_idb_batch()
    if sym in batch and batch[sym].get("price"):
        log.debug(f"{sym} market ← IDBourse")
        return batch[sym]

    # 2. Médias24 quote individuelle
    time.sleep(1 + random.random())
    med = _fetch_medias24_quote(sym)
    if med and med.get("price"):
        log.debug(f"{sym} market ← Médias24")
        return med

    # 3. casabourse.ma
    time.sleep(2 + random.random())
    csb = _fetch_casabourse(sym)
    if csb and csb.get("price"):
        log.debug(f"{sym} market ← casabourse.ma")
        return csb

    log.warning(f"{sym} market: toutes sources échouées")
    return None
