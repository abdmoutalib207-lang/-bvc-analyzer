#!/usr/bin/env python3
"""Imports historiques complets Sonasid / Stokvis : identité, série et cache."""
from __future__ import annotations

import csv
import io
import json
import sys
from pathlib import Path

import pandas as pd

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))
sys.path.insert(0, str(RACINE / "pipeline"))

SOURCES = {
    "SNA": RACINE / "sources" / "SNA" /
           "6a582f20-Cours_SID___2023-09-16_2026-09-15.csv",
    "STK": RACINE / "sources" / "STK" /
           "4b146aac-Cours_SNA_2023-09-17_2026-09-16.csv",
}
ATTENDU = {
    "SNA": {"code": "SID", "instrument": "SONASID", "fin": "2026-09-14"},
    "STK": {"code": "SNA", "instrument": "STOKVIS NORD AFRIQUE",
            "fin": "2026-09-15"},
}


def _rows(ticker):
    txt = SOURCES[ticker].read_text(encoding="utf-8-sig")
    return list(csv.DictReader(io.StringIO(txt), delimiter=";"))


def _iso(fr):
    j, m, a = fr.split("/")
    return f"{a}-{m}-{j}"


def _f(v, repli=None):
    v = (v or "").strip()
    if v in ("", "-", "--"):
        return repli
    return float(v)


def _normalisee(r):
    c = _f(r["Dernier Cours"])
    return {
        "d": _iso(r["Séance"]),
        "o": _f(r["Ouverture"], c),
        "h": _f(r["Plus Haut"], c),
        "l": _f(r["Plus Bas"], c),
        "c": c,
        "v": int(_f(r["Titres Échangés"], 0)),
    }


def _serie(ticker):
    return json.loads((RACINE / "pipeline" / "candles" / f"{ticker}.json")
                      .read_text(encoding="utf-8"))


def test_identite_et_code_operateur_sont_inverses_sans_ambiguite():
    for t, a in ATTENDU.items():
        rows = _rows(t)
        assert {r["Ticker"].strip() for r in rows} == {a["code"]}
        assert {r["Instrument"].strip() for r in rows} == {a["instrument"]}

    # Deux preuves arithmétiques indépendantes du nom de fichier.
    assert {
        round(float(r["Capitalisation"]) / float(r["Dernier Cours"]))
        for r in _rows("SNA")
    } == {3_900_000}

    regimes_stk = {
        round(float(r["Capitalisation"]) / float(r["Dernier Cours"]))
        for r in _rows("STK")
    }
    assert regimes_stk == {9_195_150, 17_695_150}


def test_le_changement_de_capital_stokvis_est_date_et_non_une_inversion():
    lignes = sorted(
        [(_iso(r["Séance"]),
          round(float(r["Capitalisation"]) / float(r["Dernier Cours"])))
         for r in _rows("STK")])
    anciens = [d for d, n in lignes if n == 9_195_150]
    nouveaux = [d for d, n in lignes if n == 17_695_150]
    assert max(anciens) == "2024-10-17"
    assert min(nouveaux) == "2024-10-18"


def test_la_serie_publiee_est_l_export_sur_toute_sa_periode():
    for t, a in ATTENDU.items():
        op = {_normalisee(r)["d"]: _normalisee(r) for r in _rows(t)}
        serie = _serie(t)
        couvert = [b for b in serie if b["d"] <= a["fin"]]
        assert [b["d"] for b in couvert] == sorted(op), (
            f"{t}: dates publiées différentes de l'export")
        ecarts = []
        for b in couvert:
            attendu = op[b["d"]]
            if any(float(b[k]) != float(attendu[k])
                   for k in ("o", "h", "l", "c", "v")):
                ecarts.append((b["d"], b, attendu))
        assert not ecarts, f"{t}: {len(ecarts)} bougies divergent {ecarts[:2]}"


def test_les_seances_valides_post_export_sont_conservees():
    sna, stk = _serie("SNA"), _serie("STK")
    assert [b["d"] for b in sna[-2:]] == ["2026-09-15", "2026-09-16"]
    assert stk[-1]["d"] == "2026-09-16"
    assert len(sna) == len(stk) == 735


def test_aucune_seance_feriee_ou_annulee_ne_survit():
    for t in ("SNA", "STK"):
        dates = {b["d"] for b in _serie(t)}
        assert "2026-07-30" not in dates
        assert "2026-09-17" not in dates


