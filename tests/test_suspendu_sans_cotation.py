"""Titre suspendu : la date du cours n'est jamais celle d'une rediffusion.

DLM (Delattre Levivier, en liquidation) est suspendu depuis 2023 et n'a
aucune bougie portant un volume. La source rediffusait 40 DH daté du jour, et
`prix_asof` le recopiait : le 13/10, DLM se comptait parmi les 67 titres
« cotés à la séance », contre 66 valeurs traitées par la synthèse.
"""
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

from update_data import reference_suspendu  # noqa: E402


def test_sans_aucune_cotation_la_date_devient_inconnue():
    r = reference_suspendu(40.0, "2026-10-13", [])
    assert r["prix_asof"] is None
    assert r["price"] == 40.0 and r["prix_diffuse"] == 40.0
    assert r["source"] is None


def test_bougies_a_volume_nul_ne_comptent_pas():
    bougies = [{"d": "2026-10-10", "c": 40.0, "v": 0}, {"d": "2026-10-13", "c": 40.0, "v": 0}]
    assert reference_suspendu(40.0, "2026-10-13", bougies)["prix_asof"] is None


def test_cas_cmt_la_derniere_cotation_reelle_reste_la_reference():
    bougies = [{"d": "2026-07-15", "c": 4480.0, "v": 1200},
               {"d": "2026-07-16", "c": 4501.0, "v": 67515},
               {"d": "2026-07-17", "c": 4350.0, "v": 0}]
    r = reference_suspendu(4350.0, "2026-09-10", bougies)
    assert (r["price"], r["prix_asof"], r["prix_diffuse"]) == (4501.0, "2026-07-16", 4350.0)
    assert r["source"] == "derniere_cotation_avant_suspension"


def test_reference_deja_alignee_ne_change_rien():
    bougies = [{"d": "2026-07-16", "c": 4501.0, "v": 67515}]
    r = reference_suspendu(4501.0, "2026-07-16", bougies)
    assert (r["price"], r["prix_asof"], r["prix_diffuse"], r["source"]) == (4501.0, "2026-07-16", None, None)


def test_sans_date_ni_cotation_rien_n_est_invente():
    r = reference_suspendu(40.0, None, [])
    assert r["prix_asof"] is None and r["prix_diffuse"] is None
