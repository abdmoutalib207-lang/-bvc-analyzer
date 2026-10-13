#!/usr/bin/env python3
"""Comparaison : note fondamentale ACTUELLE contre note PAR MÉTIER, 80 titres.

    python3 pipeline/comparaison_note_metier.py [--nom comparaison_note_metier_AAAA-MM-JJ.json]

Lecture seule, aucun réseau. Les cours, P/B et notes actuelles viennent de
`data.json` ; les comptes de `fondamentaux.json`, `bpa.json`,
`pipeline/faits_financiers.json` et `datasets/resultats_s1_2026.json`. Deux
exécutions sur les mêmes fichiers donnent le même résultat à l'octet près.

⚠️ MODE COMPARAISON (11/10/2026) : la note par métier n'est PAS retenue dans la
note publiée. Ce fichier existe pour que chaque critère de chaque titre se
vérifie : famille, note actuelle, note par métier, et pour chaque critère sa
valeur, sa source (fichier + pièce), sa période, sa base, son ÉTAT (présent,
absent, zéro confirmé, remplacement, suspendu), son poids nominal et EFFECTIF
après abstentions, et sa référence de comparaison (famille ou cote entière).

⚠️ LA v53 « SIMULÉE » est approchée : v53 publiée + (note métier − note actuelle)
× poids fondamental publié (entier, en %). L'erreur d'arrondi du poids est de
l'ordre de 0,005 × l'écart de note ; elle ne suffit à changer un palier que
pour un titre à moins de ~0,01 d'une frontière.
"""
from __future__ import annotations

import argparse
import collections
import hashlib
import json
import statistics
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

from pipeline.smart_money import fond_score_sectoriel as fs  # noqa: E402

DEFAUT = "comparaison_note_metier_{date}.json"


def palier(v) -> str:
    if v is None:
        return "Données insuffisantes"
    return ("ACHETER" if v >= 6.5 else "SURVEILLER" if v >= 5.5 else "ATTENDRE" if v >= 4.5
            else "ÉVITER" if v >= 3.5 else "ÉVITER FORT")


def palier_publie(signal) -> str | None:
    """Le palier d'un signal publié (« ACHETER ★★ » → ACHETER) ; Données
    insuffisantes et SUSPENDU restent tels quels."""
    sig = (signal or "").strip()
    for p in ("ACHETER", "SURVEILLER", "ATTENDRE", "ÉVITER FORT", "ÉVITER"):
        if sig.startswith(p):
            return p
    return sig or None


_CATEGORIES_MOTIF = (
    ("grandeur contestée", "grandeur contestée (dette nette contredite par l'endettement net)"),
    ("contredite par l'endettement net", "grandeur contestée (dette nette contredite par l'endettement net)"),
    ("sans objet : la dette est l'activité", "sans objet (établissement financier)"),
    ("ROE suspendu pour les foncières", "ROE suspendu : juste valeur des immeubles (foncières)"),
    ("aucun barème sourcé", "dette nette / fonds propres : aucun barème sourcé"),
    ("ROE sans objet", "ROE sans objet (courtier)"),
    ("ratios en vérification", "ratios en vérification (MSA)"),
    ("sans comptes déposés", "société sans comptes déposés"),
    ("périodes différentes", "VE/EBITDA : périodes différentes"),
    ("bilan plus récent", "VE/EBITDA : bilan plus récent disponible"),
    ("EBITDA non positif", "VE/EBITDA : EBITDA non positif"),
    ("minoritaires négatifs", "VE/EBITDA : minoritaires négatifs"),
    ("minoritaires inconnus", "VE/EBITDA : minoritaires inconnus"),
    ("nombre d'actions", "VE/EBITDA : nombre d'actions non recoupé"),
    ("dette nette ou EBITDA absents", "VE/EBITDA : dette nette ou EBITDA absents"),
    ("moins de 3 pairs", "P/B comptable : moins de 3 pairs (actif net réévalué non disponible)"),
    ("P/B comptable non calculable", "P/B comptable non calculable"),
    ("ni ROIC ni ROE", "ni ROIC ni ROE calculables"),
    ("aucun ROE calculé", "aucun ROE calculé"),
    ("croissance non issue", "croissance non issue des dépôts S1 2026"),
    ("BPA 12 mois ou cours absent", "BPA 12 mois ou cours absent"),
    ("dette nette / EBITDA non calculable", "dette nette / EBITDA non calculable"),
    ("dette nette / fonds propres non calculable", "dette nette / fonds propres non calculable à la même date"),
    ("aucune médiane", "aucune médiane de référence"),
)


def categorie_motif(motif: str | None) -> str:
    m = motif or ""
    return next((lib for needle, lib in _CATEGORIES_MOTIF if needle in m), m[:60] or "non précisé")


