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
         "rerating": True, "cycle_commodities": "bullish",
         # Depuis le 14/10/2026 une saisie sans pièce n'est plus notée : les
         # ratios de la fiche d'essai sont donc « publiés ».
         "ratios_publies": {"roic": {"valeur": 15}, "dette_nette_ebitda": {"valeur": 1.0},
                            "cash_conversion": {"valeur": 70}}}


def test_le_wacc_saisi_n_est_plus_lu():
    a = F.compute_fond_score("X", {"X": dict(FICHE, wacc=9)}, per_publie=10, croissance_sourcee=True)
    b = F.compute_fond_score("X", {"X": dict(FICHE, wacc=12)}, per_publie=10, croissance_sourcee=True)
    assert a == b


def test_les_modificateurs_saisis_ne_bonifient_plus():
    # ROIC 15 − WACC 10 = 5 → 7,0 ; croissance 30 → 7,5 ; PER 10 → 8,5 ;
    # dette 1,0 → 7,0 : 2,8 + 2,25 + 1,7 + 0,7 = 7,45 (et non 7,45 + 1,0)
    assert F.compute_fond_score("X", {"X": FICHE}, per_publie=10, croissance_sourcee=True) == 7.45


def test_croissance_et_per_non_sources_sont_non_evalues():
    # Non évalués = RETIRÉS (14/10/2026), plus notés 5,0 : qualité 7,0 × 0,4
    # + bilan 7,0 × 0,1, sur une couverture de 0,5 → 7,0.
    assert F.compute_fond_score("X", {"X": FICHE}, per_publie=None, croissance_sourcee=False) == 7.0


def test_une_saisie_sans_piece_n_est_pas_notee():
    saisie = {k: v for k, v in FICHE.items() if k != "ratios_publies"}
    d = F.detail_fond_score("X", {"X": saisie}, per_publie=10, croissance_sourcee=True)
    assert d["composantes"]["qualite"]["note"] is None
    assert d["composantes"]["bilan"]["note"] is None       # plus de dette fictive 1,0×
    assert d["couverture"] == 0.5 and d["note"] == 7.9     # (7,5 × 0,3 + 8,5 × 0,2) / 0,5


def test_sans_couverture_suffisante_pas_de_note():
    saisie = {k: v for k, v in FICHE.items() if k != "ratios_publies"}
    assert F.compute_fond_score("X", {"X": saisie}, per_publie=None, croissance_sourcee=False) is None
    assert F.compute_fond_score("ABSENT", {"X": FICHE}, per_publie=10, croissance_sourcee=True) is None


def test_une_dette_nette_contestee_suspend_roic_et_bilan():
    F.CONTESTES["X"] = "grandeur contestée (essai)"
    try:
        d = F.detail_fond_score("X", {"X": FICHE}, per_publie=10, croissance_sourcee=True)
        assert d["composantes"]["qualite"]["note"] is None and d["composantes"]["bilan"]["note"] is None
        assert F.ratio_effectif(FICHE, "X", "roic") is None                 # alertes et écran aussi
        assert F.ratio_effectif(FICHE, "X", "dette_nette_ebitda") is None
    finally:
        F.CONTESTES.pop("X", None)
