#!/usr/bin/env python3
"""Qualifier chaque observation : ce qu'elle représente, et pour quoi elle vaut.

CE QUE CE MODULE AJOUTE
───────────────────────
Jusqu'ici une ligne de chandelle portait des nombres et rien d'autre. On ne
pouvait pas distinguer :

  · une séance où le titre a été négocié ;
  · une séance où le marché était ouvert mais le titre n'a pas échangé ;
  · une séance où le titre était suspendu ;
  · un volume que la source n'a pas renseigné ;
  · un jour où le marché était fermé.

Les cinq s'écrivaient de la même façon : `v = 0`, ou une ligne absente.

CE QUE CETTE CONFUSION A COÛTÉ
──────────────────────────────
`inventaire.py` calculait sa médiane de volume sur `(b.get("v") or 0)`. Un
volume INCONNU devenait donc un zéro mesuré. Aucune valeur absente n'existait
dans les données du 11/09 — les quatre médianes livrées restent justes — mais
la convention contredisait le contrat du projet et aurait produit une erreur
dès la première donnée manquante. Relevé par la revue externe.

LA RÈGLE
────────
Une statistique se calcule sur les valeurs ADMISSIBLES, et publie leur nombre
à côté de la taille de la fenêtre. En deçà d'une couverture déclarée, elle
n'est pas calculée : elle est **non calculable**, ce qui n'est pas zéro.
"""

from __future__ import annotations

import statistics
from enum import Enum

# Couverture minimale pour qu'une statistique de fenêtre soit publiée.
# Nommée ici pour qu'un désaccord porte sur la règle, pas sur le résultat.
COUVERTURE_MINIMALE = 0.60


class Volume(str, Enum):
    """Les trois états d'une valeur de volume, qui ne se remplacent pas."""

    MESURE = "mesuré"          # la source a renseigné une quantité, même nulle
    INCONNU = "inconnu"        # la source n'a rien renseigné
    INVALIDE = "invalide"      # négatif, non numérique, ou hors plage


class Seance(str, Enum):
    """Ce que représente une observation. ⚠️ Distincts, jamais interchangeables."""

    NEGOCIEE = "négociée"                  # échanges constatés
    SANS_TRANSACTION = "sans transaction"  # marché ouvert, titre non échangé
    SUSPENDUE = "suspendue"                # cotation suspendue par le régulateur
    MARCHE_FERME = "marché fermé"          # week-end ou férié établi
    INCONNUE = "inconnue"                  # aucun des précédents n'est démontré


def qualifier_volume(v) -> tuple:
    """(état, valeur admissible ou None). Ne substitue JAMAIS zéro à inconnu."""
    if v is None:
        return Volume.INCONNU, None
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        return Volume.INVALIDE, None
    if v != v or v < 0:                                   # NaN ou négatif
        return Volume.INVALIDE, None
    return Volume.MESURE, float(v)


def qualifier_seance(bougie: dict, suspendu: bool, marche_ferme: bool | None) -> Seance:
    """Statut d'une observation, à partir de ce qui est ÉTABLI.

    ⚠️ `marche_ferme` vaut None quand le calendrier ne permet pas de trancher.
    Dans ce cas le statut est INCONNUE — jamais « sans transaction » par
    défaut. La revue externe a écarté la règle « des clôtures identiques
    signalent une fermeture » : une ressemblance de cours peut déclencher une
    alerte, elle ne décide pas qu'un jour est férié.
    """
    if suspendu:
        return Seance.SUSPENDUE
    if marche_ferme is True:
        return Seance.MARCHE_FERME
    etat, valeur = qualifier_volume(bougie.get("v"))
    if etat is Volume.MESURE and valeur > 0:
        return Seance.NEGOCIEE
    if etat is Volume.MESURE and valeur == 0 and marche_ferme is False:
        return Seance.SANS_TRANSACTION
    return Seance.INCONNUE


def mediane_admissible(valeurs: list, fenetre: int,
                       couverture_min: float = COUVERTURE_MINIMALE) -> dict:
    """Médiane sur les seules valeurs admissibles, avec sa couverture.

    Retourne un dict qui dit TOUJOURS sur quoi il porte :

        {"valeur": …|None, "admissibles": n, "fenetre": N,
         "couverture": n/N, "calculable": bool, "motif": …}

    ⚠️ `valeur` vaut None quand la couverture est insuffisante. None n'est pas
    zéro : une statistique non calculable ne doit pas se lire comme une mesure
    basse.
    """
    admissibles = []
    inconnus = invalides = 0
    for v in valeurs:
        etat, val = qualifier_volume(v)
        if etat is Volume.MESURE:
            admissibles.append(val)
        elif etat is Volume.INCONNU:
            inconnus += 1
        else:
            invalides += 1

    n, N = len(admissibles), max(len(valeurs), 1)
    couverture = n / N
    calculable = n > 0 and couverture >= couverture_min
    return {
        "valeur": statistics.median(admissibles) if calculable else None,
        "admissibles": n,
        "inconnus": inconnus,
        "invalides": invalides,
        "fenetre": fenetre,
        "lignes_dans_la_fenetre": len(valeurs),
        "couverture": round(couverture, 4),
        "couverture_minimale": couverture_min,
        "calculable": calculable,
        "motif": None if calculable else
                 f"couverture {couverture:.0%} < {couverture_min:.0%} — "
                 f"statistique NON CALCULABLE, ce qui n'est pas zéro",
        "formule": "statistics.median sur les valeurs d'état « mesuré » "
                   "uniquement ; inconnues et invalides EXCLUES, jamais "
                   "remplacées par zéro",
    }


def part_sans_transaction(valeurs: list) -> dict:
    """Part de séances à volume mesuré NUL — distincte de la part d'inconnus.

    ⚠️ La revue a demandé de ne pas présenter une part de valeurs inconnues
    comme une part de séances sans transaction. Les deux sont publiées
    séparément ; leur somme n'a pas de sens.
    """
    mesures_nulles = inconnus = invalides = mesures = 0
    for v in valeurs:
        etat, val = qualifier_volume(v)
        if etat is Volume.MESURE:
            mesures += 1
            if val == 0:
                mesures_nulles += 1
        elif etat is Volume.INCONNU:
            inconnus += 1
        else:
            invalides += 1
    total = max(len(valeurs), 1)
    return {
        "lignes": len(valeurs),
        "volume_mesure": mesures,
        "volume_mesure_nul": mesures_nulles,
        "volume_inconnu": inconnus,
        "volume_invalide": invalides,
        "part_mesure_nulle": round(mesures_nulles / mesures, 4) if mesures else None,
        "part_inconnue": round(inconnus / total, 4),
        "_reserve": "« volume mesuré nul » ne prouve pas l'absence de "
                    "transaction : il faut le statut de séance pour cela. "
                    "« inconnu » n'est pas « nul ».",
    }
