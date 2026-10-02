"""Les comptes semestriels 2026 dans les fondamentaux — 29/09/2026.

Attendus écrits À LA MAIN, depuis les montants du dépôt AMMC — pas recalculés
avec la fonction testée.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

from pipeline.resultats_semestriels import appliquer, douze_mois  # noqa: E402

JEU = json.loads((RACINE / "datasets" / "resultats_s1_2026.json").read_text(encoding="utf-8"))


def test_hps_douze_mois_a_la_main():
    # 105,78 + 34,811645 − (−47,254113) = 187,845758 MDH ; ÷ 7 406 190 = 25,36
    m = douze_mois(JEU["titres"]["HPS"])
    assert m["rnpg_12m"] == 187.846
    assert m["bpa_12m"] == 25.36


def test_une_base_negative_prend_la_croissance_publiee():
    """HPS passe d'une perte à un bénéfice : 34,8 ÷ (−47,3) − 1 donnerait
    −174 %, une « baisse » absurde. On reprend le +173,7 % de l'émetteur."""
    assert douze_mois(JEU["titres"]["HPS"])["croissance_bpa"] == 173.7


def test_cosumar_recule():
    # 333 ÷ 387 − 1 = −13,95 % ; 4 825 ÷ 5 362 − 1 = −10,01 %
    m = douze_mois(JEU["titres"]["CSR"])
    assert m["croissance_bpa"] == -14.0 and m["croissance_ca"] == -10.0


def test_risma_hors_elements_exceptionnels():
    """Les +169 MDH de cessions ne doivent pas entrer dans le résultat
    récurrent : 269,622 + 144 − 118 = 295,622, pas 269,622 + 313 − 135."""
    assert douze_mois(JEU["titres"]["RIS"])["rnpg_12m"] == 295.622


def test_une_valeur_manquante_ne_se_comble_pas():
    t = dict(JEU["titres"]["CSR"], rnpg_exercice_2025=None)
    assert douze_mois(t) is None


def test_le_bpa_faux_de_cfg_bank_est_corrige_et_l_ancien_garde():
    # 370,445 MDH ÷ 35 007 960 actions = 10,58 DH — le fichier portait 18.
    bpa = {"CFGB": {"bpa": 18}}
    appliquer({"fin_periode": "2026-06-30", "titres": {"CFGB": JEU["titres"]["CFGB"]}}, bpa, {})
    assert bpa["CFGB"]["bpa"] == 10.58
    assert bpa["CFGB"]["bpa_avant_2026_09_29"] == 18


def test_les_anciennes_valeurs_sont_conservees():
    fond = {"CSR": {"croissance_bpa": -17.2, "croissance_ca": 2.4, "forward_per": 17.2}}
    appliquer({"fin_periode": "2026-06-30", "titres": {"CSR": JEU["titres"]["CSR"]}}, {}, fond)
    assert fond["CSR"]["avant_2026_09_29"]["croissance_bpa"] == -17.2
    # ⚠️ Ce qui ne se lit pas dans un semestriel n'est pas touché.
    assert fond["CSR"]["forward_per"] == 17.2


def test_chaque_chiffre_porte_son_document_et_sa_page():
    for s, t in JEU["titres"].items():
        assert t["url"].startswith("https://www.ammc.ma/"), s
        assert t.get("pages"), s
        assert t.get("source_actions"), s


def test_les_fichiers_publies_portent_les_douze_mois():
    bpa = json.loads((RACINE / "bpa.json").read_text(encoding="utf-8"))
    assert bpa["MNG"]["bpa_12m"] == 53.94      # (3 002 + 3 778 − 380) ÷ 118,65 M
    assert bpa["CFGB"]["bpa"] == 10.58
    assert bpa["SGTM"]["bpa"] == 22.37         # 1 342 ÷ 60 M, pas 37


def test_le_per_ne_vaut_jamais_zero():
    from update_data import _per
    assert _per(100, None) is None and _per(0, 5) is None
    assert _per(626, 25.36) == 24.7


# ── Lot 2 — 29/09/2026 ─────────────────────────────────────────────────────

def test_maroc_leasing_n_est_plus_marsa_maroc():
    """La fiche MRL se disait « Alias MSA » et portait les 73 395 600 actions
    de Marsa Maroc. Deux sociétés distinctes — MSA/MUT est la confusion que
    CLAUDE.md interdit, MSA/MRL en était une autre."""
    fond = json.loads((RACINE / "fondamentaux.json").read_text(encoding="utf-8"))
    assert fond["MRL"]["nb_actions"] == 2776768
    assert fond["MRL"]["nb_actions"] != fond["MSA"]["nb_actions"]
    assert not (fond["MRL"].get("note") or "").startswith("Alias MSA")
    bpa = json.loads((RACINE / "bpa.json").read_text(encoding="utf-8"))
    # 107,295 MDH ÷ 2 776 768 = 38,64
    assert bpa["MRL"]["bpa"] == 38.64


