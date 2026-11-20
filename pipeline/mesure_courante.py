#!/usr/bin/env python3
"""Pointeur de la mesure courante du Score BVC, lu par le terminal.

    python3 pipeline/mesure_courante.py [ARTEFACT]

Sans argument : l'artefact `datasets/backtests/score_bvc_hebdo_*.json` le plus
récent. Écrit `datasets/backtests/score_bvc_mesure_courante.json`, que le
terminal charge au lieu de chiffres écrits à la main (feuille de route, lot 1.7).

Principes
  * Aucune mesure n'est refaite : chaque chiffre est RECOPIÉ de l'artefact
    (variante `sans_rentabilite`, la seule sans biais d'anticipation), qui reste
    l'unique source. Le fichier porte le chemin et l'empreinte SHA-256 de
    l'artefact ; `tests/test_mesure_synchronisee.py` les recalcule.
  * La conclusion est DÉDUITE des tests de l'artefact, pas écrite d'avance :
    une tranche n'est dite distincte que si les deux p (Newey-West et
    bootstrap par blocs) sont sous 5 %.
  * R8 : ce module ne change ni facteur, ni poids, ni seuil, ni tranche.
  * Stdlib seulement (R4).
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
DOSSIER = RACINE / "datasets" / "backtests"
SORTIE = DOSSIER / "score_bvc_mesure_courante.json"
ARTEFACT_HORS_ECHANTILLON = "datasets/backtests/score_bvc_2026-11-03.json"
SEUIL = 0.05
SCHEMA = "mesure_score_bvc/1"


def dernier_artefact(dossier: Path = DOSSIER) -> Path:
    c = sorted(dossier.glob("score_bvc_hebdo_????-??-??.json"))
    if not c:
        raise FileNotFoundError("aucun artefact score_bvc_hebdo_*.json")
    return c[-1]


def _plage(nom: str) -> str:
    return nom.replace(" – ", "–")


def _fr(d: str) -> str:
    return "/".join(reversed(d.split("-")))


def construire(chemin: Path, racine: Path = RACINE) -> dict:
    chemin = Path(chemin)
    brut = chemin.read_bytes()
    art = json.loads(brut.decode("utf-8"))
    r = art["resultats"]["principal_echange_a_la_cloture_de_la_semaine"]["sans_rentabilite"]
    cal = art["entrees"]["calendrier"]
    fs = art["entrees"]["fins_de_semaine"]
    tr = []
    distinctes = []
    for nom, t in r["tranches"].items():
        tr.append({"plage": _plage(nom), "n": t["n"], "dates": t["dates"],
                   "part_battu_masi_pct": round(t["frequence_surperformance"] * 100, 1),
                   "ic95_blocs_pct": [round(x * 100, 1) for x in t["frequence_ic95_blocs"]],
                   "p_newey_west": t["p_newey_west"], "p_bootstrap_blocs": t["p_bootstrap_blocs"],
                   "effectif_suffisant": bool(t["effectif_suffisant"])})
        if t["p_newey_west"] < SEUIL and t["p_bootstrap_blocs"] < SEUIL:
            distinctes.append(_plage(nom))
    if distinctes:
        concl = ("Au moins une tranche se distingue à 5 % selon les deux méthodes : "
                 + ", ".join(distinctes) + " ; à lire avec les réserves ci-dessous.")
    else:
        concl = ("Aucune tranche ne se distingue de façon robuste du taux moyen "
                 "(aucune sous 5 % selon les deux méthodes) : le Score BVC décrit "
                 "la situation, il ne distingue pas les gagnants.")
    ut = r["utilite"]["correlation_rang_score_ecart"]
    try:
        rel = chemin.resolve().relative_to(Path(racine).resolve()).as_posix()
    except ValueError:
        rel = chemin.as_posix()
    return {
        "schema": SCHEMA,
        "_quoi": "Pointeur lu par le terminal ; chiffres recopiés de l'artefact référencé, jamais recalculés ici.",
        "_commande": "python3 pipeline/mesure_courante.py",
        "artefact": rel,
        "artefact_sha256": hashlib.sha256(brut).hexdigest(),
        "date_artefact": art["date_artefact"],
        "version_score": art["version_score"],
        "variante": "sans_rentabilite",
        "definition": "Observation = un titre échangé à la clôture d'une semaine close ; part des cas ayant fait mieux "
                      "que le MASI 20 séances plus tard, dividendes réinvestis, frais d'aller-retour déduits.",
        "horizon_seances": art["horizon_seances"],
        "frais_aller_retour_pct": round(art["frais_aller_retour"] * 100, 1),
        "periode": {"calendrier_du": cal["du"], "calendrier_au": cal["au"],
                    "premiere_semaine": fs["premiere"], "derniere_semaine": fs["derniere"],
                    "du_fr": _fr(cal["du"]), "au_fr": _fr(cal["au"])},
        "observations": r["observations_total"],
        "dates_d_entree": r["dates"],
        "base_pct": round(r["taux_de_base_global"] * 100, 1),
        "tranches": tr,
        "correlation_rang": {"moyenne": ut["moyenne"], "p_newey_west": ut["p"], "jours": ut["jours"]},
        "conclusion": {"tranche_distincte_a_5pct": distinctes, "texte": concl},
        "hors_echantillon": {
            "artefact": ARTEFACT_HORS_ECHANTILLON,
            "formule_figee_au": "2026-11-03", "entrees_a_partir_du": "2026-11-04",
            "effectif_suffisant": "vers l'automne 2027",
            "texte": "Test hors échantillon gelé : formule figée au 03/11/2026, entrées à partir du 04/11/2026 ; "
                     "effectif suffisant vers l'automne 2027. Tant qu'il n'est pas atteint, aucune conclusion."},
        "reserves": ["Descriptif, pas une prévision.",
                     "Un seul cycle de marché (environ trois ans) ; univers des titres cotés aujourd'hui (biais du survivant).",
                     "Mesure faite sans le facteur rentabilité : le ROE 2025 n'était pas connu en 2023-2024.",
                     "Observations hebdomadaires qui se chevauchent : fourchettes par blocs de 20 séances."],
    }


def publier(chemin: Path | None = None, sortie: Path = SORTIE) -> Path:
    chemin = Path(chemin) if chemin else dernier_artefact()
    m = construire(chemin)
    Path(sortie).write_text(json.dumps(m, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return Path(sortie)


if __name__ == "__main__":
    f = publier(sys.argv[1] if len(sys.argv) > 1 else None)
    print(f"✅ {f}")
