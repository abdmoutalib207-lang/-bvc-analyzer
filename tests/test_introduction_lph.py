"""LAPROPHAN (LPH), introduite le 25/11/2026 — inscrite le 26/11 (accord R2).

Même démarche que JET ENERGY (tests/test_introduction_nrj.py), avec le cas
symétrique : la première séance a BAISSÉ de 12,02 % (300,00 DH pour un prix
d'introduction de 341,00), au-delà de ±10 %, dans le plafond de ±20 %.

Ce qui est vérifié, chaque fois avec le cas qui doit rester refusé :
1. l'identité vient de la pièce et se recoupe par le calcul (clé ISIN,
   montant alloué de l'avis AV-2026-145) ;
2. le plafond vaut ±20 % pendant les cinq premières séances, ±10 % ensuite ;
3. la variation réelle du premier jour (−12,02 %) n'est plus remplacée par
   0,00 % (R9), mais −25 % le serait toujours ;
4. la première bougie est celle relevée chez l'opérateur, et le titre sort de
   l'annotation « hors registre » (sinon compté deux fois).
"""
import json
import logging
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))
logging.disable(logging.CRITICAL)

import bvc_config as C  # noqa: E402
from test_introduction_nrj import _cle_isin_valide  # noqa: E402


def test_identite_inscrite_sur_piece():
    assert C.ISIN_MAP["LPH"] == "MA0000012882"
    assert _cle_isin_valide(C.ISIN_MAP["LPH"])
    assert not _cle_isin_valide("MA0000012881"), "contrôle négatif de la clé"
    assert list(C.ISIN_MAP.values()).count("MA0000012882") == 1
    assert "LPH" in C.TICKERS_ALL and C.TICKERS_ALL.count("LPH") == 1
    assert C.IDB_TICKER_MAP["LPH"] == "LPH"
    assert [k for k, v in C.IDB_TICKER_MAP.items() if v == "LPH"] == ["LPH"]
    assert C.COMPANY_NAMES["LPH"] == "Laprophan"
    assert C.COMPANY_SECTORS["LPH"] == C.COMPANY_SECTORS["SOT"] == "Santé"
    assert "LPH" not in C.SIGLES_AMBIGUS
    e = C.INTRODUCTIONS["LPH"]
    assert (e["date"], e["prix"], e["actions"]) == ("2026-11-25", 341.0, 17_315_725)
    # 4 105 500 nouvelles + 2 412 200 cédées = 6 517 700 attribuées (AV-2026-145) ;
    # montant alloué = 6 517 700 × 341 − 329 700 × (341 − 273), décote des salariés.
    assert 4_105_500 + 2_412_200 == 6_517_700
    assert 6_517_700 * 341 - 329_700 * (341 - 273) == 2_200_116_100
    index = json.loads((RACINE / e["piece"]).read_text(encoding="utf-8"))
    assert {p["fichier"] for p in index["pieces"]} >= {
        "av-2026-137_fr.pdf", "av-2026-145_fr.pdf", "laprophan_ipo_no_033_2026.pdf"}
    assert all(len(p["sha256"]) == 64 and p["commitable"] is False for p in index["pieces"])


def test_plafond_selon_le_rang_de_seance():
    attendu = {"2026-11-25": 20.0, "2026-11-26": 20.0, "2026-11-27": 20.0,
               "2026-11-30": 20.0, "2026-12-01": 20.0, "2026-12-02": 10.0}
    assert {d: C.plafond_variation_pct("LPH", d) for d in attendu} == attendu
    assert C.seances_depuis_introduction("LPH", "2026-12-01") == 5
    assert C.plafond_variation_pct("LPH", "2026-11-24") == 10.0, "avant l'admission"


def test_la_variation_du_premier_jour_est_conservee():
    import pandas as pd
    import update_data as ud
    assert round((300.0 - 341.0) / 341.0 * 100, 2) == -12.02
    bougies = pd.DataFrame([{"d": "2026-11-25", "o": 305.0, "h": 333.0, "l": 300.0,
                             "c": 300.0, "v": 358274}])
    # deuxième séance : −15 % sur la clôture du 25/11, sous le plafond de 20 %
    assert ud.recalculer_variation("LPH", 255.0, 0.0, bougies, "2026-11-26", "2026-11-26") == -15.0
    # contrôle négatif : au-delà de 20 %, la variation reste refusée
    assert ud.recalculer_variation("LPH", 225.0, 0.0, bougies, "2026-11-26", "2026-11-26") == 0.0
    # contrôle négatif : après la cinquième séance, ±10 % de nouveau
    assert ud.recalculer_variation("LPH", 255.0, 0.0, bougies, "2026-12-02", "2026-12-02") == 0.0


def test_premiere_bougie_relevee_chez_l_operateur():
    serie = json.loads((RACINE / "pipeline" / "candles" / "LPH.json").read_text(encoding="utf-8"))
    b = serie[0]
    assert b == {"d": "2026-11-25", "o": 305.0, "h": 333.0, "l": 300.0, "c": 300.0, "v": 358274}
    assert b["l"] <= min(b["o"], b["c"]) <= max(b["o"], b["c"]) <= b["h"]    # invariant OHLC
    # capitalisation de l'opérateur : 300 × 17 315 725
    assert b["c"] * C.INTRODUCTIONS["LPH"]["actions"] == 5_194_717_500


def test_entree_au_registre_retire_le_titre_de_l_annotation_hors_registre(tmp_path):
    """Rejeu du 26/11 : LPH, annotée hors registre le 25/11 (109 343 283,65 DH),
    entre au registre ; la liste hors registre arrive vide. Les codes connus
    sont ceux du registre lui-même, comme dans `update_data.run`."""
    from pipeline import marche_history as mh
    p = tmp_path / "marche.json"
    ligne = {"Cours": 16571.3179, "VariationP": -1.15, "Volume": 558383323.58,
             "NbrTransaction": 6352, "NbrValeur": 66, "NbrHausse": 17, "NbrBaisse": 45,
             "NbrInchange": 4, "QteEchange": 1076173}
    mh.enregistrer(ligne, "2026-11-25", p, aujourd_hui="2026-11-25")
    mh.annoter_hors_registre("2026-11-25", [{"code": "LPH", "libelle": "LAPROPHAN S.A",
                                              "echange_dh": 109343283.65, "qte": 358274}], p)
    assert mh.dernier(p)["volume_hors_registre_dh"] == 109343283.65
    # contrôle négatif : sans LPH parmi les codes connus, l'annotation tient
    connus_avant = set(C.IDB_TICKER_MAP.values()) - {"LPH"}
    assert not mh.annoter_hors_registre("2026-11-25", [], p, connus=connus_avant)
    assert mh.annoter_hors_registre("2026-11-25", [], p, connus=set(C.IDB_TICKER_MAP.values()))
    d = mh.dernier(p)
    assert d["hors_registre"] == [] and d["volume_hors_registre_dh"] == 0
