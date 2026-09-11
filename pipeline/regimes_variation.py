#!/usr/bin/env python3
"""Les seuils de variation de la BVC — par régime, par date, avec leur source.

POURQUOI CE MODULE EXISTE
─────────────────────────
Un contrôle d'amplitude écrit en dur sur « ±10 % » tenait une limite unique
pour universelle. Elle ne l'est pas. La revue externe a relevé qu'un titre
nouvellement admis peut varier de ±20 %, et qu'une bougie `h=120, l=80` —
parfaitement licite sous ce régime — était déclarée « amplitude impossible,
mélange de bases » par notre détecteur.

CE QUE LE CONTRÔLE PEUT ET NE PEUT PAS CONCLURE
──────────────────────────────────────────────
Nous ne savons PAS, titre par titre et jour par jour, quel régime s'applique :
ni le mode de cotation (continu ou fixing), ni les dates d'admission. Le
contrôle ne peut donc pas trancher dans le cas général.

Il reste néanmoins concluant dans un cas précis : quand l'amplitude dépasse
**tous les régimes connus**, aucune hypothèse de régime ne la rend licite. La
conclusion ne dépend alors plus de ce qu'on ignore.

D'où trois issues, et non deux :

    CONFORME        sous le régime le PLUS STRICT — licite quoi qu'il arrive
    NON_CONCLUANT   licite sous un régime, pas sous un autre — on ne sait pas
    SUSPECTE        au-delà du régime le PLUS PERMISSIF — anomalie établie

⚠️ « SUSPECTE » qualifie l'AMPLITUDE, jamais sa CAUSE. Une amplitude
réglementairement impossible dit qu'une bougie est incohérente ; elle ne dit
pas pourquoi. La cause se déclare ailleurs, avec son propre niveau de preuve.
"""

from __future__ import annotations

from enum import Enum

# ── État de la connaissance sur les seuils ──────────────────────────────────
#
# ⚠️ NIVEAU DE PREUVE : ces valeurs ont été RELAYÉES PAR LA REVUE EXTERNE et
# n'ont PAS été vérifiées par nous sur le texte original de l'AMMC. Le dépôt
# ne conserve aucune copie de la circulaire. Tant que la pièce n'est pas
# jointe, le champ `verifie_sur_source_primaire` reste False et doit le rester.
SOURCE_SEUILS = {
    "reference": "circulaire AMMC du 25/06/2026",
    "relaye_par": "revue externe, message de réception du lot 1B",
    "verifie_sur_source_primaire": False,
    "ce_qui_manque": "copie de la circulaire, ou renvoi à l'article précis du "
                     "règlement général de la Bourse de Casablanca",
    "en_vigueur_depuis": "2026-06-23",
}

REGIMES = {
    "continu": {
        "limite": 0.10,
        "libelle": "±10 % — cotation en continu",
        "source": SOURCE_SEUILS,
    },
    "fixing": {
        "limite": 0.06,
        "libelle": "±6 % — cotation au fixing",
        "source": SOURCE_SEUILS,
    },
    "admission_cinq_premieres_seances": {
        "limite": 0.20,
        "libelle": "±20 % — cinq premières séances suivant l'admission",
        "source": SOURCE_SEUILS,
    },
}


def borne_amplitude(limite: float) -> float:
    """Rapport plus-haut / plus-bas maximal sous une limite symétrique ±s.

    Le plus-haut ne peut excéder `(1 + s) × référence` ni le plus-bas descendre
    sous `(1 − s) × référence`, donc `h / l ≤ (1 + s) / (1 − s)`.

    ⚠️ Cette borne suppose **un même cours de référence** pour les deux bornes
    de la séance. C'est le cas d'une séance ordinaire ; ce ne l'est pas si la
    référence est révisée en séance.
    """
    return (1.0 + limite) / (1.0 - limite)


# ⚠️ TOLÉRANCE RELATIVE SUR LA COMPARAISON AUX BORNES.
# `borne_amplitude(0.20)` vaut 1.4999999999999998 en virgule flottante, tandis
# qu'une bougie h=120, l=80 donne exactement 1.5. Sans tolérance, une bougie
# PILE À LA LIMITE réglementaire est déclarée suspecte — et c'est précisément
# le contre-exemple que la revue externe a construit. Le dépassement doit être
# franc pour compter.
EPS = 1e-9


def depasse(rapport: float, borne: float) -> bool:
    """Dépassement FRANC d'une borne. À la limite exacte, il n'y a pas excès."""
    return rapport > borne * (1.0 + EPS)


