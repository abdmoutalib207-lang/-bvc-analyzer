# ============================================================
# BVC PDF & WEB SCRAPER — CDG Capital + BKGR + Boursenews
# Extraction : cours cible, historique fondamental 3-5 ans
# Compatible Google Colab — v2.0
# ============================================================

# ── INSTALLATION (à lancer en 1ère cellule Colab) ──────────
# !pip install requests beautifulsoup4 pdfplumber pandas lxml -q

import requests
import pdfplumber
import re
import json
import time
import os
import pandas as pd
from bs4 import BeautifulSoup
from datetime import datetime
from io import BytesIO

# ── CONFIG ──────────────────────────────────────────────────
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "fr-FR,fr;q=0.9",
    "Accept": "text/html,application/xhtml+xml,*/*;q=0.8",
}

# Sources PDF connues — Notes d'analystes BVC
PDF_SOURCES = [
    ("SGTM", "CDG Capital IPO",
     "https://www.cdgcapital.ma/sites/default/files/publication/2025-12/IPO-SGTM.pdf"),
    ("TGC",  "CDG Capital TGCC",
     "https://www.cdgcapital.ma/sites/default/files/publication/2021-12/Introduction%20en%20Bourse%20du%20groupe%20TGCC.pdf"),
    ("SGTM", "AGR IPO Nov 2025",
     "https://attijaricib.com/sites/default/files/2025-12/IPO%20SGTM-Nov.%202025.pdf"),
]

TICKER_NAMES = {
    "SMI":  ["SMI", "Imiter", "Métallurgique d'Imiter"],
    "MNG":  ["Managem", "MANAGEM"],
    "RIS":  ["Risma", "RISMA"],
    "RDS":  ["Dar Saada", "RDS", "Résidences Dar Saada"],
    "CSR":  ["Cosumar", "COSUMAR"],
    "SOT":  ["Sothema", "SOTHEMA"],
    "ADI":  ["Alliances", "ADI"],
    "MSA":  ["Marsa Maroc", "SODEP"],
    "ADH":  ["Addoha", "ADDOHA"],
    "TGC":  ["TGCC", "TGC", "Travaux Généraux"],
    "CMT":  ["Minière Touissit", "CMT", "Touissit"],
    "SRM":  ["Réalisations Mécaniques", "SRM"],
    "CFGB": ["CFG Bank", "CFGB"],
    "CMGP": ["CMGP", "Agrossem"],
    "VCNE": ["Vicenne", "VCNE"],
    "CASH": ["Cash Plus", "CASH"],
    "SGTM": ["SGTM", "Travaux du Maroc"],
    "AKD":  ["Akdital", "AKD"],
    "SNA":  ["Snep", "SNA"],
}

# ISIN pour Médias24 API
ISIN_MAP = {
    "CMT":  "MA0000011793", "SMI":  "MA0000010068", "CASH": "MA0000012767",
    "MNG":  "MA0000011058", "AKD":  "MA0000012585", "SOT":  "MA0000012502",
    "SGTM": "MA0000012783", "MSA":  "MA0000012312", "CFGB": "MA0000012627",
    "RIS":  "MA0000011462", "ADI":  "MA0000011819", "VCNE": "MA0000012759",
    "CMGP": "MA0000012718", "CSR":  "MA0000012247", "TGCC": "MA0000012528",
    "ADH":  "MA0000011512", "SRM":  "MA0000011595", "SNA":  "MA0000010019",
    "RDS":  "MA0000012239",
}


# ════════════════════════════════════════════════════════════
# MODULE 1 — RECHERCHE AUTOMATIQUE DE PDFS
# ════════════════════════════════════════════════════════════

def rechercher_pdfs_boursenews(ticker: str) -> list:
    """Recherche liens PDF sur boursenews.ma pour un ticker."""
    noms = TICKER_NAMES.get(ticker, [ticker])
    pdfs_trouves = []

    for nom in noms[:2]:
        url_search = f"https://boursenews.ma/recherche?q={nom}+note+recherche+cours+cible"
        try:
            r = requests.get(url_search, headers=HEADERS, timeout=10)
            soup = BeautifulSoup(r.text, "html.parser")
            for a in soup.find_all("a", href=True):
                href = a["href"]
                if href.endswith(".pdf") and any(n.lower() in href.lower() for n in noms):
                    pdfs_trouves.append(href)
        except Exception as e:
            print(f"   Recherche boursenews {ticker}: {e}")
        time.sleep(1)

    return list(set(pdfs_trouves))


def rechercher_pdfs_cdg(ticker: str) -> list:
    """Recherche PDFs sur CDG Capital Bourse."""
    noms = TICKER_NAMES.get(ticker, [ticker])
    pdfs_trouves = []

    base_url = "https://www.cdgcapitalbourse.ma/identite/publication"
    try:
        r = requests.get(base_url, headers=HEADERS, timeout=10)
        soup = BeautifulSoup(r.text, "html.parser")
        for a in soup.find_all("a", href=True):
            href = a["href"]
            texte = a.text.strip().lower()
            if href.endswith(".pdf") and any(
                n.lower() in texte or n.lower() in href.lower() for n in noms
            ):
                if not href.startswith("http"):
                    href = "https://www.cdgcapitalbourse.ma" + href
                pdfs_trouves.append(href)
    except Exception as e:
        print(f"   Recherche CDG {ticker}: {e}")

    return pdfs_trouves


# ════════════════════════════════════════════════════════════
# MODULE 2 — EXTRACTION PDF (pdfplumber)
# ════════════════════════════════════════════════════════════

