"""Nouveau pilier technique (« v2 ») — UNE seule définition, partagée par la
mesure (`pipeline/calibrage_score_v2.py`) et par le moteur, où il tourne en
MODE OMBRE : calculé et publié à côté de l'ancien, sans entrer dans la note.

⚠️ RECETTE FIXÉE LE 03/10/2026, AVANT LE TEST (étape 3 du calibrage)
Base 5.
  Marché en tendance (MASI > MA200 ET plus de 50 % des titres liquides
  au-dessus de leur MA200) :
    + 2,0   cassure du plus haut 90 jours avec volume (> 1,5 × médiane 50 s.)
            dans les 20 dernières séances
    + 1,5   sortie de la zone de surachat du RSI 14 (passage sous 70) dans les
            20 dernières séances
    + 1,0   pullback en cours (cours > MA200, MA50 > MA200, cours ≥ 3 % sous MA20)
  Hors tendance :
    − 1,0   pullback en cours
    ± 1,5   3 × (rang du momentum 120 séances dans la cote − 0,5)
Bornée à [0, 10].

⚠️ Toutes les grandeurs se lisent sur les chandelles telles qu'elles sont
stockées (une ligne par séance, échangée ou non), comme dans la mesure.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

RECENT = 20


def _rsi(c: np.ndarray, p: int = 14) -> np.ndarray:
    from technical.figures import _rsi as rsi
    return rsi(c, p)


def score_v2(tendance: bool, cassure_recente: bool, surachat_recent: bool,
             pullback: bool, rang_mom: float | None) -> float:
    s = 5.0
    if tendance:
        s += 2.0 * cassure_recente + 1.5 * surachat_recent + 1.0 * pullback
    else:
        s -= 1.0 * pullback
        if rang_mom is not None and not np.isnan(rang_mom):
            s += 3.0 * (rang_mom - 0.5)
    return round(min(max(s, 0.0), 10.0), 2)


def signaux_titre(bougies) -> dict | None:
    """Signaux du titre à la DERNIÈRE séance des chandelles fournies."""
    if bougies is None:
        return None
    df = pd.DataFrame(bougies) if not hasattr(bougies, "columns") else bougies.copy()
    if len(df) < 60 or not {"c", "h", "v"} <= set(df.columns):
        return None
    df = df.sort_values("d").reset_index(drop=True)
    c = pd.to_numeric(df["c"], errors="coerce")
    h = pd.to_numeric(df["h"], errors="coerce")
    v = pd.to_numeric(df["v"], errors="coerce").fillna(0)
    ma20, ma50, ma200 = c.rolling(20).mean(), c.rolling(50).mean(), c.rolling(200).mean()
    cassure = (c > h.shift(1).rolling(90).max()) & (v > 1.5 * v.shift(1).rolling(50).median())
    rsi = pd.Series(_rsi(c.to_numpy(dtype=float)), index=df.index)
    sortie = (rsi.shift(1) > 70) & (rsi <= 70)
    pullback = (c > ma200) & (ma50 > ma200) & (c / ma20 - 1 <= -0.03)
    mom = c.shift(5) / c.shift(120) - 1
    dist = c / ma200 - 1
    der = len(df) - 1
    return {"date": str(df["d"].iloc[der])[:10], "echange": bool(v.iloc[der] > 0),
            "cassure_recente": bool(cassure.iloc[-RECENT:].any()),
            "surachat_recent": bool(sortie.iloc[-RECENT:].any()),
            "pullback": bool(pullback.iloc[der]),
            "mom120": None if pd.isna(mom.iloc[der]) else float(mom.iloc[der]),
            "dist_ma200": None if pd.isna(dist.iloc[der]) else float(dist.iloc[der])}


def regime(masi: dict, dist_ma200_liquides: list) -> dict:
    """État du marché à la dernière séance de l'historique du MASI."""
    s = pd.Series({k: float(v) for k, v in masi.items()}).sort_index()
    ma = s.rolling(200).mean()
    sur = bool(len(s) >= 200 and s.iloc[-1] > ma.iloc[-1])
    vals = [x for x in dist_ma200_liquides if x is not None]
    part = (sum(x > 0 for x in vals) / len(vals)) if len(vals) >= 10 else None
    return {"date": s.index[-1] if len(s) else None, "masi_sur_ma200": sur,
            "part_titres_liquides_sur_ma200": None if part is None else round(part, 3),
            "tendance": bool(sur and part is not None and part > 0.5)}


def scores_cote(bougies_par_titre: dict, masi: dict, liquides: set) -> dict:
    """{ticker: {score, signaux…}} pour toute la cote, et l'état du marché."""
    sig = {t: signaux_titre(b) for t, b in bougies_par_titre.items()}
    sig = {t: s for t, s in sig.items() if s}
    reg = regime(masi, [s["dist_ma200"] for t, s in sig.items() if t in liquides])
    # ⚠️ Le rang se calcule parmi les titres ÉCHANGÉS à la séance, comme dans
    # la mesure (une observation n'y existe que si le titre a échangé). Un
    # titre qui n'a pas échangé est situé par rapport à eux.
    moms = pd.Series({t: s["mom120"] for t, s in sig.items()
                      if s["mom120"] is not None and s["echange"]})
    rangs = moms.rank(pct=True).to_dict() if len(moms) else {}
    for t, s in sig.items():
        if t not in rangs and s["mom120"] is not None and len(moms):
            u = pd.concat([moms, pd.Series({t: s["mom120"]})])
            rangs[t] = float(u.rank(pct=True)[t])
    out = {}
    for t, s in sig.items():
        out[t] = {**s, "rang_mom120": None if t not in rangs else round(rangs[t], 3),
                  "score": score_v2(reg["tendance"], s["cassure_recente"], s["surachat_recent"],
                                    s["pullback"], rangs.get(t))}
    return {"regime": reg, "titres": out}
