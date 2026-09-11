#!/usr/bin/env python3
"""Tests de COMPORTEMENT de la couche normalisée.

⚠️ RÈGLE DE CONSTRUCTION DE CES TESTS
─────────────────────────────────────
La revue externe a posé une contrainte explicite :

    « N'écris pas l'attendu en réutilisant la fonction que tu cherches à
      tester. »

Les attendus ci-dessous sont donc **écrits en dur**, tirés du diagnostic
(`docs/DIAGNOSTIC_SPLITS.md`) et des sources primaires — jamais recalculés par
le module testé. Un test qui appellerait `normaliser()` pour fabriquer sa
propre référence passerait quoi qu'il arrive, y compris si le module devenait
faux.

La seule chose comparée machine-à-machine est l'IDENTITÉ des valeurs entre
l'instantané et la couche dérivée — et c'est précisément le point : la couche
dérivée ne doit RIEN modifier.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))
sys.path.insert(0, str(RACINE / "pipeline"))

from normaliser import amplitude_impossible  # noqa: E402

LOT1A = RACINE / "datasets" / "lot1a"
LOT1B = RACINE / "datasets" / "lot1b"

TITRES = ["ADH", "ADI", "CSR", "MNG", "CMT", "TQA", "SOT"]

# ── Attendus écrits à la main, depuis le diagnostic et les sources ──────────

# Nombre de lignes : compté sur l'instantané au moment du gel (manifeste 1A).
LIGNES = {"ADH": 797, "ADI": 797, "CSR": 794, "MNG": 797,
          "CMT": 514, "TQA": 65, "SOT": 542}

# État d'ajustement : établi par docs/DIAGNOSTIC_SPLITS.md, pas par le code.
BASES = {"ADH": "sans_operation_declaree", "ADI": "sans_operation_declaree",
         "CSR": "sans_operation_declaree", "MNG": "ajuste_une_fois",
         "CMT": "sans_operation_declaree", "TQA": "sans_operation_declaree",
         "SOT": "double_ajustement"}

# Date d'effet du split SOT — source : registre SPLITS, avis BVC.
SPLIT_SOT = "2026-05-05"

# La bougie SOT du 05/05 : valeurs relevées à la main dans l'instantané.
SOT_0505 = {"o": 1700.0, "h": 1700.0, "l": 369.0, "c": 369.0}


def charger(dossier: Path, ticker: str) -> dict | list:
    return json.loads((dossier / f"{ticker}.json").read_text(encoding="utf-8"))


# ═══ 1. La couche dérivée ne modifie AUCUNE valeur ═════════════════════════

@pytest.mark.parametrize("ticker", TITRES)
def test_aucune_valeur_modifiee(ticker):
    """Prix et volumes de la couche normalisée == ceux de l'instantané.

    C'est la promesse centrale du lot 1B : qualifier sans retoucher.
    """
    brut = charger(LOT1A, ticker)
    norm = charger(LOT1B, ticker)["observations"]
    assert len(brut) == len(norm), f"{ticker} : le nombre de lignes a changé"

    for i, (b, o) in enumerate(zip(brut, norm)):
        assert str(b["d"])[:10] == o["date"], f"{ticker}[{i}] : date déplacée"
        assert b.get("o") == o["ouverture"], f"{ticker}[{i}] : ouverture modifiée"
        assert b.get("h") == o["plus_haut"], f"{ticker}[{i}] : plus-haut modifié"
        assert b.get("l") == o["plus_bas"], f"{ticker}[{i}] : plus-bas modifié"
        assert b.get("c") == o["cloture"], f"{ticker}[{i}] : clôture modifiée"


@pytest.mark.parametrize("ticker", TITRES)
def test_volume_inconnu_ne_devient_jamais_zero(ticker):
    """Un volume absent à la source reste absent. Il ne se replie pas sur 0."""
    brut = charger(LOT1A, ticker)
    norm = charger(LOT1B, ticker)["observations"]
    for b, o in zip(brut, norm):
        if b.get("v") is None:
            assert o["volume"] is None, f"{ticker} {o['date']} : inconnu → {o['volume']}"
            assert o["volume_etat"] == "inconnu"
        else:
            assert o["volume"] == float(b["v"])


@pytest.mark.parametrize("ticker", TITRES)
def test_nombre_de_lignes_attendu(ticker):
    """Effectifs écrits à la main depuis le manifeste du gel."""
    assert len(charger(LOT1B, ticker)["observations"]) == LIGNES[ticker]


# ═══ 2. L'état d'ajustement est celui du diagnostic ════════════════════════

@pytest.mark.parametrize("ticker", TITRES)
def test_base_prix_declaree(ticker):
    assert charger(LOT1B, ticker)["base_prix"]["etat"] == BASES[ticker]


def test_mng_n_est_pas_reajuste():
    """MNG est déjà divisé par 10. Le journal doit dire de NE PAS y toucher.

    ⚠️ Le risque sur MNG n'est pas l'inaction, c'est l'action : réappliquer
    l'ajustement produirait une double division.
    """
    d = charger(LOT1B, "MNG")
    ajust = [t for t in d["journal_transformations"]
             if t["transformation"] == "ajustement des opérations sur titres"]
    assert len(ajust) == 1
    assert ajust[0]["applique"] is False
    assert "double division" in ajust[0]["etat_diagnostique"]["consequence"]


def test_mng_reste_pleinement_exploitable():
    """Une base connue et saine ne doit disqualifier aucune observation."""
    obs = charger(LOT1B, "MNG")["observations"]
    assert all(o["admissible_pour"] for o in obs), \
        "MNG est ajusté correctement : aucune observation ne doit être écartée"


# ═══ 3. SOT — le double ajustement disqualifie l'historique ════════════════

def test_sot_avant_le_split_est_inadmissible():
    """Une base fausse ne sert à rien. Pas même « pour information »."""
    obs = charger(LOT1B, "SOT")["observations"]
    avant = [o for o in obs if o["date"] < SPLIT_SOT]
    assert avant, "aucune observation avant le split — le test ne prouverait rien"
    for o in avant:
        assert o["admissible_pour"] == [], \
            f"SOT {o['date']} : base 5× trop basse mais déclarée utilisable"


def test_sot_apres_le_split_redevient_exploitable():
    """La disqualification doit s'arrêter là où le diagnostic s'arrête."""
    obs = charger(LOT1B, "SOT")["observations"]
    apres = [o for o in obs if o["date"] > SPLIT_SOT]
    assert len(apres) > 50
    assert any(o["admissible_pour"] for o in apres), \
        "le diagnostic ne porte que sur l'avant-split — l'après doit servir"


def test_sot_bougie_du_split_ecartee():
    """La bougie du 05/05 mêle deux bases. Elle ne sert à rien non plus.

    ⚠️ Elle satisfait pourtant l'invariant OHLC (l ≤ o, c ≤ h) : aucun contrôle
    de forme ne peut la refuser. Seule l'amplitude la trahit.
    """
    obs = charger(LOT1B, "SOT")["observations"]
    b = next(o for o in obs if o["date"] == SPLIT_SOT)

    # valeurs relevées à la main, pas recalculées
    assert (b["ouverture"], b["plus_haut"], b["plus_bas"], b["cloture"]) == \
           (SOT_0505["o"], SOT_0505["h"], SOT_0505["l"], SOT_0505["c"])
    assert b["plus_bas"] <= b["ouverture"] <= b["plus_haut"]   # invariant OHLC tenu
    assert b["amplitude_impossible"] is not None
    assert b["admissible_pour"] == []


# ═══ 4. Le seuil d'amplitude se déduit de R10, il n'est pas choisi ═════════

def test_amplitude_accepte_une_seance_au_plafond_de_r10():
    """+10 % puis -10 % dans la journée : licite, donc jamais signalé."""
    assert amplitude_impossible({"h": 110.0, "l": 90.0, "o": 100.0, "c": 100.0}) is None


def test_amplitude_refuse_un_ecart_de_base():
    """Un rapport de 4,6 est hors de tout ce que R10 permet."""
    r = amplitude_impossible({"h": 1700.0, "l": 369.0, "o": 1700.0, "c": 369.0})
    assert r is not None
    assert r["rapport_h_l"] == pytest.approx(4.607, abs=0.001)


def test_amplitude_muette_sur_valeur_absente():
    """Pas de plus-bas : on ne conclut pas. Absence n'est pas anomalie."""
    assert amplitude_impossible({"h": 100.0, "l": None}) is None
    assert amplitude_impossible({"h": 100.0, "l": 0}) is None


