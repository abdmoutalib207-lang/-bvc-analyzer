#!/usr/bin/env python3
"""Sothema : 486 séances à une échelle vingt-trois fois trop basse.

⚠️ CE QUI ÉTAIT SERVI
─────────────────────
    moyenne 200 jours       164,94 DH
    plus-bas 52 semaines     65,99 DH
pour un titre qui en vaut 365. Les deux tiers de la fenêtre étaient à une
échelle vingt-trois fois trop basse : la série disait 73,80 DH là où le marché
cotait 1 700,00.

⚠️ D'OÙ VIENT LE 23
Sothema a regroupé ses titres le 05/05/2026. L'ajustement a été appliqué DEUX
FOIS à l'historique — environ 4,61 puis 5 — et 4,61 × 5 ≈ 23,03.

⚠️ LE RATIO EST MESURÉ, PAS SUPPOSÉ
Capitalisation ÷ cours, sur les deux séances qui ENCADRENT la date d'effet,
dans l'export de l'opérateur :

    04/05/2026   13 025 230 000 ÷ 1 700 =  7 661 900 titres
    05/05/2026   14 097 896 000 ÷   368 = 38 309 500 titres

Exactement ×5. Jamais une moyenne de trente séances : elle lisserait la marche
qu'on cherche précisément à lire.

⚠️ ET ON NE REPREND PAS L'EXPORT TEL QUEL
L'opérateur publie les cours BRUTS, non ajustés. Les recopier aurait inscrit
une chute de 78 % au 05/05 dans le graphique, alors que rien n'a chuté. Les
prix antérieurs sont donc ramenés à la base d'aujourd'hui, en divisant par 5.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE / "pipeline"))

RECU = RACINE / "datasets" / "corrections_acceptees" / "SOT.json"
EFFET = "2026-05-05"


@pytest.fixture(scope="module")
def recu():
    return json.loads(RECU.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def serie():
    return json.loads((RACINE / "pipeline" / "candles" / "SOT.json")
                      .read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def cache():
    return json.loads((RACINE / "pipeline" / "historical_data.json")
                      .read_text(encoding="utf-8"))["SOT"]


# ── L'échelle ──────────────────────────────────────────────────────────────

def test_plus_aucune_bougie_a_l_echelle_de_l_ancien_ajustement(serie):
    """⚠️ LE CONTRÔLE QUI MORD. Sothema n'a jamais valu 40 DH. Une bougie sous
    150 DH sur cette série est un reliquat du double ajustement."""
    basses = [b["d"] for b in serie if b["l"] < 150]
    assert basses == [], f"bougies encore à l'ancienne échelle : {basses[:8]}"


def test_la_serie_reste_dans_une_fourchette_plausible(serie):
    """Entre mai 2024 et aujourd'hui, l'opérateur va de ~880 à ~1 950 DH bruts,
    soit 176 à 390 une fois ramenés à la base actuelle."""
    assert 150 < min(b["l"] for b in serie) < 250
    assert 350 < max(b["h"] for b in serie) < 450


def test_aucune_marche_de_regroupement_ne_subsiste(serie):
    """⚠️ Le but même de la division par 5 : le graphique ne doit pas montrer
    une chute qui n'a pas eu lieu. Aucune séance ne s'écarte de la précédente
    au-delà de la limite réglementaire de ±10 % (R10) — hors les séances sans
    échange, où le cours est rediffusé."""
    fautives = []
    for a, b in zip(serie, serie[1:]):
        if not a["c"] or not b["c"]:
            continue
        if abs(b["c"] / a["c"] - 1) > 0.101:
            fautives.append((b["d"], a["c"], b["c"]))
    assert fautives == [], f"marches au-delà de ±10 % : {fautives[:5]}"


def test_le_ratio_du_regroupement_est_documente_comme_mesure(recu):
    """⚠️ Un ratio supposé ne vaut rien. Le document doit dire d'où il vient."""
    assert "7 661 900" in recu["_le_ratio_est_MESURÉ_pas_supposé"]
    assert "38 309 500" in recu["_le_ratio_est_MESURÉ_pas_supposé"]
    assert "×5" in recu["_le_ratio_est_MESURÉ_pas_supposé"]
    assert "ENCADRENT" in recu["_le_ratio_est_MESURÉ_pas_supposé"]


def test_les_deux_bases_sont_declarees(recu):
    """⚠️ Les prix sont ramenés à la base postérieure, les QUANTITÉS ne sont pas
    converties. Fondre les deux en silence serait le défaut d'origine."""
    assert "POSTÉRIEURE" in recu["_base_retenue"]
    assert "ne sont PAS converties" in recu["_base_des_quantites"]
    assert "ANTÉRIEURE" in recu["_base_des_quantites"]


# ── Les indicateurs servis ─────────────────────────────────────────────────

def test_la_moyenne_200_jours_n_est_plus_a_la_moitie_du_cours(cache, serie):
    """164,94 pour un titre à 365 : les deux tiers de la fenêtre étaient faux."""
    assert cache["ma200"] > 300
    assert abs(cache["ma200"] / serie[-1]["c"] - 1) < 0.35


def test_le_plus_bas_52_semaines_n_est_plus_65_99(cache):
    assert cache["l52w"] == 304.0
    assert cache["l52w"] > 250, "un plancher annuel sous 250 DH serait un reliquat"


# ── Les séances sans échange ───────────────────────────────────────────────

def test_une_seance_sans_echange_n_a_pas_d_amplitude(recu, serie):
    """⚠️ 29 séances où l'opérateur ne publie QUE la clôture : le titre n'a pas
    coté. On y écrit o=h=l=c et v=0 — convention du 10/08/2026 — plutôt que de
    garder des extrêmes fabriqués depuis la veille."""
    par_date = {b["d"]: b for b in serie}
    sans = [l for l in recu["lignes"] if l["corrige"]["v"] == 0]
    assert len(sans) == 29
    for l in sans:
        b = par_date[l["d"]]
        assert b["o"] == b["h"] == b["l"] == b["c"], l["d"]
        assert b["v"] == 0


# ── La durabilité ──────────────────────────────────────────────────────────

def test_la_correction_resiste_a_une_recontamination(recu, serie):
    """⚠️ L'import réécrit les chandelles. Sans réimposition, le double
    ajustement reviendrait au prochain passage."""
    from corrections_acceptees import appliquer
    sale = [dict(b) for b in serie]
    par_date = {l["d"]: l for l in recu["lignes"]}
    for b in sale:
        if b["d"] in par_date:
            b.update(par_date[b["d"]]["remplace"])
    assert sale != serie
    out, rapport = appliquer("SOT", sale)
    assert rapport["corrections"] == len(recu["lignes"]) == 514
    assert rapport["refus"] == []
    assert out == serie


def test_ce_qui_reste_ouvert_est_nomme(recu):
    """⚠️ Sept séances décalées d'un jour et 191 séances absentes de notre
    série : nommées, non corrigées. Un lot qui tait ce qu'il laisse derrière
    lui se lit comme s'il avait tout réglé."""
    txt = recu["_ce_qui_n_est_pas_corrige_ici"]
    assert "décalage d'une séance" in txt and "191" in txt
