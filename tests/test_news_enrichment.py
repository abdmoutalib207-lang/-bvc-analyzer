"""Tests du passage commun Actualités / Radar BVC.

Le but est de rendre le tri éditorial reproductible sans dépendre d'un service
externe. Les tests portent sur les faits produits (type, importance, horizon),
pas sur une opinion de marché.
"""
from pipeline.enrich_news import enrich_article, enrich_payload


def test_publication_ammc_sur_resultats_est_materielle():
    a = enrich_article({
        "title": "AMMC : publication des résultats annuels de TGCC",
        "summary": "Le résultat net progresse et le chiffre d'affaires atteint un record.",
        "source": "AMMC",
        "category": "bvc",
        "scope": "MAROC",
        "tickers": ["TGCC"],
        "sentiment": "POSITIF",
    })
    assert a["event_type"] == "resultats"
    assert a["source_tier"] == "A"
    assert a["material"] is True
    assert a["importance"] >= 65
    assert a["horizon"] == "IMMEDIAT"


def test_sentiment_fort_peut_sortir_un_neutre_du_brouillard():
    a = enrich_article({
        "title": "Recul et baisse du résultat net",
        "summary": "La marge se dégrade après une forte perte.",
        "source": "Medias24",
        "category": "bvc",
        "scope": "MAROC",
        "tickers": ["ADI"],
        "sentiment": "NEUTRE",
    })
    assert a["sentiment_lexical"] == "NEUTRE"
    assert a["sentiment"] == "NEGATIF"


def test_article_contextuel_non_rattache_reste_secondaire():
    a = enrich_article({
        "title": "Perspectives économiques régionales",
        "summary": "Analyse générale sans société cotée citée.",
        "source": "RFI Économie",
        "category": "economie",
        "scope": "INTL",
        "tickers": [],
        "sentiment": "NEUTRE",
    })
    assert a["material"] is False
    assert a["importance"] < 65


def test_payload_conserve_les_articles_et_publie_un_resume_enrichi():
    p = enrich_payload({
        "updated": "2026-09-18T10:00:00+00:00",
        "articles": [
            {"title": "TGCC remporte un contrat", "summary": "", "source": "BourseNews",
             "category": "bvc", "scope": "MAROC", "tickers": ["TGCC"], "sentiment": "POSITIF"},
            {"title": "Contexte international", "summary": "", "source": "RFI Économie",
             "category": "economie", "scope": "INTL", "tickers": [], "sentiment": "NEUTRE"},
        ],
    })
    assert p["count"] == 2
    assert len(p["articles"]) == 2
    assert p["enrichment"]["version"] == 1
    assert p["enrichment"]["ticker_tagged_count"] == 1
