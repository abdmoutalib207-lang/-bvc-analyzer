#!/usr/bin/env python3
"""SMI a rediffusé un cours pendant six séances — et deux constats qui portent
sur tout le terminal.

⚠️ CE QUI EST ÉTABLI SUR SMI
───────────────────────────
Du 19/06 au 01/07/2026, notre série est restée FIGÉE à 6 976,00 DH pendant six
séances, avec un volume NUL. L'opérateur, lui, publie une baisse jusqu'à 5 801
et enregistre des échanges chaque jour :

    séance        notre c    opérateur c    titres échangés
    2026-06-25     6 976         5 900           1 852
    2026-06-26     6 976         5 950             683
    2026-06-29     6 976         5 801             944
    2026-06-30     6 976         6 000           1 824
    2026-07-01     6 976         6 149             335

Le prix n'a pas été mesuré : il a été rediffusé. SMI figure parmi les cinq
titres dont le journal du 29/06/2026 relève que les sources ne les servaient
plus.

⚠️ Et les 18 et 19/06, notre `v` valait 15 034 166 quand l'opérateur compte
2 126 puis 2 117 titres : le MONTANT EN DIRHAMS écrit à la place du NOMBRE DE
TITRES.

⚠️ CE QUI N'EST PAS CORRIGÉ, ET RESTE MESURÉ
────────────────────────────────────────────
· trois séances manquent à 63 de nos 73 titres (22, 23 et 24/06/2026) ;
· le champ `v` n'a pas la même unité selon le titre.
Les deux sont chiffrés dans le dossier candidat, appliqués nulle part.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE / "pipeline"))

RECU = RACINE / "datasets" / "corrections_acceptees" / "SMI.json"
DOSSIER = RACINE / "datasets" / "historiques_candidats" / "ADI_SMI" / "confrontation.json"
GELEES = ("2026-06-25", "2026-06-26", "2026-06-29", "2026-06-30", "2026-07-01")


@pytest.fixture(scope="module")
def recu():
    return json.loads(RECU.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def serie():
    return {b["d"]: b for b in json.loads(
        (RACINE / "pipeline" / "candles" / "SMI.json").read_text(encoding="utf-8"))}


# ── SMI : le cours rediffusé ───────────────────────────────────────────────

def test_le_cours_ne_reste_plus_fige_a_6976(serie):
    """⚠️ Le contrôle qui mord : six clôtures identiques d'affilée sur un titre
    qui, d'après l'opérateur, baissait de 10 % dans la même fenêtre."""
    figees = [d for d in GELEES if serie[d]["c"] == 6976.0]
    assert figees == [], f"séances encore figées à 6 976 : {figees}"


def test_aucune_des_seances_corrigees_ne_porte_un_volume_nul(serie, recu):
    """Un volume nul disait « aucun échange » là où l'opérateur en compte."""
    for l in recu["lignes"]:
        assert serie[l["d"]]["v"] > 0, l["d"]


def test_les_valeurs_viennent_de_l_operateur(recu, serie):
    for l in recu["lignes"]:
        assert {k: serie[l["d"]][k] for k in ("o", "h", "l", "c", "v")} == l["corrige"]


def test_le_montant_en_dirhams_n_est_plus_dans_le_champ_des_titres(serie):
    """15 034 166 « titres » pour SMI, c'était le montant en dirhams."""
    for d in ("2026-06-18", "2026-06-19"):
        assert serie[d]["v"] < 10000, f"{d} porte encore un montant : {serie[d]['v']}"


def test_la_correction_resiste_a_une_recontamination(recu, serie):
    from corrections_acceptees import appliquer
    ordonnee = json.loads((RACINE / "pipeline" / "candles" / "SMI.json")
                          .read_text(encoding="utf-8"))
    sale = [dict(b) for b in ordonnee]
    par_date = {l["d"]: l for l in recu["lignes"]}
    for b in sale:
        if b["d"] in par_date:
            b.update(par_date[b["d"]]["remplace"])
    assert sale != ordonnee
    out, rapport = appliquer("SMI", sale)
    assert rapport["corrections"] == 7 and rapport["refus"] == []
    assert out == ordonnee


# ── Les deux constats, mesurés et non appliqués ────────────────────────────

@pytest.fixture(scope="module")
def dossier():
    return json.loads(DOSSIER.read_text(encoding="utf-8"))


def test_le_trou_de_trois_seances_est_chiffre_a_l_echelle_du_marche(dossier):
    """⚠️ 22, 23 et 24/06/2026 manquent à 63 de nos 73 titres. Le dossier doit
    porter la liste, pas seulement le nombre."""
    c = dossier["constat_1_trois_seances_manquent_au_marche_entier"]
    assert c["seances"] == ["2026-06-22", "2026-06-23", "2026-06-24"]
    assert c["titres_a_qui_les_TROIS_manquent"] == len(c["liste"]) == 63
    assert "ADI" in c["liste"] and "SMI" in c["liste"]


def test_les_trois_seances_manquent_toujours_et_ne_sont_pas_fabriquees():
    """⚠️ Une correction dit « cette bougie est fausse », pas « elle devrait
    exister ». Tant que les exports des 63 titres manquent, le trou reste —
    et il vaut mieux qu'une cotation inventée."""
    for t in ("ADI", "SMI"):
        dates = {b["d"] for b in json.loads(
            (RACINE / "pipeline" / "candles" / f"{t}.json").read_text(encoding="utf-8"))}
        assert not (dates & {"2026-06-22", "2026-06-23", "2026-06-24"})


def test_l_unite_du_volume_est_mesuree_et_non_uniformisee(dossier):
    """⚠️ LE CONSTAT LE PLUS LOURD. Le champ `v` porte tantôt des titres,
    tantôt des dirhams. Il est mesuré titre par titre, et rien n'est converti :
    convertir réécrirait ~670 séances sur cinq titres au moins, sur la foi
    d'une convention déduite et non déclarée."""
    c = dossier["constat_2_le_champ_v_n_a_pas_la_meme_unite_selon_le_titre"]
    conventions = {t: v["convention"] for t, v in c["par_titre"].items()}
    assert len(conventions) >= 15
    assert conventions["ADI"] == "MONTANT MAD"
    assert conventions["SMI"] == "TITRES"
    assert set(conventions.values()) >= {"TITRES", "MONTANT MAD", "MÉLANGÉE"}, (
        "si une seule convention subsistait, ce constat n'aurait plus d'objet")


def test_adi_n_est_pas_contaminee_mais_reste_candidate(dossier):
    """ADI : 57 séances s'écartent, aucune d'un ordre de grandeur. Pas de trace
    de contamination d'identité — et donc aucune correction appliquée."""
    c = dossier["constat_3_adi_confrontee"]
    assert c["seances_en_ecart"] == len(c["lignes"]) == 57
    assert not (RACINE / "datasets" / "corrections_acceptees" / "ADI.json").exists()
