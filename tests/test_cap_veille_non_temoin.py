"""18/11/2026 — la capitalisation de NRJ ne se reconduit plus d'elle-même.

NRJ restait à 2 366 MDHS alors que 190 DH × 13 125 000 actions (registre des
introductions, note d'opération visée par l'AMMC) = 2 494, le chiffre de la
Bourse. La valeur de la veille, gardée « sous le seuil d'écart », se
confirmait elle-même à chaque passage."""
import json
import logging
import sys
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))
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


def test_le_meta_dit_d_ou_vient_le_nombre_d_actions():
    d = ud._cap_detail("NRJ", "calculee_actions_introduction", 2494, None)
    assert d["cap_actions_source"] == "introduction"


def test_controle_negatif_un_temoin_du_jour_garde_son_role():
    assert ud._capitalisation("NRJ", 190.0, 2366, "cdg", cloture_veille=171.55,
                              temoin_du_jour=True) == (2366, "servie")


def test_controle_negatif_comptes_releves_rendent_la_main_a_hal(monkeypatch):
    # Dès que NRJ a des comptes relevés, le nombre d'introduction n'est plus lu
    # et la règle HAL reprend : la valeur servie reste sous le seuil.
    monkeypatch.setattr(ud, "FAITS_DATA", {"NRJ": {"faits": {"nombre_actions_existant": {"valeur": 13_125_000}}}})
    assert ud._actions_introduction("NRJ") is None
    cap, src = ud._capitalisation("NRJ", 190.0, 2366, "cdg", cloture_veille=171.55, temoin_du_jour=False)
    assert src != "calculee_actions_introduction"


def test_controle_negatif_le_releve_officiel_prend_le_pas(monkeypatch):
    monkeypatch.setattr(ud, "_actions_bourse", lambda t: 13_125_000 if t == "NRJ" else None)
    assert ud._capitalisation("NRJ", 190.0, 2366, "cdg", temoin_du_jour=False) == (2494, "calculee_bourse_officielle")


def test_un_split_posterieur_a_l_introduction_est_applique(monkeypatch):
    monkeypatch.setattr(ud, "SPLITS", {"NRJ": [{"date": "2027-01-15", "ratio": 2}]})
    assert ud._actions_introduction("NRJ") == 26_250_000
    # et un split ANTÉRIEUR (déjà dans le nombre d'après l'opération) ne l'est pas
    monkeypatch.setattr(ud, "SPLITS", {"NRJ": [{"date": "2026-11-16", "ratio": 10}]})
    assert ud._actions_introduction("NRJ") == 13_125_000


def test_le_terminal_explique_la_provenance():
    ecran = (RACINE / "terminal.src.html").read_text(encoding="utf-8")
    assert "calculee_actions_introduction:" in ecran


def test_donnees_publiees_cours_fois_nombre_d_introduction():
    """Famille « données publiées » : vaut dès que le moteur a tourné sur ce code."""
    data = json.loads((RACINE / "data.json").read_text(encoding="utf-8"))
    lignes = [t for t in data["tickers"]
              if (t.get("_meta") or {}).get("cap_source") == "calculee_actions_introduction"]
    if not lignes:
        pytest.skip("data.json antérieur à ce correctif")
    for t in lignes:
        n = ud._actions_introduction(t["symbol"])
        assert t["cap"] == ud._arrondi_cap(t["price"] * n / 1e6), t["symbol"]
