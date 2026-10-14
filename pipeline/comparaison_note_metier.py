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


def _palier_simule(t: dict, note, partielle: bool) -> tuple:
    """(v53 simulée, palier simulé, limité par le garde-fou) pour un titre `t` du
    data.json et une note par métier `note`. Pure."""
    actuelle, v53 = t.get("score_fond"), t.get("v53")
    wf = ((t.get("poids") or {}).get("f") or 0) / 100
    simulee = (round(min(max(v53 + (note - actuelle) * wf, 0), 10), 2)
               if None not in (note, v53, actuelle) else None)
    actuel = palier_publie(t.get("sig"))
    if actuel in ("Données insuffisantes", "SUSPENDU"):
        simule = actuel
    else:
        simule = palier(simulee)
        if simule == "ACHETER" and t.get("technique_neutralise"):
            simule = "SURVEILLER"
    avant_garde = simule
    simule = fs.limiter_signal_partiel(actuel, simule, partielle)
    return simulee, simule, simule != avant_garde


_LIBELLE_CODE = {
    "registre_operation_capital": "opération sur le capital (registre OPERATIONS_SUR_CAPITAL)",
    "residu_non_explique": "mouvement de fonds propres hors résultat non expliqué (résidu R > +5 %)",
    "base_non_confirmee": "base 2024 non confirmée identique",
    "bases_contradictoires": "bases contradictoires (sociale / consolidée)",
    "numerateur_non_reproduit": "RNPG ÷ fonds propres 2025 ne reproduit pas le ROE publié",
    "fonds_propres_non_positifs": "fonds propres négatifs ou nuls",
}


def compter_motifs(roes: dict) -> dict:
    """Compte EXACT des motifs d'écartement de la moyenne, par CODE — jamais par
    recherche de texte : le motif du résidu et celui du registre sont deux codes
    distincts et ne se recouvrent pas. `roes` : {titre: dict ROE du module}."""
    c = collections.Counter(r["moyenne_code"] for r in roes.values()
                            if r.get("convention") == "cloture_moyenne_ecartee")
    return {_LIBELLE_CODE.get(k, k): v for k, v in sorted(c.items())}


# ROE d'une assurance avec et sans gains latents (OCI) : AUCUN choix appliqué (décision d'Abd).
# Valeurs relevées sur pièce par la contre-vérification de #241 ; les montants d'OCI ne sont pas
# dans les faits financiers du dépôt. Ce qui n'est pas relevé est ABSENT, jamais zéro ni estimé.
OCI_ASSURANCES = {
    "WAF": {"roe_avec_oci": {"cloture": 6.86, "moyenne": 7.45}, "roe_hors_oci": {"cloture": 10.05, "moyenne": 10.35},
            "source": "Wafa Assurance RFA 2025 p.16 (gains latents), relevé de la contre-vérification de #241 du 14/10/2026"},
    "ATL": {"roe_avec_oci": None, "roe_hors_oci": None,
            "source": "non relevé : ni le montant d'OCI d'AtlantaSanad ni son ROE hors gains latents ne sont dans les faits "
                      "financiers ; à lire dans le RFA 2025 avant toute décision"},
}


def _bloc_oci(res: dict) -> dict:
    out = {}
    for t, x in OCI_ASSURANCES.items():
        roe = res[t]["entree"]["roe"]
        out[t] = {**x, "roe_avec_oci_recalcule": {"cloture": roe.get("valeur_cloture_non_arrondie"),
                                                  "moyenne": roe.get("valeur_moyenne")},
                  "convention_retenue_dans_la_comparaison": roe.get("convention"),
                  "decision": "AUCUN choix appliqué — revient à Abd Moutalib"}
    return out


def _roe_exercice(res: dict) -> dict:
    """Pour chaque titre qui a un ROE d'exercice : ROE de clôture (publié et NON arrondi),
    ROE moyen, convention retenue, motif, résidu, pages. L'écart est mesuré contre la clôture
    NON arrondie (RNPG ÷ fonds propres 2025), pas contre le ROE publié à 0,1."""
    out = {}
    for s, r in res.items():
        roe = r["entree"]["roe"]
        if not roe.get("convention") or roe["convention"] == "remplacement_12m":
            continue
        nr, mv = roe.get("valeur_cloture_non_arrondie"), roe.get("valeur_moyenne")
        out[s] = {"famille": r["famille"], "convention": roe["convention"], "motif": roe.get("moyenne_ecartee"),
                  "code_motif": roe.get("moyenne_code"),
                  "roe_cloture_publie": roe.get("valeur_cloture_publiee"), "roe_cloture_non_arrondi": nr,
                  "roe_moyen": mv, "ecart_moyen_moins_cloture_non_arrondie": (round(mv - nr, 3) if None not in (mv, nr) else None),
                  "roe_retenu": roe["valeur"],
                  "residu_mmad": roe.get("residu_mmad"), "residu_pct_fonds_propres_2024": roe.get("residu_pct"),
                  "fonds_propres_2024": roe.get("fonds_propres_2024"), "fonds_propres_2025": roe.get("fonds_propres_2025"),
                  "rnpg_2025": roe.get("rnpg_2025"), "page_2025": roe.get("page_2025"), "page_2024": roe.get("page_2024"),
                  "rentabilite_utilise_le_roe": r["criteres"]["rentabilite"].get("convention") is not None}
    return out


