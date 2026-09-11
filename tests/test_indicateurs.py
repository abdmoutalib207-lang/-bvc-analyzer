#!/usr/bin/env python3
"""Socle mathématique du lot 2 — attendus établis INDÉPENDAMMENT du code.

COMMENT LES ATTENDUS SONT OBTENUS
─────────────────────────────────
    « Sur des séries de contrôle dont les résultats attendus sont établis
      indépendamment. »  — revue externe

Chaque attendu ci-dessous est soit calculé à la main et l'arithmétique est
ÉCRITE dans le test, soit déduit de la définition de l'indicateur (un cas
limite : que vaut le RSI quand il n'y a aucune baisse ?). Aucun n'est produit
en appelant la fonction testée.

⚠️ LES SÉRIES CONSTRUITES ICI NE SONT PAS DES DONNÉES DE MARCHÉ.
Elles portent le préfixe `SERIE_CONSTRUITE_` et ne doivent jamais réapparaître
comme historique dans un résultat de performance. Un test vérifie qu'aucune ne
se trouve sous `datasets/`.
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))
sys.path.insert(0, str(RACINE / "pipeline"))

from indicateurs import (  # noqa: E402
    PREFIXE_SERIE_CONSTRUITE, atr, bollinger, ema, macd, obv, rsi_wilder, sma,
)

# ── Séries de contrôle, toutes fabriquées ──────────────────────────────────
SERIE_CONSTRUITE_RAMPE = [1.0, 2.0, 3.0, 4.0, 5.0]
SERIE_CONSTRUITE_PAIRS = [2.0, 4.0, 6.0, 8.0, 10.0]
SERIE_CONSTRUITE_DESCENTE = [5.0, 4.0, 3.0, 2.0, 1.0]
SERIE_CONSTRUITE_ZIGZAG = [10.0, 11.0, 10.0, 11.0]
SERIE_CONSTRUITE_PLATE = [5.0] * 40
SERIE_CONSTRUITE_TROUEE = [1.0, 2.0, None, 4.0, 5.0]


# ═══ SMA — moyenne arithmétique, vérifiable de tête ════════════════════════

def test_sma_valeurs_calculees_a_la_main():
    """(1+2+3)/3 = 2 · (2+3+4)/3 = 3 · (3+4+5)/3 = 4."""
    assert sma(SERIE_CONSTRUITE_RAMPE, 3) == [None, None, 2.0, 3.0, 4.0]


def test_sma_longueur_preservee_et_debut_vide():
    """⚠️ Décaler une série d'indicateur par rapport à ses dates est la faute
    classique, et elle est invisible à l'œil."""
    for n in (1, 2, 3, 5):
        out = sma(SERIE_CONSTRUITE_RAMPE, n)
        assert len(out) == len(SERIE_CONSTRUITE_RAMPE)
        assert out[:n - 1] == [None] * (n - 1)
        assert out[n - 1] is not None


def test_sma_ne_comble_jamais_un_trou():
    """Toute fenêtre contenant un trou vaut None — ni zéro, ni report."""
    out = sma(SERIE_CONSTRUITE_TROUEE, 3)
    assert out == [None] * 5, out


def test_sma_refuse_une_fenetre_absurde():
    with pytest.raises(ValueError):
        sma(SERIE_CONSTRUITE_RAMPE, 0)


# ═══ EMA — amorçage déclaré, lissage vérifiable ═══════════════════════════

def test_ema_amorcee_par_la_sma_puis_lissee():
    """n=3 ⇒ k = 2/4 = 0,5.

    amorce = (2+4+6)/3 = 4
    i=3 : 8 × 0,5 + 4 × 0,5 = 6
    i=4 : 10 × 0,5 + 6 × 0,5 = 8
    """
    assert ema(SERIE_CONSTRUITE_PAIRS, 3) == [None, None, 4.0, 6.0, 8.0]


def test_ema_se_rompt_sur_un_trou_au_lieu_de_reporter():
    out = ema(SERIE_CONSTRUITE_TROUEE, 2)
    assert out[2] is None, "le trou doit interrompre le lissage"


def test_ema_d_une_serie_plate_vaut_la_valeur_plate():
    """Une moyenne de 5 vaut 5, quel que soit le lissage."""
    out = ema(SERIE_CONSTRUITE_PLATE, 10)
    assert all(v == 5.0 for v in out if v is not None)


