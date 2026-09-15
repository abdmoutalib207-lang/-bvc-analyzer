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
    # ⚠️ LA SÉRIE GRANDIT. Le moteur y ajoute la séance du jour à chaque run —
    # `tests.yml` le fait avant d'exécuter cette suite. Figer « 30 bougies »
    # aurait donc rougi dès le lendemain, et c'est ce qui est arrivé en CI le
    # 15/09 : 31 bougies contre 30 attendues. Ce qui est DURABLE, c'est que
    # chaque séance de l'export se retrouve chez nous à l'identique.
    assert len(ops) == 30, "l'export archivé, lui, ne bouge pas"
    assert len(serie) >= len(ops)
    couvertes = 0
    for b in serie:
        r = ops.get(b["d"])
        if r is None:
            assert b["d"] > max(ops), (
                f"{b['d']} n'est ni dans l'export ni postérieure à lui")
            continue
        couvertes += 1
        assert r["Instrument"].strip() == "T2S GROUP HOLDING"
        assert b["c"] == float(r["Dernier Cours"])
        assert b["o"] == float(r["Ouverture"])
        assert b["v"] == int(float(r["Titres Échangés"])), b["d"]
    assert couvertes == len(ops), "des séances de l'export manquent chez nous"


def test_la_serie_est_triee_sans_doublon_et_coherente(serie):
    dates = [b["d"] for b in serie]
    assert dates == sorted(dates) and len(set(dates)) == len(dates)
    for b in serie:
        assert b["l"] <= min(b["o"], b["c"]) <= max(b["o"], b["c"]) <= b["h"], b["d"]


def test_t2s_commence_a_son_introduction(serie):
    """⚠️ T2S est une introduction récente. Sa série ne commence pas en 2023
    parce que le titre n'existait pas — ce n'est pas un trou."""
    assert serie[0]["d"] == "2026-07-27"
    # ⚠️ Pas d'égalité sur la dernière date : le moteur ajoute la séance du
    # jour. On exige seulement qu'elle ne précède pas la fin de l'export.
    assert serie[-1]["d"] >= "2026-09-14"


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
    # ⚠️ Les valeurs ne sont pas figées : le cache est recalculé quand la série
    # grandit. Ce qui est durable, c'est que ces « extrêmes 52 semaines » ne
    # portent que sur les séances dont nous disposons.
    assert cache["h52w"] >= max(b["h"] for b in serie[:30])
    assert cache["l52w"] <= min(b["l"] for b in serie[:30])
    assert serie[0]["d"] == "2026-07-27", (
        "l'étiquette « 52 semaines » ne couvre que depuis l'introduction")
    assert len(serie) < 250, (
        "si la série dépasse une année de cotation, ce test n'a plus d'objet")


# ── L'écran : une moyenne absente s'affiche « — », jamais « 0,00 » ─────────

def _jsx() -> str:
    """Le bloc JSX d'index.html, COMMENTAIRES ÔTÉS.

    ⚠️ Sans ce filtrage, les tests ci-dessous passeraient sur le commentaire
    qui explique la correction plutôt que sur le code. Ce dépôt s'y est laissé
    prendre cinq fois.
    """
    import re
    s = (RACINE / "index.html").read_text(encoding="utf-8")
    bloc = re.search(r'<script type="text/babel"[^>]*>(.*?)</script>', s, re.S).group(1)
    bloc = re.sub(r"\{/\*.*?\*/\}", "", bloc, flags=re.S)
    return re.sub(r"/\*.*?\*/", "", bloc, flags=re.S)


def test_aucune_moyenne_n_est_rendue_par_un_zero():
    """⚠️ `px(r.ma50||0)` affichait « 0,00 » pour une moyenne absente. Un zéro
    se lit comme un cours, pas comme une absence — et depuis que `calc_ma`
    rend None sous sa période, le cas se produit pour de vrai (T2S)."""
    src = _jsx()
    for champ in ("ma20", "ma50", "ma200"):
        assert f"px(r.{champ}||0)" not in src, (
            f"r.{champ} est rendu par zéro quand il est absent")
        assert f"r.{champ}?px(r.{champ})" in src, (
            f"r.{champ} doit être rendu « — » quand il est absent")
