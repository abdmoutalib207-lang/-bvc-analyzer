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
  · le BPA correspondant, sur le nombre MOYEN PONDÉRÉ d'actions de la période
    (IAS 33.19-20 — règle e du 20/10/2026, voir `bvc_config.HISTORIQUE_ACTIONS`) ;
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


FIN_12M = "2026-06-30"
DEBUT_12M = "2025-07-01"


def _ponderees(sym: str | None, t: dict, debut: str, fin: str) -> dict:
    """Nombre d'actions de la période (IAS 33). Sans symbole : nombre actuel."""
    if sym is None:
        return {"nombre": t["actions"], "methode": "nombre actuel", "reserve": None}
    if str(RACINE) not in sys.path:
        sys.path.insert(0, str(RACINE))
    from bvc_config import actions_ponderees
    return actions_ponderees(sym, debut, fin, t["actions"])


def _historique() -> dict:
    if str(RACINE) not in sys.path:
        sys.path.insert(0, str(RACINE))
    from bvc_config import HISTORIQUE_ACTIONS
    return HISTORIQUE_ACTIONS


def douze_mois(t: dict, sym: str | None = None) -> dict | None:
    """Résultat, BPA et croissances sur douze mois. None si une valeur manque.

    ⚠️ RÈGLE e — 20/10/2026 — IAS 33.19-20, 33.21(a), 33.26-28 et 33.64. Le BPA
    se calcule sur le nombre MOYEN PONDÉRÉ d'actions de la période, et non sur
    le nombre ACTUEL : une émission en numéraire ne compte qu'à partir de sa
    date (exclue si elle suit la clôture), une division ou une attribution
    gratuite est rétro-ajustée sur toutes les périodes. Les mouvements, chacun
    avec sa pièce, sont dans `bvc_config.HISTORIQUE_ACTIONS` ; un titre absent
    garde nombre pondéré = nombre actuel. Cas : CIH (émission du 31/07/2025
    dans la période, celle du 28/07/2026 exclue), CDM (émission du 23/07/2026
    exclue), T2S (traitement des actions de priorité non établi : nombre
    actuel ET réserve publiée). Sans `sym`, nombre actuel (tests d'unité)."""
    cles = ("rnpg_exercice_2025", "rnpg_s1_2026", "rnpg_s1_2025", "actions")
    if any(t.get(k) is None for k in cles) or not t["actions"]:
        return None
    # ⚠️ RÈGLE g — 20/10/2026 — IAS 21 / référentiels : jamais d'addition d'un
    # exercice et de semestres tenus dans des référentiels (SCE tunisien, IFRS,
    # CGNC) ou des monnaies différents (ENK : exercice 2025 SCE, S1 2026 IFRS).
    for cle in ("referentiel", "devise"):
        ex, s1 = t.get(f"{cle}_exercice"), t.get(f"{cle}_s1")
        if ex and s1 and ex != s1:
            return None
    rn = t["rnpg_exercice_2025"] + t["rnpg_s1_2026"] - t["rnpg_s1_2025"]
    pond = _ponderees(sym, t, DEBUT_12M, FIN_12M)
    out = {"rnpg_12m": round(rn, 3),
           "bpa_12m": round(rn * 1e6 / pond["nombre"], 2),
           "actions_12m": pond["nombre"], "methode_actions_12m": pond["methode"]}
    if pond.get("reserve"):
        out["reserve_bpa"] = pond["reserve"]
    # ⚠️ Une croissance rapportée à une base NÉGATIVE n'a pas de sens : il n'y
    # a alors PAS de croissance du BPA — 22/10/2026, accord R8 d'Abd Moutalib
    # (audit verificateur-finance, lot B2). Le code reprenait jusqu'ici la
    # croissance publiée par l'émetteur quand il en donnait une : HPS était
    # noté sur +173,7 % (BPA S1 2025 = −47,25 MDH) quand M2M, SNP et UNI, dans
    # le même cas mais sans pourcentage publié, n'en avaient aucune. Une seule
    # règle désormais : base négative → pas de croissance BPA, la note la
    # retire et remet le poids du CA à l'échelle (fond_score, B1). Le
    # pourcentage publié reste consigné (`croissance_bpa_publiee_non_retenue`).
    # ⚠️ Base positive (20/10/2026) — 20/10/2026 (verificateur-finance). Le code
    # reprenait la croissance publiée dès qu'elle existait, base positive
    # comprise : IAM était noté sur +8,1 % « hors exceptionnel » au lieu des
    # −39,7 % que donnent ses comptes (2 482 ÷ 4 117 − 1), CIH sur −11,3 % au
    # lieu de +0,3 %. Base positive : la croissance se CALCULE. La valeur
    # publiée reste consignée dans le jeu de données et rendue à côté
    # (`croissance_bpa_publiee_non_retenue`), jamais appliquée.
    publiee = t.get("croissance_bpa_publiee")
    # ⚠️ RÈGLE c — 20/10/2026 — ÉLÉMENTS EXCEPTIONNELS (IAS 33, IAS 1.87 et
    # 1.97). La VALORISATION lit le résultat PUBLIÉ : le douze mois et le PER
    # ci-dessus ne sont jamais retraités. La CROISSANCE ne l'est que si
    # l'émetteur chiffre l'élément exceptionnel EN MONTANT, sur pièce
    # (`retraitement_exceptionnel` : résultats ajustés des deux semestres, page,
    # citation) ; le pourcentage est alors RECALCULÉ ici sur ses montants,
    # jamais repris. Un pourcentage « hors exceptionnel » publié sans montant
    # (IAM, accord Wana) ne retraite rien : la croissance reste calculée sur le
    # publié.
    # ⚠️ RÈGLE d — 20/10/2026 — PÉRIMÈTRE (IFRS 3.B64(q), IFRS 15, CGNC). La
    # croissance n'est lue à périmètre CONSTANT que si l'émetteur publie le
    # comparatif pro forma EN MONTANTS (`proforma_s1_2025` : ca, rnpg, page,
    # citation) — recalculée ici sur ces montants, jamais son pourcentage.
    # Composante sans montant pro forma : croissance PUBLIÉE et réserve
    # « périmètre élargi » (`perimetre_elargi`). BTP au CGNC : « production de
    # l'exercice » si le CPC en donne la ligne (`production_s1_2026/2025`),
    # sinon le chiffre d'affaires ; jamais les « produits d'exploitation ».
    pf = t.get("proforma_s1_2025") if isinstance(t.get("proforma_s1_2025"), dict) else {}
    perim = []
    rx = t.get("retraitement_exceptionnel")
    if isinstance(rx, dict) and rx.get("rnpg_ajuste_s1_2025") and rx.get("rnpg_ajuste_s1_2026") is not None \
            and rx["rnpg_ajuste_s1_2025"] > 0:
        out["croissance_bpa"] = round((rx["rnpg_ajuste_s1_2026"] / rx["rnpg_ajuste_s1_2025"] - 1) * 100, 1)
        out["croissance_bpa_retraitee"] = rx.get("motif")
        if t["rnpg_s1_2025"] > 0:
            out["croissance_bpa_publiee_brute"] = round((t["rnpg_s1_2026"] / t["rnpg_s1_2025"] - 1) * 100, 1)
    elif pf.get("rnpg") and pf["rnpg"] > 0:
        out["croissance_bpa"] = round((t["rnpg_s1_2026"] / pf["rnpg"] - 1) * 100, 1)
        perim.append(f"résultat à périmètre constant ({t['rnpg_s1_2026']} ÷ {pf['rnpg']} pro forma)")
    elif t["rnpg_s1_2025"] > 0:
        out["croissance_bpa"] = round((t["rnpg_s1_2026"] / t["rnpg_s1_2025"] - 1) * 100, 1)
        if publiee is not None:
            out["croissance_bpa_publiee_non_retenue"] = publiee
    else:
        # Base nulle ou négative (B2, 22/10/2026) : pas de croissance du BPA,
        # pourcentage publié ou non. Il reste consigné à côté, jamais appliqué.
        out["croissance_bpa_base_negative"] = t["rnpg_s1_2025"]
        if publiee is not None:
            out["croissance_bpa_publiee_non_retenue"] = publiee
    if t.get("croissance_ca_publiee") is not None:
        # Variation publiée sans montant (BCP, S1 2026) : reprise telle quelle.
        out["croissance_ca"] = t["croissance_ca_publiee"]
    elif t.get("production_s1_2026") is not None and t.get("production_s1_2025"):
        out["croissance_ca"] = round((t["production_s1_2026"] / t["production_s1_2025"] - 1) * 100, 1)
    elif pf.get("ca") and t.get("ca_s1_2026") is not None:
        out["croissance_ca"] = round((t["ca_s1_2026"] / pf["ca"] - 1) * 100, 1)
        perim.append(f"chiffre d'affaires à périmètre constant ({t['ca_s1_2026']} ÷ {pf['ca']} pro forma)")
    elif t.get("ca_s1_2025"):
        out["croissance_ca"] = round((t["ca_s1_2026"] / t["ca_s1_2025"] - 1) * 100, 1)
    if t.get("perimetre_elargi") or pf:
        publiees = [n for n, k in (("résultat", "rnpg"), ("chiffre d'affaires", "ca"))
                    if not pf.get(k) and not (k == "rnpg" and isinstance(rx, dict))]
        out["perimetre"] = {
            "constant": perim,
            "reserve": (f"périmètre élargi — {', '.join(publiees)} : croissance publiée, pas de comparatif pro "
                        "forma en montants"
                        + (f" ({t.get('perimetre_elargi') or pf.get('motif')})"
                           if (t.get('perimetre_elargi') or pf.get('motif')) else "")
                        if publiees else None),
            "source": pf.get("source"), "page": pf.get("page")}
    return out


