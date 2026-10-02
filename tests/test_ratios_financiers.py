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


def test_la_note_fondamentale_ne_lit_que_les_trois_ratios_approuves():
    """Jusqu'au 01/10/2026 la note ne lisait aucun de ces ratios. Abd Moutalib
    a approuvé (R8) qu'elle lise ROIC, dette nette / EBITDA et conversion de
    trésorerie calculés ; le ROE et les autres restent hors de la note tant
    qu'aucune mesure ni accord ne les y fait entrer."""
    import re
    src = (RACINE / "pipeline" / "smart_money" / "fond_score.py").read_text(encoding="utf-8")
    lus = set(re.findall(r'ratio_effectif\(f, sym, "(\w+)"\)', src))
    assert lus == {"roic", "dette_nette_ebitda", "cash_conversion"}
    # 02/10/2026 (lot 1) : le ROE publié entre dans la note des SEULES
    # financières, par `roe_effectif`, et nulle part ailleurs.
    assert src.count('"roe_12m"') == 1 and src.count('"roe_2025"') == 1
    assert "if est_financiere(f):\n        _roe = roe_effectif(f, sym)" in src


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
    # VCNE : titres de placement de nature non tranchée → pas de dette nette.
    # (GAZ l'était aussi, pour une dette locative non identifiable : levée le
    # 01/10 en lisant la note 14 sur image, voir test_gaz_...)
    for s in ("VCNE",):
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


def test_seuls_les_trois_ratios_approuves_font_bouger_la_note():
    """Retirer ratios_publies ne change la note QUE d'un titre portant un
    ROIC, une dette nette / EBITDA ou une conversion calculés — et jamais de
    MSA, tenu à l'écart (décision du 01/10/2026, R8)."""
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
            rp = f.get("ratios_publies") or {}
            fin = str(f.get("secteur") or "").startswith(("Banque", "Assurance", "Finance"))
            # « dette_nette » depuis le 02/10 : lue quand elle est négative et
            # qu'aucun ratio dette / EBITDA n'existe (trésorerie nette).
            cles = ("roe_12m", "roe_2025") if fin else ("roic", "dette_nette_ebitda", "cash_conversion", "dette_nette")
            lu = s != "MSA" and any(
                isinstance(rp.get(k), dict) and isinstance(rp[k].get("valeur"), (int, float))
                for k in cles)
            if not lu:
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


def test_roe_bancaires_sur_bilans_reboucles():
    """Capitaux propres part du groupe des banques, chacun rebouclé par
    l'arithmétique du bilan déposé. BOA 12,0 et BMCI 5,7 = yuna ; ATW,
    CDM, BCP diffèrent de yuna (convention non identifiée, signalée)."""
    # BOA : 3 813,552 ÷ 31 794,360 = 11,99 % ; BMCI : 434,829 ÷ 7 572,464 = 5,74 %
    assert (_r("BOA", "roe_2025"), _r("BMC", "roe_2025")) == (12.0, 5.7)
    # ATW : 10 644,852 ÷ 69 431,269 = 15,33 % ; BCP : 4 503,361 ÷ 36 974,989 = 12,18 %
    assert (_r("ATW", "roe_2025"), _r("BCP", "roe_2025")) == (15.3, 12.2)


# ── Lot « ratios de bilan 2 » (01/10/2026) : titres sans ratio jusque-là ──
# Attendus calculés à la main depuis les états déposés (pages dans
# pipeline/faits_financiers.json), pas relus dans la sortie du module.

def test_oulmes_quatre_ratios_a_la_main():
    # dette = 1 657,237 + 657,269 = 2 314,506 ; dette nette = 2 314,506 − 134,320 = 2 180,186
    assert _r("OUL", "dette_nette") == 2180.2
    # EBITDA consolidé publié 605,5 (recoupé : 285,335 + 320,124 = 605,459) ; 2 180,186 ÷ 605,5 = 3,60
    assert _r("OUL", "ebitda") == 605.5 and _r("OUL", "dette_nette_ebitda") == 3.6
    # RAI dérivé 185,308 − 5,386 = 179,922 ; impôt 76,138 − 12,370 = 63,768 ; t = 35,44 %
    # 285,335 × 0,6456 ÷ (809,5 + 2 180,186) = 6,16 %
    assert _r("OUL", "roic") == 6.2
    # 183,629 ÷ 116,155 = 158,1 %
    assert _r("OUL", "cash_conversion") == 158.1
    # la valeur saisie en juin (0,57) est incompatible avec ce bilan et n'a pas été touchée
    assert FOND["OUL"]["dette_nette_ebitda"] == 0.57


