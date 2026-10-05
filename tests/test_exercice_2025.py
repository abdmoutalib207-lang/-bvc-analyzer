"""L'exercice 2025 rectifié — lot 13, 30/09/2026.

Attendus écrits À LA MAIN depuis les montants des dépôts AMMC, pas recalculés
avec la fonction testée.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

from pipeline.exercice_2025 import appliquer, bpa_exercice  # noqa: E402

JEU = json.loads((RACINE / "datasets" / "exercice_2025_rectifie.json").read_text(encoding="utf-8"))
S1 = json.loads((RACINE / "datasets" / "resultats_s1_2026.json").read_text(encoding="utf-8"))
T = JEU["titres"]
TA = {**JEU["_passes_au_s1"], **T}  # une fiche passée au S1 garde son exercice


def test_bpa_a_la_main():
    # 851,083 ÷ 8,96 M = 94,987 ; publié « 95 » (p.6)
    assert bpa_exercice(TA["TMA"]) == 94.99
    # 56,204 ÷ 1,225978 M = 45,845 ; publié 45,84 (p.7)
    assert bpa_exercice(TA["CTM"]) == 45.84
    # 407,601 ÷ 22,078588 M = 18,461
    assert bpa_exercice(JEU["_passes_au_s1"]["ADI"]) == 18.46
    # 453,719263 ÷ 402,551254 M = 1,127 ; publié 1.13 — fiche passée au jeu
    # S1 le 01/10, conservée sous _passes_au_s1
    assert bpa_exercice(JEU["_passes_au_s1"]["ADH"]) == 1.13
    # 148,198775 ÷ 1,384182 M = 107,07 ; publié 107.07 (p.9)
    assert bpa_exercice(TA["MGL"]) == 107.07
    # 32,558354 ÷ 0,81207 M = 40,09
    assert bpa_exercice(TA["S2M"]) == 40.09
    # −25,642371 ÷ 5,265 M = −4,87
    assert bpa_exercice(TA["CAR"]) == -4.87
    # 59,914634 ÷ 1 M
    assert bpa_exercice(TA["PPM"]) == 59.91


def test_valeur_manquante_ne_se_comble_pas():
    assert bpa_exercice(dict(TA["TMA"], actions=None)) is None
    assert bpa_exercice(dict(TA["TMA"], rnpg_exercice_2025=None)) is None


def test_l_ancien_bpa_est_conserve_et_rien_d_autre_n_est_touche():
    bpa = {"TMA": {"bpa": 108.21, "div_dh": 156.57, "roe": 25.0}}
    appliquer({"titres": {"TMA": TA["TMA"]}}, bpa)
    assert bpa["TMA"]["bpa"] == 94.99
    assert bpa["TMA"]["bpa_avant_2026_09_29"] == 108.21
    assert bpa["TMA"]["div_dh"] == 156.57 and bpa["TMA"]["roe"] == 25.0


def test_un_ancien_bpa_deja_conserve_n_est_pas_reecrit():
    bpa = {"CTM": {"bpa": 30.0, "bpa_avant_2026_09_29": 38.0}}
    appliquer({"titres": {"CTM": TA["CTM"]}}, bpa)
    assert bpa["CTM"]["bpa_avant_2026_09_29"] == 38.0


def test_un_bpa_confirme_ne_cree_pas_d_ancien():
    bpa = {"ADI": {"bpa": 18.46}}
    appliquer({"titres": {"ADI": JEU["_passes_au_s1"]["ADI"]}}, bpa)
    assert "bpa_avant_2026_09_29" not in bpa["ADI"]


def test_une_perte_porte_sa_piece():
    bpa = {}
    appliquer({"titres": {"CAR": TA["CAR"]}}, bpa)
    assert bpa["CAR"]["bpa"] == -4.87
    assert "25 642 371,05" in bpa["CAR"]["perte_documentee"]
    bpa2 = {"PPM": {"perte_documentee": "x"}}
    appliquer({"titres": {"PPM": TA["PPM"]}}, bpa2)
    assert "perte_documentee" not in bpa2["PPM"]


def test_chaque_chiffre_porte_sa_page_et_sa_source():
    for s, t in T.items():
        assert t["url"].startswith("https://www.ammc.ma/"), s
        assert t["pages"].startswith("p.") and t["source_exercice_2025"] and t["source_actions"], s
        assert t["base"] and t.get("yuna"), s


def test_aucun_titre_n_est_a_la_fois_ici_et_dans_le_jeu_s1():
    assert not set(T) & set(S1["titres"])


def test_un_titre_passe_au_s1_y_est_bien():
    for s in JEU.get("_passes_au_s1") or {}:
        assert s in S1["titres"] and s not in T, s


def test_les_ecartes_portent_un_motif():
    for s in ("ENK", "MDP", "IBM", "DLM", "DIS"):
        assert len(JEU["_ecartes"][s]) > 80, s
        assert s not in T


def test_un_avertissement_sur_resultats_n_est_pas_un_compte():
    assert "PPM_S1" in JEU["_ecartes"]
    assert "rnpg_s1_2026" not in TA["PPM"]


def test_fichier_publie():
    bpa = json.loads((RACINE / "bpa.json").read_text(encoding="utf-8"))
    assert bpa["TMA"]["bpa"] == 94.99 and bpa["TMA"]["bpa_avant_2026_09_29"] == 108.21
    assert bpa["CTM"]["bpa"] == 45.84 and bpa["CTM"]["bpa_avant_2026_09_29"] == 38.0
    assert bpa["S2M"]["bpa"] == 40.09 and bpa["S2M"]["bpa_avant_2026_09_29"] == 35.79
    assert bpa["MGL"]["bpa"] == 107.07
    assert bpa["CAR"]["bpa"] == -4.87 and bpa["CAR"]["perte_documentee"]
    assert bpa["PPM"]["bpa"] == 59.91
    # REB : 1,054255 + 0,017407 − 0,399198 = 0,672 MDH ; ÷ 176 456 = 3,81
    assert bpa["REB"]["bpa"] == 5.97 and bpa["REB"]["bpa_12m"] == 3.81
    # T2S : 204,576 + 91 − 109 = 186,576 MDH ; ÷ 21 785 174 = 8,56
    assert bpa["T2S"]["bpa"] == 9.39 and bpa["T2S"]["bpa_12m"] == 8.56


def test_lot_bpa_sources_primaires_05_10():
    """Les 31 BPA `casablancabourse_derive` relus à l'état déposé (05/10/2026).

    Attendus écrits à la main depuis les pièces, pas recalculés par la fonction testée.
    """
    # M2M : « Résultat consolidé 5 305 374 » classé sous « Capitaux propres (Part
    # du groupe) » (M2M_Group_2025.pdf p.4) ÷ 647 777 = 8,190 ; publié « 8,19 ».
    # L'ancien 26,39 ne correspondait à aucun état (2024 = 22,62).
    assert bpa_exercice(T["M2M"]) == 8.19
    # Contrôle arithmétique de la pièce : ensemble 6 545 127 − minoritaires 1 239 753
    assert 6545127 - 1239753 == 5305374 == round(T["M2M"]["rnpg_exercice_2025"] * 1e6)
    # AFM : 72 655 851 ÷ 1 000 000 = 72,66 (publié 72,66), pas « 73 MDH »
    assert bpa_exercice(S1["titres"]["AFM"]) == 72.66
    # AKD : 443 680 156 ÷ 14 159 207 = 31,335 ; MIC : 69 547 790,96 ÷ 1 680 000 = 41,40
    assert bpa_exercice(S1["titres"]["AKD"]) == 31.34
    assert bpa_exercice(S1["titres"]["MIC"]) == 41.4


def test_bpa_json_publie_apres_relecture_a_l_etat():
    bpa = json.loads((RACINE / "bpa.json").read_text(encoding="utf-8"))
    assert bpa["M2M"]["bpa"] == 8.19 and bpa["M2M"]["bpa_avant_2026_09_29"] == 26.39
    assert (bpa["AFM"]["bpa"], bpa["AKD"]["bpa"], bpa["MIC"]["bpa"]) == (72.66, 31.34, 41.4)
    # L'étiquette « tiers » ne reste que sur ce qui n'a PAS été relu à l'état.
    for s in ("AFI AFM AGM AKD ALU BAL CASH COL DAR DHO DSW DTT EQD M2M MIC MOX "
              "NEJ SNP TMA VCNE S2M").split():
        assert bpa[s]["source"] == "resultats_officiels", s
        assert bpa[s]["source_avant_2026_10_05"] == "casablancabourse_derive", s


def test_etiquette_tiers_remplacee_sans_effacer():
    bpa = {"TMA": {"bpa": 94.99, "source": "casablancabourse_derive"}}
    appliquer({"titres": {"TMA": TA["TMA"]}}, bpa)
    assert bpa["TMA"]["source"] == "resultats_officiels"
    assert bpa["TMA"]["source_avant_2026_10_05"] == "casablancabourse_derive"


def test_t2s_ne_cree_pas_de_fiche_fondamentaux():
    """R8 : une fiche, même vide, change la note (compute_fond_score)."""
    from pipeline.resultats_semestriels import appliquer as app_s1
    bpa, fond = {}, {}
    app_s1({"fin_periode": "2026-06-30", "titres": {"T2S": S1["titres"]["T2S"]}}, bpa, fond)
    assert "T2S" not in fond
    assert bpa["T2S"]["bpa_12m"] == 8.56
