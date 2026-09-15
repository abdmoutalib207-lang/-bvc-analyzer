#!/usr/bin/env python3
"""Une moyenne ne s'invente pas sur moins de séances que sa période.

⚠️ LE DÉFAUT, MESURÉ LE 15/09/2026
──────────────────────────────────
`calc_ma` rendait la moyenne de CE QU'ELLE AVAIT quand la série était trop
courte. Un titre de trente séances sortait donc une « MA200 » qui était une
moyenne de trente jours, et rien à l'écran ne le disait.

    32 titres sur 74 affichaient une MA200 calculée sur 52 à 166 séances.

Ce n'est pas une approximation : c'est un indicateur qui porte le nom d'un
autre. Le terminal rend une valeur absente par « — » ; c'est la seule écriture
juste tant que la période n'est pas atteinte.

⚠️ CE QUE LA CORRECTION A RÉVÉLÉ EN CASCADE
Rendre `None` a fait tomber le moteur — deux fois, avant toute publication :

    calc_score_tech   '>' not supported between float and NoneType
    setup technique   '<' not supported between float and NoneType

Le code supposait qu'une moyenne mobile est toujours un nombre. Une moyenne
absente ne vaut désormais NI POUR NI CONTRE, exactement comme un RSI absent
depuis le 12/09. Lui attribuer zéro aurait été pire que le défaut : zéro se
lit « sous les deux moyennes », c'est-à-dire −1,2 point de score technique.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE / "pipeline"))

SOURCE = "sources/T2S"


@pytest.fixture(scope="module")
def collecteur():
    import importlib.util
    sys.argv = ["collect_history_bvcscrap.py"]
    spec = importlib.util.spec_from_file_location(
        "col_ma", RACINE / "pipeline" / "collect_history_bvcscrap.py")
    m = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(m)
    except SystemExit:
        pass
    return m


# ── La moyenne elle-même ───────────────────────────────────────────────────

@pytest.mark.parametrize("periode", [20, 50, 200])
def test_pas_de_moyenne_sous_la_periode(ud, collecteur, periode):
    """⚠️ Les DEUX producteurs. Corriger un seul les ferait diverger — c'est
    la leçon du RSI, où 73 des 74 valeurs publiées venaient de l'autre copie.
    """
    import pandas as pd
    court = pd.Series(range(periode - 1), dtype=float)
    assert ud.calc_ma(court, periode) is None
    assert collecteur.calc_ma(court, periode) is None


@pytest.mark.parametrize("periode", [20, 50, 200])
def test_la_moyenne_est_rendue_des_que_la_periode_est_atteinte(ud, collecteur, periode):
    """⚠️ Contre-épreuve : une garde qui refuserait toujours ne servirait à
    rien. À period séances exactement, la moyenne existe et vaut la moyenne."""
    import pandas as pd
    s = pd.Series(range(periode), dtype=float)
    attendu = round((periode - 1) / 2, 2)      # moyenne de 0..period-1, écrite ici
    assert ud.calc_ma(s, periode) == attendu
    assert collecteur.calc_ma(s, periode) == attendu


def test_les_deux_copies_rendent_la_meme_chose(ud, collecteur):
    import pandas as pd
    s = pd.Series([100.0, 101.0, 99.0, 102.0, 98.0] * 12)   # 60 points
    for p in (20, 50, 200):
        assert ud.calc_ma(s, p) == collecteur.calc_ma(s, p)


# ── Le score : une moyenne absente ne vaut ni pour ni contre ───────────────

def test_le_score_technique_s_abstient_sur_une_moyenne_absente(ud):
    """⚠️ Zéro n'est pas l'abstention : zéro se lit « sous les deux moyennes »."""
    base = ud.calc_score_tech(50.0, 100.0, None, None, 120.0, 80.0)
    dessous = ud.calc_score_tech(50.0, 100.0, 110.0, 120.0, 120.0, 80.0)
    assert base is not None
    assert base != dessous, "l'absence se confond avec « sous les deux moyennes »"


def test_le_score_technique_ne_leve_plus_sur_une_moyenne_absente(ud):
    """Le run s'arrêtait net sur T2S. Aucune combinaison ne doit lever."""
    for ma20, ma50 in ((None, None), (None, 95.0), (105.0, None)):
        v = ud.calc_score_tech(45.0, 100.0, ma20, ma50, 120.0, 80.0)
        assert 0 <= v <= 10


