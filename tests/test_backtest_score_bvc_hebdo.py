"""Garde-fous de la mesure hebdomadaire du Score BVC (`pipeline/backtest_score_bvc_hebdo.py`).

Ne gèle PAS les fréquences (ce sera le travail d'`ingenieur-tests`) : vérifie les
briques et la cohérence interne de l'artefact daté.
"""
import json
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))
sys.path.insert(0, str(RACINE / "pipeline"))

from pipeline import backtest_score_bvc_hebdo as h  # noqa: E402

ARTEFACTS = sorted((RACINE / "datasets" / "backtests").glob("score_bvc_hebdo_*.json"))


def test_wilson_valeur_connue():
    lo, hi = h.wilson(50, 100)
    assert abs(lo - 0.4038) < 1e-3 and abs(hi - 0.5962) < 1e-3
    assert h.wilson(0, 0) == [None, None]


def test_une_fin_de_semaine_par_semaine_et_semaine_en_cours_exclue():
    bg = {f"T{i}": [{"d": d, "c": 10.0, "v": 1} for d in
                    ("2026-11-02", "2026-11-03", "2026-11-06", "2026-11-09", "2026-11-10")] for i in range(25)}
    assert h.fins_de_semaine(bg) == ["2026-11-06"]   # la semaine du 09 n'est pas close


def test_artefact_coherent():
    assert ARTEFACTS, "artefact hebdomadaire absent"
    a = json.loads(ARTEFACTS[-1].read_text(encoding="utf-8"))
    assert a["seuil_effectif_publiable"]["n_min"] == 300
    assert a["seuil_effectif_publiable"]["blocs_de_20_seances_min"] == 30
    assert a["horizon_seances"] == 20 and a["frais_aller_retour"] == 0.02
    assert a["tranches"] == ["< 40", "40 – 59", "60 – 74", "≥ 75"]
    for defn in a["resultats"].values():
        for v in ("sans_rentabilite", "avec_roe_actuel"):
            x = defn[v]
            assert sum(t["n"] for t in x["tranches"].values()) == x["observations"]
            for t in x["tranches"].values():
                assert t["gagnants"] <= t["n"]
                assert t["effectif_suffisant"] == (t["n"] >= 300 and t["blocs_de_20_seances_touches"] >= 30)
    assert "_biais" in a["resultats"]["principal_echange_a_la_cloture_de_la_semaine"]["avec_roe_actuel"]
    assert a["entrees"]["roe_2025_table"] and a["entrees"]["roe_2025_empreinte_sha256"]