def telecharger_pdf(url: str) -> bytes:
    """Télécharge un PDF depuis une URL."""
    try:
        r = requests.get(url, headers=HEADERS, timeout=30)
        r.raise_for_status()
        if "pdf" in r.headers.get("Content-Type", "").lower() or url.endswith(".pdf"):
            return r.content
        print(f"   ⚠️ Pas un PDF : {url[:60]}")
        return None
    except Exception as e:
        print(f"   ❌ Téléchargement échoué : {e}")
        return None


def extraire_texte_pdf(pdf_bytes: bytes) -> str:
    """Extrait tout le texte d'un PDF."""
    texte = ""
    try:
        with pdfplumber.open(BytesIO(pdf_bytes)) as pdf:
            for page in pdf.pages:
                t = page.extract_text()
                if t:
                    texte += t + "\n"
    except Exception as e:
        print(f"   ❌ Extraction texte PDF : {e}")
    return texte


def extraire_tableaux_pdf(pdf_bytes: bytes) -> list:
    """Extrait les tableaux structurés d'un PDF → liste de DataFrames."""
    tables = []
    try:
        with pdfplumber.open(BytesIO(pdf_bytes)) as pdf:
            for i, page in enumerate(pdf.pages):
                page_tables = page.extract_tables()
                for t in page_tables:
                    if t and len(t) > 1:
                        try:
                            df = pd.DataFrame(t[1:], columns=t[0])
                            df["_page"] = i + 1
                            tables.append(df)
                        except Exception:
                            pass
    except Exception as e:
        print(f"   ❌ Extraction tableaux PDF : {e}")
    return tables


# ════════════════════════════════════════════════════════════
# MODULE 3 — PARSING DONNÉES FINANCIÈRES
# ════════════════════════════════════════════════════════════

def extraire_cours_cible(texte: str) -> dict:
    """Extrait cours cible, recommandation, upside, analyste depuis texte PDF/HTML."""
    result = {
        "cours_cible": None,
        "recommandation": None,
        "upside_pct": None,
        "analyste": None,
        "date_note": None,
    }

    patterns_cours = [
        r"cours\s+(?:cible|objectif)[^\d]*(\d[\d\s,.]+)\s*(?:DH|MAD|dh)",
        r"(?:target|objectif)\s+(?:price|cours)[^\d]*(\d[\d\s,.]+)\s*(?:DH|MAD|dh)",
        r"valoris\w+[^\d]*(\d[\d\s,.]+)\s*(?:DH|MAD|dh)",
        r"(\d[\d\s,.]+)\s*(?:DH|MAD|dh)[,\s]*(?:soit|représentant|avec)\s+un\s+(?:potentiel|upside)",
    ]
    for pat in patterns_cours:
        m = re.search(pat, texte, re.IGNORECASE)
        if m:
            val = nettoyer_nombre_pdf(m.group(1))
            if val and 10 < val < 100000:
                result["cours_cible"] = val
                break

    for rec in ["Achat", "Acheter", "Buy", "Accumuler", "Accumulate",
                "Conserver", "Neutre", "Hold", "Vendre", "Sell", "Souscrire"]:
        if re.search(r"\b" + rec + r"\b", texte, re.IGNORECASE):
            result["recommandation"] = rec
            break

    m = re.search(r"(?:potentiel|upside|hausse)[^\d]*[+]?\s*(\d+[,.]?\d*)\s*%", texte, re.IGNORECASE)
    if m:
        result["upside_pct"] = nettoyer_nombre_pdf(m.group(1))

    for analyste in ["BKGR", "AGR", "CDG Capital", "CFG Bank",
                     "Sogécapital", "BMCE Capital", "Attijariwafa",
                     "Upline Securities", "Wafabourse", "BMCI Bourse"]:
        if analyste.lower() in texte.lower():
            result["analyste"] = analyste
            break

    m = re.search(r"(\d{1,2})[/\s-](\d{1,2})[/\s-](20\d{2})", texte)
    if m:
        result["date_note"] = f"{m.group(3)}-{m.group(2).zfill(2)}-{m.group(1).zfill(2)}"

    return result


