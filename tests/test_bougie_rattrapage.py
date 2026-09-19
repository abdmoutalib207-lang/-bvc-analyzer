#!/usr/bin/env python3
"""Une séance échue sans bougie doit pouvoir en recevoir une — une seule fois.

⚠️ CE QUI EST ARRIVÉ LE 18/09/2026
──────────────────────────────────
    18/09  tous les runs de séance échouent aux contrôles bloquants ;
           les deux runs tardifs sont écartés par la porte horaire.
           → aucune bougie du 18/09 n'est commitée
    19/09  la séance cotée est le 18, « pas aujourd'hui » → refus d'écrire
           → le trou devient DÉFINITIF

Le cours du 18/09 était publié dans `data.json` — 79 titres, sources CDG et
IDBourse, non périmés. Mais aucun graphique, RSI ou moyenne mobile ne le
connaissait : les chandelles s'arrêtaient au 16/09. Le contrôle quotidien
signalait l'écart tous les jours, et il avait raison.

⚠️ LA LIGNE QUE CE FICHIER DÉFEND
─────────────────────────────────
Le rattrapage **ajoute ce qui manque ; il ne réécrit jamais le passé.** C'est
toute la différence entre combler un trou et rouvrir une clôture arrêtée. Le
rafraîchissement — extrêmes qui s'étendent, clôture qui suit — reste réservé à
la séance du jour, la seule qui évolue encore.

Parade appliquée à chaque test : « qu'est-ce qui, demain, le ferait rougir sans
que rien soit cassé ? » Aucune date n'est ici un instantané du dépôt — les
séances sont des paramètres, et la règle vaut pour n'importe quel calendrier.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

import update_data as moteur  # noqa: E402


# ── La séance du jour : comportement historique, inchangé ───────────────────

def test_la_seance_du_jour_se_rafraichit_quand_elle_est_deja_la():
    """⚠️ Non négociable : le 10/08, 57 bougies s'étaient figées sur un cours
    de milieu de séance parce que l'étape passait son tour dès qu'un point du
    jour existait. La séance du jour évolue jusqu'à la clôture."""
    assert moteur.bougie_a_ecrire("2026-09-18", "2026-09-18",
                                  "2026-09-18") == "rafraichir"


def test_la_seance_du_jour_s_ajoute_quand_elle_manque():
    assert moteur.bougie_a_ecrire("2026-09-18", "2026-09-18",
                                  "2026-09-16") == "ajouter"


def test_la_seance_du_jour_s_ajoute_sur_une_serie_vide():
    assert moteur.bougie_a_ecrire("2026-09-18", "2026-09-18",
                                  None) == "ajouter"


# ── Le rattrapage : ce que le 18/09 exigeait ───────────────────────────────

def test_une_seance_echue_absente_est_rattrapee():
    """LE CAS DU 18/09. Au 19/09, la série s'arrête au 16 : le 18 doit entrer.
    Sans cette ligne, la bougie d'une journée dont les runs ont tous échoué est
    perdue pour toujours."""
    assert moteur.bougie_a_ecrire("2026-09-18", "2026-09-19",
                                  "2026-09-16") == "ajouter"


def test_une_seance_echue_est_rattrapee_sur_une_serie_vide():
    assert moteur.bougie_a_ecrire("2026-09-18", "2026-09-19",
                                  None) == "ajouter"


def test_le_rattrapage_ne_rouvre_pas_une_cloture_deja_arretee():
    """⚠️ LA GARDE CENTRALE. La séance échue est déjà écrite : on n'y touche
    plus. Un run tardif — ou vingt — ne peut pas revenir bousculer une clôture
    arrêtée. C'est ce qui distingue « combler un trou » de « réécrire »."""
    assert moteur.bougie_a_ecrire("2026-09-18", "2026-09-19",
                                  "2026-09-18") == "ignorer"


def test_le_rattrapage_ne_recule_pas_derriere_une_serie_plus_avancee():
    """Si la série connaît déjà le 21, une source qui redate le 18 ne doit
    surtout pas venir réécrire derrière elle."""
    assert moteur.bougie_a_ecrire("2026-09-18", "2026-09-22",
                                  "2026-09-21") == "ignorer"


# ── Ce qui reste interdit ──────────────────────────────────────────────────

def test_une_seance_future_est_toujours_ignoree():
    """Aucune source ne doit pouvoir fabriquer une séance qui n'a pas eu lieu —
    c'est la protection d'origine de l'étape 6c, et elle ne bouge pas."""
    assert moteur.bougie_a_ecrire("2026-09-21", "2026-09-19",
                                  "2026-09-16") == "ignorer"
    assert moteur.bougie_a_ecrire("2026-09-21", "2026-09-19",
                                  None) == "ignorer"


def test_une_seance_inconnue_est_ignoree():
    """IDBourse muet : pas de date, donc pas de bougie."""
    for vide in ("", None):
        assert moteur.bougie_a_ecrire(vide, "2026-09-19",
                                      "2026-09-16") == "ignorer"


# ── Les propriétés, indépendantes de toute date écrite en dur ──────────────

@pytest.mark.parametrize("seance,aujourd_hui", [
    ("2026-01-05", "2026-01-05"), ("2025-12-31", "2026-01-02"),
    ("2026-07-16", "2026-09-19"), ("2026-09-18", "2026-09-19"),
])
def test_une_seance_deja_ecrite_n_est_jamais_reecrite(seance, aujourd_hui):
    """Propriété : quelle que soit la date, une séance ÉCHUE déjà présente est
    ignorée. Seule la séance du jour a le droit d'être rafraîchie."""
    verdict = moteur.bougie_a_ecrire(seance, aujourd_hui, seance)
    attendu = "rafraichir" if seance == aujourd_hui else "ignorer"
    assert verdict == attendu


@pytest.mark.parametrize("derniere", [None, "2020-01-01", "2026-09-16"])
def test_toute_seance_echue_manquante_est_rattrapable(derniere):
    """Propriété miroir : tant que la série ne connaît pas encore la séance,
    le rattrapage doit l'accepter — sinon le trou du 18/09 se reproduit."""
    assert moteur.bougie_a_ecrire("2026-09-18", "2026-09-19",
                                  derniere) == "ajouter"


def test_le_verdict_est_toujours_l_un_des_trois():
    """Aucune valeur de retour surprise : l'appelant s'y fie pour brancher."""
    permis = {"rafraichir", "ajouter", "ignorer"}
    for s in ("", "2026-09-17", "2026-09-18", "2026-09-19", "2026-09-30"):
        for d in (None, "2026-09-15", "2026-09-18", "2026-09-19"):
            assert moteur.bougie_a_ecrire(s, "2026-09-18", d) in permis