def test_une_seule_bougie_depasse_sur_tout_le_lot():
    """Le contrôle ne disqualifie rien d'autre au passage.

    ⚠️ Un seuil correct qui écarterait la moitié des données serait inutilisable.
    Ce test mesure le coût du contrôle, pas seulement sa justesse.
    """
    trouvees = []
    for t in TITRES:
        for o in charger(LOT1B, t)["observations"]:
            if o["amplitude_impossible"]:
                trouvees.append((t, o["date"]))
    assert trouvees == [("SOT", SPLIT_SOT)], f"attendu 1 cas, trouvé {trouvees}"


# ═══ 5. Chaînage avec l'instantané ═════════════════════════════════════════

@pytest.mark.parametrize("ticker", TITRES)
def test_empreinte_source_concorde(ticker):
    """L'empreinte inscrite doit être celle du fichier figé, aujourd'hui.

    Un instantané modifié après coup rend la couche dérivée mensongère.
    """
    import hashlib
    attendue = hashlib.sha256((LOT1A / f"{ticker}.json").read_bytes()).hexdigest()
    assert charger(LOT1B, ticker)["empreinte_source"] == attendue


def test_la_couche_livree_est_reproductible_par_le_code():
    """Le JSON livré doit être exactement ce que le code d'AUJOURD'HUI produit.

    ⚠️ CE TEST N'EST PAS CIRCULAIRE, et la distinction compte.
    Il ne fabrique pas un attendu avec la fonction testée : il compare un
    ARTEFACT COMMITÉ à ce que le code régénère. Les deux peuvent diverger, et
    c'est précisément ce qu'on cherche — soit le code a changé sans que la
    livraison suive, soit la livraison a été retouchée à la main.

    Il comble un angle mort mesuré : en neutralisant le seuil d'amplitude, un
    seul test tombait. Tous les autres relisent le fichier déjà produit et ne
    voyaient rien. C'est la « seconde famille » de tests du projet — elle décrit
    les données publiées, pas le code.
    """
    from normaliser import charger_calendrier, normaliser as regenerer

    cal = charger_calendrier()
    for ticker in TITRES:
        attendu = regenerer(ticker, cal)
        livre = charger(LOT1B, ticker)
        assert livre["observations"] == attendu["observations"], (
            f"{ticker} : la couche livrée diffère de ce que le code produit — "
            f"relancer pipeline/normaliser.py, ou expliquer l'écart")
        assert livre["base_prix"] == attendu["base_prix"]


def test_manifeste_1a_ne_dit_plus_donnees_brutes_fournisseur():
    """Réserve de vocabulaire demandée en revue.

    Nous ne conservons AUCUNE charge utile de source : l'expression est donc
    réservée, et l'instantané doit se présenter comme ce qu'il est.
    """
    m = json.loads((LOT1A / "MANIFESTE.json").read_text(encoding="utf-8"))
    assert "INSTANTANÉ" in m["_quoi"]
    assert "brutes fournisseur" in m["_ce_que_ce_n_est_pas"]
    assert len(m["_commit_depot"]) == 40, "le commit doit être complet, pas abrégé"
    for t, s in m["series"].items():
        assert len(s["commit_source_complet"]) == 40, f"{t} : commit abrégé"
        assert "etat" in s["etat_ajustement"]