def test_trois_bpa_secondaires_remplaces_par_le_depot():
    # 85,457932 ÷ 1,885762 = 45,32 ; 307,19143 ÷ 87,6 = 3,51 ; 750,5 ÷ 3,4375 = 218,33
    bpa = json.loads((RACINE / "bpa.json").read_text(encoding="utf-8"))
    assert (bpa["DSW"]["bpa"], bpa["DHO"]["bpa"], bpa["GAZ"]["bpa"]) == (45.32, 3.51, 218.33)
    assert (bpa["DSW"]["bpa_avant_2026_09_29"], bpa["GAZ"]["bpa_avant_2026_09_29"]) == (56.43, 266.9)


def test_cih_est_ecarte_faute_de_piece():
    """Le dépôt dit 35,6 M d'actions au 30/06, le marché en implique 39,2 M
    aujourd'hui. Sans pièce, R11 : on n'écrit rien."""
    assert "CIH" not in JEU["titres"] and "CIH" in JEU["_ecartes"]


def test_cmgp_et_vicenne_sur_piece():
    """Lot 3 : deux BPA de source secondaire, trop hauts d'environ 40 %."""
    bpa = json.loads((RACINE / "bpa.json").read_text(encoding="utf-8"))
    # 244 ÷ 17 000 900 = 14,35 ; 144,284126 ÷ 10 258 850 = 14,06
    assert (bpa["CMGP"]["bpa"], bpa["VCNE"]["bpa"]) == (14.35, 14.06)


def test_banques_et_assureurs_sur_piece():
    """Lot 4. Attendus calculés à la main depuis les dépôts AMMC."""
    bpa = json.loads((RACINE / "bpa.json").read_text(encoding="utf-8"))
    # AtlantaSanad, CONSOLIDÉ depuis le 02/10 (verificateur-finance) :
    # 467,639 + 288,218 − 276,054 = 479,803 MDH ÷ 60 283 595 = 7,959 → 7,96.
    # L'ancien 1,99 supposait un bénéfice annuel de 100 MDH, inférieur à un
    # seul semestre (273 MDH) : impossible.
    assert bpa["ATL"]["bpa_12m"] == 7.96 and bpa["ATL"]["bpa_avant_2026_09_29"] == 1.99
    # Wafa Assurance : 1 026,036 ÷ 3 500 000 = 293,15 (l'ancien divisait par 4,18 M)
    assert bpa["WAF"]["bpa"] == 293.15
    # BOA : 3 813,552 ÷ 220 281 881 = 17,31
    assert bpa["BOA"]["bpa"] == 17.31
    # BCP, résultat S1 IMPRIMÉ depuis le 02/10 : 4 503,361 + 3 218,498 −
    # 2 915,647 = 4 806,212 ÷ 203 312 473 = 23,64
    assert bpa["BCP"]["bpa_12m"] == 23.64
    # BMCI : 434,829 + 352,528 − 222,773 = 564,584 ÷ 13 279 286 = 42,52
    assert bpa["BMC"]["bpa_12m"] == 42.52


def test_variation_publiee_sans_montant_reprise_telle_quelle():
    """BCP ne publie que « PNB consolidé −3,2 % ». La croissance de l'exercice
    (+5,4 %) ne doit pas rester en place comme si elle était celle du semestre."""
    fond = json.loads((RACINE / "fondamentaux.json").read_text(encoding="utf-8"))
    assert fond["BCP"]["croissance_ca"] == -3.2


def test_sanlam_ecarte_pour_fusion():
    """Bénéfices d'avant la fusion avec Allianz, actions d'après : pas de BPA."""
    assert "SAF" not in JEU["titres"] and "Allianz" in JEU["_ecartes"]["SAF"]


def test_lot5_grandes_valeurs_sur_piece():
    """Lot 5. Attendus calculés à la main depuis les dépôts AMMC."""
    bpa = json.loads((RACINE / "bpa.json").read_text(encoding="utf-8"))
    # CDM : 863,551 + 531,692 − 445,147 = 950,096 ÷ 11 626 499 = 81,72
    # (actions APRÈS l'augmentation de capital de 745 285 titres)
    assert bpa["CDM"]["bpa_12m"] == 81.72
    # IAM : 6 969 + 2 482 − 4 117 = 5 334 ÷ 879 095 340 = 6,07 — la recette
    # exceptionnelle du S1 2025 sort avec le semestre soustrait.
    assert bpa["IAM"]["bpa_12m"] == 6.07
    # EQD : 98,561 ÷ 1 670 250 = 59,01 (l'ancien 123,33 était du double)
    assert bpa["EQD"]["bpa"] == 59.01
    # CASH : 242,296 ÷ 24 553 090 = 9,87
    assert bpa["CASH"]["bpa"] == 9.87


