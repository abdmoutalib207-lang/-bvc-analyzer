#!/usr/bin/env python3
"""Étape 0 du calibrage technique : le score technique ACTUEL annonce-t-il
quelque chose ? Mesure, sans promesse, et sans rien changer à ce qui est publié.

⚠️ POURQUOI ON PEUT REJOUER LE TECHNIQUE, ET PAS LE RESTE
`backtest.py` refuse à juste titre de recalculer la note du passé : les
fondamentaux sont datés d'aujourd'hui, les rejouer en 2024 donnerait au modèle
la connaissance du futur. Le score technique, lui, ne dépend QUE des cours.
Chaque jour on ne lui donne que les séances connues ce jour-là
(`compute_indicators(..., as_of=jour)` sur la série tronquée) : aucune
information postérieure n'entre dans le calcul.

⚠️ CE QUI EST MESURÉ
- Le score est celui de la PRODUCTION (`update_data.calc_score_tech`), avec les
  indicateurs de la production (`collect_history_bvcscrap.compute_indicators`).
  Aucune copie de la formule ici : une copie dériverait.
- Rendement futur à h séances (séances de la série du titre), comparé au MASI
  sur les mêmes dates (`masi_history.json`, 916 séances depuis le 02/01/2023).
- Frais : un aller-retour en formule « Trading » Attijari Intermédiation coûte
  0,9 % HT par ordre (courtage 0,6 + règlement-livraison 0,2 + Bourse 0,1),
  soit 1,8 % HT ; avec la TVA, ~2,0 % (TVA 10 %) ou ~2,2 % (TVA 20 %) — le taux
  n'est pas dans la grille fournie. Les résultats nets sont donnés aux deux.
- Seules comptent les dates où le titre a ÉCHANGÉ (volume > 0) : on ne peut pas
  acheter un cours qui n'a pas traité.

⚠️ LIMITES, AVANT LES RÉSULTATS
1. Observations CHEVAUCHANTES : le rendement à 20 séances du lundi partage 19
   séances avec celui du mardi. Les t naïfs sont surestimés ; on donne aussi la
   mesure sur des dates espacées de h séances (non chevauchantes).
2. Deux périodes, jugées séparément : 04/10/2023 → 31/12/2024 et 01/01/2025 →
   aujourd'hui. Un effet qui n'existe que dans l'une n'est pas un effet.
3. Les titres suspendus (DIS, DLM) n'échangent pas : ils sortent d'eux-mêmes
   par la règle « volume > 0 ». Les titres introduits en cours de période
   n'entrent qu'avec 20 séances d'historique au moins.

Usage : python3 pipeline/mesure_score_tech.py [--sortie FICHIER.json]
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import pandas as pd

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))
sys.path.insert(0, str(RACINE / "pipeline"))

from collect_history_bvcscrap import compute_indicators  # noqa: E402
from update_data import calc_score_tech  # noqa: E402

DEBUT = "2023-10-04"
COUPURE = "2025-01-01"
HORIZONS = (5, 10, 20, 60)
FRAIS_AR = {"HT": 0.018, "TTC_TVA10": 0.0198, "TTC_TVA20": 0.0216}
MIN_HISTO = 20


def _serie(t: str) -> pd.DataFrame | None:
    f = RACINE / "pipeline" / "candles" / f"{t}.json"
    try:
        b = json.loads(f.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if len(b) < MIN_HISTO + 1:
        return None
    df = pd.DataFrame(b).rename(columns={"d": "date", "o": "open", "h": "high",
                                         "l": "low", "c": "close", "v": "volume"})
    df["date"] = pd.to_datetime(df["date"])
    return df.sort_values("date").reset_index(drop=True)


def _masi() -> dict:
    m = json.loads((RACINE / "pipeline" / "masi_history.json").read_text(encoding="utf-8"))
    return {d: float(v) for d, v in m["seances"].items()}


def _obs_titre(t: str) -> list[dict]:
    masi = _masi()
    df = _serie(t)
    if df is None:
        return []
    dates = df["date"].dt.strftime("%Y-%m-%d").tolist()
    closes = df["close"].tolist()
    vols = df["volume"].fillna(0).tolist()
    opens, highs, lows = df["open"].tolist(), df["high"].tolist(), df["low"].tolist()
    obs = []
    for i in range(MIN_HISTO, len(df)):
        d = dates[i]
        if d < DEBUT or not vols[i] or vols[i] <= 0:
            continue
        ind = compute_indicators(df.iloc[: i + 1], as_of=d)
        s = calc_score_tech(ind.get("rsi"), closes[i], ind.get("ma20"),
                            ind.get("ma50"), ind.get("h90"), ind.get("l90"))
        # Mode et liquidité, établis À LA DATE avec les 20 dernières séances
        # échangées — jamais la liste du 02/10/2026 appliquée à reculons.
        ech = [k for k in range(max(0, i - 60), i + 1) if vols[k] and vols[k] > 0][-20:]
        plates = sum(1 for k in ech if opens[k] == highs[k] == lows[k] == closes[k])
        montants = sorted(closes[k] * vols[k] for k in ech)
        o = {"t": t, "d": d, "score": s,
             "fixing": plates * 2 > len(ech),
             "montant_median": montants[len(montants) // 2] if montants else 0.0}
        for h in HORIZONS:
            j = i + h
            if j >= len(df) or dates[j] not in masi or d not in masi:
                continue
            r = closes[j] / closes[i] - 1
            o[f"r{h}"] = r
            o[f"a{h}"] = r - (masi[dates[j]] / masi[d] - 1)
        obs.append(o)
    return obs


def observations() -> list[dict]:
    """Un titre par processus : le rejeu jour par jour coûte ~14 ms par séance."""
    from multiprocessing import Pool
    titres = [f.stem for f in sorted((RACINE / "pipeline" / "candles").glob("*.json"))]
    with Pool() as pool:
        return [o for lot in pool.map(_obs_titre, titres) for o in lot]


def _spearman(x: list, y: list) -> float | None:
    if len(x) < 5:
        return None
    rx = pd.Series(x).rank()
    ry = pd.Series(y).rank()
    c = rx.corr(ry)
    return None if c is None or math.isnan(c) else float(c)


def _resume(vals: list) -> dict:
    n = len(vals)
    if n == 0:
        return {"n": 0}
    m = sum(vals) / n
    sd = (sum((v - m) ** 2 for v in vals) / (n - 1)) ** 0.5 if n > 1 else 0.0
    return {"n": n, "moyenne": round(m, 5), "t_naif": round(m / (sd / n ** 0.5), 2) if sd else None,
            "part_positive": round(sum(v > 0 for v in vals) / n, 3)}


def mesurer(obs: list[dict]) -> dict:
    out = {}
    periodes = {"2023-10_2024-12": lambda d: d < COUPURE, "2025-01_2026": lambda d: d >= COUPURE,
                "tout": lambda d: True}
    for nom, garde in periodes.items():
        sous = [o for o in obs if garde(o["d"])]
        res = {"observations": len(sous)}
        for h in HORIZONS:
            k = f"a{h}"
            avec = [o for o in sous if k in o]
            # Corrélation de rang JOUR PAR JOUR (coupe transversale), puis moyenne
            par_jour = {}
            for o in avec:
                par_jour.setdefault(o["d"], []).append(o)
            ics = [c for c in (_spearman([o["score"] for o in g], [o[k] for o in g])
                               for g in par_jour.values() if len(g) >= 10) if c is not None]
            # Dates espacées de h séances : une observation par titre tous les h jours
            jours = sorted(par_jour)
            espaces = set(jours[::h])
            icn = [c for c in (_spearman([o["score"] for o in par_jour[d0]], [o[k] for o in par_jour[d0]])
                               for d0 in sorted(espaces) if len(par_jour[d0]) >= 10) if c is not None]
            # Quintiles de score, sur l'ensemble de la période
            q = pd.Series([o["score"] for o in avec]).rank(pct=True).tolist() if avec else []
            haut = [o[k] for o, p in zip(avec, q) if p > 0.8]
            bas = [o[k] for o, p in zip(avec, q) if p <= 0.2]
            res[f"{h}_seances"] = {
                "ic_moyen": round(sum(ics) / len(ics), 4) if ics else None,
                "ic_jours": len(ics),
                "ic_part_positive": round(sum(c > 0 for c in ics) / len(ics), 3) if ics else None,
                "ic_non_chevauchant": round(sum(icn) / len(icn), 4) if icn else None,
                "ic_non_chevauchant_dates": len(icn),
                "alpha_quintile_haut": _resume(haut),
                "alpha_quintile_bas": _resume(bas),
                "ecart_haut_moins_bas": round(sum(haut) / len(haut) - sum(bas) / len(bas), 5)
                if haut and bas else None,
                "rendement_brut_quintile_haut": _resume([o[f"r{h}"] for o, p in zip(avec, q) if p > 0.8]),
                "net_de_frais_quintile_haut": {
                    nomf: round(sum(o[f"r{h}"] for o, p in zip(avec, q) if p > 0.8) / max(1, len(haut)) - f, 5)
                    for nomf, f in FRAIS_AR.items()},
            }
        out[nom] = res
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sortie", default="")
    a = ap.parse_args()
    obs = observations()
    res = {
        "_quoi": "Étape 0 du calibrage technique — pouvoir prédictif du score technique ACTUEL, rejoué au jour le jour",
        "_methode": __doc__.split("⚠️ LIMITES")[0].strip(),
        "frais_aller_retour": FRAIS_AR,
        "titres": len({o["t"] for o in obs}),
        "observations": len(obs),
        "periode": [min(o["d"] for o in obs), max(o["d"] for o in obs)] if obs else None,
        "mesures": mesurer(obs),
    }
    # ⚠️ SEGMENTS — la réserve de l'étape 0 : sur un titre peu liquide, la
    # clôture oscille entre les rares échanges et fabrique un faux reflux.
    tri = sorted(o["montant_median"] for o in obs)
    s1, s2 = tri[len(tri) // 3], tri[2 * len(tri) // 3]
    res["seuils_liquidite_dh"] = [round(s1), round(s2)]
    res["segments"] = {
        "continu": mesurer([o for o in obs if not o["fixing"]]),
        "fixing": mesurer([o for o in obs if o["fixing"]]),
        "liquidite_basse": mesurer([o for o in obs if o["montant_median"] < s1]),
        "liquidite_moyenne": mesurer([o for o in obs if s1 <= o["montant_median"] < s2]),
        "liquidite_haute": mesurer([o for o in obs if o["montant_median"] >= s2]),
    }
    res["effectifs_segments"] = {
        "continu": sum(not o["fixing"] for o in obs), "fixing": sum(o["fixing"] for o in obs)}
    texte = json.dumps(res, ensure_ascii=False, indent=1)
    if a.sortie:
        Path(a.sortie).write_text(texte + "\n", encoding="utf-8")
    print(texte)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
