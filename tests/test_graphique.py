#!/usr/bin/env python3
"""Le graphique — orientation, interruptions, statut de qualité.

⚠️ POURQUOI CES TESTS EXISTENT
L'axe des prix était INVERSÉ : le graphique affichait 176 en haut et 200 en
bas. Aucun test de calcul ne pouvait l'attraper — les nombres étaient justes,
seule leur mise en place était fausse. Le défaut n'est apparu qu'en regardant
l'image produite.

Les tests ci-dessous portent donc sur la GÉOMÉTRIE, pas sur l'arithmétique.
"""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))
sys.path.insert(0, str(RACINE / "pipeline"))

from graphique import (  # noqa: E402
    BORNES_OSCILLATEUR, JOURS_AVANT_RUPTURE, PANNEAU_SEPARE, echelle, segments,
)

Y_BAS, Y_HAUT = 500.0, 150.0          # en SVG, l'axe y descend


# ═══ Orientation — le défaut réellement survenu ════════════════════════════

def test_une_valeur_basse_est_dessinee_EN_BAS():
    """Le défaut exact : les prix bas apparaissaient en HAUT du cadre."""
    f, lo, hi = echelle([10.0, 20.0, 30.0], Y_BAS, Y_HAUT)
    assert f(10.0) > f(30.0), "la valeur basse doit avoir une ordonnée PLUS GRANDE"


def test_l_echelle_reste_dans_le_cadre():
    f, lo, hi = echelle([10.0, 30.0], Y_BAS, Y_HAUT)
    for v in (10.0, 20.0, 30.0):
        assert Y_HAUT <= f(v) <= Y_BAS, v


def test_l_echelle_est_monotone():
    f, _, _ = echelle([5.0, 50.0], Y_BAS, Y_HAUT)
    ys = [f(v) for v in range(5, 51, 5)]
    assert ys == sorted(ys, reverse=True), "monter en valeur doit monter à l'écran"


def test_une_serie_plate_ne_divise_pas_par_zero():
    f, lo, hi = echelle([42.0] * 10, Y_BAS, Y_HAUT)
    assert Y_HAUT <= f(42.0) <= Y_BAS


def test_une_serie_vide_ne_plante_pas():
    f, lo, hi = echelle([None, None], Y_BAS, Y_HAUT)
    assert Y_HAUT <= f(1.0) <= Y_BAS


def test_les_valeurs_absentes_sont_ignorees_pas_comptees_pour_zero():
    """Un None traité comme 0 écraserait toute l'échelle vers le bas."""
    _, lo, hi = echelle([100.0, None, 110.0], Y_BAS, Y_HAUT)
    assert lo > 50.0, f"borne basse {lo} : un None a été lu comme zéro"


# ═══ Interruptions — un trou n'est jamais enjambé ══════════════════════════

def pts(jours, ys=None):
    ys = ys if ys is not None else [1.0] * len(jours)
    return [{"jour": date.fromisoformat(j), "y": y} for j, y in zip(jours, ys)]


def test_un_trou_long_coupe_le_trait():
    """Relier deux points séparés d'un mois dessine une tendance inexistante."""
    s = segments(pts(["2026-06-01", "2026-06-02", "2026-07-15", "2026-07-16"]),
                 JOURS_AVANT_RUPTURE)
    assert len(s) == 2, "le trait doit être rompu en deux segments"
    assert len(s[0]) == 2 and len(s[1]) == 2


def test_un_week_end_ordinaire_ne_coupe_pas():
    """Vendredi → lundi : trois jours, c'est normal, le trait continue."""
    s = segments(pts(["2026-06-05", "2026-06-08", "2026-06-09"]),
                 JOURS_AVANT_RUPTURE)
    assert len(s) == 1


