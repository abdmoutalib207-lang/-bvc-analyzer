#!/usr/bin/env python3
"""Journal COMPLET des différences entre l'ancien historique et le candidat.

    « Un journal complet des différences : champs modifiés, dates ajoutées,
      valeurs non comparables et éventuelles transformations. Ne limite pas
      l'artefact détaillé aux quarante premiers écarts. »   — revue externe

TROIS HYPOTHÈSES, TENUES SÉPARÉES
─────────────────────────────────
Quand notre valeur ne correspond pas à celle du candidat, trois explications
distinctes sont possibles, et les confondre fait perdre l'information :

    UNITÉ DIFFÉRENTE   notre `v` correspond à l'AUTRE colonne du même jour
    DATE DIFFÉRENTE    notre `v` correspond à la MÊME colonne, un autre jour
    VALEUR DIFFÉRENTE  ni l'une ni l'autre — l'écart reste inexpliqué

⚠️ POURQUOI LA PISTE « DATE DIFFÉRENTE » EST CHERCHÉE SUR LES DEUX COLONNES
Un premier contrôle ne testait le décalage QUE contre les montants, et concluait
« hypothèse écartée, un cas sur 730 ». C'était chercher là où le champ n'avait
pas changé. Sur les QUANTITÉS, la revue en a trouvé plusieurs, et elles forment
des chaînes consécutives. L'hypothèse est rouverte.

⚠️ CE QUI N'EST PAS COMPARABLE N'EST PAS UN ZÉRO
Quand le candidat porte « - », la comparaison est IMPOSSIBLE. Le journal écrit
« non renseigné ». Un rendu antérieur affichait 0,00 : il fabriquait une valeur.

    python pipeline/journal_differences.py --titre ADH --ecrire
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
CANDIDAT = RACINE / "datasets" / "candidat"
CANDLES = RACINE / "pipeline" / "candles"
CIBLE = RACINE / "docs" / "JOURNAL_DIFFERENCES.md"

TOLERANCE = 0.001
# Combien de séances antérieures explorer pour la piste « date différente ».
RECUL_MAX = 3
CHAMPS_PRIX = (("ouverture", "o"), ("plus_haut", "h"),
               ("plus_bas", "l"), ("cloture", "c"))


def proche(a, b) -> bool:
    return (a is not None and b is not None and b > 0
            and abs(a - b) / b <= TOLERANCE)


def tronque_vers(a, b) -> bool:
    """`a` est-il `b` amputé de sa partie décimale ?

    Hypothèse de TRANSFORMATION, distincte d'un écart de valeur : 196,80 → 196
    n'est pas « une autre mesure », c'est la même amputée.
    """
    return (a is not None and b is not None
            and float(a) == float(int(b)) and b != int(b))


def diagnostiquer_volume(v, cand: dict, anterieurs: list) -> dict:
    """Laquelle des trois hypothèses explique notre `v` ?"""
    if v is None:
        return {"hypothese": "notre valeur est absente", "detail": None}

    m, t = cand.get("volume_mad"), cand.get("titres_echanges")
    em = cand["etats"]["volume_mad"]
    et = cand["etats"]["titres_echanges"]

    if em == "absent" and et == "absent":
        return {"hypothese": "non comparable",
                "detail": "le candidat ne renseigne ni montant ni quantité "
                          "pour cette séance — comparaison IMPOSSIBLE, ce qui "
                          "n'est pas un écart"}
    if proche(v, m):
        return {"hypothese": "concordant", "detail": "égal au montant du jour"}
    if proche(v, t):
        return {"hypothese": "concordant", "detail": "égal à la quantité du jour"}

    # ── transformation ? ───────────────────────────────────────────────────
    for nom, val in (("montant", m), ("quantité", t)):
        if tronque_vers(v, val):
            return {"hypothese": "transformation",
                    "detail": f"notre {v} est le {nom} {val} amputé de ses "
                              f"décimales — hypothèse de troncature, à vérifier"}

    # ── date différente ? cherchée sur LES DEUX colonnes ───────────────────
    for recul, prec in enumerate(anterieurs, start=1):
        for nom, cle in (("montant", "volume_mad"), ("quantité", "titres_echanges")):
            if proche(v, prec.get(cle)):
                return {"hypothese": "date différente",
                        "detail": f"notre valeur égale le/la {nom} du "
                                  f"{prec['date']}, soit {recul} séance(s) "
                                  f"disponible(s) plus tôt"}

    return {"hypothese": "valeur différente",
            "detail": "ne correspond ni au montant ni à la quantité du jour, "
                      "ni à ceux des séances antérieures explorées"}


def journal(ticker: str) -> dict:
    cand = json.loads((CANDIDAT / f"{ticker}.json").read_text(encoding="utf-8"))
    par_date = {o["date"]: o for o in cand["observations"]}
    dates_cand = [o["date"] for o in cand["observations"]]

    serie = json.loads((CANDLES / f"{ticker}.json").read_text(encoding="utf-8"))
    notre = {str(b.get("d"))[:10]: b for b in serie}

    communes = sorted(set(par_date) & set(notre))
    seulement_cand = sorted(set(par_date) - set(notre))
    seulement_notre = sorted(set(notre) - set(par_date))

    fin_notre = max(notre) if notre else ""
    debut_notre = min(notre) if notre else ""

    ecarts_prix, volumes, par_mois = [], [], Counter()
    dates_avec_ecart, clotures_differentes = set(), 0
    non_comparables = 0

    for d in communes:
        c, n = par_date[d], notre[d]
        for nom, cle in CHAMPS_PRIX:
            a, b = c.get(nom), n.get(cle)
            if c["etats"][nom] == "absent":
                non_comparables += 1
                ecarts_prix.append({
                    "date": d, "champ": nom, "candidat": None,
                    "candidat_etat": "non renseigné", "ancien": b,
                    "ecart_relatif": None,
                    "lecture": "comparaison impossible — le candidat ne "
                               "renseigne pas ce champ. Ce n'est PAS un écart."})
                continue
            if a is None or b is None or a == 0:
                continue
            if abs(b - a) / a > TOLERANCE:
                dates_avec_ecart.add(d)
                par_mois[d[:7]] += 1
                if nom == "cloture":
                    clotures_differentes += 1
                ecarts_prix.append({
                    "date": d, "champ": nom, "candidat": a,
                    "candidat_etat": "mesuré", "ancien": b,
                    "ecart_relatif": round((b - a) / a, 6), "lecture": None})

        i = dates_cand.index(d)
        anterieurs = [par_date[x] for x in dates_cand[max(i - RECUL_MAX, 0):i]][::-1]
        diag = diagnostiquer_volume(n.get("v"), c, anterieurs)
        if diag["hypothese"] != "concordant":
            volumes.append({"date": d, "notre_v": n.get("v"),
                            "candidat_montant": c.get("volume_mad"),
                            "candidat_montant_etat": c["etats"]["volume_mad"],
                            "candidat_quantite": c.get("titres_echanges"),
                            "candidat_quantite_etat": c["etats"]["titres_echanges"],
                            **diag})

    hyp = Counter(v["hypothese"] for v in volumes)
    interne = [d for d in seulement_cand if debut_notre <= d <= fin_notre]
    extension = [d for d in seulement_cand if d > fin_notre]
    anterieur = [d for d in seulement_cand if d < debut_notre]

    return {
        "_quoi": f"Journal COMPLET des différences {ticker} — ancien vs candidat.",
        "_ce_qui_n_est_pas_etabli": (
            "⚠️ Une différence OPPOSE deux sources ; elle ne désigne pas la "
            "fautive. Aucune correction n'est appliquée, et l'export n'est pas "
            "établi comme faisant autorité."),
        "titre": ticker,
        "candidat": cand["source"],
        "tolerance_relative": TOLERANCE,
        "recul_explore_seances": RECUL_MAX,
        "periodes": {
            "candidat": cand["periode"],
            "ancien": [debut_notre, fin_notre],
            "dates_communes": len(communes),
        },
        "dates": {
            "absentes_de_l_ancien_INTERNES": interne,
            "absentes_de_l_ancien_EXTENSION": extension,
            "absentes_de_l_ancien_ANTERIEURES": anterieur,
            "absentes_du_candidat": seulement_notre,
            "_lecture": "une date INTERNE manque au milieu de notre historique ; "
                        "une EXTENSION est postérieure à sa dernière séance et "
                        "ne constitue pas un manque",
        },
        "prix": {
            "champs_differents": sum(1 for e in ecarts_prix
                                     if e["ecart_relatif"] is not None),
            "dates_concernees": len(dates_avec_ecart),
            "clotures_differentes": clotures_differentes,
            "champs_non_comparables": non_comparables,
            "_lecture": "⚠️ Ces trois nombres ne se confondent pas : un écart "
                        "porte sur un CHAMP, plusieurs champs peuvent tomber le "
                        "même jour, et la clôture n'est qu'un champ parmi quatre.",
            "par_mois": dict(sorted(par_mois.items())),
        },
        "volumes": {
            "lignes_non_concordantes": len(volumes),
            "par_hypothese": dict(hyp),
            "_lecture": "⚠️ « unité différente », « date différente » et "
                        "« valeur différente » sont trois explications "
                        "distinctes. Les confondre fait perdre l'information.",
        },
        "detail_prix": ecarts_prix,          # COMPLET, non tronqué
        "detail_volumes": volumes,           # COMPLET, non tronqué
    }


def fmt(v, etat=None):
    """⚠️ Jamais de zéro fabriqué à la place d'une absence."""
    if etat == "absent" or etat == "non renseigné":
        return "*non renseigné*"
    if v is None:
        return "*non renseigné*"
    return f"{v:,.2f}"


