"""Nos bougies retrouvent les volumes officiels du marché central.

Référence : datasets/volumes_marche.json (export de la Bourse de Casablanca).
Famille « données publiées » : un échec peut venir d'une bougie fausse OU
d'une séance pas encore écrite — lire l'écart avant de corriger.

- Titres échangés : même grandeur des deux côtés (somme des `v`) → tolérance 0,5 %.
- Montant : nous valorisons au cours de clôture, la Bourse à chaque prix
  d'exécution → écart structurel mesuré ≤ 0,9 % sur 21 séances, tolérance 2 %.
"""
import collections
import glob
import json
import os

import pytest

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _officiel():
    with open(os.path.join(RACINE, "datasets", "volumes_marche.json"), encoding="utf-8") as f:
        return {s["seance"]: s for s in json.load(f)["seances"] if s["marche"] == "Marché central"}


def _nos_totaux(dates):
    titres, montant = collections.defaultdict(float), collections.defaultdict(float)
    for chemin in glob.glob(os.path.join(RACINE, "pipeline", "candles", "*.json")):
        with open(chemin, encoding="utf-8") as f:
            serie = json.load(f)
        serie = serie.get("candles", serie) if isinstance(serie, dict) else serie
        for b in serie:
            if b.get("d") in dates and b.get("v"):
                titres[b["d"]] += b["v"]
                montant[b["d"]] += b["v"] * b["c"]
    return titres, montant


OFFICIEL = _officiel()
TITRES, MONTANT = _nos_totaux(set(OFFICIEL))


@pytest.mark.parametrize("seance", sorted(OFFICIEL))
def test_titres_echanges(seance):
    off = OFFICIEL[seance]["titres"]
    assert abs(TITRES[seance] / off - 1) <= 0.005, (seance, TITRES[seance], off)


@pytest.mark.parametrize("seance", sorted(OFFICIEL))
def test_montant_echange(seance):
    off = OFFICIEL[seance]["volume_mad"]
    assert abs(MONTANT[seance] / off - 1) <= 0.02, (seance, MONTANT[seance], off)
