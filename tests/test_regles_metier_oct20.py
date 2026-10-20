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


# ── règle b : dette nette / EBITDA aux dates appariées ──
from pipeline.ratios_financiers import periode_bilan, RESERVE_BFR_30_06  # noqa: E402

FOND = json.loads((RACINE / "fondamentaux.json").read_text(encoding="utf-8"))


def _rb(origine="calculé"):
    return {"ebitda": {"valeur": 100.0, "valeur_exacte": 100.0, "origine": origine},
            "dette_nette_ebitda": {"valeur": -0.5, "date": "2025-12-31", "base": "consolidé"}}


def _e(base="calculé", dn=60.0):
    return {"source": "x.pdf", "base_ebitda": base,
            "dette_nette_30_06_2026": {"valeur": dn, "page": 4, "formule": "a − b"},
            "ebitda_s1_2026": {"valeur": 50.0, "page": 4, "formule": "c"},
            "ebitda_s1_2025": {"valeur": 30.0, "page": 4, "formule": "d"}}


def test_b_complet_dette_du_30_06_sur_ebitda_12_mois():
    rb = _rb()
    periode_bilan(rb, _e(), None)
    r = rb["dette_nette_ebitda"]
    assert (r["valeur"], r["date"], r["ebitda_12m"]) == (0.5, "2026-06-30", 120.0)   # 60 ÷ (100 + 50 − 30)
    assert r["reserve"] == RESERVE_BFR_30_06 and rb["dette_nette_ebitda_31_12_2025"]["valeur"] == -0.5


def test_b_incomplet_ou_autre_base_garde_le_31_12_avec_motif():
    for e, motif in ((None, "non relevé"), (_e(dn=None), "non relevé"), (_e(base="publié"), "autre base")):
        rb = _rb()
        periode_bilan(rb, e, None)
        r = rb["dette_nette_ebitda"]
        assert r["valeur"] == -0.5 and r["periode"].startswith("31/12/2025 ÷ exercice 2025") and motif in r["periode"]


def test_b_tma_sur_piece():
    r = FOND["TMA"]["ratios_publies"]["dette_nette_ebitda"]
    # 326,343 ÷ (1 685,486 + 562,182 − 731,903) = 326,343 ÷ 1 515,765
    assert (r["valeur"], r["date"], r["ebitda_12m"]) == (0.22, "2026-06-30", 1515.765)
    from pipeline.smart_money.fond_score import detail_fond_score
    b = detail_fond_score("TMA", FOND, per_publie=14.6, croissance_sourcee=True)["composantes"]["bilan"]
    assert b["note"] == 8.5 and "période : 30/06/2026" in b["mesure"] and "saisonnalité" in b["reserve"]


# ── règle h : EBITDA encadré, borne publiée si le palier ne change pas ──
from pipeline.ratios_financiers import calculer_bilan  # noqa: E402

FAITS = json.loads((RACINE / "pipeline" / "faits_financiers.json").read_text(encoding="utf-8"))


def test_h_cmt_borne_superieure_sur_piece():
    r = FOND["CMT"]["ratios_publies"]["dette_nette_ebitda"]
    # 142,868134 ÷ 387,848 = 0,36836 → arrondi VERS LE HAUT : 0,3684 (sous le seuil de 0,5)
    assert (r["valeur"], r["borne"]) == (0.3684, "supérieure") and r["valeur"] >= 142.868134 / 387.848
    from pipeline.smart_money.fond_score import detail_fond_score
    d = detail_fond_score("CMT", FOND, per_publie=21.9, croissance_sourcee=True)
    b = d["composantes"]["bilan"]
    assert b["note"] == 9.0 and "≤ 0.3684" in b["mesure"] and "borne" in b["mesure"] and "valeur)" in b["mesure"]
    assert d["note"] == 8.4    # (8,5×0,4 + 10×0,3 + 5,5×0,2 + 9,0×0,1) ÷ 1


def test_h_pas_de_borne_si_le_palier_change():
    import copy
    e = copy.deepcopy(FAITS["CMT"])
    e["_controles_ratios_2025"]["ebitda_borne_inferieure"]["valeur"] = 100.0   # 142,9 ÷ 100 = 1,43 : 8,5 → 7,0
    rb, non = calculer_bilan(e)
    assert "dette_nette_ebitda" not in rb and "palier" in non["dette_nette_ebitda"]
