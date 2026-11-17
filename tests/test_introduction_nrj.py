"""JET ENERGY (NRJ), introduite le 16/11/2026 — inscrite le 17/11 (accord R2).

Ce qui est vérifié, chaque fois avec le cas qui doit rester refusé :
1. l'identité vient de la pièce et se recoupe par le calcul (clé ISIN) ;
2. le plafond de variation vaut ±20 % pendant les cinq premières séances
   d'une admission (décision AMMC du 23/06/2026), ±10 % ensuite et ailleurs ;
3. la variation réelle du premier jour (+19,97 %) n'est plus remplacée par
   0,00 % (R9), mais une variation de +25 % le serait toujours ;
4. les bornes « prochaine séance » de la fiche suivent la même règle.
"""
import json
import logging
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))
logging.disable(logging.CRITICAL)

import bvc_config as C  # noqa: E402


def _cle_isin_valide(isin: str) -> bool:
    chiffres = "".join(str(int(c, 36)) for c in isin[:-1])
    total = 0
    for i, ch in enumerate(reversed(chiffres)):
        n = int(ch)
        if i % 2 == 0:
            n = n * 2 - 9 if n * 2 > 9 else n * 2
        total += n
    return (10 - total % 10) % 10 == int(isin[-1])


def test_identite_inscrite_sur_piece():
    assert C.ISIN_MAP["NRJ"] == "MA0000012874"
    assert _cle_isin_valide(C.ISIN_MAP["NRJ"])
    assert not _cle_isin_valide("MA0000012873"), "contrôle négatif de la clé"
    assert "NRJ" in C.TICKERS_ALL and C.IDB_TICKER_MAP["NRJ"] == "NRJ"
    assert C.COMPANY_NAMES["NRJ"] == "Jet Energy" and C.COMPANY_NAMES["JET"] == "Jet Contractors"
    e = C.INTRODUCTIONS["NRJ"]
    assert (e["date"], e["prix"], e["actions"]) == ("2026-11-16", 143.0, 13_125_000)
    index = json.loads((RACINE / e["piece"]).read_text(encoding="utf-8"))
    assert {p["fichier"] for p in index["pieces"]} >= {"av-2026-142_fr.pdf", "av-2026-144_fr.pdf"}
    assert all(len(p["sha256"]) == 64 for p in index["pieces"])


def test_plafond_selon_le_rang_de_seance():
    # 18/11 : fête de l'Indépendance, pas une séance
    attendu = {"2026-11-16": 20.0, "2026-11-17": 20.0, "2026-11-19": 20.0,
               "2026-11-23": 20.0, "2026-11-24": 10.0}
    assert {d: C.plafond_variation_pct("NRJ", d) for d in attendu} == attendu
    assert C.seances_depuis_introduction("NRJ", "2026-11-23") == 5
    assert C.plafond_variation_pct("NRJ", "2026-11-13") == 10.0, "avant l'admission"
    assert C.plafond_variation_pct("IAM", "2026-11-17") == 10.0, "hors registre"


def test_la_variation_du_premier_jour_est_conservee():
    import pandas as pd
    import update_data as ud
    bougies = pd.DataFrame([{"d": "2026-11-16", "o": 171.55, "h": 171.55, "l": 171.55,
                             "c": 171.55, "v": 99993}])
    # deuxième séance : +19,9 % sur la clôture du 16/11, sous le plafond de 20 %
    assert ud.recalculer_variation("NRJ", 205.7, 0.0, bougies, "2026-11-17", "2026-11-17") == 19.91
    # contrôle négatif : au-delà de 20 %, la variation reste refusée
    assert ud.recalculer_variation("NRJ", 214.4, 0.0, bougies, "2026-11-17", "2026-11-17") == 0.0
    # contrôle négatif : après la cinquième séance, ±10 % de nouveau
    assert ud.recalculer_variation("NRJ", 205.7, 0.0, bougies, "2026-11-24", "2026-11-24") == 0.0


def test_bornes_de_la_fiche():
    from pipeline.niveaux import bornes_reglementaires
    b = bornes_reglementaires(171.55, "NRJ", "2026-11-16")
    assert b["pct"] == 20.0 and b["plafond"] == 205.86 and "introduction" in b["_methode"]
    # séance 5 publiée : la prochaine est la 6e, de nouveau ±10 %
    assert bornes_reglementaires(171.55, "NRJ", "2026-11-23")["pct"] == 10.0
    assert bornes_reglementaires(90.0, "IAM", "2026-11-16")["pct"] == 10.0


def test_entree_au_registre_retire_le_titre_de_l_annotation_hors_registre(tmp_path):
    """Rejeu du 17/11 : NRJ, annotée hors registre par le passage de 07h50,
    entre au registre ; la liste hors registre arrive vide. Garder l'ancienne
    annotation comptait NRJ deux fois (152,8 M DH contre 135,6 M de synthèse)."""
    from pipeline import marche_history as mh
    p = tmp_path / "marche.json"
    ligne = {"Cours": 17239.5269, "VariationP": -0.63, "Volume": 135629736.67,
             "NbrTransaction": 2189, "NbrValeur": 66, "NbrHausse": 20, "NbrBaisse": 36,
             "NbrInchange": 10, "QteEchange": 356118}
    mh.enregistrer(ligne, "2026-11-16", p, aujourd_hui="2026-11-16")
    mh.annoter_hors_registre("2026-11-16", [{"code": "NRJ", "libelle": "JET ENERGY",
                                              "echange_dh": 17153799.15, "qte": 99993}], p)
    # contrôle négatif : sans NRJ parmi les codes connus, l'annotation tient
    assert not mh.annoter_hors_registre("2026-11-16", [], p, connus={"IAM"})
    assert mh.annoter_hors_registre("2026-11-16", [], p, connus={"NRJ", "IAM"})
    d = mh.dernier(p)
    assert d["hors_registre"] == [] and d["volume_hors_registre_dh"] == 0
