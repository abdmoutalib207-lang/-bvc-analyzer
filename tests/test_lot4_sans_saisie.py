"""Lot 4 — plus aucune saisie manuelle lue par la note (02/10/2026).

Attendus calculés à la main : note = q×0,40 + g×0,30 + v×0,20 + b×0,10.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pipeline.smart_money import fond_score as F  # noqa: E402

FICHE = {"secteur": "Industrie", "roic": 15, "wacc": 9, "croissance_bpa": 30,
         "croissance_ca": 30, "forward_per": 10, "dette_nette_ebitda": 1.0,
         "cash_conversion": 70, "momentum_fondamental": "très positif",
         "rerating": True, "cycle_commodities": "bullish"}


def test_le_wacc_saisi_n_est_plus_lu():
    a = F.compute_fond_score("X", {"X": dict(FICHE, wacc=9)}, per_publie=10, croissance_sourcee=True)
    b = F.compute_fond_score("X", {"X": dict(FICHE, wacc=12)}, per_publie=10, croissance_sourcee=True)
    assert a == b


def test_les_modificateurs_saisis_ne_bonifient_plus():
    # ROIC 15 − WACC 10 = 5 → 7,0 ; croissance 30 → 7,5 ; PER 10 → 8,5 ;
    # dette 1,0 → 7,0 : 2,8 + 2,25 + 1,7 + 0,7 = 7,45 (et non 7,45 + 1,0)
    assert F.compute_fond_score("X", {"X": FICHE}, per_publie=10, croissance_sourcee=True) == 7.45


def test_croissance_et_per_non_sources_sont_non_evalues():
    # g 5,0 et v 5,0 : 2,8 + 1,5 + 1,0 + 0,7 = 6,0
    assert F.compute_fond_score("X", {"X": FICHE}, per_publie=None, croissance_sourcee=False) == 6.0
