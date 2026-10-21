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

RÈGLES (21/10/2026) : `--regles 2026-10-03` rejoue les règles d'origine,
`--regles 2026-10-21` (défaut) ajoute les règles « figures strictes » de
`technical/regles_strictes.py`. `--fin` tronque les chandelles (le banc
d'essai initial s'arrêtait au 02/10/2026), `--seuil-liquidite` fixe le seuil de
l'univers « liquides » (sinon : tiers inférieur des montants des événements
du run — il bouge dès que l'ensemble d'événements bouge). Le VOLUME est mesuré,
pas filtré : section `volume` du résultat.

Usage : python3 pipeline/calibrage_figures.py [--sortie FICHIER.json] [--regles AAAA-MM-JJ]
                                              [--fin AAAA-MM-JJ] [--seuil-liquidite DH]
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
from technical.lignes import gaps, lignes  # noqa: E402
from technical.regles_strictes import VOLUME_SEUIL_INFO, ratio_volume  # noqa: E402

# Injectés par `main()` ou par l'appelant (`frequences.py` pose `FIN`), AVANT la
# création du Pool. None = tout / règles les plus récentes.
FIN: str | None = None
REGLES: str | None = None

DEBUT, COUPURE = "2023-10-04", "2025-01-01"
HORIZONS = (20, 60, 120)
FRAIS_AR = 0.02


def _evenements(t: str) -> list[dict]:
    try:
        b = json.loads((RACINE / "pipeline" / "candles" / f"{t}.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    if FIN is not None:
        b = [x for x in b if x["d"] <= FIN]
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
    oe, he, le = (df[k].astype(float).values[ech] for k in ("o", "h", "l"))
    kw = {} if REGLES is None else {"regles": REGLES}
    fl = figures(ce, **kw) + lignes(ce, **kw)
    ve = df["v"].astype(float).values[ech]
    vol = {(int(ech[j]), nom): ratio_volume(ve, j) for j, nom, sens in fl}   # information
    brut = [(int(ech[j]), nom, sens) for j, nom, sens in
            fl + indicateurs(ce) + gaps(oe, he, le, ce)]
    # Hebdomadaire (03/10/2026) : la même recette sur des bougies de semaine,
    # pivots 10 %, expiration 12 semaines. Le signal est daté de la DERNIÈRE
    # séance échangée de la semaine de cassure — jamais plus tôt.
    sem = df.loc[ech].assign(s=df.loc[ech, "date"].dt.to_period("W-FRI"))
    der = sem.groupby("s").apply(lambda g: g.index.max()).to_numpy()
    cw = sem.groupby("s")["c"].last().astype(float).to_numpy()
    for j, nom, sens in figures(cw, 0.10, 12, **kw) + lignes(cw, 0.10, 12, **kw):
        brut.append((int(der[j]), "hebdo_" + nom, sens))
    out, dernier = [], {}
    for i, nom, sens in sorted(brut):
        d = df["date"][i]
        if str(d.date()) < DEBUT:
            continue
        if nom in dernier and i - dernier[nom] < 20:
            continue
        dernier[nom] = i
        o = {"t": t, "date": str(d.date()), "signal": nom, "sens": sens, "montant": montant[i],
             "vol_ratio": vol.get((i, nom))}
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


def _stats_signees(g: pd.DataFrame, h: int) -> dict:
    """Part et médiane de l'alpha SIGNÉ (alpha × sens) : valable pour un mélange
    de figures haussières et baissières."""
    a = (g[f"a{h}"] * g["sens"]).dropna()
    if a.empty:
        return {"n": 0}
    return {"n": int(len(a)), "dans_le_bon_sens": round(float((a > 0).mean()), 3),
            "alpha_signe_median": round(float(a.median()), 4)}


def _volume(ev: pd.DataFrame) -> dict:
    """Les cassures où le volume vaut au moins 1,5 × la médiane des 20 séances
    précédentes font-elles mieux que les autres ? MESURE seulement : aucun
    filtre n'en découle sans décision d'Abd. Figures et droites quotidiennes
    déclenchées (hors Fibonacci : un constat, pas une cassure)."""
    g = ev[ev["vol_ratio"].notna() & ~ev["signal"].str.startswith("fibo_")].copy()
    out = {"seuil_ratio": VOLUME_SEUIL_INFO,
           "definition": "volume de la séance de cassure ÷ médiane du volume des 20 séances échangées précédentes",
           "note": "alpha signé = alpha × sens ; part = part des cas dans le bon sens ; aucun filtre"}

    def coupe(x: pd.DataFrame) -> dict:
        fort, faible = x[x["vol_ratio"] >= VOLUME_SEUIL_INFO], x[x["vol_ratio"] < VOLUME_SEUIL_INFO]
        return {f"h{h}": {"ratio_ge_1_5": _stats_signees(fort, h), "ratio_lt_1_5": _stats_signees(faible, h)}
                for h in HORIZONS}
    out["tous_signaux"] = {lib: {"toutes_periodes": coupe(s),
                                 "2023-10_2024-12": coupe(s[s["date"] < COUPURE]),
                                 "2025-01_2026-10": coupe(s[s["date"] >= COUPURE])}
                           for lib, s in (("tous", g), ("liquides", g[g["liquide"]]))}
    out["par_signal"] = {nom: {lib: coupe(s) for lib, s in (("tous", x), ("liquides", x[x["liquide"]]))}
                         for nom, x in g.groupby("signal")}
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sortie", default="")
    ap.add_argument("--regles", default=None)
    ap.add_argument("--fin", default=None)
    ap.add_argument("--seuil-liquidite", type=float, default=None)
    arg = ap.parse_args()
    global FIN, REGLES
    from technical.regles_strictes import REGLES as DEFAUT, verifier
    import calibrage_signaux as cs
    REGLES = verifier(arg.regles or DEFAUT)
    FIN = cs.FIN = arg.fin
    titres = [p.stem for p in sorted((RACINE / "pipeline" / "candles").glob("*.json"))]
    with Pool() as pool:
        ev = pd.DataFrame([o for lot in pool.map(_evenements, titres) for o in lot])
    seuil = arg.seuil_liquidite if arg.seuil_liquidite is not None else float(ev["montant"].quantile(1 / 3))
    ev["liquide"] = ev["montant"] >= seuil
    res = {"_quoi": "Étape 1 bis — figures chartistes et signaux d'indicateurs",
           "_methode": __doc__.split("Usage :")[0].strip(),
           "regles": REGLES, "fin_donnees": FIN,
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
    res["volume"] = _volume(ev)
    texte = json.dumps(res, ensure_ascii=False, indent=1)
    if arg.sortie:
        Path(arg.sortie).write_text(texte + "\n", encoding="utf-8")
    print(f"{len(ev)} événements")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