_MOTIFS_VE = ("périodes différentes", "contredite par l'endettement net", "nombre d'actions", "bilan plus récent",
              "EBITDA non positif", "minoritaires négatifs", "minoritaires inconnus",
              "dette nette ou EBITDA absents", "cours absent")


def _categorie_ve(ve: dict) -> str:
    if not ve.get("motif"):
        return ve["etat"]
    return ve["etat"] + " : " + next((m for m in _MOTIFS_VE if m in ve["motif"]), ve["motif"][:60])


def _stats(x: list[float]) -> dict:
    if not x:
        return {"n": 0}
    return {"n": len(x), "moyenne": round(statistics.mean(x), 2), "mediane": round(statistics.median(x), 2),
            "ecart_type": round(statistics.pstdev(x), 2), "min": min(x), "max": max(x),
            "valeurs_distinctes": len(set(x))}


def construire(racine: Path = RACINE) -> dict:
    res = fs.noter_depuis_fichiers(racine=racine)
    data = json.loads((racine / "data.json").read_text(encoding="utf-8"))
    T = {t["symbol"]: t for t in data["tickers"]}
    titres, bases_roe, motifs_ve = {}, collections.Counter(), collections.Counter()
    etats = {k: collections.Counter() for k in fs.POIDS}
    refs = {k: collections.Counter() for k in fs.POIDS}
    for s, r in res.items():
        t = T.get(s, {})
        actuelle, v53 = t.get("score_fond"), t.get("v53")
        wf = ((t.get("poids") or {}).get("f") or 0) / 100
        note = r["note"]
        simulee = (round(min(max(v53 + (note - actuelle) * wf, 0), 10), 2)
                   if None not in (note, v53, actuelle) else None)
        crit = r["criteres"]
        for k, c in crit.items():
            etats[k][c["etat"]] += 1
            if c.get("reference"):
                refs[k][c["reference"]["type"]] += 1
        roe = crit["rentabilite"]
        if roe["etat"] in (fs.PRESENT, fs.ZERO, fs.REMPLACEMENT) and (roe.get("base") or "").startswith("RNPG"):
            bases_roe["exercice 2025 sur fonds propres MOYENS"
                      if "MOYENS" in roe["base"] else "exercice 2025 sur CLÔTURE 31/12/2025"] += 1
        elif roe["etat"] == fs.REMPLACEMENT and "ROE 12 mois" in (roe.get("base") or ""):
            bases_roe["REMPLACEMENT : 12 mois à fin juin 2026 sur clôture 30/06/2026"] += 1
        elif roe["etat"] in (fs.PRESENT, fs.ZERO, fs.REMPLACEMENT):
            bases_roe["ROIC (comptes publiés) — pas de ROE"] += 1
        else:
            bases_roe[f"pas de ROE ({roe['etat']})"] += 1
        motifs_ve[_categorie_ve(r["entree"]["ve"])] += 1
        # Signal simulé : « Données insuffisantes » (reprise, sans comptes) et
        # SUSPENDU ne dépendent pas de la note ; le plafond de liquidité du
        # verdict (technique neutralisé) transforme ACHETER en SURVEILLER.
        actuel = palier_publie(t.get("sig"))
        limite = False
        if actuel in ("Données insuffisantes", "SUSPENDU"):
            simule = actuel
        else:
            simule = palier(simulee)
            if simule == "ACHETER" and t.get("technique_neutralise"):
                simule = "SURVEILLER"
        # Règle 11 : une note PARTIELLE ne peut pas être plus favorable que la grille actuelle.
        avant_garde = simule
        simule = fs.limiter_signal_partiel(actuel, simule, r["partielle"])
        limite = simule != avant_garde
        titres[s] = {
            "famille": r["famille"], "secteur_referentiel": t.get("sector"),
            "note_actuelle": actuelle, "note_metier": note, "ecart": (round(note - actuelle, 2)
                                                                      if None not in (note, actuelle) else None),
            "v53_actuelle": v53, "v53_simulee": simulee,
            "signal_actuel": t.get("sig"), "palier_actuel": actuel, "palier_simule": simule,
            "poids_disponible": r["poids_disponible"], "motif_sans_note": r["motif"],
            "partielle": r["partielle"], "criteres_essentiels_manquants": r["criteres_essentiels_manquants"],
            "signal_limite_par_note_partielle": limite,
            "dependance_cote": r.get("dependance_cote"), "criteres": crit}
    notes_a = [x["note_actuelle"] for x in titres.values() if x["note_actuelle"] is not None]
    notes_m = [x["note_metier"] for x in titres.values() if x["note_metier"] is not None]
    changements = {s: {"de": x["palier_actuel"], "a": x["palier_simule"], "v53": x["v53_actuelle"],
                       "v53_simulee": x["v53_simulee"]}
                   for s, x in titres.items() if x["palier_actuel"] != x["palier_simule"]}
    suspensions, absences = collections.Counter(), collections.Counter()
    for x in titres.values():
        for c in x["criteres"].values():
            if c["etat"] == fs.SUSPENDU:
                suspensions[categorie_motif(c["motif"])] += 1
            elif c["etat"] == fs.ABSENT:
                absences[categorie_motif(c["motif"])] += 1
    par_famille = {}
    for s, x in titres.items():
        f = par_famille.setdefault(x["famille"], {"titres": [], "notes": 0, "sans_note": []})
        f["titres"].append(s)
        if x["note_metier"] is None:
            f["sans_note"].append(s)
        else:
            f["notes"] += 1
    dep = {s: x["dependance_cote"] for s, x in titres.items() if x["dependance_cote"] and x["dependance_cote"]["criteres"]}
    ecarts = [d["ecart_points"] for d in dep.values() if d["ecart_points"] is not None]
    from bvc_config import TICKERS_ACTIFS
    synthese = {
        "titres": len(titres), "notes_metier": len(notes_m), "sans_note_metier": len(titres) - len(notes_m),
        "distribution_note_actuelle": _stats(notes_a), "distribution_note_metier": _stats(notes_m),
        "par_famille": {f: {"n": len(v["titres"]), "notes": v["notes"], "sans_note": sorted(v["sans_note"])}
                        for f, v in sorted(par_famille.items())},
        "etats_par_critere": {k: dict(sorted(v.items())) for k, v in etats.items()},
        "base_du_roe": dict(sorted(bases_roe.items())),
        "ve_ebitda_etats": dict(sorted(motifs_ve.items())),
        "reference_de_comparaison_par_critere": {k: dict(sorted(v.items())) for k, v in refs.items() if v},
        "dependance_a_la_cote_entiere": {
            "titres_concernes": len(dep), "liste": sorted(dep),
            "points_de_note_en_jeu_somme_absolue": round(sum(abs(e) for e in ecarts), 2),
            "ecart_moyen_points": round(statistics.mean(ecarts), 2) if ecarts else None,
            "ecart_max_points": max((abs(e) for e in ecarts), default=None),
            "notes_qui_n_existeraient_pas_sans_la_cote": sorted(s for s, d in dep.items() if d["note_inexistante_sans_cote"])},
        "notes_partielles": {
            "nombre": sum(1 for x in titres.values() if x["partielle"]),
            "liste": {s: x["criteres_essentiels_manquants"] for s, x in titres.items() if x["partielle"]},
            "signaux_limites_par_le_garde_fou": sorted(s for s, x in titres.items() if x["signal_limite_par_note_partielle"])},
        "suspensions_par_motif": dict(sorted(suspensions.items(), key=lambda kv: (-kv[1], kv[0]))),
        "absences_par_motif": dict(sorted(absences.items(), key=lambda kv: (-kv[1], kv[0]))),
        "criteres_en_remplacement": {k: sum(1 for x in titres.values() if x["criteres"][k]["etat"] == fs.REMPLACEMENT)
                                     for k in fs.POIDS},
        "changements_de_palier_simules": {"nombre": len(changements), "detail": changements},
        "masi_1_sans_note_metier": {s: titres[s]["motif_sans_note"] for s in TICKERS_ACTIFS
                                    if s in titres and titres[s]["note_metier"] is None},
        "lecture": [
            "Les foncières (ARD, IMI, BAL) n'ont pas de note : ROE suspendu (juste valeur), bilan suspendu "
            "(aucun barème sourcé pour dette nette / fonds propres), P/B comptable inutilisable avec 2 pairs. "
            "Résultat attendu, pas un défaut.",
            "Une comparaison à la cote entière n'est pas sectorielle : elle est étiquetée comme telle, son effet "
            "est chiffré ci-dessus.",
            "La note par métier n'est PAS retenue dans la note publiée (mode comparaison)."],
    }
    return {"_quoi": "Comparaison note actuelle / note par métier — mode comparaison, NON retenue dans la note",
            "_methode": __doc__.strip(), "date_donnees": data.get("date_analyse"),
            "source_cours": "data.json",
            "empreintes_sha256": {f: hashlib.sha256((racine / f).read_bytes()).hexdigest() for f in (
                "data.json", "fondamentaux.json", "bpa.json", "pipeline/faits_financiers.json",
                "datasets/resultats_s1_2026.json")},
            "synthese": synthese, "titres": titres}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--nom", default=None)
    a = ap.parse_args()
    out = construire()
    nom = a.nom or DEFAUT.format(date=out["date_donnees"])
    chemin = RACINE / "datasets" / nom
    chemin.write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    sy = out["synthese"]
    print(chemin)
    print(f"{sy['notes_metier']} notes par métier sur {sy['titres']} ; {sy['changements_de_palier_simules']['nombre']} "
          f"changements de palier simulés ; {sy['dependance_a_la_cote_entiere']['titres_concernes']} titres dépendent de la cote entière")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
