#!/usr/bin/env python3
"""Avant / après les règles « figures strictes » (21/10/2026).

Trois colonnes, parce que deux choses ont bougé et qu'il ne faut pas les mêler :
  publie   l'artefact du 03/10 (`etape4_lignes_gaps_hebdo_2026-10-03.json`),
           celui dont les fréquences étaient publiées jusqu'ici ;
  avant    le MÊME détecteur (règles du 03/10) REJOUÉ aujourd'hui, même
           protocole, mêmes chandelles arrêtées au 02/10, même seuil de
           liquidité — l'écart `publie` → `avant` ne vient pas des règles mais de
           `masi_history.json` complété le 14/10 (sept séances manquantes) ;
  apres    les règles du 21/10.
Seule la comparaison `avant` → `apres` mesure l'effet des règles.

Pour chaque signal de figure ou de droite, univers « tous » et « liquides »,
horizon 20 séances : effectif total (deux périodes), part dans le bon sens
(reconstruite comme dans `figures_publiees.py` : k = part × n par période),
et le passage sous 30 cas.

Usage : python3 pipeline/comparer_regles.py [--sortie FICHIER.json]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))
sys.path.insert(0, str(RACINE / "pipeline"))

from figures_publiees import SIGNAUX_PUBLIES  # noqa: E402

CAL = RACINE / "datasets" / "calibrage_technique"
FICHIERS = {"publie": "etape4_lignes_gaps_hebdo_2026-10-03.json",
            "avant": "etape4_regles_2026-10-03_rejeu_2026-10-21.json",
            "apres": "etape4_regles_2026-10-21.json"}
PERIODES = ("2023-10_2024-12", "2025-01_2026-10")
MIN_CAS = 30


def _agrege(sig: dict, lib: str, h: str) -> dict:
    cel = [sig[lib][p][h] for p in PERIODES]
    n = sum(c.get("n", 0) for c in cel)
    k = sum(round(c["dans_le_bon_sens"] * c["n"]) for c in cel if c.get("n"))
    return {"n": n, "part_pct": round(100 * k / n, 1) if n else None}


def comparer() -> dict:
    art = {k: json.loads((CAL / f).read_text(encoding="utf-8")) for k, f in FICHIERS.items()}
    out = {"_quoi": "Avant / après les règles figures strictes (21/10/2026)",
           "horizon_seances": 20, "min_cas": MIN_CAS, "colonnes": FICHIERS,
           "evenements": {k: a["evenements"] for k, a in art.items()},
           "signaux": {}, "sous_30_cas": {}}
    noms = list(SIGNAUX_PUBLIES)
    for nom in noms:
        out["signaux"][nom] = {lib: {col: _agrege(art[col]["signaux"][nom], lib, "h20")
                                     for col in FICHIERS}
                               for lib in ("tous", "liquides")} if all(
            nom in art[c]["signaux"] for c in FICHIERS) else None
    for lib in ("tous", "liquides"):
        passes = [n for n in noms if out["signaux"][n]
                  and out["signaux"][n][lib]["avant"]["n"] >= MIN_CAS
                  and out["signaux"][n][lib]["apres"]["n"] < MIN_CAS]
        sous = {col: [n for n in noms if (out["signaux"][n] is None
                                          or out["signaux"][n][lib][col]["n"] < MIN_CAS)]
                for col in FICHIERS}
        out["sous_30_cas"][lib] = {
            "passes_sous_30_apres_etre_publies_avant": passes,
            "nombre_de_types_sous_30": {c: len(v) for c, v in sous.items()},
            "types_sous_30": sous}
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sortie", default="")
    arg = ap.parse_args()
    res = comparer()
    texte = json.dumps(res, ensure_ascii=False, indent=1)
    if arg.sortie:
        Path(arg.sortie).write_text(texte + "\n", encoding="utf-8")
    print(texte)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
