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

⚠️ ÉVOLUTION DU DOSSIER
56 autres séances avaient d'abord été déposées en candidat, sans être appliquées.
L'export opérateur complet a ensuite été réceptionné comme historique de
référence après vérification indépendante de l'identité SID = SONASID. Le
candidat est conservé pour l'audit, mais il est désormais supersédé.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE / "pipeline"))

import _echelle  # noqa: E402  (contrôles relatifs, voir ce module)

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
    autour de 67. Une bougie de Sonasid au niveau de Stokvis est une bougie
    mixte.

    ⚠️ 11/10/2026 : ce test exigeait `l >= 200 et o >= 200`, un niveau de
    marché daté — il aurait rougi si Sonasid cotait un jour sous 200 DH.
    Le défaut se reconnaît sans niveau : l'amplitude d'une bougie mixte (ouverture
    et plus-bas de Stokvis, clôture de Sonasid) vaut ~28, quand R10 en interdit
    plus de ~1,22 (+10 % / −10 % autour de la référence) ; et une séance d'un autre titre coupe la série par une
    rupture. Facteur mesuré : Stokvis 67 DH / Sonasid 1 900 DH.
    """
    basses = _echelle.hors_echelle(_echelle.charger_bougies("SNA"),
                                   _echelle.facteur_d_echelle("SNA"))
    assert basses == [], f"bougies au niveau de Stokvis : {basses}"


def test_chaque_bougie_corrigee_respecte_la_limite_de_variation(serie):
    """R10 : ±10 % par séance. Une amplitude intraséance de −96 % n'existe pas."""
    for d in DATES:
        b = serie[d]
        assert b["l"] <= min(b["o"], b["c"]) <= max(b["o"], b["c"]) <= b["h"]
        assert abs(b["l"] / b["c"] - 1) < 0.10, d


def test_les_valeurs_corrigees_sont_celles_de_l_operateur(recu, serie):
    for l in recu["lignes"]:
        assert {k: serie[l["d"]][k] for k in ("o", "h", "l", "c", "v")} == l["corrige"]


def _planchers_attendus(ordonnee, ancre):
    """Plus-bas 52 semaines et 90 jours des séances JUSQU'À `ancre` (la date du
    cache). ⚠️ 11/10/2026 : l'ancre était `pd.Timestamp.now()`, l'horloge de la
    machine d'essai — un attendu daté : un lundi, avant la régénération du
    cache, un plus-bas sorti de la fenêtre entre-temps faisait échouer un test
    de la garde bloquante sur des données saines."""
    import pandas as pd
    df = pd.DataFrame(ordonnee)
    dates = pd.to_datetime(df["d"], errors="coerce")
    ancre = pd.Timestamp(ancre)
    df, dates = df[dates <= ancre], dates[dates <= ancre]
    d52 = df[dates >= ancre - pd.Timedelta(weeks=52)]
    d90 = df[dates >= ancre - pd.Timedelta(days=90)]
    return (float((d52 if not d52.empty else df)["l"].min()),
            float((d90 if not d90.empty else df)["l"].min()))


def test_le_plus_bas_52_semaines_n_est_plus_un_cours_de_stokvis():
    """67,08 DH était le plus-bas de Stokvis du 11/09, servi comme plancher
    annuel de Sonasid — un titre à 1 900 DH."""
    cache = json.loads((RACINE / "pipeline" / "historical_data.json")
                       .read_text(encoding="utf-8"))["SNA"]
    ordonnee = json.loads((RACINE / "pipeline" / "candles" / "SNA.json")
                          .read_text(encoding="utf-8"))
    attendu_l52, attendu_l90 = _planchers_attendus(ordonnee, cache["last_date"])

    assert cache["l52w"] == attendu_l52
    assert cache["l90"] == attendu_l90
    # ⚠️ 11/10/2026 : `l52w > 1000 and l90 > 1000` est retiré. Ce plancher
    # rougissait sur une vraie baisse de Sonasid sous 1 000 DH (elle cote 1 650
    # au plus-bas de l'année). Le défaut — le 67,08 de Stokvis — est une valeur
    # que NULLE séance du tronçon continu de Sonasid n'atteint.
    bougies = _echelle.charger_bougies("SNA")
    facteur = _echelle.facteur_d_echelle("SNA")
    assert _echelle.defauts_extreme("l52w", cache, bougies, facteur) == []
    assert not _echelle.valeur_hors_echelle(cache["l90"], bougies, facteur), (
        "un plancher à 90 jours d'une autre échelle serait encore une "
        "contamination Stokvis")


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

