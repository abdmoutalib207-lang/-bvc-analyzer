#!/usr/bin/env python3
"""Qualifier une FENÊTRE DATÉE pour un indicateur précis.

POURQUOI PAR FENÊTRE, ET NON PAR TITRE
──────────────────────────────────────
Une première version jugeait la série entière : un titre dont la provenance
n'était pas établie n'autorisait aucun calcul, nulle part. La revue externe a
demandé de pouvoir qualifier « une fenêtre datée, sans exiger de certifier
immédiatement tout l'historique d'un titre ». C'est ce que fait ce module.

POURQUOI PAR INDICATEUR
───────────────────────
« Une moyenne de clôtures n'exige pas toutes les colonnes OHLC. À l'inverse, un
indicateur utilisant les volumes doit vérifier leur disponibilité et leur
comparabilité. » Chaque indicateur déclare donc ses BESOINS, et la fenêtre
n'est jugée que sur ces champs-là.

LES TROIS ISSUES
────────────────
    REFUSE       valeurs invalides, ou anomalie non résolue dans la fenêtre
    EXPLORATOIRE valeurs exploitables, provenance ou ajustement incomplets
    QUALIFIE     tout est réuni pour l'usage demandé

⚠️ Un résultat EXPLORATOIRE n'alimente NI le signal officiel, NI une
probabilité, NI une performance présentée comme validée.
"""

from __future__ import annotations

import sys
from enum import Enum
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))
sys.path.insert(0, str(RACINE / "pipeline"))
from bvc_config import SPLITS  # noqa: E402
from qualification import COUVERTURE_MINIMALE  # noqa: E402


class Champ(str, Enum):
    OUVERTURE = "ouverture"
    PLUS_HAUT = "plus_haut"
    PLUS_BAS = "plus_bas"
    CLOTURE = "cloture"
    VOLUME = "volume"


# Ce dont chaque indicateur a RÉELLEMENT besoin. Rien de plus.
# ⚠️ Surdéclarer un besoin revient à refuser des calculs légitimes ; le
# sous-déclarer revient à calculer sur des champs absents. Les deux sont des
# fautes, et la seconde est pire.
BESOINS = {
    "sma":        {Champ.CLOTURE},
    "ema":        {Champ.CLOTURE},
    "rsi_wilder": {Champ.CLOTURE},
    "macd":       {Champ.CLOTURE},
    "bollinger":  {Champ.CLOTURE},
    "atr":        {Champ.PLUS_HAUT, Champ.PLUS_BAS, Champ.CLOTURE},
    "obv":        {Champ.CLOTURE, Champ.VOLUME},
    "volume_median": {Champ.VOLUME},
}


class Verdict(str, Enum):
    REFUSE = "refusé"
    EXPLORATOIRE = "exploratoire — signalé"
    QUALIFIE = "qualifié"


# Usages dont la présence sur une observation vaut provenance établie.
USAGE_PUBLIABLE = "indicateur"
USAGE_EXPLORATOIRE = "indicateur_exploratoire"


def _valeurs(obs: list, champ: Champ) -> list:
    return [o.get(champ.value) for o in obs]


# Usage dont la présence est exigée pour qu'un champ soit exploitable.
# ⚠️ Une valeur MESURÉE n'est pas une valeur UTILISABLE. Un volume peut être
# parfaitement lisible et rester incomparable dans le temps — c'est le cas de
# MNG avant sa division d'action. Une version antérieure ne regardait que
# l'état du champ et accordait donc une couverture de 100 % sur une fenêtre où
# 19 observations sur 29 refusaient l'usage du volume. Relevé par la revue.
USAGE_REQUIS = {
    Champ.VOLUME: "volume",
    Champ.OUVERTURE: "prix_analyse",
    Champ.PLUS_HAUT: "prix_analyse",
    Champ.PLUS_BAS: "prix_analyse",
    Champ.CLOTURE: "prix_analyse",
}


