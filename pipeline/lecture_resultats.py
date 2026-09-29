#!/usr/bin/env python3
"""Lire un résultat semestriel dans le texte d'un dépôt AMMC — sans deviner.

⚠️ LE PROBLÈME QUE CE MODULE RÉSOUT
───────────────────────────────────
Dans un communiqué, la ligne

    Résultat net part du Groupe 3 778 380 3 397

se lit de plusieurs façons : l'espace sépare les milliers ET les colonnes.
« 3 778 | 380 | 3 397 », « 3 778 380 | 3 397 », « 3 | 778 380 | 3 397 »…
Une expression régulière qui choisit la première lecture venue se trompe
une fois sur trois, et se trompe EN SILENCE.

⚠️ LA RÈGLE : L'ÉMETTEUR TRANCHE LUI-MÊME
Presque toutes ces lignes portent leur propre contrôle : une variation en
pourcentage (« +10 % ») ou en valeur (« 3 397 »). Une lecture n'est retenue
que si elle est COHÉRENTE avec ce contrôle : 3 778 − 380 = 3 398 ≈ 3 397.
Sans contrôle sur la ligne, elle n'est retenue que si elle est la SEULE
lecture plausible. Sinon : aucune réponse. « Je ne sais pas » vaut mieux
qu'un chiffre faux, qui se retient quand l'avertissement s'oublie.

⚠️ LES UNITÉS SE DÉDUISENT DU MARCHÉ, PAS DE LA MISE EN PAGE
Un même document mélange MDH, milliers et dirhams. On ramène chaque lecture
en MDH en choisissant l'unité qui donne un résultat semestriel plausible
pour la capitalisation du titre — entre 0,05 % et 50 % de celle-ci.

Ce module ne fait que LIRE. Il n'écrit rien : c'est `controles_resultats`
qui décide si une lecture peut entrer dans les fondamentaux.
"""

from __future__ import annotations

import math
import re
from itertools import combinations

# Libellés, du plus précis au plus large. Le premier qui donne une lecture
# cohérente l'emporte ; `base` dit ce qui a été lu.
LIBELLES_RESULTAT = [
    (r"r[ée]sultat net\s*[-–(]?\s*part du groupe\)?", "RNPG"),
    (r"\bRNPG\b", "RNPG"),
    (r"r[ée]sultat net revenant [àa] la soci[ée]t[ée] m[èe]re", "RNPG"),
    (r"r[ée]sultat net(?: de l'ensemble)? consolid[ée]", "résultat net consolidé"),
    (r"r[ée]sultat net\b", "résultat net"),
]
LIBELLES_CA = [
    (r"chiffre d.affaires consolid[ée]", "CA consolidé"),
    (r"produit net bancaire", "PNB"),
    (r"produits des activit[ée]s ordinaires", "produits des activités ordinaires"),
    (r"chiffre d.affaires", "CA"),
]

_POURCENT = re.compile(r"([+\-−]?\s?\d{1,4}(?:[.,]\d+)?)\s?%")
# Un « morceau » : chiffres avec éventuellement un signe et une partie décimale.
_MORCEAU = re.compile(r"^[+\-−(]?\d[\d.,]*\)?$")


def _normaliser_morceau(m: str) -> str:
    return m.replace("−", "-").replace("(", "-").replace(")", "")


def _valeur_pointee(m: str) -> float | None:
    """« 125.379.902,14 » ou « 199.562 » : le point sépare les milliers."""
    m = _normaliser_morceau(m)
    if re.fullmatch(r"-?\d{1,3}(\.\d{3})+(,\d+)?", m):
        return float(m.replace(".", "").replace(",", "."))
    return None


