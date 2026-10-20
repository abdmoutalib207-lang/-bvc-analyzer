#!/usr/bin/env python3
"""File d'attente des comptes à lire — 30/09/2026.

⚠️ POURQUOI CE MODULE
La DÉTECTION des dépôts existe (`depots_ammc.py`, rafraîchie par
`update_bvc`) ; ce qui manquait est l'ÉCART entre ce qui est déposé et ce qui
est intégré dans `datasets/resultats_s1_2026.json`. Au 30/09, sept sociétés
avaient déposé des comptes semestriels que personne n'avait encore lus, sans
que rien ne le signale.

Ce module ne lit aucun PDF et n'écrit aucun chiffre : il dresse la liste, et
la lecture reste un acte relu (agent `lecteur-comptes`, puis PR). Il ne fait
jamais échouer un workflow — une file non vide n'est pas une panne.

    python pipeline/file_attente_comptes.py
    python pipeline/file_attente_comptes.py --bourse candidats_comptes_bourse.json

SECONDE SOURCE — 20/10/2026. La Bourse de Casablanca met aussi en ligne des
comptes d'émetteurs (`pipeline/controle_bourse.py` en tire les semestriels
non intégrés). Ils s'AJOUTENT à la file, dans une liste à part, sans jamais
remplacer l'AMMC (R3) : un titre déjà présent côté AMMC n'est pas redoublé.
"""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

JEU = RACINE / "datasets" / "resultats_s1_2026.json"
# Un dépôt SEMESTRIEL : « 1er semestre », « S1 », « RFS » (rapport financier
# semestriel), « 30 juin ». Un avertissement sur résultats annonce des
# comptes, il n'en contient pas : il est listé à part.
_SEMESTRE = re.compile(r"(?i)1er semestre|premier semestre|\bS1\b|\bRFS\b|30 juin|juin 2026")


def file_attente(depots: dict, jeu: dict, depuis: str) -> dict:
    """Répartit les dépôts semestriels postérieurs à `depuis`. Fonction pure.

    Renvoie {"a_lire": [...], "avertissements": [...], "ecartes": [...]},
    chaque entrée {ticker, date, titre, url} ; triée par date.
    """
    integres = set(jeu.get("titres") or {})
    ecartes = set(jeu.get("_ecartes") or {})
    out = {"a_lire": [], "avertissements": [], "ecartes": []}
    for t, d in depots.items():
        if d["date"] <= depuis or not _SEMESTRE.search(d.get("titre") or ""):
            continue
        if t in integres:
            continue
        e = {"ticker": t, "date": d["date"], "titre": d["titre"], "url": d.get("url")}
        if t in ecartes:
            out["ecartes"].append(e)
        elif d.get("avertissement"):
            out["avertissements"].append(e)
        else:
            out["a_lire"].append(e)
    for v in out.values():
        v.sort(key=lambda e: (e["date"], e["ticker"]))
    return out


def ajouter_bourse(f: dict, candidats: list[dict], jeu: dict) -> dict:
    """Ajoute les candidats de la Bourse sous `bourse`, sans toucher aux listes AMMC. Pure.

    Écartés : un titre déjà intégré ou écarté dans le jeu, ou déjà présent dans
    une liste AMMC (celle-ci reste la source première).
    """
    out = {k: list(v) for k, v in f.items()}
    deja = {e["ticker"] for v in f.values() for e in v}
    deja |= set(jeu.get("titres") or {}) | set(jeu.get("_ecartes") or {})
    vus = set()
    out["bourse"] = []
    for c in candidats or []:
        t = c.get("ticker")
        if not t or t in deja or t in vus:
            continue
        vus.add(t)
        out["bourse"].append({"ticker": t, "date": c.get("date"), "titre": c.get("titre"),
                              "url": c.get("url"), "source": "Bourse de Casablanca"})
    out["bourse"].sort(key=lambda e: (e["date"] or "", e["ticker"]))
    return out


def rapport(f: dict) -> str:
    lignes = [f"## Comptes déposés à l'AMMC, pas encore intégrés : {len(f['a_lire'])}", ""]
    for e in f["a_lire"]:
        lignes.append(f"- **{e['ticker']}** — {e['date']} — [{e['titre']}]({e['url']})")
    if f["avertissements"]:
        lignes += ["", "Avertissements sur résultats (pas de comptes) :"]
        lignes += [f"- {e['ticker']} — {e['date']} — {e['titre']}" for e in f["avertissements"]]
    if f["ecartes"]:
        lignes += ["", "Écartés, motif consigné dans le jeu :"]
        lignes += [f"- {e['ticker']} — {e['date']}" for e in f["ecartes"]]
    if "bourse" in f:
        lignes += ["", f"## Seconde source — Bourse de Casablanca, absents côté AMMC : {len(f['bourse'])}", ""]
        lignes += [f"- **{e['ticker']}** — {e['date'] or 'date inconnue'} — [{e['titre']}]({e['url']})"
                   for e in f["bourse"]]
    return "\n".join(lignes) + "\n"


def _candidats_bourse(argv: list[str]) -> list[dict] | None:
    """Le fichier passé par `--bourse`, ou None. Absent ou illisible : on s'en passe."""
    if "--bourse" not in argv or argv.index("--bourse") + 1 >= len(argv):
        return None
    try:
        return json.loads(Path(argv[argv.index("--bourse") + 1]).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def main(argv: list[str] | None = None) -> int:
    from pipeline.depots_ammc import charger, depots_par_ticker
    jeu = json.loads(JEU.read_text(encoding="utf-8"))
    f = file_attente(depots_par_ticker(charger()), jeu, jeu["fin_periode"])
    bourse = _candidats_bourse(sys.argv[1:] if argv is None else argv)
    if bourse is not None:
        f = ajouter_bourse(f, bourse, jeu)
    texte = rapport(f)
    print(texte)
    resume = os.environ.get("GITHUB_STEP_SUMMARY")
    if resume:
        with open(resume, "a", encoding="utf-8") as h:
            h.write(texte)
    return 0


if __name__ == "__main__":
    sys.exit(main())
