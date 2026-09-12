#!/usr/bin/env python3
"""Confronte notre historique d'un titre à l'export de l'opérateur.

⚠️ L'IDENTITÉ D'ABORD, LE RAPPROCHEMENT ENSUITE
───────────────────────────────────────────────
Rien n'est comparé tant que l'identité de l'instrument n'est pas établie sur
la ligne du cours. C'est l'ordre qui manquait en juin 2026 : on rapprochait des
séries en supposant qu'elles désignaient la même société, et l'une d'elles
portait les cours d'une autre.

CE QUE CE PROGRAMME ÉTABLIT
───────────────────────────
  · l'identité portée par l'export, constante ou non
  · la période, les colonnes, leurs unités
  · les séances communes, celles qui manquent de chaque côté
  · les écarts de clôture, datés et chiffrés
  · ce que suit notre champ « v » : le MONTANT EN DIRHAMS ou le NOMBRE DE
    TITRES — les deux restent DISTINCTS, aucune conversion n'est appliquée

CE QU'IL N'ÉTABLIT PAS
──────────────────────
⚠️ Il ne dit pas qui a raison. L'export est la publication de l'opérateur ;
c'est la source la plus proche du marché dont nous disposions, ce n'est pas une
preuve d'exactitude. Un écart est un ÉCART, pas une erreur de notre côté tant
que sa cause n'est pas établie.

⚠️ Les corrections proposées vont dans une COUCHE CANDIDATE, jamais dans les
chandelles publiées. Chaque proposition porte son motif et son niveau de
preuve — « établi par la mesure » ou « hypothèse à confirmer ».

    python pipeline/confronter_historique.py MSA MUT --ecrire
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import statistics
import subprocess
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
SOURCES = RACINE / "sources"
CANDIDAT = RACINE / "datasets" / "historiques_candidats"

COLS = {
    "ouverture": ("Ouverture", "cours en dirhams"),
    "cloture": ("Dernier Cours", "cours en dirhams"),
    "plus_haut": ("Plus Haut", "cours en dirhams"),
    "plus_bas": ("Plus Bas", "cours en dirhams"),
    "volume_mad": ("Volume (MAD)", "MONTANT échangé, en dirhams"),
    "titres_echanges": ("Titres Échangés", "NOMBRE de titres"),
    "nb_transactions": ("Nb Transactions", "nombre de transactions"),
    "capitalisation": ("Capitalisation", "capitalisation en dirhams"),
}
ABSENCES = {"", "-", "--", "n/a", "N/A", "ND"}


def _nb(brut: str):
    s = (brut or "").strip().replace(" ", "").replace(" ", "")
    if s in ABSENCES:
        return None
    try:
        return float(s)
    except ValueError:
        return None


def lire_export(chemin: Path) -> dict:
    lignes = {}
    with chemin.open(encoding="utf-8-sig", newline="") as f:
        lecteur = csv.DictReader(f, delimiter=";")
        colonnes = lecteur.fieldnames or []
        for r in lecteur:
            brut = (r.get("Séance") or "").strip()
            try:
                j, m, a = brut.split("/")
            except ValueError:
                continue
            lignes[f"{a}-{m}-{j}"] = {k: _nb(r.get(c)) for k, (c, _) in COLS.items()}
    return {"colonnes": colonnes, "seances": lignes}


def nos_chandelles(ticker: str, ref: str = "origin/main") -> dict:
    try:
        s = subprocess.check_output(
            ["git", "show", f"{ref}:pipeline/candles/{ticker}.json"],
            text=True, cwd=RACINE, stderr=subprocess.DEVNULL)
    except subprocess.CalledProcessError:
        return {}
    return {b["d"]: b for b in json.loads(s)}


def _unite_du_champ_v(comm, nous, exp) -> dict:
    """Notre « v » suit-il le montant en dirhams, ou le nombre de titres ?

    ⚠️ La réponse N'EST PAS la même d'un titre à l'autre. Mesurée sur ADH et
    CSR, elle donnait le montant en dirhams ; sur MSA, elle donne les titres.
    Aucune conversion n'est donc appliquée nulle part, et les deux colonnes de
    l'export restent séparées.
    """
    mad = titres = base = 0
    for d in comm:
        v = nous[d].get("v")
        e = exp[d]
        if v is None or e["volume_mad"] is None or e["titres_echanges"] is None:
            continue
        base += 1
        if abs(v - e["volume_mad"]) <= max(1.0, 0.01 * e["volume_mad"]):
            mad += 1
        if abs(v - e["titres_echanges"]) <= max(1.0, 0.01 * e["titres_echanges"]):
            titres += 1
    if not base:
        return {"comparables": 0, "_lecture": "aucune séance comparable"}
    return {
        "comparables": base,
        "suit_le_montant_mad": mad, "part_mad": round(100 * mad / base, 1),
        "suit_le_nombre_de_titres": titres, "part_titres": round(100 * titres / base, 1),
        "_lecture": "⚠️ mesure propre à CE titre. Elle ne s'étend à aucun autre : "
                    "la convention du champ varie d'un titre à l'autre et, sur "
                    "un même titre, selon les périodes.",
    }


def confronter(ticker: str, ref: str = "origin/main") -> dict:
    # ── 1. L'IDENTITÉ, AVANT TOUT RAPPROCHEMENT ────────────────────────────
    from identite_source import identite_de_l_export
    from identites import autoriser_ecriture

    fichiers = sorted((SOURCES / ticker).glob("*.csv"))
    if not fichiers:
        return {"ticker": ticker, "erreur": f"aucun export dans sources/{ticker}/"}
    chemin = fichiers[-1]
    lu = identite_de_l_export(chemin)
    if not lu["identite_portee"]:
        return {"ticker": ticker, "identite": lu,
                "_arret": "identité non portée — AUCUN rapprochement n'est fait"}
    aut = autoriser_ecriture(ticker, lu["instrument"])
    if not aut["autorise"]:
        return {"ticker": ticker, "identite": lu, "autorisation": aut,
                "_arret": "l'identité portée ne concorde pas avec notre "
                          "référentiel — AUCUN rapprochement n'est fait"}

    # ── 2. Les deux séries ─────────────────────────────────────────────────
    exp = lire_export(chemin)["seances"]
    nous = nos_chandelles(ticker, ref)
    comm = sorted(set(exp) & set(nous))
    debut_nous = min(nous) if nous else None

    manquantes_dans_notre_plage = sorted(
        d for d in exp if debut_nous and d >= debut_nous and d not in nous)
    anterieures = sorted(d for d in exp if debut_nous and d < debut_nous)
    chez_nous_seulement = sorted(set(nous) - set(exp))

    # ── 3. Les écarts de clôture ───────────────────────────────────────────
    ecarts = []
    for d in comm:
        a, b = nous[d].get("c"), exp[d]["cloture"]
        if a is None or b is None:
            continue
        if abs(a - b) > 0.005:
            ecarts.append({"seance": d, "notre_cloture": a, "operateur": b,
                           "ecart_pct": round((a - b) / b * 100, 2) if b else None})
    par_mois = {}
    for e in ecarts:
        par_mois[e["seance"][:7]] = par_mois.get(e["seance"][:7], 0) + 1

    comparables = [d for d in comm
                   if nous[d].get("c") is not None and exp[d]["cloture"] is not None]
    pct = [abs(e["ecart_pct"]) for e in ecarts if e["ecart_pct"] is not None]

    return {
        "_quoi": f"confrontation de notre historique {ticker} à l'export de l'opérateur",
        "ticker": ticker,
        "piece": {
            "fichier": chemin.name,
            "sha256": hashlib.sha256(chemin.read_bytes()).hexdigest(),
            "octets": chemin.stat().st_size,
        },
        "identite": {
            "instrument_porte": lu["instrument"],
            "ticker_porte": lu["ticker_fournisseur"],
            "constante_sur": lu["lignes_de_cours"],
            "autorisation": aut["preuve"],
            "_lecture": "établie AVANT tout rapprochement, sur la ligne du cours",
        },
        "colonnes_et_unites": {k: {"colonne": c, "unite": u} for k, (c, u) in COLS.items()},
        "periodes": {
            "export": [min(exp), max(exp)] if exp else [None, None],
            "chez_nous": [debut_nous, max(nous)] if nous else [None, None],
            "seances_export": len(exp), "seances_chez_nous": len(nous),
        },
        "couverture": {
            "communes": len(comm),
            "anterieures_a_notre_historique": len(anterieures),
            "manquantes_dans_notre_plage": manquantes_dans_notre_plage,
            "chez_nous_mais_pas_chez_l_operateur": chez_nous_seulement,
        },
        "clotures": {
            "comparables": len(comparables),
            "identiques": len(comparables) - len(ecarts),
            "divergentes": len(ecarts),
            "part_identiques_pct": round(100 * (len(comparables) - len(ecarts))
                                         / len(comparables), 1) if comparables else None,
            "par_mois": dict(sorted(par_mois.items())),
            "ecart_median_pct": round(statistics.median(pct), 2) if pct else None,
            "ecart_max_pct": round(max(pct), 2) if pct else None,
            "superieurs_a_20_pct": sum(1 for p in pct if p > 20),
            "detail": ecarts,
        },
        "champ_v": _unite_du_champ_v(comm, nous, exp),
        "_ce_qui_n_est_pas_etabli":
            "⚠️ Un écart est un ÉCART. L'export est la publication de "
            "l'opérateur, pas une preuve d'exactitude. Aucune correction n'est "
            "appliquée ici : les propositions vont dans une couche candidate.",
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("tickers", nargs="+")
    ap.add_argument("--ref", default="origin/main")
    ap.add_argument("--ecrire", action="store_true")
    a = ap.parse_args()

    for t in a.tickers:
        r = confronter(t, a.ref)
        if a.ecrire:
            CANDIDAT.mkdir(parents=True, exist_ok=True)
            (CANDIDAT / f"confrontation_{t}.json").write_text(
                json.dumps(r, ensure_ascii=False, indent=2), encoding="utf-8")
            print(f"→ datasets/historiques_candidats/confrontation_{t}.json")
        court = {k: v for k, v in r.items() if k != "clotures"}
        if "clotures" in r:
            court["clotures"] = {k: v for k, v in r["clotures"].items() if k != "detail"}
        print(json.dumps(court, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