def segmentations(morceaux: list[str]) -> list[list[float]]:
    """Toutes les façons de regrouper des morceaux en nombres.

    Un nombre = un premier morceau de 1 à 3 chiffres (signé éventuellement),
    suivi de morceaux d'exactement 3 chiffres ; le dernier peut porter une
    décimale (« 809,88 »). Un morceau déjà pointé (« 125.379.902,14 ») est un
    nombre à lui seul.
    """
    n = len(morceaux)
    out: list[list[float]] = []

    def pousser(i: int, acc: list[float]):
        if i == n:
            out.append(list(acc))
            return
        m = _normaliser_morceau(morceaux[i])
        pv = _valeur_pointee(m)
        if pv is not None and ("." in m):
            pousser(i + 1, acc + [pv])
            return
        if not re.fullmatch(r"-?\d{1,3}(,\d+)?", m) and not re.fullmatch(r"-?\d+,\d+", m):
            return
        signe = -1 if m.startswith("-") else 1
        tete = m.lstrip("-")
        if "," in tete:                         # nombre complet, décimal
            pousser(i + 1, acc + [signe * float(tete.replace(",", "."))])
            return
        chiffres = tete
        j = i
        while True:
            pousser(j + 1, acc + [signe * float(chiffres)])
            if j + 1 >= n:
                break
            suiv = _normaliser_morceau(morceaux[j + 1])
            if re.fullmatch(r"\d{3}", suiv):
                chiffres += suiv
                j += 1
                continue
            if re.fullmatch(r"\d{3},\d+", suiv):
                pousser(j + 2, acc + [signe * float(chiffres + suiv.replace(",", "."))])
            break

    pousser(0, [])
    return out


def _pourcentage(texte: str) -> float | None:
    m = _POURCENT.search(texte)
    if not m:
        return None
    v = m.group(1).replace(" ", "").replace("−", "-").replace(",", ".")
    try:
        return float(v)
    except ValueError:
        return None


def lire_ligne(ligne: str, motif: str) -> tuple[float, float] | None:
    """(N, N−1) lus sur UNE ligne après le libellé, ou None si ambigu."""
    m = re.search(motif, ligne, flags=re.I)
    if not m:
        return None
    reste = ligne[m.end():]
    pct = _pourcentage(reste)
    sup_100 = bool(re.search(r">\s*100\s*%", reste))
    # ⚠️ Le pourcentage est lu À PART, puis retiré : « 793 739 +7,3% » ne doit
    # pas faire de « +7,3 » une troisième colonne de montants.
    reste = re.sub(r">\s*100\s*%", " ", reste)
    reste = _POURCENT.sub(" ", reste)
    # Les morceaux numériques consécutifs qui suivent le libellé.
    morceaux = []
    for tok in reste.replace("%", " % ").split():
        if tok in ("%", ">", "<"):
            break
        if _MORCEAU.match(tok):
            morceaux.append(tok)
        elif morceaux:
            break
    if len(morceaux) < 2:
        return None
    candidats = []
    for seg in segmentations(morceaux):
        if len(seg) < 2:
            continue
        n, n1 = seg[0], seg[1]
        if n1 == 0:
            continue
        coherent = False
        if len(seg) >= 3:
            ecart = seg[2]
            # la troisième colonne est une variation en valeur…
            if abs((n - n1) - ecart) <= max(2.0, 0.01 * abs(ecart)):
                coherent = True
            # …ou en pourcentage écrit sans « % »
            elif n1 > 0 and abs((n / n1 - 1) * 100 - ecart) <= 1.5:
                coherent = True
        if pct is not None and n1 > 0 and abs((n / n1 - 1) * 100 - pct) <= 1.5:
            coherent = True
        if sup_100 and n1 > 0 and n / n1 > 2:
            coherent = True
        if coherent:
            candidats.append((n, n1, True))
        elif len(seg) == 2 and pct is None and not sup_100:
            candidats.append((n, n1, False))
    surs = {(a, b) for a, b, ok in candidats if ok}
    if len(surs) == 1:
        return surs.pop()
    if surs:
        return None
    # Aucune lecture contrôlée : on n'accepte qu'une lecture UNIQUE et
    # plausible (les deux colonnes dans un rapport de 1 à 20).
    plausibles = {(a, b) for a, b, _ in candidats
                  if b and 0.05 <= abs(a / b) <= 20}
    return plausibles.pop() if len(plausibles) == 1 else None


_PROSE = re.compile(
    r"(?:à|a|de)\s+(-?[\d  ]+(?:[.,]\d+)?)\s*(M\s?DH|MMAD|M MAD|millions? de dirhams|MDh|Mdh)"
    r"[^.;]{0,80}?(?:contre|comparé à|vs\.?|par rapport à)\s+(-?[\d  ]+(?:[.,]\d+)?)\s*"
    r"(?:M\s?DH|MMAD|M MAD|millions? de dirhams|MDh|Mdh)", re.I)


