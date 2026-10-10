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


def _publie(**titres):
    return {"tickers": [dict(symbol=s, _meta={"prix_asof": SEANCE}, **v)
                        for s, v in titres.items()]}


def test_un_instantane_plus_ancien_de_la_meme_seance_est_ecarte():
    publie = _publie(MNG={"price": 1479.0, "chg": -1.2, "vol": 8633, "echange_dh": 12_768_207.0})
    live = {"MNG": {"price": 1479.0, "chg": -1.2, "vol": 4387, "echange_dh": 6_488_373.0,
                    "asof": SEANCE}}
    assert ud._cliquet_volume(live, publie) == ["MNG"]
    assert live["MNG"]["vol"] == 8633 and live["MNG"]["echange_dh"] == 12_768_207.0


def test_le_prix_aussi_vient_de_la_ligne_la_plus_recente():
    """08/10 : Sothema publiée à 310 (299 titres) par un instantané ancien,
    quand la clôture était 291 (5 202 titres)."""
    publie = _publie(SOT={"price": 291.0, "chg": -7.35, "vol": 5202})
    live = {"SOT": {"price": 310.0, "chg": -1.31, "vol": 299, "asof": "2026-10-09"}}
    ud._cliquet_volume(live, publie)
    assert live["SOT"]["price"] == 291.0 and live["SOT"]["chg"] == -7.35


def test_un_volume_superieur_ou_une_nouvelle_seance_passent():
    publie = _publie(MNG={"price": 1479.0, "vol": 4387})
    live = {"MNG": {"price": 1479.0, "vol": 8633, "asof": SEANCE}}
    assert ud._cliquet_volume(live, publie) == []
    assert live["MNG"]["vol"] == 8633
    # Séance suivante : le volume repart de zéro, aucune comparaison.
    publie = _publie(MNG={"price": 1479.0, "vol": 8633})
    live = {"MNG": {"price": 1490.0, "vol": 120, "asof": "2026-10-12"}}
    assert ud._cliquet_volume(live, publie) == []
    assert live["MNG"]["price"] == 1490.0


def test_le_volume_global_ne_recule_pas_dans_la_seance():
    publie = {"masi": {"asof": SEANCE, "volume_mad": 129_043_014.54,
                       "titres_echanges": 485_710, "transactions": 3691}}
    masi = {"asof": SEANCE, "volume_mad": 122_647_419.54,
            "titres_echanges": 478_237, "transactions": 3691}
    assert ud._cliquet_volume_global(masi, publie) is True
    assert masi["volume_mad"] == 129_043_014.54 and masi["titres_echanges"] == 485_710
    # Séance suivante : pas de comparaison.
    masi = {"asof": "2026-10-12", "volume_mad": 5_000_000.0}
    assert ud._cliquet_volume_global(masi, publie) is False
    assert masi["volume_mad"] == 5_000_000.0


def test_les_deux_cliquets_sont_branches_avant_l_ecriture():
    src = (RACINE / "update_data.py").read_text(encoding="utf-8")
    ecriture = src.index("OUTPUT.write_text(json.dumps(output")
    assert 0 < src.index("_cliquet_volume(live_prices)") < ecriture
    assert 0 < src.index("_cliquet_volume_global(output.get") < ecriture
