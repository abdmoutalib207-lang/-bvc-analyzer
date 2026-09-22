#!/usr/bin/env python3
"""Un fichier écrit avant la clôture ne peut pas la contenir.

⚠️ LE CHIEN DE GARDE A DIT « TOUT VA BIEN » LES DEUX JOURS OÙ LE PRODUIT
ÉTAIT CASSÉ
───────────────────────────────────────────────────────────────────────
    18/09 21h07   contrôle VERT.   data.json écrit à 04h44, portant le 16/09.
                  La séance du 18 avait eu lieu et n'était nulle part.
    21/09 22h07   contrôle VERT.   data.json écrit à 11h44, annonçant 60
                  titres « au 21/09 » — des cours figés EN PLEINE SÉANCE.
                  BCP publiait 1 337 titres échangés quand la séance en avait
                  vu 469 537, soit 0,3 %.

Les douze contrôles vérifiaient la présence, la cohérence, les bornes. Aucun
ne posait la seule question qui tranche. Abd Moutalib a découvert les deux
pannes lui-même, et c'est exactement ce que la surveillance doit éviter.

⚠️ POURQUOI CE CONTRÔLE NE CRIE PAS AU LOUP UN JOUR FÉRIÉ
─────────────────────────────────────────────────────────
Il ne demande pas « la Bourse a-t-elle coté ? » — question à laquelle nous ne
savons pas répondre sans calendrier lunaire — mais « le moteur a-t-il tourné
depuis la dernière clôture ? ». Un jour férié, le moteur tourne comme les
autres jours et réécrit `data.json` avec les mêmes cours mais un horodatage
frais : le contrôle passe. C'est le raisonnement du 14/08 sur les séances
fantômes — déduire des données, jamais d'une liste écrite d'avance.
"""

from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))
sys.path.insert(0, str(RACINE / "pipeline"))

from verifier_seance import (derniere_cloture_ecoulee,  # noqa: E402
                             horodatage_couvre_la_cloture)

CASA = ZoneInfo("Africa/Casablanca")


def _t(txt):
    return datetime.fromisoformat(txt).replace(tzinfo=CASA)


# ── Les deux pannes réelles ────────────────────────────────────────────────

def test_la_panne_du_21_septembre_aurait_ete_vue():
    """Contrôle lancé à 22h07 ; `data.json` écrit à 11h44, en pleine séance."""
    cloture = derniere_cloture_ecoulee(_t("2026-09-21T22:07:00"))
    assert cloture == _t("2026-09-21T15:30:00")
    assert _t("2026-09-21T11:44:32") < cloture, (
        "un fichier de 11h44 doit être reconnu antérieur à la clôture de 15h30")


def test_la_panne_du_18_septembre_aurait_ete_vue():
    """Contrôle lancé à 21h07 ; `data.json` écrit à 04h44, avant l'ouverture."""
    cloture = derniere_cloture_ecoulee(_t("2026-09-18T21:07:00"))
    assert cloture == _t("2026-09-18T15:30:00")
    assert _t("2026-09-18T04:44:47") < cloture


def test_un_run_de_cloture_normal_passe():
    """Contre-épreuve : le run de 15h45, celui qui fixe le cours, est accepté.
    Sans ça le contrôle refuserait le fonctionnement nominal."""
    cloture = derniere_cloture_ecoulee(_t("2026-09-22T19:32:00"))
    assert _t("2026-09-22T15:45:00") >= cloture
    assert _t("2026-09-22T18:03:00") >= cloture


# ── La borne, vue des deux côtés ───────────────────────────────────────────

def test_la_cloture_exacte_est_acceptee():
    """15h30 pile : la séance est close, le fichier peut la porter."""
    cloture = derniere_cloture_ecoulee(_t("2026-09-22T19:00:00"))
    assert _t("2026-09-22T15:30:00") >= cloture


def test_une_minute_avant_la_cloture_est_refusee():
    cloture = derniere_cloture_ecoulee(_t("2026-09-22T19:00:00"))
    assert _t("2026-09-22T15:29:00") < cloture


# ── Ce que la fonction calcule, indépendamment de toute panne ──────────────

def test_avant_la_cloture_du_jour_on_vise_la_veille():
    """À 10h du matin, la dernière clôture écoulée est celle d'hier — sinon le
    contrôle exigerait une clôture qui n'a pas encore eu lieu."""
    assert derniere_cloture_ecoulee(_t("2026-09-22T10:00:00")) \
        == _t("2026-09-21T15:30:00")


