#!/usr/bin/env python3
"""Les fenêtres où un titre porte les cours d'une autre société.

CE QUI EST ÉTABLI, ET COMMENT
─────────────────────────────
MSA a porté les cours de Mutandis. La mesure est reproductible : sur les dates
où les deux séries existent, les clôtures sont identiques au centime.

⚠️ TROIS HORLOGES, QUI NE DOIVENT PAS ÊTRE CONFONDUES
La revue l'a exigé, et la confusion m'avait fait écrire « le 18 juin, jour de
la correction » :

    date de séance    la date inscrite DANS la donnée
    date d'écriture   le jour où un import a déposé cette ligne
    date du correctif le jour où le code a changé

Un import du 6 juin peut écrire des cours datés du 13 mai. Une observation
antérieure à un workflow ne démontre donc PAS l'existence d'un autre écrivain.
Et le retour de MSA à 860 DH le 18/06 est une date de SÉANCE : l'appeler « jour
de la correction » demanderait de connaître la date d'écriture, que nous
n'avons pas.

CE QUE CE MODULE SERT À FAIRE
─────────────────────────────
Empêcher qu'une fenêtre reconnue contaminée alimente SILENCIEUSEMENT un
indicateur ou un backtest. Il ne répare rien, ne reconstitue rien.

⚠️ NE JAMAIS DÉDUIRE LES VRAIS COURS D'UNE SOCIÉTÉ DE CEUX D'UNE AUTRE.
Savoir que MSA porte les cours de Mutandis ne dit RIEN de ce que valait Marsa
Maroc ces jours-là. Il n'y a pas de règle de trois pour deux entreprises.

    python pipeline/contamination.py --ecrire
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
CANDLES = RACINE / "pipeline" / "candles"
CIBLE = RACINE / "docs" / "CONTAMINATIONS.md"

TOLERANCE = 0.001

# Fenêtres SOUPÇONNÉES de contamination, avec leur niveau de preuve.
# ⚠️ Une entrée ici n'affirme pas que la fenêtre est fausse : elle affirme
# qu'elle ne peut PAS alimenter un calcul sans que le doute soit dit.
SOUPCONS = [
    {
        "titre": "MSA", "suspect": "MUT",
        "debut_seance": "2026-05-13", "fin_seance": "2026-06-16",
        "niveau": "établi par la mesure",
        "fait_observe": "sur les dates où les deux séries existent, les "
                        "clôtures de MSA sont identiques à celles de MUT",
        "hypothese": "le collecteur a demandé « Mutandis » pour MSA et déversé "
                     "les cours reçus dans le fichier de MSA",
        "piece": "commit 48b3c583 du 23/06/2026 — MANUAL_MAP : "
                 "MSA « Mutandis » → « Marsa Maroc »",
        "ce_qui_manque": "la date d'ÉCRITURE des lignes. Le commit est daté du "
                         "23/06 et les séances contaminées s'arrêtent au 16/06 : "
                         "sans journal d'import, le lien reste une inférence.",
        "usages_atteints": ["prix_analyse", "indicateur", "execution_simulee"],
    },
    {
        "titre": "ATL", "suspect": "HAL",
        "debut_seance": "2026-06-05", "fin_seance": "2026-06-16",
        "niveau": "nommé par une pièce, NON reproduit",
        "fait_observe": "rupture aller-retour des clôtures sur la période",
        "hypothese": "ATL a reçu les cours d'Auto Hall",
        "piece": "commit 48b3c583 — ATL « Auto Hall » → « AtlantaSanad »",
        "ce_qui_manque": "la série de HAL ne commence qu'au 19/06/2026 : "
                         "aucune date commune, la correspondance ne peut pas "
                         "être mesurée. L'absence de recouvrement n'est ni une "
                         "confirmation ni une infirmation.",
        "usages_atteints": ["prix_analyse", "indicateur", "execution_simulee"],
    },
    {
        "titre": "CFGB", "suspect": "BMC",
        "debut_seance": "2026-05-13", "fin_seance": "2026-06-16",
        "niveau": "nommé par une pièce, NON reproduit",
        "fait_observe": "rupture aller-retour des clôtures sur la période",
        "hypothese": "CFGB a reçu les cours de BMCI",
        "piece": "commit 48b3c583 — CFGB « BMCI » → « CFG Bank »",
        "ce_qui_manque": "la série de BMC ne commence qu'au 19/06/2026 : aucune "
                         "date commune sur la période suspecte.",
        "usages_atteints": ["prix_analyse", "indicateur", "execution_simulee"],
    },
    {
        "titre": "DAR", "suspect": "RDS",
        "debut_seance": "2026-05-13", "fin_seance": "2026-06-23",
        "niveau": "nommé par une pièce, NON reproduit",
        "fait_observe": "rupture de 176,00 à 4 190,00 au 24/06/2026",
        "hypothese": "DAR a reçu les cours de Résidences Dar Saada",
        "piece": "commit 48b3c583 — DAR « Res.Dar Saada » → « Dari Couspate »",
        "ce_qui_manque": "sur la période, DAR et RDS n'ont qu'UNE date commune "
                         "— le 19/06 — et leurs clôtures y diffèrent. Un seul "
                         "point discordant ne tranche rien.",
        "usages_atteints": ["prix_analyse", "indicateur", "execution_simulee"],
    },
    {
        "titre": "SBS", "suspect": None,
        "debut_seance": None, "fin_seance": None,
        "niveau": "risque ouvert, aucune fenêtre datée",
        "fait_observe": "le collecteur demande encore « Super Cereales » alors "
                        "que le référentiel dit « Société des Boissons du "
                        "Maroc », ISIN MA0000010365",
        "hypothese": "un rafraîchissement d'historique écrirait les cours "
                     "d'une autre société",
        "piece": "commit 48b3c583 — SBS « Ste Boissons » → « Super Cereales », "
                 "correction qui contredit notre propre référentiel",
        "ce_qui_manque": "la réponse du fournisseur. Aucune fenêtre passée "
                         "n'est démontrée contaminée : le risque porte sur "
                         "l'AVENIR, pas sur les données existantes.",
        "usages_atteints": [],
    },
]


def serie(t: str) -> dict:
    f = CANDLES / f"{t}.json"
    if not f.exists():
        return {}
    try:
        s = json.loads(f.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return {}
    return {str(b.get("d"))[:10]: b.get("c") for b in s if b.get("c")}


def mesurer_recouvrement(titre: str, suspect: str, debut: str, fin: str) -> dict:
    """Table reproductible des correspondances entre deux séries."""
    a, b = serie(titre), serie(suspect)
    dates = sorted(d for d in a if debut <= d <= fin)
    communes = [d for d in dates if d in b]
    lignes = [{"date": d, titre: a[d], suspect: b[d],
               "identiques": abs(a[d] - b[d]) / b[d] <= TOLERANCE if b[d] else False}
              for d in communes]
    ident = sum(1 for l in lignes if l["identiques"])
    return {
        "titre": titre, "suspect": suspect,
        "fenetre": [debut, fin],
        "seances_du_titre": len(dates),
        "dates_communes": len(communes),
        "identiques": ident,
        "taux": round(ident / len(communes), 4) if communes else None,
        "_lecture": (
            f"{ident} correspondance(s) exacte(s) sur {len(communes)} date(s) "
            f"comparable(s)" if communes else
            "AUCUNE date commune : le recouvrement ne peut pas être mesuré. "
            "Ce n'est ni une confirmation ni une infirmation."),
        "lignes": lignes,
    }


def inventaire() -> dict:
    out = []
    for s in SOUPCONS:
        e = dict(s)
        if s["suspect"] and s["debut_seance"]:
            e["mesure"] = mesurer_recouvrement(
                s["titre"], s["suspect"], s["debut_seance"], s["fin_seance"])
        else:
            e["mesure"] = None
        out.append(e)
    return {
        "_quoi": "Fenêtres où un titre pourrait porter les cours d'une autre société.",
        "_trois_horloges": (
            "⚠️ Les dates ci-dessous sont des dates de SÉANCE, inscrites dans la "
            "donnée. Elles ne disent NI quand la ligne a été écrite, NI quand le "
            "code a été corrigé. Un import du 6 juin peut écrire des cours datés "
            "du 13 mai."),
        "_interdit": (
            "⚠️ NE JAMAIS déduire les cours d'une société de ceux d'une autre. "
            "Savoir que MSA porte les cours de Mutandis ne dit rien de ce que "
            "valait Marsa Maroc."),
        "fenetres": out,
    }


def fenetre_contaminee(ticker: str, debut: str, fin: str) -> list:
    """Les soupçons qui recouvrent la fenêtre demandée.

    Utilisé par `pipeline/fenetre.py` pour refuser un calcul. ⚠️ Le refus porte
    sur les soupçons DATÉS ; un risque sans fenêtre (SBS) ne bloque aucun
    calcul passé, il bloque une écriture future.
    """
    touches = []
    for s in SOUPCONS:
        if not s["debut_seance"] or s["titre"] != ticker:
            continue
        if (not fin or s["debut_seance"] <= fin) and (not debut or s["fin_seance"] >= debut):
            touches.append(s)
    return touches


def rendre(inv: dict) -> str:
    L = ["# Contaminations entre entreprises — inventaire",
         "",
         "> ⚠️ **Généré** par `pipeline/contamination.py`.",
         "",
         inv["_trois_horloges"], "", inv["_interdit"], "",
         "| Titre | Suspect | Fenêtre (séances) | Niveau | Mesure |",
         "|---|---|---|---|---|"]
    for f in inv["fenetres"]:
        m = f["mesure"]
        mes = (f"{m['identiques']}/{m['dates_communes']} identiques"
               if m and m["dates_communes"] else
               ("aucune date commune" if m else "—"))
        fen = (f"{f['debut_seance']} → {f['fin_seance']}"
               if f["debut_seance"] else "—")
        L.append(f"| **{f['titre']}** | {f['suspect'] or '—'} | {fen} | "
                 f"{f['niveau']} | {mes} |")
    L.append("")

    for f in inv["fenetres"]:
        L += [f"## {f['titre']}", "",
              f"- **Niveau** : {f['niveau']}",
              f"- **Fait observé** : {f['fait_observe']}",
              f"- **Hypothèse** : {f['hypothese']}",
              f"- **Pièce** : {f['piece']}",
              f"- **Ce qui manque** : {f['ce_qui_manque']}",
              f"- **Usages atteints** : "
              f"{', '.join(f['usages_atteints']) or 'aucun usage passé'}", ""]
        m = f["mesure"]
        if m and m["lignes"]:
            L += [f"**Table reproductible — {m['_lecture']}**", "",
                  f"| Date | {m['titre']} | {m['suspect']} | |",
                  "|---|--:|--:|---|"]
            for l in m["lignes"]:
                mark = "**identiques**" if l["identiques"] else ""
                L.append(f"| {l['date']} | {l[m['titre']]:,.2f} | "
                         f"{l[m['suspect']]:,.2f} | {mark} |")
            L.append("")
        elif m:
            L += [f"⚠️ {m['_lecture']}", ""]
    return "\n".join(L)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--ecrire", action="store_true")
    ap.add_argument("--json", type=Path)
    a = ap.parse_args()
    inv = inventaire()
    if a.json:
        a.json.write_text(json.dumps(inv, ensure_ascii=False, indent=1),
                          encoding="utf-8")
    if a.ecrire:
        CIBLE.parent.mkdir(parents=True, exist_ok=True)
        CIBLE.write_text(rendre(inv) + "\n", encoding="utf-8")
        print(f"→ {CIBLE.relative_to(RACINE)}")
    print(rendre(inv))


if __name__ == "__main__":
    main()
