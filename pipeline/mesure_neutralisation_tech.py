#!/usr/bin/env python3
"""Mesure, AVANT décision : que donnerait la neutralisation du pilier
technique sur les titres peu liquides et au fixing ?

⚠️ CE QUI EST PROPOSÉ (soumis à l'accord d'Abd Moutalib, R8)
Sur un titre peu liquide ou coté au fixing, le pilier technique actuel
annonce l'INVERSE de la suite (étape 0 : corrélation −0,18 à −0,30 à 5
séances). La proposition est de lui donner un poids nul sur ces titres : sa
part revient au fondamental. La note devient
    v53' = v53 + (score_fond − score_tech) × poids_t
ce qui conserve tout le reste de la formule (bonus compris, nuls depuis le
30/09).

⚠️ RÈGLE FIXÉE AVANT LA MESURE
« Peu liquide » : montant médian échangé sur les 20 dernières séances
échangées < 125 947 DH — le seuil du tiers le moins liquide mesuré à
l'étape 0. « Au fixing » : la majorité de ces 20 séances sont plates
(O = H = B = C). Les deux sont établis À LA DATE, depuis les chandelles.

Deux mesures :
1. Effet sur la livraison actuelle (`data.json`) : écarts de note et
   changements de palier.
2. Effet sur les notes RÉELLEMENT PUBLIÉES depuis le 12/08 (premier jour où
   `poids` est publié), confiance ≥ 2 : corrélation de rang jour par jour
   entre la note et l'alpha futur en rendement total (5 et 20 séances), avec
   et sans neutralisation. ⚠️ Un seul régime de marché, observations
   chevauchantes : cela peut établir qu'on ne dégrade rien, pas davantage.
"""
from __future__ import annotations

import json
import math
import subprocess
import sys
from pathlib import Path

import pandas as pd

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE / "pipeline"))
from calibrage_signaux import _dividendes, _masi  # noqa: E402

SEUIL_DH = 125_947
DEPUIS = "2026-08-12"
HORIZONS = (5, 20)
PALIERS = ((6.5, "ACHETER ★★"), (5.5, "SURVEILLER ★"), (4.5, "ATTENDRE"),
           (3.5, "ÉVITER"), (-1, "ÉVITER FORT"))


def palier(v: float) -> str:
    return next(n for s, n in PALIERS if v >= s)


def _series() -> dict:
    out = {}
    for f in (RACINE / "pipeline" / "candles").glob("*.json"):
        b = json.loads(f.read_text(encoding="utf-8"))
        if len(b) < 25:
            continue
        df = pd.DataFrame(b)
        df["date"] = df["d"].str[:10]
        df = df.sort_values("date").reset_index(drop=True)
        df["v"] = df["v"].fillna(0)
        div = pd.Series(0.0, index=df.index)
        for e in _dividendes().get(f.stem, []):
            k = df.index[df["date"] >= e["detachement"]]
            if len(k):
                div[k[0]] += e["montant_ajuste_split"]
        df["tr"] = ((df["c"] + div) / df["c"].shift(1)).fillna(1.0).cumprod()
        out[f.stem] = df
    return out


def neutralise(df: pd.DataFrame, date: str) -> tuple[bool, float]:
    """(neutraliser ?, montant médian) établi à la date."""
    s = df[(df["date"] <= date) & (df["v"] > 0)].tail(20)
    if s.empty:
        return True, 0.0
    plates = ((s["o"] == s["h"]) & (s["h"] == s["l"]) & (s["l"] == s["c"])).sum()
    montant = float((s["c"] * s["v"]).median())
    return bool(montant < SEUIL_DH or plates * 2 > len(s)), montant


def note_neutralisee(x: dict) -> float | None:
    p = x.get("poids") or {}
    st, sf, v = x.get("score_tech"), x.get("score_fond"), x.get("v53")
    if None in (st, sf, v) or "t" not in p:
        return None
    return round(min(max(v + (sf - st) * p["t"] / 100, 0), 10), 2)


