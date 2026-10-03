"""Figures chartistes et signaux d'indicateurs, détectés SANS regarder le futur.

⚠️ LA RÈGLE QUI REND LA MESURE HONNÊTE
Un sommet ou un creux n'existe qu'APRÈS coup : on ne sait qu'un cours était un
creux que lorsqu'il est remonté. Chaque pivot porte donc sa date de
CONFIRMATION, et une figure n'est utilisable qu'à partir de la confirmation de
son dernier pivot. Le signal est daté du jour de la CASSURE — la clôture qui
franchit le niveau de déclenchement — jamais du creux ou du sommet lui-même.

⚠️ PARAMÈTRES FIXÉS AVANT LA MESURE (03/10/2026), valeurs de manuel :
- pivots en zigzag sur les clôtures des séances ÉCHANGÉES, seuil 6 %
- une figure armée expire 40 séances après son dernier pivot (60 pour la
  tasse avec anse) ; elle est annulée si le cours franchit le niveau
  d'invalidation avant la cassure
- tolérances : creux / sommets « égaux » à 3 %, épaules à 5 %, côtés plats
  d'un triangle à 2 %, côtés montants ou descendants d'au moins 3 %

Chaque signal : (index de la séance dans la série échangée, nom, sens +1/−1).
"""
from __future__ import annotations

import numpy as np

SEUIL = 0.06
EXPIRE = 40


def pivots(c: np.ndarray, s: float = SEUIL) -> list[tuple]:
    """Zigzag : [(index, prix, 'H'|'L', index_de_confirmation), ...]."""
    out, n = [], len(c)
    if n < 3:
        return out
    tend, hi, lo, hi_i, lo_i = 0, c[0], c[0], 0, 0
    for i in range(1, n):
        x = c[i]
        if tend == 0:
            if x > hi:
                hi, hi_i = x, i
            if x < lo:
                lo, lo_i = x, i
            if x >= lo * (1 + s) and lo_i < i:
                out.append((lo_i, lo, "L", i)); tend, hi, hi_i = 1, x, i
            elif x <= hi * (1 - s) and hi_i < i:
                out.append((hi_i, hi, "H", i)); tend, lo, lo_i = -1, x, i
        elif tend == 1:
            if x > hi:
                hi, hi_i = x, i
            elif x <= hi * (1 - s):
                out.append((hi_i, hi, "H", i)); tend, lo, lo_i = -1, x, i
        else:
            if x < lo:
                lo, lo_i = x, i
            elif x >= lo * (1 + s):
                out.append((lo_i, lo, "L", i)); tend, hi, hi_i = 1, x, i
    return out


def _cassure(c, depuis, expire, haut=None, bas=None, invalide_sous=None,
             invalide_sur=None, niveau=None):
    """Première clôture qui franchit le niveau, avant expiration ou invalidation.
    `niveau(i)` rend un niveau variable (ligne de cou inclinée)."""
    for i in range(depuis, min(expire, len(c))):
        if invalide_sous is not None and c[i] < invalide_sous:
            return None
        if invalide_sur is not None and c[i] > invalide_sur:
            return None
        lvl = niveau(i) if niveau else None
        if haut is not None and c[i] > (lvl if lvl is not None else haut):
            return i
        if bas is not None and c[i] < (lvl if lvl is not None else bas):
            return i
    return None


