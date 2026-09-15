#!/usr/bin/env python3
"""Sonasid portait les cours de Stokvis dans six de ses bougies.

⚠️ CE QUI L'ÉTABLIT, ET POURQUOI CE N'EST PAS UN SIMPLE ÉCART
─────────────────────────────────────────────────────────────
Pour chacune des six séances, notre ouverture et notre plus-bas se retrouvent
À L'IDENTIQUE dans l'export de STOKVIS NORD AFRIQUE — parfois du jour même,
parfois de la veille :

    séance        notre o / l     ouverture de Stokvis
    2026-06-25       75,00            74,99  (25/06)
    2026-06-26       74,99            74,99  (25/06)
    2026-06-29       74,67            74,67  (26/06)
    2026-09-10       68,00            68,00  (10/09)
    2026-09-11       67,08            67,08  (11/09)

Et l'amplitude qu'ils impliquent est interdite : un plus-bas de 67,08 avec une
clôture de 1 923 serait une séance à −96,5 %, quand la Bourse de Casablanca
plafonne à ±10 % (R10). Ce ne sont pas des écarts d'appréciation : ce sont les
cours d'une autre société.

C'est l'inversion de codes documentée depuis le 10/08 : `SNA` désigne STOKVIS
à la Bourse de Casablanca, et Sonasid y est `SID`.

⚠️ CE QUE CE LOT NE CORRIGE PAS
56 autres séances s'écartent de l'export, dont 23 sur la CLÔTURE. Leur cause
n'est pas établie ; elles sont mesurées et déposées en candidat, pas appliquées.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE / "pipeline"))

RECU = RACINE / "datasets" / "corrections_acceptees" / "SNA.json"
CANDIDAT = RACINE / "datasets" / "historiques_candidats" / "SNA_ecarts" / "ecarts.json"
DATES = ("2026-06-18", "2026-06-25", "2026-06-26",
         "2026-06-29", "2026-09-10", "2026-09-11")


@pytest.fixture(scope="module")
def recu():
    return json.loads(RECU.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def serie():
    return {b["d"]: b for b in json.loads(
        (RACINE / "pipeline" / "candles" / "SNA.json").read_text(encoding="utf-8"))}


def test_le_lot_porte_six_seances_et_l_identite_sonasid(recu):
    assert recu["ticker"] == "SNA" and recu["instrument"] == "SONASID"
    assert recu["source"]["code_operateur"] == "SID", (
        "⚠️ le fichier `Cours_SNA` de l'opérateur est STOKVIS ; Sonasid est SID")
    assert tuple(l["d"] for l in recu["lignes"]) == DATES


def test_plus_aucune_bougie_de_sonasid_ne_descend_au_niveau_de_stokvis(serie):
    """⚠️ Le contrôle qui mord. Sonasid cote autour de 1 900 DH ; Stokvis
    autour de 67. Une bougie de Sonasid sous 200 DH est une bougie mixte."""
    basses = {d: b for d, b in serie.items() if b["l"] < 200 or b["o"] < 200}
    assert basses == {}, f"bougies au niveau de Stokvis : {sorted(basses)}"


def test_chaque_bougie_corrigee_respecte_la_limite_de_variation(serie):
    """R10 : ±10 % par séance. Une amplitude intraséance de −96 % n'existe pas."""
    for d in DATES:
        b = serie[d]
        assert b["l"] <= min(b["o"], b["c"]) <= max(b["o"], b["c"]) <= b["h"]
        assert abs(b["l"] / b["c"] - 1) < 0.10, d


def test_les_valeurs_corrigees_sont_celles_de_l_operateur(recu, serie):
    for l in recu["lignes"]:
        assert {k: serie[l["d"]][k] for k in ("o", "h", "l", "c", "v")} == l["corrige"]


def test_le_plus_bas_52_semaines_n_est_plus_un_cours_de_stokvis():
    """67,08 DH était le plus-bas de Stokvis du 11/09, servi comme plancher
    annuel de Sonasid — un titre à 1 900 DH."""
    cache = json.loads((RACINE / "pipeline" / "historical_data.json")
                       .read_text(encoding="utf-8"))["SNA"]
    assert cache["l52w"] == 1820.0
    assert cache["l90"] == 1890.0
    assert cache["l52w"] > 1000, "un plancher sous 1 000 DH serait encore Stokvis"


def test_la_correction_resiste_a_une_recontamination(recu, serie):
    """⚠️ Même exigence que pour MSA : l'import réécrit les chandelles, la
    couche doit réimposer les six séances."""
    from corrections_acceptees import appliquer
    ordonnee = json.loads((RACINE / "pipeline" / "candles" / "SNA.json")
                          .read_text(encoding="utf-8"))
    sale = [dict(b) for b in ordonnee]
    par_date = {l["d"]: l for l in recu["lignes"]}
    for b in sale:
        if b["d"] in par_date:
            b.update(par_date[b["d"]]["remplace"])
    assert sale != ordonnee
    out, rapport = appliquer("SNA", sale)
    assert rapport["corrections"] == 6 and rapport["refus"] == []
    assert out == ordonnee


# ── Le candidat : il propose, il n'instruit pas ────────────────────────────

def test_les_56_autres_ecarts_sont_candidats_et_non_appliques(serie):
    """⚠️ Un écart est un ÉCART tant que sa cause n'est pas établie. Ces
    séances sont mesurées, datées, chiffrées — et laissées telles quelles
    dans les chandelles publiées."""
    c = json.loads(CANDIDAT.read_text(encoding="utf-8"))
    assert c["_statut"].startswith("CANDIDAT")
    assert c["seances_en_ecart"] == 56
    assert c["champs_en_ecart"]["cloture"] == 23
    # Aucune valeur du candidat n'a été écrite dans la série publiée.
    ecrites = [l["d"] for l in c["lignes"]
               if all(serie[l["d"]][k] == l["operateur"][k]
                      for k in l["champs_en_ecart"])]
    assert ecrites == [], f"des valeurs candidates ont été appliquées : {ecrites}"


def test_l_hypothese_porte_ce_qui_la_contredit():
    """⚠️ Une hypothèse qui ne cite que ce qui l'arrange n'est pas une
    hypothèse. Celle-ci doit nommer les neuf séances qu'elle n'explique pas."""
    c = json.loads(CANDIDAT.read_text(encoding="utf-8"))
    h = c["_hypothese_a_confirmer"]
    assert h["_conclusion"].startswith("hypothese_a_confirmer")
    assert "ce_qui_la_CONTREDIT" in h and h["ce_qui_la_CONTREDIT"]


def test_la_seance_fantome_du_30_juillet_est_signalee_pas_supprimee(serie):
    """L'opérateur ne publie pas le 30/07/2026. Nous la portons encore — comme
    72 de nos 74 titres. La retirer dépasse ce lot ; la taire serait pire."""
    c = json.loads(CANDIDAT.read_text(encoding="utf-8"))
    assert "2026-07-30" in c["_seances_absentes_de_l_export"]["dates"]
    assert "2026-07-30" in serie, "la séance n'a pas à disparaître dans ce lot"
