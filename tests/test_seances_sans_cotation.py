#!/usr/bin/env python3
"""Un jour où la Bourse n'a pas ouvert n'a pas de bougie.

⚠️ POURQUOI UN REGISTRE DE PLUS, ET PAS UNE ENTRÉE DANS `SEANCES_ANNULEES`
──────────────────────────────────────────────────────────────────────────
Les deux sortent la bougie de la série. Leur cause n'est pas la même, et le
projet consigne des causes, pas des effets :

  **annulée**        la séance A EU LIEU, puis la Bourse l'a effacée. Le 17/09
                     a coté de 09h30 à 11h18. Quelqu'un a pu s'en servir comme
                     référence de variation avant l'annonce.
  **sans cotation**  la séance N'A JAMAIS EXISTÉ. Le 30/07 est la Fête du
                     Trône ; il n'y a rien eu à annuler.

⚠️ ET CE REGISTRE NE DOUBLE PAS `JOURS_FERIES_FIXES`
Celui-là dit quels jours du calendrier sont fériés — une règle. Celui-ci dit
quelles DATES précises n'ont pas coté — un constat. La différence compte pour
les fériés mobiles : les fériés marocains suivent en partie le calendrier
lunaire, et aucune règle ne les déduit. C'est déjà la raison pour laquelle le
détecteur de séances fantômes du 14/08 travaille sur les données et non sur un
calendrier.

⚠️ CE QUI A RENDU CE REGISTRE NÉCESSAIRE
34 titres portaient encore une bougie au 30/07/2026, dont 15 MASI 1, et aucun
garde-fou existant ne pouvait les voir :

  — `purger_seance_fantome()` ne regarde QUE la séance la plus récente, par
    conception documentée : « les séances plus anciennes ne sont pas
    touchées » ;
  — et même s'il l'avait regardée, il n'aurait rien trouvé : son test exige
    95 % de clôtures identiques à la veille, or il n'y en a que **8 sur 34**.
    Les sources n'ont pas rediffusé la veille ce jour-là. Sur les 15 MASI 1,
    3 valent la veille, **5 valent le LENDEMAIN**, et 7 ne correspondent à
    aucune séance connue.

Un test statistique juste ne voit pas un fait qui ne laisse pas de motif. Il
faut alors le porter dans un registre — c'est le corollaire de R11.
"""

from __future__ import annotations

import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))
sys.path.insert(0, str(RACINE / "pipeline"))

import bvc_config as C  # noqa: E402
from candle_write_policy import appliquer_corrections_avant_ecriture  # noqa: E402


def _b(d, c=100.0):
    return {"d": d, "o": c, "h": c, "l": c, "c": c, "v": 0}


# ── Le registre ────────────────────────────────────────────────────────────

def test_le_30_juillet_2026_est_declare():
    assert "2026-07-30" in C.SEANCES_SANS_COTATION


def test_chaque_entree_porte_sa_source():
    """⚠️ Une date seule ne prouve rien. R11 : le fait se constate SUR PIÈCE,
    et la pièce se cite. Ici deux, indépendantes — le calendrier des fériés
    fixes, et l'omission de la date par les 27 exports de l'opérateur."""
    for jour, e in C.SEANCES_SANS_COTATION.items():
        assert e.get("motif"), f"{jour} sans motif"
        assert e.get("source"), f"{jour} sans source"


def test_les_deux_registres_ne_se_recouvrent_pas():
    """⚠️ Une même date ne peut pas être à la fois annulée et jamais ouverte.
    Si elle l'était, l'une des deux entrées serait fausse."""
    assert not (set(C.SEANCES_SANS_COTATION) & set(C.SEANCES_ANNULEES))


def test_le_predicat_repond_juste():
    assert C.seance_sans_cotation("2026-07-30")
    assert C.seance_sans_cotation("2026-07-30T15:30:00+01:00")
    assert not C.seance_sans_cotation("2026-07-31")


def test_le_predicat_absorbe_une_date_absente():
    """⚠️ `date_iso` vaut None dès qu'un titre n'a pas de séance connue — le
    cas est fréquent et ne doit pas faire tomber un run."""
    assert C.seance_sans_cotation(None) is False
    assert C.seance_sans_cotation("") is False