def test_imiter_base_sociale_dite_et_conversion_absente_avec_son_motif():
    rp = FOND["SMI"]["ratios_publies"]
    # 34,684488 + 0,196120 − 10,957381 = 23,923227 ; ÷ EBE 864,051358 = 0,0277
    assert rp["dette_nette"]["valeur"] == 23.9 and rp["dette_nette_ebitda"]["valeur"] == 0.03
    # t = 191,056147 ÷ 588,164741 = 32,48 % ; 615,038858 × 0,67516 ÷ (1 660,223158 + 23,923227) = 24,66 %
    assert rp["roic"]["valeur"] == 24.7
    assert "SOCIAL" in rp["roic"]["base"]
    # pas de tableau des flux de trésorerie dans des comptes sociaux marocains
    assert "cash_conversion" not in rp and "tableau des flux" in rp["non_calcules_2025"]["cash_conversion"]


def test_un_resultat_net_minuscule_n_est_pas_converti():
    # Lesieur : résultat net de l'ensemble 5 MMAD, arrondi au million → pas de ratio
    rp = FOND["LES"]["ratios_publies"]
    assert "cash_conversion" not in rp and "arrondi" in rp["non_calcules_2025"]["cash_conversion"]
    # dette retenue 1 + 296 + 176 = 473 (et non les 1 109 du bilan, qui contiennent 634 de dérivés)
    assert rp["dette_nette"]["valeur"] == 4.0          # 473 − 469


def test_mutandis_ecart_avec_la_dette_nette_publiee_est_consigne():
    # 931,815 + 94,706 + 222,429 − (200,480 + 59,248) = 989,222
    assert _r("MUT", "dette_nette") == 989.2
    e = FAITS["MUT"]
    assert e["faits"]["endettement_net"]["valeur"] == 828.0     # chiffre de la société, non utilisé
    assert e["_ecarts_mesures"]["dette_nette"]["rapport"] == 828.0 and "161" in e["_ecarts_mesures"]["dette_nette"]["ecart"]


def test_lot_2_chaque_fait_porte_page_unite_et_citation_et_les_controles_passent():
    nouveaux = ("ARD", "CTM", "GAZ", "IMI", "LES", "MUT", "OUL", "SMI", "SRM")
    for s in nouveaux:
        e = FAITS[s]
        assert e["_controles_ratios_2025"]["controles"], s
        for c in e["_controles_ratios_2025"]["controles"]:
            assert c["ok"], (s, c)
        for k, x in e["faits"].items():
            if x.get("releve_le") != "2026-10-01":
                continue
            assert isinstance(x.get("page"), int) and x.get("unite_au_rapport"), (s, k)
            assert "«" in x.get("note", "") or x.get("composantes"), (s, k)


def test_gaz_doute_leve_par_la_note_14_lue_sur_image():
    # Note 14 (p.133-134, image) : dettes de financement 1 061,912 + 132,631 = 1 194,543
    # DONT 601,158 de dettes de location ; + banques créditrices 318,011 = 1 512,554 ;
    # − trésorerie 1 039,041 = 473,513 (la société écrit « trésorerie nette 473 513 »)
    assert _r("GAZ", "dette_nette") == 473.5
    # EBITDA publié 1 576,721 = REX 1 166,687 + dotations 410,034 ; 473,513 ÷ 1 576,721 = 0,300
    assert _r("GAZ", "dette_nette_ebitda") == 0.3
    # t = 394,403 ÷ 1 067,008 = 36,96 % ; 1 166,687 × 0,6304 ÷ (3 387,010 + 473,513) = 19,05 %
    assert _r("GAZ", "roic") == 19.1
    # 804,904 ÷ 750,500 = 107,2 %
    assert _r("GAZ", "cash_conversion") == 107.2


# ── Règle des titres de placement — 02/10/2026 (verificateur-finance) ─────
# Trésorerie = disponibilités + titres de placement ; dette nette « stricte »
# publiée à côté. Attendus calculés à la main depuis les faits relevés.

def test_les_titres_de_placement_comptent_dans_la_tresorerie():
    rp = FOND["NEJ"]["ratios_publies"]["dette_nette"]
    # 636,535 − 92,131 = 544,404 (stricte) ; − 363,226 de placements = 181,178
    assert rp["valeur"] == 181.2 and rp["dette_nette_stricte"] == 544.4
    assert FOND["COL"]["ratios_publies"]["dette_nette"]["valeur"] == -119.4


def test_capitaux_employes_residuels_pas_de_roic():
    # DAR : 366,807 + (−365,7) ≈ 1,1 MMAD pour 683,177 d'actif : < 10 %
    assert "roic" not in FOND["DAR"]["ratios_publies"]
    assert "roic" in FOND["DAR"]["ratios_publies"]["non_calcules_2025"]
