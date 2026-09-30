#!/usr/bin/env python3
"""Les comptes semestriels 2026 entrent dans les fondamentaux — 29/09/2026.

⚠️ POURQUOI CE MODULE
─────────────────────
Au 29/09, trente-deux sociétés avaient déposé à l'AMMC des comptes plus récents
que les nôtres, et le terminal le disait sans rien en faire. La chaîne
automatique prévue pour ça (`fetch_annual_reports.py`) n'a jamais tourné :
secret absent, et programmée quatre fois l'an alors que les semestriels
tombent en septembre.

Ce module applique des chiffres LUS DANS LES DÉPÔTS, consignés avec leur page
dans `datasets/resultats_s1_2026.json`. Il ne lit aucun PDF lui-même : lire
un chiffre et l'appliquer sont deux actes distincts, et le premier se relit.

⚠️ CE QU'IL CALCULE, ET SEULEMENT CELA
  · le résultat sur douze mois glissants :
        exercice 2025 + S1 2026 − S1 2025
    — le semestre 2026 ne REMPLACE pas l'exercice, il le décale de six mois ;
  · le BPA correspondant, sur le nombre d'actions ACTUEL ;
  · la croissance semestrielle du résultat et du chiffre d'affaires, qui
    remplace dans la note fondamentale une croissance saisie en juin.

⚠️ CE QU'IL NE TOUCHE PAS
Le `forward_per`, le ROIC, le WACC, le momentum : aucun ne se lit dans un
communiqué semestriel. Les réécrire ici serait les inventer.

    python pipeline/resultats_semestriels.py            # applique
    python pipeline/resultats_semestriels.py --montrer  # montre sans écrire
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
JEU = RACINE / "datasets" / "resultats_s1_2026.json"
DATE_MAJ = "2026-09-29"


def douze_mois(t: dict) -> dict | None:
    """Résultat, BPA et croissances sur douze mois. None si une valeur manque."""
    cles = ("rnpg_exercice_2025", "rnpg_s1_2026", "rnpg_s1_2025", "actions")
    if any(t.get(k) is None for k in cles) or not t["actions"]:
        return None
    rn = t["rnpg_exercice_2025"] + t["rnpg_s1_2026"] - t["rnpg_s1_2025"]
    out = {"rnpg_12m": round(rn, 3),
           "bpa_12m": round(rn * 1e6 / t["actions"], 2)}
    # ⚠️ Une croissance rapportée à une base NÉGATIVE n'a pas de sens : on
    # reprend alors celle que l'émetteur publie, et on le dit.
    if t.get("croissance_bpa_publiee") is not None:
        out["croissance_bpa"] = t["croissance_bpa_publiee"]
    elif t["rnpg_s1_2025"] > 0:
        out["croissance_bpa"] = round((t["rnpg_s1_2026"] / t["rnpg_s1_2025"] - 1) * 100, 1)
    if t.get("croissance_ca_publiee") is not None:
        # Variation publiée sans montant (BCP, S1 2026) : reprise telle quelle.
        out["croissance_ca"] = t["croissance_ca_publiee"]
    elif t.get("ca_s1_2025"):
        out["croissance_ca"] = round((t["ca_s1_2026"] / t["ca_s1_2025"] - 1) * 100, 1)
    return out


def appliquer(jeu: dict, bpa: dict, fond: dict) -> list[str]:
    """Met à jour `bpa` et `fond` EN PLACE. Renvoie le journal des changements."""
    journal = []
    for s, t in jeu["titres"].items():
        m = douze_mois(t)
        if m is None:
            journal.append(f"{s} : incomplet, rien d'appliqué")
            continue
        exercice = round(t["rnpg_exercice_2025"] * 1e6 / t["actions"], 2)
        b = bpa.setdefault(s, {})
        # ⚠️ L'ancien BPA est conservé à côté du nouveau, jamais effacé.
        if b.get("bpa") is not None and abs(b["bpa"] - exercice) > 0.05:
            b.setdefault("bpa_avant_2026_09_29", b["bpa"])
            journal.append(f"{s} : BPA 2025 {b['bpa']} → {exercice} "
                           f"({t['rnpg_exercice_2025']} MDH ÷ {t['actions']:,} actions)")
            b["bpa"] = exercice
        elif b.get("bpa") is None:
            # Titre sans BPA jusqu'ici (BMCI) : l'exercice publié le fournit.
            b["bpa"] = exercice
            b.setdefault("source", "resultats_officiels")
            journal.append(f"{s} : BPA 2025 absent → {exercice}")
        # ⚠️ UNE PERTE SE DOCUMENTE — 30/09/2026. validate.py refuse un BPA
        # négatif (garde du 13/06 contre les erreurs de saisie) ; une perte
        # RÉELLE porte donc sa pièce, que le contrôle exige. Cas : SNEP.
        if exercice < 0 or m["bpa_12m"] < 0:
            b["perte_documentee"] = t.get("source_exercice_2025") or t["url"]
        else:
            b.pop("perte_documentee", None)
        b["rnpg_12m"] = m["rnpg_12m"]
        b["bpa_12m"] = m["bpa_12m"]
        b["fin_12m"] = jeu["fin_periode"]
        b["source_12m"] = (f"exercice 2025 + S1 2026 − S1 2025 ; S1 : {t['url']} "
                           f"{t['pages']} ; base : {t['base']}")
        f = fond.setdefault(s, {})
        avant = {k: f.get(k) for k in ("croissance_bpa", "croissance_ca",
                                        "nb_actions", "date_maj")}
        f.setdefault("avant_2026_09_29", avant)
        for k in ("croissance_bpa", "croissance_ca"):
            if k in m:
                f[k] = m[k]
        f["nb_actions"] = t["actions"]
        f["date_maj"] = DATE_MAJ
        f["source_s1_2026"] = t["url"]
        journal.append(f"{s} : 12 mois {m['rnpg_12m']} MDH, BPA {m['bpa_12m']} ; "
                       f"croissance BPA {avant['croissance_bpa']} → {f['croissance_bpa']}, "
                       f"CA {avant['croissance_ca']} → {f['croissance_ca']}")
    return journal


def main() -> int:
    jeu = json.loads(JEU.read_text(encoding="utf-8"))
    pb, pf = RACINE / "bpa.json", RACINE / "fondamentaux.json"
    bpa = json.loads(pb.read_text(encoding="utf-8"))
    fond = json.loads(pf.read_text(encoding="utf-8"))
    for ligne in appliquer(jeu, bpa, fond):
        print(ligne)
    if "--montrer" not in sys.argv:
        pb.write_text(json.dumps(bpa, ensure_ascii=False, indent=2), encoding="utf-8")
        pf.write_text(json.dumps(fond, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
