#!/usr/bin/env python3
"""Combien d'événements de l'artefact `etape4` traversent une rupture ?

Le banc d'essai du 03/10/2026 (`calibrage_figures.py`) n'avait pas de filtre de
rupture (écart de clôture > 10 % entre deux séances échangées, opération
déclarée dans `SPLITS` / `SUSPENSIONS`) ; la publication (`figures_publiees.py`)
en a un. Cet outil mesure ce que le filtre aurait changé AUX FRÉQUENCES
PUBLIÉES, sans rien réécrire :

1. rejoue les événements du banc d'essai (mêmes chandelles arrêtées au
   02/10/2026, même dé-duplication) pour les signaux de figures et de droites
   publiés (`figures_publiees.SIGNAUX_PUBLIES`, horizon 20 séances) ;
2. rattache chaque événement à la figure qui l'a produit
   (`figures_detail`), et repère celle dont l'étendue — premier pivot
   → séance du signal — traverse une rupture ;
3. recalcule, SANS ces événements, l'effectif, la part dans le bon sens et
   l'alpha médian de chaque signal / univers / période, et rend le plus grand
   écart de part en points.

Usage : python3 pipeline/calibrage_ruptures.py [--sortie FICHIER.json]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))
sys.path.insert(0, str(RACINE / "pipeline"))

import calibrage_figures as cf  # noqa: E402
import calibrage_signaux as cs  # noqa: E402
from figures_publiees import SIGNAUX_PUBLIES  # noqa: E402
from technical.figures_detail import figures_detail, lignes_detail  # noqa: E402
from technical.serie_propre import charger, evenements_titre, ruptures, traverse  # noqa: E402

FIN = "2026-10-02"
H = 20


def _etendues(t: str) -> dict:
    """{(signal, date_du_signal): [étendue traverse une rupture ?, …]}"""
    s = charger(RACINE / "pipeline" / "candles" / f"{t}.json", FIN)
    if s is None or len(s["c"]) < 80:
        return {}
    rup = ruptures(s["d"], s["c"], evenements_titre(t))
    out: dict = {}
    for f in figures_detail(s["c"]) + lignes_detail(s["c"]):
        if f["statut"] != "declenchee" or not f["signal"]:
            continue
        debut = f["pivots"][0][0] if "pivots" in f else f["points"][0][0]
        out.setdefault((f["signal"], s["d"][f["i_fin"]]), []).append(
            traverse(rup, debut, max(f["i_fin"], f["conf"])))
    return out


def _stats(g: pd.DataFrame, sens: int) -> dict:
    a = g[f"a{H}"].dropna()
    if a.empty:
        return {"n": 0}
    return {"n": int(len(a)), "part_pct": round(100 * float(((a * sens) > 0).mean()), 1),
            "alpha_median_pct": round(100 * float(a.median()), 2)}


def mesurer() -> dict:
    cs.FIN = cf.FIN = FIN
    try:
        titres = [p.stem for p in sorted((RACINE / "pipeline" / "candles").glob("*.json"))]
        ev = pd.DataFrame([o for t in titres for o in cf._evenements(t)])
        etendues = {t: _etendues(t) for t in titres}
    finally:
        cs.FIN = cf.FIN = None
    ev = ev[ev["signal"].isin(SIGNAUX_PUBLIES)].copy()
    # Un événement est « traversant » si TOUTES les figures qui le portent le sont.
    ev["traverse"] = [bool(etendues[r.t].get((r.signal, r.date)) and
                           all(etendues[r.t][(r.signal, r.date)]))
                      for r in ev.itertuples()]
    ev["rattache"] = [bool(etendues[r.t].get((r.signal, r.date))) for r in ev.itertuples()]
    seuil = cf_seuil()
    ev["liquide"] = ev["montant"] >= seuil
    res = {"_quoi": "Événements de l'artefact etape4 qui traversent une rupture",
           "fin_donnees": FIN, "horizon_seances": H,
           "evenements_publies_signaux": int(len(ev)),
           "evenements_sans_figure_rattachee": int((~ev["rattache"]).sum()),
           "evenements_traversant_une_rupture": int(ev["traverse"].sum()),
           "pct_traversant": round(100 * float(ev["traverse"].mean()), 2),
           "par_signal": {}}
    plus_grand = 0.0
    for nom, g in ev.groupby("signal"):
        sens = int(g["sens"].iloc[0])
        r = {"traversant": int(g["traverse"].sum()), "n": int(len(g)), "ecarts_part_points": {}}
        for lib, sous in (("tous", g), ("liquides", g[g["liquide"]])):
            for p, deb, fin in (("2023-10_2024-12", "0", cf.COUPURE), ("2025-01_2026-10", cf.COUPURE, "9")):
                c = sous[(sous["date"] >= deb) & (sous["date"] < fin)]
                av, ap = _stats(c, sens), _stats(c[~c["traverse"]], sens)
                if av["n"] and ap["n"]:
                    e = abs(av["part_pct"] - ap["part_pct"])
                    r["ecarts_part_points"][f"{lib}/{p}"] = round(e, 1)
                    plus_grand = max(plus_grand, e)
        res["par_signal"][nom] = r
    res["plus_grand_ecart_part_points"] = round(plus_grand, 1)
    # Contrôle de reproduction : les effectifs rejoués égalent-ils ceux de l'artefact ?
    art = json.loads((RACINE / "datasets" / "calibrage_technique" /
                      "etape4_lignes_gaps_hebdo_2026-10-03.json").read_text(encoding="utf-8"))["signaux"]
    diff = {}
    for nom, g in ev.groupby("signal"):
        for p_, deb, fin in (("2023-10_2024-12", "0", cf.COUPURE), ("2025-01_2026-10", cf.COUPURE, "9")):
            c = g[(g["date"] >= deb) & (g["date"] < fin)]
            n_rejoue = _stats(c, 1)["n"]
            n_art = art[nom]["tous"][p_][f"h{H}"].get("n", 0)
            if n_rejoue != n_art:
                diff[f"{nom}/{p_}"] = [n_rejoue, n_art]
    res["effectifs_rejoues_differents_de_l_artefact"] = diff
    return res


def cf_seuil() -> float:
    """Seuil de liquidité de l'artefact (tiers inférieur des montants, tous signaux)."""
    return json.loads((RACINE / "datasets" / "calibrage_technique" /
                       "etape4_lignes_gaps_hebdo_2026-10-03.json").read_text(encoding="utf-8"))["seuil_liquidite_dh"]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sortie", default="")
    arg = ap.parse_args()
    res = mesurer()
    texte = json.dumps(res, ensure_ascii=False, indent=1)
    if arg.sortie:
        Path(arg.sortie).write_text(texte + "\n", encoding="utf-8")
    print(texte)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
