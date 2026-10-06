#!/usr/bin/env python3
"""Le backtest publié ne doit jamais changer en silence.

Trois familles :
  - un CAS JOUET dont les attendus sont calculés à la main (voir commentaires) ;
  - le DÉTERMINISME : deux exécutions sur les mêmes entrées, même fichier à
    l'octet près ;
  - la SÉPARATION DES GRILLES de confiance (06/10/2026).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd
import pytest

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE / "pipeline"))

import backtest_reproductible as br  # noqa: E402


def test_t_a_la_main():
    # x = [1,2,3], h=1 : moyenne 2, écart-type 1 → t naïf = 2 / (1/√3) = 3,4641.
    # Retard 0 : gamma0 = (1+0+1)/3 = 2/3 → t = 2 / √((2/3)/3) = 4,2426.
    s = br.t_serie([1, 2, 3], 1)
    assert s["t_naif"] == pytest.approx(3.4641, abs=1e-4)
    assert s["t_newey_west"] == pytest.approx(4.2426, abs=1e-4)
    assert s["t_non_chevauchant"] == pytest.approx(3.4641, abs=1e-4)
    # x = [0,2,0,2], h=2 : e = [-1,1,-1,1], gamma0 = 1, gamma1 = -3/4,
    # variance = 1 + 2·(1−1/2)·(−0,75) = 0,25 → t = 1 / √(0,25/4) = 4.
    assert br.t_serie([0, 2, 0, 2], 2)["t_newey_west"] == pytest.approx(4.0)
    # Une date sur deux : [0, 0] → écart-type nul → pas de t.
    assert br.t_serie([0, 2, 0, 2], 2)["t_non_chevauchant"] is None


def test_conclusion_refusee_sur_peu_de_jours():
    b = br._bloc_t([0.1] * 5 + [0.2] * 5, 5)
    assert b["conclusion_autorisee"] is False
    assert "insuffisant" in str(b["lecture"])


def test_grilles_jamais_melangees():
    assert br.grille("2026-10-05") == "v1"
    assert br.grille("2026-10-06") == "v2"
    assert br.palier("ACHETER ★★") == "ACHETER"
    assert br.palier("ÉVITER FORT") == "ÉVITER"
    assert br.palier("Données insuffisantes") is None


def test_cas_jouet(tmp_path, monkeypatch):
    dates = pd.bdate_range("2026-09-01", periods=6)  # d0 … d5
    masi = pd.Series([1000, 1000, 1000, 1000, 1000, 1020.0], index=dates)
    d = [x.strftime("%Y-%m-%d") for x in dates]

    def ecrire(t, closes):
        (tmp_path / f"{t}.json").write_text(json.dumps(
            [{"d": d[i], "o": c, "h": c, "l": c, "c": c, "v": 100} for i, c in enumerate(closes)]))

    ecrire("A", [100, 100, 100, 100, 100, 110])   # dividende 5 détaché en d3
    ecrire("B", [100, 100, 100, 100, 100, 90])
    monkeypatch.setattr(br, "_dividendes",
                        lambda: {"A": [{"detachement": d[3], "montant_ajuste_split": 5.0}]})
    note = lambda t, sig, conf, asof=d[0]: {"date": d[0], "t": t, "v53": 7.0, "sig": sig,  # noqa: E731
                                            "conf": conf, "asof": asof}
    notes = [note("A", "ACHETER ★★", 3), note("B", "ÉVITER FORT", 4),
             note("A", "ACHETER ★★", 1),            # confiance insuffisante
             note("B", "ATTENDRE", 3, asof="2026-08-05")]  # cours d'une autre séance
    df, ecarts = br.observations(notes, tmp_path, masi)
    assert ecarts["confiance_insuffisante"] == 1 and ecarts["cours_d_une_autre_seance"] == 1
    assert len(df) == 2
    # A : (105/100)·(110/100) − 1 = 0,155 ; MASI +2 % → alpha 0,135.
    a = df[df["t"] == "A"].iloc[0]
    assert a["r5"] == pytest.approx(0.155) and a["a5"] == pytest.approx(0.135)
    # B : −10 % ; alpha −0,12.
    assert df[df["t"] == "B"].iloc[0]["a5"] == pytest.approx(-0.12)
    m = br.mesurer_grille(df, 5)
    ach, evi = m["par_palier"]["ACHETER"], m["par_palier"]["ÉVITER"]
    assert ach["observations"] == 1 and ach["alpha_moyen_brut"] == pytest.approx(0.135)
    assert ach["alpha_moyen_net_frais"] == pytest.approx(0.115)       # 0,135 − 2 %
    assert ach["rendement_total_net_frais_moyen"] == pytest.approx(0.135)  # 0,155 − 2 %
    assert ach["bon_sens"] == 1.0
    assert evi["alpha_moyen_brut"] == pytest.approx(-0.12) and evi["bon_sens"] == 1.0
    # Horizon 20 : fenêtre hors calendrier, rien à mesurer, et c'est compté.
    assert ecarts["horizon_non_atteint"]["h20"] == 2


def test_rupture_de_serie_ecartee(tmp_path, monkeypatch):
    dates = pd.bdate_range("2026-09-01", periods=6)
    masi = pd.Series([1000.0] * 6, index=dates)
    d = [x.strftime("%Y-%m-%d") for x in dates]
    (tmp_path / "Z.json").write_text(json.dumps(
        [{"d": d[i], "o": c, "h": c, "l": c, "c": c, "v": 1} for i, c in enumerate([100, 100, 10, 10, 10, 10])]))
    monkeypatch.setattr(br, "_dividendes", lambda: {})
    n = {"date": d[0], "t": "Z", "v53": 7.0, "sig": "ACHETER", "conf": 5, "asof": d[0]}
    df, ecarts = br.observations([n], tmp_path, masi)
    assert ecarts["rupture_de_serie"] == 1 and df["a5"].isna().all()


def test_determinisme_a_l_octet(tmp_path):
    """Même entrées, même commit : le même fichier, à l'octet près."""
    r1 = br.construire("score_history")
    r2 = br.construire("score_history")
    assert json.dumps(r1, ensure_ascii=False) == json.dumps(r2, ensure_ascii=False)
    a = br.ecrire(r1, tmp_path / "a")
    b = br.ecrire(r2, tmp_path / "b")
    assert a[0].name == b[0].name
    assert a[0].read_bytes() == b[0].read_bytes()
    assert a[1].read_bytes() == b[1].read_bytes()
    # Les empreintes sont bien là : une par entrée et par chandelle lue.
    sha = r1["entrees"]["sha256"]
    assert len(sha["candles"]) == len(list((RACINE / "pipeline" / "candles").glob("*.json")))
    assert all(len(v) == 64 for k, v in sha.items() if isinstance(v, str))
    # Le nom du fichier porte la dernière séance des entrées, pas l'horloge.
    assert a[0].name == f"backtest_{r1['entrees']['derniere_seance']}.json"


def test_les_limites_precedent_les_resultats():
    cles = list(br.construire("score_history"))
    assert cles.index("limites_ecrites_avant_les_resultats") < cles.index("resultats")
