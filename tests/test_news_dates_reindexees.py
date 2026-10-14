"""Le flux Google News `site:casablanca-bourse.com` est retiré (14/10/2026) :
son pubDate est la date de réindexation, et des avis de 2022-2023 sortaient
datés du jour sous l'étiquette « BVC Officiel »."""
from pathlib import Path

SRC = (Path(__file__).resolve().parent.parent / "pipeline" / "fetch_news.py").read_text(encoding="utf-8")


def test_le_flux_reindexe_n_est_plus_collecte():
    from pipeline.fetch_news import SOURCES_RSS
    assert not [u for u, nom, *_ in SOURCES_RSS if "casablanca-bourse.com" in u and "news.google" in u]


def test_l_archive_les_ecarte():
    assert 'a.get("source") == "BVC Officiel" and "news.google.com" in' in SRC