def figures(c: np.ndarray) -> list[tuple]:
    """Figures chartistes sur une série de clôtures (séances échangées)."""
    P = pivots(c)
    sig = []
    for k in range(len(P)):
        conf = P[k][3]
        # ── Double creux / double sommet : X1, Y, X2 ──────────────────────
        if k >= 2:
            (i1, p1, t1, _), (iy, py, ty, _), (i2, p2, t2, _) = P[k - 2], P[k - 1], P[k]
            if 15 <= i2 - i1 <= 120 and abs(p2 / p1 - 1) <= 0.03:
                if t1 == "L" and py >= max(p1, p2) * 1.08:
                    j = _cassure(c, conf, i2 + EXPIRE, haut=py, invalide_sous=min(p1, p2) * 0.97)
                    if j is not None:
                        sig.append((j, "double_creux", +1))
                if t1 == "H" and py <= min(p1, p2) * 0.92:
                    j = _cassure(c, conf, i2 + EXPIRE, bas=py, invalide_sur=max(p1, p2) * 1.03)
                    if j is not None:
                        sig.append((j, "double_sommet", -1))
        # ── Épaule-tête-épaule (ETE) et ETE inversée : S1 N1 T N2 S2 ─────
        if k >= 4:
            (a, pa, ta, _), (n1, pn1, _, _), (h, ph, _, _), (n2, pn2, _, _), (b, pb, _, _) = P[k - 4:k + 1]
            if 20 <= b - a <= 200 and abs(pb / pa - 1) <= 0.05 and n2 > n1:
                cou = (lambda i, n1=n1, pn1=pn1, n2=n2, pn2=pn2:
                       pn1 + (pn2 - pn1) * (i - n1) / (n2 - n1))
                if ta == "L" and ph <= min(pa, pb) * 0.97:
                    j = _cassure(c, conf, b + EXPIRE, haut=1, invalide_sous=ph, niveau=cou)
                    if j is not None:
                        sig.append((j, "ete_inversee", +1))
                if ta == "H" and ph >= max(pa, pb) * 1.03:
                    j = _cassure(c, conf, b + EXPIRE, bas=1, invalide_sur=ph, niveau=cou)
                    if j is not None:
                        sig.append((j, "ete", -1))
        # ── Tasse avec anse : A (H), B (L), C (H) puis anse et cassure ────
        if k >= 2 and P[k][2] == "H":
            (ia, pa, ta, _), (ib, pb, _, _), (ic, pc, _, _) = P[k - 2], P[k - 1], P[k]
            prof = 1 - pb / pa
            if (ta == "H" and 0.12 <= prof <= 0.40 and abs(pc / pa - 1) <= 0.05
                    and 30 <= ic - ia <= 250 and 0.25 <= (ib - ia) / (ic - ia) <= 0.75):
                plafond = max(pa, pc)
                anse_max = min(0.15, prof / 2)
                j = _cassure(c, conf, ic + 60, haut=plafond,
                             invalide_sous=pc * (1 - anse_max))
                if j is not None:
                    sig.append((j, "tasse_anse", +1))
        # ── Triangles : quatre pivots alternés ────────────────────────────
        if k >= 3:
            q = P[k - 3:k + 1]
            hauts = [x for x in q if x[2] == "H"]
            bas_ = [x for x in q if x[2] == "L"]
            if len(hauts) == 2 and len(bas_) == 2 and q[-1][0] - q[0][0] >= 20:
                h1, h2 = hauts[0][1], hauts[1][1]
                l1, l2 = bas_[0][1], bas_[1][1]
                fin = q[-1][0] + EXPIRE
                if abs(h2 / h1 - 1) <= 0.02 and l2 >= l1 * 1.03:
                    j = _cassure(c, conf, fin, haut=max(h1, h2), invalide_sous=l2)
                    if j is not None:
                        sig.append((j, "triangle_ascendant", +1))
                elif abs(l2 / l1 - 1) <= 0.02 and h2 <= h1 * 0.97:
                    j = _cassure(c, conf, fin, bas=min(l1, l2), invalide_sur=h2)
                    if j is not None:
                        sig.append((j, "triangle_descendant", -1))
                elif h2 <= h1 * 0.97 and l2 >= l1 * 1.03:
                    j = _cassure(c, conf, fin, haut=h2, bas=l2)
                    if j is not None:
                        sig.append((j, "triangle_sym_haut" if c[j] > h2 else "triangle_sym_bas",
                                    +1 if c[j] > h2 else -1))
        # ── Fibonacci : rebond sur 38,2-61,8 % d'une jambe haussière ≥ 20 % ─
        if k >= 2 and P[k][2] == "L":
            (i0, p0, t0, _), (ih, phh, _, _), (il, pl, _, _) = P[k - 2], P[k - 1], P[k]
            if t0 == "L" and phh >= p0 * 1.20:
                r = (phh - pl) / (phh - p0)
                if 0.352 <= r <= 0.648:
                    sig.append((conf, "fibo_rebond_382_618", +1))
                elif r > 0.786:
                    sig.append((conf, "fibo_au_dela_786", -1))
    return sig


