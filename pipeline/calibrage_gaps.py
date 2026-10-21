#!/usr/bin/env python3
"""Fréquence de COMBLEMENT des gaps — banc d'essai, aucune note modifiée.

Les artefacts du 03/10/2026 mesurent ce qui suit un REBOND sur la zone d'un
gap (`gap_haussier_rebond`, `gap_baissier_rejet`), pas la fréquence à laquelle
un gap se comble. Celle-ci est mesurée ici, avec le protocole de
`calibrage_figures.py` :

- données : chandelles `pipeline/candles/`, séances ÉCHANGÉES seules, arrêtées
  au 02/10/2026 (stable d'une séance à l'autre, comme `frequences.py`) ;
- événement : le gap, daté de SA séance — connu à la clôture de ce jour-là,
  jamais plus tôt. Définition de `lignes.gaps` : extrêmes de la séance au moins
  1 % au-dessus du plus haut (au-dessous du plus bas) de la veille, deux
  séances à extrêmes réels. Plus : jamais à travers une rupture, jamais un
  écart de plus de 10 % (R10/R11, voir `technical/serie_propre.py`) ;
- une occurrence au plus par titre, par sens et par fenêtre de 20 séances ;
- période : à partir du 04/10/2023 ; deux sous-périodes (coupure 01/01/2025) ;
- univers : « tous » et « liquides » (montant médian ≥ le seuil FIXE de
  l'artefact `etape4`, 119 564 DH — le même que celui qui sert à marquer un
  titre liquide dans `figures_publiees.json`) ;
- comblement : une séance ultérieure dont l'extrême traverse TOUTE la zone
  (bas ≤ plus haut de la veille pour un gap haussier ; haut ≥ plus bas de la
  veille pour un gap baissier). Mesuré à 20 et à 60 séances. Un gap sans
  `horizon` séances de recul n'est pas compté (censure) ; un gap dont le suivi
  est interrompu par une rupture avant l'horizon non plus.

⚠️ Le comblement n'est PAS une performance : c'est la fréquence d'un fait de
marché (le cours revient sur son point de départ). Il n'est pas en alpha ni en
frais — aucun achat n'est supposé. Observations chevauchantes entre titres un
même jour (une baisse de marché ouvre des gaps baissiers partout) : les
intervalles sont optimistes.

Usage : python3 pipeline/calibrage_gaps.py [--sortie FICHIER.json]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))
sys.path.insert(0, str(RACINE / "pipeline"))

from frequences import wilson  # noqa: E402
from technical.figures_detail import gaps_detail  # noqa: E402
from technical.serie_propre import charger, evenements_titre, ruptures  # noqa: E402

FIN = "2026-10-02"
DEBUT, COUPURE = "2023-10-04", "2025-01-01"
HORIZONS = (20, 60)
SEUIL_LIQUIDITE_DH = 119564        # artefact etape4_lignes_gaps_hebdo_2026-10-03.json
PERIODES = (("2023-10_2024-12", DEBUT, COUPURE), ("2025-01_2026-10", COUPURE, "9999"))


def evenements(racine: Path = RACINE, fin: str = FIN) -> list[dict]:
    out = []
    import bvc_config as cfg
    for t in cfg.TICKERS_ALL:
        s = charger(racine / "pipeline" / "candles" / f"{t}.json", fin)
        if s is None or len(s["c"]) < 80:
            continue
        rup = ruptures(s["d"], s["c"], evenements_titre(t))
        n, dernier = len(s["c"]), {}
        for g in gaps_detail(s["o"], s["h"], s["l"], s["c"], frozenset(rup)):
            t0, sens = g["t"], g["sens"]
            if s["d"][t0] < DEBUT:
                continue
            if sens in dernier and t0 - dernier[sens] < 20:
                continue
            dernier[sens] = t0
            o = {"t": t, "date": s["d"][t0], "sens": sens,
                 "liquide": bool(s["montant"][t0] >= SEUIL_LIQUIDITE_DH)}
            for h in HORIZONS:
                inconnu = (t0 + h >= n or (g["i_comble"] is None and g["i_interruption"] is not None
                                           and g["i_interruption"] <= t0 + h))
                o[f"c{h}"] = None if inconnu else int(g["i_comble"] is not None and g["i_comble"] - t0 <= h)
            out.append(o)
    return out


def _cellule(evs: list[dict], h: int) -> dict:
    ks = [e[f"c{h}"] for e in evs if e[f"c{h}"] is not None]
    n, k = len(ks), sum(ks)
    if n == 0:
        return {"n": 0}
    lo, hi = wilson(k, n)
    return {"n": n, "combles_k": k, "pct_combles": round(100 * k / n, 1),
            "ic95_combles": [round(100 * lo, 1), round(100 * hi, 1)]}


def mesurer(racine: Path = RACINE, fin: str = FIN) -> dict:
    ev = evenements(racine, fin)
    res = {"_quoi": "Fréquence de comblement des gaps (mesurée, pas reprise d'un artefact)",
           "_methode": __doc__.split("Usage :")[0].strip(),
           "fin_donnees": fin, "seuil_liquidite_dh": SEUIL_LIQUIDITE_DH,
           "evenements": len(ev), "gaps": {}}
    for sens, nom in ((+1, "gap_haussier"), (-1, "gap_baissier")):
        g = [e for e in ev if e["sens"] == sens]
        r = {}
        for lib, sous in (("tous", g), ("liquides", [e for e in g if e["liquide"]])):
            r[lib] = {p: {f"h{h}": _cellule([e for e in sous if a <= e["date"] < b], h)
                          for h in HORIZONS} for p, a, b in PERIODES}
            r[lib]["toutes_periodes"] = {f"h{h}": _cellule(sous, h) for h in HORIZONS}
        res["gaps"][nom] = r
    return res


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sortie", default="")
    arg = ap.parse_args()
    res = mesurer()
    texte = json.dumps(res, ensure_ascii=False, indent=1)
    if arg.sortie:
        Path(arg.sortie).write_text(texte + "\n", encoding="utf-8")
    print(f"{res['evenements']} gaps")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