def extraire_historique_fondamental(texte: str, tables: list) -> dict:
    """
    Extrait l'historique fondamental depuis tableaux PDF et texte brut.
    Retourne dict : {"2023": {ca, rn, bpa, dpa, per, ...}, "2024": {...}}
    """
    historique = {}

    # ── 1. Depuis les tableaux ────────────────────────────
    for df in tables:
        if df is None or df.empty:
            continue

        annees_cols = {}
        for col in df.columns:
            if col and re.match(r"20\d{2}[Ee]?", str(col).strip()):
                annee = re.match(r"(20\d{2})", str(col).strip()).group(1)
                annees_cols[col] = annee

        if not annees_cols:
            continue

        for _, row in df.iterrows():
            label = str(row.iloc[0]).lower().strip() if len(row) > 0 else ""
            champ = detecter_champ_pdf(label)
            if not champ:
                continue
            for col_orig, annee in annees_cols.items():
                val = nettoyer_nombre_pdf(str(row.get(col_orig, "")))
                if val is not None:
                    if annee not in historique:
                        historique[annee] = {}
                    historique[annee][champ] = val

    # ── 2. Regex sur texte brut ───────────────────────────
    patterns_histo = [
        (r"CA\s+(?:consolid[ée]?\s+)?(\d{4})[Ee]?\s*[:\-]\s*(\d[\d\s,.]+)\s*(?:MDH|MMAD|Mds)?", "ca_mdh"),
        (r"RNPG\s+(\d{4})[Ee]?\s*[:\-]\s*(\d[\d\s,.]+)\s*(?:MDH|MMAD)?", "rn_mdh"),
        (r"BPA\s+(\d{4})[Ee]?\s*[:\-]\s*(\d[\d\s,.]+)\s*(?:DH|MAD)?", "bpa"),
        (r"DPA\s+(\d{4})[Ee]?\s*[:\-]\s*(\d[\d\s,.]+)\s*(?:DH|MAD)?", "dpa"),
        (r"P[/\-]E\s+(\d{4})[Ee]?\s*[:\-]\s*(\d[\d\s,.]+)\s*[xX]?", "per"),
        (r"marge\s+nette\s+(\d{4})[Ee]?\s*[:\-]\s*(\d[\d\s,.]+)\s*%", "marge_nette_pct"),
        (r"dividende.{0,15}(\d{4})[Ee]?\s*[:\-]\s*(\d[\d\s,.]+)\s*(?:DH|MAD)?", "dpa"),
    ]
    for pattern, champ in patterns_histo:
        for m in re.finditer(pattern, texte, re.IGNORECASE):
            annee = m.group(1)
            val = nettoyer_nombre_pdf(m.group(2))
            if val is not None and 1990 < int(annee) < 2030:
                if annee not in historique:
                    historique[annee] = {}
                if champ not in historique[annee]:
                    historique[annee][champ] = val

    # ── 3. Blocs tableaux "En MDH | 2022 | 2023 | 2024 | 2025E" ──
    lignes = texte.split("\n")
    annees_trouvees = []
    bloc_actif = False

    for ligne in lignes:
        annees_ligne = re.findall(r"20\d{2}[Ee]?", ligne)
        if len(annees_ligne) >= 2:
            annees_trouvees = [re.match(r"(20\d{2})", a).group(1) for a in annees_ligne]
            bloc_actif = True
            continue

        if not bloc_actif or not annees_trouvees:
            continue

        if len(ligne.strip()) < 3:
            bloc_actif = False
            annees_trouvees = []
            continue

        champ = detecter_champ_pdf(ligne.lower())
        if not champ:
            continue

        valeurs = re.findall(r"[-]?\d[\d\s,.]*(?:\.\d+)?", ligne)
        valeurs_clean = [nettoyer_nombre_pdf(v) for v in valeurs if nettoyer_nombre_pdf(v) is not None]

        for j, annee in enumerate(annees_trouvees):
            if j < len(valeurs_clean):
                if annee not in historique:
                    historique[annee] = {}
                if champ not in historique[annee]:
                    historique[annee][champ] = valeurs_clean[j]

    return historique


def extraire_donnees_marche(texte: str) -> dict:
    """Extrait free float, nb actions, capitalisation, ISIN depuis texte."""
    data = {}
    patterns = [
        (r"(?:free.?float|flottant)[^\d]*(\d+[,.]?\d*)\s*%", "free_float_pct"),
        (r"(?:nombre\s+d.actions|capital)[^\d]*([\d\s,.]+)\s*(?:actions|titres)", "nb_actions"),
        (r"(?:capitalisation)[^\d]*([\d\s,.]+)\s*(?:MDH|MMAD|Mds)", "cap_boursiere_mdh"),
        (r"ISIN\s*[:\s]+([A-Z]{2}\d{10})", "isin"),
        (r"(?:cours\s+d.introduction|prix\s+d.émission)[^\d]*(\d[\d\s,.]+)\s*(?:DH|MAD)", "prix_introduction"),
        (r"(?:nombre\s+de\s+titres)[^\d]*([\d\s,.]+)", "nb_titres_total"),
    ]
    for pattern, champ in patterns:
        m = re.search(pattern, texte, re.IGNORECASE)
        if m:
            if champ == "isin":
                data[champ] = m.group(1).strip()
            else:
                val = nettoyer_nombre_pdf(m.group(1))
                if val is not None:
                    data[champ] = val
    return data


# ════════════════════════════════════════════════════════════
# MODULE 4 — HELPERS
# ════════════════════════════════════════════════════════════

def nettoyer_nombre_pdf(texte: str) -> float:
    """Convertit texte → float. Gère formats FR/EN."""
    if not texte:
        return None
    t = str(texte).strip()
    t = re.sub(r"[^\d,.\-]", "", t)
    if not t or t in ["-", ".", ","]:
        return None
    if re.match(r"^\d{1,3}(\.\d{3})+,\d+$", t):
        t = t.replace(".", "").replace(",", ".")
    elif re.match(r"^\d{1,3}(\.\d{3})+$", t):
        t = t.replace(".", "")
    elif "," in t and "." not in t:
        t = t.replace(",", ".")
    try:
        val = float(t)
        return val if val != 0 else None
    except Exception:
        return None


