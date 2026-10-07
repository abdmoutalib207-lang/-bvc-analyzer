"""Capitalisation : cours × nombre d'actions de l'opérateur, à 2 % — 02/10/2026.

Demande d'Abd Moutalib : vérifier la capitalisation d'ADI et de toute la cote.
ADI était juste (365 × 22 078 588 = 8 059). LHM ne l'était pas : 41 005 MDHS
servis, quand 1 600 × 23 431 240 (opérateur) = 37 490 ; l'ancienne tolérance
de 10 % la laissait passer. Attendus calculés à la main.
"""

import json
import logging
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))
logging.disable(logging.CRITICAL)


def test_le_nombre_d_actions_de_l_operateur_prime(ud):
    assert ud._actions_sourcees("LHM") == 23431240
    assert ud._actions_sourcees("ADI") == 22078588


def test_une_capitalisation_surevaluee_de_9_pour_cent_est_refusee(ud):
    cap, src = ud._capitalisation("LHM", 1600.0, 41005, "cdg")
    assert (cap, src) == (37490, "calculee_apres_refus")     # 1 600 × 23 431 240


def test_une_capitalisation_juste_est_recoupee(ud):
    # 365 × 22 078 588 = 8 058,7 → 8 059 : la source concorde, on publie le produit.
    assert ud._capitalisation("ADI", 365.0, 8059, "cdg") == (8059, "calculee_recoupee")


def test_l_augmentation_de_capital_de_hal_est_inscrite(ud):
    # 50 294 528 + 3 846 050 (avis d'émission AMMC) = 54 140 578 ; 61 × 54 140 578 ≈ 3 303
    ud.FAITS_DATA = json.loads((RACINE / "pipeline" / "faits_financiers.json").read_text(encoding="utf-8"))
    assert ud._actions_sourcees("HAL") == 54140578
    assert ud._capitalisation("HAL", 61.0, 3303, "cdg") == (3303, "calculee_recoupee")
