#!/usr/bin/env python3
"""Figures, obliques, canaux et gaps PUBLIÉS comme des FAITS DATÉS.

Produit `datasets/figures_publiees.json` : pour chacun des 80 titres de
`bvc_config.TICKERS_ALL`, ce que les détecteurs du 03/10/2026 (`figures.py`,
`lignes.py`, paramètres inchangés) constatent sur les 60 dernières séances
échangées, avec la géométrie nécessaire pour le dessiner, et — pour chaque type
— la fréquence de ce qui a suivi dans le passé, avec son effectif et sa période.

⚠️ CE QUE CE FICHIER N'EST PAS
- Une prévision. Une figure est un fait (« ce motif s'est formé, daté de la
  confirmation de son dernier pivot »). Aucun objectif de cours. Les repères de
  retracement de Fibonacci sont des niveaux de la jambe PASSÉE.
- Une entrée de la note. Rien ici ne touche au score (R8) : mode ombre.
- Une fréquence sur une figure ARMÉE. Les artefacts mesurent ce qui suit la
  CASSURE. Pour une figure armée, la fréquence décrit « les cas où la cassure a
  eu lieu », pas « les cas où elle aura lieu ».

RÈGLE DES 30 CAS : sous 30 cas, aucun pourcentage n'est publié — le statut est
« echantillon_insuffisant » et les champs chiffrés sont absents. Valable pour le
total ET pour chaque sous-période.

FRAIS : les artefacts mesurent l'alpha BRUT de frais ; la part « dans le bon
sens » est donc brute. Le rendement net de 2 % d'aller-retour est publié tel
quel (c'est un rendement moyen du titre, pas un alpha). L'alpha MÉDIAN net de
frais n'existe pas dans les artefacts : `null`, avec la raison.

NON DÉTERMINISTE ? Non. Aucune horloge dans le fichier : il ne change que si les
chandelles changent. Un run sans séance nouvelle réécrit le même octet — donc
aucun commit (voir le rapport de branchement).

Usage : python3 pipeline/figures_publiees.py [--sortie FICHIER] [--fin AAAA-MM-JJ]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))
sys.path.insert(0, str(RACINE / "pipeline"))

from technical.figures import EXPIRE, SEUIL  # noqa: E402
from technical.figures_detail import (ARMEE, DECLENCHEE, EXPIREE, INVALIDEE,  # noqa: E402
                                      figures_detail, gaps_detail, lignes_detail)
from technical.serie_propre import charger, evenements_titre, ruptures, traverse  # noqa: E402

FENETRE = 60                 # dernières séances échangées examinées
MIN_CAS = 30                 # sous ce seuil : « échantillon insuffisant »
INACTIF_APRES = 10           # séances de la place sans échange => titre écarté
ARTEFACT_ALPHA = "datasets/calibrage_technique/etape4_lignes_gaps_hebdo_2026-10-03.json"
ARTEFACT_GAPS = "datasets/calibrage_technique/gaps_comblement_2026-10-21.json"
SORTIE = RACINE / "datasets" / "figures_publiees.json"
PERIODES_ALPHA = {"2023-10_2024-12": {"debut": "2023-10-04", "fin": "2024-12-31"},
                  "2025-01_2026-10": {"debut": "2025-01-01",
                                      "fin": "2026-10 (artefact daté du 2026-10-03)"}}

LIBELLES = {
    "double_creux": "Double creux", "double_sommet": "Double sommet",
    "ete": "Épaule-tête-épaule", "ete_inversee": "Épaule-tête-épaule inversée",
    "tasse_anse": "Tasse avec anse",
    "triangle_ascendant": "Triangle ascendant", "triangle_descendant": "Triangle descendant",
    "triangle_sym": "Triangle symétrique",
    "fibo_rebond_382_618": "Rebond sur le retracement 38,2-61,8 %",
    "fibo_au_dela_786": "Retracement au-delà de 78,6 %",
    "oblique_baissiere": "Oblique descendante", "oblique_haussiere": "Oblique ascendante",
    "canal_haussier": "Canal ascendant",
    "gap_haussier": "Gap haussier", "gap_baissier": "Gap baissier",
}
# Quel signal mesuré décrit « ce qui suit la cassure » de chaque type armé.
REF_ARMEE = {"triangle_sym": ["triangle_sym_haut", "triangle_sym_bas"],
             "canal_haussier": ["canal_rebond_support", "canal_cassure_bas"],
             "oblique_baissiere": ["oblique_baissiere_cassee"],
             "oblique_haussiere": ["oblique_haussiere_cassee"]}
# Signaux dont la fréquence est publiée : ceux que les figures / lignes affichées
# peuvent porter. Les indicateurs (MACD, RSI, Bollinger…) et le hebdomadaire sont
# mesurés dans l'artefact mais ne sont pas détectés ici.
SIGNAUX_PUBLIES = (
    "double_creux", "double_sommet", "ete", "ete_inversee", "tasse_anse",
    "triangle_ascendant", "triangle_descendant", "triangle_sym_haut", "triangle_sym_bas",
    "fibo_rebond_382_618", "fibo_au_dela_786",
    "oblique_baissiere_cassee", "oblique_haussiere_cassee",
    "canal_rebond_support", "canal_cassure_bas")
RAISON_ALPHA_NET = ("l'artefact de calibrage mesure l'alpha brut de frais ; l'alpha médian "
                    "après 2 % d'aller-retour n'y figure pas et n'est pas recalculé ici")
RAISON_MEDIANE = ("la médiane ne s'agrège pas entre deux périodes : elle n'est publiée "
                  "que par période")


# ── fréquences ───────────────────────────────────────────────────────────

def _cellule_alpha(c: dict) -> dict:
    n = int(c.get("n", 0))
    if n < MIN_CAS:
        return {"n": n, "statut": "echantillon_insuffisant"}
    return {"n": n, "statut": "publie", "titres": c["titres"],
            "part_bon_sens_brute_pct": round(100 * c["dans_le_bon_sens"], 1),
            "alpha_median_pct": round(100 * c["alpha_median"], 2),
            "alpha_median_net_frais_pct": None, "raison_alpha_net": RAISON_ALPHA_NET,
            "rendement_net_frais_moyen_pct": round(100 * c["rendement_net_frais"], 2)}


def frequence_signal(sig: dict, h: str = "h20") -> dict:
    """Fréquence d'un signal depuis l'artefact, effectifs et période compris."""
    out = {"sens_teste": sig["sens_attendu"], "horizon_seances": int(h[1:]),
           "mesure": "alpha contre le MASI, rendement total, à l'horizon",
           "frais_inclus_dans_la_part": False, "frais_aller_retour_pct": 2,
           "periodes": PERIODES_ALPHA, "univers": {}}
    for lib in ("tous", "liquides"):
        cel = {p: sig[lib][p][h] for p in PERIODES_ALPHA}
        n = sum(int(c.get("n", 0)) for c in cel.values())
        u = {"n": n, "periodes": {p: _cellule_alpha(c) for p, c in cel.items()}}
        if n < MIN_CAS:
            u["statut"] = "echantillon_insuffisant"
        else:
            k = sum(round(c["dans_le_bon_sens"] * c["n"]) for c in cel.values() if c.get("n"))
            u.update({"statut": "publie", "part_bon_sens_brute_pct": round(100 * k / n, 1),
                      "alpha_median_pct": None, "raison_alpha_median": RAISON_MEDIANE})
        if lib == "liquides":
            u["reproductible_sur_deux_periodes"] = bool(sig["retenu_liquides"][h])
        out["univers"][lib] = u
    return out


def frequence_gap(g: dict) -> dict:
    """Fréquence de comblement (mesurée par `calibrage_gaps.py`)."""
    out = {"mesure": ("part des gaps dont la zone est entièrement traversée en ≤ N séances "
                      "depuis la séance du gap (l'âge de chaque gap publié est `age_seances`)"),
           "frais_inclus": False, "note": "fait de marché, pas une performance : aucun achat supposé",
           "univers": {}}
    for lib in ("tous", "liquides"):
        u = {}
        for h in ("h20", "h60"):
            def cel(c):
                if c.get("n", 0) < MIN_CAS:
                    return {"n": c.get("n", 0), "statut": "echantillon_insuffisant"}
                return {"n": c["n"], "statut": "publie", "pct_combles": c["pct_combles"],
                        "ic95_combles": c["ic95_combles"]}
            u[h] = {"toutes_periodes": cel(g[lib]["toutes_periodes"][h]),
                    "periodes": {p: cel(g[lib][p][h]) for p in PERIODES_ALPHA}}
        out["univers"][lib] = u
    return out


def table_frequences(racine: Path = RACINE) -> tuple[dict, dict]:
    alpha = json.loads((racine / ARTEFACT_ALPHA).read_text(encoding="utf-8"))
    gaps = json.loads((racine / ARTEFACT_GAPS).read_text(encoding="utf-8"))
    freq = {nom: frequence_signal(alpha["signaux"][nom]) for nom in SIGNAUX_PUBLIES}
    for nom, g in gaps["gaps"].items():
        freq[nom] = frequence_gap(g)
    return freq, {"seuil_liquidite_dh": alpha["seuil_liquidite_dh"],
                  "gaps_fin_donnees": gaps["fin_donnees"]}


# ── géométrie ────────────────────────────────────────────────────────────

def _p(s: dict, i: int, prix: float) -> dict:
    return {"date": s["d"][i], "prix": round(float(prix), 4)}


def _droite_en(points: list, i: int) -> float:
    (i1, p1), (i2, p2) = points
    return p1 + (p2 - p1) / (i2 - i1) * (i - i1)


def _hors_fenetre(statut: str, i_fin, n: int) -> bool:
    return statut != ARMEE and (i_fin is None or i_fin < n - FENETRE)


def _fig_publiee(f: dict, s: dict, n: int) -> dict:
    piv = [{"date": s["d"][i], "prix": round(float(p), 4),
            "type": "sommet" if t == "H" else "creux", "date_confirmation": s["d"][cf]}
           for i, p, t, cf in f["pivots"]]
    niv, niv2 = f["niveau"], f["niveau_bas"]

    def niveau(x):
        if x is None:
            return None
        if x["forme"] == "horizontal":
            return {"forme": "horizontal", "prix": round(float(x["prix"]), 4)}
        pts = x["points"]
        return {"forme": "oblique", "points": [_p(s, i, p) for i, p in pts],
                "prix_a_la_derniere_seance": round(float(_droite_en(pts, n - 1)), 4)}
    o = {"type": f["type"], "libelle": LIBELLES[f["type"]],
         "orientation_classique": f["orientation"], "statut": f["statut"],
         "pivots": piv, "date_confirmation": s["d"][f["conf"]],
         "niveau_declenchement": niveau(niv), "niveau_declenchement_bas": niveau(niv2),
         "niveau_invalidation": ({k: round(float(v), 4) for k, v in f["invalidation"].items()}
                                 if f["invalidation"] else None),
         "date_cassure": s["d"][f["i_fin"]] if f["statut"] == DECLENCHEE else None,
         "date_fin": s["d"][f["i_fin"]] if f["statut"] in (INVALIDEE, EXPIREE) else None,
         "signal": f["signal"],
         "frequence_ref": ([f["signal"]] if f["signal"]
                           else REF_ARMEE.get(f["type"], [f["type"]]))}
    if f["statut"] == ARMEE:
        o["frequence_condition"] = "apres_cassure"   # la fréquence décrit ce qui suit la cassure
    if f["type"].startswith("fibo_"):
        (_, p0, _, _), (_, ph, _, _), _ = f["pivots"]
        o["reperes_retracement"] = {str(r): round(float(ph - r * (ph - p0)), 4)
                                    for r in (0.382, 0.5, 0.618, 0.786)}
        o["date_cassure"] = None          # un fait constaté, pas une cassure
        o["date_constat"] = s["d"][f["conf"]]
    return o


def _ligne_publiee(f: dict, s: dict, n: int) -> dict:
    pts = f["points"]
    o = {"type": f["type"], "libelle": LIBELLES[f["type"]], "statut": f["statut"],
         "points": [_p(s, i, p) for i, p in pts],
         "prix_a_la_derniere_seance": round(float(f["droite"](n - 1)), 4),
         "date_confirmation": s["d"][f["conf"]],
         "niveau_invalidation": ({k: round(float(v), 4) for k, v in f["invalidation"].items()}
                                 if f["invalidation"] else None),
         "date_cassure": s["d"][f["i_fin"]] if f["statut"] == DECLENCHEE else None,
         "date_fin": s["d"][f["i_fin"]] if f["statut"] in (EXPIREE, INVALIDEE) else None,
         "signal": f["signal"],
         "frequence_ref": ([f["signal"]] if f["signal"]
                           else REF_ARMEE.get(f["type"], [f["type"]]))}
    if f["statut"] == ARMEE:
        o["frequence_condition"] = "apres_cassure"
    if f["type"] == "canal_haussier":
        ih, ph = f["sommet"]
        decal = ph - f["droite"](ih)          # parallèle au support passant par le sommet
        o["parallele"] = {"points": [_p(s, i, f["droite"](i) + decal) for i, _ in pts],
                          "prix_a_la_derniere_seance": round(float(f["droite"](n - 1) + decal), 4)}
        o["sommet"] = _p(s, ih, ph)
    return o


def _gap_publie(g: dict, s: dict, n: int) -> dict:
    t = g["t"]
    if g["i_comble"] is not None:
        statut = "comble"
    elif g["i_touche"] is not None:
        statut = "partiellement_comble"
    else:
        statut = "ouvert"
    nom = "gap_haussier" if g["sens"] == +1 else "gap_baissier"
    return {"type": nom, "libelle": LIBELLES[nom], "date": s["d"][t], "statut": statut,
            "zone_haute": round(g["haut"], 4), "zone_basse": round(g["bas"], 4),
            "date_retour_dans_la_zone": s["d"][g["i_touche"]] if g["i_touche"] is not None else None,
            "date_comblement": s["d"][g["i_comble"]] if g["i_comble"] is not None else None,
            "age_seances": n - 1 - t, "frequence_ref": [nom]}


# ── un titre ─────────────────────────────────────────────────────────────

def analyser(t: str, s: dict | None, calendrier: list[str], seuil_liq: float) -> dict:
    """Entrée du fichier pour un titre. `s` : sortie de `serie_propre.charger`."""
    vide = {"statut_titre": None, "figures": [], "lignes": [], "gaps": [], "ecartes": {}}
    if s is None or len(s["c"]) < 80:
        return {**vide, "statut_titre": "historique_insuffisant",
                "n_seances_echangees": 0 if s is None else len(s["c"]),
                "raison": "moins de 80 séances échangées (seuil du banc d'essai)"}
    n = len(s["c"])
    der = s["d"][-1]
    base = {"derniere_seance_echangee": der, "n_seances_echangees": n}
    m = s["montant"][-1]
    base["montant_median_60_dh"] = None if np.isnan(m) else round(float(m))
    base["liquide"] = bool(not np.isnan(m) and m >= seuil_liq)
    if len(calendrier) >= INACTIF_APRES and der < calendrier[-INACTIF_APRES]:
        return {**vide, **base, "statut_titre": "inactif",
                "raison": f"aucun échange depuis plus de {INACTIF_APRES} séances de la place"}
    rup = ruptures(s["d"], s["c"], evenements_titre(t))
    ec = {"traversent_une_rupture": 0, "gaps_interrompus_par_une_rupture": 0,
          "gaps_anterieurs_a_une_rupture": 0,
          "anterieures_a_une_rupture": 0}
    figs, lig, gps = [], [], []
    derniere_rupture = max(rup, default=0)
    for f in figures_detail(s["c"]):
        if _hors_fenetre(f["statut"], f["i_fin"], n):
            continue
        fin = n - 1 if f["i_fin"] is None else f["i_fin"]
        if max(fin, f["conf"]) < derniere_rupture:     # autre régime : avant l'opération
            ec["anterieures_a_une_rupture"] += 1
            continue
        if traverse(rup, f["pivots"][0][0], max(fin, f["conf"])):
            ec["traversent_une_rupture"] += 1
            continue
        figs.append(_fig_publiee(f, s, n))
    for f in lignes_detail(s["c"]):
        # Une droite « encore valide » : armée, ou cassée récemment. Une oblique
        # invalidée ou expirée n'est plus une droite à tracer.
        if f["statut"] in (INVALIDEE, EXPIREE) or _hors_fenetre(f["statut"], f["i_fin"], n):
            continue
        fin = n - 1 if f["i_fin"] is None else f["i_fin"]
        if max(fin, f["conf"]) < derniere_rupture:
            ec["anterieures_a_une_rupture"] += 1
            continue
        if traverse(rup, f["points"][0][0], max(fin, f["conf"])):
            ec["traversent_une_rupture"] += 1
            continue
        lig.append(_ligne_publiee(f, s, n))
    for g in gaps_detail(s["o"], s["h"], s["l"], s["c"], frozenset(rup)):
        if not (g["t"] >= n - FENETRE or (g["i_comble"] is not None and g["i_comble"] >= n - FENETRE)):
            continue
        if g["t"] < derniere_rupture:      # avant une opération / reprise : autre régime
            ec["gaps_anterieurs_a_une_rupture"] += 1
            continue
        if g["interrompu"]:
            ec["gaps_interrompus_par_une_rupture"] += 1
            continue
        gps.append(_gap_publie(g, s, n))
    figs.sort(key=lambda x: (x["date_confirmation"], x["type"]))
    lig.sort(key=lambda x: (x["date_confirmation"], x["type"]))
    gps.sort(key=lambda x: (x["date"], x["type"]))
    return {**base, "statut_titre": "analyse", "figures": figs, "lignes": lig,
            "gaps": gps, "ecartes": ec}


def calendrier_marche(series: dict) -> list[str]:
    """Séances où au moins 20 titres ont échangé : le calendrier réel de la place."""
    from collections import Counter
    cnt = Counter(d for s in series.values() if s for d in s["d"])
    return sorted(d for d, k in cnt.items() if k >= 20)


def empreinte(racine: Path = RACINE, fin: str | None = None) -> str:
    """SHA-256 des chandelles lues (80 titres, jusqu'à `fin` inclus).

    Elle dit à quelles données le fichier correspond : si les chandelles ont
    bougé depuis (autre run intrajournalier, réparation rétroactive), le fichier
    n'est plus celui qu'on obtiendrait — et un test le voit sans deviner.
    """
    import hashlib

    import bvc_config as cfg
    h = hashlib.sha256()
    for t in sorted(cfg.TICKERS_ALL):
        try:
            b = json.loads((racine / "pipeline" / "candles" / f"{t}.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            b = []
        h.update(t.encode())
        for x in sorted((x for x in b if fin is None or x["d"] <= fin), key=lambda x: x["d"]):
            h.update(repr((x["d"], x.get("o"), x.get("h"), x.get("l"), x.get("c"), x.get("v"))).encode())
    return h.hexdigest()


def construire(racine: Path = RACINE, fin: str | None = None) -> dict:
    import bvc_config as cfg
    freq, meta = table_frequences(racine)
    series = {t: charger(racine / "pipeline" / "candles" / f"{t}.json", fin)
              for t in cfg.TICKERS_ALL}
    cal = calendrier_marche(series)
    titres = {t: analyser(t, series[t], cal, meta["seuil_liquidite_dh"])
              for t in sorted(cfg.TICKERS_ALL)}
    return {
        "_quoi": "Figures, obliques, canaux et gaps constatés — faits datés, pas des prévisions",
        "_ne_pas_editer": "Produit par pipeline/figures_publiees.py ; tests/test_figures_publiees.py le contrôle.",
        "_r8": "Mode ombre : aucune note ne dépend de ce fichier.",
        "_avertissement": ("Fréquences passées, pas des promesses. Observations chevauchantes "
                           "(un même mouvement compte plusieurs fois) et un seul régime de marché "
                           "par période : les écarts affichés sont optimistes. Les parts sont brutes "
                           "de frais (2 % d'aller-retour non déduits) : la part « dans le bon sens » "
                           "est mesurée sur l'alpha avant frais. Une figure armée n'a pas de "
                           "fréquence propre : la fréquence décrit ce qui suit une CASSURE "
                           "(frequence_condition = apres_cassure)."),
        "derniere_seance_du_marche": cal[-1] if cal else None,
        "entree_sha256": empreinte(racine, fin),
        "methode": {
            "donnees": "pipeline/candles/, séances à volume > 0 uniquement",
            "fenetre_seances": FENETRE, "detecteurs": "pipeline/technical/figures.py et lignes.py, paramètres inchangés",
            "parametres": {"seuil_pivot": SEUIL, "expiration_seances": EXPIRE},
            "pivots": "zigzag sur clôtures, datés de leur CONFIRMATION ; une figure n'existe qu'après la confirmation de son dernier pivot",
            "statuts": {ARMEE: "motif formé, pas encore cassé ni expiré", DECLENCHEE: "clôture au-delà du niveau de déclenchement",
                        INVALIDEE: "clôture au-delà du niveau d'invalidation avant la cassure",
                        EXPIREE: "fenêtre d'observation épuisée sans cassure"},
            "ruptures": ("aucune figure ni gap ne traverse un écart de clôture > 10 % entre deux séances "
                         "échangées (R10) ni une opération déclarée dans bvc_config.SPLITS / SUSPENSIONS (R11)"),
            "gaps": "extrêmes ≥ 1 % au-dessus/au-dessous de la veille, séances à extrêmes réels, jamais > 10 % de la clôture de la veille",
            "titre_inactif": f"écarté si aucun échange depuis plus de {INACTIF_APRES} séances de la place",
            "min_cas_pour_publier": MIN_CAS,
            "artefacts": {"figures_lignes": ARTEFACT_ALPHA, "gaps_comblement": ARTEFACT_GAPS},
            "hebdomadaire": "les variantes hebdomadaires mesurées dans l'artefact ne sont pas détectées ici",
        },
        "seuil_liquidite_dh": meta["seuil_liquidite_dh"],
        "frequences": freq,
        "titres": titres,
    }


def resume(res: dict) -> dict:
    from collections import Counter
    t = res["titres"]
    par_type = Counter()
    par_statut = Counter()
    for v in t.values():
        for k in ("figures", "lignes", "gaps"):
            for x in v[k]:
                par_type[x["type"]] += 1
                par_statut[(x["type"], x["statut"])] += 1
    avec = [k for k, v in t.items() if v["figures"] or v["lignes"] or v["gaps"]]
    def st(f, lib):
        u = f["univers"][lib]
        return u["h20"]["toutes_periodes"]["statut"] if "h20" in u else u["statut"]
    freq_statuts = {k: {lib: st(f, lib) for lib in ("tous", "liquides")}
                    for k, f in res["frequences"].items()}
    return {"titres": len(t), "titres_avec_au_moins_un_element": len(avec),
            "par_type": dict(par_type), "par_type_statut": {f"{a}|{b}": v for (a, b), v in par_statut.items()},
            "statuts_titre": dict(Counter(v["statut_titre"] for v in t.values())),
            "frequences": freq_statuts}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sortie", default=str(SORTIE))
    ap.add_argument("--fin", default=None, help="tronque les chandelles (AAAA-MM-JJ), pour rejouer le passé")
    arg = ap.parse_args()
    res = construire(RACINE, arg.fin)
    texte = json.dumps(res, ensure_ascii=False, indent=1, sort_keys=False) + "\n"
    sortie = Path(arg.sortie)
    # Réécrit seulement si le contenu change : pas de mtime inutile, pas de commit inutile.
    if not sortie.exists() or sortie.read_text(encoding="utf-8") != texte:
        sortie.write_text(texte, encoding="utf-8")
    print(json.dumps(resume(res), ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
