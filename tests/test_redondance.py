#!/usr/bin/env python3
"""Mesurer la redondance, et ne pas la supposer.

⚠️ LA FAUTE SYMÉTRIQUE
──────────────────────
La critique reçue le 24/09 disait : « quatre indicateurs qui disent tous
baissier ne valent pas quatre votes ». Le raisonnement est exact en général, et
la tentation est alors de retirer trois indicateurs sur quatre.

Ce serait une faute symétrique. **L'ADX ne mesure pas la direction, il mesure
la force d'une tendance** — un ADX élevé accompagne aussi bien une hausse
franche qu'une baisse franche. Mesuré sur nos propres séries le 24/09 :

    stoch_k ~ stoch_d   +0,940        rsi ~ adx    +0,021
    rsi     ~ stoch_k   +0,801        macd ~ adx   +0,182

Le RSI et les deux stochastiques forment un groupe. L'ADX est indépendant, au
sens statistique et pas seulement au sens théorique. Un module qui les
fondrait tous rendrait un chiffre juste et une conclusion fausse.

⚠️ Aucun attendu n'est calculé par le code testé : les corrélations des cas
construits valent 1, −1 ou 0 par construction.
"""

from __future__ import annotations

import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))
sys.path.insert(0, str(RACINE / "pipeline"))

from redondance import (  # noqa: E402
    INDICATEURS, MIN_TITRES, SEUIL_REDONDANCE, correlation, mesurer,
)


def _flux(n=30, **series):
    """n titres portant les six indicateurs ; `series` impose les valeurs."""
    out = []
    for i in range(n):
        t = {"symbol": f"T{i}"}
        for k in INDICATEURS:
            v = series.get(k)
            t[k] = v(i) if callable(v) else (i if v is None else v)
        out.append(t)
    return out


# ── Le coefficient lui-même ────────────────────────────────────────────────

def test_deux_series_identiques_donnent_un():
    assert correlation([1, 2, 3, 4, 5], [1, 2, 3, 4, 5]) == 1.0


def test_deux_series_opposees_donnent_moins_un():
    assert correlation([1, 2, 3, 4, 5], [5, 4, 3, 2, 1]) == -1.0


def test_une_serie_constante_ne_donne_pas_zero():
    """⚠️ Une constante n'a pas une corrélation NULLE : elle n'en a aucune.
    Rendre 0.0 ferait passer une absence de mesure pour une indépendance
    mesurée — et l'indépendance est justement ce qu'on cherche à établir."""
    assert correlation([1, 2, 3, 4], [7, 7, 7, 7]) is None


def test_un_echantillon_trop_court_ne_donne_rien():
    assert correlation([1, 2], [1, 2]) is None


# ── ⚠️ Ne pas conclure sur un échantillon mince ────────────────────────────

def test_sous_le_seuil_de_titres_rien_n_est_mesure():
    r = mesurer(_flux(n=MIN_TITRES - 1))
    assert r["mesurable"] is False
    assert "correlations" not in r


def test_au_seuil_la_mesure_se_fait():
    assert mesurer(_flux(n=MIN_TITRES))["mesurable"] is True


def test_un_titre_incomplet_ne_compte_pas():
    """⚠️ L'alignement est la condition d'une corrélation lisible : comparer
    des échantillons différents pour chaque paire rendrait les coefficients
    incomparables entre eux."""
    f = _flux(n=MIN_TITRES + 5)
    for t in f[:5]:
        t.pop("adx")
    assert mesurer(f)["titres_complets"] == MIN_TITRES


# ── Ce que la mesure doit conclure ─────────────────────────────────────────

def test_deux_indicateurs_identiques_sont_groupes():
    f = _flux(n=30, rsi=lambda i: i, stoch_k=lambda i: i,
              stoch_d=lambda i: i * 7 + 3,  # même ordre → corrélation 1
              macd=lambda i: (-1) ** i, macd_hist=lambda i: i % 5,
              adx=lambda i: (i * 13) % 29)
    r = mesurer(f)
    groupe = next(g for g in r["groupes_redondants"] if "rsi" in g)
    assert {"rsi", "stoch_k", "stoch_d"} <= set(groupe)


