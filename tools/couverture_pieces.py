"""Couverture des pièces sources : un relevé par titre, pour TOUS les titres.

Le chercheur de pièces couvre l'univers entier, pas seulement les titres
bloqués : un titre noté à 100 % sur des chiffres sans pièce n'est pas
plus fiable qu'un titre bloqué, il le cache mieux. Ce script dit, pour
chacun des titres de data.json, s'il a un relevé, de quand il date, et
ce que dit la note publiée. Lecture seule.

    python3 tools/couverture_pieces.py            # tableau complet
    python3 tools/couverture_pieces.py --a-faire  # titres sans relevé ou relevé périmé
"""
import argparse
import datetime as dt
import json
import os
import sys

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PERIME_JOURS = 120  # au-delà, un nouveau dépôt (semestriel, annuel) a pu paraître


def etat(racine=RACINE, aujourd_hui=None):
    aujourd_hui = aujourd_hui or dt.date.today()
    with open(os.path.join(racine, "data.json"), encoding="utf-8") as f:
        titres = json.load(f)["tickers"]
    lignes = []
    for t in titres:
        sym = t["symbol"]
        nf = t.get("note_fond") or {}
        chemin = os.path.join(racine, "datasets", "releves", f"{sym}.json")
        releve_le, age = None, None
        if os.path.exists(chemin):
            with open(chemin, encoding="utf-8") as f:
                releve_le = (json.load(f).get("releve_le") or "")[:10] or None
            if releve_le:
                age = (aujourd_hui - dt.date.fromisoformat(releve_le)).days
        manquantes = [k for k, v in (nf.get("composantes") or {}).items()
                      if v.get("note") is None]
        a_faire = releve_le is None or age is None or age > PERIME_JOURS
        lignes.append({"symbol": sym, "couverture": nf.get("couverture"),
                       "manquantes": manquantes, "releve_le": releve_le,
                       "age_jours": age, "a_faire": a_faire})
    return lignes


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("--a-faire", action="store_true")
    a = p.parse_args(argv)
    lignes = etat()
    vues = [l for l in lignes if l["a_faire"]] if a.a_faire else lignes
    for l in vues:
        print(f'{l["symbol"]:6} couverture={l["couverture"]!s:5} '
              f'relevé={l["releve_le"] or "—":10} manquantes={",".join(l["manquantes"]) or "—"}')
    faits = sum(not l["a_faire"] for l in lignes)
    print(f"\n{faits}/{len(lignes)} titres ont un relevé de moins de {PERIME_JOURS} jours.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
