#!/usr/bin/env python3
"""
BVC Annual Report Analyzer — pipeline/fetch_annual_reports.py
Télécharge les rapports annuels (PDF) des sociétés cotées BVC depuis :
  - AMMC (agrément de l'Autorité Marocaine des Marchés de Capitaux)
  - CDG Capital, Attijariwafa CIB, BMCE Capital, CFG Research (notes d'analystes)
  - Boursenews.ma (résumés et rapports de résultats)
  - IR pages des sociétés (rapports d'activité)

Extrait les données clés via Claude API :
  PER, Forward PER, ROIC, WACC, croissance BPA/CA, dette/EBITDA,
  marge nette, cash conversion, dividende, catalyseurs, risques.

Met à jour fondamentaux.json avec les nouvelles données.

Usage:
  python pipeline/fetch_annual_reports.py --ticker MNG
  python pipeline/fetch_annual_reports.py --all
  python pipeline/fetch_annual_reports.py --ticker IAM --pdf-url https://...

Nécessite: ANTHROPIC_API_KEY dans l'environnement
"""

import argparse
import json
import logging
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from io import BytesIO
from urllib.parse import urljoin, urlparse

for pkg in ["requests", "anthropic"]:
    try:
        __import__(pkg)
    except ImportError:
        import subprocess
        subprocess.run([sys.executable, "-m", "pip", "install", pkg, "-q"], check=True)

import requests
import anthropic

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)-8s | %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger("AnnualReports")

ROOT          = Path(__file__).parent.parent
FOND_PATH     = ROOT / "fondamentaux.json"
REPORTS_CACHE = ROOT / "pipeline" / "reports_cache"
REPORTS_CACHE.mkdir(parents=True, exist_ok=True)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept-Language": "fr-FR,fr;q=0.9",
}

# ── Sources PDF par ticker ────────────────────────────────────────────────────

PDF_SOURCES = {
    # Notes d'introduction / IPO
    "SGTM": [
        "https://www.cdgcapital.ma/sites/default/files/publication/2025-12/IPO-SGTM.pdf",
        "https://attijaricib.com/sites/default/files/2025-12/IPO%20SGTM-Nov.%202025.pdf",
    ],
    "TGCC": [
        "https://www.cdgcapital.ma/sites/default/files/publication/2021-12/Introduction%20en%20Bourse%20du%20groupe%20TGCC.pdf",
    ],
    "AKD": [
        "https://www.cdgcapital.ma/sites/default/files/publication/2022-12/IPO-Akdital.pdf",
    ],
    "CFGB": [
        "https://www.cdgcapital.ma/sites/default/files/publication/2022-06/Note-CFGBank.pdf",
    ],
}

# Noms de sociétés pour recherche boursenews
COMPANY_NAMES = {
    "IAM":  ["Maroc Telecom", "Itissalat"],
    "ATW":  ["Attijariwafa"],
    "BCP":  ["Banque Populaire", "BCP"],
    "BOA":  ["Bank of Africa", "BMCE"],
    "CIH":  ["CIH Bank"],
    "CDM":  ["Crédit du Maroc"],
    "WAF":  ["Wafa Assurance"],
    "LHM":  ["LafargeHolcim", "Lafarge Maroc"],
    "GAZ":  ["Afriquia Gaz"],
    "ATL":  ["Auto Hall"],
    "HPS":  ["HPS"],
    "LBV":  ["Label Vie"],
    "LES":  ["Lesieur Cristal"],
    "TQA":  ["Taqa Morocco", "JLEC"],
    "MRL":  ["Marsa Maroc"],
    "TMA":  ["Total Maroc", "TotalEnergies"],
    "CMT":  ["Compagnie Minière Touissit", "CMT"],
    "MNG":  ["Managem"],
    "SMI":  ["SM Imiter", "Métallurgique Imiter"],
    "AKD":  ["Akdital"],
    "CSR":  ["Cosumar"],
    "ADH":  ["Addoha"],
    "ADI":  ["Alliances Développement"],
    "RIS":  ["Risma"],
    "MSA":  ["Mutandis"],
    "TGCC": ["TGCC", "Travaux Généraux Construction"],
    "CFGB": ["CFG Bank"],
    "CASH": ["Cash Plus"],
    "SGTM": ["SGTM"],
    "CMGP": ["CMGP"],
    "VCNE": ["Vivo Energy"],
    "ARD":  ["Aradei Capital"],
    "SAF":  ["Saham Assurance"],
    "OUL":  ["Oulmès"],
    "IMI":  ["Immorente"],
    "CTM":  ["CTM"],
}


