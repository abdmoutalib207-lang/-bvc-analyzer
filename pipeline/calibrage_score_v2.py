#!/usr/bin/env python3
"""Étape 3 du calibrage technique : un NOUVEAU pilier technique, bâti avec les
seuls ingrédients qui ont tenu, comparé à l'actuel. Mesure seule — rien n'est
branché sur la note publiée.

⚠️ LA RECETTE EST ÉCRITE ICI AVANT LE TEST (03/10/2026)
Base 5. Le marché est « en tendance » selon la règle de l'étape 2 (MASI >
MA200 et plus de 50 % des titres liquides au-dessus de leur MA200).
  En tendance :
    + 2,0   cassure du plus haut 90 jours avec volume dans les 20 dernières séances
    + 1,5   sortie de la zone de surachat du RSI (70) dans les 20 dernières séances
    + 1,0   pullback en cours (tendance haussière, cours ≥ 3 % sous la MA20)
  Hors tendance :
    − 1,0   pullback en cours (il a perdu hors tendance)
    ± 1,5   momentum : 3 × (rang du momentum 120 séances dans la cote − 0,5)
Bornée à [0, 10]. Les points reprennent l'ordre de grandeur des alphas
mesurés sur 2023-24 SEULEMENT ; aucun n'est ajusté après coup.

⚠️ L'HONNÊTETÉ SUR LE « HORS ÉCHANTILLON »
Les poids viennent de 2023-24. Mais le CHOIX des ingrédients a été fait en
voyant aussi 2025-26 (étapes 1 et 2) : la période 2025-26 n'est donc pas un
test vierge. Le seul test vraiment neuf sera l'avenir — d'où un suivi « en
ombre » avant toute publication.

Mesure : titres liquides (deux tiers supérieurs), corrélation de rang jour par
jour avec l'alpha en rendement total à 20, 60 et 120 séances ; alpha et part
de cas gagnants du quintile haut et du quintile bas ; ancien pilier mesuré à
l'identique sur les mêmes observations.

Usage : python3 pipeline/calibrage_score_v2.py [--sortie FICHIER.json]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE / "pipeline"))
sys.path.insert(0, str(RACINE))

from calibrage_regime import regimes  # noqa: E402
from calibrage_signaux import _ic, panel  # noqa: E402
from technical.score_v2 import score_v2  # noqa: E402  — définition unique

COUPURE = "2025-01-01"
HORIZONS = (20, 60, 120)
RECENT = 20


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sortie", default="")
    arg = ap.parse_args()
    p = panel()
    reg = regimes(p)
    p = p.join(reg[["tendance"]], on="date")
    p = p.sort_values(["t", "date"])
    p["cassure_recente"] = p.groupby("t")["cassure90"].transform(
        lambda s: s.astype(float).rolling(RECENT, min_periods=1).max() > 0)
    p["surachat_recent"] = p.groupby("t")["sortie_surachat"].transform(
        lambda s: s.astype(float).rolling(RECENT, min_periods=1).max() > 0)
    p["rang_mom"] = p.groupby("date")["mom120"].rank(pct=True)
    p["score_v2"] = [score_v2(bool(a), bool(b), bool(c), bool(d), e) for a, b, c, d, e in
                     zip(p["tendance"].fillna(False), p["cassure_recente"], p["surachat_recent"],
                         p["pullback"].fillna(False), p["rang_mom"])]
    liq = p[p["liquidite"] != "basse"]
    res = {"_quoi": "Étape 3 — nouveau pilier technique contre l'ancien",
           "_methode": __doc__.split("Usage :")[0].strip(), "mesures": {}}
    for per, masque in (("2023-10_2024-12", liq["date"] < COUPURE),
                        ("2025-01_2026-10", liq["date"] >= COUPURE)):
        s = liq[masque]
        r = {"observations": int(len(s)),
             "repartition_score": {k: int(v) for k, v in s["score_v2"].round().value_counts().sort_index().items()}}
        for h in HORIZONS:
            a = f"a{h}"
            d = s.dropna(subset=[a])
            q = d.groupby("date")["score_v2"].rank(pct=True)
            haut, bas = d[q > 0.8][a], d[q <= 0.2][a]
            r[f"h{h}"] = {"ic_v2": _ic(d, "score_v2", a),
                          "alpha_quintile_haut": round(float(haut.mean()), 4) if len(haut) else None,
                          "part_gagnante_haut": round(float((haut > 0).mean()), 3) if len(haut) else None,
                          "alpha_quintile_bas": round(float(bas.mean()), 4) if len(bas) else None,
                          "part_gagnante_bas": round(float((bas > 0).mean()), 3) if len(bas) else None}
        res["mesures"][per] = r
    texte = json.dumps(res, ensure_ascii=False, indent=1)
    if arg.sortie:
        Path(arg.sortie).write_text(texte + "\n", encoding="utf-8")
    print(texte)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
