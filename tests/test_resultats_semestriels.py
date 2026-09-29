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
