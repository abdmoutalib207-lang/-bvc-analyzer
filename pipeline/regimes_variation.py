#!/usr/bin/env python3
"""Amplitude d'une séance — ce qu'elle mesure, et ce qu'elle ne prouve pas.

CE QUE CE MODULE A CESSÉ DE PRÉTENDRE
─────────────────────────────────────
Une version antérieure répondait « conforme » et écrivait « licite sous tous
les régimes connus ». C'était un verdict réglementaire rendu par une fonction
qui n'en a pas les moyens. La revue externe l'a démontré par un contre-exemple :

    cours de référence 100 · ouverture et plus-bas 200 · plus-haut 201 · clôture 200

Le rapport plus-haut / plus-bas vaut 1,005 : amplitude minuscule, donc
« conforme ». Sous une limite de ±20 % autour de 100, ces prix sont pourtant
tous hors bornes. **La fonction ne reçoit pas le cours de référence : elle ne
peut pas voir où se situent les prix, seulement de combien ils s'écartent entre
eux.**

Second défaut de portée, d'ampleur plus grande encore : la source citée n'entre
en vigueur qu'au 23/06/2026, et **3 999 de nos 4 306 observations lui sont
antérieures** — 93 %. L'étiquette réglementaire était apposée sur des données
que le texte invoqué ne couvre pas.

LES DEUX QUESTIONS, MAINTENANT SÉPARÉES
───────────────────────────────────────
  1. AMPLITUDE  — de combien les prix s'écartent-ils ENTRE EUX dans la séance ?
                  Calculable à partir de la seule bougie. C'est ce que fait
                  `evaluer_amplitude`, et rien de plus.

  2. CONFORMITÉ — les prix respectent-ils la limite autour du COURS DE
                  RÉFÉRENCE ? Exige la référence, le régime et sa période de
                  validité. C'est `evaluer_conformite`, qui répond « non
                  vérifiable » tant qu'il lui manque une de ces trois pièces.

Une amplitude compatible avec l'enveloppe testée **ne vaut pas** conformité.
Un test de comportement l'interdit explicitement.

CE QUE L'ALERTE D'AMPLITUDE EXTRÊME AFFIRME, ET CE QU'ELLE N'AFFIRME PAS
────────────────────────────────────────────────────────────────────────
Elle affirme : les prix de cette bougie s'écartent entre eux au-delà de tout ce
que l'enveloppe testée admet. C'est un constat de **cohérence de donnée**.

Elle n'affirme NI que la bougie est illégale, NI ce qui l'a produite. Elle vaut
donc quelle que soit la période — elle ne s'appuie sur aucun texte.
"""

from __future__ import annotations

from enum import Enum

# ── État de la connaissance sur les seuils ──────────────────────────────────
#
# ⚠️ NIVEAU DE PREUVE : relayées par la revue externe, NON vérifiées par nous
# sur le texte original. Le dépôt ne conserve aucune copie de la circulaire.
SOURCE_SEUILS = {
    "reference": "circulaire AMMC du 25/06/2026",
    "relaye_par": "revue externe, message de réception du lot 1B",
    "verifie_sur_source_primaire": False,
    "ce_qui_manque": "copie de la circulaire, ou renvoi à l'article précis du "
                     "règlement général de la Bourse de Casablanca",
    "en_vigueur_depuis": "2026-06-23",
    "en_vigueur_jusqu_a": None,
    "_portee": "⚠️ 93 % de nos observations sont antérieures au 23/06/2026. "
               "Le régime qui leur était applicable n'est pas établi.",
}

REGIMES = {
    "continu": {"limite": 0.10, "libelle": "±10 % — cotation en continu",
                "source": SOURCE_SEUILS},
    "fixing": {"limite": 0.06, "libelle": "±6 % — cotation au fixing",
               "source": SOURCE_SEUILS},
    "admission_cinq_premieres_seances": {
        "limite": 0.20,
        "libelle": "±20 % — cinq premières séances suivant l'admission",
        "source": SOURCE_SEUILS},
}


def borne_amplitude(limite: float) -> float:
    """Écart maximal plus-haut / plus-bas sous une limite symétrique ±s.

    `h ≤ (1 + s) × réf` et `l ≥ (1 − s) × réf`, donc `h / l ≤ (1+s)/(1−s)`.

    ⚠️ C'est une condition NÉCESSAIRE, jamais suffisante. Deux prix peuvent
    respecter cet écart tout en étant l'un et l'autre hors des bornes — il
    suffit qu'ils soient tous deux du même côté, loin de la référence. C'est
    exactement le contre-exemple de la revue.
    """
    return (1.0 + limite) / (1.0 - limite)


