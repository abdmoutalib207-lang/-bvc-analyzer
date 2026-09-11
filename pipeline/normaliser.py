#!/usr/bin/env python3
"""Couche de données normalisées — distincte de l'instantané conservé.

CE QU'ELLE EST, ET CE QU'ELLE N'EST PAS
───────────────────────────────────────
`datasets/lot1a/` est un INSTANTANÉ des séries du dépôt : une copie conforme,
jamais retraitée. Il reste intact.

Cette couche-ci est DÉRIVÉE : chaque observation y porte ce qu'elle
représente et pour quels usages elle est admissible. Aucune valeur de prix
n'est modifiée — le diagnostic des bases de prix (docs/DIAGNOSTIC_SPLITS.md)
est en cours et la revue a demandé qu'aucune correction automatique ne soit
appliquée avant.

⚠️ RÉSERVE DE L'EXPRESSION « DONNÉES BRUTES FOURNISSEUR »
Ni l'instantané ni cette couche ne sont des charges utiles de fournisseur. Ce
sont des séries du dépôt, écrites par le moteur à des dates inconnues, par des
programmes non enregistrés. L'expression « brutes fournisseur » est réservée
aux charges utiles effectivement conservées — nous n'en gardons aucune.

CE QUE CHAQUE OBSERVATION DÉCLARE
─────────────────────────────────
  statut_seance      négociée · sans transaction · suspendue · marché fermé ·
                     inconnue
  volume_etat        mesuré · inconnu · invalide
  base_prix          état d'ajustement CONNU ou INCONNU, jamais supposé
  admissible_pour    les usages auxquels l'observation peut servir

USAGE
    python pipeline/normaliser.py --sortie datasets/lot1b
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))
sys.path.insert(0, str(RACINE / "pipeline"))
from bvc_config import SPLITS, SUSPENSIONS, est_suspendu  # noqa: E402
from qualification import Seance, qualifier_seance, qualifier_volume  # noqa: E402

SOURCE = RACINE / "datasets" / "lot1a"
CALENDRIER = RACINE / "pipeline" / "calendrier_bvc.json"


def charger_calendrier() -> dict:
    if not CALENDRIER.exists():
        return {}
    return json.loads(CALENDRIER.read_text(encoding="utf-8")).get("jours", {})


def marche_ferme(jour: str, cal: dict):
    """True / False / None. ⚠️ None signifie « non confirmé », jamais « ouvert »."""
    e = cal.get(jour)
    if not e:
        return None
    return {"ferme": True, "ouvert": False}.get(e["statut"])


def etat_base_prix(ticker: str) -> dict:
    """Ce que l'on SAIT de la base de prix. Le diagnostic fait foi.

    ⚠️ « inconnu » est le défaut. Une base n'est déclarée que lorsqu'un
    diagnostic l'a établie — voir docs/DIAGNOSTIC_SPLITS.md.
    """
    connus = {
        "MNG": {"etat": "ajuste_une_fois",
                "preuve": "rapport des clôtures 24/07 → 27/07 = 1,091, continu",
                "consequence": "NE PAS réappliquer adjust_splits : double division"},
        "SOT": {"etat": "double_ajustement",
                "preuve": "rapport des clôtures 04/05 → 05/05 = 5,000 exact ; "
                          "l'ouverture du 05/05 (1700) est un prix pré-split",
                "consequence": "historique 5× trop bas avant le 05/05 — NON "
                               "CORRIGÉ, faute de source primaire pré-split"},
    }
    if ticker in connus:
        return connus[ticker]
    if ticker in SPLITS:
        return {"etat": "inconnu",
                "preuve": None,
                "consequence": "opération déclarée au registre, état "
                               "d'ajustement NON diagnostiqué"}
    return {"etat": "sans_operation_declaree", "preuve": None, "consequence": None}


# Amplitude intraday maximale compatible avec R10.
# R10 plafonne la séance à ±10 % du cours de référence : le plus-haut ne peut
# donc excéder 1,10 × référence et le plus-bas descendre sous 0,90 × référence.
# Le rapport h/l est borné par 1,10 / 0,90 ≈ 1,222. Au-delà, la bougie mélange
# des prix qui n'appartiennent pas à la même séance ou pas à la même base.
AMPLITUDE_MAX_R10 = 1.10 / 0.90


def amplitude_impossible(b: dict) -> dict | None:
    """Bougie dont l'amplitude intraday viole la limite réglementaire.

    ⚠️ Ce contrôle a été écrit après un premier détecteur FAUX. La première
    version cherchait `h / l == ratio de l'opération` à 1 % près — elle ne
    trouvait rien, parce que le cours bouge en séance : la bougie SOT du
    05/05/2026 vaut h/l = 4,607, pas 5,000. La coupure nette est ailleurs, et
    elle ne dépend d'aucun ratio : **aucune bougie licite ne peut dépasser
    l'amplitude que R10 autorise.**

    Mesure sur les 4 306 bougies des sept séries figées : UNE seule dépasse le
    seuil, et c'est exactement celle que le diagnostic avait identifiée. Le
    critère ne disqualifie donc rien d'autre au passage.
    """
    h, l = b.get("h"), b.get("l")
    if not h or not l or l <= 0:
        return None
    r = h / l
    if r <= AMPLITUDE_MAX_R10:
        return None
    return {"rapport_h_l": round(r, 4), "maximum_R10": round(AMPLITUDE_MAX_R10, 4),
            "lecture": "amplitude intraday supérieure à ce que la limite ±10 % "
                       "permet : la bougie mêle des prix de bases différentes"}


def cause_amplitude(ticker: str, jour: str) -> str:
    """Nomme la cause quand elle est ÉTABLIE ; sinon dit qu'elle ne l'est pas."""
    for op in SPLITS.get(ticker) or []:
        if op["date"] == jour:
            return (f"opération sur titres déclarée le {jour} (ratio "
                    f"{op['ratio']}) : la bougie porte un prix d'ouverture "
                    f"pré-opération et une clôture post-opération")
    return "cause NON ÉTABLIE — anomalie constatée, non expliquée"


def admissibilite(statut: Seance, base: dict, ticker: str, jour: str,
                  bougie: dict | None = None) -> list:
    """Les usages auxquels cette observation peut servir.

    Une liste vide n'est pas une erreur : elle dit que rien ne peut s'appuyer
    sur cette observation, et c'est une information.
    """
    usages = []
    if base["etat"] == "double_ajustement" and jour < SPLITS[ticker][0]["date"]:
        return []                       # base fausse : aucun usage
    if bougie is not None and amplitude_impossible(bougie):
        return []                       # deux bases dans une seule bougie
    if statut is Seance.NEGOCIEE:
        usages += ["prix", "volume", "indicateur", "execution"]
    elif statut is Seance.SANS_TRANSACTION:
        usages += ["prix", "indicateur"]   # valorisation, pas exécution
    elif statut is Seance.SUSPENDUE:
        usages += ["prix"]                 # dernière cotation, jamais exécution
    elif statut is Seance.INCONNUE:
        usages += ["prix"]
    if base["etat"] == "inconnu":
        usages = [u for u in usages if u != "indicateur"]
    return usages


def normaliser(ticker: str, cal: dict) -> dict:
    src = SOURCE / f"{ticker}.json"
    serie = json.loads(src.read_text(encoding="utf-8"))
    base = etat_base_prix(ticker)
    obs, journal = [], []

    for b in serie:
        jour = str(b.get("d") or "")[:10]
        susp = bool(est_suspendu(ticker, jour))
        mf = marche_ferme(jour, cal)
        statut = qualifier_seance(b, susp, mf)
        etat_v, val_v = qualifier_volume(b.get("v"))
        obs.append({
            "date": jour,
            "ouverture": b.get("o"), "plus_haut": b.get("h"),
            "plus_bas": b.get("l"), "cloture": b.get("c"),
            "volume": val_v,
            "volume_etat": etat_v.value,
            "volume_unite": "nombre de titres",
            "volume_certitude_unite": "présumée — non enregistrée dans la donnée",
            "statut_seance": statut.value,
            "calendrier_confirme": mf is not None,
            "base_prix": base["etat"],
            "admissible_pour": admissibilite(statut, base, ticker, jour, b),
            "amplitude_impossible": (
                dict(amp, cause=cause_amplitude(ticker, jour))
                if (amp := amplitude_impossible(b)) else None),
        })

    journal.append({
        "transformation": "qualification",
        "applique": True,
        "effet": "ajout des statuts ; AUCUNE valeur de prix ou de volume modifiée",
    })
    journal.append({
        "transformation": "ajustement des opérations sur titres",
        "applique": False,
        "effet": "AUCUN. Le diagnostic des bases est en cours et la revue a "
                 "demandé de ne rien corriger automatiquement avant.",
        "etat_diagnostique": base,
    })
    return {"ticker": ticker, "source": str(src.relative_to(RACINE)),
            "empreinte_source": hashlib.sha256(src.read_bytes()).hexdigest(),
            "lignes": len(obs), "base_prix": base,
            "journal_transformations": journal, "observations": obs}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--sortie", type=Path, default=RACINE / "datasets" / "lot1b")
    a = ap.parse_args()
    a.sortie.mkdir(parents=True, exist_ok=True)
    cal = charger_calendrier()
    manif = {
        "_quoi": "Couche NORMALISÉE, dérivée de l'instantané datasets/lot1a.",
        "_ce_que_ce_n_est_pas": "Ni une charge utile de fournisseur, ni une "
                                "série corrigée. Aucune valeur de prix n'a été "
                                "modifiée.",
        "_genere_le": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "_calendrier": str(CALENDRIER.relative_to(RACINE)),
        "series": {},
    }
    for f in sorted(SOURCE.glob("*.json")):
        if f.stem == "MANIFESTE":
            continue
        n = normaliser(f.stem, cal)
        (a.sortie / f"{f.stem}.json").write_text(
            json.dumps(n, ensure_ascii=False, indent=1), encoding="utf-8")
        from collections import Counter
        st = Counter(o["statut_seance"] for o in n["observations"])
        ad = Counter(len(o["admissible_pour"]) == 0 for o in n["observations"])
        manif["series"][f.stem] = {
            "lignes": n["lignes"], "base_prix": n["base_prix"]["etat"],
            "statuts": dict(st), "observations_inadmissibles": ad.get(True, 0),
            "empreinte_source": n["empreinte_source"],
        }
        print(f"  {f.stem:5} {n['lignes']:>4} obs · base {n['base_prix']['etat']:22} "
              f"· inadmissibles {ad.get(True, 0)}")
    (a.sortie / "MANIFESTE.json").write_text(
        json.dumps(manif, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n→ {a.sortie}")


if __name__ == "__main__":
    main()
