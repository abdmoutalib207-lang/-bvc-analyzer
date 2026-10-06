#!/usr/bin/env python3
"""Étape 1 du calibrage technique : quels ingrédients annoncent quelque chose
sur la BVC ? Banc d'essai — aucune note publiée n'est modifiée.

⚠️ LES RÈGLES SONT ÉCRITES ICI AVANT D'AVOIR VU LES RÉSULTATS
Chaque ingrédient est défini une fois, avec des paramètres de manuel, et n'est
pas retouché pour « mieux tomber ». Tester cent variantes et garder la
meilleure fabriquerait un gagnant par hasard. Les deux périodes servent de
garde-fou : un ingrédient qui ne tient que dans l'une n'est pas retenu.

Ingrédients, tous calculés AU JOUR t avec les seules séances connues à t :
  court terme
    rev5         variation des 5 dernières séances (reflux de court terme)
    pullback     tendance haussière (cours > MA200 et MA50 > MA200) ET cours
                 au moins 3 % sous la MA20 — « acheter la correction »
  moyen terme
    cassure90    clôture au-dessus du plus haut des 90 séances précédentes ET
                 volume du jour > 1,5 × médiane des 50 séances précédentes
    dist_ma200   écart du cours à la MA200
  long terme
    mom120       performance de t−120 à t−5 (on saute la dernière semaine,
                 convention du momentum : elle porte le reflux de court terme)
    mom250       performance de t−250 à t−5
    dist_h52     écart au plus haut des 250 séances
  secteur
    mom_secteur  moyenne de mom120 des AUTRES titres du secteur à la date
    rel_secteur  mom120 du titre moins mom_secteur (force dans son thème)
  défensif
    volat60      écart-type des variations quotidiennes sur 60 séances
    beta250      bêta contre le MASI sur 250 séances

Mesures : corrélation de rang JOUR PAR JOUR entre l'ingrédient et l'alpha
futur (rendement du titre moins celui du MASI) à 5, 20, 60, 120 et 250
séances ; par période (2023-10 → 2024-12, 2025-01 → 2026-10) et par tiers de
liquidité (montant médian échangé sur 20 séances, établi à la date). Pour les
événements (pullback, cassure90) : alpha moyen quand l'événement se produit,
une occurrence au plus par titre et par fenêtre de 20 séances, et rendement
moyen après un aller-retour à 2 % de frais.

⚠️ LIMITES, AVANT LES RÉSULTATS
1. Nos séries commencent au 04/10/2023 pour presque tous les titres : un
   ingrédient sur 250 séances n'existe qu'à partir d'octobre 2024, et
   l'horizon 250 séances s'arrête en octobre 2025. Le long terme est donc
   mesuré sur peu de fenêtres indépendantes — la preuve y est plus faible.
2. Observations chevauchantes (signalé, non corrigé).
3. RENDEMENT TOTAL depuis le 03/10/2026 : cours + dividendes réinvestis à la
   date de DÉTACHEMENT (`datasets/dividendes_bvc.json`, calendrier de
   l'opérateur). Couverture : 2025-2026 pour tous, 2024 pour Immorente
   seulement — ailleurs, 2024 et fin 2023 restent en cours seuls. Les
   INGRÉDIENTS restent calculés sur le cours : c'est lui que lit le chartiste.
4. Les secteurs sont ceux de `bvc_config.COMPANY_SECTORS`, figés aujourd'hui.

Usage : python3 pipeline/calibrage_signaux.py [--sortie FICHIER.json]
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from multiprocessing import Pool
from pathlib import Path

import numpy as np
import pandas as pd

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))
sys.path.insert(0, str(RACINE / "pipeline"))

from bvc_config import COMPANY_SECTORS  # noqa: E402

DEBUT = "2023-10-04"
COUPURE = "2025-01-01"
HORIZONS = (5, 20, 60, 120, 250)
FRAIS_AR = 0.02
CONTINUS = ("rev5", "dist_ma200", "mom120", "mom250", "dist_h52",
            "mom_secteur", "rel_secteur", "volat60", "beta250")
EVENEMENTS = ("pullback", "cassure90")


# Troncature des données à une date (AAAA-MM-JJ), pour rejouer une mesure telle
# qu'elle était à cette date. None = aucune troncature : comportement d'origine.
FIN: str | None = None


def _masi() -> pd.Series:
    m = json.loads((RACINE / "pipeline" / "masi_history.json").read_text(encoding="utf-8"))
    s = pd.Series({pd.Timestamp(d): float(v) for d, v in m["seances"].items()
                   if FIN is None or d <= FIN}).sort_index()
    return s


_DIV = None


def _dividendes() -> dict:
    global _DIV
    if _DIV is None:
        f = RACINE / "datasets" / "dividendes_bvc.json"
        _DIV = json.loads(f.read_text(encoding="utf-8")).get("dividendes", {}) if f.exists() else {}
    return _DIV


def _titre(t: str) -> pd.DataFrame | None:
    try:
        b = json.loads((RACINE / "pipeline" / "candles" / f"{t}.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if FIN is not None:
        b = [x for x in b if x["d"] <= FIN]
    if len(b) < 60:
        return None
    df = pd.DataFrame(b).rename(columns={"d": "date", "o": "open", "h": "high",
                                         "l": "low", "c": "close", "v": "volume"})
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date").reset_index(drop=True)
    df["volume"] = df["volume"].fillna(0)
    masi = _masi().reindex(df["date"]).values
    c, h, v = df["close"], df["high"], df["volume"]
    # Indice de rendement total : le dividende détaché s'ajoute au cours du
    # jour de détachement (ou de la première séance qui suit).
    div = pd.Series(0.0, index=df.index)
    for e in _dividendes().get(t, []):
        k = df.index[df["date"] >= pd.Timestamp(e["detachement"])]
        if len(k):
            div[k[0]] += e["montant_ajuste_split"]
    tr = ((c + div) / c.shift(1)).fillna(1.0).cumprod()
    ret = c.pct_change()
    rm = pd.Series(masi).pct_change()
    ma20, ma50, ma200 = c.rolling(20).mean(), c.rolling(50).mean(), c.rolling(200).mean()
    f = pd.DataFrame({"date": df["date"], "t": t})
    f["traite"] = v > 0
    f["close"] = c
    # Sortie de la zone de surachat du RSI 14 (passage sous 70), étape 3
    from technical.figures import _rsi
    rsi = pd.Series(_rsi(c.to_numpy(dtype=float)), index=df.index)
    f["sortie_surachat"] = (rsi.shift(1) > 70) & (rsi <= 70)
    f["rev5"] = c / c.shift(5) - 1
    f["pullback"] = (c > ma200) & (ma50 > ma200) & (c / ma20 - 1 <= -0.03)
    f["cassure90"] = (c > h.shift(1).rolling(90).max()) & (v > 1.5 * v.shift(1).rolling(50).median())
    f["dist_ma200"] = c / ma200 - 1
    f["mom120"] = c.shift(5) / c.shift(120) - 1
    f["mom250"] = c.shift(5) / c.shift(250) - 1
    f["dist_h52"] = c / h.rolling(250).max() - 1
    f["volat60"] = ret.rolling(60).std()
    cov = ret.rolling(250).cov(rm)
    f["beta250"] = cov / rm.rolling(250).var()
    ech = (c * v).where(v > 0)
    f["montant_median"] = ech.rolling(60, min_periods=10).median()
    for hz in HORIZONS:
        r = tr.shift(-hz) / tr - 1
        rmf = pd.Series(masi).shift(-hz) / pd.Series(masi) - 1
        f[f"a{hz}"] = r - rmf.values
        f[f"r{hz}"] = r
    return f


def panel() -> pd.DataFrame:
    titres = [p.stem for p in sorted((RACINE / "pipeline" / "candles").glob("*.json"))]
    with Pool() as pool:
        lots = [x for x in pool.map(_titre, titres) if x is not None]
    p = pd.concat(lots, ignore_index=True)
    p["secteur"] = p["t"].map(COMPANY_SECTORS)
    # Momentum du secteur SANS le titre lui-même, à la date
    g = p.groupby(["date", "secteur"])["mom120"]
    somme, n = g.transform("sum"), g.transform("count")
    p["mom_secteur"] = (somme - p["mom120"].fillna(0)) / (n - p["mom120"].notna().astype(int))
    p.loc[(n - p["mom120"].notna().astype(int)) < 1, "mom_secteur"] = np.nan
    p["rel_secteur"] = p["mom120"] - p["mom_secteur"]
    p = p[(p["date"] >= DEBUT) & p["traite"]]
    q1, q2 = p["montant_median"].quantile([1 / 3, 2 / 3])
    p["liquidite"] = np.where(p["montant_median"] >= q2, "haute",
                              np.where(p["montant_median"] >= q1, "moyenne", "basse"))
    p.attrs["seuils"] = [round(float(q1)), round(float(q2))]
    return p


def _ic(sous: pd.DataFrame, x: str, y: str) -> dict:
    d = sous[["date", x, y]].dropna()
    ics = []
    for _, g in d.groupby("date"):
        if len(g) >= 10 and g[x].nunique() > 1:
            c = g[x].rank().corr(g[y].rank())
            if c is not None and not math.isnan(c):
                ics.append(c)
    if not ics:
        return {"jours": 0}
    a = np.array(ics)
    return {"ic": round(float(a.mean()), 4), "jours": len(a),
            "part_positive": round(float((a > 0).mean()), 3)}


def _evenement(sous: pd.DataFrame, x: str, hz: int) -> dict:
    e = sous[sous[x] == True].sort_values(["t", "date"])  # noqa: E712
    # Une occurrence au plus par titre et par fenêtre de 20 séances
    garde, dernier = [], {}
    for idx, row in e.iterrows():
        k = row["t"]
        if k in dernier and (row["date"] - dernier[k]).days < 28:
            continue
        dernier[k] = row["date"]
        garde.append(idx)
    e = e.loc[garde].dropna(subset=[f"a{hz}"])
    if e.empty:
        return {"n": 0}
    a, r = e[f"a{hz}"], e[f"r{hz}"]
    return {"n": int(len(e)), "titres": int(e["t"].nunique()),
            "alpha_moyen": round(float(a.mean()), 4),
            "alpha_part_positive": round(float((a > 0).mean()), 3),
            "rendement_net_frais": round(float(r.mean() - FRAIS_AR), 4)}


def mesurer(p: pd.DataFrame) -> dict:
    periodes = {"2023-10_2024-12": p["date"] < COUPURE, "2025-01_2026-10": p["date"] >= COUPURE}
    out = {}
    for liq in ("toutes", "haute", "moyenne", "basse"):
        base = p if liq == "toutes" else p[p["liquidite"] == liq]
        out[liq] = {}
        for nom, masque in periodes.items():
            sous = base[masque.loc[base.index]]
            r = {"observations": int(len(sous))}
            for x in CONTINUS:
                r[x] = {f"h{hz}": _ic(sous, x, f"a{hz}") for hz in HORIZONS}
            for x in EVENEMENTS:
                r[x] = {f"h{hz}": _evenement(sous, x, hz) for hz in HORIZONS}
            out[liq][nom] = r
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sortie", default="")
    a = ap.parse_args()
    p = panel()
    res = {"_quoi": "Étape 1 du calibrage technique — banc d'essai des ingrédients",
           "_methode": __doc__.split("Usage :")[0].strip(),
           "frais_aller_retour": FRAIS_AR,
           "seuils_liquidite_dh": p.attrs["seuils"],
           "observations": int(len(p)), "titres": int(p["t"].nunique()),
           "periode": [str(p["date"].min().date()), str(p["date"].max().date())],
           "mesures": mesurer(p)}
    texte = json.dumps(res, ensure_ascii=False, indent=1)
    if a.sortie:
        Path(a.sortie).write_text(texte + "\n", encoding="utf-8")
    print(texte[:400])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
