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
