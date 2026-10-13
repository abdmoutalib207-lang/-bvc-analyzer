"""Lecture en séance : ce que le briefing ne doit pas affirmer avant 15h30.

1. Les indices sectoriels ne sont rafraîchis par la source qu'en fin de
   séance. Mesuré sur les dix lectures de mi-journée archivées (01/10 →
   13/10) : 23/23 au cours de la veille, à chaque fois ; 0 à 3/23 à la
   clôture. « 0 en hausse, 0 en baisse » n'était pas une mesure (R9).
2. La dernière valeur du MASI à 13h45 n'est pas une clôture : le 13/10 la
   lecture de mi-journée annonçait « clôture 17\u00a0175,05 », la séance a clos à
   17\u00a0041,91.
"""
from __future__ import annotations

import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

from pipeline import briefing as bf  # noqa: E402

SEANCE = "2026-10-13"


def _secteurs(n_figes, n=23):
    return [{"code": f"S{i}", "libelle": f"SECTEUR {i}", "cours": 100.0 + (0 if i < n_figes else i),
             "cours_veille": 100.0, "variation_pct": 0.0 if i < n_figes else round(i, 2)}
            for i in range(n)]


def _traj(clo, rejoint=True):
    return {"seance": SEANCE, "veille": 16954.4971, "ouverture": 16953.1678,
            "heure_ouverture": "09:30:00", "plus_haut": 17176.4013,
            "heure_plus_haut": "13:49:58", "plus_bas": 16951.1774,
            "heure_plus_bas": "09:31:16", "cloture": clo,
            "serie_jusqu_a": "13:41:21", "serie_rejoint_cloture": rejoint}


# ── Secteurs figés ─────────────────────────────────────────────────────────

def test_23_sur_23_a_la_veille_sont_figes():
    assert bf.secteurs_figes(_secteurs(23))


def test_trois_sur_23_inchanges_a_la_cloture_ne_sont_pas_figes():
    # Le maximum observé à la clôture sur dix séances.
    assert not bf.secteurs_figes(_secteurs(3))


def test_liste_vide_n_est_pas_figee():
    assert not bf.secteurs_figes([])


def _enrichir(secteurs, traj=None):
    b = {"seance": SEANCE, "constats": [], "non_mesurable": []}
    ctx = {"seance_marche": {SEANCE: {"secteurs": secteurs, "trajectoire": traj, "matieres": []}}}
    return bf.enrichir(b, [], ctx)


def test_secteurs_figes_ne_produisent_aucun_constat():
    b = _enrichir(_secteurs(23))
    assert b["secteurs"] == []
    assert not any("Indices sectoriels" in c for c in b["constats"])
    assert any("fin de séance" in x for x in b["non_mesurable"])


def test_secteurs_rafraichis_restent_publies():
    b = _enrichir(_secteurs(1))
    assert len(b["secteurs"]) == 23
    assert any(c.startswith("Indices sectoriels (23 servis)") for c in b["constats"])


# ── « Clôture » en séance ──────────────────────────────────────────────────

def test_en_seance_la_derniere_valeur_n_est_pas_une_cloture():
    p = bf.phrase_trajectoire(_traj(17175.0521), en_seance=True)
    assert "dernière valeur relevée 17\u00a0175,05 (13:41:21)" in p
    assert "clôture" not in p.replace("clôture de la veille", "")


def test_heure_omise_si_la_serie_ne_rejoint_pas_la_valeur():
    p = bf.phrase_trajectoire(_traj(17175.0521, rejoint=False), en_seance=True)
    assert "dernière valeur relevée 17\u00a0175,05 pour" in p


def test_apres_la_seance_la_cloture_reste_une_cloture():
    p = bf.phrase_trajectoire(_traj(17041.9131))
    assert "clôture 17\u00a0041,91 pour une veille" in p


def test_dater_en_seance_reecrit_la_phrase():
    b = _enrichir(_secteurs(23), _traj(17175.0521))
    assert any("clôture 17\u00a0175,05" in c for c in b["constats"])
    b = bf.dater(b, SEANCE, 1345)
    assert not any("clôture 17\u00a0175,05" in c for c in b["constats"])
    assert any("dernière valeur relevée 17\u00a0175,05" in c for c in b["constats"])


def test_dater_apres_la_cloture_ne_touche_rien():
    b = _enrichir(_secteurs(1), _traj(17041.9131))
    avant = list(b["constats"])
    assert bf.dater(b, SEANCE, 1845)["constats"] == avant