# ⚠️ TOLÉRANCE RELATIVE. `borne_amplitude(0.20)` vaut 1.4999999999999998 quand
# une bougie h=120, l=80 donne exactement 1.5 : sans tolérance, une bougie pile
# à la limite ressortait en alerte. Le dépassement doit être franc.
EPS = 1e-9


def depasse(rapport: float, borne: float) -> bool:
    """Dépassement FRANC. À la limite exacte, il n'y a pas excès."""
    return rapport > borne * (1.0 + EPS)


ENVELOPPE_LA_PLUS_ETROITE = min(borne_amplitude(r["limite"]) for r in REGIMES.values())
ENVELOPPE_LA_PLUS_LARGE = max(borne_amplitude(r["limite"]) for r in REGIMES.values())


class Amplitude(str, Enum):
    """⚠️ Aucun de ces états n'est un verdict de conformité réglementaire."""

    COMPATIBLE = "compatible avec l'enveloppe testée"
    INDETERMINE = "enveloppe non concluante"
    HORS_ENVELOPPE = "hors enveloppe testée — alerte de cohérence"
    NON_EVALUABLE = "non évaluable"


class Conformite(str, Enum):
    CONFORME = "conforme au régime déclaré"
    NON_CONFORME = "hors bornes du régime déclaré"
    NON_VERIFIABLE = "non vérifiable — pièces manquantes"


# Régime applicable, titre par titre et période par période.
# ⚠️ VIDE À DESSEIN : nous ne disposons ni des modes de cotation ni des dates
# d'admission. Une entrée inventée rendrait le contrôle concluant à tort.
REGIME_PAR_TITRE: dict = {}


def regime_applicable(ticker: str, date_iso: str):
    for periode in REGIME_PAR_TITRE.get(ticker, []):
        if periode["du"] <= date_iso <= (periode.get("au") or "9999-12-31"):
            return periode["regime"]
    return None


def source_couvre(date_iso: str) -> bool:
    """La source des seuils couvre-t-elle cette date ?

    ⚠️ Une règle n'a pas d'effet rétroactif. Appliquer une circulaire du
    25/06/2026 à une séance de 2023 est une extrapolation, pas une vérification.
    """
    if not date_iso:
        return False
    debut = SOURCE_SEUILS["en_vigueur_depuis"]
    fin = SOURCE_SEUILS["en_vigueur_jusqu_a"] or "9999-12-31"
    return debut <= date_iso <= fin