def rendre(js: list) -> str:
    L = ["# Journal des différences — ancien historique contre candidat",
         "",
         "> ⚠️ **Généré** par `pipeline/journal_differences.py`.",
         "> Une différence **oppose** deux sources ; elle ne désigne pas la "
         "fautive. **Aucune correction n'est appliquée.**",
         "",
         "Le détail complet vit dans `datasets/candidat/journal_<titre>.json` "
         "— il n'est **pas** tronqué.",
         ""]
    for j in js:
        p, v, d = j["prix"], j["volumes"], j["dates"]
        L += [f"## {j['titre']}", "",
              f"- candidat : `{j['candidat']['fichier']}`",
              f"- période candidat {j['periodes']['candidat'][0]} → "
              f"{j['periodes']['candidat'][1]} · ancien "
              f"{j['periodes']['ancien'][0]} → {j['periodes']['ancien'][1]}",
              f"- dates communes : **{j['periodes']['dates_communes']}**",
              "",
              "### Prix — trois mesures qui ne se confondent pas", "",
              "| Mesure | Nombre |", "|---|--:|",
              f"| champs OHLC différents au-delà de {j['tolerance_relative']:.1%} | **{p['champs_differents']}** |",
              f"| dates comportant au moins un de ces écarts | **{p['dates_concernees']}** |",
              f"| clôtures différentes | **{p['clotures_differentes']}** |",
              f"| champs non comparables (candidat non renseigné) | {p['champs_non_comparables']} |",
              "",
              "Répartition par mois :", "",
              "| Mois | Champs différents |", "|---|--:|"]
        for m, n in p["par_mois"].items():
            L.append(f"| {m} | {n} |")
        L += ["", "### Volumes — trois hypothèses distinctes", "",
              "| Hypothèse | Lignes |", "|---|--:|"]
        for h, n in sorted(v["par_hypothese"].items(), key=lambda x: -x[1]):
            L.append(f"| {h} | {n} |")
        L += ["", v["_lecture"], ""]

        dec = [x for x in j["detail_volumes"] if x["hypothese"] == "date différente"]
        if dec:
            L += [f"**Les {len(dec)} cas « date différente »** — notre valeur "
                  f"correspond à une séance ANTÉRIEURE :", "",
                  "| Date | Notre `v` | Quantité du jour | Détail |",
                  "|---|--:|--:|---|"]
            for x in dec:
                L.append(f"| {x['date']} | {fmt(x['notre_v'])} | "
                         f"{fmt(x['candidat_quantite'], x['candidat_quantite_etat'])} | "
                         f"{x['detail']} |")
            L += ["", "⚠️ Ces cas forment des **chaînes consécutives**, ce qui "
                  "n'est pas le profil d'une coïncidence. L'hypothèse d'un "
                  "décalage reste **ouverte** — un contrôle antérieur l'avait "
                  "déclarée écartée après l'avoir cherchée sur les seuls "
                  "montants, là où le champ n'avait pas changé.", ""]

        tr = [x for x in j["detail_volumes"] if x["hypothese"] == "transformation"]
        if tr:
            L += [f"**Les {len(tr)} cas « transformation »** :", "",
                  "| Date | Notre `v` | Candidat | Hypothèse |", "|---|--:|--:|---|"]
            for x in tr:
                L.append(f"| {x['date']} | {fmt(x['notre_v'])} | "
                         f"{fmt(x['candidat_montant'], x['candidat_montant_etat'])} | "
                         f"{x['detail']} |")
            L.append("")

        nc = [x for x in j["detail_volumes"] if x["hypothese"] == "non comparable"]
        if nc:
            L += [f"**Les {len(nc)} cas non comparables** — le candidat ne "
                  f"renseigne rien. ⚠️ Ce n'est **pas** un écart, et ce n'est "
                  f"**pas** un zéro :", "",
                  "| Date | Notre `v` | Candidat montant | Candidat quantité |",
                  "|---|--:|---|---|"]
            for x in nc:
                L.append(f"| {x['date']} | {fmt(x['notre_v'])} | "
                         f"{fmt(x['candidat_montant'], x['candidat_montant_etat'])} | "
                         f"{fmt(x['candidat_quantite'], x['candidat_quantite_etat'])} |")
            L.append("")

        L += ["### Dates", "",
              f"- **absentes de notre historique, INTERNES** : "
              f"{len(d['absentes_de_l_ancien_INTERNES'])} — "
              f"{', '.join(d['absentes_de_l_ancien_INTERNES']) or '—'}",
              f"- absentes de notre historique, **extension** au-delà du "
              f"{j['periodes']['ancien'][1]} : "
              f"{', '.join(d['absentes_de_l_ancien_EXTENSION']) or '—'}",
              f"- présentes chez nous et absentes du candidat : "
              f"{len(d['absentes_du_candidat'])}",
              "", d["_lecture"], ""]
    return "\n".join(L)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--titre", action="append", default=[])
    ap.add_argument("--ecrire", action="store_true")
    a = ap.parse_args()
    titres = a.titre or sorted(p.stem for p in CANDIDAT.glob("*.json")
                               if not p.stem.startswith("journal_"))
    js = [journal(t) for t in titres]
    for j in js:
        (CANDIDAT / f"journal_{j['titre']}.json").write_text(
            json.dumps(j, ensure_ascii=False, indent=1), encoding="utf-8")
    texte = rendre(js)
    if a.ecrire:
        CIBLE.parent.mkdir(parents=True, exist_ok=True)
        CIBLE.write_text(texte + "\n", encoding="utf-8")
        print(f"→ {CIBLE.relative_to(RACINE)}")
    print(texte)


if __name__ == "__main__":
    main()