def effet_actuel(series: dict) -> dict:
    # La livraison PUBLIÉE (main), pas la copie de la branche de travail.
    d = json.loads(subprocess.run(["git", "show", "origin/main:data.json"],
                                  capture_output=True, text=True, cwd=RACINE).stdout)
    date = max(df["date"].iloc[-1] for df in series.values())
    lignes, changes = [], []
    for x in d.get("tickers") or []:
        t = x.get("symbol")
        if t not in series or x.get("v53") is None or x.get("sig") in ("SUSPENDU",):
            continue
        neu, montant = neutralise(series[t], date)
        if not neu:
            continue
        v2 = note_neutralisee(x)
        if v2 is None:
            continue
        lignes.append({"t": t, "v53": x["v53"], "v53_neutralise": v2,
                       "ecart": round(v2 - x["v53"], 2), "montant_median_dh": round(montant),
                       "poids_tech": (x.get("poids") or {}).get("t")})
        if palier(v2) != palier(x["v53"]):
            changes.append({"t": t, "avant": palier(x["v53"]), "apres": palier(v2),
                            "v53": x["v53"], "v53_neutralise": v2})
    e = [l["ecart"] for l in lignes]
    return {"date": date, "titres_neutralises": len(lignes),
            "ecart_min": min(e) if e else None, "ecart_max": max(e) if e else None,
            "ecart_median": sorted(e)[len(e) // 2] if e else None,
            "paliers_changes": changes, "detail": sorted(lignes, key=lambda l: l["ecart"])}


def _publies() -> dict:
    log = subprocess.run(["git", "log", "origin/main", "--format=%H %ad",
                          "--date=format:%Y-%m-%d", "--", "data.json"],
                         capture_output=True, text=True, cwd=RACINE).stdout.splitlines()
    jour = {}
    for l in log:
        h, _, d = l.partition(" ")
        if d >= DEPUIS:
            jour.setdefault(d, h)
    out = {}
    for d, h in sorted(jour.items()):
        try:
            flux = json.loads(subprocess.run(["git", "show", f"{h}:data.json"], capture_output=True,
                                             text=True, cwd=RACINE).stdout)
        except ValueError:
            continue
        out[d] = [x for x in flux.get("tickers") or []
                  if ((x.get("_meta") or {}).get("confidence") or 0) >= 2]
    return out


def _ic(paires: list) -> float | None:
    if len(paires) < 10:
        return None
    s = pd.DataFrame(paires, columns=["x", "y"])
    c = s["x"].rank().corr(s["y"].rank())
    return None if math.isnan(c) else c


def effet_historique(series: dict) -> dict:
    masi = _masi()
    masi.index = masi.index.strftime("%Y-%m-%d")
    pub = _publies()
    res = {}
    for h in HORIZONS:
        avant, apres, n, nneu = [], [], 0, 0
        jours_ecartes = 0
        for d, lignes in pub.items():
            # ⚠️ `score_fond` n'est publié que depuis fin septembre : un jour où
            # il manque pour un titre à neutraliser ne peut pas être rejoué.
            # On l'écarte EN ENTIER, plutôt que de comparer des jours amputés
            # de leurs titres illiquides.
            if any(x.get("symbol") in series and neutralise(series[x["symbol"]], d)[0]
                   and note_neutralisee(x) is None for x in lignes):
                jours_ecartes += 1
                continue
            pa, pb = [], []
            for x in lignes:
                t = x.get("symbol")
                df = series.get(t)
                if df is None or x.get("v53") is None:
                    continue
                idx = df.index[df["date"] >= d]
                if len(idx) == 0 or idx[0] + h >= len(df):
                    continue
                i = idx[0]
                d0, d1 = df["date"][i], df["date"][i + h]
                if d0 not in masi.index or d1 not in masi.index:
                    continue
                a = df["tr"][i + h] / df["tr"][i] - 1 - (masi[d1] / masi[d0] - 1)
                neu, _ = neutralise(df, d)
                v2 = note_neutralisee(x) if neu else x["v53"]
                if v2 is None:
                    continue
                pa.append((x["v53"], a)); pb.append((v2, a))
                n += 1; nneu += neu
            ca, cb = _ic(pa), _ic(pb)
            if ca is not None and cb is not None:
                avant.append(ca); apres.append(cb)
        res[f"h{h}"] = {"jours": len(avant), "jours_ecartes_sans_score_fond": jours_ecartes,
                        "premier_jour": min(d for d in pub if d not in []) if pub else None, "observations": n, "dont_neutralisees": nneu,
                        "ic_publie": round(sum(avant) / len(avant), 4) if avant else None,
                        "ic_neutralise": round(sum(apres) / len(apres), 4) if apres else None}
    return res


def main() -> int:
    s = _series()
    res = {"_quoi": "Neutralisation du pilier technique sur les titres peu liquides et au fixing — mesure avant décision",
           "_methode": __doc__.strip(), "seuil_dh": SEUIL_DH,
           "effet_actuel": effet_actuel(s), "effet_historique": effet_historique(s)}
    sortie = RACINE / "datasets" / "calibrage_technique" / "neutralisation_tech_illiquides.json"
    sortie.write_text(json.dumps(res, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    a = res["effet_actuel"]
    print(json.dumps({k: a[k] for k in ("date", "titres_neutralises", "ecart_min", "ecart_max", "ecart_median")},
                     ensure_ascii=False))
    print(json.dumps(a["paliers_changes"], ensure_ascii=False))
    print(json.dumps(res["effet_historique"], ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
