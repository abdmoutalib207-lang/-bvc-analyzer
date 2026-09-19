#!/usr/bin/env python3
"""Contrat de la synchronisation quotidienne du cache historique."""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE / "pipeline"))

import recalculer_cache as rc


def _b(d, c, h=None):
    return {"d": d, "o": float(c), "h": float(h if h is not None else c),
            "l": float(c), "c": float(c), "v": 10}


class _Moteur:
    @staticmethod
    def compute_indicators(df):
        d = df.copy()
        dates = pd.to_datetime(d["date"])
        closes = [float(x) for x in d["close"]]
        highs = [float(x) for x in d["high"]]
        lows = [float(x) for x in d["low"]]
        n = len(d)
        candles = []
        for _, row in d.iterrows():
            date = pd.Timestamp(row["date"]).strftime("%Y-%m-%d")
            candles.append({"d": date, "o": float(row["open"]),
                            "h": float(row["high"]), "l": float(row["low"]),
                            "c": float(row["close"]), "v": int(row["volume"])})
        dernier = closes[-1]
        # Valeurs déterministes : leur but est de révéler ce qui avance et ce
        # qui doit rester protégé, pas de retester les formules financières.
        return {
            "rsi": float(n), "ma20": dernier, "ma50": dernier,
            "ma200": dernier, "h52w": max(highs), "l52w": min(lows),
            "h90": max(highs), "l90": min(lows),
            "macd": dernier - closes[0], "macd_signal": float(n),
            "macd_hist": dernier - closes[0] - float(n),
            "bb_upper": dernier + n, "bb_mid": dernier,
            "bb_lower": dernier - n, "stoch_k": float(n * 2),
            "stoch_d": float(n * 3), "last_close": dernier,
            "last_date": dates.iloc[-1].strftime("%Y-%m-%d"),
            "n_candles": n, "candles": candles[-250:],
        }


def _entree(serie):
    return _Moteur.compute_indicators(rc._df(serie))


def test_append_avance_les_champs_reproductibles_et_preserve_une_correction():
    # Le brut conserve une ancienne anomalie (haut 1700), mais le cache livré
    # porte déjà la correction réceptionnée : h52w=380 et bougie corrigée.
    brut_15 = _b("2026-09-15", 369, h=1700)
    b16 = _b("2026-09-16", 375, h=380)
    b18 = _b("2026-09-18", 382, h=385)
    ancien = _entree([brut_15, b16])
    ancien["h52w"] = 380.0
    ancien["candles"][0]["h"] = 380.0

    nouveau, rapport = rc._synchroniser_un_ajout(
        "SOT", ancien, [brut_15, b16, b18], _Moteur())

    assert nouveau is not None, rapport
    assert nouveau["last_date"] == "2026-09-18"
    assert nouveau["n_candles"] == 3
    assert nouveau["rsi"] == 3.0, "un champ reproductible doit avancer"
    assert nouveau["h52w"] == 380.0, "la correction historique ne doit pas être rejouée"
    assert "h52w" in rapport["champs_preserves"]
    assert nouveau["candles"][0]["h"] == 380.0
    assert nouveau["candles"][-1]["d"] == "2026-09-18"


def test_remplacement_intraday_de_la_derniere_bougie_est_synchronise():
    b15 = _b("2026-09-15", 90)
    ancien16 = _b("2026-09-16", 100)
    nouveau16 = _b("2026-09-16", 105)
    ancien = _entree([b15, ancien16])

    nouveau, rapport = rc._synchroniser_un_ajout(
        "SNA", ancien, [b15, nouveau16], _Moteur())

    assert nouveau is not None, rapport
    assert nouveau["last_date"] == "2026-09-16"
    assert nouveau["n_candles"] == 2
    assert nouveau["last_close"] == 105.0
    assert nouveau["ma20"] == 105.0
    assert nouveau["candles"][-1]["c"] == 105.0


def test_un_prefixe_historique_modifie_est_refuse():
    b14 = _b("2026-09-14", 80)
    b15 = _b("2026-09-15", 90)
    b16 = _b("2026-09-16", 100)
    ancien = _entree([b14, b15, b16])

    # La série courante a perdu une séance AVANT la date que le cache décrit.
    nouveau, rapport = rc._synchroniser_un_ajout(
        "SNA", ancien, [b15, b16, _b("2026-09-18", 105)], _Moteur())

    assert nouveau is None
    assert "préfixe modifié" in rapport["motif"]
