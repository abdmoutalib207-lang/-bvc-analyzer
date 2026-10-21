"""Séries de séances ÉCHANGÉES, nettoyées avant toute détection.

Garde-fous, tous antérieurs à la détection (jamais appliqués après coup sur un
résultat) :

1. Seules les séances à volume > 0 entrent. Une séance à volume nul est un
   report de cours (ou une bougie plate réparée : `o = h = l = c`, `v = 0`),
   pas une transaction ; un pivot ou un gap bâti dessus est fabriqué.
2. Une RUPTURE entre deux séances échangées consécutives est :
   - un écart de clôture de plus de 10 % (R10 : un cours coté ne bouge pas de
     plus de 10 % en une séance — donc opération sur titres ou donnée fausse,
     jamais un mouvement) ;
   - ou une opération DÉCLARÉE tombant entre les deux dates : split
     (`bvc_config.SPLITS`), suspension ou reprise (`SUSPENSIONS`). R11 : une
     opération se constate sur pièce ; ici on la CONSULTE, on ne la déduit pas.
   Aucune figure ni aucun gap ne traverse une rupture.
3. On ne lit que ce que les chandelles contiennent : aucune séance inventée.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

PLAFOND = 0.10


def evenements_titre(ticker: str) -> list[str]:
    """Dates (AAAA-MM-JJ) des opérations déclarées au registre pour ce titre."""
    import bvc_config as cfg
    dates = [e["date"] for e in cfg.SPLITS.get(ticker, [])]
    for e in cfg.SUSPENSIONS.get(ticker, []):
        dates += [e[k] for k in ("depuis", "reprise") if e.get(k)]
    return sorted(set(dates))


def charger(chemin: Path, fin: str | None = None) -> dict | None:
    """Séances échangées d'un fichier de chandelles, ou None si illisible/vide.

    Rend dates (`d`), o, h, l, c, v (numpy) et `montant` : médiane glissante sur
    60 lignes du montant échangé (c × v), min 10 séances échangées — la
    définition exacte du banc d'essai (`calibrage_figures.py`), calculée sur
    TOUTES les lignes puis restreinte aux séances échangées.
    """
    try:
        b = json.loads(chemin.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if fin is not None:
        b = [x for x in b if x["d"] <= fin]
    if not b:
        return None
    df = pd.DataFrame(b).sort_values("d").reset_index(drop=True)
    df["v"] = df["v"].fillna(0)
    c = df["c"].astype(float)
    montant = (c * df["v"]).where(df["v"] > 0).rolling(60, min_periods=10).median()
    ech = df["v"] > 0
    df, montant = df[ech], montant[ech]
    if df.empty:
        return None
    return {"d": df["d"].tolist(), "o": df["o"].astype(float).values,
            "h": df["h"].astype(float).values, "l": df["l"].astype(float).values,
            "c": df["c"].astype(float).values, "v": df["v"].astype(float).values,
            "montant": montant.values}


def ruptures(dates: list[str], c: np.ndarray, declares: list[str]) -> set[int]:
    """Indices b tels qu'une rupture sépare la séance b-1 de la séance b."""
    rup = set()
    for b in range(1, len(c)):
        if abs(c[b] / c[b - 1] - 1) > PLAFOND:
            rup.add(b)
        if any(dates[b - 1] < e <= dates[b] for e in declares):
            rup.add(b)
    return rup


def traverse(rup: set[int], i0: int, i1: int) -> bool:
    """Vrai si une rupture tombe entre les séances i0 et i1 (i0 < b <= i1)."""
    return any(i0 < b <= i1 for b in rup)
