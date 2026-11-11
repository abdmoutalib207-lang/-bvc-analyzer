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


# ── 3. RIS (Risma) : capital 2026, BPA 2025 publié, bases S1, exception à la règle c ──

def test_ris_registre_des_deux_emissions_de_2026():
    a, b = bvc_config.HISTORIQUE_ACTIONS["RIS"]["mouvements"]
    assert (a["date"], a["avant"], a["apres"]) == ("2026-02-05", 14326947, 15826947)     # 1 500 000 actions, public
    assert (b["date"], b["avant"], b["apres"]) == ("2026-03-06", 15826947, 16012132)     # 185 185, dirigeants
    assert a["apres"] - a["avant"] == 1500000 and b["apres"] - b["avant"] == 185185
    assert "NO_RISMA_01_2026.pdf p.31" in a["source"] and "CP_Risma_resultats_augmentation_capital.pdf" in a["source"]
    assert "CP_Risma_cloture_augmentation_capital_dirigeants_eligibles.pdf" in b["source"]
    assert "15 826 947" in b["source"] and "16 012 132" in b["source"]
    # Aucune des deux pièces ne publie la date du constat : c'est dit, et la sensibilité est chiffrée.
    for m in (a, b):
        assert m["date_previsionnelle"] is True and "PRÉVISIONNELLE" in m["source"]
    assert "18,68" in b["source"] and "18,69" in b["source"] and "18,73" in b["source"]
    # Exercice 2025 : capital constant. Douze mois : 219 j à 14 326 947 (01/07 → 04/02),
    # 29 j à 15 826 947 (05/02 → 05/03), 117 j à 16 012 132 (06/03 → 30/06).
    assert bvc_config.actions_ponderees("RIS", "2025-01-01", "2025-12-31", 16012132)["nombre"] == 14326947
    assert bvc_config.actions_ponderees("RIS", "2025-07-01", "2026-06-30", 16012132)["nombre"] == \
        round((219 * 14326947 + 29 * 15826947 + 117 * 16012132) / 365) == 14986308


def test_ris_bpa_2025_est_celui_du_rapport_p45():
    b = BPA["RIS"]
    # RFA 2025 p.45 : RNPG 269 622 KMAD, « Nombre moyen d'actions en circulation 14 326 947 ».
    assert b["bpa"] == round(269622000 / 14326947, 2) == 18.82 and b["bpa_avant_2026_11_09"] == 16.84
    assert b["actions_exercice_2025"] == 14326947 and "p.45" in b["source"] and "AMMC" in b["source"]
    assert "14 326 947" in JEU["titres"]["RIS"]["source_exercice_2025"]
    assert "16,84" in b["note_avant_2026_11_09"]                     # l'ancienne note est gardée, pas effacée


def test_ris_publie_comparable_et_pro_forma_ne_se_confondent_plus():
    t = JEU["titres"]["RIS"]
    # CP_Risma_S1_26 p.1 : « RNPG 117 135 313 » = Publié / Comparable / 30 juin 2026 ; « CA 653 754 863 ».
    assert (t["rnpg_publie_s1_2025"], t["rnpg_publie_s1_2026"], t["ca_publie_s1_2025"]) == (117, 313, 653)
    assert t["avant_2026_11_09"]["rnpg_publie_s1_2025"] == 135
    pf = t["proforma_s1_2025"]
    assert (pf["ca"], pf["rnpg"], pf["page"], pf["libelle"]) == (754, 135, 1, "Comparable")
    assert "RNPG 117 135 313" in pf["citation"] and "CP_Risma_S1_26.pdf" in pf["source"]
    # Risma_S1_26 p.4 : seconde base, « Pro forma » — consignée, non retenue.
    autre = pf["autre_base_publiee"]
    assert (autre["ca"], autre["rnpg"], autre["page"]) == (764, 131, 4) and "Risma_S1_26.pdf" in autre["source"]
    # Croissances INCHANGÉES : 144 ÷ 118 − 1 = 22,0 % (règle c, montants de l'émetteur) ;
    # 863 ÷ 754 − 1 = 14,5 % (règle d, périmètre comparable) ; la brute se lit sur le publié.
    m = douze_mois(t, "RIS")
    assert (m["croissance_bpa"], m["croissance_ca"]) == (22.0, 14.5) == \
        (FOND["RIS"]["croissance_bpa"], FOND["RIS"]["croissance_ca"])
    assert m["croissance_bpa_publiee_brute"] == round((313 / 117 - 1) * 100, 1) == 167.5
    assert m["perimetre"]["page"] == 1 and m["perimetre"]["reserve"] is None


