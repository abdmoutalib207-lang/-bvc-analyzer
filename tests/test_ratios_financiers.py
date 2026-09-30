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
            if k in ("calcule_le", "non_calcules_2025", "ratios_bilan_2025"):
                continue
            assert x["date"] and x["formule"] and any(x["sources"].values()), (s, k)


def test_la_note_fondamentale_ne_lit_pas_ces_ratios():
    """Aucune note ne change avec ce calcul (R8)."""
    src = (RACINE / "pipeline" / "smart_money" / "fond_score.py").read_text(encoding="utf-8")
    assert "ratios_publies" not in src and '"roe"' not in src


# ── Ratios de bilan 2025 — dette nette, EBITDA, ROIC, conversion ─────────
# Attendus recalculés à la main depuis les faits relevés (pages citées dans
# pipeline/faits_financiers.json), pas relus dans la sortie du module.

import sys
sys.path.insert(0, str(RACINE / "pipeline"))
from ratios_financiers import calculer_bilan, est_financier  # noqa: E402

FAITS = json.loads((RACINE / "pipeline" / "faits_financiers.json").read_text(encoding="utf-8"))


def test_marsa_dette_nette_egale_l_endettement_net_publie():
    # 1 367,295 − (154,902 + 1 965,022) = −752,629 ; la note 12 du rapport
    # publie « Endettement net - 752 628 » : concordance au millier près.
    assert _r("MSA", "dette_nette") == -752.6
    assert abs(_r("MSA", "dette_nette") - FAITS["MSA"]["faits"]["endettement_net"]["valeur"]) < 0.1


def test_cosumar_quatre_ratios_a_la_main():
    # dette nette 23,4 + 1 090,5 − 832,0 = 281,9 (et non une trésorerie nette)
    assert _r("CSR", "dette_nette") == 281.9
    # 281,9 ÷ EBE publié 1 668,0 = 0,169
    assert _r("CSR", "dette_nette_ebitda") == 0.17
    # t = 384,6 ÷ 1 088,7 = 35,33 % ; 1 145,4 × 0,6467 ÷ (5 641,4 + 281,9) = 12,51 %
    assert _r("CSR", "roic") == 12.5
    # 1 551,5 ÷ 704,1 = 220,35 %
    assert _r("CSR", "cash_conversion") == 220.4


def test_hps_ebitda_publie_prioritaire():
    # (452,171904 + 40,0 − 296,133526) ÷ 286 = 0,685
    assert FOND["HPS"]["ratios_publies"]["ebitda"]["origine"] == "publié"
    assert _r("HPS", "dette_nette_ebitda") == 0.69


def test_une_perte_ne_fabrique_ni_impot_ni_ratio_absurde():
    rp = FOND["SNP"]["ratios_publies"]
    # RAI −172,788 ≤ 0 → t = 0 ; −133,729 ÷ (487,051 + 815,038) = −10,27 %
    assert rp["roic"]["valeur"] == -10.3 and rp["roic"]["taux_impot_effectif"] == 0.0
    # EBITDA −31,751 et résultat net −185,186 : pas de ratio, une raison
    assert "dette_nette_ebitda" not in rp and "cash_conversion" not in rp
    assert "négatif" in rp["non_calcules_2025"]["dette_nette_ebitda"]
    assert "≤ 0" in rp["non_calcules_2025"]["cash_conversion"]


def test_les_financieres_sont_sans_objet_et_rien_n_est_calcule():
    for s in ("ATW", "BCP", "CIH", "WAF", "EQD", "CASH", "ATL", "AFM"):
        rp = FOND[s]["ratios_publies"]
        assert rp["ratios_bilan_2025"]["sans_objet"] == "sans objet : établissement financier", s
        assert not {"dette_nette", "ebitda", "roic", "cash_conversion"} & set(rp), s


def test_un_doute_declare_empeche_le_calcul():
    # GAZ : dette locative non identifiable → pas de dette nette ; VCNE :
    # titres de placement de nature non tranchée → idem.
    for s in ("GAZ", "VCNE"):
        rp = FOND[s]["ratios_publies"]
        assert "dette_nette" not in rp and "roic" not in rp, s
        assert rp["non_calcules_2025"]["dette_nette"].startswith("doute"), s


def test_calculer_bilan_sur_un_cas_construit():
    def fait(v):
        return {"valeur": v, "page": 1}
    e = {"document": "D", "url": "U", "faits": {
        "dettes_financieres": fait(100), "tresorerie_actif": fait(40),
        "resultat_exploitation": fait(50), "dotations_amortissements_exploitation": fait(10),
        "resultat_avant_impot": fait(40), "impot_resultat": fait(10),
        "capitaux_propres_consolides": fait(200), "flux_tresorerie_exploitation": fait(30),
        "resultat_net_consolide": fait(30)}, "_controles_ratios_2025": {"base": "consolidé"}}
    r, non = calculer_bilan(e)
    assert r["dette_nette"]["valeur"] == 60
    assert r["ebitda"]["valeur"] == 60 and r["ebitda"]["origine"] == "calculé"
    assert r["dette_nette_ebitda"]["valeur"] == 1.0
    assert r["roic"]["valeur"] == 14.4          # 50 × 0,75 ÷ 260 = 14,42 %
    assert r["cash_conversion"]["valeur"] == 100.0
    assert non == {}
    e["_controles_ratios_2025"]["non_calcules"] = {"ebitda": "doute"}
    r, non = calculer_bilan(e)
    assert "ebitda" not in r and non["ebitda"] == "doute"
    assert calculer_bilan({"faits": e["faits"]}) == ({}, {})   # sans contrôles : rien


def test_les_champs_lus_par_la_note_ne_sont_pas_ecrits():
    """R8 : roic, dette_nette_ebitda, cash_conversion de premier niveau restent la saisie."""
    src = (RACINE / "pipeline" / "ratios_financiers.py").read_text(encoding="utf-8")
    for champ in ("roic", "dette_nette_ebitda", "cash_conversion"):
        assert f'fond[sym]["{champ}"]' not in src and f'fiche["{champ}"] =' not in src
    assert est_financier({"secteur": "Banque"}) and not est_financier({"secteur": "Agroalimentaire"})


def test_la_note_fondamentale_est_invariante_par_les_ratios_publies():
    """Retirer ratios_publies ne change aucune note fondamentale (R8)."""
    import copy
    sys.path.insert(0, str(RACINE / "pipeline" / "smart_money"))
    from fond_score import compute_fond_score
    sans = copy.deepcopy(FOND)
    for f in sans.values():
        if isinstance(f, dict):
            f.pop("ratios_publies", None)
    for s, f in FOND.items():
        if isinstance(f, dict):
            assert set(f) - {"ratios_publies"}, f"{s} : fiche créée pour des ratios publiés"
            assert compute_fond_score(s, FOND) == compute_fond_score(s, sans), s


def test_chaque_fait_2025_est_source_et_chaque_controle_passe():
    n = 0
    for s, e in FAITS.items():
        if s.startswith("_") or "_controles_ratios_2025" not in e:
            continue
        for c in e["_controles_ratios_2025"]["controles"]:
            assert c["ok"], (s, c)
        for k, x in e["faits"].items():
            if x.get("releve_le") != "2026-09-30":
                continue
            n += 1
            assert isinstance(x.get("page"), int) and x.get("unite_au_rapport"), (s, k)
            assert "«" in x.get("note", "") or x.get("composantes"), (s, k)
    assert n >= 200, n
