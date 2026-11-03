#!/usr/bin/env python3
"""Backtest du SCORE BVC unique (Nour + Boursenews) contre Nour seul.

    python3 pipeline/backtest_score_bvc.py [--jusqu-au AAAA-MM-JJ] [--depuis AAAA-MM-JJ]

Sortie : `datasets/backtests/score_bvc_AAAA-MM-JJ.json` (date de la dernière
séance). MÊMES règles que `backtest_score_descriptif.py` — horizon 20 séances,
2 % de frais, rendement total, référence MASI (941 séances), fenêtres rompues
écartées, taux de base des mêmes dates, écart apparié, Newey-West, bootstrap par
blocs, aucun t sous 30 observations / 20 dates / 10 blocs — et MÊME ÉCHANTILLON
pour les deux scores : seules comptent les observations où Nour ET le score BVC
sont calculables, pour que la différence ne vienne pas de l'échantillon.
Deux variantes : SANS rentabilité (point-in-time) et AVEC le ROE actuel (biais
d'anticipation, écrit dans l'artefact).

⚠️ MOMENTUM — NE PAS CORRIGER SUR CES DONNÉES
Le backtest du 28/10 a observé que les zones RSI < 30 et RSI > 70, que la règle
de Nour note 0, sur-performent. Le score BVC reprend la règle SANS la toucher :
la retoucher sur les données qui ont servi à l'observer fabriquerait un gagnant
par surapprentissage. Cette observation est publiée (`momentum_par_zone_de_rsi`)
avec sa stabilité par moitié de période, comme HYPOTHÈSE.

TEST HORS ÉCHANTILLON PROPOSÉ (écrit avant d'avoir des données)
  Gel : formule et poids du score BVC `bvc-score-v1`, à la date du 03/11/2026.
  Données : uniquement les observations dont la DATE D'ENTRÉE est postérieure
  au 03/11/2026 (`--depuis 2026-11-04`) ; la première sortie à 20 séances
  tombe fin novembre, un effectif suffisant (≥ 20 dates distinctes ET ≥ 10
  blocs de 20 séances) ne sera atteint que vers l'automne 2027.
  Hypothèses fixées d'avance, une seule lecture chacune :
    H1  RSI < 30 ou > 70 : fréquence de surperformance > taux de base (écart
        apparié > 0, Newey-West p < 0,05).
    H2  tranche ≥ 60 du score BVC : écart apparié > 0 ; tranche < 40 : < 0.
  Tant que l'effectif n'est pas atteint, le texte dit « insuffisant ».
  Aucun changement de formule avant cette lecture.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))
sys.path.insert(0, str(RACINE / "pipeline"))

import backtest_score_descriptif as bs  # noqa: E402
from pipeline import score_bvc as sb  # noqa: E402
from pipeline import score_descriptif as sd  # noqa: E402

COMMANDE = "python3 pipeline/backtest_score_bvc.py"
CODE = ("pipeline/backtest_score_bvc.py", "pipeline/score_bvc.py",
        "pipeline/backtest_score_descriptif.py", "pipeline/score_descriptif.py")
FACTEURS = tuple(n for n, _ in sb.POIDS_BVC if n != "rentabilité")


def extra_bvc(roe_par_titre=None):
    """Colonnes du score BVC pour chaque (titre, séance), calculées à la date."""
    cache: dict = {}

    def f(ctx):
        t, i, c, m = ctx["t"], ctx["i"], ctx["c"], ctx["m"]
        if t not in cache:
            cache[t] = sb.serie_macd(c)
        mc = cache[t]
        macd = sig = hist = hprec = None
        if i >= 1 and mc[i] is not None and mc[i - 1] is not None:
            macd, sig, hist = mc[i]
            hprec = mc[i - 1][2]
        ma200 = round(float(np.mean(c[i - 199:i + 1])), 2) if i >= 199 else None
        kw = dict(prix=ctx["prix"], ma20=ctx["ma20"], ma50=ctx["ma50"], ma200=ma200, rsi=ctx["rsi"],
                  macd=macd, macd_signal=sig, hist=hist, hist_prec=hprec,
                  ratio_volume=m["ratio_volume"], montant_median=m["montant_median"],
                  liquidite_prete=m["liquidite_prete"], decision=ctx["decision"], motif=ctx["motif"])
        sans = sb.score_bvc(roe=None, **kw)
        avec = sb.score_bvc(roe=ctx["roe"], **kw)
        out = {"bvc_sans": sans["valeur"], "bvc_avec": avec["valeur"], "macd_hausse": None if hist is None else hist > hprec,
               "rsi_j": ctx["rsi"]}
        for nom, fa in avec["facteurs"].items():
            out["bp_" + nom] = fa["points"]
            out["bw_" + nom] = fa["poids"]
        return out
    return f


def par_facteur(df: pd.DataFrame, col: str, T: int, tir) -> dict:
    d = df[df[col].notna()]
    base = d.groupby("pos")["gagne"].mean()
    bp = np.full(T, np.nan)
    bp[base.index.to_numpy()] = base.to_numpy()
    cles = ("n", "dates", "frequence_surperformance", "taux_de_base_memes_dates",
            "ecart_apparie_pts", "p_newey_west", "conclusion_autorisee")
    out = {}
    for f in FACTEURS:
        pts, w = d["bp_" + f], d["bw_" + f]
        out[f] = {}
        for nom, cond in (("plein", pts >= w), ("partiel", (pts > 0) & (pts < w)), ("zero", pts <= 0)):
            l_ = bs.ligne_groupe(d[(cond & (w > 0)).fillna(False)], bp, T, tir, "gagne", "ex")
            out[f][nom] = {k: l_.get(k) for k in cles}
    # RSI par zone, et stabilité par moitié de période (exploratoire)
    pos_med = int(d["pos"].median())
    zones = (("RSI < 30", d["rsi_j"] < 30), ("30 ≤ RSI < 45", (d["rsi_j"] >= 30) & (d["rsi_j"] < 45)),
             ("45 ≤ RSI ≤ 70", (d["rsi_j"] >= 45) & (d["rsi_j"] <= 70)), ("RSI > 70", d["rsi_j"] > 70))
    det = {"_lecture": "EXPLORATOIRE — hypothèse H1, à tester hors échantillon (voir en-tête du script)."}
    for nom, cond in zones:
        for suf, mk in (("", cond), (" · 1re moitié", cond & (d["pos"] <= pos_med)),
                        (" · 2e moitié", cond & (d["pos"] > pos_med))):
            l_ = bs.ligne_groupe(d[mk.fillna(False)], bp, T, tir, "gagne", "ex")
            det[nom + suf] = {k: l_.get(k) for k in cles + ("mediane_ecart_net_frais_pct",)}
    out["momentum_par_zone_de_rsi"] = det
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--sortie", default=str(bs.SORTIE))
    ap.add_argument("--jusqu-au", default=None, metavar="AAAA-MM-JJ")
    ap.add_argument("--depuis", default=None, metavar="AAAA-MM-JJ",
                    help="test hors échantillon : observations dont l'entrée est POSTÉRIEURE à cette date")
    a = ap.parse_args(argv)

    bougies = bs.charger_bougies(a.jusqu_au)
    cal = bs.calendrier(bougies)
    T = len(cal)
    masi = bs.masi_serie(a.jusqu_au)
    roes = bs.roe_actuels()
    P = bs.construire_panel(bougies, cal, roes, masi, bs.dividendes(), extra=extra_bvc())
    tir = bs._tirages(T)
    if a.depuis:
        P = P[P["date"] > a.depuis]
    fin = cal[-1]
    res = {}
    for nom, nour_c, bvc_c in (("sans_rentabilite", "sans", "bvc_sans"), ("avec_roe_actuel", "avec", "bvc_avec")):
        # même échantillon : Nour ET score BVC calculables, fenêtre propre
        E = P[P["propre"] & P[nour_c].notna() & P[bvc_c].notna()]
        bloc = {"observations_communes": int(len(E))}
        for etiq, col in (("score_bvc", bvc_c), ("nour_seul", nour_c)):
            bloc[etiq] = {**bs.table(E, col, bs.TRANCHES, T=T, tir=tir),
                          "utilite": bs.ic_et_ecart_haut_bas(E, col, 60, 40, "gagne", "ex", T),
                          "par_semestre": bs.periodes(E, col, bs.TRANCHES, cal, T, tir)}
        if nom == "sans_rentabilite":
            bloc["score_bvc"]["par_facteur"] = par_facteur(E, bvc_c, T, tir)
        else:
            bloc["_biais"] = ("BIAIS D'ANTICIPATION : ROE 2025 appliqué à toutes les dates. Borne, "
                              "pas une performance atteignable.")
        res[nom] = bloc
    art = {
        "_quoi": "Backtest du score BVC unique (Nour + Boursenews) contre Nour seul — mode fantôme",
        "_commande": COMMANDE, "version_score": sb.VERSION, "poids": dict(sb.POIDS_BVC),
        "sous_poids_moyennes_mobiles": dict(sb.SOUS_MM), "version_nour": sd.VERSION,
        "date_artefact": fin, "depuis": a.depuis, "horizon_seances": bs.HORIZON,
        "frais_aller_retour": bs.FRAIS_AR, "reference_principale": "MASI",
        "regles": "identiques à datasets/backtests/score_descriptif_*.json (`regles_et_limites`, `limites`)",
        "regles_et_limites": bs.__doc__.split("LIMITES, AVANT LES RÉSULTATS")[0].split("RÈGLES — ÉCRITES")[1].strip(),
        "limites": bs.__doc__.split("LIMITES, AVANT LES RÉSULTATS")[1].strip(),
        "test_hors_echantillon": __doc__.split("TEST HORS ÉCHANTILLON PROPOSÉ")[1].strip(),
        "entrees": {"calendrier": {"seances": T, "du": cal[0], "au": fin},
                    "masi": {"seances": len(masi)},
                    "code_sha256": {c: bs._sha(RACINE / c) for c in CODE}},
        "exclusions": bs.exclusions(P),
        "resultats": res,
    }
    out = Path(a.sortie)
    out.mkdir(parents=True, exist_ok=True)
    f = out / f"score_bvc_{fin}.json"
    f.write_text(json.dumps(art, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"✅ {f}  ({f.stat().st_size // 1024} Ko)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
