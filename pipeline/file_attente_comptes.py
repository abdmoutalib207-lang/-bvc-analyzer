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
    return "\n".join(lignes) + "\n"


def main() -> int:
    from pipeline.depots_ammc import charger, depots_par_ticker
    jeu = json.loads(JEU.read_text(encoding="utf-8"))
    f = file_attente(depots_par_ticker(charger()), jeu, jeu["fin_periode"])
    texte = rapport(f)
    print(texte)
    resume = os.environ.get("GITHUB_STEP_SUMMARY")
    if resume:
        with open(resume, "a", encoding="utf-8") as h:
            h.write(texte)
    return 0


if __name__ == "__main__":
    sys.exit(main())