def test_la_position_dans_la_range_tolere_des_extremes_absents(ud):
    assert 0 <= ud.calc_score_tech(45.0, 100.0, 99.0, 98.0, None, None) <= 10


# ── La série T2S ───────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def serie():
    return json.loads((RACINE / "pipeline" / "candles" / "T2S.json")
                      .read_text(encoding="utf-8"))


def test_la_serie_t2s_vient_de_l_export_archive(serie):
    """⚠️ L'attendu n'est pas recalculé par le code éprouvé : il est relu dans
    l'export de l'opérateur, archivé avec son empreinte."""
    import csv, io
    src = sorted((RACINE / SOURCE).glob("*.csv"))[0]
    ops = {}
    for r in csv.DictReader(io.StringIO(src.read_text(encoding="utf-8-sig")),
                            delimiter=";"):
        j, m, a = r["Séance"].split("/")
        ops[f"{a}-{m}-{j}"] = r
    assert len(serie) == len(ops) == 30
    for b in serie:
        r = ops[b["d"]]
        assert r["Instrument"].strip() == "T2S GROUP HOLDING"
        assert b["c"] == float(r["Dernier Cours"])
        assert b["o"] == float(r["Ouverture"])
        assert b["v"] == int(float(r["Titres Échangés"])), b["d"]


def test_la_serie_est_triee_sans_doublon_et_coherente(serie):
    dates = [b["d"] for b in serie]
    assert dates == sorted(dates) and len(set(dates)) == len(dates)
    for b in serie:
        assert b["l"] <= min(b["o"], b["c"]) <= max(b["o"], b["c"]) <= b["h"], b["d"]


def test_t2s_commence_a_son_introduction(serie):
    """⚠️ T2S est une introduction récente. Sa série ne commence pas en 2023
    parce que le titre n'existait pas — ce n'est pas un trou."""
    assert serie[0]["d"] == "2026-07-27"
    assert serie[-1]["d"] == "2026-09-14"


def test_le_cache_t2s_n_annonce_aucune_moyenne_longue():
    """⚠️ LE POINT DE CE LOT. Trente séances : pas de MA50, pas de MA200.
    L'ancienne version en aurait publié deux, égales à la moyenne des trente."""
    cache = json.loads((RACINE / "pipeline" / "historical_data.json")
                       .read_text(encoding="utf-8"))["T2S"]
    assert cache["n_candles"] == 30
    assert cache["ma50"] is None and cache["ma200"] is None
    assert cache["ma20"] == 234.93
    assert cache["rsi"] == 18.6, "RSI de Wilder réel, et non la valeur neutre 50"


def test_les_extremes_de_t2s_ne_couvrent_pas_52_semaines(serie):
    """⚠️ UNE LIMITE, ÉCRITE PLUTÔT QUE TUE.

    `h52w` et `l52w` de T2S valent 267,55 et 224,00 — les extrêmes de trente
    séances, pas de cinquante-deux semaines. C'est arithmétiquement « le plus
    haut des 52 dernières semaines », mais le titre n'a que sept semaines de
    cotation : l'étiquette promet plus que la mesure. Ce test fige le constat
    pour qu'il ne se perde pas.
    """
    cache = json.loads((RACINE / "pipeline" / "historical_data.json")
                       .read_text(encoding="utf-8"))["T2S"]
    assert cache["h52w"] == max(b["h"] for b in serie) == 267.55
    assert cache["l52w"] == min(b["l"] for b in serie) == 224.0
    assert len(serie) < 250, (
        "si la série dépasse une année de cotation, ce test n'a plus d'objet")
