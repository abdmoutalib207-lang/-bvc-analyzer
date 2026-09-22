#!/usr/bin/env python3
"""Le sentiment d'actualité entre dans le pilier NLP — sous conditions.

⚠️ POURQUOI DES CONDITIONS, ET NON UN SIMPLE BRANCHEMENT
────────────────────────────────────────────────────────
Mesuré le 22/09 sur 300 articles :

    rattachés à un titre                    72
    dont PORTANT un sentiment                8   sur 6 titres seulement
    dépôts AMMC rattachés                   37   sentiment NEUTRE par
                                                 construction

Les dépôts réglementaires sont la meilleure matière — ils nomment l'émetteur —
mais nous lisons l'INDEX et jamais le PDF, donc `annotate_provenance()` leur
impose un sentiment neutre. Nous savons que Sonasid a publié ses résultats ;
nous ne savons pas s'ils sont bons.

Brancher tel quel aurait fait monter six titres arbitraires — **tous les huit
articles porteurs étaient positifs** — et n'aurait rien changé pour les
soixante-quatorze autres. Ce n'est pas un signal, c'est un biais.

D'où deux garde-fous que ce fichier défend :

  1. un SEUIL DE PREUVE : une seule manchette ne déplace pas un score ;
  2. une INFLUENCE BORNÉE : ±0,10 sur `smart`, l'ordre de grandeur de la table
     existante. Au-delà, l'entrée neuve écraserait l'ancienne et changerait DE
     FAIT le poids du pilier — ce que R8 interdit sans backtesting.

⚠️ R8 N'EST PAS TOUCHÉE : aucune pondération ne bouge. On remplit une entrée
creuse, on ne redistribue pas les poids.
"""

from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))
sys.path.insert(0, str(RACINE / "pipeline"))

import news_sentiment as ns  # noqa: E402

MAINTENANT = datetime(2026, 9, 22, 12, 0, tzinfo=timezone.utc)


def _a(ticker="SNA", sentiment="POSITIF", jours=1, importance=50, titre="x"):
    return {"title": titre, "tickers": [ticker], "sentiment": sentiment,
            "importance": importance,
            "date": (MAINTENANT - timedelta(days=jours)).isoformat()}


# ── Le seuil de preuve ─────────────────────────────────────────────────────

def test_une_seule_manchette_ne_deplace_rien():
    """⚠️ LA GARDE CENTRALE. Sans elle, un titre gagnait un demi-point parce
    qu'un journal a écrit « hausse » une fois."""
    m = ns.sentiment_par_titre([_a()], MAINTENANT)
    assert m["SNA"]["n"] == 1
    assert ns.contribution(m["SNA"]) == 0.0


def test_deux_articles_concordants_font_bouger():
    m = ns.sentiment_par_titre([_a(), _a(titre="y")], MAINTENANT)
    assert m["SNA"]["n"] == 2
    assert ns.contribution(m["SNA"]) > 0


def test_un_titre_sans_actualite_ne_recoit_rien():
    assert ns.contribution(None) == 0.0
    assert ns.contribution({}) == 0.0


# ── L'influence bornée ─────────────────────────────────────────────────────

def test_la_contribution_ne_depasse_jamais_le_plafond():
    """⚠️ Vingt articles unanimes ne valent pas plus que le plafond. Sans
    cela, une vague de presse changerait de fait le poids du pilier."""
    beaucoup = [_a(titre=str(i), importance=100) for i in range(20)]
    m = ns.sentiment_par_titre(beaucoup, MAINTENANT)
    assert m["SNA"]["n"] == 20
    assert abs(ns.contribution(m["SNA"])) <= ns.PLAFOND + 1e-9


@pytest.mark.parametrize("sens,signe", [("POSITIF", 1), ("NEGATIF", -1)])
def test_le_plafond_vaut_dans_les_deux_sens(sens, signe):
    m = ns.sentiment_par_titre([_a(sentiment=sens, titre=str(i))
                                for i in range(10)], MAINTENANT)
    c = ns.contribution(m["SNA"])
    assert abs(c) <= ns.PLAFOND + 1e-9
    assert c * signe > 0


def test_le_plafond_reste_dans_l_ordre_de_grandeur_de_la_table():
    """La table existante va de −0,36 à +0,085. Un plafond plus grand ferait
    du sentiment d'actualité le pilier à lui seul."""
    assert 0 < ns.PLAFOND <= 0.15


# ── Ce que le module mesure ────────────────────────────────────────────────

def test_les_articles_neutres_ne_comptent_pas():
    """Un article neutre n'est pas une demi-voix : il n'en est pas une.
    ⚠️ Les 37 dépôts AMMC rattachés sont neutres par construction — les
    compter comme des voix noierait le peu de signal existant."""
    m = ns.sentiment_par_titre([_a(sentiment="NEUTRE"),
                                _a(sentiment="NEUTRE", titre="y")], MAINTENANT)
    assert m == {}