def search_boursenews_pdfs(ticker: str) -> list:
    """Recherche des PDFs de résultats sur boursenews.ma."""
    noms = COMPANY_NAMES.get(ticker, [ticker])
    pdfs = []
    for nom in noms[:2]:
        url = f"https://www.boursenews.ma/recherche?q={nom.replace(' ','+')}+resultats"
        try:
            r = requests.get(url, headers=HEADERS, timeout=10)
            for href in re.findall(r'href=["\']([^"\']+\.pdf)["\']', r.text, re.IGNORECASE):
                if not href.startswith("http"):
                    href = urljoin("https://www.boursenews.ma", href)
                if any(n.lower().split()[0] in href.lower() for n in noms):
                    pdfs.append(href)
        except Exception as e:
            log.debug(f"boursenews search {ticker}: {e}")
        time.sleep(0.5)
    return list(set(pdfs))


def download_pdf(url: str, ticker: str) -> bytes | None:
    """Télécharge un PDF et le met en cache."""
    cache_file = REPORTS_CACHE / f"{ticker}_{urlparse(url).path.split('/')[-1]}"
    if cache_file.exists() and cache_file.stat().st_size > 10_000:
        log.info(f"  Cache hit: {cache_file.name}")
        return cache_file.read_bytes()
    try:
        r = requests.get(url, headers=HEADERS, timeout=30, allow_redirects=True)
        r.raise_for_status()
        if len(r.content) < 5_000:
            return None
        cache_file.write_bytes(r.content)
        log.info(f"  Téléchargé: {url} ({len(r.content)//1024} KB)")
        return r.content
    except Exception as e:
        log.warning(f"  Téléchargement échoué {url}: {e}")
        return None


def extract_with_claude(ticker: str, pdf_content: bytes, pdf_url: str) -> dict | None:
    """
    Envoie le PDF à Claude API et extrait les données fondamentales clés.
    Utilise claude-opus-4-8 avec vision PDF.
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        log.error("ANTHROPIC_API_KEY manquant — impossible d'analyser le PDF")
        return None

    client = anthropic.Anthropic(api_key=api_key)

    prompt = f"""Tu es un analyste financier expert en valeurs marocaines cotées à la Bourse de Casablanca (BVC).

Analyse ce rapport financier pour le ticker {ticker} et extrais UNIQUEMENT les données suivantes en JSON strict.
Si une donnée n'est pas disponible, mets null. Ne calcule pas ce qui n'est pas explicitement dans le document.