def _effet_convention_roe(res: dict, res_cloture: dict, T: dict) -> dict:
    """Effet de la convention « fonds propres moyens » sur la note par métier."""
    par_titre, comptes = {}, collections.Counter()
    roes = {s: r["entree"]["roe"] for s, r in res.items()}
    for s, r in res.items():
        roe = r["entree"]["roe"]
        comptes[roe.get("convention") or ("roe_" + roe["etat"])] += 1
        r0 = res_cloture[s]
        n1, n0 = r["note"], r0["note"]
        c1, c0 = r["criteres"]["rentabilite"], r0["criteres"]["rentabilite"]
        if c1.get("valeur") == c0.get("valeur") and n1 == n0:
            continue
        _, p1, _ = _palier_simule(T.get(s, {}), n1, r["partielle"])
        _, p0, _ = _palier_simule(T.get(s, {}), n0, r0["partielle"])
        par_titre[s] = {"convention": roe.get("convention"),
                        "roe_cloture": c0.get("valeur"), "roe_moyenne": c1.get("valeur"),
                        "note_rentabilite_avant": c0.get("note"), "note_rentabilite_apres": c1.get("note"),
                        "note_metier_avant": n0, "note_metier_apres": n1,
                        "ecart_note_metier": round(n1 - n0, 2) if None not in (n0, n1) else None,
                        "palier_simule_avant": p0, "palier_simule_apres": p1}
    ecarts = [x["ecart_note_metier"] for x in par_titre.values() if x["ecart_note_metier"] is not None]
    ex = _roe_exercice(res)
    sur_moy = [x["ecart_moyen_moins_cloture_non_arrondie"] for x in ex.values()
               if x["convention"] == "moyenne" and x["ecart_moyen_moins_cloture_non_arrondie"] is not None]
    return {
        "titres_avec_roe_d_exercice": len(ex),
        "titres_sur_moyenne": comptes.get("moyenne", 0),
        "titres_sur_cloture_moyenne_ecartee": comptes.get("cloture_moyenne_ecartee", 0),
        "titres_sur_cloture_moyenne_indisponible": comptes.get("cloture_moyenne_indisponible", 0),
        "titres_en_remplacement_12_mois": comptes.get("remplacement_12m", 0),
        "titres_sans_roe_d_exercice": sum(v for k, v in comptes.items() if k.startswith("roe_")),
        "moyenne_ecartee_par_motif": compter_motifs(roes),
        "ecart_roe_moyen_moins_cloture_non_arrondie": {
            "reference": "ROE de clôture NON arrondi = RNPG 2025 ÷ fonds propres 31/12/2025 (le ROE publié est arrondi à 0,1)",
            "titres": len(sur_moy), "mediane": round(statistics.median(sur_moy), 3) if sur_moy else None,
            "moyenne": round(statistics.mean(sur_moy), 3) if sur_moy else None,
            "min": min(sur_moy, default=None), "max": max(sur_moy, default=None),
            "extremes": {s: x["ecart_moyen_moins_cloture_non_arrondie"] for s, x in sorted(
                ex.items(), key=lambda kv: -abs(kv[1]["ecart_moyen_moins_cloture_non_arrondie"] or 0))[:5]
                if x["convention"] == "moyenne"}},
        "notes_metier_modifiees": len([x for x in par_titre.values() if x["ecart_note_metier"]]),
        "ecart_moyen_note_metier": round(statistics.mean(ecarts), 3) if ecarts else None,
        "ecart_absolu_max": max((abs(e) for e in ecarts), default=None),
        "changements_de_palier_simule": {s: {"de": x["palier_simule_avant"], "a": x["palier_simule_apres"]}
                                         for s, x in par_titre.items() if x["palier_simule_avant"] != x["palier_simule_apres"]},
        "detail": par_titre}


def construire(racine: Path = RACINE) -> dict:
    res = fs.noter_depuis_fichiers(racine=racine)
    res_cloture = fs.noter_depuis_fichiers(racine=racine, roe_moyenne=False)
    data = json.loads((racine / "data.json").read_text(encoding="utf-8"))
    T = {t["symbol"]: t for t in data["tickers"]}
    titres, bases_roe, motifs_ve = {}, collections.Counter(), collections.Counter()
    etats = {k: collections.Counter() for k in fs.POIDS}
    refs = {k: collections.Counter() for k in fs.POIDS}
    for s, r in res.items():
        t = T.get(s, {})
        actuelle, v53 = t.get("score_fond"), t.get("v53")
        note = r["note"]
        simulee, simule, limite = _palier_simule(t, note, r["partielle"])
        actuel = palier_publie(t.get("sig"))
        crit = r["criteres"]
        for k, c in crit.items():
            etats[k][c["etat"]] += 1
            if c.get("reference"):
                refs[k][c["reference"]["type"]] += 1
        roe = crit["rentabilite"]
        conv = roe.get("convention")
        if roe["etat"] in (fs.PRESENT, fs.ZERO, fs.REMPLACEMENT) and conv:
            bases_roe[{"moyenne": "ROE d'exercice 2025 sur fonds propres MOYENS (31/12/2024 et 31/12/2025)",
                       "cloture_moyenne_ecartee": "ROE d'exercice 2025 sur CLÔTURE — moyenne ÉCARTÉE (étiqueté)",
                       "cloture_moyenne_indisponible": "ROE d'exercice 2025 sur CLÔTURE — moyenne indisponible (étiqueté)",
                       "remplacement_12m": "REMPLACEMENT : ROE 12 mois à fin juin 2026"}[conv]] += 1
        elif roe["etat"] in (fs.PRESENT, fs.ZERO, fs.REMPLACEMENT):
            bases_roe["ROIC (comptes publiés) — pas de ROE"] += 1
        else:
            bases_roe[f"pas de ROE ({roe['etat']})"] += 1
        motifs_ve[_categorie_ve(r["entree"]["ve"])] += 1
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
        "effet_convention_fonds_propres_moyens": _effet_convention_roe(res, res_cloture, T),
        "roe_d_exercice_par_titre": _roe_exercice(res),
        "assurances_gains_latents_oci": _bloc_oci(res),
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