def detecter_champ_pdf(label: str) -> str:
    """Mappe label PDF/HTML → clé JSON standardisée."""
    label = label.lower().strip()
    mapping = [
        (["chiffre d'affaires", "ca ", "revenus", "produits", "turnover"], "ca_mdh"),
        (["résultat net", "rnpg", "bénéfice net", "net income", "résultat net part"], "rn_mdh"),
        (["résultat d'exploitation", "rex ", "ebit "], "rex_mdh"),
        (["ebitda", "ebe ", "excédent brut"], "ebitda_mdh"),
        (["bpa", "bénéfice par action", "earnings per share", "eps "], "bpa"),
        (["dpa", "dividende par action", "dividend per share"], "dpa"),
        (["p/e", "per ", "price.earning", "ratio cours"], "per"),
        (["marge nette", "net margin"], "marge_nette_pct"),
        (["marge ebitda", "marge ebe"], "marge_ebitda_pct"),
        (["marge brute"], "marge_brute_pct"),
        (["dette nette/ebitda", "gearing", "levier"], "dette_nette_ebitda"),
        (["dette nette", "endettement net"], "dette_nette_mdh"),
        (["rendement", "dividend yield", "d/y"], "div_yield_pct"),
        (["roic", "return on invested"], "roic_pct"),
        (["roe", "return on equity"], "roe_pct"),
        (["capex", "investissements"], "capex_mdh"),
        (["free cash flow", "fcf"], "fcf_mdh"),
    ]
    for mots_cles, champ in mapping:
        if any(mc in label for mc in mots_cles):
            return champ
    return None


# ════════════════════════════════════════════════════════════
# MODULE 5 — ORCHESTRATEUR PDF
# ════════════════════════════════════════════════════════════

def analyser_pdf(url_ou_chemin: str, ticker: str = None, source: str = None) -> dict:
    """Analyse complète d'un PDF (URL ou chemin local)."""
    result = {
        "ticker": ticker,
        "source": source or url_ou_chemin,
        "cours_cible": {},
        "historique": {},
        "marche": {},
        "texte_brut_extrait": False,
        "nb_tableaux": 0,
        "erreur": None,
    }

    if url_ou_chemin.startswith("http"):
        print(f"   📥 Téléchargement : {url_ou_chemin[:70]}...")
        pdf_bytes = telecharger_pdf(url_ou_chemin)
    else:
        print(f"   📂 Lecture locale : {url_ou_chemin}")
        try:
            with open(url_ou_chemin, "rb") as f:
                pdf_bytes = f.read()
        except Exception as e:
            result["erreur"] = str(e)
            return result

    if not pdf_bytes:
        result["erreur"] = "PDF non disponible"
        return result

    texte = extraire_texte_pdf(pdf_bytes)
    tables = extraire_tableaux_pdf(pdf_bytes)
    result["texte_brut_extrait"] = len(texte) > 100
    result["nb_tableaux"] = len(tables)

    if not texte:
        result["erreur"] = "PDF vide ou non parsable (scan image ?)"
        return result

    result["cours_cible"] = extraire_cours_cible(texte)
    result["historique"] = extraire_historique_fondamental(texte, tables)
    result["marche"] = extraire_donnees_marche(texte)

    nb_champs_cours = sum(1 for v in result["cours_cible"].values() if v)
    print(f"   ✅ {ticker or '?'} — cours_cible: {nb_champs_cours} champs | "
          f"historique: {len(result['historique'])} années | tableaux: {len(tables)}")
    return result


# ════════════════════════════════════════════════════════════
# MODULE 6 — SCRAPING HTML DES SITES FINANCIERS BVC
# ════════════════════════════════════════════════════════════

def _get_soup(url: str, timeout: int = 12) -> BeautifulSoup | None:
    """GET d'une URL → BeautifulSoup ou None si erreur."""
    try:
        r = requests.get(url, headers=HEADERS, timeout=timeout)
        r.raise_for_status()
        return BeautifulSoup(r.text, "lxml")
    except Exception as e:
        print(f"   ⚠️ {url[:60]} — {e}")
        return None


# ── boursenews.ma ─────────────────────────────────────────

def scraper_boursenews_ticker(ticker: str) -> dict:
    """
    Scrape boursenews.ma pour un ticker :
    - Articles récents avec cours cible mentionné
    - Résultats financiers publiés
    Retourne dict unifié avec cours_cible + historique.
    """
    noms = TICKER_NAMES.get(ticker, [ticker])
    resultats = []

    for nom in noms[:2]:
        url = f"https://boursenews.ma/article/bourse/{nom.lower().replace(' ', '-')}"
        soup = _get_soup(url)
        if soup:
            resultats += _parser_articles_boursenews(soup, ticker)
            time.sleep(1)

        # Recherche full-text
        url_s = f"https://boursenews.ma/?s={nom}"
        soup = _get_soup(url_s)
        if soup:
            for lien in soup.select("article a[href*='/article/']")[:5]:
                art_url = lien.get("href", "")
                if not art_url.startswith("http"):
                    art_url = "https://boursenews.ma" + art_url
                art_soup = _get_soup(art_url)
                if art_soup:
                    resultats += _parser_articles_boursenews(art_soup, ticker)
                    time.sleep(0.8)

    return _fusionner_resultats_web(resultats, ticker, "Boursenews")


def _parser_articles_boursenews(soup: BeautifulSoup, ticker: str) -> list:
    """Parse article boursenews → liste de dicts cours_cible/historique."""
    resultats = []
    # Tout le texte de l'article
    article = soup.find("article") or soup.find("div", class_=re.compile(r"post|entry|content"))
    if not article:
        return resultats

    texte = article.get_text(separator="\n")
    cc = extraire_cours_cible(texte)
    histo = extraire_historique_fondamental(texte, [])
    marche = extraire_donnees_marche(texte)

    if any(v for v in cc.values()) or histo:
        resultats.append({"cours_cible": cc, "historique": histo, "marche": marche})

    return resultats


# ── medias24.com/bourse ───────────────────────────────────