Réponds UNIQUEMENT avec ce JSON (pas de texte avant ou après) :
{{
  "secteur": "secteur d'activité",
  "per": <PER actuel ou nul>,
  "forward_per": <PER forward N+1 ou nul>,
  "croissance_ca": <croissance CA % sur 1 an ou nul>,
  "croissance_bpa": <croissance BPA % sur 1 an ou nul>,
  "dette_nette_ebitda": <ratio dette nette/EBITDA ou nul>,
  "roic": <ROIC % ou nul>,
  "wacc": <WACC % estimé ou nul, sinon null>,
  "marge_nette": <marge nette % ou nul>,
  "cash_conversion": <taux de conversion du résultat en cash % ou nul>,
  "div_yield": <rendement dividende % ou nul>,
  "bpa_2025": <BPA estimé 2025 en DH ou nul>,
  "bpa_2026": <BPA estimé 2026 en DH ou nul>,
  "dps_2025": <dividende par action estimé 2025 en DH ou nul>,
  "dps_2026": <dividende par action estimé 2026 en DH ou nul>,
  "momentum_fondamental": "très positif | positif | stable | en redressement | négatif",
  "rerating": <true si potentiel de rerating, false sinon>,
  "catalyseur": "résumé des principaux catalyseurs en 1-2 phrases",
  "risque": "résumé des principaux risques en 1-2 phrases",
  "source": "{pdf_url}",
  "date_maj": "{datetime.now(timezone.utc).strftime('%Y-%m-%d')}"
}}"""

    try:
        import base64
        pdf_b64 = base64.standard_b64encode(pdf_content).decode("utf-8")
        msg = client.messages.create(
            model="claude-opus-4-8",
            max_tokens=2000,
            messages=[{
                "role": "user",
                "content": [
                    {
                        "type": "document",
                        "source": {
                            "type": "base64",
                            "media_type": "application/pdf",
                            "data": pdf_b64,
                        },
                    },
                    {"type": "text", "text": prompt},
                ],
            }],
        )
        raw = msg.content[0].text.strip()
        # Extraire le JSON si entouré de texte parasite
        m = re.search(r"\{.*\}", raw, re.DOTALL)
        if m:
            return json.loads(m.group())
        return json.loads(raw)
    except json.JSONDecodeError as e:
        log.warning(f"  JSON invalide depuis Claude: {e}")
        return None
    except Exception as e:
        log.warning(f"  Claude API erreur: {e}")
        return None


def update_fondamentaux(ticker: str, new_data: dict) -> bool:
    """Merge les nouvelles données dans fondamentaux.json."""
    try:
        existing = json.loads(FOND_PATH.read_text(encoding="utf-8")) if FOND_PATH.exists() else {}
        current = existing.get(ticker, {})
        # Merge : ne remplacer que les champs non-null
        for k, v in new_data.items():
            if v is not None:
                current[k] = v
        existing[ticker] = current
        FOND_PATH.write_text(json.dumps(existing, ensure_ascii=False, indent=2), encoding="utf-8")
        log.info(f"  fondamentaux.json mis à jour pour {ticker}")
        return True
    except Exception as e:
        log.error(f"  Écriture fondamentaux.json: {e}")
        return False


def analyze_ticker(ticker: str, pdf_url: str = None) -> bool:
    """Analyse complète d'un ticker : recherche PDF → extraction → mise à jour."""
    log.info(f"\n{'='*50}")
    log.info(f"Analyse : {ticker}")

    # 1. Trouver les PDFs
    urls = []
    if pdf_url:
        urls = [pdf_url]
    else:
        urls = PDF_SOURCES.get(ticker, [])
        if not urls:
            urls = search_boursenews_pdfs(ticker)

    if not urls:
        log.warning(f"  Aucun PDF trouvé pour {ticker}")
        return False

    # 2. Télécharger et analyser le premier PDF disponible
    for url in urls[:2]:
        pdf_bytes = download_pdf(url, ticker)
        if not pdf_bytes:
            continue
        log.info(f"  Analyse Claude en cours...")
        extracted = extract_with_claude(ticker, pdf_bytes, url)
        if extracted:
            log.info(f"  Données extraites: {json.dumps({k:v for k,v in extracted.items() if k not in ('catalyseur','risque','source')}, ensure_ascii=False)}")
            return update_fondamentaux(ticker, extracted)
        time.sleep(2)

    log.warning(f"  Extraction échouée pour tous les PDFs de {ticker}")
    return False


def run_all(tickers: list = None):
    """Analyse tous les tickers avec PDFs disponibles."""
    targets = tickers or list({**PDF_SOURCES, **COMPANY_NAMES}.keys())
    ok = 0
    for sym in targets:
        if analyze_ticker(sym):
            ok += 1
        time.sleep(3)   # éviter le rate-limiting Claude
    log.info(f"\n✅ {ok}/{len(targets)} tickers mis à jour dans fondamentaux.json")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="BVC Annual Report Analyzer")
    parser.add_argument("--ticker",  type=str, help="Ticker spécifique (ex: MNG)")
    parser.add_argument("--pdf-url", type=str, help="URL PDF directe")
    parser.add_argument("--all",     action="store_true", help="Analyser tous les tickers")
    args = parser.parse_args()

    if args.ticker:
        analyze_ticker(args.ticker, args.pdf_url)
    elif args.all:
        run_all()
    else:
        parser.print_help()