def test_une_valeur_absente_coupe_aussi_le_trait():
    s = segments(pts(["2026-06-01", "2026-06-02", "2026-06-03", "2026-06-04"],
                     [1.0, None, 3.0, 4.0]), JOURS_AVANT_RUPTURE)
    assert len(s) == 2
    assert [p["y"] for p in s[0]] == [1.0]
    assert [p["y"] for p in s[1]] == [3.0, 4.0]


def test_un_point_isole_ne_produit_pas_de_trait():
    s = segments(pts(["2026-06-01", "2026-08-01"]), JOURS_AVANT_RUPTURE)
    assert all(len(seg) == 1 for seg in s)


# ═══ Oscillateurs — échelle propre, jamais celle des prix ══════════════════

def test_le_rsi_a_son_propre_panneau():
    """Sur l'échelle d'un titre à 200 DH, un RSI de 0 à 100 serait écrasé en bas
    du cadre et se lirait comme un prix."""
    assert "rsi_wilder" in PANNEAU_SEPARE
    assert BORNES_OSCILLATEUR["rsi_wilder"][:2] == (0.0, 100.0)


def test_les_reperes_du_rsi_sont_dans_ses_bornes():
    lo, hi, reperes = BORNES_OSCILLATEUR["rsi_wilder"]
    assert all(lo < r < hi for r in reperes)


def test_une_moyenne_mobile_partage_l_echelle_des_prix():
    """Elle EST un prix : lui donner un panneau séparé serait trompeur."""
    assert "sma" not in PANNEAU_SEPARE and "ema" not in PANNEAU_SEPARE


# ═══ La page produite porte son statut ════════════════════════════════════

LOT2 = RACINE / "datasets" / "lot2"


@pytest.mark.parametrize("fichier", ["ADH_sma_20.html", "CSR_rsi_wilder_14.html"])
def test_la_page_affiche_son_statut_exploratoire(fichier):
    """⚠️ Un exploratoire qu'on ne distingue pas d'un publiable sera lu comme
    publiable. Le statut doit être dans la page, pas dans un fichier annexe."""
    p = LOT2 / fichier
    if not p.exists():
        pytest.skip(f"{fichier} non généré — lancer pipeline/graphique.py")
    html = p.read_text(encoding="utf-8")
    assert "RÉSULTAT EXPLORATOIRE" in html
    for mot in ("signal officiel", "probabilité", "performance"):
        assert mot in html, mot


@pytest.mark.parametrize("fichier", ["ADH_sma_20.html", "CSR_rsi_wilder_14.html"])
def test_la_page_ne_charge_rien_depuis_l_exterieur(fichier):
    """Elle doit s'ouvrir hors ligne et ne parler à personne."""
    p = LOT2 / fichier
    if not p.exists():
        pytest.skip(f"{fichier} non généré")
    html = p.read_text(encoding="utf-8")
    for interdit in ("http://", "https://", "<script", "src=", "@import"):
        assert interdit not in html, interdit


@pytest.mark.parametrize("fichier", ["ADH_sma_20.html", "CSR_rsi_wilder_14.html"])
def test_la_page_annonce_ses_interruptions(fichier):
    p = LOT2 / fichier
    if not p.exists():
        pytest.skip(f"{fichier} non généré")
    html = p.read_text(encoding="utf-8")
    assert "écart" in html.lower() and "calendaire" in html.lower()
    # ⚠️ Précision demandée : une coupure du TRAIT n'est pas une coupure du CALCUL.
    assert "le calcul ne l'est pas" in html
    # ⚠️ Précision demandée : le seuil ne voit pas toutes les séances manquantes.
    assert "pas toutes les séances manquantes" in html
    # ⚠️ Précision demandée : « clôtures absentes » porte sur les lignes REÇUES.
    assert "parmi les lignes reçues" in html.lower()


def test_la_page_ne_promet_aucune_performance():
    p = LOT2 / "ADH_sma_20.html"
    if not p.exists():
        pytest.skip("non généré")
    html = p.read_text(encoding="utf-8")
    assert "Aucune performance, aucun rendement" in html