def scraper_medias24_ticker(ticker: str) -> dict:
    """
    Scrape medias24.com/bourse pour un ticker :
    - Page valeur : cours, capitalisation, cours objectif
    - Articles avec résultats financiers
    """
    resultats = []
    noms = TICKER_NAMES.get(ticker, [ticker])

    # Page valeur directe (format medias24)
    for nom in noms[:1]:
        url = f"https://medias24.com/bourse/valeurs/{nom.lower()}.html"
        soup = _get_soup(url)
        if soup:
            res = _parser_page_valeur_medias24(soup, ticker)
            if res:
                resultats.append(res)
            time.sleep(1)

    # Articles récents
    for nom in noms[:2]:
        url_s = f"https://medias24.com/?s={nom}+bourse+résultats"
        soup = _get_soup(url_s)
        if soup:
            for a in soup.select("article h2 a, article h3 a")[:4]:
                art_url = a.get("href", "")
                art_soup = _get_soup(art_url)
                if art_soup:
                    texte = (art_soup.find("article") or art_soup).get_text(separator="\n")
                    cc = extraire_cours_cible(texte)
                    histo = extraire_historique_fondamental(texte, [])
                    if any(v for v in cc.values()) or histo:
                        resultats.append({
                            "cours_cible": cc,
                            "historique": histo,
                            "marche": extraire_donnees_marche(texte),
                        })
                    time.sleep(0.8)

    return _fusionner_resultats_web(resultats, ticker, "Medias24")


def _parser_page_valeur_medias24(soup: BeautifulSoup, ticker: str) -> dict | None:
    """Parse page valeur medias24 → cours objectif, capitalisation, etc."""
    texte = soup.get_text(separator="\n")
    cc = extraire_cours_cible(texte)
    marche = extraire_donnees_marche(texte)

    # Cours objectif spécifique à medias24
    for pat in [
        r"(?:cours\s+objectif|objectif\s+de\s+cours)[^\d]*(\d[\d\s,.]+)",
        r"(?:valeur\s+cible|target)[^\d]*(\d[\d\s,.]+)",
    ]:
        m = re.search(pat, texte, re.IGNORECASE)
        if m:
            val = nettoyer_nombre_pdf(m.group(1))
            if val and 10 < val < 100000:
                cc["cours_cible"] = val
                break

    # Capitalisation boursière depuis tableau récap
    for row in soup.select("tr, .data-row"):
        label = row.get_text().lower()
        if "capitalisation" in label:
            m = re.search(r"(\d[\d\s,.]+)\s*(?:MDH|Mds|MMAD)", row.get_text())
            if m:
                marche["cap_boursiere_mdh"] = nettoyer_nombre_pdf(m.group(1))

    if any(v for v in cc.values()) or marche:
        return {"cours_cible": cc, "historique": {}, "marche": marche}
    return None


# ── leconomiste.com ───────────────────────────────────────

def scraper_leconomiste_ticker(ticker: str) -> dict:
    """
    Scrape leconomiste.com pour un ticker :
    - Articles financiers avec résultats, cours cibles
    """
    noms = TICKER_NAMES.get(ticker, [ticker])
    resultats = []

    for nom in noms[:2]:
        url_s = f"https://www.leconomiste.com/recherche?search={nom}"
        soup = _get_soup(url_s)
        if not soup:
            continue

        liens = []
        for a in soup.select("h2 a, h3 a, .article-title a")[:5]:
            href = a.get("href", "")
            if not href.startswith("http"):
                href = "https://www.leconomiste.com" + href
            if href not in liens:
                liens.append(href)

        for url in liens:
            art_soup = _get_soup(url)
            if not art_soup:
                continue
            texte = (art_soup.find("article") or art_soup).get_text(separator="\n")
            if not any(n.lower() in texte.lower() for n in noms):
                continue
            cc = extraire_cours_cible(texte)
            histo = extraire_historique_fondamental(texte, [])
            if any(v for v in cc.values()) or histo:
                resultats.append({
                    "cours_cible": cc,
                    "historique": histo,
                    "marche": extraire_donnees_marche(texte),
                })
            time.sleep(1)

    return _fusionner_resultats_web(resultats, ticker, "L'Economiste")


# ── wafabourse.ma ──────────────────────────────────────────

def scraper_wafabourse_ticker(ticker: str) -> dict:
    """
    Scrape wafabourse.ma pour un ticker :
    - Page fiche valeur : cours objectif, recommandation, données fondamentales
    """
    resultats = []
    noms = TICKER_NAMES.get(ticker, [ticker])

    # Page fiche valeur
    url = f"https://www.wafabourse.com/bourse/detail/{ticker.lower()}"
    soup = _get_soup(url)
    if soup:
        res = _parser_fiche_wafabourse(soup, ticker)
        if res:
            resultats.append(res)
        time.sleep(1)

    # Essai avec nom complet
    if not resultats and noms:
        url2 = f"https://www.wafabourse.com/bourse/recherche?q={noms[0]}"
        soup2 = _get_soup(url2)
        if soup2:
            premier = soup2.select_one("a[href*='/detail/']")
            if premier:
                href = premier.get("href", "")
                if not href.startswith("http"):
                    href = "https://www.wafabourse.com" + href
                soup3 = _get_soup(href)
                if soup3:
                    res = _parser_fiche_wafabourse(soup3, ticker)
                    if res:
                        resultats.append(res)

    return _fusionner_resultats_web(resultats, ticker, "Wafabourse")