# ═══ RSI de Wilder ════════════════════════════════════════════════════════

def test_rsi_vaut_cent_sans_aucune_baisse():
    """Découle de la définition : perte moyenne nulle ⇒ RS infini ⇒ RSI = 100."""
    out = rsi_wilder(SERIE_CONSTRUITE_RAMPE, 2)
    assert out[-1] == 100.0


def test_rsi_vaut_zero_sans_aucune_hausse():
    """Gain moyen nul ⇒ RS nul ⇒ RSI = 0."""
    out = rsi_wilder(SERIE_CONSTRUITE_DESCENTE, 2)
    assert out[-1] == 0.0


def test_rsi_zigzag_calcule_a_la_main():
    """Série 10 → 11 → 10 → 11, n = 2. Variations : +1, −1, +1.

    i=2 amorce : gains (1+0)/2 = 0,5 · pertes (0+1)/2 = 0,5
                 RS = 1 ⇒ RSI = 100 − 100/2 = 50
    i=3 Wilder : gains (0,5×1 + 1)/2 = 0,75 · pertes (0,5×1 + 0)/2 = 0,25
                 RS = 3 ⇒ RSI = 100 − 100/4 = 75
    """
    assert rsi_wilder(SERIE_CONSTRUITE_ZIGZAG, 2) == [None, None, 50.0, 75.0]


def test_rsi_serie_plate_est_neutre_par_convention():
    """⚠️ CONVENTION DÉCLARÉE, pas un résultat mathématique.

    Sans hausse ni baisse, RS = 0/0 n'est pas défini. Nous rendons 50, valeur
    neutre. Un autre choix serait défendable — il doit rester visible.
    """
    out = rsi_wilder(SERIE_CONSTRUITE_PLATE, 14)
    assert all(v == 50.0 for v in out if v is not None)


def test_rsi_reste_dans_ses_bornes():
    out = rsi_wilder([10, 12, 11, 15, 14, 18, 13, 19, 12, 20, 11, 21, 10, 22,
                      9, 23, 8, 24], 14)
    assert all(0.0 <= v <= 100.0 for v in out if v is not None)


# ═══ Bollinger ════════════════════════════════════════════════════════════

def test_bollinger_calculee_a_la_main():
    """[1,2,3,4,5], n = 5, k = 2.

    moyenne = 3
    variance de population = (4+1+0+1+4)/5 = 2 ⇒ écart-type = √2
    haute = 3 + 2√2 · basse = 3 − 2√2
    """
    b = bollinger(SERIE_CONSTRUITE_RAMPE, 5, 2.0)
    assert b["milieu"][-1] == pytest.approx(3.0)
    assert b["ecart_type"][-1] == pytest.approx(math.sqrt(2.0))
    assert b["haute"][-1] == pytest.approx(3.0 + 2.0 * math.sqrt(2.0))
    assert b["basse"][-1] == pytest.approx(3.0 - 2.0 * math.sqrt(2.0))


def test_bollinger_serie_plate_a_des_bandes_confondues():
    """Écart-type nul ⇒ les trois bandes se superposent."""
    b = bollinger(SERIE_CONSTRUITE_PLATE, 20, 2.0)
    i = -1
    assert b["ecart_type"][i] == pytest.approx(0.0)
    assert b["haute"][i] == b["basse"][i] == b["milieu"][i]


def test_bollinger_declare_sa_convention_d_ecart_type():
    """Population (÷ n) ou échantillon (÷ n−1) ne donnent pas les mêmes bandes."""
    b = bollinger(SERIE_CONSTRUITE_RAMPE, 5, 2.0)
    assert "population" in b["_convention"]
    # ÷(n−1) donnerait √2,5 ≈ 1,5811 — différent, et c'est le point
    assert b["ecart_type"][-1] != pytest.approx(math.sqrt(2.5))


# ═══ ATR ══════════════════════════════════════════════════════════════════

