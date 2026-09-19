import json
from pathlib import Path

import pytest

from pipeline import finaliser_snapshot as fs


def _ecrire(path: Path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj), encoding="utf-8")


def _ticker(symbol, asof, price):
    return {"symbol": symbol, "price": price, "_meta": {"prix_asof": asof}}


def test_retard_16_vers_18_est_remplace_sans_toucher_les_autres(tmp_path, monkeypatch):
    data = tmp_path / "data.json"
    candles = tmp_path / "candles"
    _ecrire(data, {
        "updated": "2026-09-18T01:00:00+0100",
        "date_analyse": "2026-09-18",
        "market_status": "CLOSED",
        "masi": {"value": 18000, "asof": "2026-09-16", "stale": True},
        "tickers": [_ticker("AAA", "2026-09-16", 100), _ticker("BBB", "2026-09-18", 200)],
    })
    _ecrire(candles / "AAA.json", [
        {"d": "2026-09-16", "o": 99, "h": 101, "l": 98, "c": 100, "v": 10},
        {"d": "2026-09-18", "o": 100, "h": 112, "l": 100, "c": 110, "v": 20},
    ])
    _ecrire(candles / "BBB.json", [
        {"d": "2026-09-18", "o": 200, "h": 201, "l": 199, "c": 200, "v": 5},
    ])

    candidat = {
        "updated": "2026-09-19T14:00:00+0100",
        "date_analyse": "2026-09-19",
        "market_status": "CLOSED",
        "masi": {"value": 18100, "asof": "2026-09-18", "stale": False},
        "tickers": [_ticker("AAA", "2026-09-18", 110), _ticker("BBB", "2026-09-18", 999)],
    }
    rapport = fs.finaliser(data, candles, runner=lambda: candidat)
    resultat = json.loads(data.read_text())
    par = {x["symbol"]: x for x in resultat["tickers"]}

    assert rapport["n_remplaces"] == 1
    assert par["AAA"]["price"] == 110
    assert par["AAA"]["_meta"]["prix_asof"] == "2026-09-18"
    # BBB n'était pas en retard : le finaliseur n'a pas le droit de le remplacer.
    assert par["BBB"]["price"] == 200
    assert resultat["masi"]["asof"] == "2026-09-18"


def test_echec_du_recalcul_ne_modifie_pas_data_json(tmp_path):
    data = tmp_path / "data.json"
    candles = tmp_path / "candles"
    initial = {
        "updated": "x",
        "masi": {"value": 18000, "asof": "2026-09-16"},
        "tickers": [_ticker("AAA", "2026-09-16", 100)],
    }
    _ecrire(data, initial)
    _ecrire(candles / "AAA.json", [
        {"d": "2026-09-18", "o": 100, "h": 111, "l": 99, "c": 110, "v": 20},
    ])

    with pytest.raises(RuntimeError, match="rattrapage incomplet"):
        fs.finaliser(data, candles, runner=lambda: {
            "tickers": [_ticker("AAA", "2026-09-16", 100)]
        })
    assert json.loads(data.read_text()) == initial


def test_snapshot_aligne_ne_relance_pas_le_moteur(tmp_path):
    data = tmp_path / "data.json"
    candles = tmp_path / "candles"
    _ecrire(data, {"tickers": [_ticker("AAA", "2026-09-18", 110)]})
    _ecrire(candles / "AAA.json", [{"d": "2026-09-18", "c": 110}])

    appele = False
    def runner():
        nonlocal appele
        appele = True
        return {}

    rapport = fs.finaliser(data, candles, runner=runner)
    assert rapport["modifie"] is False
    assert appele is False


def test_serie_legacy_absente_de_data_est_ignoree(tmp_path):
    data = tmp_path / "data.json"
    candles = tmp_path / "candles"
    _ecrire(data, {"tickers": [_ticker("TGCC", "2026-09-18", 672)]})
    _ecrire(candles / "TGCC.json", [{"d": "2026-09-18", "c": 672}])
    # Ancien symbole conservé pour l'historique local mais absent de l'univers
    # public courant : il ne doit pas créer un faux retard.
    _ecrire(candles / "TGC.json", [{"d": "2026-05-12", "c": 500}])

    assert fs.retards_snapshot(data, candles) == {}

    appele = False
    def runner():
        nonlocal appele
        appele = True
        return {}

    rapport = fs.finaliser(data, candles, runner=runner)
    assert rapport["modifie"] is False
    assert appele is False