def test_ris_douze_mois_hors_non_courants_exception_declaree():
    t = JEU["titres"]["RIS"]
    e = t["exception_regle_c"]
    assert e["rnpg_exercice_2025_hors_non_courants"] == 254.0
    assert "CP_Risma_2025.pdf p.2" in e["source"] and "254 Mdh" in e["source"]
    assert "Sofitel Casablanca Tour Blanche" in e["motif"] and "+169 MDH" in e["motif"]
    assert "CMG" in e["reserve"]
    b = BPA["RIS"]
    # 254 + 144 − 118 = 280 MDH ; ÷ 14 986 308 actions pondérées = 18,68.
    assert (b["rnpg_12m"], b["bpa_12m"], b["actions_12m"]) == (280.0, 18.68, 14986308)
    assert (b["rnpg_12m_avant_2026_11_09"], b["bpa_12m_avant_2026_11_09"]) == (295.622, 18.46)
    x = b["exception_regle_c"]
    assert x["base"] == "hors éléments non courants" and x["formule"] == "254 + 144 − 118 = 280 MDH"
    # Le publié reste consigné : 269,622 + 313 − 117 = 465,622 MDH.
    assert x["rnpg_12m_publie"] == 465.622 and x["bpa_12m_publie"] == round(465.622e6 / 14986308, 2) == 31.07
    assert b["reserve_bpa"].startswith("Exception déclarée à la règle c") and "465,622" in b["reserve_bpa"]


def test_l_exception_a_la_regle_c_ne_s_applique_qu_a_qui_la_declare():
    """Sans le champ explicite, le douze mois reste sur les montants de l'entrée."""
    t = {k: v for k, v in JEU["titres"]["RIS"].items() if k != "exception_regle_c"}
    m = douze_mois(t, "RIS")
    assert m["rnpg_12m"] == 295.622 and "exception_regle_c" not in m and "reserve_bpa" not in m
    declares = sorted(s for s, v in JEU["titres"].items() if v.get("exception_regle_c"))
    assert declares == ["RIS"] == sorted(s for s, v in BPA.items() if v.get("exception_regle_c"))


def test_l_exception_est_publiee_et_affichee_sur_la_fiche():
    moteur = (RACINE / "update_data.py").read_text(encoding="utf-8")
    assert '"pe_exception": (BPA_DATA.get(ticker) or {}).get("exception_regle_c")' in moteur
    src = (RACINE / "terminal.src.html").read_text(encoding="utf-8")
    assert "pe_exception:t.pe_exception" in src                       # la ligne la reçoit de data.json
    assert 'ratio==="pe"&&r.pe_exception&&' in src and "exception : {r.pe_exception.base}" in src
    assert "r.bpa_reserve?`\\n⚠ ${r.bpa_reserve}`" in src            # l'explication du PER porte la réserve


# ── registre HISTORIQUE_ACTIONS : cohérence avec la règle e (IAS 33.19-20) ──

