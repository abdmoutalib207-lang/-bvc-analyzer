"""Le suivi des pièces couvre TOUS les titres publiés, pas un sous-ensemble."""
import datetime as dt
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tools"))
import couverture_pieces as cp  # noqa: E402


def test_un_etat_par_titre_publie():
    with open(os.path.join(cp.RACINE, "data.json"), encoding="utf-8") as f:
        attendus = {t["symbol"] for t in json.load(f)["tickers"]}
    assert {l["symbol"] for l in cp.etat()} == attendus


def test_titre_sans_releve_est_a_faire(tmp_path):
    (tmp_path / "datasets" / "releves").mkdir(parents=True)
    (tmp_path / "data.json").write_text(json.dumps({"tickers": [
        {"symbol": "AAA", "note_fond": {"couverture": 1.0, "composantes": {}}},
        {"symbol": "BBB", "note_fond": {"couverture": 0.5, "composantes": {"bilan": {"note": None}}}},
        {"symbol": "CCC", "note_fond": {"couverture": 1.0, "composantes": {}}},
    ]}), encoding="utf-8")
    (tmp_path / "datasets" / "releves" / "BBB.json").write_text(
        json.dumps({"releve_le": "2026-10-10"}), encoding="utf-8")
    (tmp_path / "datasets" / "releves" / "CCC.json").write_text(
        json.dumps({"releve_le": "2026-01-01"}), encoding="utf-8")
    e = {l["symbol"]: l for l in cp.etat(str(tmp_path), dt.date(2026, 10, 16))}
    assert e["AAA"]["a_faire"]            # aucun relevé, même noté à 100 %
    assert not e["BBB"]["a_faire"]
    assert e["BBB"]["manquantes"] == ["bilan"]
    assert e["CCC"]["a_faire"]            # relevé périmé
