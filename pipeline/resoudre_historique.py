#!/usr/bin/env python3
"""Résolution du conflit sur `pipeline/historical_data.json`, entrée par entrée.

⚠️ CE QUE LA REVUE A INTERDIT, ET POURQUOI
──────────────────────────────────────────
« N'arbitrez pas globalement sur la date du fichier. » La consigne est juste :
`_updated` décrit le moment où le fichier a été ÉCRIT, pas la fraîcheur de ce
qu'il contient. Un fichier écrit plus tard peut très bien porter, pour tel
titre, une séance plus ancienne — c'est précisément ce qui s'est produit le
28/08, quand une source a reculé d'une séance sans que rien ne le signale.

Ce programme n'ouvre donc jamais `_updated`. Il compare **titre par titre**.

LA RÈGLE, EN TROIS CAS, ET RIEN D'AUTRE
───────────────────────────────────────
Pour chaque titre présent d'un côté ou de l'autre :

  1. **DERNIÈRE SÉANCE PLUS RÉCENTE** — l'entrée qui porte la séance la plus
     récente est retenue. C'est la seule comparaison qui parle des données.

  2. **MÊME DERNIÈRE SÉANCE, CONTENU DIFFÉRENT** — on regarde QUELS champs
     diffèrent. Un extremum glissant (`h52w`, `l52w`, `h90`, `l90`) dépend de
     la date à laquelle la fenêtre est ancrée, pas de la séance : deux runs
     séparés d'un jour donnent deux valeurs justes. On retient alors celle du
     run le plus récent, en le DISANT. Tout autre champ en désaccord est
     signalé et **non arbitré** : il n'y a pas de règle pour lui.

  3. **PRÉSENT D'UN SEUL CÔTÉ** — conservé. Un titre ne disparaît jamais d'une
     résolution de conflit.

CE QUE CETTE RÉSOLUTION N'ÉTABLIT PAS
─────────────────────────────────────
⚠️ Elle évite une régression ; elle ne rend pas le fichier fiable. Aucune des
deux versions n'a été produite par le collecteur muni du garde-fou d'identité :
ce sont deux sorties de l'ancien moteur. Les cinq semaines de cours Mutandis
dans l'historique de MSA sont dans les deux.

⚠️ Le moteur protégé ne prend effet qu'au PREMIER RUN APRÈS fusion — et ce run
refusera la quasi-totalité des titres, faute de source portant leur identité.
C'est `save()` qui conservera alors les entrées anciennes, en les marquant.

    python pipeline/resoudre_historique.py --nôtre A.json --leur B.json [--ecrire C.json]
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

# Champs dont la valeur dépend de l'ANCRAGE de la fenêtre, pas de la séance.
# Deux runs séparés d'un jour en donnent deux valeurs également justes.
EXTREMA_GLISSANTS = {"h52w", "l52w", "h90", "l90"}


def _seance(entree: dict | None) -> str:
    return (entree or {}).get("last_date") or ""


def _champs_en_desaccord(a: dict, b: dict) -> list:
    return sorted(k for k in set(a) | set(b)
                  if not k.startswith("_") and a.get(k) != b.get(k))


def resoudre(gauche: dict, droite: dict,
             nom_gauche: str = "gauche", nom_droite: str = "droite") -> dict:
    """Rend le contenu résolu ET le journal de CHAQUE décision.

    Aucune décision n'est prise en bloc : le journal en compte autant que de
    titres, et chacune porte son motif.
    """
    titres = sorted(k for k in set(gauche) | set(droite) if not k.startswith("_"))
    resolu: dict = {}
    journal: list = []
    non_arbitres: list = []

    for t in titres:
        g, d = gauche.get(t), droite.get(t)

        if g is None or d is None:
            cote = nom_gauche if d is None else nom_droite
            resolu[t] = g if d is None else d
            journal.append({"titre": t, "cas": "present_d_un_seul_cote",
                            "retenu": cote,
                            "motif": "un titre ne disparaît pas d'une "
                                     "résolution de conflit"})
            continue

        if g == d:
            resolu[t] = g
            journal.append({"titre": t, "cas": "identique", "retenu": "les deux"})
            continue

        sg, sd = _seance(g), _seance(d)
        if sg != sd:
            plus_recent, cote = (g, nom_gauche) if sg > sd else (d, nom_droite)
            resolu[t] = plus_recent
            journal.append({
                "titre": t, "cas": "seance_plus_recente", "retenu": cote,
                "seances": {nom_gauche: sg or None, nom_droite: sd or None},
                "motif": "la dernière séance portée par l'entrée, jamais la "
                         "date du fichier",
            })
            continue

        # Même séance, contenus différents.
        champs = _champs_en_desaccord(g, d)
        hors_fenetre = [c for c in champs if c not in EXTREMA_GLISSANTS]
        if hors_fenetre:
            # ⚠️ Aucune règle ne couvre ce cas. On ne tranche pas au hasard :
            # on garde l'existant et on le signale pour décision humaine.
            resolu[t] = g
            non_arbitres.append({"titre": t, "seance": sg, "champs": hors_fenetre,
                                 f"{nom_gauche}": {c: g.get(c) for c in hors_fenetre},
                                 f"{nom_droite}": {c: d.get(c) for c in hors_fenetre}})
            journal.append({"titre": t, "cas": "NON_ARBITRE", "retenu": nom_gauche,
                            "champs": hors_fenetre,
                            "motif": "désaccord sur un champ qu'aucune règle "
                                     "ne couvre — conservé tel quel, à trancher"})
            continue

        # Seuls des extrema glissants diffèrent : la fenêtre a glissé.
        resolu[t] = d
        journal.append({
            "titre": t, "cas": "fenetre_glissante", "retenu": nom_droite,
            "champs": champs,
            "valeurs": {c: {nom_gauche: g.get(c), nom_droite: d.get(c)}
                        for c in champs},
            "motif": "ces extrema dépendent de la date d'ancrage de la "
                     "fenêtre, pas de la séance : les deux valeurs sont "
                     "justes, on retient celle du run le plus récent",
        })

    cas = {}
    for e in journal:
        cas[e["cas"]] = cas.get(e["cas"], 0) + 1

    return {
        "_quoi": "résolution du conflit historical_data.json, entrée par entrée",
        "_ce_qui_n_a_PAS_arbitre": (
            "⚠️ La date du fichier (`_updated`) n'est lue nulle part. Un "
            "fichier écrit plus tard peut porter, pour un titre donné, une "
            "séance plus ancienne — cela s'est produit le 28/08/2026."),
        "_ce_qui_n_est_pas_etabli": (
            "⚠️ Cette résolution évite une régression. Elle ne rend PAS le "
            "fichier fiable : aucune des deux versions n'a été produite par le "
            "collecteur muni du garde-fou d'identité."),
        "titres": len(titres),
        "decisions_par_cas": cas,
        "non_arbitres": non_arbitres,
        "journal": journal,
        "resolu": resolu,
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--notre", required=True, type=Path)
    ap.add_argument("--leur", required=True, type=Path)
    ap.add_argument("--nom-notre", default="branche")
    ap.add_argument("--nom-leur", default="main")
    ap.add_argument("--ecrire", type=Path)
    a = ap.parse_args()

    g = json.loads(a.notre.read_text(encoding="utf-8"))
    d = json.loads(a.leur.read_text(encoding="utf-8"))
    r = resoudre(g, d, a.nom_notre, a.nom_leur)

    if a.ecrire:
        sortie = {k: v for k, v in d.items() if k.startswith("_")}
        sortie["_resolution"] = {
            "quoi": "conflit de fusion résolu entrée par entrée",
            "regle": "séance la plus récente ; à séance égale, seuls les "
                     "extrema glissants sont arbitrés ; tout autre désaccord "
                     "est signalé et non tranché",
            "decisions_par_cas": r["decisions_par_cas"],
            "non_arbitres": [x["titre"] for x in r["non_arbitres"]],
        }
        sortie["_tickers"] = len(r["resolu"])
        sortie.update(r["resolu"])
        a.ecrire.write_text(json.dumps(sortie, ensure_ascii=False), encoding="utf-8")
        print(f"→ {a.ecrire}")

    print(json.dumps({k: v for k, v in r.items()
                      if k not in ("resolu", "journal")},
                     ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