def test_l_ancien_candidat_est_conserve_et_supersede(serie):
    """Le dossier de mesure reste auditable mais n'est plus une instruction active."""
    c = json.loads(CANDIDAT.read_text(encoding="utf-8"))
    assert c["_statut"].startswith("SUPERSÉDÉ")
    assert c["_supersede_par"] == "datasets/historiques_importes/SNA.json"
    assert (RACINE / c["_supersede_par"]).exists()
    assert c["seances_en_ecart"] == 56
    assert c["champs_en_ecart"]["cloture"] == 23

    # Sur la période de l'export, les anciennes valeurs candidates sont
    # désormais celles de la série publiée. On conserve les lignes pour
    # expliquer le changement de décision, pas pour continuer à les refuser.
    non_alignees = [
        l["d"] for l in c["lignes"]
        if not all(serie[l["d"]][k] == l["operateur"][k]
                   for k in l["champs_en_ecart"])
    ]
    assert non_alignees == [], (
        f"l'import opérateur n'a pas repris toutes les valeurs supersédées : "
        f"{non_alignees[:5]}")


def test_l_hypothese_porte_ce_qui_la_contredit():
    """⚠️ Une hypothèse qui ne cite que ce qui l'arrange n'est pas une
    hypothèse. Celle-ci doit nommer les neuf séances qu'elle n'explique pas."""
    c = json.loads(CANDIDAT.read_text(encoding="utf-8"))
    h = c["_hypothese_a_confirmer"]
    assert h["_conclusion"].startswith("hypothese_a_confirmer")
    assert "ce_qui_la_CONTREDIT" in h and h["ce_qui_la_CONTREDIT"]


def test_le_30_juillet_disparait_avec_l_import_operateur(serie):
    """Le 30/07 est un jour férié déclaré et l'export opérateur l'omet."""
    c = json.loads(CANDIDAT.read_text(encoding="utf-8"))
    assert "2026-07-30" in c["_seances_absentes_de_l_export"]["dates"]
    assert c["_statut"].startswith("SUPERSÉDÉ")
    assert "2026-07-30" not in serie, (
        "une bougie du jour de la Fête du Trône a survécu à l'import complet")


# ── Contrôles du recalcul daté (11/10/2026) ────────────────────────────────

def test_controle_negatif_le_recalcul_attrape_un_plancher_de_stokvis():
    ordonnee = json.loads((RACINE / "pipeline" / "candles" / "SNA.json")
                          .read_text(encoding="utf-8"))
    cache = json.loads((RACINE / "pipeline" / "historical_data.json")
                       .read_text(encoding="utf-8"))["SNA"]
    l52, l90 = _planchers_attendus(ordonnee, cache["last_date"])
    assert (cache["l52w"], cache["l90"]) == (l52, l90)
    assert l52 != 67.08, "le plancher de Stokvis ne passerait pas"
    # série polluée : un plancher de Stokvis dans la fenêtre change l'attendu,
    # donc un cache resté à la vraie valeur serait vu comme faux.
    sale = [dict(b) for b in ordonnee]
    sale[-5].update({"o": 67.08, "l": 67.08})
    assert _planchers_attendus(sale, cache["last_date"])[0] == 67.08 != cache["l52w"]


def test_controle_positif_l_attendu_ne_depend_pas_de_l_horloge_de_la_machine(monkeypatch):
    """Même résultat quelle que soit la date d'aujourd'hui (machine simulée six
    mois plus tard), et une vraie chute continue (sous 1 000) ne fait pas
    échouer le recalcul daté."""
    import pandas as pd
    import _echelle
    ordonnee = json.loads((RACINE / "pipeline" / "candles" / "SNA.json")
                          .read_text(encoding="utf-8"))
    cache = json.loads((RACINE / "pipeline" / "historical_data.json")
                       .read_text(encoding="utf-8"))["SNA"]
    monkeypatch.setattr(pd.Timestamp, "now",
                        classmethod(lambda cls, *a, **k: pd.Timestamp("2027-04-12")))
    assert _planchers_attendus(ordonnee, cache["last_date"]) == (cache["l52w"], cache["l90"])
    chute = _echelle.prolonger(ordonnee, round(ordonnee[-1]["c"] * 0.45, 2))
    c2 = _echelle.cache_recalcule(chute)
    l52, _ = _planchers_attendus(chute, c2["last_date"])
    assert l52 == c2["l52w"] < 1000
