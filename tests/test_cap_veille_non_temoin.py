"""18/11/2026 — la capitalisation de NRJ ne se reconduit plus d'elle-même.

NRJ restait à 2 366 MDHS alors que 190 DH × 13 125 000 actions (registre des
introductions, note d'opération visée par l'AMMC) = 2 494, le chiffre de la
Bourse. La valeur de la veille, gardée « sous le seuil d'écart », se
confirmait elle-même à chaque passage."""
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
logging.disable(logging.CRITICAL)

import update_data as ud  # noqa: E402

ATTENDU = (2494, "calculee_actions_introduction")


def test_nrj_source_du_jour_sans_capitalisation():
    assert ud._actions_introduction("NRJ") == 13_125_000
    assert ud._capitalisation("NRJ", 190.0, 2366, "cdg", cloture_veille=171.55,
                              temoin_du_jour=False) == ATTENDU


def test_nrj_cours_des_chandelles():
    assert ud._capitalisation("NRJ", 190.0, 2366, "candles", cloture_veille=171.55,
                              temoin_du_jour=False) == ATTENDU


def test_controle_negatif_un_temoin_du_jour_garde_son_role():
    assert ud._capitalisation("NRJ", 190.0, 2366, "cdg", cloture_veille=171.55,
                              temoin_du_jour=True) == (2366, "servie")


def test_controle_negatif_titre_avec_comptes_ou_releve_inchange():
    # Un titre à comptes relevés n'a pas de nombre « d'introduction ».
    assert ud._actions_introduction("IAM") is None
    assert ud._actions_introduction("T2S") is None or "T2S" not in ud.INTRODUCTIONS


def test_le_terminal_explique_la_provenance():
    ecran = (Path(__file__).resolve().parent.parent / "terminal.src.html").read_text(encoding="utf-8")
    assert "calculee_actions_introduction:" in ecran
