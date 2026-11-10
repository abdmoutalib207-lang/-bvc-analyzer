"""Corrections établies sur pièce par la contre-vérification du 09/11/2026 contre ms-screener.

Un test par correction : la VALEUR, recalculée à la main depuis la pièce citée,
et la PIÈCE elle-même (URL, page) dans l'enregistrement. Les attendus ne sont
pas recalculés avec la fonction testée.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

import bvc_config  # noqa: E402
from pipeline.resultats_semestriels import appliquer, douze_mois  # noqa: E402

JEU = json.loads((RACINE / "datasets" / "resultats_s1_2026.json").read_text(encoding="utf-8"))
BPA = json.loads((RACINE / "bpa.json").read_text(encoding="utf-8"))
FOND = json.loads((RACINE / "fondamentaux.json").read_text(encoding="utf-8"))


# ── mécanisme : l'ancienne valeur rangée sous la date du lot ──

def test_une_correction_datee_garde_l_ancienne_valeur_sous_sa_date():
    """`corrige_le` range l'ancien BPA sous `bpa_avant_<date>` et ne pose PAS
    la clé du lot du 29/09, qui mentirait sur la date de l'ancienne valeur."""
    t = {"rnpg_exercice_2025": 100.0, "rnpg_s1_2026": 60.0, "rnpg_s1_2025": 40.0,
         "actions": 10_000_000, "url": "x.pdf", "pages": "p.1", "base": "test",
         "corrige_le": "2026-11-09"}
    bpa = {"ZZZ": {"bpa": 12.0, "bpa_12m": 13.0, "rnpg_12m": 130.0}}
    appliquer({"fin_periode": "2026-06-30", "titres": {"ZZZ": t}}, bpa, {})
    b = bpa["ZZZ"]
    assert (b["bpa"], b["bpa_12m"], b["rnpg_12m"]) == (10.0, 12.0, 120.0)
    assert (b["bpa_avant_2026_11_09"], b["bpa_12m_avant_2026_11_09"], b["rnpg_12m_avant_2026_11_09"]) == \
        (12.0, 13.0, 130.0)
    assert "bpa_avant_2026_09_29" not in b and "bpa_12m_avant_2026_10_20" not in b
    # Idempotent : un second passage ne réécrit pas l'ancienne valeur.
    appliquer({"fin_periode": "2026-06-30", "titres": {"ZZZ": t}}, bpa, {})
    assert bpa["ZZZ"]["bpa_avant_2026_11_09"] == 12.0


# ── 1. T2S : dénominateur aligné sur 22 584 118 actions ──

def test_t2s_bpa_sur_22_584_118_actions_et_sa_piece():
    t = JEU["titres"]["T2S"]
    assert t["actions"] == 22584118 == 21785174 + 798944 and t["actions_avant_2026_11_09"] == 21785174
    # 204,576 ÷ 22,584118 = 9,058 ; (204,576 + 91,307 − 108,864) = 187,019 ÷ 22,584118 = 8,281
    b = BPA["T2S"]
    assert (b["bpa"], b["bpa_12m"], b["rnpg_12m"]) == (9.06, 8.28, 187.019)
    assert (b["bpa_avant_2026_11_09"], b["bpa_12m_avant_2026_11_09"]) == (9.39, 8.58)
    assert b["actions_12m"] == b["actions_exercice_2025"] == FOND["T2S"]["nb_actions"] == 22584118
    for texte in (t["source_actions"], b["reserve_bpa"], FOND["T2S"]["reserve_nb_actions"],
                  bvc_config.HISTORIQUE_ACTIONS["T2S"]["reserve"]):
        assert "CP_T2S_group_augmentation_capital_reservee_dirigeant.pdf" in texte and "23/09/2026" in texte
        assert "798 944" in texte and "p.45" in texte
    # Le traitement IAS 33 n'est toujours pas tranché : nombre ACTUEL et réserve publiée.
    assert bvc_config.HISTORIQUE_ACTIONS["T2S"]["denominateur_ambigu"] and "PLANCHER" in b["reserve_bpa"]


# ── 2. HAL (Auto Hall) : l'émission de septembre 2026 est postérieure aux deux périodes ──

def test_hal_bpa_sur_les_50_294_528_actions_de_la_periode():
    t = JEU["titres"]["HAL"]
    # Auto_Hall_S1_26.pdf p.5 : 64 812 881,31 et 47 305 263,28 DH ; avis AGO p.7 : 99 832 376,79 DH.
    assert (t["rnpg_s1_2026"], t["rnpg_s1_2025"], t["rnpg_exercice_2025"]) == (64.812881, 47.305263, 99.832377)
    assert "64 812 881,31 47 305 263,28" in t["pages"] and "99 832 376,79" in t["source_exercice_2025"]
    assert t["actions"] == 54140578                                # le nombre ACTUEL reste celui de la capitalisation
    (m,) = bvc_config.HISTORIQUE_ACTIONS["HAL"]["mouvements"]
    assert (m["date"], m["nature"], m["avant"], m["apres"]) == ("2026-09-02", "numeraire", 50294528, 54140578)
    assert m["apres"] - m["avant"] == 3846050
    assert "CP_Auto_Hall_rsultats_augmentation_capital.pdf" in m["source"] and "2 septembre 2026" in m["source"]
    assert "NO_AutoHall_025_2026.pdf" in m["source"] and "22/07/2026" in m["source"] and "03/09/2026" in m["source"]
    # Émission postérieure au 30/06/2026 : exclue des deux périodes (IAS 33.21).
    for debut, fin in (("2025-01-01", "2025-12-31"), ("2025-07-01", "2026-06-30")):
        assert bvc_config.actions_ponderees("HAL", debut, fin, 54140578)["nombre"] == 50294528
    b = BPA["HAL"]
    # 99 832 377 ÷ 50 294 528 = 1,985 ; 117 339 995 ÷ 50 294 528 = 2,333
    assert (b["bpa"], b["bpa_12m"], b["rnpg_12m"]) == (1.98, 2.33, 117.34)
    assert b["rnpg_12m"] == round((99832377 + 64812881 - 47305263) / 1e6, 3)
    assert (b["bpa_avant_2026_11_09"], b["bpa_12m_avant_2026_11_09"], b["rnpg_12m_avant_2026_11_09"]) == \
        (1.84, 2.17, 117.332)
    assert b["actions_12m"] == b["actions_exercice_2025"] == 50294528