def _parser_fiche_wafabourse(soup: BeautifulSoup, ticker: str) -> dict | None:
    """Parse fiche valeur wafabourse → cours objectif, données fondamentales."""
    texte = soup.get_text(separator="\n")
    cc = extraire_cours_cible(texte)
    marche = extraire_donnees_marche(texte)
    histo = {}

    # Tableau données fondamentales (PE, PB, rendement, BPA)
    for row in soup.select("table tr"):
        cells = [c.get_text(strip=True) for c in row.find_all(["td", "th"])]
        if len(cells) >= 2:
            champ = detecter_champ_pdf(cells[0])
            if champ:
                val = nettoyer_nombre_pdf(cells[1])
                if val:
                    annee = str(datetime.today().year)
                    histo.setdefault(annee, {})[champ] = val

    # Cours objectif dans div/span spécifiques
    for sel in [".cours-objectif", ".target-price", "[data-cours-objectif]"]:
        el = soup.select_one(sel)
        if el:
            val = nettoyer_nombre_pdf(el.get_text())
            if val and 10 < val < 100000:
                cc["cours_cible"] = val
                break

    if any(v for v in cc.values()) or marche or histo:
        return {"cours_cible": cc, "historique": histo, "marche": marche}
    return None


# ── cdgcapital.ma (publications) ──────────────────────────

def scraper_cdg_publications(ticker: str) -> dict:
    """
    Scrape cdgcapital.ma/publications pour un ticker :
    - Liste des notes de recherche HTML
    - Extraction cours cible depuis résumés
    """
    noms = TICKER_NAMES.get(ticker, [ticker])
    resultats = []

    urls_publications = [
        "https://www.cdgcapital.ma/fr/publications/notes-de-recherche",
        "https://www.cdgcapital.ma/fr/publications/flash-resultats",
        "https://www.cdgcapital.ma/fr/publications/revues-de-marche",
    ]

    for base_url in urls_publications:
        soup = _get_soup(base_url)
        if not soup:
            continue

        for a in soup.select("a[href]"):
            texte_lien = a.get_text(strip=True).lower()
            href = a.get("href", "")
            if any(n.lower() in texte_lien or n.lower() in href.lower() for n in noms):
                if href.endswith(".pdf"):
                    # PDF direct
                    if not href.startswith("http"):
                        href = "https://www.cdgcapital.ma" + href
                    pdf_bytes = telecharger_pdf(href)
                    if pdf_bytes:
                        texte = extraire_texte_pdf(pdf_bytes)
                        tables = extraire_tableaux_pdf(pdf_bytes)
                        cc = extraire_cours_cible(texte)
                        histo = extraire_historique_fondamental(texte, tables)
                        if any(v for v in cc.values()) or histo:
                            resultats.append({
                                "cours_cible": cc,
                                "historique": histo,
                                "marche": extraire_donnees_marche(texte),
                            })
                        time.sleep(2)
                elif "/article/" in href or "/publication/" in href:
                    # Page HTML
                    if not href.startswith("http"):
                        href = "https://www.cdgcapital.ma" + href
                    art_soup = _get_soup(href)
                    if art_soup:
                        texte = art_soup.get_text(separator="\n")
                        cc = extraire_cours_cible(texte)
                        histo = extraire_historique_fondamental(texte, [])
                        if any(v for v in cc.values()) or histo:
                            resultats.append({
                                "cours_cible": cc,
                                "historique": histo,
                                "marche": extraire_donnees_marche(texte),
                            })
                    time.sleep(1)

        time.sleep(1)

    return _fusionner_resultats_web(resultats, ticker, "CDG Capital")


# ── Médias24 API (données structurées) ────────────────────

def scraper_medias24_api(ticker: str) -> dict:
    """
    Interroge l'API Médias24 pour récupérer :
    - Données de marché en temps réel
    - Historique de prix
    """
    isin = ISIN_MAP.get(ticker)
    if not isin:
        return {}

    result = {"cours_cible": {}, "historique": {}, "marche": {}}

    # Infos valeur
    url_info = f"https://medias24.com/content/api?method=getStockInfo&ISIN={isin}"
    try:
        r = requests.get(url_info, headers=HEADERS, timeout=10)
        data = r.json()
        info = data.get("result", {})
        if info:
            result["marche"]["cap_boursiere_mdh"] = info.get("marketCap")
            result["marche"]["nb_actions"] = info.get("sharesNumber")
            if info.get("eps"):
                annee = str(datetime.today().year)
                result["historique"].setdefault(annee, {})["bpa"] = info["eps"]
            if info.get("dividendPerShare"):
                annee = str(datetime.today().year)
                result["historique"].setdefault(annee, {})["dpa"] = info["dividendPerShare"]
            if info.get("per"):
                annee = str(datetime.today().year)
                result["historique"].setdefault(annee, {})["per"] = info["per"]
    except Exception as e:
        print(f"   ⚠️ Médias24 API {ticker}: {e}")

    return result


# ── Consolidation ─────────────────────────────────────────

def _fusionner_resultats_web(resultats: list, ticker: str, source: str) -> dict:
    """Consolide plusieurs résultats web en un seul dict."""
    if not resultats:
        return {}

    cours_cibles = []
    historique = {}
    marche = {}

    for r in resultats:
        cc = r.get("cours_cible", {})
        if cc.get("cours_cible"):
            cours_cibles.append({
                "valeur": cc["cours_cible"],
                "recommandation": cc.get("recommandation"),
                "upside_pct": cc.get("upside_pct"),
                "analyste": cc.get("analyste") or source,
                "date": cc.get("date_note"),
                "source": source,
            })

        for annee, champs in r.get("historique", {}).items():
            historique.setdefault(annee, {})
            for champ, val in champs.items():
                if champ not in historique[annee]:
                    historique[annee][champ] = val

        for k, v in r.get("marche", {}).items():
            if k not in marche and v:
                marche[k] = v

    return {
        "ticker": ticker,
        "source_web": source,
        "cours_cibles_web": cours_cibles,
        "historique": historique,
        "marche": marche,
    }


