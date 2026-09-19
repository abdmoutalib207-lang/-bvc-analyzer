import json
from pathlib import Path

import pytest

from pipeline import import_cdg_session as imp

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "pipeline" / "bulletins" / "cdg_2026-09-18.json"


def test_releve_18_septembre_est_complet_et_date():
    doc = json.loads(SOURCE.read_text(encoding="utf-8"))
    assert doc["_meta"]["session_date"] == "2026-09-18"
    assert len(doc["cotations"]) == 81
    assert sum(float(x.get("cours") or 0) > 0 for x in doc["cotations"].values()) == 66


def test_identites_critiques_sont_traduites_avant_import():
    doc = json.loads(SOURCE.read_text(encoding="utf-8"))
    bougies, rapport = imp.traduire_source(doc)
    assert rapport["hors_univers"] == []
    assert rapport["bougies_cotees"] == 66

    # Codes officiels/CDG -> tickers internes : surtout ne jamais inverser
    # Sonasid (SID) et Stokvis (SNA).
    assert bougies["SNA"]["c"] == 1800.0   # SID = Sonasid
    assert bougies["STK"]["c"] == 63.26   # SNA = Stokvis
    assert bougies["TGCC"]["c"] == 672.0  # TGC = TGCC SA
    assert bougies["AKD"]["c"] == 1120.0  # AKT = Akdital
    assert bougies["ADI"] == {
        "d": "2026-09-18", "o": 400.0, "h": 400.0,
        "l": 376.0, "c": 377.0, "v": 30140155.2,
    }


def test_import_est_transactionnel_et_idempotent(tmp_path):
    doc = {
        "_meta": {"session_date": "2026-09-18", "source": "test"},
        "cotations": {
            "ADI": {"cours": 377, "ouverture": 400, "haut": 400,
                    "bas": 376, "qte": 10, "volume": 1000},
            "SID": {"cours": 1800, "ouverture": 1850, "haut": 1851,
                    "bas": 1800, "qte": 2, "volume": 3600},
        },
    }
    src = tmp_path / "src.json"
    src.write_text(json.dumps(doc), encoding="utf-8")
    candles = tmp_path / "candles"
    candles.mkdir()
    (candles / "ADI.json").write_text(json.dumps([
        {"d": "2026-09-16", "o": 390, "h": 391, "l": 385, "c": 390, "v": 10}
    ]), encoding="utf-8")
    (candles / "SNA.json").write_text(json.dumps([
        {"d": "2026-09-16", "o": 1800, "h": 1840, "l": 1790, "c": 1840, "v": 20}
    ]), encoding="utf-8")

    identite = lambda ticker, serie: (serie, {"refus": []})
    r1 = imp.importer(src, candles, ecrire=True, policy=identite)
    assert r1["n_ajoutes"] == 2
    assert r1["series_creees"] == []
    assert json.loads((candles / "ADI.json").read_text())[-1]["d"] == "2026-09-18"

    r2 = imp.importer(src, candles, ecrire=True, policy=identite)
    assert r2["n_ajoutes"] == 0
    assert r2["series_creees"] == []
    assert sorted(r2["deja_presents_identiques"]) == ["ADI", "SNA"]


def test_import_initialise_une_serie_absente_sans_inventer_d_historique(tmp_path):
    doc = {
        "_meta": {"session_date": "2026-09-18", "source": "test"},
        "cotations": {
            "MDP": {"cours": 24, "ouverture": 24.2, "haut": 24.4,
                    "bas": 23.8, "qte": 10, "volume": 1000},
        },
    }
    src = tmp_path / "src.json"
    src.write_text(json.dumps(doc), encoding="utf-8")
    candles = tmp_path / "candles"
    candles.mkdir()

    identite = lambda ticker, serie: (serie, {"refus": []})
    r = imp.importer(src, candles, ecrire=True, policy=identite)
    assert r["n_ajoutes"] == 1
    assert r["series_creees"] == ["MDP"]
    assert json.loads((candles / "MDP.json").read_text()) == [
        {"d": "2026-09-18", "o": 24.2, "h": 24.4,
         "l": 23.8, "c": 24.0, "v": 1000.0}
    ]


def test_import_refuse_un_ecrasement_different(tmp_path):
    doc = {
        "_meta": {"session_date": "2026-09-18"},
        "cotations": {
            "ADI": {"cours": 377, "ouverture": 400, "haut": 400,
                    "bas": 376, "qte": 10, "volume": 1000},
        },
    }
    src = tmp_path / "src.json"
    src.write_text(json.dumps(doc), encoding="utf-8")
    candles = tmp_path / "candles"
    candles.mkdir()
    original = [{"d": "2026-09-18", "o": 400, "h": 400, "l": 376, "c": 378, "v": 1000}]
    (candles / "ADI.json").write_text(json.dumps(original), encoding="utf-8")

    with pytest.raises(ValueError, match="déjà présente mais différente"):
        imp.importer(src, candles, ecrire=True,
                     policy=lambda ticker, serie: (serie, {"refus": []}))
    assert json.loads((candles / "ADI.json").read_text()) == original