def test_registre_des_actions_coherent_avec_la_regle_e():
    from datetime import date
    for s, e in bvc_config.HISTORIQUE_ACTIONS.items():
        mvts = e["mouvements"]
        assert [m["date"] for m in mvts] == sorted(m["date"] for m in mvts), s
        num = [m for m in mvts if m["nature"] == "numeraire"]
        for m in num:
            date.fromisoformat(m["date"])
            assert 0 < m["avant"] < m["apres"], (s, m["date"])            # une émission AJOUTE des actions
            assert m["source"].count("«") >= 1, (s, m["date"])            # la pièce est citée
            if m.get("date_previsionnelle"):
                assert "PRÉVISIONNELLE" in m["source"], (s, m["date"])
        for a, b in zip(num, num[1:]):
            assert a["apres"] == b["avant"], (s, a["date"], b["date"])    # la chaîne ne saute aucune action
        t, b = JEU["titres"].get(s), BPA.get(s)
        if e.get("denominateur_ambigu") or not t or not num:
            continue
        actuel = t["actions"]
        assert num[-1]["apres"] == actuel, s                              # le dernier nombre est le nombre ACTUEL
        # bpa.json porte le nombre pondéré de CHAQUE période, recalculé ici.
        p25 = bvc_config.actions_ponderees(s, "2025-01-01", "2025-12-31", actuel)["nombre"]
        p12 = bvc_config.actions_ponderees(s, "2025-07-01", "2026-06-30", actuel)["nombre"]
        assert (b["actions_exercice_2025"], b["actions_12m"]) == (p25, p12), s
        # IAS 33.21 : une émission postérieure à la clôture n'entre pas dans la période.
        if num[0]["date"] > "2026-06-30":
            assert p25 == p12 == num[0]["avant"], s
        if num[0]["date"] > "2025-12-31":
            assert p25 == num[0]["avant"], s
        assert num[0]["avant"] <= p25 <= actuel and num[0]["avant"] <= p12 <= actuel, s
        # Le BPA publié se redéduit du résultat et du nombre pondéré.
        assert b["bpa"] == round(t["rnpg_exercice_2025"] * 1e6 / p25, 2), s
        assert b["bpa_12m"] == round(b["rnpg_12m"] * 1e6 / p12, 2), s


# ── 5. Arrondis : les montants de l'état déposé, pas ceux du communiqué ──

def test_tgcc_montants_exacts_de_l_etat():
    t = JEU["titres"]["TGCC"]
    # TGCC_S1_26.pdf p.2 : « Dont part du groupe 434 840 416 623 », « Résultat consolidé 434 840 952 053 ».
    assert (t["rnpg_s1_2026"], t["rnpg_s1_2025"], t["rnpg_exercice_2025"]) == (434.84, 416.623, 952.053)
    assert "Dont part du groupe 434 840 416 623" in t["pages"] and "TGCC_S1_26.pdf p.2" in t["pages"]
    assert "952 053 521 810" in t["source_exercice_2025"] and "TGCC_RFA_2025.pdf p.96" in t["source_exercice_2025"]
    b = BPA["TGCC"]
    # 952 053 + 434 840 − 416 623 = 970 270 KMAD ; ÷ 34 483 118 = 28,137 ; exercice ÷ 32 978 348 = 28,869.
    assert b["rnpg_12m"] == (952053 + 434840 - 416623) / 1000 == 970.27
    assert (b["bpa_12m"], b["bpa"]) == (28.14, 28.87)
    assert (b["bpa_12m_avant_2026_11_09"], b["rnpg_12m_avant_2026_11_09"]) == (28.16, 971.0)
    assert FOND["TGCC"]["croissance_bpa"] == round((434.84 / 416.623 - 1) * 100, 1) == 4.4      # 4,6 sur 435 ÷ 416


def test_sot_douze_mois_au_kmad_et_commentaire_du_split():
    t = JEU["titres"]["SOT"]
    # Sothema_S1_26.pdf p.2 : « Part du groupe 215 072 193 702 » ; exercice 385 526 (RFA p.53).
    assert (t["rnpg_s1_2026"], t["rnpg_s1_2025"], t["rnpg_exercice_2025"]) == (215.072, 193.702, 385.526)
    assert "Part du groupe 215 072 193 702" in t["pages"]
    b = BPA["SOT"]
    assert b["rnpg_12m"] == (385526 + 215072 - 193702) / 1000 == 406.896 and b["rnpg_12m_avant_2026_11_09"] == 406.526
    assert b["bpa_12m"] == round(406.896e6 / 38309500, 2) == 10.62 and b["bpa"] == 10.06
    # Le split ×5 donne 38 033 640 ; les 275 860 actions restantes sont une émission en numéraire.
    assert 7606728 * 5 == 38033640 and 38033640 + 275860 == 38309500 == t["actions"]
    config = (RACINE / "bvc_config.py").read_text(encoding="utf-8")
    assert "7 606 728 → 38 033 640" in config and "38 033 640 + 275 860" in config
    assert "Actions ×5 → 38 309 500." not in config
    assert bvc_config.SPLITS["SOT"] == [{"date": "2026-05-05", "ratio": 5}]


