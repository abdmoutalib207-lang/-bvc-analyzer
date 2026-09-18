"""Politique commune appliquée avant toute écriture de chandelles.

Ce module ne collecte rien et ne décide pas quelle source gagne. Il applique
uniquement les corrections déjà RÉCEPTIONNÉES, puis normalise le rapport pour
que tous les écrivains aient le même contrat.

But : une correction acceptée ne doit pas pouvoir être contournée par une
porte d'écriture secondaire.
"""
from __future__ import annotations

from typing import Any

try:
    from .corrections_acceptees import appliquer
except ImportError:  # exécution directe depuis pipeline/
    from corrections_acceptees import appliquer


def appliquer_corrections_avant_ecriture(
    ticker: str, candles: list[dict[str, Any]]
) -> tuple[list[dict[str, Any]], dict]:
    """Réimpose les corrections reçues et rend un rapport au contrat stable.

    Un refus n'écrit rien par lui-même : l'appelant DOIT conserver le fichier
    existant. Cette séparation permet de tester la politique sans I/O.
    """
    corrigees, rapport = appliquer(ticker, candles)
    rapport = dict(rapport or {})
    rapport.setdefault("ticker", ticker)
    rapport.setdefault("corrections", 0)
    rapport.setdefault("deja_conformes", 0)
    rapport.setdefault("refus", [])
    rapport.setdefault("seances_absentes", [])
    return corrigees, rapport
