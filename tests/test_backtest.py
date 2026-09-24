#!/usr/bin/env python3
"""Un backtest se juge sur sa prudence avant de se juger sur son résultat.

⚠️ LES DEUX FAÇONS DE MENTIR AVEC UN BACKTEST
─────────────────────────────────────────────
  **regarder le futur**  — rejouer le modèle d'aujourd'hui sur les données
                           d'hier. Ici ce serait fatal : les fondamentaux sont
                           figés à leur valeur actuelle, les appliquer à juin
                           donnerait au modèle la connaissance de ce qui allait
                           arriver ;
  **conclure sur rien**  — annoncer « le score sépare » sur huit observations.
                           C'est ce que le premier jet de ce module faisait, et
                           le chiffre aurait été cité comme un résultat.

Ces tests défendent surtout la seconde. La première est écartée par
construction : on lit les scores RÉELLEMENT PUBLIÉS dans l'historique git, on
ne recalcule rien.

⚠️ ET UN TROISIÈME PIÈGE, PLUS SOURNOIS
Mesurer un rendement brut là où le marché entier a bougé. Sur la période, tous
les paliers ressortent négatifs — le MASI a reculé. Un score qui choisit des
titres perdant 6 % quand le marché perd 8 % est utile, et le rendement brut le
dirait mauvais. On mesure donc l'ÉCART AU MARCHÉ.
"""

from __future__ import annotations

import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))
sys.path.insert(0, str(RACINE / "pipeline"))

from backtest import (  # noqa: E402
    MIN_OBSERVATIONS, PALIERS, mesurer, rendement_futur, verdict,
)

SERIE = [(f"2026-09-{j:02d}", 100.0 + j) for j in range(1, 29)]


# ── ⚠️ Pas de regard vers le futur ─────────────────────────────────────────

def test_le_rendement_part_de_la_cloture_du_jour_du_score():
    """⚠️ On achète APRÈS avoir lu le score, au cours de clôture de ce jour —
    pas à celui qui a servi à le calculer. Partir d'un cours antérieur
    supposerait qu'on a agi avant de savoir."""
    # départ 101 (01/09), arrivée 106 (06/09) → +4,95 %
    r = rendement_futur(SERIE, "2026-09-01", 5)
    assert abs(r - (106 / 101 - 1) * 100) < 1e-9


def test_une_fenetre_incomplete_ne_rend_rien():
    """⚠️ Et surtout pas le dernier cours connu : ce serait mesurer un horizon
    plus court en le présentant comme le long."""
    assert rendement_futur(SERIE, "2026-09-28", 5) is None
    assert rendement_futur(SERIE, "2026-09-26", 20) is None


def test_une_date_absente_de_la_serie_ne_rend_rien():
    assert rendement_futur(SERIE, "2026-07-04", 5) is None


# ── ⚠️ Ne pas conclure sur rien ────────────────────────────────────────────

def test_le_verdict_refuse_de_conclure_sous_le_seuil():
    """LA GARDE CENTRALE. Le premier jet écrivait « le score NE sépare PAS »
    sur un palier de HUIT observations — un verdict tiré d'un tirage."""
    mesure = {"20_seances": {"par_palier": {
        "≥ 7 — achat": {"n": 8, "moyenne_pct": -6.0},
        "≤ 4 — évitement": {"n": 5, "moyenne_pct": -3.0}}}}
    v = verdict(mesure)["20_seances"]
    assert "INSUFFISANT" in v["conclusion"]
    assert "ecart_achat_moins_evitement_pts" not in v


def test_le_verdict_conclut_quand_l_echantillon_suffit():
    n = MIN_OBSERVATIONS
    mesure = {"5_seances": {"par_palier": {
        "≥ 7 — achat": {"n": n, "moyenne_pct": 2.0},
        "≤ 4 — évitement": {"n": n, "moyenne_pct": -1.0}}}}
    v = verdict(mesure)["5_seances"]
    assert v["conclusion"] == "le score sépare"
    assert v["ecart_achat_moins_evitement_pts"] == 3.0


