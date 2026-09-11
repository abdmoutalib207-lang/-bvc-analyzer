#!/usr/bin/env python3
"""Socle mathématique des indicateurs techniques — lot 2.

CE QUE CE MODULE EST
────────────────────
Des fonctions PURES. Elles reçoivent des listes de nombres et rendent des
listes de nombres. Elles ne lisent aucun fichier, ne connaissent aucun titre,
et ne décident pas si un calcul est légitime — cette question appartient à
`pipeline/fenetre.py`.

TROIS RÈGLES QUI NE SE NÉGOCIENT PAS
────────────────────────────────────
1. **Aucune valeur absente n'est comblée.** Un `None` en entrée produit un
   `None` en sortie sur toute fenêtre qui le contient. Jamais un zéro, jamais
   une interpolation, jamais la dernière valeur connue. Une série trouée qu'on
   rebouche devient une série lisse qui ment.

2. **La longueur de sortie égale la longueur d'entrée.** Les premières
   positions, où la fenêtre n'est pas encore pleine, valent `None`. Décaler
   silencieusement une série d'indicateur par rapport à ses dates est la faute
   classique — et invisible.

3. **Aucune performance n'est calculée ici.** Ce module produit des nombres,
   pas des signaux, pas des probabilités, pas des rendements.

⚠️ SUR TA-LIB
Absente de l'environnement, et ce n'est pas un obstacle : ces formules sont
publiques et courtes. Le filtrage réseau n'est pas contourné.

⚠️ SUR LES SÉRIES CONSTRUITES
Les séries fabriquées pour tester ces fonctions servent EXCLUSIVEMENT aux
tests mathématiques. Elles ne doivent jamais réapparaître comme historique de
marché dans un résultat de performance. Elles portent pour cela le préfixe
`SERIE_CONSTRUITE_`, et un test vérifie qu'aucune ne se trouve sous `datasets/`.
"""

from __future__ import annotations

import math

PREFIXE_SERIE_CONSTRUITE = "SERIE_CONSTRUITE_"


def _exploitable(v) -> bool:
    return (isinstance(v, (int, float)) and not isinstance(v, bool)
            and math.isfinite(v))


def _fenetre_pleine(valeurs: list, i: int, n: int) -> list | None:
    """Les n valeurs finissant en i, ou None si l'une manque.

    ⚠️ C'est ici que la règle « on ne comble rien » est appliquée, une fois,
    pour tout le module.
    """
    if i + 1 < n:
        return None
    bloc = valeurs[i + 1 - n:i + 1]
    return bloc if all(_exploitable(v) for v in bloc) else None


def sma(valeurs: list, n: int) -> list:
    """Moyenne mobile simple. Besoins : la clôture seule."""
    if n < 1:
        raise ValueError("n doit valoir au moins 1")
    out = []
    for i in range(len(valeurs)):
        bloc = _fenetre_pleine(valeurs, i, n)
        out.append(sum(bloc) / n if bloc else None)
    return out


def ema(valeurs: list, n: int) -> list:
    """Moyenne mobile exponentielle, amorcée par la SMA des n premiers points.

    Coefficient k = 2 / (n + 1). L'amorçage par la SMA est la convention la
    plus répandue ; elle est déclarée ici parce qu'elle n'est pas unique — un
    amorçage sur la première valeur donnerait des nombres différents.

    ⚠️ Une valeur absente APRÈS l'amorçage interrompt le lissage : la sortie
    repasse à None et l'EMA se ré-amorce dès qu'une fenêtre pleine réapparaît.
    Reporter la moyenne par-dessus le trou reviendrait à inventer.
    """
    if n < 1:
        raise ValueError("n doit valoir au moins 1")
    k = 2.0 / (n + 1.0)
    out, precedent = [], None
    for i, v in enumerate(valeurs):
        if not _exploitable(v):
            out.append(None)
            precedent = None
            continue
        if precedent is None:
            bloc = _fenetre_pleine(valeurs, i, n)
            if bloc is None:
                out.append(None)
                continue
            precedent = sum(bloc) / n
        else:
            precedent = v * k + precedent * (1.0 - k)
        out.append(precedent)
    return out


