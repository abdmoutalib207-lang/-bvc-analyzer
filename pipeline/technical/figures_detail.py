"""Figures, obliques, canaux et gaps AVEC LEUR GÉOMÉTRIE ET LEUR STATUT.

`figures.py` et `lignes.py` ne rendent que les SIGNAUX (le jour de la cassure) :
c'est ce que le banc d'essai du 03/10/2026 a mesuré. Pour PUBLIER une figure il
faut aussi ses pivots, son niveau de déclenchement et son statut — armée,
déclenchée, invalidée, expirée — y compris tant qu'elle n'a pas cassé.

⚠️ AUCUNE RÈGLE N'EST CHANGÉE. Les conditions de détection, les tolérances et
les paramètres (SEUIL, EXPIRE, 3 %, 5 %, 8 %…) sont ceux de `figures.py` et de
`lignes.py`, recopiés condition pour condition. Ce qui est ajouté, c'est ce
qu'elles jetaient : la figure armée, l'invalidée, l'expirée.

La preuve que rien n'a bougé n'est pas ce commentaire mais un test :
`tests/test_figures_publiees.py` vérifie, sur chacun des 80 titres, que les
figures DÉCLENCHÉES d'ici sont exactement les signaux de `figures()` et de
`lignes()` (même séance, même nom, même sens).

Tout est en INDICES de la série des séances échangées ; la conversion en dates
est faite par l'appelant. Aucun regard vers le futur : une figure n'existe qu'à
partir de la confirmation de son dernier pivot (`conf`), et son statut ne lit
que les clôtures postérieures à `conf`.
"""
from __future__ import annotations

import numpy as np

from technical.figures import EXPIRE, SEUIL, pivots

ARMEE, DECLENCHEE, INVALIDEE, EXPIREE = "armee", "declenchee", "invalidee", "expiree"


def _suivre(c, depuis, fin, haut=None, bas=None, invalide_sous=None,
            invalide_sur=None, niveau=None):
    """Même boucle que `figures._cassure`, mais qui dit POURQUOI elle s'arrête.

    Rend (statut, indice) ou None si la fenêtre est vide (la figure a expiré
    avant d'être confirmée : elle n'a jamais été armée, `_cassure` ne la
    voyait pas non plus). `fin` est exclusif, comme dans `_cassure`.
    """
    n = len(c)
    if depuis >= fin:
        return None
    for i in range(depuis, min(fin, n)):
        if invalide_sous is not None and c[i] < invalide_sous:
            return (INVALIDEE, i)
        if invalide_sur is not None and c[i] > invalide_sur:
            return (INVALIDEE, i)
        lvl = niveau(i) if niveau else None
        if haut is not None and c[i] > (lvl if lvl is not None else haut):
            return (DECLENCHEE, i)
        if bas is not None and c[i] < (lvl if lvl is not None else bas):
            return (DECLENCHEE, i)
    if fin <= n:
        return (EXPIREE, fin - 1)       # fenêtre épuisée : dernière séance couverte
    return (ARMEE, None)


def _fig(type_, orient, piv, conf, niveau, invalidation, suivi, signal=None, sens=0,
         niveau2=None):
    statut, i_fin = suivi
    return {"type": type_, "orientation": orient, "pivots": piv, "conf": conf,
            "niveau": niveau, "niveau_bas": niveau2, "invalidation": invalidation,
            "statut": statut, "i_fin": i_fin, "signal": signal, "sens": sens}