def test_juste_apres_la_cloture_on_vise_le_jour_meme():
    assert derniere_cloture_ecoulee(_t("2026-09-22T15:31:00")) \
        == _t("2026-09-22T15:30:00")


def test_minuit_vise_la_cloture_de_la_veille():
    assert derniere_cloture_ecoulee(_t("2026-09-22T00:16:00")) \
        == _t("2026-09-21T15:30:00")


@pytest.mark.parametrize("instant", [
    "2026-01-05T19:32:00", "2026-06-30T19:32:00", "2026-12-31T19:32:00",
])
def test_la_cloture_visee_est_toujours_passee(instant):
    """Propriété : quelle que soit la date, la clôture retenue est dans le
    passé. Une clôture future rendrait le contrôle impossible à satisfaire."""
    maintenant = _t(instant)
    assert derniere_cloture_ecoulee(maintenant) <= maintenant


@pytest.mark.parametrize("instant", [
    "2026-09-22T00:00:00", "2026-09-22T09:30:00", "2026-09-22T15:29:59",
    "2026-09-22T15:30:00", "2026-09-22T23:59:00",
])
def test_la_cloture_visee_date_de_moins_de_24_heures(instant):
    """Elle ne recule jamais de plus d'un jour : sinon un fichier périmé de
    plusieurs jours passerait le contrôle."""
    maintenant = _t(instant)
    ecart = (maintenant - derniere_cloture_ecoulee(maintenant)).total_seconds()
    assert 0 <= ecart < 24 * 3600


# ── Le contrôle, sur le chemin réel ────────────────────────────────────────

def test_le_controle_est_branche_dans_la_liste():
    """⚠️ Une fonction juste qui n'est appelée nulle part ne protège rien."""
    import verifier_seance as V
    source = Path(V.__file__).read_text(encoding="utf-8")
    assert "data.json écrit après la dernière clôture" in source
    assert "horodatage_couvre_la_cloture(" in source


# ── LA DÉCISION ELLE-MÊME, ET NON SA SEULE PRÉSENCE ────────────────────────
#
# ⚠️ Ces tests existent parce qu'un mutant a survécu. Inverser `>=` en `<=`
# dans le contrôle — donc accepter exactement ce qu'on voulait refuser — ne
# faisait rougir aucun test : je ne vérifiais que la présence de la ligne dans
# le source. Vérifier qu'une ligne existe n'est pas vérifier qu'elle marche.

def test_le_verdict_refuse_le_fichier_du_21_septembre():
    ok, detail = horodatage_couvre_la_cloture(
        "2026-09-21T11:44:32+01:00", _t("2026-09-21T22:07:00"))
    assert ok is False
    assert "ANTÉRIEUR" in detail


def test_le_verdict_refuse_le_fichier_du_18_septembre():
    ok, _ = horodatage_couvre_la_cloture(
        "2026-09-18T04:44:47+01:00", _t("2026-09-18T21:07:00"))
    assert ok is False


def test_le_verdict_accepte_un_run_de_cloture():
    ok, detail = horodatage_couvre_la_cloture(
        "2026-09-22T15:45:00+01:00", _t("2026-09-22T19:32:00"))
    assert ok is True
    assert "ANTÉRIEUR" not in detail


def test_le_verdict_accepte_la_cloture_exacte():
    ok, _ = horodatage_couvre_la_cloture(
        "2026-09-22T15:30:00+01:00", _t("2026-09-22T19:32:00"))
    assert ok is True


def test_le_verdict_refuse_une_minute_avant():
    ok, _ = horodatage_couvre_la_cloture(
        "2026-09-22T15:29:00+01:00", _t("2026-09-22T19:32:00"))
    assert ok is False


@pytest.mark.parametrize("mauvais", ["", None, "pas une date", "2026-13-45T99:99"])
def test_un_horodatage_illisible_vaut_echec(mauvais):
    """On ne présume pas de l'innocence d'un fichier qui ne sait pas dire
    quand il a été écrit."""
    ok, detail = horodatage_couvre_la_cloture(mauvais, _t("2026-09-22T19:32:00"))
    assert ok is False
    assert "illisible" in detail