def test_les_avis_opposes_se_compensent():
    m = ns.sentiment_par_titre([_a(sentiment="POSITIF"),
                                _a(sentiment="NEGATIF", titre="y")], MAINTENANT)
    assert m["SNA"]["n"] == 2
    assert abs(m["SNA"]["sent"]) < 1e-9
    assert ns.contribution(m["SNA"]) == 0.0


def test_un_article_important_pese_plus_qu_un_entrefilet():
    fort = ns.sentiment_par_titre(
        [_a(importance=100), _a(sentiment="NEGATIF", importance=0, titre="y")],
        MAINTENANT)
    assert fort["SNA"]["sent"] > 0, "l'article matériel devrait l'emporter"


def test_aucun_article_ne_pese_zero():
    """Sinon le seuil de preuve deviendrait illusoire : deux articles sans
    importance déclarée compteraient pour rien tout en franchissant le seuil."""
    assert ns._poids_article({"importance": 0}) > 0
    assert ns._poids_article({}) > 0


def test_un_article_trop_ancien_est_ignore():
    m = ns.sentiment_par_titre([_a(jours=ns.FENETRE_JOURS + 5),
                                _a(jours=ns.FENETRE_JOURS + 6, titre="y")],
                               MAINTENANT)
    assert m == {}


def test_un_article_peut_porter_plusieurs_titres():
    a = _a()
    a["tickers"] = ["SNA", "STK"]
    m = ns.sentiment_par_titre([a, dict(a, title="y")], MAINTENANT)
    assert m["SNA"]["n"] == m["STK"]["n"] == 2


# ── La robustesse : le moteur ne doit jamais tomber là-dessus ──────────────

def test_un_flux_absent_laisse_le_moteur_inchange(tmp_path):
    """⚠️ Une entrée neuve ne doit jamais pouvoir empêcher la publication."""
    assert ns.charger(tmp_path / "rien.json") == {}


def test_un_flux_illisible_laisse_le_moteur_inchange(tmp_path):
    f = tmp_path / "casse.json"
    f.write_text("{ceci n'est pas du json", encoding="utf-8")
    assert ns.charger(f) == {}


def test_un_article_malforme_ne_fait_pas_tomber_le_calcul():
    m = ns.sentiment_par_titre(
        [{"sentiment": "POSITIF"}, {"tickers": ["SNA"]}, None, _a(), _a(titre="y")],
        MAINTENANT)
    assert m["SNA"]["n"] == 2


# ── Le branchement, sur le chemin réel ─────────────────────────────────────

def test_le_pilier_utilise_bien_l_apport():
    """⚠️ Une fonction juste qui n'est appelée nulle part ne change rien."""
    source = (RACINE / "update_data.py").read_text(encoding="utf-8")
    assert "_apport_actualites(ticker)" in source
    assert "smart = max(-1.0, min(1.0, sent[\"smart\"] + apport_news))" in source
    assert "score_nlp = (smart + 1) * 5" in source


def test_les_ponderations_ne_sont_pas_touchees():
    """⚠️ R8. Le branchement remplit une entrée ; il ne redistribue pas les
    poids. Ce test rougit si quelqu'un croit « améliorer » le pilier en
    changeant son poids par la même occasion."""
    source = (RACINE / "update_data.py").read_text(encoding="utf-8")
    assert 'w["technique"]' in source
    assert 'w["fondamental"]' in source
    assert 'w["comportemental"]' in source
    # la formule du socle doit rester une somme pondérée des trois piliers
    assert "score_nlp  * w[\"comportemental\"]" in source


def test_les_deux_entrees_du_pilier_sont_publiees():
    """⚠️ Sans elles, `nlp` serait une valeur composite indécomposable : devant
    un score, impossible de dire ce qui vient du corpus et ce qui vient de
    l'actualité. Ma première version les calculait sans les propager jusqu'à
    `data.json` — elles sortaient à `None`."""
    source = (RACINE / "update_data.py").read_text(encoding="utf-8")
    assert '"nlp_corpus": v53.get("nlp_corpus")' in source
    assert '"nlp_news":   v53.get("nlp_news")' in source


def test_le_flux_publie_porte_les_deux_entrees():
    import json
    chemin = RACINE / "data.json"
    if not chemin.exists():
        pytest.skip("data.json absent de ce clone")
    lignes = json.loads(chemin.read_text(encoding="utf-8")).get("tickers") or []
    if not lignes:
        pytest.skip("data.json vide")
    manquants = [r["symbol"] for r in lignes if "nlp_news" not in r]
    assert not manquants, (
        f"{len(manquants)} titre(s) sans `nlp_news` — le pilier agit sans "
        f"dire ce qu'il doit à l'actualité : {manquants[:5]}")
