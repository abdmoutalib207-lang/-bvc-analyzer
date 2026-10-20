"""Règles métier des fondamentaux du 20/10/2026 (verificateur-finance ; « la norme prime »).

Un test par règle, dans l'ordre d'implémentation. Chaque attendu est recalculé
à la main depuis la pièce citée au point d'application.
"""
import json
import sys
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

import bvc_config  # noqa: E402
from pipeline.resultats_semestriels import douze_mois  # noqa: E402

BPA = json.loads((RACINE / "bpa.json").read_text(encoding="utf-8"))
JEU = json.loads((RACINE / "datasets" / "resultats_s1_2026.json").read_text(encoding="utf-8"))


# ── règle e : BPA sur le nombre moyen pondéré (IAS 33.19-20, 21, 26-28, 64) ──
def test_e_cih_emission_dans_la_periode_ponderee():
    # 31 497 283 actions du 01/07 au 30/07/2025 (30 j), 35 605 624 ensuite (335 j) ;
    # l'émission du 28/07/2026 suit la clôture : exclue.
    n = bvc_config.actions_ponderees("CIH", "2025-07-01", "2026-06-30", 38641338)["nombre"]
    assert n == round((31497283 * 30 + 35605624 * 335) / 365)
    m = douze_mois(JEU["titres"]["CIH"], "CIH")
    assert m["bpa_12m"] == round(1090.912e6 / n, 2) == 30.93
    # Exercice 2025 : 211 jours avant le 31/07, 154 après.
    assert BPA["CIH"]["bpa"] == round(1089.362e6 / ((31497283 * 211 + 35605624 * 154) / 365), 2) == 32.78
    assert BPA["CIH"]["bpa_12m"] == 30.93 and BPA["CIH"]["bpa_12m_avant_2026_10_20"] == 28.23


def test_e_cdm_emission_posterieure_exclue():
    assert bvc_config.actions_ponderees("CDM", "2025-07-01", "2026-06-30", 11626499)["nombre"] == 10881214
    assert (BPA["CDM"]["bpa"], BPA["CDM"]["bpa_12m"]) == (79.36, 87.32)


def test_e_t2s_ambigu_garde_le_calcul_et_publie_la_reserve():
    r = bvc_config.actions_ponderees("T2S", "2025-07-01", "2026-06-30", 21785174)
    assert r["nombre"] == 21785174 and "IAS 33" in r["reserve"]
    assert BPA["T2S"]["bpa_12m"] == 8.58 and "PLANCHER" in BPA["T2S"]["reserve_bpa"]


def test_e_titre_absent_garde_le_nombre_actuel():
    assert "ATW" not in bvc_config.HISTORIQUE_ACTIONS
    assert bvc_config.actions_ponderees("ATW", "2025-07-01", "2026-06-30", 215140839)["nombre"] == 215140839
    assert "reserve_bpa" not in BPA.get("ATW", {})


def test_e_division_retro_ajustee_meme_apres_la_cloture(monkeypatch):
    monkeypatch.setitem(bvc_config.HISTORIQUE_ACTIONS, "ZZZ", {"mouvements": [
        {"date": "2026-01-01", "nature": "numeraire", "avant": 100, "apres": 200, "source": "test"},
        {"date": "2026-08-01", "nature": "division", "ratio": 2, "source": "test"}]})
    # 2025 : 100 actions ×2 (division postérieure, rétro-ajustée) ; émission de 2026 hors période.
    assert bvc_config.actions_ponderees("ZZZ", "2025-01-01", "2025-12-31", 400)["nombre"] == 200
    # S1 2026 : 200 ×2 tout le semestre.
    assert bvc_config.actions_ponderees("ZZZ", "2026-01-01", "2026-06-30", 400)["nombre"] == 400


def test_e_registre_source_chaque_mouvement():
    for s, e in bvc_config.HISTORIQUE_ACTIONS.items():
        assert e.get("reserve") if e.get("denominateur_ambigu") else e["mouvements"], s
        for m in e["mouvements"]:
            assert m["source"] and m["nature"] in ("numeraire", "division"), s
