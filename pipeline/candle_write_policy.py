"""Politique commune appliquée avant toute écriture de chandelles.

Ce module ne collecte rien et ne décide pas quelle source gagne. Il applique
uniquement les corrections déjà RÉCEPTIONNÉES, puis normalise le rapport pour
que tous les écrivains aient le même contrat.

But : une correction acceptée ne doit pas pouvoir être contournée par une
porte d'écriture secondaire.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

RACINE = Path(__file__).resolve().parent.parent
HISTORIQUES_IMPORTES = RACINE / "datasets" / "historiques_importes"

try:
    from .corrections_acceptees import appliquer
except ImportError:  # exécution directe depuis pipeline/
    from corrections_acceptees import appliquer

try:
    from bvc_config import SEANCES_ANNULEES, SEANCES_SANS_COTATION
except ImportError:
    SEANCES_ANNULEES = {}
    SEANCES_SANS_COTATION = {}


def fin_historique_importe(ticker: str, dossier: Path | None = None) -> str | None:
    """Dernière séance couverte par un historique réceptionné, si elle existe.

    Les anciens documents utilisent `periode`, les nouveaux `periode_source`.
    La fonction accepte les deux pour ne pas créer deux conventions.
    """
    f = (dossier or HISTORIQUES_IMPORTES) / f"{ticker}.json"
    if not f.exists():
        return None
    try:
        doc = json.loads(f.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if doc.get("ticker") != ticker:
        raise ValueError(f"{f.name} porte le ticker {doc.get('ticker')} : refus")
    periode = doc.get("periode_source") or doc.get("periode")
    if not isinstance(periode, list) or len(periode) != 2:
        return None
    return str(periode[1])[:10] or None


def appliquer_corrections_avant_ecriture(
    ticker: str, candles: list[dict[str, Any]]
) -> tuple[list[dict[str, Any]], dict]:
    """Réimpose les corrections reçues et rend un rapport au contrat stable.

    Un refus n'écrit rien par lui-même : l'appelant DOIT conserver le fichier
    existant. Cette séparation permet de tester la politique sans I/O.
    """
    annulees = set(SEANCES_ANNULEES)
    # ⚠️ Deux registres, une même conséquence sur la série, et deux causes
    # qu'il ne faut pas confondre : une séance ANNULÉE a été cotée puis effacée
    # par la Bourse ; une séance SANS COTATION n'a jamais eu lieu. Elles
    # sortent toutes deux des chandelles, et le rapport les distingue.
    sans_cotation = set(SEANCES_SANS_COTATION)
    a_retirer = annulees | sans_cotation
    retirees = [str(b.get("d") or "")[:10] for b in candles
                if str(b.get("d") or "")[:10] in annulees]
    jamais_ouvertes = [str(b.get("d") or "")[:10] for b in candles
                       if str(b.get("d") or "")[:10] in sans_cotation]
    valides = [b for b in candles
               if str(b.get("d") or "")[:10] not in a_retirer]

    corrigees, rapport = appliquer(ticker, valides)
    rapport = dict(rapport or {})
    rapport.setdefault("ticker", ticker)
    rapport.setdefault("corrections", 0)
    rapport.setdefault("deja_conformes", 0)
    rapport.setdefault("refus", [])
    rapport.setdefault("seances_absentes", [])
    rapport["seances_annulees_retirees"] = retirees
    rapport["seances_sans_cotation_retirees"] = jamais_ouvertes
    return corrigees, rapport
