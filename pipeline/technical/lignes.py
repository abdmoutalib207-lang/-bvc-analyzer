"""Obliques, canaux et gaps — détectés SANS regarder le futur.

⚠️ DEUX JEUX DE RÈGLES (21/10/2026) : `lignes(c, regles=...)`. "2026-10-03" = les
règles d'origine ci-dessous (fonction archivée `lignes_v1`, intacte) ;
"2026-10-21" (défaut) exige en plus 3 contacts et aucune clôture au mauvais
côté de la droite — voir `technical/regles_strictes.py`. Les gaps ne changent pas.

⚠️ RÈGLES FIXÉES LE 03/10/2026, AVANT LA MESURE (demande d'Abd Moutalib,
captures RDS et ADI à l'appui : oblique mensuelle cassée puis pullback, canal
hebdomadaire, comblement de gap).

Pivots : zigzag de `figures.pivots`, datés de leur CONFIRMATION.

  oblique_baissiere_cassee (+1)   deux sommets descendants H1 > H2, écartés de
      20 à 250 séances ; la ligne qui les joint est prolongée ; signal à la
      première clôture AU-DESSUS de la ligne, après confirmation de H2 et dans
      les `expire` séances ; annulé si le cours passe sous le dernier creux.
  oblique_haussiere_cassee (−1)   miroir : deux creux montants, clôture SOUS
      la ligne.
  canal_rebond_support (+1)       deux creux montants L1 < L2 encadrant un
      sommet H ; support = droite (L1, L2), résistance = parallèle par H.
      Après confirmation de L2 : le cours revient à moins de 2 % du support,
      puis clôture au moins 3 % au-dessus — signal à cette clôture. Annulé si
      une clôture passe 2 % sous le support (c'est alors la cassure).
  canal_cassure_bas (−1)          dans le même canal, clôture 2 % sous le
      support.
  gap_haussier_rebond (+1)        ouverture au-dessus du plus haut de la
      veille d'au moins 1 % (séances à extrêmes réels : pas de bougie plate) ;
      dans les 60 séances, le cours revient dans la zone du gap [plus haut de
      la veille, plus bas du jour du gap] SANS clôturer 2 % sous elle, puis
      clôture 3 % au-dessus du haut de zone — signal à cette clôture.
  gap_baissier_rejet (−1)         miroir.
"""
from __future__ import annotations

import numpy as np

from technical.figures import EXPIRE, SEUIL, pivots


def _droite(i1, p1, i2, p2):
    pente = (p2 - p1) / (i2 - i1)
    return lambda i: p1 + pente * (i - i1)


def lignes_v1(c: np.ndarray, s: float = SEUIL, expire: int = EXPIRE) -> list[tuple]:
    """ARCHIVE — règles du 03/10/2026, conservées telles quelles (regles="2026-10-03")."""
    P = pivots(c, s)
    sig, n = [], len(c)
    hauts = [p for p in P if p[2] == "H"]
    bas = [p for p in P if p[2] == "L"]
    # ── Obliques ─────────────────────────────────────────────────────────
    for a, b in zip(hauts, hauts[1:]):
        if b[1] < a[1] and 20 <= b[0] - a[0] <= 250:
            f = _droite(a[0], a[1], b[0], b[1])
            plancher = min((p[1] for p in bas if a[0] < p[0] < b[0]), default=None)
            for i in range(b[3], min(n, b[3] + expire)):
                if plancher is not None and c[i] < plancher:
                    break
                if c[i] > f(i):
                    sig.append((i, "oblique_baissiere_cassee", +1))
                    break
    for a, b in zip(bas, bas[1:]):
        if b[1] > a[1] and 20 <= b[0] - a[0] <= 250:
            f = _droite(a[0], a[1], b[0], b[1])
            plafond = max((p[1] for p in hauts if a[0] < p[0] < b[0]), default=None)
            for i in range(b[3], min(n, b[3] + expire)):
                if plafond is not None and c[i] > plafond:
                    break
                if c[i] < f(i):
                    sig.append((i, "oblique_haussiere_cassee", -1))
                    break
    # ── Canaux haussiers ─────────────────────────────────────────────────
    for k in range(2, len(P)):
        l1, h, l2 = P[k - 2], P[k - 1], P[k]
        if not (l1[2] == "L" and h[2] == "H" and l2[2] == "L"):
            continue
        if not (l2[1] > l1[1] and 20 <= l2[0] - l1[0] <= 250):
            continue
        sup = _droite(l1[0], l1[1], l2[0], l2[1])
        touche = False
        for i in range(l2[3], min(n, l2[3] + expire)):
            if c[i] < sup(i) * 0.98:
                sig.append((i, "canal_cassure_bas", -1))
                break
            if c[i] <= sup(i) * 1.02:
                touche = True
            elif touche and c[i] >= sup(i) * 1.03:
                sig.append((i, "canal_rebond_support", +1))
                break
    return sig


