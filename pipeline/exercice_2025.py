#!/usr/bin/env python3
"""L'exercice 2025 rectifié sur le document publié — lot 13, 30/09/2026.

POURQUOI CE MODULE
──────────────────
`resultats_semestriels.py` exige quatre valeurs (exercice 2025, S1 2026, S1
2025, actions) pour calculer un douze mois. Un titre qui n'a PAS déposé de S1
2026 ne peut donc pas y entrer — et une entrée S1 incomplète est refusée
(« on ne comble pas »). Mais son BPA de la table peut être faux quand même :
TMA portait 108,21 pour 94,99 publié, CTM 38,0 (le BPA 2024) pour 45,84, S2M
35,79 pour 40,09.

Ce module applique l'EXERCICE seul, lu dans `datasets/exercice_2025_rectifie.json`
(chaque montant avec sa page). Il ne lit aucun PDF.

CE QU'IL ÉCRIT DANS bpa.json, ET SEULEMENT CELA
  · `bpa` = résultat net × 1e6 ÷ actions ;
  · l'ancien dans `bpa_avant_2026_09_29` (jamais effacé, jamais réécrit s'il
    existe déjà) ;
  · `perte_documentee` (la pièce) si le résultat est une perte, sinon retiré ;
  · `source_exercice_2025` et `exercice_clos` : la provenance du nouveau BPA.
Ni fondamentaux.json, ni data.json, ni les dividendes, ni le ROE de bpa.json.

    python pipeline/exercice_2025.py            # applique
    python pipeline/exercice_2025.py --montrer  # montre sans écrire
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
JEU = RACINE / "datasets" / "exercice_2025_rectifie.json"


def bpa_exercice(t: dict) -> float | None:
    """BPA de l'exercice, ou None si une valeur manque. Fonction pure."""
    if t.get("rnpg_exercice_2025") is None or not t.get("actions"):
        return None
    return round(t["rnpg_exercice_2025"] * 1e6 / t["actions"], 2)


def appliquer(jeu: dict, bpa: dict) -> list[str]:
    """Met à jour `bpa` EN PLACE. Renvoie le journal des changements."""
    journal = []
    for s, t in jeu["titres"].items():
        nouveau = bpa_exercice(t)
        if nouveau is None:
            journal.append(f"{s} : incomplet, rien d'appliqué")
            continue
        b = bpa.setdefault(s, {})
        ancien = b.get("bpa")
        if ancien is None:
            b["bpa"] = nouveau
            b.setdefault("source", "resultats_officiels")
            journal.append(f"{s} : BPA absent → {nouveau}")
        elif abs(ancien - nouveau) > 0.05:
            # ⚠️ L'ancien BPA est conservé à côté du nouveau, jamais effacé.
            b.setdefault("bpa_avant_2026_09_29", ancien)
            b["bpa"] = nouveau
            journal.append(f"{s} : BPA {ancien} → {nouveau} "
                           f"({t['rnpg_exercice_2025']} MDH ÷ {t['actions']:,} actions)")
        else:
            journal.append(f"{s} : BPA {ancien} confirmé ({nouveau})")
        # Une perte se documente : validate.py refuse un BPA négatif sans pièce.
        if nouveau < 0:
            b["perte_documentee"] = t["source_exercice_2025"]
        else:
            b.pop("perte_documentee", None)
        b["source_exercice_2025"] = f"{t['url']} ; {t['pages']}"
        b["exercice_clos"] = t.get("exercice_clos", "2025-12-31")
    return journal


def main() -> int:
    jeu = json.loads(JEU.read_text(encoding="utf-8"))
    pb = RACINE / "bpa.json"
    bpa = json.loads(pb.read_text(encoding="utf-8"))
    for ligne in appliquer(jeu, bpa):
        print(ligne)
    if "--montrer" not in sys.argv:
        pb.write_text(json.dumps(bpa, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
