#!/usr/bin/env python3
"""Le volume d'une séance est un NOMBRE DE TITRES. Jamais autre chose.

⚠️ POURQUOI CE MODULE EXISTE
────────────────────────────
Le recoupement des 27 exports de l'opérateur, le 23/09/2026, a trouvé
**13 636 séances** où notre volume était un montant en dirhams et
**3 019 séances** où il valait le COURS. Les deux causes étaient dans le code,
écrites en toutes lettres, et aucune n'était une erreur d'inattention : chacune
paraissait raisonnable à l'endroit où elle a été écrite.

**Cause n°1 — la mauvaise colonne, préférée à la bonne.**
La source publie DEUX colonnes : un montant échangé (« Volume », « Volume
(MAD) », `volumeGlobal`) et un nombre de titres (« Titres Échangés »,
« Quantité échangée », `cumulTitresEchanges`). Une table de correspondance
faisait de la première le `volume` et reléguait la seconde en repli :

    "volume":            "volume",
    "quantite echangee": "_qty",     # fallback volume

Le repli n'était donc jamais atteint. ATW le 22/09 : 23 343 966,70 dirhams
échangés pour **33 778 titres** — nous publiions le premier nombre.

Ailleurs, un `elif "vol" in colonne` produisait le même effet sans table :
« Volume (MAD) » contient « vol », « Titres Échangés » non.

**Cause n°2 — le cours versé dans le volume quand la colonne manque.**

    for col in ["high", "low", "open", "volume"]:
        if col not in df.columns:
            df[col] = df["close"]

Pour `high`, `low` et `open`, c'est juste : une séance sans extrêmes connus est
une bougie plate, et la clôture est la meilleure valeur disponible. Pour
`volume`, **il n'y a pas de continuité à assurer** : le cours n'est pas une
approximation d'un nombre de titres, c'est une grandeur sans rapport. D'où
CDM à `v = 700` pour un titre qui cote 700,00, sur 131 séances.

⚠️ CE QUE LE DÉFAUT N°2 RENDAIT INVISIBLE
Une séance SANS ÉCHANGE devenait une séance échangée, et son volume suivait
mécaniquement son cours. Tout indicateur de liquidité bâti là-dessus mesurait
le prix en croyant mesurer l'activité.

⚠️ LA RÈGLE, ET SON UNIQUE EXCEPTION
Un volume inconnu vaut **0**, et 0 se lit « nous ne savons pas qu'il y a eu des
échanges » — pas « il n'y en a pas eu ». C'est moins que l'idéal (un `None`
dirait mieux la chose) mais c'est ce que le format des chandelles accepte, et
c'est surtout la seule valeur qui **ne ment pas sur l'ordre de grandeur**.
"""

from __future__ import annotations

import re
import unicodedata

# Un en-tête qui désigne un NOMBRE DE TITRES. Ordre indifférent : on exige la
# correspondance entière du motif, pas une inclusion, pour qu'aucune de ces
# formes n'attrape « volume » au passage.
_TITRES = (
    "titres echanges",
    "quantite echangee",
    "quantites echangees",
    "cumultitresechanges",
    "nombre de titres",
    "qty",
    "quantity",
    "shares traded",
    "volume titres",
)

# Un en-tête qui désigne un MONTANT en dirhams. Reconnu explicitement pour
# pouvoir le REFUSER en connaissance de cause, au lieu de le laisser passer
# faute de l'avoir prévu.
_MONTANTS = (
    "volume mad",
    "volume dh",
    "volume dhs",
    "volumeglobal",
    "volume global",
    "montant",
    "capitaux",
    "turnover",
    "valeur echangee",
)


def _normaliser(entete: str) -> str:
    """Un en-tête comparable : sans accents, sans ponctuation, en minuscules.

    « Volume (MAD) » → « volume mad » ; « Titres Échangés » → « titres
    echanges ». Sans cette normalisation, chaque source imposerait sa
    graphie et la table se remplirait de variantes.
    """
    sans_accent = unicodedata.normalize("NFD", str(entete)) \
        .encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", " ", sans_accent.lower()).strip()


def designe_des_titres(entete: str) -> bool:
    """Cet en-tête annonce-t-il un nombre de titres ?"""
    return _normaliser(entete) in _TITRES


def designe_un_montant(entete: str) -> bool:
    """Cet en-tête annonce-t-il un montant échangé ?

    ⚠️ « volume » tout court en fait partie **en pratique** chez cette source :
    l'API de la Bourse nomme ainsi `volumeGlobal`, un montant. Mais d'autres
    fournisseurs appellent « volume » un nombre de titres, et le refuser
    partout viderait leurs séries. Il est donc traité à part — voir
    `choisir_colonne()`, qui ne le retient qu'à défaut de mieux.
    """
    return _normaliser(entete) in _MONTANTS


def choisir_colonne(entetes) -> str | None:
    """L'en-tête à retenir comme volume, ou None s'il n'y en a aucun.

    ⚠️ L'ORDRE EST LA CORRECTION. Une colonne de titres l'emporte TOUJOURS sur
    une colonne de montants, quelle que soit sa position dans le fichier.
    C'est l'inverse exact de ce que faisait la table précédente.

    « volume » seul n'est retenu qu'en dernier ressort : chez cette source il
    désigne un montant, mais chez d'autres un nombre de titres, et le refuser
    sans distinction viderait leurs séries. Quand une colonne de titres existe,
    la question ne se pose pas.
    """
    entetes = list(entetes)
    for e in entetes:
        if designe_des_titres(e):
            return e
    for e in entetes:
        if _normaliser(e) == "volume":
            return e
    for e in entetes:
        # Un montant reconnu comme tel : accepté faute de mieux, mais c'est le
        # cas où la série mérite d'être recoupée avec un export officiel.
        if designe_un_montant(e):
            return e
    return None


def volume_inconnu() -> int:
    """Ce qu'on écrit quand la source ne dit rien du volume.

    ⚠️ Zéro, et JAMAIS le cours. Le point entier de ce module tient dans cette
    fonction d'une ligne : elle existe pour qu'on ne puisse pas réécrire
    `df["volume"] = df["close"]` sans s'en rendre compte.
    """
    return 0