def test_mng_la_note_ne_presente_plus_4_dh_comme_le_dividende():
    m = BPA["MNG"]
    assert m["bpa"] == round(3002.0e6 / 118646760, 2) == 25.3 and m["div_dh"] == 5.5
    assert "253,1" in m["note"] and "11 864 676" in m["note"] and "au titre de 2024" in m["note"]
    assert "4,00 DH" in m["note_avant_2026_11_09"]                       # l'ancienne note est gardée


def test_iam_exercice_de_l_etat_audite_et_croissance_non_appliquee():
    t = JEU["titres"]["IAM"]
    # Maroc_Telecom_RFA_2025.pdf p.24 : « Part du groupe 5 283 1 801 6 968 ».
    assert t["rnpg_exercice_2025"] == 6968.0 and t["avant_2026_11_09"]["rnpg_exercice_2025"] == 6969.0
    assert "Part du groupe 5 283 1 801 6 968" in t["source_exercice_2025"]
    assert "La croissance retenue est celle publiée" not in t["pages"] and "n'est PAS appliquée" in t["pages"]
    b = BPA["IAM"]
    # 6 968 + 2 482 − 4 117 = 5 333 ; ÷ 879 095 340 = 6,07 ; 6 968 ÷ 879 095 340 = 7,93 : inchangés au centime.
    assert (b["rnpg_12m"], b["bpa_12m"], b["bpa"]) == (5333.0, 6.07, 7.93)
    assert "La croissance retenue est celle publiée" not in b["source_12m"]
    assert FOND["IAM"]["croissance_bpa"] == -39.7


# ── 6. CIH et CFG Bank : le BPA publié est CONSIGNÉ, pas appliqué (définitions différentes) ──

def test_cih_et_cfg_bpa_publie_consigne_sans_toucher_au_notre():
    cih, cfg = JEU["titres"]["CIH"]["bpa_publie_emetteur"], JEU["titres"]["CFGB"]["bpa_publie_emetteur"]
    assert (cih["valeur"], cih["page"]) == (30.6, 25) and "30,6 27,8" in cih["citation"]
    assert round(1089.362e6 / 35605624, 1) == 30.6 and "FIN d'exercice" in cih["note"]       # sa définition
    assert (cfg["valeur"], cfg["page"]) == (10.89, 44) and "10,89 7,95" in cfg["citation"]
    assert "dénominateur n'est pas publié" in cfg["note"]
    # Nos valeurs ne bougent pas.
    assert (BPA["CIH"]["bpa"], BPA["CIH"]["bpa_12m"], BPA["CFGB"]["bpa"]) == (32.78, 30.93, 10.58)


# ── 4. BOA : attribution gratuite d'1 pour 43, détachée le 22/10/2026 — partie comptable ──

def test_boa_les_avis_de_la_bourse_sont_consignes():
    pieces = {p["fichier"]: p for p in json.loads(
        (RACINE / "datasets/pieces/BOA/index.json").read_text(encoding="utf-8"))["pieces"]}
    assert pieces["av-2026-131_fr.pdf"]["sha256"].startswith("e3759db6")      # 15/10 : détachement le 22/10/2026
    assert pieces["av-2026-136_fr.pdf"]["sha256"].startswith("f53d28f2")      # 29/10 : 220.281.881 → 225.404.715
    src = JEU["titres"]["BOA"]["source_actions"]
    for morceau in ("AV-2026-131", "22/10/2026", "AV-2026-136", "225.404.715", "IAS 33"):
        assert morceau in src, morceau
    # Pas d'entrée au registre des actions : le nombre actuel EST le nombre rétro-ajusté (IAS 33.64).
    assert "BOA" not in bvc_config.HISTORIQUE_ACTIONS
    assert bvc_config.actions_ponderees("BOA", "2025-01-01", "2025-12-31", 225404715)["nombre"] == 225404715