def operations_dans_la_fenetre(ticker: str, debut: str, fin: str) -> list:
    """Opérations DÉCLARÉES au registre dont la date d'effet tombe dedans.

    ⚠️ Une fenêtre qui enjambe une opération mêle deux bases de prix, même si
    chaque observation prise isolément est irréprochable. Le défaut ne se voit
    qu'à l'échelle de la fenêtre.

    ⚠️ Le registre recense ce que nous y avons inscrit : une fenêtre sans
    opération déclarée n'est PAS une fenêtre sans opération.
    """
    return [op for op in (SPLITS.get(ticker) or [])
            if (not debut or op["date"] > debut) and (not fin or op["date"] <= fin)]


def qualifier_fenetre(observations: list, indicateur: str,
                      debut: str = "", fin: str = "",
                      couverture_min: float = COUVERTURE_MINIMALE,
                      longueur_requise: int | None = None,
                      periode: int | None = None,
                      ticker: str = "") -> dict:
    """Cette fenêtre permet-elle de calculer cet indicateur, et à quel titre ?

    `observations` : les lignes de la couche normalisée (datasets/lot1b), qui
    portent déjà leurs statuts et leurs usages admissibles.
    """
    if indicateur not in BESOINS:
        raise ValueError(
            f"indicateur « {indicateur} » inconnu — déclarer ses besoins dans "
            f"BESOINS avant de l'utiliser. Connus : {sorted(BESOINS)}")
    besoins = BESOINS[indicateur]

    fen = [o for o in observations
           if (not debut or o["date"] >= debut) and (not fin or o["date"] <= fin)]
    n = len(fen)
    requis = longueur_requise if longueur_requise is not None else n
    motifs, couvertures = [], {}

    if n == 0:
        return {"indicateur": indicateur, "verdict": Verdict.REFUSE.value,
                "debut": debut, "fin": fin, "lignes": 0, "besoins": sorted(
                    c.value for c in besoins),
                "couvertures": {}, "motifs": ["fenêtre vide"],
                "observations_retenues": []}

    # ── 1. Les VALEURS sont-elles exploitables sur les champs requis ? ──────
    for champ in sorted(besoins, key=lambda c: c.value):
        usage = USAGE_REQUIS[champ]
        if champ is Champ.VOLUME:
            etats = [o.get("volume_etat") for o in fen]
        else:
            etats = [o.get("prix_etats", {}).get(champ.value) for o in fen]
        invalides = sum(1 for e in etats if e == "invalide")
        mesures = sum(1 for e in etats if e == "mesuré")
        # ⚠️ Exploitable = valeur mesurée ET usage accordé sur l'observation.
        ok = sum(1 for o, e in zip(fen, etats)
                 if e == "mesuré" and usage in o.get("admissible_pour", []))
        refuses = mesures - ok
        couvertures[champ.value] = {
            "exploitables": ok, "sur": n,
            "mesures": mesures,
            "mesures_mais_usage_refuse": refuses,
            "usage_requis": usage,
            "couverture": round(ok / max(requis, 1), 4),
            "invalides": invalides,
        }
        if invalides:
            motifs.append(f"{champ.value} : {invalides} valeur(s) invalide(s)")
        if refuses:
            motifs.append(
                f"{champ.value} : {refuses} observation(s) mesurée(s) mais dont "
                f"l'usage « {usage} » est refusé — une valeur lisible n'est pas "
                f"une valeur utilisable")
        if ok / max(requis, 1) < couverture_min:
            motifs.append(
                f"{champ.value} : couverture {ok / max(requis, 1):.0%} de la "
                f"longueur requise ({requis}) < {couverture_min:.0%}")

    # ── 2. La fenêtre traverse-t-elle une anomalie NON RÉSOLUE ? ────────────
    alertes = [o["date"] for o in fen
               if o.get("amplitude", {}).get("statut", "").startswith("hors enveloppe")]
    if alertes:
        motifs.append(
            f"la fenêtre traverse {len(alertes)} alerte(s) de cohérence non "
            f"résolue(s) : {', '.join(alertes[:5])}"
            + (" …" if len(alertes) > 5 else ""))

    # ── La fenêtre est-elle assez longue pour l'indicateur demandé ? ───────
    if periode is not None:
        if periode < 1:
            motifs.append(f"période demandée absurde : {periode}")
        elif n < periode:
            motifs.append(
                f"fenêtre de {n} observation(s) pour un indicateur de période "
                f"{periode} : aucun point ne peut être calculé")

    # ── La fenêtre enjambe-t-elle une opération sur titres déclarée ? ──────
    ops = operations_dans_la_fenetre(ticker, debut or (fen[0]["date"] if fen else ""),
                                     fin or (fen[-1]["date"] if fen else ""))
    if ops:
        motifs.append(
            "la fenêtre enjambe " + ", ".join(
                f"une opération déclarée le {o['date']} (ratio {o['ratio']})"
                for o in ops) +
            " : deux bases de prix s'y côtoient, même si chaque observation "
            "prise isolément est irréprochable")

    sans_usage = [o["date"] for o in fen if not o["admissible_pour"]]
    if sans_usage:
        motifs.append(
            f"{len(sans_usage)} observation(s) sans aucun usage admissible "
            f"dans la fenêtre")

    if motifs:
        return {"indicateur": indicateur, "verdict": Verdict.REFUSE.value,
                "debut": debut, "fin": fin, "lignes": n,
                "longueur_requise": requis,
                "besoins": sorted(c.value for c in besoins),
                "periode": periode, "operations_enjambees": ops,
                "couvertures": couvertures, "motifs": motifs,
                "observations_retenues": []}

    # ── 3. La PROVENANCE est-elle établie, ou seulement suffisante pour voir ?
    publiable = all(USAGE_PUBLIABLE in o["admissible_pour"] for o in fen)
    exploratoire = all(USAGE_EXPLORATOIRE in o["admissible_pour"] for o in fen)

    if publiable:
        verdict, note = Verdict.QUALIFIE, None
    elif exploratoire:
        verdict = Verdict.EXPLORATOIRE
        note = ("provenance ou ajustement incomplets sur au moins une "
                "observation de la fenêtre. ⚠️ RÉSULTAT EXPLORATOIRE : "
                "n'alimente NI le signal officiel, NI une probabilité, NI une "
                "performance présentée comme validée.")
    else:
        return {"indicateur": indicateur, "verdict": Verdict.REFUSE.value,
                "debut": debut, "fin": fin, "lignes": n,
                "longueur_requise": requis,
                "besoins": sorted(c.value for c in besoins),
                "couvertures": couvertures,
                "motifs": ["au moins une observation n'autorise même pas un "
                           "calcul exploratoire"],
                "observations_retenues": []}

    return {
        "indicateur": indicateur, "verdict": verdict.value,
        "debut": fen[0]["date"], "fin": fen[-1]["date"],
        "lignes": n, "longueur_requise": requis,
        "besoins": sorted(c.value for c in besoins),
        "periode": periode, "operations_enjambees": [],
        "couvertures": couvertures,
        "motifs": [], "reserve": note,
        "observations_retenues": [o["date"] for o in fen],
    }


def extraire(observations: list, champ: Champ, debut: str = "", fin: str = "") -> list:
    """Les valeurs d'un champ sur une fenêtre, dans l'ordre des dates.

    ⚠️ Ne remplace aucune valeur absente. Un `None` reste un `None` : c'est à
    l'appelant de refuser, jamais à l'extraction de combler.
    """
    fen = [o for o in observations
           if (not debut or o["date"] >= debut) and (not fin or o["date"] <= fin)]
    return _valeurs(fen, champ)