def test_iam_croissance_hors_exceptionnel():
    """−39,7 % brut ; +8,1 % publié hors recette exceptionnelle. On retient
    ce que l'émetteur publie, et le dataset le dit."""
    fond = json.loads((RACINE / "fondamentaux.json").read_text(encoding="utf-8"))
    assert fond["IAM"]["croissance_bpa"] == 8.1
    assert "exceptionnelle" in JEU["titres"]["IAM"]["pages"]


def test_une_societe_en_perte_n_a_pas_de_per():
    """SNEP : perte de 185 MDH en 2025 ; l'ancien BPA de +117,5 affichait un
    PER de 2,6. Un BPA négatif ne produit aucun PER, jamais un nombre."""
    from update_data import _per
    assert _per(300, -60.06) is None and _per(300, 0) is None
    bpa = json.loads((RACINE / "bpa.json").read_text(encoding="utf-8"))
    # −185,186 − 50,029 + 91,075 = −144,14 MDH ÷ 2 400 000 = −60,06
    assert bpa["SNP"]["bpa_12m"] == -60.06 and bpa["SNP"]["bpa_avant_2026_09_29"] == 117.5


def test_lot6_sur_piece():
    bpa = json.loads((RACINE / "bpa.json").read_text(encoding="utf-8"))
    # ARD : 534,413 ÷ 12 568 130 = 42,52 (yuna : 42,54)
    # MOX : 15,447 ÷ 812 500 = 19,01 (consolidé ; le social est une autre base)
    # SLM : 96,117 ÷ 3 124 119 = 30,77
    assert (bpa["ARD"]["bpa"], bpa["MOX"]["bpa"], bpa["SLM"]["bpa"]) == (42.52, 19.01, 30.77)


def test_le_controle_refuse_toujours_un_bpa_negatif_sans_piece():
    """La garde du 13/06 reste bloquante ; seule une perte documentée passe."""
    import importlib, sys as _s
    _s.path.insert(0, str(RACINE / "pipeline"))
    src = (RACINE / "pipeline" / "validate.py").read_text(encoding="utf-8")
    assert 'bpa < 0 and not v.get("perte_documentee")' in src
    bpa = json.loads((RACINE / "bpa.json").read_text(encoding="utf-8"))
    assert "SNEP_2025.pdf" in bpa["SNP"]["perte_documentee"]
    assert all(v.get("perte_documentee") for v in bpa.values()
               if isinstance(v, dict) and (v.get("bpa") or 0) < 0)


def test_lot7_communiques_lus_et_recoupes():
    """Lot 7 — chiffres lus dans des communiqués (graphiques lus sur l'image
    quand le texte ne les porte pas). Recoupés sur yuna.ma : OUL 56,72 et
    MIC 41,37 identiques ; SBS 121,32 / 121,22 ; DTT 25,94 / 25,85."""
    bpa = json.loads((RACINE / "bpa.json").read_text(encoding="utf-8"))
    # OUL : 112,3 ÷ 1 980 000 = 56,72 ; MIC : 69,5 ÷ 1 680 000 = 41,37
    assert (bpa["OUL"]["bpa"], bpa["MIC"]["bpa"]) == (56.72, 41.37)
    # SBS : 343 + 79,9 − 87,3 = 335,6 ÷ 2 829 653 = 118,60
    assert bpa["SBS"]["bpa_12m"] == 118.6
    # DTT : exercice 2025 lu au RFA p.25 depuis le 02/10 (verificateur-finance) :
    # 25,878 + 16,1 − 12,5 = 29,478 ÷ 998 110 = 29,53
    assert bpa["DTT"]["bpa_12m"] == 29.53


def test_lot8_fnb_uni_inv_hal():
    bpa = json.loads((RACINE / "bpa.json").read_text(encoding="utf-8"))
    # HAL : 99,832 + 64,8 − 47,3 = 117,332 ÷ 54 140 578 = 2,17 ; ROE 2025
    # 99,832 ÷ 1 445,976 = 6,9 % (yuna : 6,9)
    assert bpa["HAL"]["bpa_12m"] == 2.17
    # UNI : 11 + 29 − (−40) = 80 ÷ 11 413 880 = 7,01
    assert bpa["UNI"]["bpa_12m"] == 7.01
    # INV : exercice 2025 lu au rapport (0,116, p.35) depuis le 02/10, au lieu
    # de l'arrondi 0,1 : 0,116 − 3,8 − 2,8 = −6,484 ÷ 382 716 = −16,94
    assert bpa["INV"]["bpa_12m"] == -16.94 and bpa["INV"]["perte_documentee"]
    fond = json.loads((RACINE / "fondamentaux.json").read_text(encoding="utf-8"))
    assert fond["HAL"]["ratios_publies"]["roe_2025"]["valeur"] == 6.9


