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
    # ⚠️ 14/10/2026 : les extrêmes glissants avancent depuis la copie
    # CORRIGÉE du cache. L'anomalie brute (1700) n'est pas rejouée, mais le
    # nouveau plus-haut (385, bougie du 18/09) est pris : l'ancienne attente
    # (380 figé) était le défaut lui-même — c'est ainsi que le plus-haut
    # 90 jours de CMT est resté à 5 100 après la sortie du sommet de la fenêtre.
    assert nouveau["h52w"] == 385.0, "la correction est respectée et le nouveau sommet compte"
    assert nouveau["h52w"] != 1700.0, "la correction historique ne doit pas être rejouée"
    assert "h52w" in rapport["champs_recalcules"]
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


def test_un_sommet_sorti_de_la_fenetre_ne_reste_pas_fige():
    """Cas CMT : sommet ancien hors fenêtre de 90 jours, valeur du cache figée."""
    ancien_sommet = _b("2026-06-18", 5100, h=5100)
    recentes = [_b(f"2026-09-{j:02d}", 4500, h=4550) for j in (1, 2, 3)]
    nouvelle = _b("2026-09-04", 4520, h=4573)
    ancien = _entree([ancien_sommet] + recentes)
    ancien["h90"] = 5100.0                       # valeur restée figée
    nouveau, rapport = rc._synchroniser_un_ajout(
        "CMT", ancien, [ancien_sommet] + recentes + [nouvelle], _Moteur())
    assert nouveau is not None, rapport
    ext = rc.extremes_glissants(nouveau["candles"], serie_complete=True)
    assert nouveau["h90"] == ext["h90"]
    assert nouveau["h90"] != 5100.0 or ext["h90"] == 5100.0


def test_extremes_sur_une_fenetre_non_couverte_sont_preserves():
    """Une copie qui ne couvre pas 52 semaines et n'est pas la série entière :
    aucun extrême calculé sur une fenêtre partielle."""
    copie = [_b("2026-09-15", 100), _b("2026-09-16", 101)]
    assert rc.extremes_glissants(copie, maintenant="2026-10-14") is None
    assert rc.extremes_glissants(copie, maintenant="2026-10-14", serie_complete=True) == {
        "h52w": 101.0, "l52w": 100.0, "h90": 101.0, "l90": 100.0}


def test_bornes_des_fenetres_comme_le_calculateur():
    copie = [_b("2025-10-01", 900, h=900), _b("2026-07-10", 500, h=520), _b("2026-10-13", 400, h=410)]
    x = rc.extremes_glissants(copie, maintenant="2026-10-14")
    assert x["h52w"] == 520.0          # le 01/10/2025 est hors des 52 semaines
    assert x["h90"] == 410.0           # le 10/07 est hors des 90 jours