def rsi_wilder(cloture: list, n: int = 14) -> list:
    """RSI de Wilder. Besoins : la clôture seule.

    Lissage de Wilder : après l'amorçage par la moyenne arithmétique des n
    premières variations, `moyenne = (précédente × (n − 1) + courante) / n`.

    Deux cas limites, qui découlent de la définition et non du code :
      · aucune baisse sur la fenêtre → RS infini → RSI = 100
      · aucune hausse sur la fenêtre → RS nul   → RSI = 0
    """
    if n < 1:
        raise ValueError("n doit valoir au moins 1")
    out = [None] * len(cloture)
    gains, pertes = [None] * len(cloture), [None] * len(cloture)
    for i in range(1, len(cloture)):
        a, b = cloture[i - 1], cloture[i]
        if _exploitable(a) and _exploitable(b):
            d = b - a
            gains[i], pertes[i] = max(d, 0.0), max(-d, 0.0)

    mg = mp = None
    for i in range(len(cloture)):
        if gains[i] is None:
            mg = mp = None                       # le lissage est rompu
            continue
        if mg is None:
            bloc_g = _fenetre_pleine(gains, i, n)
            bloc_p = _fenetre_pleine(pertes, i, n)
            if bloc_g is None or bloc_p is None:
                continue
            mg, mp = sum(bloc_g) / n, sum(bloc_p) / n
        else:
            mg = (mg * (n - 1) + gains[i]) / n
            mp = (mp * (n - 1) + pertes[i]) / n
        if mp == 0:
            out[i] = 100.0 if mg > 0 else 50.0   # ni hausse ni baisse : neutre
        elif mg == 0:
            out[i] = 0.0
        else:
            out[i] = 100.0 - 100.0 / (1.0 + mg / mp)
    return out


def macd(cloture: list, court: int = 12, long: int = 26, signal: int = 9) -> dict:
    """MACD. Besoins : la clôture seule.

    Rend les trois séries séparément — `ligne`, `signal`, `histogramme` —
    parce que les confondre est une source d'erreur fréquente.
    """
    if not 0 < court < long:
        raise ValueError("il faut 0 < court < long")
    ec, el = ema(cloture, court), ema(cloture, long)
    ligne = [(a - b) if (a is not None and b is not None) else None
             for a, b in zip(ec, el)]
    sig = ema(ligne, signal)
    hist = [(a - b) if (a is not None and b is not None) else None
            for a, b in zip(ligne, sig)]
    return {"ligne": ligne, "signal": sig, "histogramme": hist}


def bollinger(cloture: list, n: int = 20, k: float = 2.0) -> dict:
    """Bandes de Bollinger. Besoins : la clôture seule.

    ⚠️ Écart-type de POPULATION (division par n), convention usuelle pour cet
    indicateur. L'écart-type d'échantillon (division par n − 1) donnerait des
    bandes plus larges ; le choix est déclaré ici pour qu'il soit discutable.
    """
    milieu = sma(cloture, n)
    haute, basse, ecarts = [], [], []
    for i in range(len(cloture)):
        bloc = _fenetre_pleine(cloture, i, n)
        if bloc is None or milieu[i] is None:
            haute.append(None), basse.append(None), ecarts.append(None)
            continue
        m = milieu[i]
        et = math.sqrt(sum((v - m) ** 2 for v in bloc) / n)
        ecarts.append(et)
        haute.append(m + k * et)
        basse.append(m - k * et)
    return {"milieu": milieu, "haute": haute, "basse": basse,
            "ecart_type": ecarts, "_convention": "écart-type de population (÷ n)"}


def atr(plus_haut: list, plus_bas: list, cloture: list, n: int = 14) -> list:
    """ATR de Wilder. Besoins : plus-haut, plus-bas ET clôture.

    Le « true range » du jour i vaut le maximum de :
      h − l · |h − clôture de la veille| · |l − clôture de la veille|
    """
    if not (len(plus_haut) == len(plus_bas) == len(cloture)):
        raise ValueError("les trois séries doivent avoir la même longueur")
    tr = [None] * len(cloture)
    for i in range(len(cloture)):
        h, l = plus_haut[i], plus_bas[i]
        if not (_exploitable(h) and _exploitable(l)):
            continue
        if i == 0:
            tr[i] = h - l
            continue
        cv = cloture[i - 1]
        tr[i] = (h - l) if not _exploitable(cv) else max(
            h - l, abs(h - cv), abs(l - cv))

    out, precedent = [None] * len(cloture), None
    for i in range(len(cloture)):
        if tr[i] is None:
            precedent = None
            continue
        if precedent is None:
            bloc = _fenetre_pleine(tr, i, n)
            if bloc is None:
                continue
            precedent = sum(bloc) / n
        else:
            precedent = (precedent * (n - 1) + tr[i]) / n
        out[i] = precedent
    return out


def obv(cloture: list, volume: list) -> list:
    """On-Balance Volume. Besoins : clôture ET volume.

    ⚠️ Cet indicateur cumule des QUANTITÉS. Il n'a de sens que si les volumes
    sont comparables d'un bout à l'autre de la fenêtre — ce que la couche de
    qualification doit établir AVANT l'appel, jamais ici.
    """
    if len(cloture) != len(volume):
        raise ValueError("les deux séries doivent avoir la même longueur")
    out, cumul = [], None
    for i in range(len(cloture)):
        if not (_exploitable(cloture[i]) and _exploitable(volume[i])):
            out.append(None)
            cumul = None                         # le cumul est rompu
            continue
        if i == 0 or cumul is None or not _exploitable(cloture[i - 1]):
            cumul = 0.0
        elif cloture[i] > cloture[i - 1]:
            cumul += volume[i]
        elif cloture[i] < cloture[i - 1]:
            cumul -= volume[i]
        out.append(cumul)
    return out