def lire_prose(texte: str, motif: str) -> tuple[float, float] | None:
    """« Le RNPG ressort à 333 MDh, comparé à 387 MDh » — la phrase porte ses
    deux montants et leur unité, sans ambiguïté de colonnes."""
    plat = " ".join(texte.split())
    for m in re.finditer(motif, plat, flags=re.I):
        # ⚠️ LA PHRASE, PAS LE PARAGRAPHE. Relevé sur Risma le 29/09 : sans
        # cette borne, « RNPG Juin 2026 » allait chercher ses deux montants
        # dans la phrase suivante — celle de l'ENDETTEMENT NET, 1 029 contre
        # 1 968 MDH. Une lecture fausse, cohérente, et invisible.
        suite = re.split(r"(?<=[a-zé%)])\.\s|[›•▪]", plat[m.end(): m.end() + 220])[0]
        p = _PROSE.search(suite)
        if not p:
            continue
        try:
            n = float(p.group(1).replace(" ", "").replace("\u202f", "").replace(",", "."))
            n1 = float(p.group(3).replace(" ", "").replace("\u202f", "").replace(",", "."))
        except ValueError:
            continue
        return n, n1
    return None


def en_mdh(valeur: float, cap_mdh: float | None) -> float | None:
    """Ramène une valeur en MDH en choisissant l'unité plausible.

    Un résultat SEMESTRIEL vaut entre 0,05 % et 50 % de la capitalisation.
    Une seule unité doit tomber dans cette fenêtre, sinon : None.
    """
    if not cap_mdh:
        return None
    ok = [valeur * u for u in (1.0, 1e-3, 1e-6)
          if 0.0005 <= abs(valeur * u) / cap_mdh <= 0.5]
    return ok[0] if len(ok) == 1 else None


def lire(texte: str, cap_mdh: float | None) -> dict:
    """Le résultat et le chiffre d'affaires semestriels, avec leur base.

    Renvoie {"resultat": (N, N−1) en MDH | None, "base": …, "ca": …,
    "lectures": nombre de lignes concordantes}. Plusieurs lignes qui donnent
    la même lecture la renforcent ; deux lectures contradictoires l'annulent.
    """
    lignes = [l.strip() for l in texte.splitlines() if l.strip()]
    res: dict = {"resultat": None, "base": None, "ca": None, "lectures": 0}
    for motif, base in LIBELLES_RESULTAT:
        vus = []
        for l in lignes:
            lu = lire_ligne(l, motif)
            if lu is None:
                continue
            a, b = en_mdh(lu[0], cap_mdh), en_mdh(lu[1], cap_mdh)
            if a is None or b is None:
                continue
            vus.append((round(a, 1), round(b, 1)))
        if not vus:
            # Rien dans les tableaux : la phrase du communiqué, déjà en MDH.
            pr = lire_prose(texte, motif)
            if pr and en_mdh(pr[0], cap_mdh) == pr[0]:
                res["resultat"], res["base"], res["lectures"] = (round(pr[0], 1), round(pr[1], 1)), base, 1
                break
            continue
        distincts = set(vus)
        # ⚠️ Deux lectures différentes pour le même libellé : le bilan porte
        # la colonne 31/12, le compte de résultat la colonne 30/06 de l'année
        # précédente. On retient la lecture MAJORITAIRE, et seulement si
        # elle l'est strictement.
        comptes = sorted(((vus.count(v), v) for v in distincts), reverse=True)
        if len(comptes) > 1 and comptes[0][0] == comptes[1][0]:
            continue
        res["resultat"], res["base"], res["lectures"] = comptes[0][1], base, comptes[0][0]
        break
    for motif, base in LIBELLES_CA:
        for l in lignes:
            lu = lire_ligne(l, motif)
            if lu is None:
                continue
            # Le chiffre d'affaires est comparé à la capitalisation avec une
            # fenêtre plus large : une distribution peut dépasser sa valeur.
            conv = [(lu[0] * u, lu[1] * u) for u in (1.0, 1e-3, 1e-6)
                    if cap_mdh and 0.001 <= abs(lu[0] * u) / cap_mdh <= 5]
            if len(conv) == 1:
                res["ca"] = (round(conv[0][0], 1), round(conv[0][1], 1))
                res["base_ca"] = base
                break
        if res["ca"]:
            break
    return res
