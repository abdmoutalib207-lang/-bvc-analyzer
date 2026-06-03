"""
Collecte des données financières historiques (CA, RN, dette/EBITDA)
Sources : Médias24 scraping articles → casabourse.ma → PDF AMMC (phase 2)
"""
import logging
import random
import re
import time
from datetime import datetime

from bs4 import BeautifulSoup

from .constants import HEADERS_LIST, ISIN_MAP, timeout_session

log = logging.getLogger(__name__)

MED_WEB  = "https://medias24.com"
CSB_BASE = "https://www.casabourse.ma"


def _parse_mdh(text: str) -> float | None:
    """Extrait une valeur MDH depuis du texte (gère K, M, Mds, MDH)."""
    text = text.replace("\xa0", "").replace(" ", "").replace(",", ".")
    m = re.search(r"([+-]?\d[\d.]*)\s*(Mds?|MDH|M|K)?", text, re.IGNORECASE)
    if not m:
        return None
    val = float(m.group(1))
    unit = (m.group(2) or "").upper()
    if unit in ("MDS", "MDS"):
        val *= 1000
    elif unit in ("MDH", "M"):
        pass
    elif unit == "K":
        val /= 1000
    return round(val, 1)


def _extract_financial_table(text: str) -> dict:
    """
    Extrait CA, RN, EBITDA depuis un texte structuré type tableau annuel.
    Supporte les formats : "CA 2025 : 5 200 MDH", tableaux avec années en colonnes.
    """
    result = {"revenue_mdh": {}, "net_income_mdh": {}}

    # Patterns avec année explicite
    patterns = [
        (r"(?:chiffre\s+d.affaires?|CA|revenus?)[^\d]*(20\d{2})[Ee]?\s*[:\-–]\s*([\d\s,.]+)\s*(?:MDH|Mds|M)?", "revenue_mdh"),
        (r"(20\d{2})[Ee]?[^\d](?:CA|chiffre\s+d.affaires?)[^\d]*([\d\s,.]+)\s*(?:MDH|Mds)?", "revenue_mdh"),
        (r"(?:résultat\s+net|RNPG|bénéfice\s+net)[^\d]*(20\d{2})[Ee]?\s*[:\-–]\s*([\d\s,.]+)\s*(?:MDH|Mds|M)?", "net_income_mdh"),
        (r"(20\d{2})[Ee]?[^\d](?:résultat\s+net|RNPG)[^\d]*([\d\s,.]+)\s*(?:MDH|Mds)?", "net_income_mdh"),
    ]

    for pattern, key in patterns:
        for m in re.finditer(pattern, text, re.IGNORECASE):
            year, val_str = m.group(1), m.group(2)
            val = _parse_mdh(val_str)
            if val and 1990 < int(year) < 2030 and val > 0:
                result[key][year] = val

    # Blocs tabulaires "En MDH | 2023 | 2024 | 2025"
    lines = text.split("\n")
    header_years = []
    for i, line in enumerate(lines):
        years = re.findall(r"20\d{2}[Ee]?", line)
        if len(years) >= 2:
            header_years = [re.match(r"(20\d{2})", y).group(1) for y in years]
            # Chercher les lignes suivantes
            for j in range(i + 1, min(i + 20, len(lines))):
                row = lines[j].lower()
                if not row.strip():
                    continue
                key = None
                if any(k in row for k in ["chiffre d", "revenus", " ca ", "turnover"]):
                    key = "revenue_mdh"
                elif any(k in row for k in ["résultat net", "rnpg", "bénéfice"]):
                    key = "net_income_mdh"
                elif any(k in row for k in ["ebitda", "excédent brut"]):
                    key = "ebitda_mdh"

                if key:
                    nums = re.findall(r"[+-]?\d[\d\s,.]*", row)
                    nums_clean = [_parse_mdh(n) for n in nums if _parse_mdh(n)]
                    for k, yr in enumerate(header_years):
                        if k < len(nums_clean) and nums_clean[k]:
                            result.setdefault(key, {})[yr] = nums_clean[k]

    return result