def test_stokvis_retrouve_son_vrai_sommet_et_jamais_490():
    serie = _serie("STK")
    b = next(x for x in serie if x["d"] == "2025-10-07")
    assert (b["o"], b["h"], b["l"], b["c"], b["v"]) == (
        133.6, 138.0, 133.6, 135.0, 120405)
    assert not [x for x in serie if x["c"] == 490.0]


def test_le_cache_est_exactement_recalculable_par_le_producteur():
    import recalculer_cache as rc

    livre = json.loads((RACINE / "pipeline" / "historical_data.json")
                       .read_text(encoding="utf-8"))
    r = rc.recalculer(["SNA", "STK"], [])
    recalcule = r["_nouveau"]

    champs = (
        "rsi", "ma20", "ma50", "ma200", "h52w", "l52w", "h90", "l90",
        "macd", "macd_signal", "macd_hist", "bb_upper", "bb_mid", "bb_lower",
        "stoch_k", "stoch_d", "last_close", "last_date", "n_candles", "candles",
    )
    for t in ("SNA", "STK"):
        assert {k: livre[t].get(k) for k in champs} == {
            k: recalcule[t].get(k) for k in champs
        }, f"{t}: historical_data.json ne décrit pas la série publiée"


def test_la_politique_connait_la_fin_de_l_historique_et_retire_une_annulation():
    from candle_write_policy import (
        appliquer_corrections_avant_ecriture,
        fin_historique_importe,
    )

    assert fin_historique_importe("SNA") == "2026-09-14"
    assert fin_historique_importe("STK") == "2026-09-15"
    # Compatibilité avec les anciens documents qui utilisent encore `periode`.
    assert fin_historique_importe("WAF") == "2026-09-16"

    serie = [
        {"d": "2026-09-16", "o": 1, "h": 1, "l": 1, "c": 1, "v": 1},
        {"d": "2026-09-17", "o": 2, "h": 2, "l": 2, "c": 2, "v": 2},
    ]
    out, rapport = appliquer_corrections_avant_ecriture("ZZZ", serie)
    assert [b["d"] for b in out] == ["2026-09-16"]
    assert rapport["seances_annulees_retirees"] == ["2026-09-17"]


def test_medias24_ne_peut_pas_ecraser_la_periode_importee():
    import generate_candles as gc

    existant = [
        {"d": "2025-10-07", "o": 133.6, "h": 138.0,
         "l": 133.6, "c": 135.0, "v": 120405},
        {"d": "2026-09-16", "o": 64.75, "h": 64.75,
         "l": 63.8, "c": 63.8, "v": 5133},
    ]
    secondaire = [
        {"d": "2025-10-07", "o": 80, "h": 80, "l": 80, "c": 80, "v": 1},
        {"d": "2026-09-18", "o": 64, "h": 65, "l": 64, "c": 65, "v": 10},
    ]
    out = gc._merge_respectant_historique_importe(
        "STK", existant, secondaire)
    par_date = {b["d"]: b for b in out}
    assert par_date["2025-10-07"]["h"] == 138.0
    assert par_date["2026-09-18"]["c"] == 65


def test_bvcscrap_ne_peut_pas_retrancher_ou_ecraser_l_historique():
    import collect_history_bvcscrap as ch

    existant = pd.DataFrame([
        {"date": pd.Timestamp("2025-10-07"), "open": 133.6, "high": 138.0,
         "low": 133.6, "close": 135.0, "volume": 120405},
        {"date": pd.Timestamp("2026-09-16"), "open": 64.75, "high": 64.75,
         "low": 63.8, "close": 63.8, "volume": 5133},
    ])
    secondaire = pd.DataFrame([
        {"date": pd.Timestamp("2025-10-07"), "open": 80.0, "high": 80.0,
         "low": 80.0, "close": 80.0, "volume": 1},
        {"date": pd.Timestamp("2026-09-18"), "open": 64.0, "high": 65.0,
         "low": 64.0, "close": 65.0, "volume": 10},
    ])
    out = ch.fusionner_avec_existant("STK", secondaire, existant)
    par_date = {str(r["date"])[:10]: r for _, r in out.iterrows()}
    assert par_date["2025-10-07"]["high"] == 138.0
    assert par_date["2026-09-16"]["close"] == 63.8
    assert par_date["2026-09-18"]["close"] == 65.0
