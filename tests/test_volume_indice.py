"""Volume global vs somme des fiches de la séance (06/10/2026).

Cas réel : indice CDG 346 377 516,02 DH, somme des 68 fiches = bulletin CDG
= 349 551 480,02 DH. Attendus écrits à la main.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import update_data as ud  # noqa: E402

S = "2026-10-06"


def _t(sym, ech, vol=10, asof=S):
    return {"symbol": sym, "vol": vol, "echange_dh": ech, "_meta": {"prix_asof": asof}}


def test_indice_en_retard_la_somme_des_fiches_est_publiee():
    r = ud.volume_indice_coherent({"asof": S, "volume_mad": 346377516.02},
                                  [_t("A", 300000000.0), _t("B", 49551480.02)])
    assert r["volume_mad"] == 349551480.02
    assert r["volume_mad_indice_cdg"] == 346377516.02
    assert r["volume_source"].startswith("somme_des_titres")


def test_accord_rien_ne_change():
    r = ud.volume_indice_coherent({"asof": S, "volume_mad": 1000.0}, [_t("A", 1000.0)])
    assert "volume_mad" not in r and r["volume_source"] == "indice_cdg"


def test_somme_inferieure_non_remplacee():
    r = ud.volume_indice_coherent({"asof": S, "volume_mad": 2000.0}, [_t("A", 1000.0)])
    assert "volume_mad" not in r and "non remplacé" in r["volume_source"]


def test_ecart_trop_grand_signale_sans_remplacer():
    # +10 % : une fiche comptée deux fois, pas un indice en retard
    r = ud.volume_indice_coherent({"asof": S, "volume_mad": 1000.0}, [_t("A", 1100.0)])
    assert "volume_mad" not in r and "non remplacé" in r["volume_source"]


def test_fiche_de_la_seance_sans_montant_rend_la_couverture_incomplete():
    r = ud.volume_indice_coherent({"asof": S, "volume_mad": 10.0},
                                  [_t("A", 1000.0), _t("B", None, vol=5)])
    assert r["volume_titres_couverture"] == "incomplete"


def test_couverture_incomplete_ou_autre_seance_ignorees():
    r = ud.volume_indice_coherent({"asof": S, "volume_mad": 10.0},
                                  [_t("A", 1000.0), _t("B", None)])
    assert "volume_mad" not in r and r["volume_titres_couverture"] == "incomplete"
    # une fiche d'une autre séance ne compte pas
    r = ud.volume_indice_coherent({"asof": S, "volume_mad": 1000.0},
                                  [_t("A", 1000.0), _t("Z", 9e9, asof="2026-10-02")])
    assert "volume_mad" not in r


def test_l_ecart_reste_visible_dans_les_donnees_publiees():
    """Le briefing compare désormais à un volume corrigé : l'écart avec
    l'indice brut ne doit pas disparaître, il reste publié et borné."""
    import json
    d = json.loads((Path(__file__).resolve().parent.parent / "data.json").read_text(encoding="utf-8"))
    m = d.get("masi") or {}
    if m.get("volume_mad_indice_cdg") is not None:
        assert m["volume_source"].startswith("somme_des_titres")
        assert 0 < m["volume_mad"] - m["volume_mad_indice_cdg"] <= m["volume_mad_indice_cdg"] * 0.05