# ════════════════════════════════════════════════════════════
# MODULE 7 — ORCHESTRATEUR PRINCIPAL (PDF + WEB)
# ════════════════════════════════════════════════════════════

def scraper_toutes_sources(
    tickers: list = None,
    output_path: str = "pdf_scraping_results.json",
    activer_web: bool = True,
) -> dict:
    """
    Lance le scraping complet PDF + HTML pour tous les tickers.
    """
    if tickers is None:
        tickers = list(TICKER_NAMES.keys())

    tous_resultats = {}

    # ── PDFs sources connues ──────────────────────────────
    print("\n📚 Analyse des PDFs sources connues...")
    for ticker, source, url in PDF_SOURCES:
        if ticker not in tickers:
            continue
        print(f"\n🔍 {ticker} — {source}")
        result = analyser_pdf(url, ticker, source)
        tous_resultats.setdefault(ticker, []).append(result)
        time.sleep(2)

    # ── PDFs découverts automatiquement ──────────────────
    print("\n🔎 Recherche automatique de PDFs (Boursenews + CDG)...")
    for ticker in tickers:
        print(f"\n🔍 PDFs pour {ticker}...")
        pdfs = rechercher_pdfs_boursenews(ticker) + rechercher_pdfs_cdg(ticker)
        for url in list(set(pdfs))[:3]:
            print(f"   → {url[:70]}")
            result = analyser_pdf(url, ticker, "auto-découvert")
            tous_resultats.setdefault(ticker, []).append(result)
            time.sleep(2)

    if not activer_web:
        _sauvegarder(tous_resultats, output_path)
        return tous_resultats

    # ── Scraping HTML des sites ───────────────────────────
    print("\n🌐 Scraping HTML sites financiers BVC...")
    scrapers_web = [
        ("Boursenews",    scraper_boursenews_ticker),
        ("Medias24",      scraper_medias24_ticker),
        ("Medias24 API",  scraper_medias24_api),
        ("L'Economiste",  scraper_leconomiste_ticker),
        ("Wafabourse",    scraper_wafabourse_ticker),
        ("CDG Capital",   scraper_cdg_publications),
    ]

    for ticker in tickers:
        print(f"\n🌐 Web scraping pour {ticker}...")
        for nom_source, fn in scrapers_web:
            try:
                print(f"   → {nom_source}...")
                data_web = fn(ticker)
                if data_web:
                    tous_resultats.setdefault(ticker, []).append({
                        "ticker": ticker,
                        "source": nom_source,
                        "cours_cible": {"cours_cible": None, "recommandation": None,
                                        "upside_pct": None, "analyste": nom_source,
                                        "date_note": None},
                        "historique": data_web.get("historique", {}),
                        "marche": data_web.get("marche", {}),
                        "_cours_cibles_web": data_web.get("cours_cibles_web", []),
                        "texte_brut_extrait": True,
                        "nb_tableaux": 0,
                        "erreur": None,
                    })
                    # Injecter le premier cours cible trouvé
                    ccs = data_web.get("cours_cibles_web", [])
                    if ccs:
                        tous_resultats[ticker][-1]["cours_cible"]["cours_cible"] = ccs[0]["valeur"]
                        tous_resultats[ticker][-1]["cours_cible"]["recommandation"] = ccs[0].get("recommandation")
                        tous_resultats[ticker][-1]["cours_cible"]["upside_pct"] = ccs[0].get("upside_pct")
            except Exception as e:
                print(f"   ❌ {nom_source} {ticker}: {e}")
            time.sleep(1.5)

    _sauvegarder(tous_resultats, output_path)
    return tous_resultats


def _sauvegarder(data: dict, path: str):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2, default=str)
    print(f"\n✅ Résultats sauvegardés → {path}")


# ════════════════════════════════════════════════════════════
# MODULE 8 — FUSION AVEC fondamentaux.json
# ════════════════════════════════════════════════════════════