def test_atr_calcule_a_la_main():
    """h = [10,12,11] · l = [8,9,10] · c = [9,11,10], n = 2.

    i=0 : pas de clôture de veille ⇒ TR = 10 − 8 = 2
    i=1 : veille 9 ⇒ max(12−9=3 ; |12−9|=3 ; |9−9|=0) = 3
    i=2 : veille 11 ⇒ max(11−10=1 ; |11−11|=0 ; |10−11|=1) = 1
    amorce i=1 : (2+3)/2 = 2,5
    Wilder i=2 : (2,5×1 + 1)/2 = 1,75
    """
    assert atr([10.0, 12.0, 11.0], [8.0, 9.0, 10.0],
               [9.0, 11.0, 10.0], 2) == [None, 2.5, 1.75]


def test_atr_exige_les_trois_series_de_meme_longueur():
    with pytest.raises(ValueError):
        atr([1.0, 2.0], [1.0], [1.0, 2.0], 2)


def test_atr_jamais_negatif():
    out = atr([10, 12, 11, 14, 13, 16], [8, 9, 10, 11, 12, 13],
              [9, 11, 10, 13, 12, 15], 3)
    assert all(v >= 0 for v in out if v is not None)


# ═══ MACD ═════════════════════════════════════════════════════════════════

def test_macd_d_une_serie_plate_est_nul():
    """Deux moyennes d'une même constante sont égales : leur écart vaut 0."""
    m = macd(SERIE_CONSTRUITE_PLATE)
    assert {v for v in m["ligne"] if v is not None} == {0.0}
    assert {v for v in m["histogramme"] if v is not None} == {0.0}


def test_macd_positif_sur_une_hausse_reguliere():
    """Sur une rampe croissante, la moyenne courte dépasse la longue."""
    m = macd([float(i) for i in range(60)])
    derniers = [v for v in m["ligne"] if v is not None]
    assert derniers and all(v > 0 for v in derniers)


def test_macd_rend_trois_series_distinctes():
    """Les confondre est une source d'erreur fréquente."""
    m = macd([float(i) for i in range(60)])
    assert set(m) == {"ligne", "signal", "histogramme"}
    assert len(m["ligne"]) == len(m["signal"]) == len(m["histogramme"]) == 60


def test_macd_refuse_des_periodes_incoherentes():
    with pytest.raises(ValueError):
        macd(SERIE_CONSTRUITE_PLATE, court=26, long=12)


# ═══ OBV ══════════════════════════════════════════════════════════════════

def test_obv_calcule_a_la_main():
    """c = [10,11,10,10] · v = [100,200,300,400].

    i=0 : origine ⇒ 0
    i=1 : 11 > 10 ⇒ 0 + 200 = 200
    i=2 : 10 < 11 ⇒ 200 − 300 = −100
    i=3 : 10 = 10 ⇒ inchangé = −100
    """
    assert obv([10.0, 11.0, 10.0, 10.0],
               [100.0, 200.0, 300.0, 400.0]) == [0.0, 200.0, -100.0, -100.0]


def test_obv_rompt_le_cumul_sur_un_volume_absent():
    """Un cumul qui enjambe un trou est faux sans le dire."""
    out = obv([10.0, 11.0, 12.0], [100.0, None, 300.0])
    assert out[1] is None


# ═══ Hygiène : les séries construites restent dans les tests ══════════════

def test_aucune_serie_construite_sous_datasets():
    """⚠️ Elles ne doivent jamais réapparaître comme historique de marché.

    Instruction de la revue. Le préfixe rend la vérification mécanique.
    """
    coupables = []
    for f in (RACINE / "datasets").rglob("*.json"):
        if PREFIXE_SERIE_CONSTRUITE in f.read_text(encoding="utf-8"):
            coupables.append(str(f.relative_to(RACINE)))
    assert coupables == [], coupables


def test_le_socle_ne_calcule_aucune_performance():
    """Ce module rend des nombres, pas des signaux ni des rendements."""
    source = (RACINE / "pipeline" / "indicateurs.py").read_text(encoding="utf-8")
    corps = "\n".join(l for l in source.splitlines()
                      if not l.lstrip().startswith("#"))
    for interdit in ("def rendement", "def performance", "def signal",
                     "def backtest", "def probabilite"):
        assert interdit not in corps, interdit


@pytest.mark.parametrize("fn,args", [
    (sma, ([], 3)), (ema, ([], 3)), (rsi_wilder, ([], 14)),
])
def test_serie_vide_ne_plante_pas(fn, args):
    assert fn(*args) == []