# Bornes dérivées, calculées une fois — et non recopiées à la main.
BORNE_LA_PLUS_STRICTE = min(borne_amplitude(r["limite"]) for r in REGIMES.values())
BORNE_LA_PLUS_PERMISSIVE = max(borne_amplitude(r["limite"]) for r in REGIMES.values())


class Amplitude(str, Enum):
    CONFORME = "conforme"
    NON_CONCLUANT = "contrôle réglementaire non concluant"
    SUSPECTE = "amplitude suspecte"
    NON_EVALUABLE = "non évaluable"


# Régime applicable, titre par titre et période par période.
# ⚠️ VIDE À DESSEIN. Nous ne disposons ni des modes de cotation ni des dates
# d'admission. Une entrée inventée ici rendrait le contrôle concluant à tort ;
# l'absence d'entrée le rend prudemment non concluant, ce qui est le bon défaut.
REGIME_PAR_TITRE: dict = {}


def regime_applicable(ticker: str, date_iso: str):
    """Régime en vigueur pour ce titre ce jour-là, ou None si indéterminé."""
    for periode in REGIME_PAR_TITRE.get(ticker, []):
        if periode["du"] <= date_iso <= (periode.get("au") or "9999-12-31"):
            return periode["regime"]
    return None


def evaluer_amplitude(bougie: dict, ticker: str = "", date_iso: str = "") -> dict:
    """Statut réglementaire de l'amplitude intraday d'une bougie.

    Ne conclut à l'anomalie que lorsqu'AUCUN régime connu ne rend la bougie
    licite. Ne nomme jamais la cause.
    """
    h, l = bougie.get("h"), bougie.get("l")
    if not isinstance(h, (int, float)) or not isinstance(l, (int, float)) \
            or isinstance(h, bool) or isinstance(l, bool) \
            or h != h or l != l or l <= 0:
        return {"statut": Amplitude.NON_EVALUABLE.value, "rapport_h_l": None,
                "motif": "plus-haut ou plus-bas absent, non numérique ou ≤ 0"}

    rapport = h / l
    nom_regime = regime_applicable(ticker, date_iso)

    if nom_regime:
        borne = borne_amplitude(REGIMES[nom_regime]["limite"])
        conforme = not depasse(rapport, borne)
        return {
            "statut": (Amplitude.CONFORME if conforme else Amplitude.SUSPECTE).value,
            "rapport_h_l": round(rapport, 4),
            "regime": nom_regime,
            "regime_etabli": True,
            "borne": round(borne, 4),
            "source": REGIMES[nom_regime]["source"],
            "motif": None if conforme else
                     f"rapport {rapport:.3f} > {borne:.3f}, borne du régime "
                     f"« {REGIMES[nom_regime]['libelle']} »",
        }

    # Régime indéterminé : on raisonne sur l'enveloppe des régimes connus.
    base = {
        "rapport_h_l": round(rapport, 4),
        "regime": None,
        "regime_etabli": False,
        "borne_la_plus_stricte": round(BORNE_LA_PLUS_STRICTE, 4),
        "borne_la_plus_permissive": round(BORNE_LA_PLUS_PERMISSIVE, 4),
        "source": SOURCE_SEUILS,
    }
    if not depasse(rapport, BORNE_LA_PLUS_STRICTE):
        return {**base, "statut": Amplitude.CONFORME.value,
                "motif": "licite sous TOUS les régimes connus, y compris le "
                         "plus strict — la conclusion ne dépend pas du régime"}
    if depasse(rapport, BORNE_LA_PLUS_PERMISSIVE):
        return {**base, "statut": Amplitude.SUSPECTE.value,
                "motif": f"rapport {rapport:.3f} au-delà de "
                         f"{BORNE_LA_PLUS_PERMISSIVE:.3f}, borne du régime le "
                         f"PLUS PERMISSIF connu (±"
                         f"{max(r['limite'] for r in REGIMES.values()):.0%}) — "
                         f"aucun régime connu ne rend cette bougie licite"}
    return {**base, "statut": Amplitude.NON_CONCLUANT.value,
            "motif": f"rapport {rapport:.3f} : licite sous le régime le plus "
                     f"permissif ({BORNE_LA_PLUS_PERMISSIVE:.3f}), illicite "
                     f"sous le plus strict ({BORNE_LA_PLUS_STRICTE:.3f}). "
                     f"Le régime applicable à ce titre ce jour-là n'est pas "
                     f"établi : AUCUNE conclusion."}