def fusionner_avec_fondamentaux(
    fondamentaux_path: str,
    resultats_pdf: dict,
    output_path: str = None,
) -> dict:
    """
    Enrichit fondamentaux.json avec données extraites (PDF + web) :
    - Cours cibles analystes
    - Historique fondamental 3-5 ans
    - Tendances calculées
    """
    with open(fondamentaux_path, "r", encoding="utf-8") as f:
        fond = json.load(f)

    for ticker, analyses in resultats_pdf.items():
        if ticker not in fond:
            print(f"⚠️  {ticker} absent de fondamentaux.json — ignoré")
            continue

        historique_fusionne = {}
        cours_cibles = []

        for analyse in analyses:
            if analyse.get("erreur"):
                continue

            for annee, champs in analyse.get("historique", {}).items():
                historique_fusionne.setdefault(annee, {})
                for champ, val in champs.items():
                    if champ not in historique_fusionne[annee]:
                        historique_fusionne[annee][champ] = val

            cc = analyse.get("cours_cible", {})
            if cc.get("cours_cible"):
                cours_cibles.append({
                    "valeur": cc["cours_cible"],
                    "recommandation": cc.get("recommandation"),
                    "upside_pct": cc.get("upside_pct"),
                    "analyste": cc.get("analyste"),
                    "date": cc.get("date_note"),
                    "source": analyse.get("source"),
                })

            # Cours cibles multiples depuis scraping web
            for extra_cc in analyse.get("_cours_cibles_web", []):
                if extra_cc.get("valeur") and extra_cc not in cours_cibles:
                    cours_cibles.append(extra_cc)

            marche = analyse.get("marche", {})
            if marche.get("free_float_pct"):
                fond[ticker]["free_float"] = marche["free_float_pct"]
            if marche.get("cap_boursiere_mdh"):
                fond[ticker]["cap_boursiere_mdh"] = marche["cap_boursiere_mdh"]

        if historique_fusionne:
            fond[ticker]["historique"] = historique_fusionne
            fond[ticker].update(calculer_tendances_depuis_histo(historique_fusionne))

            # Mise à jour des indicateurs fondamentaux depuis historique
            annees = sorted(historique_fusionne.keys())
            if annees:
                last = historique_fusionne[annees[-1]]
                for champ_histo, champ_fond in [
                    ("per", "per"), ("bpa", "bpa_2026"), ("dpa", "dps_2026"),
                    ("marge_nette_pct", "marge_nette"), ("roic_pct", "roic"),
                    ("dette_nette_ebitda", "dette_nette_ebitda"),
                ]:
                    if champ_histo in last and last[champ_histo]:
                        fond[ticker][champ_fond] = last[champ_histo]

        if cours_cibles:
            fond[ticker]["consensus_analystes"] = cours_cibles
            valeurs = [c["valeur"] for c in cours_cibles if c.get("valeur")]
            if valeurs:
                fond[ticker]["cours_cible_moyen"] = round(sum(valeurs) / len(valeurs), 1)
                # Upside vs dernier cours connu
                prix_actuel = fond[ticker].get("price") or fond[ticker].get("cours_actuel")
                if prix_actuel:
                    fond[ticker]["upside_moyen_pct"] = round(
                        (fond[ticker]["cours_cible_moyen"] / prix_actuel - 1) * 100, 1
                    )

        fond[ticker]["date_maj"] = datetime.today().strftime("%Y-%m-%d")
        print(f"✅ {ticker} enrichi — {len(historique_fusionne)} années | "
              f"{len(cours_cibles)} cours cibles")

    output = output_path or fondamentaux_path.replace(".json", "_enrichi_pdf.json")
    with open(output, "w", encoding="utf-8") as f:
        json.dump(fond, f, ensure_ascii=False, indent=2)
    print(f"\n✅ JSON final enrichi → {output}")
    return fond


def calculer_tendances_depuis_histo(historique: dict) -> dict:
    """Calcule tendances sur 3 dernières années disponibles."""
    annees = sorted([a for a in historique.keys() if re.match(r"20\d{2}$", a)])

    def tendance(champ):
        vals = [(a, historique[a].get(champ)) for a in annees[-3:]]
        vals = [(a, v) for a, v in vals if v is not None]
        if len(vals) < 2:
            return "stable"
        delta = vals[-1][1] - vals[0][1]
        ref = abs(vals[0][1]) if vals[0][1] != 0 else 1
        if delta / ref > 0.05:
            return "hausse"
        elif delta / ref < -0.05:
            return "baisse"
        return "stable"

    return {
        "tendance_roic":  tendance("roic_pct"),
        "tendance_marge": tendance("marge_nette_pct"),
        "tendance_dette": tendance("dette_nette_ebitda"),
    }


# ════════════════════════════════════════════════════════════
# MODULE 9 — RAPPORT DE QUALITÉ
# ════════════════════════════════════════════════════════════

def rapport_pdf(resultats: dict):
    """Affiche récap de ce qui a été extrait par ticker."""
    print("\n" + "=" * 75)
    print(f"{'TICKER':<8} {'COURS_CIBLE':>12} {'RECO':>10} {'HISTO':>6} "
          f"{'TABLEAUX':>9} {'SOURCE'}")
    print("=" * 75)
    for ticker, analyses in resultats.items():
        for analyse in analyses:
            cc = analyse.get("cours_cible", {})
            histo = analyse.get("historique", {})
            err = (analyse.get("erreur") or "—")[:18]
            source_court = (analyse.get("source") or "?")[:22]
            print(f"{ticker:<8} "
                  f"{str(cc.get('cours_cible', '—')):>12} "
                  f"{str(cc.get('recommandation', '—')):>10} "
                  f"{len(histo):>6} ans"
                  f"{analyse.get('nb_tableaux', 0):>8} tab  "
                  f"{source_court}")
    print("=" * 75)


# ════════════════════════════════════════════════════════════
# UTILISATION DANS COLAB
# ════════════════════════════════════════════════════════════

if __name__ == "__main__":

    # ── Option 1 : Analyser un PDF spécifique ─────────────
    result = analyser_pdf(
        url_ou_chemin="https://attijaricib.com/sites/default/files/2025-12/IPO%20SGTM-Nov.%202025.pdf",
        ticker="SGTM",
        source="AGR IPO Nov 2025",
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))

    # ── Option 2 : Scraping web d'un ticker ───────────────
    # data = scraper_boursenews_ticker("SMI")
    # print(json.dumps(data, ensure_ascii=False, indent=2))

    # ── Option 3 : Tous les tickers (PDF + Web) ───────────
    # resultats = scraper_toutes_sources(
    #     tickers=["SMI", "MNG", "CSR", "SGTM"],
    #     output_path="/content/pdf_results.json",
    #     activer_web=True,
    # )
    # rapport_pdf(resultats)

    # ── Option 4 : Fusion avec fondamentaux.json ──────────
    # fond = fusionner_avec_fondamentaux(
    #     fondamentaux_path="/content/fondamentaux.json",
    #     resultats_pdf=resultats,
    #     output_path="/content/fondamentaux_final.json",
    # )