def test_lot9_akdital_tgcc_lesieur():
    bpa = json.loads((RACINE / "bpa.json").read_text(encoding="utf-8"))
    # AKD part du groupe : 444 + 225 − (214,226312 − 20,096114) = 474,87
    # ÷ 14 159 207 = 33,54 ; ROE 2025 = 444 ÷ 2 853,529 = 15,6 % (yuna : 15,6)
    assert bpa["AKD"]["bpa_12m"] == 33.54
    # TGCC : 952 ÷ 34 674 332 = 27,46 (actions confirmées par le rapport
    # annuel : 34 674 300) — l'ancien 65 était faux
    assert bpa["TGCC"]["bpa"] == 27.46 and bpa["TGCC"]["bpa_avant_2026_09_29"] == 65
    # LES : 8 − 47 − 12 = −51 ÷ 27 631 510 = −1,85 — en perte
    assert bpa["LES"]["bpa_12m"] == -1.85 and bpa["LES"]["perte_documentee"]


def test_ciments_du_maroc_valeur_deposee_et_non_retraitee():
    """Le S1 2025 retenu est la valeur DÉPOSÉE (600 998), pas le comparatif
    à périmètre retraité (671 845) du même dépôt. 1 377,432 + 514,218 −
    600,998 = 1 290,652 ÷ 14 436 004 = 89,41 ; ROE 2025 = 1 377,432 ÷
    3 739,311 = 36,8 % (yuna : 36,8)."""
    bpa = json.loads((RACINE / "bpa.json").read_text(encoding="utf-8"))
    assert bpa["CIM"]["bpa_12m"] == 89.41
    fond = json.loads((RACINE / "fondamentaux.json").read_text(encoding="utf-8"))
    assert fond["CIM"]["ratios_publies"]["roe_2025"]["valeur"] == 36.8


def test_lot12_six_integres_trois_ecartes():
    """Lot 12 (30/09/2026). Attendus calculés à la main depuis les dépôts."""
    bpa = json.loads((RACINE / "bpa.json").read_text(encoding="utf-8"))
    # ALU : 62,406 + 41,026 − 31,321 = 72,111 ÷ 465 954 = 154,76 ;
    # exercice 62,406 ÷ 465 954 = 133,93 (yuna : 133,94) — l'ancien 146 gardé
    assert bpa["ALU"]["bpa_12m"] == 154.76
    assert bpa["ALU"]["bpa"] == 133.93 and bpa["ALU"]["bpa_avant_2026_09_29"] == 146.0
    # BAL consolidé : 13,650 ÷ 1 744 000 = 7,83 (BPA publié 7,83) ;
    # 13,650 + 7,514 − 6,529 = 14,634 ÷ 1 744 000 = 8,39
    assert bpa["BAL"]["bpa"] == 7.83 and bpa["BAL"]["bpa_12m"] == 8.39
    # DAR : 52,395 + 27,937 − 25,926 = 54,406 ÷ 298 375 = 182,34
    assert bpa["DAR"]["bpa_12m"] == 182.34
    # NEJ consolidé (pas le social de yuna) : 324,182 + 114,401 − 146,966
    # = 291,617 ÷ 1 023 264 = 284,99
    assert bpa["NEJ"]["bpa_12m"] == 284.99
    # RDS : 4,494 ÷ 26 208 850 = 0,17 — l'ancien BPA « 5 » était faux d'un
    # facteur 30 ; 4,494 + 19,747 − 6,465 = 17,776 → 0,68
    assert bpa["RDS"]["bpa"] == 0.17 and bpa["RDS"]["bpa_avant_2026_09_29"] == 5
    assert bpa["RDS"]["bpa_12m"] == 0.68
    # ZLD : 21,588 ÷ 572 849 = 37,69 (titre sans BPA jusqu'ici)
    assert bpa["ZLD"]["bpa"] == 37.69
    # Écartés, motif consigné : deux états qui se contredisent (JET), une
    # part du groupe jamais publiée (M2M), une réserve qui excède le
    # bénéfice (STK).
    for s in ("JET", "M2M", "STK"):
        assert s not in JEU["titres"] and s in JEU["_ecartes"], s
    assert "91 509 542,52" in JEU["_ecartes"]["JET"]
    assert "réserve" in JEU["_ecartes"]["STK"]