def _fetch_medias24_financials(sym: str) -> dict:
    """Scrape les résultats financiers depuis les articles Médias24."""
    sess = timeout_session()
    noms = {
        "MNG": ["Managem"], "SMI": ["Imiter"], "RIS": ["Risma"],
        "MSA": ["Marsa Maroc"], "CSR": ["Cosumar"], "SOT": ["Sothema"],
        "ADI": ["Alliances"], "ADH": ["Addoha"], "CMT": ["Touissit"],
        "SGTM": ["SGTM"], "TGCC": ["TGCC"], "SRM": ["SRM"],
        "CFGB": ["CFG Bank"], "AKD": ["Akdital"], "CMGP": ["CMGP"],
        "RDS": ["Dar Saada"], "CASH": ["Cash Plus"], "VCNE": ["Vicenne"],
        "SNA": ["Snep"],
    }
    noms_ticker = noms.get(sym, [sym])
    merged = {}

    for nom in noms_ticker[:2]:
        for url in [
            f"{MED_WEB}/?s={nom}+résultats+annuels",
            f"{MED_WEB}/?s={nom}+chiffre+affaires+2025",
        ]:
            try:
                r = sess.get(url, headers=random.choice(HEADERS_LIST), timeout=15)
                r.raise_for_status()
                soup = BeautifulSoup(r.text, "lxml")

                for a in soup.select("article h2 a, article h3 a, .entry-title a")[:5]:
                    href = a.get("href", "")
                    if not href:
                        continue
                    try:
                        art = sess.get(href, headers=random.choice(HEADERS_LIST), timeout=15)
                        art.raise_for_status()
                        art_soup = BeautifulSoup(art.text, "lxml")
                        text = art_soup.get_text(separator="\n")
                        data = _extract_financial_table(text)
                        for key, years_dict in data.items():
                            if years_dict:
                                merged.setdefault(key, {}).update(years_dict)
                    except Exception as e:
                        log.debug(f"  article {href[:50]}: {e}")
                    time.sleep(0.8 + random.random())

            except Exception as e:
                log.debug(f"Médias24 fin {sym}: {e}")
            time.sleep(1.5 + random.random())

        if merged:
            break

    return merged


def _fetch_casabourse_financials(sym: str) -> dict:
    """Scrape données financières depuis casabourse.ma."""
    sess = timeout_session()
    urls = [
        f"https://www.casabourse.ma/valeurs/{sym.lower()}/resultats",
        f"https://www.casabourse.ma/Societe/indicateurs/{sym}",
    ]
    merged = {}
    for url in urls:
        try:
            r = sess.get(url, headers=random.choice(HEADERS_LIST), timeout=15)
            r.raise_for_status()
            text = BeautifulSoup(r.text, "lxml").get_text(separator="\n")
            data = _extract_financial_table(text)
            for key, years_dict in data.items():
                if years_dict:
                    merged.setdefault(key, {}).update(years_dict)
            if merged:
                break
        except Exception as e:
            log.debug(f"casabourse fin {sym}: {e}")
        time.sleep(2 + random.random())
    return merged


def fetch_financials(sym: str) -> dict:
    """
    Collecte CA, RN, EBITDA pour 2023/2024/2025.
    Sources : Médias24 → casabourse.ma
    """
    result = {
        "revenue_mdh":       {},
        "net_income_mdh":    {},
        "ebitda_mdh":        {},
        "net_debt_to_ebitda": None,
        "free_cash_flow_mdh": None,
    }

    med = _fetch_medias24_financials(sym)
    for k in ["revenue_mdh", "net_income_mdh", "ebitda_mdh"]:
        result[k].update(med.get(k, {}))

    if not any(result[k] for k in ["revenue_mdh", "net_income_mdh"]):
        csb = _fetch_casabourse_financials(sym)
        for k in ["revenue_mdh", "net_income_mdh", "ebitda_mdh"]:
            result[k].update(csb.get(k, {}))

    # Nettoyer les dicts vides → None
    for k in ["revenue_mdh", "net_income_mdh", "ebitda_mdh"]:
        if not result[k]:
            result[k] = None

    nb = sum(len(v) for v in [result["revenue_mdh"] or {}, result["net_income_mdh"] or {}])
    log.debug(f"{sym} financials: {nb} entrées récupérées")
    return result