def figures_detail(c: np.ndarray, s: float = SEUIL, expire: int = EXPIRE) -> list[dict]:
    """Toutes les figures de `figures.figures`, déclenchées ou non."""
    P = pivots(c, s)
    out = []
    for k in range(len(P)):
        conf = P[k][3]
        # ── Double creux / double sommet ──────────────────────────────────
        if k >= 2:
            (i1, p1, t1, _), (iy, py, ty, _), (i2, p2, t2, _) = P[k - 2], P[k - 1], P[k]
            if 15 <= i2 - i1 <= 120 and abs(p2 / p1 - 1) <= 0.03:
                if t1 == "L" and py >= max(p1, p2) * 1.08:
                    inv = min(p1, p2) * 0.97
                    r = _suivre(c, conf, i2 + expire, haut=py, invalide_sous=inv)
                    if r:
                        out.append(_fig("double_creux", "haussiere", P[k - 2:k + 1], conf,
                                        {"forme": "horizontal", "prix": py},
                                        {"sous": inv}, r, "double_creux", +1))
                if t1 == "H" and py <= min(p1, p2) * 0.92:
                    inv = max(p1, p2) * 1.03
                    r = _suivre(c, conf, i2 + expire, bas=py, invalide_sur=inv)
                    if r:
                        out.append(_fig("double_sommet", "baissiere", P[k - 2:k + 1], conf,
                                        {"forme": "horizontal", "prix": py},
                                        {"sur": inv}, r, "double_sommet", -1))
        # ── Épaule-tête-épaule et inversée ────────────────────────────────
        if k >= 4:
            (a, pa, ta, _), (n1, pn1, _, _), (h, ph, _, _), (n2, pn2, _, _), (b, pb, _, _) = P[k - 4:k + 1]
            if 20 <= b - a <= 200 and abs(pb / pa - 1) <= 0.05 and n2 > n1:
                cou = (lambda i, n1=n1, pn1=pn1, n2=n2, pn2=pn2:
                       pn1 + (pn2 - pn1) * (i - n1) / (n2 - n1))
                niv = {"forme": "oblique", "points": [(n1, pn1), (n2, pn2)]}
                if ta == "L" and ph <= min(pa, pb) * 0.97:
                    r = _suivre(c, conf, b + expire, haut=1, invalide_sous=ph, niveau=cou)
                    if r:
                        out.append(_fig("ete_inversee", "haussiere", P[k - 4:k + 1], conf,
                                        niv, {"sous": ph}, r, "ete_inversee", +1))
                if ta == "H" and ph >= max(pa, pb) * 1.03:
                    r = _suivre(c, conf, b + expire, bas=1, invalide_sur=ph, niveau=cou)
                    if r:
                        out.append(_fig("ete", "baissiere", P[k - 4:k + 1], conf,
                                        niv, {"sur": ph}, r, "ete", -1))
        # ── Tasse avec anse ───────────────────────────────────────────────
        if k >= 2 and P[k][2] == "H":
            (ia, pa, ta, _), (ib, pb, _, _), (ic, pc, _, _) = P[k - 2], P[k - 1], P[k]
            prof = 1 - pb / pa
            if (ta == "H" and 0.12 <= prof <= 0.40 and abs(pc / pa - 1) <= 0.05
                    and 30 <= ic - ia <= 250 and 0.25 <= (ib - ia) / (ic - ia) <= 0.75):
                plafond = max(pa, pc)
                anse_max = min(0.15, prof / 2)
                inv = pc * (1 - anse_max)
                r = _suivre(c, conf, ic + 60, haut=plafond, invalide_sous=inv)
                if r:
                    out.append(_fig("tasse_anse", "haussiere", P[k - 2:k + 1], conf,
                                    {"forme": "horizontal", "prix": plafond},
                                    {"sous": inv}, r, "tasse_anse", +1))
        # ── Triangles ─────────────────────────────────────────────────────
        if k >= 3:
            q = P[k - 3:k + 1]
            hauts = [x for x in q if x[2] == "H"]
            bas_ = [x for x in q if x[2] == "L"]
            if len(hauts) == 2 and len(bas_) == 2 and q[-1][0] - q[0][0] >= 20:
                h1, h2 = hauts[0][1], hauts[1][1]
                l1, l2 = bas_[0][1], bas_[1][1]
                fin = q[-1][0] + expire
                if abs(h2 / h1 - 1) <= 0.02 and l2 >= l1 * 1.03:
                    r = _suivre(c, conf, fin, haut=max(h1, h2), invalide_sous=l2)
                    if r:
                        out.append(_fig("triangle_ascendant", "haussiere", q, conf,
                                        {"forme": "horizontal", "prix": max(h1, h2)},
                                        {"sous": l2}, r, "triangle_ascendant", +1))
                elif abs(l2 / l1 - 1) <= 0.02 and h2 <= h1 * 0.97:
                    r = _suivre(c, conf, fin, bas=min(l1, l2), invalide_sur=h2)
                    if r:
                        out.append(_fig("triangle_descendant", "baissiere", q, conf,
                                        {"forme": "horizontal", "prix": min(l1, l2)},
                                        {"sur": h2}, r, "triangle_descendant", -1))
                elif h2 <= h1 * 0.97 and l2 >= l1 * 1.03:
                    r = _suivre(c, conf, fin, haut=h2, bas=l2)
                    if r:
                        sig, sens = None, 0
                        if r[0] == DECLENCHEE:
                            haut_ = c[r[1]] > h2
                            sig = "triangle_sym_haut" if haut_ else "triangle_sym_bas"
                            sens = +1 if haut_ else -1
                        out.append(_fig("triangle_sym", "neutre", q, conf,
                                        {"forme": "horizontal", "prix": h2}, None, r,
                                        sig, sens, niveau2={"forme": "horizontal", "prix": l2}))
        # ── Fibonacci : fait constaté à la confirmation du second creux ───
        if k >= 2 and P[k][2] == "L":
            (i0, p0, t0, _), (ih, phh, _, _), (il, pl, _, _) = P[k - 2], P[k - 1], P[k]
            if t0 == "L" and phh >= p0 * 1.20:
                r = (phh - pl) / (phh - p0)
                nom = None
                if 0.352 <= r <= 0.648:
                    nom, sens, orient = "fibo_rebond_382_618", +1, "haussiere"
                elif r > 0.786:
                    nom, sens, orient = "fibo_au_dela_786", -1, "baissiere"
                if nom:
                    out.append(_fig(nom, orient, P[k - 2:k + 1], conf, None, None,
                                    (DECLENCHEE, conf), nom, sens))
    return out


