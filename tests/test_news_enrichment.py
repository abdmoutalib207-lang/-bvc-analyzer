"""Tests du passage commun Actualités / Radar BVC.

Le but est de rendre le tri éditorial reproductible sans dépendre d'un service
externe. Les tests portent sur les faits produits (type, importance, horizon),
pas sur une opinion de marché.
"""
from pipeline.enrich_news import enrich_article, enrich_payload
from pipeline import enrich_news as en


def test_publication_ammc_sur_resultats_est_materielle():
    a = enrich_article({
        "title": "AMMC : publication des résultats annuels de TGCC",
        "summary": "Le résultat net progresse et le chiffre d'affaires atteint un record.",
        "source": "AMMC",
        # ⚠️ La provenance, pas le libellé. La version d'origine se fiait au
        # nom « AMMC » ; le collecteur renvoie « AMMC documents », et le vrai
        # flux tombait donc au rang le plus bas. Ce qui qualifie un dépôt
        # réglementaire, c'est qu'il vient de l'index du régulateur.
        "source_tier": "S1",
        "source_type": "regulator_index",
        "validation_status": "listed_officially",
        "category": "bvc",
        "scope": "MAROC",
        "tickers": ["TGCC"],
        "sentiment": "POSITIF",
    })
    assert a["event_type"] == "resultats"
    # `source_tier` reste celui du collecteur — l'enrichissement ne le réécrit pas.
    assert a["source_tier"] == "S1"
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


# ── LES DEUX DÉFAUTS TROUVÉS EN FAISANT TOURNER L'ENRICHISSEMENT ───────────
#
# ⚠️ Mesurés sur le flux réel du 22/09, pas supposés :
#
#     AMMC documents   S1 (le plus haut)  ->  C (le plus bas)
#     BVC Sociétés     S1                 ->  C
#     source_tier      {S1:14, S2:286}    ->  {A:4, B:125, C:171}
#
# Cause : deux tables de noms écrites à la main contenaient « AMMC » et
# « BVC Officiel », quand le collecteur renvoie « AMMC documents » et
# « BVC Sociétés ». Des noms SUPPOSÉS au lieu des noms OBSERVÉS — la famille
# d'erreurs la plus coûteuse de ce projet.

def _art(**kw):
    base = {"title": "x", "summary": "", "source": "peu importe",
            "category": "bvc", "tickers": [], "scope": "MAROC"}
    base.update(kw)
    return base


def test_un_depot_du_regulateur_pese_le_plus_quel_que_soit_son_libelle():
    """⚠️ LE DÉFAUT CENTRAL. Le libellé ne doit jouer AUCUN rôle : seule
    compte la provenance établie par le collecteur."""
    for libelle in ("AMMC documents", "AMMC", "BVC Sociétés", "n'importe quoi"):
        a = _art(source=libelle, source_tier="S1", source_type="regulator_index",
                 validation_status="listed_officially")
        assert en.poids_source(a) == en.POIDS_REGULATEUR, libelle


def test_les_trois_rangs_se_deduisent_de_la_provenance():
    assert en.poids_source(_art(source_type="regulator_index")) == en.POIDS_REGULATEUR
    assert en.poids_source(_art(source_type="publisher_feed")) == en.POIDS_EDITEUR
    assert en.poids_source(_art(source_type="search_relay")) == en.POIDS_RELAIS


def test_un_seul_marqueur_officiel_suffit():
    """Les trois marqueurs sont posés ensemble par `official_news.py`. Exiger
    les trois rendrait la règle fragile au changement de l'un d'eux."""
    assert en.poids_source(_art(source_tier="S1")) == en.POIDS_REGULATEUR
    assert en.poids_source(
        _art(validation_status="listed_officially")) == en.POIDS_REGULATEUR


def test_le_regulateur_pese_plus_qu_un_relais():
    """La propriété qui était violée : l'ordre des rangs."""
    assert en.POIDS_REGULATEUR > en.POIDS_EDITEUR > en.POIDS_RELAIS


def test_l_enrichissement_ne_reecrit_pas_source_tier():
    """⚠️ `source_tier` appartient au collecteur. L'écraser avec une seconde
    échelle détruisait l'information et faisait cohabiter deux vocabulaires
    pour un même champ — le défaut déjà payé sur les secteurs."""
    a = en.enrich_article(_art(source_tier="S1", source_type="regulator_index"))
    assert a["source_tier"] == "S1"
    b = en.enrich_article(_art(source_tier="S2", source_type="search_relay"))
    assert b["source_tier"] == "S2"


def test_aucune_liste_de_noms_de_sources_ne_subsiste():
    """⚠️ La parade n'est pas de corriger la liste, c'est de ne plus en avoir.
    Ce test rougit si quelqu'un en réintroduit une."""
    assert not hasattr(en, "OFFICIAL")
    assert not hasattr(en, "TRUSTED")
    assert not hasattr(en, "_source_tier")


def test_sur_le_flux_reel_le_regulateur_ne_tombe_jamais_au_rang_le_plus_bas():
    """L'épreuve sur les données publiées, pas sur un bac de test."""
    import json
    from pathlib import Path
    chemin = Path(__file__).resolve().parent.parent / "news.json"
    if not chemin.exists():
        import pytest
        pytest.skip("news.json absent de ce clone")
    articles = json.loads(chemin.read_text(encoding="utf-8")).get("articles") or []
    officiels = [a for a in articles if a.get("source_tier") == "S1"]
    if not officiels:
        import pytest
        pytest.skip("aucun article de source institutionnelle dans ce flux")
    faibles = [a["source"] for a in officiels
               if en.poids_source(a) != en.POIDS_REGULATEUR]
    assert not faibles, (
        f"{len(faibles)} article(s) de source institutionnelle rétrogradés : "
        f"{sorted(set(faibles))}")
