"""Règles « figures strictes » — FIXÉES LE 21/10/2026, AVANT TOUTE MESURE.

Pourquoi : Abd Moutalib a testé ADI et ADH et relayé une critique externe. Ce qui
tenait : une ETE asymétrique à ligne de cou inclinée était reconnue ; une
oblique n'était définie que par deux pivots, sans qu'aucune règle interdise à
une clôture de la traverser ; un triangle n'avait aucune règle de confinement ;
le volume n'était jamais regardé.

⚠️ CES RÈGLES NE SONT PAS RÉGLÉES SUR ADI NI SUR ADH. Elles viennent de la
critique, écrites avant d'avoir regardé ce qu'elles font aux fréquences. Elles
ne font que REJETER : toute figure acceptée ici l'était déjà sous les règles
précédentes (test de sous-ensemble dans `tests/test_figures_strictes.py`).

Deux jeux de règles coexistent, jamais fondus :
  REGLES_V1 = "2026-10-03"  les règles du banc d'essai initial, conservées
                            (fonctions `figures_v1` / `lignes_v1`, intactes) ;
  REGLES_V2 = "2026-10-21"  celles-ci. C'est le défaut.

LES RÈGLES (toutes en séances ÉCHANGÉES) :

1. ETE et ETE inversée, en plus des règles existantes —
   • symétrie temporelle : durée P1→P2 ÷ durée P2→P3 comprise entre 0,5 et 2
     (P1, P2, P3 : épaule gauche, tête, épaule droite) ;
   • ligne de cou : |T2/T1 − 1| ≤ 5 % (T1, T2 : les deux creux — ou sommets —
     intermédiaires). Pas d'angle en degrés : il dépend de l'échelle du graphique.

2. Triangles (ascendant, descendant, symétrique) — entre le premier pivot et la
   confirmation du dernier, au plus 2 clôtures hors des deux droites (haute par
   H1-H2, basse par L1-L2, prolongées), avec une tolérance de 1 %.

3. Obliques, et support d'un canal —
   • au moins 3 pivots du même type à moins de 1 % de la droite (les 2 qui la
     définissent, plus au moins 1) ;
   • aucune clôture au-delà de 1 % du MAUVAIS côté de la droite (au-dessus d'une
     résistance, au-dessous d'un support) entre le premier et le dernier contact.
   ⚠️ CAUSALITÉ : le pivot supplémentaire doit être CONFIRMÉ quand la droite
   devient exploitable — c'est-à-dire AVANT les deux pivots qui la définissent.
   Un contact qui n'arriverait qu'après ne ferait que redéfinir la droite sur
   d'autres pivots, et une droite « validée » par la suite aurait regardé le
   futur. Les pivots d'une même droite sont les pivots consécutifs de même
   type ; portée maximale : 250 séances, comme pour la droite elle-même.

4. Volume : AUCUN filtre. Le rapport entre le volume de la séance de cassure et
   la médiane des 20 séances échangées précédentes est publié À TITRE
   D'INFORMATION (`ratio_volume`), et mesuré dans le recalibrage (cassures à
   rapport ≥ 1,5 contre les autres). Rien n'est filtré sur cette base sans
   décision d'Abd.
"""
from __future__ import annotations

import numpy as np

REGLES_V1 = "2026-10-03"
REGLES_V2 = "2026-10-21"
REGLES = REGLES_V2

ETE_RATIO_MIN, ETE_RATIO_MAX = 0.5, 2.0
COU_MAX = 0.05
TRI_HORS_MAX = 2
TRI_TOL = 0.01
CONTACT_TOL = 0.01
MAUVAIS_COTE_TOL = 0.01
PORTEE_MAX = 250
VOLUME_FENETRE = 20
VOLUME_SEUIL_INFO = 1.5


def verifier(regles: str) -> str:
    if regles not in (REGLES_V1, REGLES_V2):
        raise ValueError(f"jeu de règles inconnu : {regles!r}")
    return regles


def droite(i1, p1, i2, p2):
    pente = (p2 - p1) / (i2 - i1)
    return lambda i: p1 + pente * (i - i1)


def ete_ok(a: int, h: int, b: int, pn1: float, pn2: float) -> bool:
    """Symétrie temporelle (a→h sur h→b) et ligne de cou quasi horizontale."""
    if b <= h or h <= a:
        return False
    ratio = (h - a) / (b - h)
    return ETE_RATIO_MIN <= ratio <= ETE_RATIO_MAX and abs(pn2 / pn1 - 1) <= COU_MAX


def triangle_confine(c: np.ndarray, hauts: list, bas: list, i0: int, conf: int) -> bool:
    """Au plus 2 clôtures hors des deux droites entre le premier pivot et `conf`.

    `hauts`, `bas` : les deux pivots (indice, prix, …) de chaque borne."""
    haute = droite(hauts[0][0], hauts[0][1], hauts[1][0], hauts[1][1])
    basse = droite(bas[0][0], bas[0][1], bas[1][0], bas[1][1])
    hors = 0
    for i in range(i0, min(conf, len(c) - 1) + 1):
        if c[i] > haute(i) * (1 + TRI_TOL) or c[i] < basse(i) * (1 - TRI_TOL):
            hors += 1
    return hors <= TRI_HORS_MAX


def droite_validee(c: np.ndarray, a: tuple, b: tuple, avant: list, cote: int) -> bool:
    """3 contacts au moins et aucune clôture au mauvais côté.

    `a`, `b` : (indice, prix, …) des deux pivots qui définissent la droite.
    `avant`  : pivots de même type confirmés AVANT `a` (voir causalité).
    `cote`   : +1 résistance (mauvais côté = au-dessus), −1 support (au-dessous)."""
    f = droite(a[0], a[1], b[0], b[1])
    contacts = [p for p in avant
                if b[0] - p[0] <= PORTEE_MAX and abs(p[1] / f(p[0]) - 1) <= CONTACT_TOL]
    if not contacts:
        return False
    premier = min(p[0] for p in contacts)
    for i in range(premier, b[0] + 1):
        if cote > 0 and c[i] > f(i) * (1 + MAUVAIS_COTE_TOL):
            return False
        if cote < 0 and c[i] < f(i) * (1 - MAUVAIS_COTE_TOL):
            return False
    return True


def ratio_volume(v, j: int):
    """Volume de la séance j ÷ médiane des 20 séances échangées précédentes.

    Information seulement — jamais un filtre. None si moins de 20 séances ou
    médiane nulle."""
    if v is None or j < VOLUME_FENETRE:
        return None
    m = float(np.median(v[j - VOLUME_FENETRE:j]))
    return None if m <= 0 else float(v[j]) / m
