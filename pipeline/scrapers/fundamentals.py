"""
Collecte des ratios fondamentaux
Sources : casabourse.ma → Zonebourse.com → stockanalysis.com
"""
import logging
import random
import re
import time

from bs4 import BeautifulSoup

from .constants import HEADERS_LIST, ISIN_MAP, timeout_session

log = logging.getLogger(__name__)

CSB_BASE  = "https://www.casabourse.ma"
ZB_BASE   = "https://www.zonebourse.com"
SA_BASE   = "https://stockanalysis.com"
MED_BASE  = "https://medias24.com/content/api"


def _extract(text: str, pattern: str, mult: float = 1.0) -> float | None:
    m = re.search(pattern, text, re.IGNORECASE)
    if not m:
        return None
    raw = m.group(1).replace("\xa0", "").replace(" ", "").replace(",", ".")
    try:
        return round(float(raw) * mult, 4)
    except ValueError:
        return None


def _fetch_casabourse_fund(sym: str) -> dict:
    """Scrape PER, BPA, P/B, dividende depuis casabourse.ma."""
    sess = timeout_session()
    result = {}
    urls = [
        f"{CSB_BASE}/valeurs/{sym.lower()}",
        f"{CSB_BASE}/Societe/cours/{sym}",
        f"{CSB_BASE}/valeurs/fiche/{sym}",
    ]
    for url in urls:
        try:
            r = sess.get(url, headers=random.choice(HEADERS_LIST), timeout=15)
            r.raise_for_status()
            soup = BeautifulSoup(r.text, "lxml")
            text = soup.get_text(separator=" ")

            # PER
            per = _extract(text, r"P[/.]E[^\d]*(\d[\d,.]+)")
            if per:
                result["pe_ratio_ttm"] = per

            # P/Book
            pb = _extract(text, r"P[/.]B(?:ook)?[^\d]*(\d[\d,.]+)")
            if pb:
                result["pb_ratio"] = pb

            # BPA / EPS
            bpa = _extract(text, r"BPA[^\d-]*([+-]?\d[\d,.]+)")
            if bpa:
                result["eps_ttm"] = bpa

            # Dividende par action
            dpa = _extract(text, r"(?:dividende?|DPA)[^\d]*(\d[\d,.]+)\s*(?:DH|MAD)?")
            if dpa:
                result["dividend_per_share"] = dpa

            # Rendement dividende
            yld = _extract(text, r"rendement[^\d]*(\d[\d,.]+)\s*%")
            if yld:
                result["dividend_yield"] = yld

            # Capitalisation boursière
            cap = _extract(text, r"capitalisation[^\d]*(\d[\d\s,.]+)\s*(?:MDH|Mds|M)")
            if cap:
                result["market_cap_mdh"] = cap

            if result:
                result["_source"] = "casabourse.ma"
                return result

        except Exception as e:
            log.debug(f"casabourse.ma fund {sym}: {e}")
        time.sleep(1.5 + random.random())

    return result


def _fetch_zonebourse(sym: str) -> dict:
    """Scrape Zonebourse.com pour ratios fondamentaux."""
    sess = timeout_session()
    result = {}
    search_urls = [
        f"{ZB_BASE}/bourse/cours/{sym}-MAROC/",
        f"{ZB_BASE}/recherche/?q={sym}&market=MAR",
    ]
    for url in search_urls:
        try:
            r = sess.get(url, headers=random.choice(HEADERS_LIST), timeout=15)
            r.raise_for_status()
            soup = BeautifulSoup(r.text, "lxml")

            # Tableau ratios
            for row in soup.select("tr, .ratio-row"):
                cells = [c.get_text(strip=True) for c in row.find_all(["td", "th"])]
                if len(cells) < 2:
                    continue
                label = cells[0].lower()
                val_text = cells[-1] if len(cells) > 1 else ""

                def parse_val(s):
                    s = s.replace(",", ".").replace("\xa0", "")
                    m = re.search(r"[+-]?\d[\d.]*", s)
                    return float(m.group()) if m else None

                if "p/e" in label or "per" in label:
                    v = parse_val(val_text)
                    if v and 0 < v < 500:
                        result["pe_ratio_ttm"] = v
                elif "p/b" in label or "p/bvpa" in label:
                    v = parse_val(val_text)
                    if v and 0 < v < 100:
                        result["pb_ratio"] = v
                elif "bpa" in label or "eps" in label:
                    v = parse_val(val_text)
                    if v:
                        result["eps_ttm"] = v
                elif "dividende" in label and "action" in label:
                    v = parse_val(val_text)
                    if v and v > 0:
                        result["dividend_per_share"] = v
                elif "rendement" in label:
                    v = parse_val(val_text)
                    if v and 0 < v < 50:
                        result["dividend_yield"] = v

            if result:
                result["_source"] = "Zonebourse"
                return result

        except Exception as e:
            log.debug(f"Zonebourse {sym}: {e}")
        time.sleep(2 + random.random())

    return result


def _fetch_medias24_fund(sym: str) -> dict:
    """Récupère fundamentaux via API Médias24 (getStockInfo)."""
    isin = ISIN_MAP.get(sym)
    if not isin:
        return {}
    sess = timeout_session()
    try:
        r = sess.get(
            f"{MED_BASE}?method=getStockInfo&ISIN={isin}",
            headers=random.choice(HEADERS_LIST), timeout=15,
        )
        r.raise_for_status()
        info = r.json().get("result", {})
        if not info:
            return {}
        result = {}
        if info.get("per"):
            result["pe_ratio_ttm"] = float(info["per"])
        if info.get("eps"):
            result["eps_ttm"] = float(info["eps"])
        if info.get("dividendPerShare"):
            result["dividend_per_share"] = float(info["dividendPerShare"])
        if info.get("dividendYield"):
            result["dividend_yield"] = float(info["dividendYield"])
        if info.get("marketCap"):
            result["market_cap_mdh"] = float(info["marketCap"]) / 1e6
        if result:
            result["_source"] = "Médias24 API"
        return result
    except Exception as e:
        log.debug(f"Médias24 fund {sym}: {e}")
        return {}


def fetch_fundamentals(sym: str) -> dict | None:
    """
    Chaîne de fallback pour les fondamentaux :
    casabourse.ma → Médias24 API → Zonebourse
    Fusionne les résultats de plusieurs sources.
    """
    merged = {}

    # Médias24 API — le plus fiable structurellement
    med = _fetch_medias24_fund(sym)
    merged.update(med)
    time.sleep(1 + random.random())

    # casabourse.ma — complète
    if len(merged) < 3:
        csb = _fetch_casabourse_fund(sym)
        for k, v in csb.items():
            if k not in merged or merged[k] is None:
                merged[k] = v
        time.sleep(1.5 + random.random())

    # Zonebourse — complète si encore vide
    if len(merged) < 2:
        zb = _fetch_zonebourse(sym)
        for k, v in zb.items():
            if k not in merged or merged[k] is None:
                merged[k] = v

    if not merged:
        log.warning(f"{sym} fundamentals: toutes sources échouées")
        return None

    merged.setdefault("_source", "multi")
    log.debug(f"{sym} fundamentals ← {merged.get('_source')} ({len(merged)} champs)")
    return merged
