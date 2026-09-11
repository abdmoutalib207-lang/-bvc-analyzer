#!/usr/bin/env python3
"""Construire une couche CANDIDATE depuis les exports de l'opérateur.

    « Une couche candidate ADH/CSR alimentée directement par les exports
      fournis par Noure, conservés comme référence de travail pour ce
      périmètre. Conserve l'ancien historique intact. »   — revue externe

CE QUI CHANGE PAR RAPPORT À NOS CHANDELLES
──────────────────────────────────────────
Nos chandelles portent UN champ `v`. L'export en porte DEUX, et la
confrontation a montré qu'ils ne se confondent pas :

    « Volume (MAD) »      un montant
    « Titres Échangés »   une quantité

⚠️ ET LE CHAMP `v` NE GARDE PAS LE MÊME CONTENU DANS LE TEMPS. Avant juin 2026
il suit le montant ; depuis, il suit tantôt la quantité, tantôt rien de
reconnaissable. Lui attribuer une unité unique serait faux. La couche candidate
garde donc les deux grandeurs SÉPARÉES, avec leur date et leur provenance, et
n'en dérive aucune.

LES CINQ CONTRÔLES DE L'IMPORT
──────────────────────────────
1. **Fichier explicitement choisi** — jamais « le dernier trouvé ».
2. **Ticker vérifié** ligne à ligne contre la colonne de l'export.
3. **Dates** analysées au format déclaré ; toute ligne illisible est comptée,
   jamais ignorée en silence.
4. **Doublons** détectés et signalés — deux lignes pour une même séance ne
   peuvent pas être départagées sans règle, donc on ne tranche pas.
5. **Absences conservées** — le tiret « - » de l'export devient `None`, JAMAIS
   zéro. C'est la faute que ce projet s'interdit partout ailleurs.

    python pipeline/importer_export.py --titre ADH \\
        --fichier sources/ADH/....csv
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter
from datetime import datetime
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
SORTIE = RACINE / "datasets" / "candidat"

# Schéma RELEVÉ sur les exports du 11/09/2026 — pas deviné.
SCHEMA = {
    "separateur": ";",
    "encodage": "utf-8-sig",
    "colonne_date": "Séance",
    "colonne_ticker": "Ticker",
    "format_date": "%d/%m/%Y",
    "champs": {
        "ouverture": "Ouverture",
        "cloture": "Dernier Cours",
        "plus_haut": "Plus Haut",
        "plus_bas": "Plus Bas",
        "volume_mad": "Volume (MAD)",
        "titres_echanges": "Titres Échangés",
        "nb_transactions": "Nb Transactions",
        "capitalisation": "Capitalisation",
    },
    "_absence": "le tiret « - » marque une valeur NON RENSEIGNÉE",
}

# Marqueurs d'absence rencontrés dans les fichiers reçus.
ABSENCES = {"", "-", "--", "n/a", "N/A", "ND"}


def lire_nombre(brut: str) -> tuple:
    """(valeur, état). Quatre états, et « absent » n'est jamais zéro."""
    s = (brut or "").strip().replace(" ", "").replace(" ", "")
    if s in ABSENCES:
        return None, "absent"
    try:
        return float(s), "mesuré"
    except ValueError:
        return None, "illisible"


def empreinte(chemin: Path) -> str:
    h = hashlib.sha256()
    with chemin.open("rb") as f:
        for bloc in iter(lambda: f.read(1 << 16), b""):
            h.update(bloc)
    return h.hexdigest()