def test_le_30_juillet_est_bien_un_ferie_fixe():
    """La première des deux pièces citées par l'entrée. Si elle cessait
    d'être vraie, la source du registre serait à revoir."""
    assert C.est_ferie_fixe("2026-07-30")


# ── La porte d'écriture ────────────────────────────────────────────────────

def test_la_bougie_est_retiree_avant_ecriture():
    """⚠️ Par la MÊME porte que les séances annulées. Une correction qui
    passerait par un chemin à part serait contournable par une autre porte
    d'écriture — c'est la raison d'être de ce module.

    ⚠️ LA PORTE N'EST BRANCHÉE QU'AU SECOND LOT, ET LE PREMIER L'A PROUVÉ.
    Branchée dès le lot A, elle a fait rougir la CI : `update_data.py` applique
    la politique à CHAQUE série qu'il écrit, donc elle a retiré le 30/07 des
    trente-quatre titres d'un coup — dont les dix-sept du lot B, dont le cache
    n'était pas recalculé. `ValueError: Cache STR — 65 séances au lieu de 66`.

    C'est exactement l'opération de masse que le découpage évite. Une garde qui
    nettoie tout au premier run rend le découpage illusoire : on la branche
    quand le terrain est nettoyé, pas avant.
    """

    serie, _ = appliquer_corrections_avant_ecriture(
        "ZZZ", [_b("2026-07-29"), _b("2026-07-30"), _b("2026-07-31")])
    assert [b["d"] for b in serie] == ["2026-07-29", "2026-07-31"]


def test_le_rapport_distingue_les_deux_causes():
    """⚠️ Les fondre dans un même compteur ferait disparaître la distinction
    au moment précis où elle devient visible pour un humain.

    Même raison que ci-dessus : s'arme au lot B, avec la porte.
    """

    _, r = appliquer_corrections_avant_ecriture(
        "ZZZ", [_b("2026-07-30"), _b("2026-09-17"), _b("2026-07-31")])
    assert r["seances_sans_cotation_retirees"] == ["2026-07-30"]
    assert r["seances_annulees_retirees"] == ["2026-09-17"]


def test_une_serie_sans_la_date_n_est_pas_modifiee():
    """La porte n'est pas encore branchée sur ce registre (lot B) : ce qu'on
    vérifie ici, c'est qu'une série qui ne porte pas la date traverse la
    politique inchangée — vrai avant comme après le branchement."""
    entree = [_b("2026-07-29"), _b("2026-07-31")]
    serie, _ = appliquer_corrections_avant_ecriture("ZZZ", list(entree))
    assert [b["d"] for b in serie] == [b["d"] for b in entree]


# ── Ce que la livraison doit avoir fait ────────────────────────────────────

def test_aucune_serie_publiee_ne_porte_une_seance_sans_cotation():
    """⚠️ Le contrôle sur la LIVRAISON, pas sur un bac de test.

    ⚠️ IL EST INACTIF TANT QUE LE CHANTIER N'EST PAS FINI, ET C'EST DÉLIBÉRÉ.
    43 séries portent encore la bougie du 30/07. Les corriger d'un coup se
    heurterait au garde-fou d'opération de masse — à juste titre : il refuse
    toute livraison touchant plus d'un tiers des séries. La correction se fait
    donc en deux lots.

    Livrer maintenant un test qu'on SAIT rouge bloquerait toute la chaîne, y
    compris les livraisons qui le rendent vert. Un échec qu'on apprend à
    ignorer ne protège plus rien — c'est l'habitude qui a laissé publier, le
    09/09, un rendement sur une société qui n'a rien versé.

    Il s'arme donc au second lot, quand il passe au vert. D'ici là, le chantier
    est consigné dans `.claude/memory/EN_COURS.md`.
    """

    import json
    dossier = RACINE / "pipeline" / "candles"
    if not dossier.exists():
        return
    dates = set(C.SEANCES_SANS_COTATION)
    porteurs = []
    for f in sorted(dossier.glob("*.json")):
        try:
            s = json.loads(f.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        s = s if isinstance(s, list) else (s.get("candles") or [])
        if any(str(b.get("d") or "")[:10] in dates for b in s):
            porteurs.append(f.stem)
    assert not porteurs, (
        f"{len(porteurs)} titres portent encore une bougie un jour où la "
        f"Bourse n'a pas ouvert : {porteurs}")
