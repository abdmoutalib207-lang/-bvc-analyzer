"""Incident du 16-17/11/2026 : le moteur bloqué à 14h56.

Enchaînement établi sur les journaux des runs 4608 à 4619 et sur un rejeu :

1. Le 16/11, JET ENERGY (code NRJ) est introduite en bourse : 17 153 799,15 DH
   et 99 993 titres dès sa première séance. La synthèse de CDG la compte
   (135 629 736,67 DH) ; nos 80 fiches non (118 475 459,86 DH). La garde de
   publication refuse l'écart à chaque passage du soir.
2. Passé minuit, la séance du 16/11 est « échue » : `marche_history` la garde
   gravée au relevé de 14h56 (48 275 993,56 DH), et la bougie du 16/11 reste
   celle de 14h56 (IAM 89,40 sur 18 002 titres au lieu de 90,00 sur 64 115).
   37 titres tombent en « cours en désaccord avec la dernière clôture ». Le
   verrou s'entretient lui-même.

Les trois corrections testées ici, chacune avec le cas qui doit rester refusé.
"""
import json
import logging
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))
logging.disable(logging.CRITICAL)

from pipeline import marche_history as mh  # noqa: E402
from pipeline.session_candles import preparer  # noqa: E402

SEANCE, LENDEMAIN = "2026-11-16", "2026-11-17"


def _ligne(volume, transactions):
    return {"Cours": 17239.5269, "VariationP": -0.63, "Volume": volume,
            "NbrTransaction": transactions, "NbrValeur": 66, "NbrHausse": 20,
            "NbrBaisse": 36, "NbrInchange": 10, "QteEchange": 356118}


# ── 1. marche_history : la dernière séance accepte un état plus avancé ─────

def test_seance_echue_rafraichie_si_le_volume_cumule_a_progresse(tmp_path):
    p = tmp_path / "marche.json"
    assert mh.enregistrer(_ligne(48275993.56, 1763), SEANCE, p, aujourd_hui=SEANCE)
    # le lendemain, la source sert l'état définitif de la même séance
    assert mh.enregistrer(_ligne(135629736.67, 2189), SEANCE, p, aujourd_hui=LENDEMAIN)
    assert mh.dernier(p)["volume_mad"] == 135629736.67


def test_controle_negatif_un_releve_plus_ancien_ne_reecrit_pas_la_seance_echue(tmp_path):
    p = tmp_path / "marche.json"
    mh.enregistrer(_ligne(135629736.67, 2189), SEANCE, p, aujourd_hui=SEANCE)
    assert not mh.enregistrer(_ligne(48275993.56, 1763), SEANCE, p, aujourd_hui=LENDEMAIN)
    assert mh.dernier(p)["volume_mad"] == 135629736.67


def test_controle_negatif_une_seance_qui_n_est_plus_la_derniere_reste_gravee(tmp_path):
    p = tmp_path / "marche.json"
    mh.enregistrer(_ligne(48275993.56, 1763), SEANCE, p, aujourd_hui=SEANCE)
    mh.enregistrer(_ligne(90000000.0, 2000), LENDEMAIN, p, aujourd_hui=LENDEMAIN)
    assert not mh.enregistrer(_ligne(135629736.67, 2189), SEANCE, p, aujourd_hui=LENDEMAIN)
    assert json.loads(p.read_text())["seances"][SEANCE]["volume_mad"] == 48275993.56


# ── 2. Titres cotés hors registre : chiffrés, et comptés dans le recoupement ─

NRJ = {"code": "NRJ", "libelle": "JET ENERGY", "asof": SEANCE,
       "echange_dh": 17153799.15, "qte": 99993, "cours": 171.55}


def test_l_introduction_est_inscrite_sur_la_seance_et_survit_au_rafraichissement(tmp_path):
    p = tmp_path / "marche.json"
    mh.enregistrer(_ligne(135000000.0, 2100), SEANCE, p, aujourd_hui=SEANCE)
    assert mh.annoter_hors_registre(SEANCE, [NRJ], p)
    mh.enregistrer(_ligne(135629736.67, 2189), SEANCE, p, aujourd_hui=SEANCE)
    d = mh.dernier(p)
    assert d["volume_hors_registre_dh"] == 17153799.15
    assert d["hors_registre"][0]["code"] == "NRJ"


def test_le_recoupement_compte_le_titre_hors_registre():
    import update_data as ud
    masi = {"asof": SEANCE, "volume_mad": 135629736.67, "volume_hors_registre_dh": 17153799.15}
    titres = [{"_meta": {"prix_asof": SEANCE}, "vol": 1, "echange_dh": 118475459.86}]
    assert ud.volume_indice_coherent(masi, titres)["volume_source"] == "indice_cdg"


def test_controle_negatif_sans_le_titre_hors_registre_l_ecart_reste_signale():
    import update_data as ud
    masi = {"asof": SEANCE, "volume_mad": 135629736.67}
    titres = [{"_meta": {"prix_asof": SEANCE}, "vol": 1, "echange_dh": 118475459.86}]
    assert ud.volume_indice_coherent(masi, titres)["volume_source"] != "indice_cdg"


# ── 3. La bougie d'une séance échue suit un état plus avancé de CDG ────────

def _q(c, v, src="cdg", o=90.0, h=90.5, l=89.0):
    return {"IAM": {"src": src, "asof": SEANCE, "open": o, "high": h, "low": l,
                    "price": c, "vol": v}}


def _serie(tmp_path):
    (tmp_path / "IAM.json").write_text(json.dumps(
        [{"d": "2026-11-13", "o": 90.45, "h": 90.5, "l": 89.0, "c": 89.0, "v": 310977},
         {"d": SEANCE, "o": 90.0, "h": 90.0, "l": 89.0, "c": 89.4, "v": 18002}]))


def test_bougie_de_mi_seance_completee_le_lendemain(tmp_path):
    _serie(tmp_path)
    out = preparer(_q(90.0, 64115), SEANCE, LENDEMAIN, tmp_path, ["IAM"])
    b = out["IAM"][-1]
    assert (b["d"], b["c"], b["v"]) == (SEANCE, 90.0, 64115)
    assert b["h"] == 90.5 and b["l"] == 89.0


def test_controle_negatif_quantite_egale_ou_moindre_refusee(tmp_path):
    _serie(tmp_path)
    assert preparer(_q(90.0, 18002), SEANCE, LENDEMAIN, tmp_path, ["IAM"]) == {}
    assert preparer(_q(90.0, 9000), SEANCE, LENDEMAIN, tmp_path, ["IAM"]) == {}


def test_controle_negatif_une_autre_source_que_cdg_refusee(tmp_path):
    _serie(tmp_path)
    assert preparer(_q(90.0, 64115, src="bmce"), SEANCE, LENDEMAIN, tmp_path, ["IAM"]) == {}
