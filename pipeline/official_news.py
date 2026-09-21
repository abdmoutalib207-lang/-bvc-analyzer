"""Documents AMMC et provenance des alertes institutionnelles (actualité seule)."""
import hashlib
import html
import re
from datetime import datetime, timezone
from urllib.parse import urljoin, urlparse

AMMC_URL = "https://www.ammc.ma/fr/communiques-presse-emetteurs"
OFFICIAL_DOMAINS = {
    "BVC Officiel": "casablanca-bourse.com", "AMMC": "ammc.ma",
    "Bank Al-Maghrib": "bkam.ma", "HCP": "hcp.ma",
    "MEF": "finances.gov.ma", "Maroclear": "maroclear.com",
    "Attijariwafa IR": "ir.attijariwafabank.com", "Maroc Telecom IR": "iam.ma",
    "LabelVie IR": "labelvie.ma", "Managem IR": "managemgroup.com",
    "Akdital IR": "akdital.ma", "Cosumar IR": "cosumar.co.ma",
    "TGCC IR": "tgcc.ma",
}


def _text(value):
    return " ".join(html.unescape(re.sub(r"<[^>]+>", " ", value)).split())


def parse_ammc(page, fetched_at):
    """L'index atteste une publication ; le contenu du PDF n'est pas validé ici."""
    articles = []
    seen = set()
    for row in re.findall(r'<li\b[^>]*class="[^"]*actualites-row[^"]*"[^>]*>(.*?)</li>', page, re.S):
        title = re.search(r'views-field-title[^>]*>\s*<span[^>]*>(.*?)</span>', row, re.S)
        date = re.search(r'<time\b[^>]*datetime="([^"]+)"', row)
        links = re.findall(r'<a\b[^>]*href="([^"]+)"', row)
        if not title or not date:
            continue
        try:
            published = datetime.fromisoformat(date[1].replace("Z", "+00:00"))
            if published.tzinfo is None or published > datetime.fromisoformat(fetched_at):
                continue
        except ValueError:
            continue
        for link in links:
            url = urljoin(AMMC_URL, html.unescape(link))
            parsed = urlparse(url)
            if parsed.scheme != "https" or parsed.hostname not in {"www.ammc.ma", "ammc.ma"} or not parsed.path.lower().endswith(".pdf"):
                continue
            if url in seen:
                continue
            seen.add(url)
            name = _text(title[1])
            articles.append({
                "id": hashlib.sha256(url.encode()).hexdigest()[:16],
                "title": name, "summary": "Publication de l’émetteur référencée par l’AMMC. Ouvrir le document pour consulter son contenu.",
                "url": url, "source": "AMMC documents", "category": "bvc",
                "date": published.isoformat(), "published_at": published.isoformat(),
                "date_precision": "second", "date_basis": "ammc_index",
                "fetched_at": fetched_at, "first_seen_at": fetched_at,
                "source_url": AMMC_URL, "primary_url": url,
                "publisher": "AMMC — publication de l’émetteur",
                "source_type": "regulator_index", "source_tier": "S1",
                "classification": "PUBLICATION", "validation_status": "listed_officially",
                "document_content_verified": False, "rights": "unknown",
                "usable_for_score": False, "scope": "MAROC", "sentiment": "NEUTRE",
            })
    return articles


def annotate_provenance(article, fetched_at=None):
    """Un relais Google n'est jamais présenté comme un document consulté."""
    article = dict(article)
    article.setdefault("usable_for_score", False)
    if article.get("validation_status") == "listed_officially":
        article["sentiment"] = "NEUTRE"
        article["scope"] = "MAROC"
        return article
    host = (urlparse(article.get("url", "")).hostname or "").lower()
    official = OFFICIAL_DOMAINS.get(article.get("source"))
    article["source_type"] = "search_relay" if host == "news.google.com" else "publisher_feed"
    article["classification"] = "SIGNAL"
    article["validation_status"] = "unverified"
    article["source_tier"] = "S2"
    article["publisher"] = article.get("source", "")
    article["source_url"] = article.get("url", "")
    article["rights"] = "unknown"
    if official:
        article["target_domain"] = official
        article["sentiment"] = "NEUTRE"
    if fetched_at:
        article["fetched_at"] = fetched_at
        article.setdefault("first_seen_at", fetched_at)
    return article
