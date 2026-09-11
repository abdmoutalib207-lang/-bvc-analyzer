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
from contamination import fenetre_contaminee  # noqa: E402
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


# ⚠️ Longueur minimale RÉELLE, indicateur par indicateur.
# Une version antérieure comparait la fenêtre à la seule « période » demandée.
# C'est faux pour deux d'entre eux, et la revue l'a mesuré :
#   · le RSI travaille sur les VARIATIONS : n variations exigent n+1 clôtures ;
#   · le MACD ne sort son signal qu'après `long + signal − 1` observations.
# Exiger trop refuse un calcul possible ; exiger trop peu annonce un calcul qui
# ne produira rien. Les deux trompent le lecteur.
def longueur_minimale(indicateur: str, periode: int | None,
                      macd_params: tuple = (12, 26, 9)) -> int | None:
    if indicateur == "macd":
        _, long, signal = macd_params
        return long + signal - 1
    if periode is None:
        return None
    if indicateur == "rsi_wilder":
        return periode + 1          # n variations ⇒ n+1 clôtures
    if indicateur == "obv":
        return 1
    return periode


def _registre_operations() -> dict:
    """Les opérations, quelle que soit la table où elles ont été inscrites.

    ⚠️ DÉFAUT CORRIGÉ : ce contrôle ne consultait que `SPLITS`, tandis que HPS
    était documenté dans `operations_titres.json`. Il rendait donc une liste
    vide pour octobre 2023 — l'opération la mieux établie du projet passait
    inaperçue. Deux registres, un seul contrôle : il faut lire les deux.
    """
    ops: dict = {}
    for t, entrees in (SPLITS or {}).items():
        for e in entrees:
            ops.setdefault(t, []).append({
                "date_effet": e["date"], "ratio": e.get("ratio"),
                "registre": "SPLITS", "traitement": None})

    f = RACINE / "pipeline" / "operations_titres.json"
    if f.exists():
        import json
        reg = json.loads(f.read_text(encoding="utf-8")).get("operations", {})
        for t, entrees in reg.items():
            for e in entrees:
                d = e.get("date_effet")
                if not d:
                    continue
                deja = [o for o in ops.get(t, []) if o["date_effet"] == d]
                tr = e.get("traitement_dans_notre_serie")
                if deja:
                    deja[0]["traitement"] = tr
                    deja[0]["registre"] += " + operations_titres"
                else:
                    ops.setdefault(t, []).append({
                        "date_effet": d, "ratio": e.get("ratio"),
                        "registre": "operations_titres", "traitement": tr})
    return ops


def raccordement_etabli(op: dict) -> bool:
    """Le passage de l'opération est-il correctement raccordé dans NOTRE série ?

    ⚠️ Une opération traversée ne signifie PAS deux bases incompatibles — la
    revue l'a rappelé. Un historique correctement ajusté reste comparable de
    part et d'autre. Ce qui doit refuser un calcul, c'est un raccordement NON
    ÉTABLI ou INCOHÉRENT, pas la simple présence d'une date dans la fenêtre.
    """
    tr = op.get("traitement")
    return bool(tr) and tr.get("niveau", "").startswith("ajustement documenté")


def operations_dans_la_fenetre(ticker: str, debut: str, fin: str) -> list:
    """Opérations déclarées — dans l'UN OU L'AUTRE registre — tombant dedans.

    ⚠️ Les registres recensent ce que nous y avons inscrit : une fenêtre sans
    opération déclarée n'est PAS une fenêtre sans opération.
    """
    return [op for op in (_registre_operations().get(ticker) or [])
            if (not debut or op["date_effet"] > debut)
            and (not fin or op["date_effet"] <= fin)]


def qualifier_fenetre(observations: list, indicateur: str,
                      debut: str = "", fin: str = "",
                      couverture_min: float = COUVERTURE_MINIMALE,
                      longueur_requise: int | None = None,
                      periode: int | None = None,
                      ticker: str = "",
                      macd_params: tuple = (12, 26, 9)) -> dict:
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
    minimum = longueur_minimale(indicateur, periode, macd_params)
    if periode is not None and periode < 1:
        motifs.append(f"période demandée absurde : {periode}")
    elif minimum is not None and n < minimum:
        motifs.append(
            f"fenêtre de {n} observation(s) pour un {indicateur} qui en exige "
            f"{minimum} : aucun point ne peut être calculé")

    # ── Le raccordement d'une opération traversée est-il établi ? ──────────
    ops = operations_dans_la_fenetre(ticker, debut or (fen[0]["date"] if fen else ""),
                                     fin or (fen[-1]["date"] if fen else ""))
    non_raccordees = [o for o in ops if not raccordement_etabli(o)]
    if non_raccordees:
        motifs.append(
            "la fenêtre enjambe " + ", ".join(
                f"l'opération du {o['date_effet']} (ratio {o['ratio']}, "
                f"registre {o['registre']})" for o in non_raccordees) +
            " dont le RACCORDEMENT n'est pas établi dans notre série. "
            "⚠️ Ce n'est pas la traversée qui refuse — un historique "
            "correctement ajusté resterait comparable ; c'est l'absence de "
            "preuve que le raccordement l'est.")

    # ── La fenêtre recouvre-t-elle une contamination entre entreprises ? ──
    # ⚠️ Une valeur peut être parfaitement formée et appartenir à une AUTRE
    # société. Aucun contrôle numérique ne le voit ; seul le registre le sait.
    contamine = fenetre_contaminee(ticker, debut or (fen[0]["date"] if fen else ""),
                                   fin or (fen[-1]["date"] if fen else ""))
    for c in contamine:
        autre = c["suspect"] or "une autre société"
        motifs.append(
            f"la fenêtre recouvre une contamination ({c['niveau']}) : {ticker} "
            f"pourrait y porter les cours de {autre}, du {c['debut_seance']} "
            f"au {c['fin_seance']}. ⚠️ Les valeurs y sont bien formées — c'est "
            f"leur APPARTENANCE qui est en cause, et aucun contrôle numérique "
            f"ne la voit.")

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
                "periode": periode, "longueur_minimale": minimum,
                "operations_enjambees": ops,
                "operations_non_raccordees": non_raccordees,
                "contaminations": contamine,
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
        "periode": periode, "longueur_minimale": minimum,
        "operations_enjambees": ops, "operations_non_raccordees": [],
        "contaminations": [],
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