def lignes(c: np.ndarray, s: float = SEUIL, expire: int = EXPIRE,
           regles: str | None = None) -> list[tuple]:
    """Obliques et canaux ; `regles` choisit le jeu de règles (défaut : le plus récent).

    "2026-10-03" : règles d'origine (= `lignes_v1`). "2026-10-21" : les mêmes plus
    3 contacts au moins et aucune clôture au mauvais côté (voir
    `technical/regles_strictes.py`). Ces règles ne font que REJETER."""
    from technical import regles_strictes as rs
    regles = rs.verifier(regles or rs.REGLES)
    if regles == rs.REGLES_V1:
        return lignes_v1(c, s, expire)
    P = pivots(c, s)
    sig, n = [], len(c)
    hauts = [p for p in P if p[2] == "H"]
    bas = [p for p in P if p[2] == "L"]
    # ── Obliques ─────────────────────────────────────────────────────────
    for m, (a, b) in enumerate(zip(hauts, hauts[1:])):
        if b[1] < a[1] and 20 <= b[0] - a[0] <= 250 and rs.droite_validee(c, a, b, hauts[:m], +1):
            f = _droite(a[0], a[1], b[0], b[1])
            plancher = min((p[1] for p in bas if a[0] < p[0] < b[0]), default=None)
            for i in range(b[3], min(n, b[3] + expire)):
                if plancher is not None and c[i] < plancher:
                    break
                if c[i] > f(i):
                    sig.append((i, "oblique_baissiere_cassee", +1))
                    break
    for m, (a, b) in enumerate(zip(bas, bas[1:])):
        if b[1] > a[1] and 20 <= b[0] - a[0] <= 250 and rs.droite_validee(c, a, b, bas[:m], -1):
            f = _droite(a[0], a[1], b[0], b[1])
            plafond = max((p[1] for p in hauts if a[0] < p[0] < b[0]), default=None)
            for i in range(b[3], min(n, b[3] + expire)):
                if plafond is not None and c[i] > plafond:
                    break
                if c[i] < f(i):
                    sig.append((i, "oblique_haussiere_cassee", -1))
                    break
    # ── Canaux haussiers (support validé) ────────────────────────────────
    for k in range(2, len(P)):
        l1, h, l2 = P[k - 2], P[k - 1], P[k]
        if not (l1[2] == "L" and h[2] == "H" and l2[2] == "L"):
            continue
        if not (l2[1] > l1[1] and 20 <= l2[0] - l1[0] <= 250):
            continue
        if not rs.droite_validee(c, l1, l2, [p for p in P[:k - 2] if p[2] == "L"], -1):
            continue
        sup = _droite(l1[0], l1[1], l2[0], l2[1])
        touche = False
        for i in range(l2[3], min(n, l2[3] + expire)):
            if c[i] < sup(i) * 0.98:
                sig.append((i, "canal_cassure_bas", -1))
                break
            if c[i] <= sup(i) * 1.02:
                touche = True
            elif touche and c[i] >= sup(i) * 1.03:
                sig.append((i, "canal_rebond_support", +1))
                break
    return sig


def gaps(o: np.ndarray, h: np.ndarray, l: np.ndarray, c: np.ndarray, fenetre: int = 60) -> list[tuple]:
    sig, n = [], len(c)
    reel = ~((o == h) & (h == l) & (l == c))
    for t in range(1, n):
        if not (reel[t] and reel[t - 1]):
            continue
        if l[t] >= h[t - 1] * 1.01:                     # gap haussier
            bas_z, haut_z = h[t - 1], l[t]
            dedans = False
            for i in range(t + 1, min(n, t + 1 + fenetre)):
                if c[i] < bas_z * 0.98:
                    break
                if l[i] <= haut_z:
                    dedans = True
                elif dedans and c[i] >= haut_z * 1.03:
                    sig.append((i, "gap_haussier_rebond", +1))
                    break
        if h[t] <= l[t - 1] * 0.99:                     # gap baissier
            haut_z, bas_z = l[t - 1], h[t]
            dedans = False
            for i in range(t + 1, min(n, t + 1 + fenetre)):
                if c[i] > haut_z * 1.02:
                    break
                if h[i] >= bas_z:
                    dedans = True
                elif dedans and c[i] <= bas_z * 0.97:
                    sig.append((i, "gap_baissier_rejet", -1))
                    break
    return sig
