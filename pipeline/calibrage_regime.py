#!/usr/bin/env python3
"""Étape 2 du calibrage technique : le RÉGIME DE MARCHÉ explique-t-il que les
signaux de tendance aient marché en 2023-24 et plus en 2025-26 ?

⚠️ RÈGLE FIXÉE AVANT LA MESURE (03/10/2026)
« Marché en tendance » au jour t, avec les seules données connues à t :
    MASI > sa moyenne des 200 dernières séances
    ET plus de 50 % des titres liquides au-dessus de leur propre MA200.
Variante mesurée à part, sans être choisie après coup : MASI > MA200 seul.
« Titres liquides » : les deux tiers supérieurs du montant médian échangé
(seuil de l'étape 1), établi à la date.

Ingrédients rejoués, tels que définis à l'étape 1 et 1 bis, SANS retouche :
momentum 120 séances, momentum de secteur, force dans le secteur, écart à la
MA200 (corrélation de rang jour par jour) ; pullback, cassure 90 jours,
double creux, rebond Fibonacci, sortie de surachat du RSI (événements).
Mesure : alpha en rendement total contre le MASI, à 20, 60 et 120 séances,
pour chaque période ET chaque régime.

⚠️ CE QUI COMPTERAIT COMME UNE RÉPONSE
Un ingrédient « dépend du régime » s'il est nettement positif quand le
régime est allumé et nul ou négatif quand il est éteint — DANS LES DEUX
PÉRIODES. Un résultat qui ne tient que dans l'une ne répond pas.

⚠️ LIMITES
1. Le MASI ne passe que quelques fois au-dessus et au-dessous de sa MA200 en
   trois ans : ce sont peu d'épisodes indépendants, même avec beaucoup de
   jours. La preuve sera faible, et elle est publiée comme telle.
2. Observations chevauchantes (signalé, non corrigé).

Usage : python3 pipeline/calibrage_regime.py [--sortie FICHIER.json]
"""
from __future__ import annotations

import argparse
import json
import sys
from multiprocessing import Pool
from pathlib import Path

import numpy as np
import pandas as pd

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE / "pipeline"))

from calibrage_figures import _evenements  # noqa: E402
from calibrage_signaux import _ic, _masi, panel  # noqa: E402

COUPURE = "2025-01-01"
HORIZONS = (20, 60, 120)
CONTINUS = ("mom120", "mom_secteur", "rel_secteur", "dist_ma200")
EVTS_PANEL = ("pullback", "cassure90")
EVTS_FIGURES = ("double_creux", "fibo_rebond_382_618", "rsi_sortie_surachat")
FRAIS_AR = 0.02


def regimes(p: pd.DataFrame) -> pd.DataFrame:
    """Par date : MASI > MA200, part des titres liquides au-dessus de leur MA200."""
    m = _masi()
    ma = m.rolling(200).mean()
    r = pd.DataFrame({"masi_sur_ma200": (m > ma) & ma.notna()})
    liq = p[p["liquidite"] != "basse"]
    part = liq.groupby("date")["dist_ma200"].apply(lambda s: (s.dropna() > 0).mean()
                                                    if s.notna().sum() >= 10 else np.nan)
    r = r.join(part.rename("part_sur_ma200"), how="left")
    r["tendance"] = r["masi_sur_ma200"] & (r["part_sur_ma200"] > 0.5)
    return r


def _evt(e: pd.DataFrame, h: int) -> dict:
    a = e[f"a{h}"].dropna()
    if a.empty:
        return {"n": 0}
    r = e.loc[a.index, f"r{h}"]
    sd = a.std(ddof=1) if len(a) > 1 else 0
    return {"n": int(len(a)), "alpha_moyen": round(float(a.mean()), 4),
            "part_alpha_positif": round(float((a > 0).mean()), 3),
            "t": round(float(a.mean() / (sd / len(a) ** 0.5)), 2) if sd else None,
            "rendement_net_frais": round(float(r.mean() - FRAIS_AR), 4)}


def _dedup(e: pd.DataFrame, col: str) -> pd.DataFrame:
    e = e[e[col] == True].sort_values(["t", "date"])  # noqa: E712
    garde, dernier = [], {}
    for idx, row in e.iterrows():
        if row["t"] in dernier and (row["date"] - dernier[row["t"]]).days < 28:
            continue
        dernier[row["t"]] = row["date"]
        garde.append(idx)
    return e.loc[garde]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sortie", default="")
    arg = ap.parse_args()
    p = panel()
    reg = regimes(p)
    p = p.join(reg, on="date")
    titres = [f.stem for f in sorted((RACINE / "pipeline" / "candles").glob("*.json"))]
    with Pool() as pool:
        fig = pd.DataFrame([o for lot in pool.map(_evenements, titres) for o in lot])
    fig["date"] = pd.to_datetime(fig["date"])
    fig = fig.join(reg, on="date")
    seuil = float(p["montant_median"].quantile(1 / 3))
    fig = fig[fig["montant"] >= seuil]
    liq = p[p["liquidite"] != "basse"]

    periodes = {"2023-10_2024-12": lambda d: d < COUPURE, "2025-01_2026-10": lambda d: d >= COUPURE}
    res = {"_quoi": "Étape 2 — régime de marché", "_methode": __doc__.split("Usage :")[0].strip(),
           "jours_en_tendance": {}, "mesures": {}}
    for per, garde in periodes.items():
        jours = reg[[garde(str(d.date())) for d in reg.index]]
        jours = jours[jours.index >= pd.Timestamp("2023-10-04")]
        res["jours_en_tendance"][per] = {
            "regle_principale": round(float(jours["tendance"].mean()), 3),
            "masi_sur_ma200_seul": round(float(jours["masi_sur_ma200"].mean()), 3),
            "jours": int(len(jours))}
    for regle in ("tendance", "masi_sur_ma200"):
        out = {}
        for per, garde in periodes.items():
            sp = liq[[garde(str(d.date())) for d in liq["date"]]]
            sf = fig[[garde(str(d.date())) for d in fig["date"]]]
            for etat in (True, False):
                cle = f"{per}|{'allume' if etat else 'eteint'}"
                a = sp[sp[regle] == etat]
                b = sf[sf[regle] == etat]
                r = {"observations": int(len(a))}
                for x in CONTINUS:
                    r[x] = {f"h{h}": _ic(a, x, f"a{h}") for h in HORIZONS}
                for x in EVTS_PANEL:
                    r[x] = {f"h{h}": _evt(_dedup(a, x), h) for h in HORIZONS}
                for x in EVTS_FIGURES:
                    r[x] = {f"h{h}": _evt(b[b["signal"] == x], h) for h in HORIZONS}
                out[cle] = r
        res["mesures"][regle] = out
    texte = json.dumps(res, ensure_ascii=False, indent=1)
    if arg.sortie:
        Path(arg.sortie).write_text(texte + "\n", encoding="utf-8")
    print(json.dumps(res["jours_en_tendance"], ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