def test_un_groupe_ne_compte_que_pour_un_indicateur():
    """Le point entier du module : six lignes publiées, moins d'information."""
    f = _flux(n=30, rsi=lambda i: i, stoch_k=lambda i: i, stoch_d=lambda i: i,
              macd=lambda i: (i * 11) % 23, macd_hist=lambda i: (i * 5) % 17,
              adx=lambda i: (i * 13) % 29)
    r = mesurer(f)
    assert r["indicateurs_declares"] == 6
    assert r["indicateurs_distincts"] < 6


def test_des_indicateurs_independants_ne_sont_pas_groupes():
    """⚠️ LE TEST QUI PROTÈGE DE LA FAUTE SYMÉTRIQUE. Sans lui, un module qui
    déclarerait tout redondant passerait — et on retirerait du score un
    indicateur qui apporte une information réelle."""
    f = _flux(n=30, rsi=lambda i: i,
              stoch_k=lambda i: (i * 7) % 11, stoch_d=lambda i: (i * 3) % 13,
              macd=lambda i: (i * 5) % 17, macd_hist=lambda i: (i * 11) % 19,
              adx=lambda i: (i * 13) % 23)
    r = mesurer(f)
    assert r["indicateurs_distincts"] >= 4, (
        f"des séries construites indépendantes sont déclarées redondantes : "
        f"{r['groupes_redondants']}")


def test_une_correlation_negative_forte_compte_aussi():
    """Deux indicateurs opposés portent la même information, au signe près.
    Ne regarder que les corrélations positives en manquerait la moitié."""
    f = _flux(n=30, rsi=lambda i: i, stoch_k=lambda i: -i,
              stoch_d=lambda i: (i * 7) % 11, macd=lambda i: (i * 5) % 17,
              macd_hist=lambda i: (i * 11) % 19, adx=lambda i: (i * 13) % 23)
    r = mesurer(f)
    assert any({"rsi", "stoch_k"} <= set(g) for g in r["groupes_redondants"])


def test_le_seuil_est_haut_a_dessein():
    """0,8 laisse de la place à des mesures parentes sans les confondre. Plus
    bas, des indicateurs qui se complètent seraient déclarés redondants."""
    assert 0.7 <= SEUIL_REDONDANCE <= 0.95


# ── ⚠️ R8 : rien n'est retiré du score ─────────────────────────────────────

def test_le_module_ne_touche_a_aucun_score():
    """Il MESURE et publie. Corriger la redondance dans le calcul déplacerait
    la note de tous les titres — ce que R8 interdit sans backtesting."""
    import ast
    arbre = ast.parse((RACINE / "pipeline" / "redondance.py")
                      .read_text(encoding="utf-8"))
    for n in ast.walk(arbre):
        if isinstance(n, ast.Constant) and isinstance(n.value, str):
            assert n.value not in {"v53", "bvc", "poids", "score_tech"}, (
                f"le module manipule « {n.value} » — il ne doit que mesurer")


def test_le_flux_n_est_pas_modifie():
    import copy
    f = _flux(n=MIN_TITRES + 2)
    avant = copy.deepcopy(f)
    mesurer(f)
    assert f == avant


# ── Le flux publié ─────────────────────────────────────────────────────────

def test_sur_le_flux_publie_l_adx_reste_independant_du_rsi():
    """⚠️ Le relevé du 24/09 donne r = 0,021 entre le RSI et l'ADX. Si cette
    valeur montait un jour au-delà du seuil, la composition du pilier technique
    devrait être rediscutée — et ce test est l'endroit où on l'apprendrait."""
    import json
    import pytest
    chemin = RACINE / "data.json"
    if not chemin.exists():
        pytest.skip("data.json absent de ce clone")
    t = json.loads(chemin.read_text(encoding="utf-8")).get("tickers") or []
    r = mesurer(t)
    if not r.get("mesurable"):
        pytest.skip("pas assez de titres complets dans ce flux")
    paire = r["correlations"].get("rsi~adx")
    assert paire is not None
    assert abs(paire) < SEUIL_REDONDANCE, (
        f"le RSI et l'ADX sont devenus redondants (r = {paire}) — la "
        f"composition du pilier technique est à rediscuter")
