#!/usr/bin/env python3
"""Étape 1 bis : les FIGURES CHARTISTES et les signaux d'indicateurs ont-ils
annoncé quelque chose sur la BVC ? Banc d'essai — aucune note publiée n'est
modifiée.

Figures (détection : `pipeline/technical/figures.py`, paramètres fixés AVANT la
mesure) : double creux, double sommet, ETE, ETE inversée, tasse avec anse,
triangles ascendant / descendant / symétrique, rebond Fibonacci 38,2-61,8 %,
retracement au-delà de 78,6 %. Indicateurs : croisement doré / mortel,
MACD, sorties de survente / surachat du RSI, compression de Bollinger,
divergences RSI.

Mesure pour chaque signal, daté du jour de la CASSURE (jamais du creux) :
alpha en RENDEMENT TOTAL contre le MASI à 20, 60 et 120 séances ; part des cas
dans le bon sens ; rendement après 2 % de frais aller-retour ; t naïf.
Une occurrence au plus par titre, par signal et par fenêtre de 20 séances.

⚠️ LIMITES, AVANT LES RÉSULTATS
1. Une figure haussière se juge par un alpha POSITIF, une baissière par un
   alpha NÉGATIF. La BVC ne permet pas la vente à découvert : un signal
   baissier vaut comme « sortir » ou « ne pas acheter », pas comme un gain.
2. Une vingtaine de signaux, trois horizons, deux périodes : sur autant
   d'essais, quelques résultats « forts » sortiront par hasard. N'est retenu
   que ce qui garde le même sens sur les DEUX périodes avec un |t| ≥ 2
   dans chacune.
3. Figures rares : beaucoup de cases ont moins de 20 cas. Un chiffre sur
   10 cas est une anecdote, il est publié avec son effectif.
4. Dividendes : 2024-2026 ; octobre-décembre 2023 en cours seuls.

Usage : python3 pipeline/calibrage_figures.py [--sortie FICHIER.json]
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

from calibrage_signaux import _dividendes, _masi  # noqa: E402
from technical.figures import figures, indicateurs  # noqa: E402

DEBUT, COUPURE = "2023-10-04", "2025-01-01"
HORIZONS = (20, 60, 120)
FRAIS_AR = 0.02


def _evenements(t: str) -> list[dict]:
    try:
        b = json.loads((RACINE / "pipeline" / "candles" / f"{t}.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    if len(b) < 80:
        return []
    df = pd.DataFrame(b)
    df["date"] = pd.to_datetime(df["d"])
    df = df.sort_values("date").reset_index(drop=True)
    df["v"] = df["v"].fillna(0)
    c = df["c"].astype(float)
    div = pd.Series(0.0, index=df.index)
    for e in _dividendes().get(t, []):
        k = df.index[df["date"] >= pd.Timestamp(e["detachement"])]
        if len(k):
            div[k[0]] += e["montant_ajuste_split"]
    tr = ((c + div) / c.shift(1)).fillna(1.0).cumprod().values
    masi = _masi().reindex(df["date"]).values
    montant = (c * df["v"]).where(df["v"] > 0).rolling(60, min_periods=10).median().values
    ech = df.index[df["v"] > 0].to_numpy()
    ce = c.values[ech]
    out, dernier = [], {}
    for j, nom, sens in sorted(figures(ce) + indicateurs(ce)):
        i = int(ech[j])
        d = df["date"][i]
        if str(d.date()) < DEBUT:
            continue
        if nom in dernier and i - dernier[nom] < 20:
            continue
        dernier[nom] = i
        o = {"t": t, "date": str(d.date()), "signal": nom, "sens": sens, "montant": montant[i]}
        for h in HORIZONS:
            if i + h < len(df) and not np.isnan(masi[i]) and not np.isnan(masi[i + h]):
                r = tr[i + h] / tr[i] - 1
                o[f"r{h}"] = r
                o[f"a{h}"] = r - (masi[i + h] / masi[i] - 1)
        out.append(o)
    return out


def _stats(g: pd.DataFrame, h: int, sens: int) -> dict:
    a = g[f"a{h}"].dropna()
    if a.empty:
        return {"n": 0}
    r = g.loc[a.index, f"r{h}"]
    sd = a.std(ddof=1) if len(a) > 1 else 0.0
    return {"n": int(len(a)), "titres": int(g.loc[a.index, "t"].nunique()),
            "alpha_moyen": round(float(a.mean()), 4),
            "alpha_median": round(float(a.median()), 4),
            "dans_le_bon_sens": round(float(((a * sens) > 0).mean()), 3),
            "t": round(float(a.mean() / (sd / len(a) ** 0.5)), 2) if sd else None,
            "rendement_net_frais": round(float(r.mean() - FRAIS_AR), 4)}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sortie", default="")
    arg = ap.parse_args()
    titres = [p.stem for p in sorted((RACINE / "pipeline" / "candles").glob("*.json"))]
    with Pool() as pool:
        ev = pd.DataFrame([o for lot in pool.map(_evenements, titres) for o in lot])
    seuil = float(ev["montant"].quantile(1 / 3))
    ev["liquide"] = ev["montant"] >= seuil
    res = {"_quoi": "Étape 1 bis — figures chartistes et signaux d'indicateurs",
           "_methode": __doc__.split("Usage :")[0].strip(),
           "seuil_liquidite_dh": round(seuil), "evenements": int(len(ev)),
           "signaux": {}}
    for nom, g in ev.groupby("signal"):
        sens = int(g["sens"].iloc[0])
        r = {"sens_attendu": sens}
        for lib, sous in (("tous", g), ("liquides", g[g["liquide"]])):
            r[lib] = {p: {f"h{h}": _stats(s, h, sens) for h in HORIZONS}
                      for p, s in (("2023-10_2024-12", sous[sous["date"] < COUPURE]),
                                   ("2025-01_2026-10", sous[sous["date"] >= COUPURE]))}
        # Verdict pré-enregistré : même sens sur les deux périodes, |t| ≥ 2 dans chacune
        ok = {}
        for h in HORIZONS:
            s1 = r["liquides"]["2023-10_2024-12"][f"h{h}"]
            s2 = r["liquides"]["2025-01_2026-10"][f"h{h}"]
            ok[f"h{h}"] = bool(s1.get("t") and s2.get("t") and s1["t"] * sens >= 2 and s2["t"] * sens >= 2)
        r["retenu_liquides"] = ok
        res["signaux"][nom] = r
    texte = json.dumps(res, ensure_ascii=False, indent=1)
    if arg.sortie:
        Path(arg.sortie).write_text(texte + "\n", encoding="utf-8")
    print(f"{len(ev)} événements")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