def appliquer(jeu: dict, bpa: dict, fond: dict) -> list[str]:
    """Met à jour `bpa` et `fond` EN PLACE. Renvoie le journal des changements."""
    journal = []
    for s, t in jeu["titres"].items():
        m = douze_mois(t, s)
        if m is None:
            journal.append(f"{s} : incomplet, rien d'appliqué")
            continue
        # Règle e (IAS 33.19-20, 20/10/2026) : exercice 2025 sur le nombre
        # moyen pondéré de 2025, comme le douze mois sur le sien.
        pond25 = _ponderees(s, t, "2025-01-01", "2025-12-31")
        exercice = round(t["rnpg_exercice_2025"] * 1e6 / pond25["nombre"], 2)
        b = bpa.setdefault(s, {})
        # ⚠️ L'ancien BPA est conservé à côté du nouveau, jamais effacé.
        if b.get("bpa") is not None and abs(b["bpa"] - exercice) > 0.05:
            b.setdefault("bpa_avant_2026_09_29", b["bpa"])
            journal.append(f"{s} : BPA 2025 {b['bpa']} → {exercice} "
                           f"({t['rnpg_exercice_2025']} MDH ÷ {pond25['nombre']:,} actions)")
            b["bpa"] = exercice
        elif t.get("affiner_bpa") and b.get("bpa") is not None and b["bpa"] != exercice:
            # Écart ≤ 0,05 : même BPA, mais calculé sur un résultat ARRONDI
            # (communiqué) avant d'être lu à l'état (05/10/2026). L'entrée le
            # demande par `affiner_bpa` ; sans ce drapeau, la tolérance de 0,05
            # protège les BPA publiés (HPS 14,31, test_bpa_verifies).
            journal.append(f"{s} : BPA 2025 {b['bpa']} → {exercice} (affiné sur l'état déposé)")
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
        # Le BPA vient désormais d'un état déposé : l'étiquette « tiers » serait
        # un mensonge (05/10/2026). L'ancienne est gardée à côté, jamais effacée.
        if b.get("source") == "casablancabourse_derive":
            b.setdefault("source_avant_2026_10_05", b["source"])
            b["source"] = "resultats_officiels"
        b["rnpg_12m"] = m["rnpg_12m"]
        if s in _historique() and b.get("bpa_12m") not in (None, m["bpa_12m"]):
            # Règle e (20/10/2026) : l'ancien BPA, sur le nombre actuel, est gardé.
            b.setdefault("bpa_12m_avant_2026_10_20", b["bpa_12m"])
        b["bpa_12m"] = m["bpa_12m"]
        if s in _historique():
            b["actions_12m"] = m["actions_12m"]
            b["actions_exercice_2025"] = pond25["nombre"]
            b["methode_actions"] = m["methode_actions_12m"]
        if m.get("reserve_bpa"):
            b["reserve_bpa"] = m["reserve_bpa"]
        else:
            b.pop("reserve_bpa", None)
        b["fin_12m"] = jeu["fin_periode"]
        b["source_12m"] = (f"exercice 2025 + S1 2026 − S1 2025 ; S1 : {t['url']} "
                           f"{t['pages']} ; base : {t['base']}")
        # ⚠️ Ne JAMAIS créer de fiche (lot 13, T2S Group) : compute_fond_score()
        # rend 5,0 pour un titre absent de fondamentaux.json et calcule avec
        # ses valeurs par défaut dès qu'une entrée existe, même vide. Créer la
        # fiche pour y poser une croissance changerait donc une note (R8).
        # Le BPA, lui, est déjà écrit dans bpa.json ci-dessus.
        if not isinstance(fond.get(s), dict):
            journal.append(f"{s} : 12 mois {m['rnpg_12m']} MDH, BPA {m['bpa_12m']} ; "
                           "absent de fondamentaux.json, aucune fiche créée (R8)")
            continue
        f = fond[s]
        avant ={k: f.get(k) for k in ("croissance_bpa", "croissance_ca",
                                        "nb_actions", "date_maj")}
        f.setdefault("avant_2026_09_29", avant)
        for k in ("croissance_bpa", "croissance_ca"):
            if k in m:
                f[k] = m[k]
            elif f.get(k) is not None and k == "croissance_bpa" and "croissance_bpa_base_negative" in m:
                # Base négative (B2, 22/10/2026) : l'ancienne croissance appliquée
                # serait reconduite sans le dire. Elle est retirée ; sa valeur
                # reste dans `avant_2026_09_29` et dans le jeu de données.
                f[k] = None
        if "croissance_bpa_base_negative" in m:
            f["croissance_bpa_non_retenue"] = {
                "publiee": m.get("croissance_bpa_publiee_non_retenue"),
                "motif": f"base négative (résultat S1 2025 = {round(m['croissance_bpa_base_negative'], 1):g} MDH) : "
                         "pas de croissance du BPA, règle unique (22/10/2026)"}
        else:
            f.pop("croissance_bpa_non_retenue", None)
        # Règle d (20/10/2026) : le périmètre de la croissance est dit sur la fiche.
        if m.get("perimetre"):
            f["croissance_perimetre"] = m["perimetre"]
        else:
            f.pop("croissance_perimetre", None)
        # Règle c (20/10/2026) : la base retraitée est dite sur la fiche.
        if m.get("croissance_bpa_retraitee"):
            f["croissance_bpa_retraitee"] = {"motif": m["croissance_bpa_retraitee"],
                                             "croissance_publiee_brute": m.get("croissance_bpa_publiee_brute")}
        else:
            f.pop("croissance_bpa_retraitee", None)
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
        # Les ratios de rentabilité suivent chaque lot (30/09/2026) : un BPA
        # mis à jour sans son ROE laisserait deux dates sur la même fiche.
        if str(RACINE) not in sys.path:
            sys.path.insert(0, str(RACINE))
        from pipeline.ratios_financiers import main as _ratios
        _ratios()
    return 0


if __name__ == "__main__":
    sys.exit(main())
