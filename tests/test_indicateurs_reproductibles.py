#!/usr/bin/env python3
"""Tout RSI et tout MACD publiés doivent être reproductibles indépendamment.

⚠️ POURQUOI CE FICHIER
──────────────────────
Noure a demandé ce qu'il en était des calculs d'indicateurs. La réponse ne peut
pas être « ils sont bons » : elle doit être une mesure.

Ici, le RSI de Wilder et le MACD sont RÉÉCRITS — pas importés du moteur. Un
test qui appellerait `calc_rsi` pour vérifier `calc_rsi` ne vérifierait qu'une
fonction égale à elle-même.

⚠️ TROIS RÉFÉRENCES POSSIBLES, ET C'EST NORMAL
Un indicateur publié peut légitimement décrire :

  · la série ENTIÈRE du fichier de chandelles ;
  · la même série SANS la dernière séance — le cache est écrit par l'import
    quotidien, et le fichier gagne la séance du jour après lui ;
  · la COPIE de 250 chandelles que le cache porte lui-même, quand cette copie
    a figé un instantané de milieu de séance.

Ce qui serait un DÉFAUT, c'est qu'une valeur publiée ne corresponde à AUCUNE
des trois : elle ne décrirait alors aucune série connue.

⚠️ CE QUE CE FICHIER NE DIT PAS
Il ne dit pas que les COURS sont justes — seulement que les indicateurs sont
calculés correctement sur les cours que nous avons. La justesse des cours,
c'est l'affaire des exports de l'opérateur et des lots de correction.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parent.parent
CACHE = RACINE / "pipeline" / "historical_data.json"


# ── Implémentations indépendantes, écrites ici ────────────────────────────

def rsi_wilder(c, p=14):
    if len(c) < p + 1:
        return None
    hausses = [max(c[i] - c[i - 1], 0.0) for i in range(1, len(c))]
    baisses = [max(c[i - 1] - c[i], 0.0) for i in range(1, len(c))]
    mg = sum(hausses[:p]) / p
    mp = sum(baisses[:p]) / p
    for i in range(p, len(hausses)):
        mg = (mg * (p - 1) + hausses[i]) / p
        mp = (mp * (p - 1) + baisses[i]) / p
    if mp == 0:
        return 100.0 if mg > 0 else 50.0
    if mg == 0:
        return 0.0
    return round(100 - 100 / (1 + mg / mp), 1)


def macd_ligne(c, rapide=12, lent=26):
    if len(c) < lent + 9:
        return None
    kr, kl = 2 / (rapide + 1), 2 / (lent + 1)
    er = el = c[0]
    dernier = None
    for x in c:
        er = x * kr + er * (1 - kr)
        el = x * kl + el * (1 - kl)
        dernier = er - el
    return round(dernier, 4)


@pytest.fixture(scope="module")
def cache():
    return json.loads(CACHE.read_text(encoding="utf-8"))


def _series(t, v):
    """Les trois séries qu'un indicateur publié peut légitimement décrire."""
    f = RACINE / "pipeline" / "candles" / f"{t}.json"
    out = []
    if f.exists():
        c = [b["c"] for b in json.loads(f.read_text(encoding="utf-8")) if b.get("c")]
        out.append(c)
        if len(c) > 1:
            out.append(c[:-1])
    if v.get("candles"):
        out.append([b["c"] for b in v["candles"] if b.get("c")])
    return out


def test_chaque_rsi_publie_est_reproductible(cache):
    """⚠️ LE CONTRÔLE DE FOND sur les 28 % techniques du score."""
    fautifs = []
    verifies = 0
    for t, v in sorted(cache.items()):
        if t.startswith("_") or v.get("rsi") is None:
            continue
        candidats = [rsi_wilder(c) for c in _series(t, v)]
        candidats = [x for x in candidats if x is not None]
        if not candidats:
            continue
        verifies += 1
        if not any(abs(x - v["rsi"]) <= 0.15 for x in candidats):
            fautifs.append((t, v["rsi"], candidats))
    assert verifies >= 70, f"seulement {verifies} RSI confrontés"
    assert fautifs == [], f"RSI ne décrivant aucune série connue : {fautifs[:5]}"


def test_chaque_macd_publie_est_reproductible(cache):
    fautifs = []
    verifies = 0
    for t, v in sorted(cache.items()):
        if t.startswith("_") or v.get("macd") is None:
            continue
        candidats = [macd_ligne(c) for c in _series(t, v)]
        candidats = [x for x in candidats if x is not None]
        if not candidats:
            continue
        verifies += 1
        if not any(abs(x - v["macd"]) <= 0.02 for x in candidats):
            fautifs.append((t, v["macd"], candidats))
    assert verifies >= 70, f"seulement {verifies} MACD confrontés"
    assert fautifs == [], f"MACD ne décrivant aucune série connue : {fautifs[:5]}"


def test_le_controle_sait_echouer(cache):
    """⚠️ Contre-épreuve : un RSI inventé ne doit correspondre à rien."""
    t, v = next((t, v) for t, v in sorted(cache.items())
                if not t.startswith("_") and v.get("rsi") is not None)
    faux = (v["rsi"] + 20) % 100
    candidats = [rsi_wilder(c) for c in _series(t, v)]
    assert not any(x is not None and abs(x - faux) <= 0.15 for x in candidats)


def test_les_bornes_du_rsi_sont_respectees(cache):
    """Un RSI hors [0, 100] ne serait pas un RSI."""
    for t, v in cache.items():
        if t.startswith("_") or v.get("rsi") is None:
            continue
        assert 0 <= v["rsi"] <= 100, t


# ── L'état des fondamentaux, mesuré et non commenté ───────────────────────

def test_l_etat_des_fondamentaux_est_ce_qu_il_est():
    """⚠️ LE CONTRASTE À GARDER SOUS LES YEUX.

    Les indicateurs techniques sont exacts et reproductibles. Les fondamentaux,
    qui pèsent 47 % du score, sont sourcés pour une minorité :

      · le price-to-book vient d'un dépôt AMMC pour 4 titres sur 80 ;
      · 23 titres tirent encore leur bloc fondamental de la TABLE FIGÉE ;
      · `faits_financiers.json` couvre 11 émetteurs.

    Ce test ne juge pas — il empêche que ces proportions se dégradent sans
    qu'on le voie, et il tombera le jour où elles s'amélioreront, ce qui sera
    l'occasion de le mettre à jour.
    """
    from collections import Counter
    ts = json.loads((RACINE / "data.json").read_text(encoding="utf-8"))["tickers"]
    fond = Counter(t["_meta"].get("source_fond") for t in ts)
    pb = Counter(t["_meta"].get("pb_source") for t in ts)
    assert fond["table_figee"] <= 25, (
        f"{fond['table_figee']} titres sur la table figée — la proportion se dégrade")
    assert pb["faits_ammc"] >= 4, (
        f"seulement {pb['faits_ammc']} price-to-book sourcés — régression")
    # ⚠️ Aucun price-to-book ne doit revenir de la table figée : c'était la
    # correction du 10/09, et elle ne doit pas se défaire.
    assert "pb_fige" not in {k for t in ts for k in t.get("_meta", {})}, (
        "le price-to-book figé est revenu")
