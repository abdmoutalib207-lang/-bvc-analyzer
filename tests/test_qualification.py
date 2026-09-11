"""Le contrat d'admissibilité : zéro, inconnu et sans objet ne se remplacent pas.

POURQUOI
────────
`inventaire.py` calculait sa médiane sur `(b.get("v") or 0)` : un volume
INCONNU devenait un zéro mesuré. Aucun volume absent n'existait dans les
données du 11/09 — les quatre médianes livrées restaient justes — mais la
convention contredisait le contrat du projet et aurait produit une erreur dès
la première donnée manquante.

La revue externe a demandé un contrôle qui empêche toute substitution
silencieuse. C'est le premier test de ce fichier, et il échouerait sur
l'ancienne écriture.
"""

import sys
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE / "pipeline"))
from qualification import (COUVERTURE_MINIMALE, Seance, Volume,  # noqa: E402
                           mediane_admissible, part_sans_transaction,
                           qualifier_seance, qualifier_volume)


# ── LE contrôle demandé ─────────────────────────────────────────────────

def test_un_volume_inconnu_n_est_jamais_remplace_par_zero():
    """Une valeur connue et une valeur inconnue : la médiane porte sur la SEULE
    valeur admissible, jamais sur [100, 0].

    Avec l'ancienne écriture `or 0`, la médiane de [100, None] valait 50.
    """
    r = mediane_admissible([100.0, None], fenetre=2, couverture_min=0.5)
    assert r["admissibles"] == 1
    assert r["inconnus"] == 1
    assert r["valeur"] == 100.0, (
        f"médiane {r['valeur']} — un inconnu a été compté comme un zéro")


def test_les_trois_etats_du_volume_sont_distincts():
    assert qualifier_volume(0)[0] is Volume.MESURE, "zéro est une MESURE"
    assert qualifier_volume(0)[1] == 0.0
    assert qualifier_volume(None)[0] is Volume.INCONNU
    assert qualifier_volume(None)[1] is None
    assert qualifier_volume(-5)[0] is Volume.INVALIDE
    assert qualifier_volume("beaucoup")[0] is Volume.INVALIDE
    assert qualifier_volume(float("nan"))[0] is Volume.INVALIDE


def test_zero_mesure_entre_dans_la_mediane():
    """Un zéro MESURÉ est une observation : il compte. Seul l'inconnu sort."""
    r = mediane_admissible([0.0, 0.0, 100.0], fenetre=3)
    assert r["admissibles"] == 3
    assert r["valeur"] == 0.0


# ── couverture insuffisante ─────────────────────────────────────────────

def test_une_couverture_insuffisante_rend_non_calculable():
    """None n'est pas zéro : une statistique non calculable ne doit pas se
    lire comme une mesure basse."""
    r = mediane_admissible([100.0] + [None] * 9, fenetre=10)
    assert r["couverture"] == 0.1
    assert r["calculable"] is False
    assert r["valeur"] is None
    assert "NON CALCULABLE" in r["motif"]


def test_la_couverture_minimale_est_nommee():
    assert 0 < COUVERTURE_MINIMALE <= 1
    r = mediane_admissible([1.0] * 6 + [None] * 4, fenetre=10)
    assert r["couverture_minimale"] == COUVERTURE_MINIMALE
    assert r["calculable"] is (0.6 >= COUVERTURE_MINIMALE)


def test_la_statistique_dit_toujours_sur_quoi_elle_porte():
    r = mediane_admissible([1.0, 2.0, None], fenetre=3)
    for cle in ("valeur", "admissibles", "inconnus", "invalides", "fenetre",
                "couverture", "calculable", "formule"):
        assert cle in r, f"la statistique ne déclare pas `{cle}`"


# ── ne pas confondre inconnu et sans transaction ────────────────────────

def test_la_part_d_inconnus_n_est_pas_la_part_sans_transaction():
    """La revue a demandé de ne pas présenter l'une comme l'autre."""
    r = part_sans_transaction([0.0, 0.0, 100.0, None, None])
    assert r["volume_mesure_nul"] == 2
    assert r["volume_inconnu"] == 2
    # part_mesure_nulle porte sur les MESURES (2 sur 3), pas sur les lignes.
    # ⚠️ Les parts sont arrondies à quatre décimales par le contrat : le test
    # le dit plutôt que de l'ignorer par une tolérance floue.
    assert r["part_mesure_nulle"] == round(2 / 3, 4)
    assert r["part_inconnue"] == round(2 / 5, 4)
    assert r["part_mesure_nulle"] != r["part_inconnue"]


# ── statut de séance ────────────────────────────────────────────────────

def test_un_calendrier_indecis_donne_inconnue_pas_sans_transaction():
    """⚠️ LE point de la revue sur le calendrier : en l'absence de preuve, le
    statut reste INCONNUE. Un volume nul ne prouve pas à lui seul que le
    marché était ouvert et le titre non échangé."""
    b = {"d": "2026-01-05", "c": 100.0, "v": 0}
    assert qualifier_seance(b, suspendu=False, marche_ferme=None) is Seance.INCONNUE
    assert qualifier_seance(b, suspendu=False, marche_ferme=False) is Seance.SANS_TRANSACTION
    assert qualifier_seance(b, suspendu=False, marche_ferme=True) is Seance.MARCHE_FERME


def test_la_suspension_prime_sur_tout():
    b = {"d": "2026-08-01", "c": 4350.0, "v": 0}
    assert qualifier_seance(b, suspendu=True, marche_ferme=False) is Seance.SUSPENDUE


def test_un_volume_positif_etablit_une_negociation():
    b = {"d": "2026-09-08", "c": 35.0, "v": 1200}
    assert qualifier_seance(b, suspendu=False, marche_ferme=None) is Seance.NEGOCIEE


# ── le calendrier versionné ─────────────────────────────────────────────

def test_le_calendrier_ne_declare_jamais_ouvert_par_defaut():
    import json
    c = json.loads((RACINE / "pipeline" / "calendrier_bvc.json").read_text(encoding="utf-8"))
    assert "non_confirme" in c["_statuts"], "le statut d'incertitude a disparu"
    assert "N'EST PAS" in c["_statuts"]["non_confirme"]
    for jour, e in c["jours"].items():
        assert e["statut"] in ("ferme", "ouvert", "non_confirme")
        # ⚠️ Seul un statut TRANCHÉ exige une source. « non confirmé » est
        # une absence de preuve : lui réclamer une source reviendrait à
        # pousser à en inventer une.
        if e["statut"] in ("ferme", "ouvert"):
            assert e.get("source"), f"{jour} : statut tranché sans source"
        else:
            assert e.get("source") is None, f"{jour} : non confirmé mais sourcé"
