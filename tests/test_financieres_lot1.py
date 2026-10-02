"""Lot 1 des rectifications — les sociétés financières (02/10/2026).

Une banque n'a ni ROIC, ni dette nette / EBITDA, ni conversion de trésorerie :
sa rentabilité se lit sur le ROE publié, comparé à un coût des fonds propres
de référence de 10 % (hypothèse déclarée). Attendus calculés À LA MAIN :

    note = qualité×0,40 + croissance×0,30 + valorisation×0,20 + bilan×0,10
    croissance nulle → 4,5 ; PER 15 → 7,0 ; bilan financier non évalué → 5,0
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pipeline.smart_money import fond_score as F  # noqa: E402

BASE = {"secteur": "Banque", "croissance_bpa": 0, "croissance_ca": 0,
        "forward_per": 15, "wacc": 10, "roic": 22.8,
        "dette_nette_ebitda": 0.0, "cash_conversion": 55}


def _banque(**kw):
    return {"X": dict(BASE, **kw)}


def test_le_roic_saisi_n_est_plus_lu_pour_une_banque():
    # ROIC saisi 22,8 (écart 12,8 → 8,5 avant). Sans ROE publié : 5,0.
    # 5,0×0,40 + 4,5×0,30 + 7,0×0,20 + 5,0×0,10 = 2,0 + 1,35 + 1,4 + 0,5 = 5,25
    assert F.compute_fond_score("X", _banque()) == 5.25


def test_le_roe_publie_juge_la_rentabilite():
    # ROE 15,3 → écart 5,3 → 7,0 : 2,8 + 1,35 + 1,4 + 0,5 = 6,05
    f = _banque(ratios_publies={"roe_2025": {"valeur": 15.3, "date": "2025-12-31"}})
    assert F.compute_fond_score("X", f) == 6.05


def test_le_roe_douze_mois_prime_sur_l_exercice():
    # ROE 12 mois 11,7 → écart 1,7 → 5,0 (même si l'exercice donnait 15,3)
    f = _banque(ratios_publies={"roe_2025": {"valeur": 15.3},
                                "roe_12m": {"valeur": 11.7}})
    assert F.compute_fond_score("X", f) == 5.25


def test_une_assurance_suit_la_meme_regle():
    f = {"X": dict(BASE, secteur="Assurance",
                   ratios_publies={"roe_2025": {"valeur": 6.9}})}
    # ROE 6,9 → écart −3,1 → 2,0 : 0,8 + 1,35 + 1,4 + 0,5 = 4,05
    assert F.compute_fond_score("X", f) == 4.05


def test_ratios_sans_objet_pour_une_financiere_meme_publies():
    f = dict(BASE, ratios_publies={"roic": {"valeur": 30.0}})
    for cle in ("roic", "dette_nette_ebitda", "cash_conversion"):
        assert F.ratio_effectif(f, "X", cle) is None


def test_une_societe_industrielle_n_est_pas_touchee():
    f = {"X": dict(BASE, secteur="Industrie", ratios_publies={"roe_2025": {"valeur": 40.0}})}
    # ROIC saisi 22,8 → écart 12,8 → 8,5 ; dette 0 → 8,5 ; conversion 55 → 8,5
    # 3,4 + 1,35 + 1,4 + 0,85 = 7,0
    assert F.compute_fond_score("X", f) == 7.0


def test_l_alerte_d_une_banque_ne_parle_plus_de_roic(ud):
    a = ud.detecter_alertes(dict(BASE, roic=5), sym="X")
    assert not any("ROIC" in x["valeur"] for x in a["liste"])


def test_le_roe_d_un_courtier_n_est_pas_lu():
    f = {"AFM": dict(BASE, secteur="Assurance", ratios_publies={"roe_2025": {"valeur": 103.2}})}
    assert F.roe_effectif(f["AFM"], "AFM") is None
    assert F.compute_fond_score("AFM", f) == 5.25   # rentabilité non évaluée


def test_les_roe_verifies_priment_sur_le_calcul_automatique():
    import json
    racine = Path(__file__).resolve().parent.parent
    v = json.loads((racine / "datasets" / "roe_verifies_2026-10-02.json").read_text(encoding="utf-8"))
    fond = json.loads((racine / "fondamentaux.json").read_text(encoding="utf-8"))
    for s, cles in v["titres"].items():
        for k, e in cles.items():
            assert fond[s]["ratios_publies"][k]["valeur"] == e["valeur"], (s, k)
            assert e["sources"]["resultat"] and e["sources"]["capitaux_propres"]
    # CIH, à la main : 1 089,362 ÷ 9 817,628 = 11,096 % → 11,1
    assert v["titres"]["CIH"]["roe_2025"]["valeur"] == 11.1