def importer(chemin: Path, ticker: str) -> dict:
    ch = SCHEMA["champs"]
    lignes, anomalies = {}, {
        "lignes_lues": 0, "dates_illisibles": [], "ticker_inattendu": [],
        "doublons": [], "valeurs_illisibles": [],
    }
    vus = Counter()

    with chemin.open(encoding=SCHEMA["encodage"], newline="") as f:
        lecteur = csv.DictReader(f, delimiter=SCHEMA["separateur"])
        manquantes = [c for c in list(ch.values()) + [SCHEMA["colonne_date"]]
                      if c not in (lecteur.fieldnames or [])]
        if manquantes:
            raise SystemExit(
                f"colonnes absentes du fichier : {manquantes}\n"
                f"présentes : {lecteur.fieldnames}")

        for n, r in enumerate(lecteur, start=2):
            anomalies["lignes_lues"] += 1

            # ── ticker vérifié ligne à ligne ────────────────────────────────
            # ⚠️ L'export écrit « CSR  » avec des espaces. On compare après
            # nettoyage, sans jamais accepter un autre code.
            brut_t = (r.get(SCHEMA["colonne_ticker"]) or "").strip()
            if brut_t and brut_t.upper() != ticker.upper():
                anomalies["ticker_inattendu"].append(
                    {"ligne": n, "trouve": brut_t, "attendu": ticker})
                continue

            brut_d = (r.get(SCHEMA["colonne_date"]) or "").strip()
            try:
                d = datetime.strptime(brut_d, SCHEMA["format_date"]).date().isoformat()
            except ValueError:
                anomalies["dates_illisibles"].append({"ligne": n, "valeur": brut_d})
                continue

            vus[d] += 1
            if vus[d] > 1:
                # ⚠️ On ne tranche pas : départager deux lignes pour une même
                # séance demanderait une règle que personne ne nous a donnée.
                anomalies["doublons"].append({"ligne": n, "date": d})
                continue

            obs, etats = {"date": d, "_ligne_source": n}, {}
            for nom, col in ch.items():
                v, etat = lire_nombre(r.get(col))
                obs[nom], etats[nom] = v, etat
                if etat == "illisible":
                    anomalies["valeurs_illisibles"].append(
                        {"ligne": n, "date": d, "champ": nom,
                         "valeur": (r.get(col) or "").strip()})
            obs["etats"] = etats
            lignes[d] = obs

    dates = sorted(lignes)
    return {
        "_quoi": f"Couche CANDIDATE {ticker}, importée de l'export de l'opérateur.",
        "_ce_qui_n_est_pas_etabli": (
            "⚠️ Importer n'est pas certifier. Ce fichier ne prouve NI que "
            "l'opérateur a raison contre notre ancien historique, NI que les "
            "opérations sur titres y sont correctement traitées."),
        "_les_deux_grandeurs_restent_separees": (
            "⚠️ `volume_mad` et `titres_echanges` sont conservés DISTINCTS et "
            "aucune conversion n'est appliquée. Notre ancien champ « v » ne "
            "garde pas le même contenu au fil de l'historique : lui attribuer "
            "une unité unique serait faux."),
        "ticker": ticker,
        "source": {
            "fichier": chemin.name,
            "chemin": str(chemin.resolve().relative_to(RACINE)
                          if RACINE in chemin.resolve().parents
                          else chemin.resolve()),
            "empreinte_sha256": empreinte(chemin),
            "importe_le": datetime.now().strftime("%Y-%m-%d %H:%M"),
        },
        "schema": SCHEMA,
        "periode": [dates[0], dates[-1]] if dates else [None, None],
        "seances": len(dates),
        "controles": anomalies,
        "champs_absents": {
            nom: sum(1 for o in lignes.values() if o["etats"][nom] == "absent")
            for nom in ch
        },
        "observations": [lignes[d] for d in dates],
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--titre", required=True)
    ap.add_argument("--fichier", type=Path, required=True,
                    help="fichier EXPLICITEMENT choisi — jamais « le dernier »")
    ap.add_argument("--sortie", type=Path, default=SORTIE)
    a = ap.parse_args()

    if not a.fichier.exists():
        raise SystemExit(f"fichier introuvable : {a.fichier}")
    d = importer(a.fichier, a.titre)
    a.sortie.mkdir(parents=True, exist_ok=True)
    cible = a.sortie / f"{a.titre}.json"
    cible.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")

    c = d["controles"]
    print(f"{a.titre} · {d['seances']} séances · {d['periode'][0]} → {d['periode'][1]}")
    print(f"  lignes lues        {c['lignes_lues']}")
    print(f"  dates illisibles   {len(c['dates_illisibles'])}")
    print(f"  ticker inattendu   {len(c['ticker_inattendu'])}")
    print(f"  doublons           {len(c['doublons'])}")
    print(f"  valeurs illisibles {len(c['valeurs_illisibles'])}")
    print(f"  champs absents     {d['champs_absents']}")
    print(f"→ {cible.relative_to(RACINE)}")


if __name__ == "__main__":
    main()