def test_boa_bpa_dividende_et_nombre_d_actions_par_action_actuelle():
    t, b = JEU["titres"]["BOA"], BPA["BOA"]
    assert t["actions"] == 225404715 == FOND["BOA"]["nb_actions"] and t["actions_avant_2026_11_09"] == 220281881
    assert 225404715 - 220281881 == 5122834
    # 3 813,552 ÷ 225,404715 = 16,919 ; (3 813,552 + 2 481,492 − 2 251,235) = 4 043,809 ÷ 225,404715 = 17,940
    assert (b["bpa"], b["bpa_12m"], b["rnpg_12m"]) == (16.92, 17.94, 4043.809)
    assert (b["bpa_avant_2026_11_09"], b["bpa_12m_avant_2026_11_09"]) == (17.31, 18.36)
    # 5 DH votés par ancienne action × 220 281 881 ÷ 225 404 715 = 4,886
    assert b["div_dh"] == round(5 * 220281881 / 225404715, 3) == 4.886 and b["div_dh_avant_2026_11_09"] == 5.0
    assert b["dividende_piece"]["dpa"] == 4.886 and b["dividende_piece"]["dpa_vote"] == 5.0


def test_boa_la_serie_de_cours_n_est_pas_ajustee_dans_ce_lot_et_c_est_dit():
    """Le rétro-ajustement des cours (R11) est un lot à part : il régénère des artefacts
    publiés. Tant qu'il n'est pas fait, ni le registre ni les chandelles ne bougent — les
    deux ensemble, ou aucun (sinon un téléchargement frais diviserait une série non ajustée)."""
    config = (RACINE / "bvc_config.py").read_text(encoding="utf-8")
    assert "AV-2026-131" in config and "PAS ENCORE DÉCLARÉE ICI" in config
    c = {k["d"]: k for k in json.loads((RACINE / "pipeline/candles/BOA.json").read_text(encoding="utf-8"))}
    ajustee = c["2026-10-21"]["c"] != 180.0
    assert ("BOA" in bvc_config.SPLITS) == ajustee


def test_boa_l_etat_intermediaire_est_dit_a_l_ecran_tant_que_la_capitalisation_n_est_pas_alignee():
    """Relecture du 11/11/2026 : BPA sur 225 404 715 actions, capitalisation
    encore sur le relevé du 20/10 (220 281 881). Les deux PER publiés
    (cours ÷ BPA, capitalisation ÷ résultat) divergent alors de ~2,3 %.
    Tant que le registre SPLITS ne porte pas BOA (série et capitalisation non
    alignées), la réserve affichée sous le PER doit le dire, chiffres compris."""
    emetteurs = json.loads((RACINE / "datasets" / "bourse_emetteurs.json").read_text(encoding="utf-8"))
    texte = json.dumps(emetteurs, ensure_ascii=False)
    capitalisation_alignee = "BOA" in bvc_config.SPLITS or "225404715" in texte.replace(" ", "")
    reserve = BPA["BOA"].get("reserve_bpa") or ""
    if capitalisation_alignee:
        return
    assert "225 404 715" in reserve and "220 281 881" in reserve and "2,3 %" in reserve, reserve
    assert "capitalisation" in reserve


def test_boa_reserve_affichee_par_le_moteur():
    """La réserve passe par `bpa_reserve` (update_data.py), seul canal affiché sous le PER."""
    src = (RACINE / "update_data.py").read_text(encoding="utf-8")
    assert '"bpa_reserve": (BPA_DATA.get(ticker) or {}).get("reserve_bpa")' in src