def _rsi(c: np.ndarray, p: int = 14) -> np.ndarray:
    d = np.diff(c, prepend=c[0])
    g, l_ = np.clip(d, 0, None), np.clip(-d, 0, None)
    ag, al = np.full(len(c), np.nan), np.full(len(c), np.nan)
    if len(c) <= p:
        return ag
    ag[p], al[p] = g[1:p + 1].mean(), l_[1:p + 1].mean()
    for i in range(p + 1, len(c)):
        ag[i] = (ag[i - 1] * (p - 1) + g[i]) / p
        al[i] = (al[i - 1] * (p - 1) + l_[i]) / p
    with np.errstate(divide="ignore", invalid="ignore"):
        return 100 - 100 / (1 + ag / al)


def _ema(x: np.ndarray, p: int) -> np.ndarray:
    a, out = 2 / (p + 1), np.empty(len(x))
    out[0] = x[0]
    for i in range(1, len(x)):
        out[i] = a * x[i] + (1 - a) * out[i - 1]
    return out


def indicateurs(c: np.ndarray) -> list[tuple]:
    """Signaux d'indicateurs classiques, sur les séances échangées."""
    n, sig = len(c), []
    if n < 60:
        return sig
    rsi = _rsi(c)
    ma50 = np.convolve(c, np.ones(50) / 50, "full")[:n]; ma50[:49] = np.nan
    ma200 = np.convolve(c, np.ones(200) / 200, "full")[:n]; ma200[:199] = np.nan
    macd = _ema(c, 12) - _ema(c, 26)
    signal = _ema(macd, 9)
    m20 = np.convolve(c, np.ones(20) / 20, "full")[:n]
    sd20 = np.array([c[max(0, i - 19):i + 1].std() if i >= 19 else np.nan for i in range(n)])
    larg = 4 * sd20 / m20
    for i in range(1, n):
        if not np.isnan(ma200[i - 1]):
            if ma50[i - 1] <= ma200[i - 1] and ma50[i] > ma200[i]:
                sig.append((i, "croisement_dore", +1))
            if ma50[i - 1] >= ma200[i - 1] and ma50[i] < ma200[i]:
                sig.append((i, "croisement_mortel", -1))
        if i >= 35 and macd[i - 1] <= signal[i - 1] and macd[i] > signal[i] and macd[i] < 0:
            sig.append((i, "macd_haussier_sous_zero", +1))
        if i >= 35 and macd[i - 1] >= signal[i - 1] and macd[i] < signal[i] and macd[i] > 0:
            sig.append((i, "macd_baissier_sur_zero", -1))
        if not np.isnan(rsi[i - 1]):
            if rsi[i - 1] < 30 <= rsi[i]:
                sig.append((i, "rsi_sortie_survente", +1))
            if rsi[i - 1] > 70 >= rsi[i]:
                sig.append((i, "rsi_sortie_surachat", -1))
        if i >= 250 and not np.isnan(larg[i - 1]):
            hist = larg[i - 250:i - 1]
            hist = hist[~np.isnan(hist)]
            if len(hist) > 100 and larg[i - 1] <= np.quantile(hist, 0.2):
                if c[i] > m20[i] + 2 * sd20[i]:
                    sig.append((i, "bollinger_compression_haut", +1))
                elif c[i] < m20[i] - 2 * sd20[i]:
                    sig.append((i, "bollinger_compression_bas", -1))
    # Divergences RSI, sur les pivots confirmés
    P = pivots(c)
    for k in range(2, len(P)):
        a, b = P[k - 2], P[k]
        if a[2] == b[2] and not np.isnan(rsi[a[0]]) and not np.isnan(rsi[b[0]]):
            if b[2] == "L" and b[1] < a[1] and rsi[b[0]] > rsi[a[0]] + 3:
                sig.append((b[3], "divergence_rsi_haussiere", +1))
            if b[2] == "H" and b[1] > a[1] and rsi[b[0]] < rsi[a[0]] - 3:
                sig.append((b[3], "divergence_rsi_baissiere", -1))
    return sig
