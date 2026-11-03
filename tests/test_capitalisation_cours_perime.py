"""Cours des chandelles et capitalisation servie périmée (03/11/2026).

Le matin du 03/11, LHM n'avait pas encore coté : cours des chandelles 1 560
(bulletin CDG du 02/11 concordant). IDBourse servait 41 005 MDHS, soit 1 750
× le nombre officiel — son propre cours périmé. Le moteur préférait la valeur
servie dès que notre cours n'était pas vivant ; le contrôle bloquant
(test_fonds_propres) refusait alors la publication.

La valeur servie ne garde le dernier mot que si une reprise sur référence
remise à neuf est inscrite au registre SUSPENSIONS (CMT, R11).
"""
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))
sys.path.insert(0, str(RACINE / "pipeline"))

import update_data as ud  # noqa: E402


def test_cours_des_chandelles_sans_reprise_inscrite_la_capitalisation_est_calculee():
    n = ud._actions_bourse("LHM")
    assert n, "LHM doit figurer au relevé officiel"
    cap, src = ud._capitalisation("LHM", 1560.0, 41005, "candles")
    assert src == "calculee_bourse_officielle"
    assert cap == ud._arrondi_cap(1560.0 * n / 1e6)


def test_reprise_inscrite_la_valeur_servie_garde_le_dernier_mot():
    assert ud._reprise_sur_reference_inscrite("CMT")
    assert ud._capitalisation("CMT", 3800.0, 3727, "candles") == (3727, "servie")


def test_seuls_les_titres_au_registre_portent_une_reprise_sur_reference():
    assert not ud._reprise_sur_reference_inscrite("LHM")
    assert not ud._reprise_sur_reference_inscrite("XXX")