def _droite(i1, p1, i2, p2):
    pente = (p2 - p1) / (i2 - i1)
    return lambda i: p1 + pente * (i - i1)


def lignes_detail(c: np.ndarray, s: float = SEUIL, expire: int = EXPIRE) -> list[dict]:
    """Toutes les obliques et canaux de `lignes.lignes`, déclenchés ou non.

    `points` : les deux pivots qui définissent la droite (indice, prix).
    Canal : `parallele` = (indice, prix) d'un point de la résistance, la
    parallèle au support passant par le sommet intermédiaire.
    """
    P = pivots(c, s)
    n, out = len(c), []
    hauts = [p for p in P if p[2] == "H"]
    bas = [p for p in P if p[2] == "L"]
    for a, b in zip(hauts, hauts[1:]):
        if b[1] < a[1] and 20 <= b[0] - a[0] <= 250:
            f = _droite(a[0], a[1], b[0], b[1])
            plancher = min((p[1] for p in bas if a[0] < p[0] < b[0]), default=None)
            r = _suivre(c, b[3], b[3] + expire, haut=1, invalide_sous=plancher, niveau=f)
            out.append({"type": "oblique_baissiere", "points": [(a[0], a[1]), (b[0], b[1])],
                        "conf": b[3], "droite": f, "statut": r[0], "i_fin": r[1],
                        "invalidation": {"sous": plancher} if plancher is not None else None,
                        "signal": "oblique_baissiere_cassee" if r[0] == DECLENCHEE else None,
                        "sens": +1 if r[0] == DECLENCHEE else 0})
    for a, b in zip(bas, bas[1:]):
        if b[1] > a[1] and 20 <= b[0] - a[0] <= 250:
            f = _droite(a[0], a[1], b[0], b[1])
            plafond = max((p[1] for p in hauts if a[0] < p[0] < b[0]), default=None)
            r = _suivre(c, b[3], b[3] + expire, bas=1, invalide_sur=plafond, niveau=f)
            out.append({"type": "oblique_haussiere", "points": [(a[0], a[1]), (b[0], b[1])],
                        "conf": b[3], "droite": f, "statut": r[0], "i_fin": r[1],
                        "invalidation": {"sur": plafond} if plafond is not None else None,
                        "signal": "oblique_haussiere_cassee" if r[0] == DECLENCHEE else None,
                        "sens": -1 if r[0] == DECLENCHEE else 0})
    for k in range(2, len(P)):
        l1, h, l2 = P[k - 2], P[k - 1], P[k]
        if not (l1[2] == "L" and h[2] == "H" and l2[2] == "L"):
            continue
        if not (l2[1] > l1[1] and 20 <= l2[0] - l1[0] <= 250):
            continue
        sup = _droite(l1[0], l1[1], l2[0], l2[1])
        touche, statut, i_fin, sig, sens = False, None, None, None, 0
        for i in range(l2[3], min(n, l2[3] + expire)):
            if c[i] < sup(i) * 0.98:
                statut, i_fin, sig, sens = DECLENCHEE, i, "canal_cassure_bas", -1
                break
            if c[i] <= sup(i) * 1.02:
                touche = True
            elif touche and c[i] >= sup(i) * 1.03:
                statut, i_fin, sig, sens = DECLENCHEE, i, "canal_rebond_support", +1
                break
        if statut is None:
            statut, i_fin = (EXPIREE, l2[3] + expire - 1) if l2[3] + expire <= n else (ARMEE, None)
        out.append({"type": "canal_haussier", "points": [(l1[0], l1[1]), (l2[0], l2[1])],
                    "parallele": (h[0], h[1]), "sommet": (h[0], h[1]),
                    "conf": l2[3], "droite": sup, "statut": statut, "i_fin": i_fin,
                    "invalidation": None, "signal": sig, "sens": sens})
    return out


