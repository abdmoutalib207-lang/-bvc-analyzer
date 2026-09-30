"""Ratios de rentabilité calculés sur comptes publiés — 30/09/2026.

Attendus calculés à la main depuis les dépôts AMMC ; recoupés avec yuna.ma
(ROE affiché) : CSR 12,5, MNG 26,2, HPS 13,0, GAZ 22,2, ATL 18,8, RIS 16,0,
DSW 12,5, WAF 6,9, ARD 9,8 — identiques au dixième.
"""

import json
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
FOND = json.loads((RACINE / "fondamentaux.json").read_text(encoding="utf-8"))


def _r(s, k):
    return FOND[s]["ratios_publies"][k]["valeur"]


def test_roe_2025_sur_comptes_publies():
    # MNG : 3 002 ÷ 11 478,3 = 26,15 % (yuna : 26,2)
    assert _r("MNG", "roe_2025") == 26.2
    # MSA : 1 588,764 ÷ 4 048,149 = 39,25 % — capitaux propres = ensemble
    # consolidé moins minoritaires (4 599 248 − 551 099 KMAD)
    assert _r("MSA", "roe_2025") == 39.2


def test_roe_12_mois_et_marge():
    # GAZ : (750,5 + 370,154 − 368,29) ÷ 3 155,598 = 23,85 %
    assert _r("GAZ", "roe_12m") == 23.8
    # LBV : 370,1705865 ÷ 10 192,528 = 3,63 %
    assert _r("LBV", "marge_nette_s1_2026") == 3.6


def test_une_perte_donne_un_roe_negatif_pas_une_absence():
    assert _r("SNP", "roe_2025") == -38.0


def test_chaque_ratio_porte_sa_date_et_ses_sources():
    for s, f in FOND.items():
        for k, x in ((f or {}).get("ratios_publies") or {}).items():
            if k == "calcule_le":
                continue
            assert x["date"] and x["formule"] and any(x["sources"].values()), (s, k)


def test_la_note_fondamentale_ne_lit_pas_ces_ratios():
    """Aucune note ne change avec ce calcul (R8)."""
    src = (RACINE / "pipeline" / "smart_money" / "fond_score.py").read_text(encoding="utf-8")
    assert "ratios_publies" not in src and '"roe"' not in src