def evaluer_amplitude(bougie: dict, ticker: str = "", date_iso: str = "") -> dict:
    """Écart des prix ENTRE EUX dans la séance. Ne conclut RIEN sur la légalité.

    Le résultat porte toujours `conformite_reglementaire`, qui dit ce qui
    manquerait pour trancher.
    """
    h, l = bougie.get("h"), bougie.get("l")
    manque = ["cours de référence de la séance — absent de nos chandelles"]
    if not regime_applicable(ticker, date_iso):
        manque.append("régime de cotation applicable à ce titre ce jour-là")
    if not source_couvre(date_iso):
        manque.append(
            f"seuils applicables à cette date — la source citée n'entre en "
            f"vigueur qu'au {SOURCE_SEUILS['en_vigueur_depuis']}")

    cadre = {
        "conformite_reglementaire": {
            "statut": Conformite.NON_VERIFIABLE.value,
            "ce_qui_manque": manque,
            "_avertissement": "⚠️ Une amplitude compatible avec l'enveloppe "
                              "testée NE VAUT PAS conformité réglementaire : "
                              "l'écart entre deux prix ne dit rien de leur "
                              "position par rapport au cours de référence.",
        },
        "source_dans_sa_periode_de_validite": source_couvre(date_iso),
        "source": SOURCE_SEUILS,
    }

    if not isinstance(h, (int, float)) or not isinstance(l, (int, float)) \
            or isinstance(h, bool) or isinstance(l, bool) \
            or h != h or l != l or l <= 0:
        return {**cadre, "statut": Amplitude.NON_EVALUABLE.value,
                "rapport_h_l": None,
                "motif": "plus-haut ou plus-bas absent, non numérique ou ≤ 0"}

    rapport = h / l
    base = {**cadre, "rapport_h_l": round(rapport, 4),
            "enveloppe_la_plus_etroite": round(ENVELOPPE_LA_PLUS_ETROITE, 4),
            "enveloppe_la_plus_large": round(ENVELOPPE_LA_PLUS_LARGE, 4)}

    if not depasse(rapport, ENVELOPPE_LA_PLUS_ETROITE):
        return {**base, "statut": Amplitude.COMPATIBLE.value,
                "motif": "écart compatible avec toutes les enveloppes testées. "
                         "⚠️ Compatible ne veut pas dire conforme."}
    if depasse(rapport, ENVELOPPE_LA_PLUS_LARGE):
        return {**base, "statut": Amplitude.HORS_ENVELOPPE.value,
                "motif": f"rapport {rapport:.3f} au-delà de "
                         f"{ENVELOPPE_LA_PLUS_LARGE:.3f}, l'enveloppe la plus "
                         f"large testée. ALERTE DE COHÉRENCE DE DONNÉE : les "
                         f"prix de cette bougie s'écartent entre eux au-delà "
                         f"de tout ce qui a été testé. N'établit NI la cause, "
                         f"NI une illégalité — le constat ne s'appuie sur "
                         f"aucun texte et vaut donc à toute période."}
    return {**base, "statut": Amplitude.INDETERMINE.value,
            "motif": f"rapport {rapport:.3f} : dans l'enveloppe large, hors de "
                     f"l'enveloppe étroite. Sans le régime applicable, AUCUNE "
                     f"conclusion — ni dans un sens, ni dans l'autre."}


def evaluer_conformite(bougie: dict, cours_reference, nom_regime: str = "",
                       date_iso: str = "") -> dict:
    """Les prix respectent-ils la limite AUTOUR DU COURS DE RÉFÉRENCE ?

    Exige les trois pièces. Sans elles, répond « non vérifiable » — et c'est le
    cas de toutes nos observations aujourd'hui, aucune chandelle ne conservant
    le cours de référence de sa séance.
    """
    manque = []
    if not isinstance(cours_reference, (int, float)) or isinstance(cours_reference, bool) \
            or cours_reference != cours_reference or cours_reference <= 0:
        manque.append("cours de référence de la séance")
    if nom_regime not in REGIMES:
        manque.append("régime de cotation applicable")
    if date_iso and not source_couvre(date_iso):
        manque.append(f"seuils en vigueur à la date {date_iso}")
    if manque:
        return {"statut": Conformite.NON_VERIFIABLE.value,
                "ce_qui_manque": manque, "champs_examines": [],
                "bornes": None, "hors_bornes": None}

    s = REGIMES[nom_regime]["limite"]
    bas, haut = cours_reference * (1.0 - s), cours_reference * (1.0 + s)
    hors, examines = [], []
    for cle, nom in (("o", "ouverture"), ("h", "plus_haut"),
                     ("l", "plus_bas"), ("c", "cloture")):
        v = bougie.get(cle)
        if not isinstance(v, (int, float)) or isinstance(v, bool) or v != v:
            continue
        examines.append(nom)
        if v < bas * (1.0 - EPS) or v > haut * (1.0 + EPS):
            hors.append({"champ": nom, "valeur": v})

    # ⚠️ DÉFAUT CORRIGÉ : une bougie SANS AUCUN prix exploitable ressortait
    # « conforme », parce que la liste des dépassements restait vide. Ne rien
    # examiner n'est pas constater une conformité — c'est ne rien constater.
    if not examines:
        return {"statut": Conformite.NON_VERIFIABLE.value,
                "ce_qui_manque": ["aucun prix exploitable dans la bougie — "
                                  "rien à confronter aux bornes"],
                "champs_examines": [], "bornes": [round(bas, 4), round(haut, 4)],
                "hors_bornes": None}
    return {
        "statut": (Conformite.NON_CONFORME if hors else Conformite.CONFORME).value,
        "ce_qui_manque": [],
        "champs_examines": examines,
        "regime": nom_regime,
        "cours_reference": cours_reference,
        "bornes": [round(bas, 4), round(haut, 4)],
        "hors_bornes": hors,
        "source": REGIMES[nom_regime]["source"],
    }