def gaps_detail(o, h, l, c, rupture=frozenset(), plafond: float = 0.10) -> list[dict]:
    """Tous les gaps de `lignes.gaps` (≥ 1 %, deux séances à extrêmes réels),
    avec leur zone et la date de leur comblement.

    `rupture` : indices b tels qu'une opération sur titres / suspension tombe
    entre la séance b-1 et la séance b. Un gap n'est jamais publié à travers
    (R10, R11). `plafond` : un écart des extrêmes de plus de 10 % par rapport à
    la clôture de la veille est impossible sur un cours coté — ce n'est pas un
    gap mais une série cassée.

    Rend pour chaque gap : t (séance du gap), sens, bas/haut de la zone,
    i_touche (première séance qui revient DANS la zone), i_comble (première
    séance qui la traverse entièrement), interrompu (une rupture est survenue
    avant le comblement : le sort du gap n'est pas connaissable).
    """
    n = len(c)
    reel = ~((o == h) & (h == l) & (l == c))
    rup = sorted(rupture)
    out = []
    for t in range(1, n):
        if not (reel[t] and reel[t - 1]) or t in rupture:
            continue
        for sens in (+1, -1):
            if sens == +1:
                if not l[t] >= h[t - 1] * 1.01 or l[t] > c[t - 1] * (1 + plafond):
                    continue
                bas_z, haut_z = h[t - 1], l[t]
            else:
                if not h[t] <= l[t - 1] * 0.99 or h[t] < c[t - 1] * (1 - plafond):
                    continue
                haut_z, bas_z = l[t - 1], h[t]
            g = {"t": t, "sens": sens, "bas": float(bas_z), "haut": float(haut_z),
                 "i_touche": None, "i_comble": None, "interrompu": False,
                 "i_interruption": None}
            fin_rup = next((b for b in rup if b > t), None)
            for i in range(t + 1, n):
                if fin_rup is not None and i >= fin_rup:
                    g["interrompu"], g["i_interruption"] = True, i
                    break
                if sens == +1:
                    if g["i_touche"] is None and l[i] <= haut_z:
                        g["i_touche"] = i
                    if l[i] <= bas_z:
                        g["i_comble"] = i
                        break
                else:
                    if g["i_touche"] is None and h[i] >= bas_z:
                        g["i_touche"] = i
                    if h[i] >= haut_z:
                        g["i_comble"] = i
                        break
            out.append(g)
    return out