def test_le_verdict_dit_aussi_quand_le_score_ne_separe_pas():
    """⚠️ Un backtest qui ne saurait annoncer qu'une bonne nouvelle ne mesure
    rien. Le cas défavorable doit sortir aussi clairement que l'autre."""
    n = MIN_OBSERVATIONS
    mesure = {"5_seances": {"par_palier": {
        "≥ 7 — achat": {"n": n, "moyenne_pct": -4.0},
        "≤ 4 — évitement": {"n": n, "moyenne_pct": 1.0}}}}
    assert verdict(mesure)["5_seances"]["conclusion"] == "le score NE sépare PAS"


def test_le_seuil_n_est_pas_symbolique():
    assert MIN_OBSERVATIONS >= 30


# ── ⚠️ L'écart au marché, pas le rendement brut ────────────────────────────

def test_le_rendement_est_mesure_en_ecart_au_marche():
    """⚠️ LE PIÈGE SOURNOIS. Un titre qui monte de 2 % quand le marché monte
    de 5 % a perdu 3 points. Le rendement brut le dirait gagnant."""
    scores = {"2026-09-01": {"AAA": {"v53": 8.0, "conf": 5}}}
    prix = {"AAA": [(d, 100.0 + i * 0.4) for i, (d, _) in enumerate(SERIE)]}
    masi = [(d, 100.0 + i * 1.0) for i, (d, _) in enumerate(SERIE)]
    sans = mesurer(scores, prix, horizons=(5,), masi=[])
    avec = mesurer(scores, prix, horizons=(5,), masi=masi)
    brut = sans["5_seances"]["ensemble"]["moyenne_pct"]
    alpha = avec["5_seances"]["ensemble"]["moyenne_pct"]
    assert brut > 0, "le titre monte"
    assert alpha < 0, "mais il monte MOINS que le marché"


# ── ⚠️ Le filtre de confiance ──────────────────────────────────────────────

def test_un_signal_que_le_produit_refuse_d_emettre_est_ecarte():
    """Mesurer la performance de signaux affichés « Données insuffisantes »
    reviendrait à créditer — ou accabler — le score de ce qu'il ne publie
    pas."""
    scores = {"2026-09-01": {"AAA": {"v53": 8.0, "conf": 1},
                             "BBB": {"v53": 8.0, "conf": 5}}}
    prix = {s: SERIE for s in ("AAA", "BBB")}
    r = mesurer(scores, prix, horizons=(5,), masi=[])
    assert r["5_seances"]["ensemble"]["n"] == 1


def test_une_confiance_absente_est_ecartee_et_non_supposee():
    """⚠️ C'est ce qui réduit la période utile : `_meta` n'existe que depuis le
    10/08, donc 1 898 observations antérieures sortent. Les supposer fiables
    gonflerait l'échantillon de données qu'on ne sait pas qualifier."""
    scores = {"2026-09-01": {"AAA": {"v53": 8.0, "conf": None}}}
    r = mesurer(scores, {"AAA": SERIE}, horizons=(5,), masi=[])
    assert r["5_seances"]["ensemble"]["n"] == 0


# ── Le classement par palier ───────────────────────────────────────────────

def test_chaque_score_tombe_dans_un_palier_et_un_seul():
    bornes = [(lo, hi) for lo, hi, _ in PALIERS]
    for v in (0, 3.99, 4, 5.49, 5.5, 6.99, 7, 10):
        n = sum(1 for lo, hi in bornes if lo <= v < hi)
        assert n == 1, f"le score {v} tombe dans {n} paliers"


def test_les_paliers_couvrent_toute_l_echelle():
    """Un score de 10 doit être classé, pas perdu en chemin."""
    assert PALIERS[0][0] == 0 and PALIERS[-1][1] > 10


def test_le_module_ne_modifie_pas_ce_qu_il_mesure():
    import copy
    scores = {"2026-09-01": {"AAA": {"v53": 8.0, "conf": 5}}}
    prix = {"AAA": list(SERIE)}
    a, b = copy.deepcopy(scores), copy.deepcopy(prix)
    mesurer(scores, prix, horizons=(5,), masi=[])
    assert scores == a and prix == b
