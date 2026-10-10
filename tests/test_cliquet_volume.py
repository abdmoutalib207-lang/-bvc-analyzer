"""Dans une même séance, le volume cumulé ne recule pas — 09/10/2026.

Le volume global publié a alterné entre 122,65 et 129,04 M DH d'un run à
l'autre après la clôture du 09/10. Le bulletin CDG donne 129,04 (66 lignes,
485 709 titres). Les runs à 122,65 recevaient un instantané de CDG figé avant
les derniers échanges : Managem 4 387 titres au lieu de 8 633, Cosumar 16 151
au lieu de 19 151. Chiffres repris des deux data.json publiés ce soir-là
(commits 34c5032d et 21bcf251) et du bulletin.
"""
import logging
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))
logging.disable(logging.CRITICAL)

import update_data as ud  # noqa: E402

SEANCE = "2026-10-09"


def _publie(src="cdg", **titres):
    return {"tickers": [dict(symbol=s, _meta={"prix_asof": SEANCE, "source_prix": src}, **v)
                        for s, v in titres.items()]}


def test_un_releve_plus_ancien_de_la_meme_seance_est_ecarte():
    publie = _publie(MNG={"price": 1479.0, "chg": -1.2, "vol": 8633, "echange_dh": 12_768_207.0})
    live = {"MNG": {"price": 1479.0, "chg": -1.2, "vol": 4387, "echange_dh": 6_488_373.0,
                    "asof": SEANCE, "src": "cdg"}}
    assert ud._cliquet_volume(live, publie) == ["MNG"]
    assert live["MNG"]["vol"] == 8633 and live["MNG"]["echange_dh"] == 12_768_207.0
    assert live["MNG"]["cliquet_volume"] is True


def test_la_ligne_publiee_est_reprise_entiere_sans_hybride():
    """08/10 : Sothema publiée à 310 (299 titres) par un relevé ancien, quand
    la clôture était 291 (5 202). Relecture du 10/10 : seuils, montant et
    extrêmes du relevé ancien ne doivent pas rester à côté du cours repris."""
    publie = _publie(SOT={"price": 291.0, "chg": -7.35, "vol": 5202, "echange_dh": None,
                          "reference": 314.1, "seuil_bas": 282.7, "seuil_haut": 345.5})
    live = {"SOT": {"price": 310.0, "chg": -1.31, "vol": 299, "echange_dh": 93_000.0,
                    "open": 325.0, "high": 312.0, "low": 309.0, "reference": 314.1,
                    "seuil_bas": 300.0, "seuil_haut": 320.0, "asof": SEANCE, "src": "cdg"}}
    ud._cliquet_volume(live, publie)
    q = live["SOT"]
    assert (q["price"], q["chg"], q["vol"]) == (291.0, -7.35, 5202)
    assert q["echange_dh"] is None, "un montant du relevé ancien resterait à côté du volume repris"
    assert (q["seuil_bas"], q["seuil_haut"]) == (282.7, 345.5)
    assert q["high"] is None and q["low"] is None


def test_la_chandelle_n_est_pas_reecrite_depuis_une_ligne_gardee(tmp_path):
    from pipeline.session_candles import preparer
    live = {"SOT": {"price": 291.0, "open": 325.0, "high": None, "low": None, "vol": 5202,
                    "asof": SEANCE, "src": "cdg"}}
    assert preparer(live, SEANCE, SEANCE, tmp_path, ["SOT"]) == {}


def test_une_autre_source_n_est_pas_comparee():
    """BMCE peut compter autrement : un volume CDG publié ne fige pas BMCE."""
    publie = _publie(src="cdg", ATW={"price": 676.0, "vol": 50_000})
    live = {"ATW": {"price": 680.0, "vol": 1_200, "asof": SEANCE, "src": "bmce"}}
    assert ud._cliquet_volume(live, publie) == []
    assert live["ATW"]["price"] == 680.0


def test_un_volume_superieur_ou_une_nouvelle_seance_passent():
    publie = _publie(MNG={"price": 1479.0, "vol": 4387})
    live = {"MNG": {"price": 1479.0, "vol": 8633, "asof": SEANCE, "src": "cdg"}}
    assert ud._cliquet_volume(live, publie) == []
    assert live["MNG"]["vol"] == 8633 and "cliquet_volume" not in live["MNG"]
    publie = _publie(MNG={"price": 1479.0, "vol": 8633})
    live = {"MNG": {"price": 1490.0, "vol": 120, "asof": "2026-10-12", "src": "cdg"}}
    assert ud._cliquet_volume(live, publie) == []
    assert live["MNG"]["price"] == 1490.0


def test_l_etat_de_marche_ne_recule_pas_dans_la_seance(tmp_path):
    """Le bloc de marché publié (volume, largeur) se lit dans marche_history :
    c'est là que le volume global est protégé, en entier."""
    from pipeline import marche_history as mh
    chemin = tmp_path / "marche_history.json"
    complet = {"Cours": "16800", "Volume": "129043014.54", "QteEchange": "485710",
               "NbHausses": "26", "NbBaisses": "29"}
    ancien = dict(complet, Volume="122647419.54", QteEchange="478237")
    assert mh.enregistrer(complet, SEANCE, chemin, aujourd_hui=SEANCE) is True
    assert mh.enregistrer(ancien, SEANCE, chemin, aujourd_hui=SEANCE) is False
    import json
    etat = json.loads(chemin.read_text(encoding="utf-8"))
    assert "129043014" in json.dumps(etat)


def test_le_cliquet_est_branche_avant_l_ecriture_et_trace_dans_meta():
    src = (RACINE / "update_data.py").read_text(encoding="utf-8")
    ecriture = src.index("OUTPUT.write_text(json.dumps(output")
    assert 0 < src.index("_cliquet_volume(live_prices)") < ecriture
    assert '"cliquet_volume": bool(cliquet_volume)' in src
    assert 'cliquet_volume=lp.get("cliquet_volume", False)' in src
