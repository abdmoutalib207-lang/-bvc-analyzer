"""`_arbitrer_masi` — l'indice suit la même règle que les cours : la DATE arbitre.

Le 28/08/2026, les prix étaient passés à CDG mais l'indice était resté sur
IDBourse, qui accusait un jour de retard. La preuve tenait dans la charge utile :
le `CoursVeille` de CDG valait 19046.9191, exactement ce qu'IDBourse donnait
comme valeur « du jour ».

R3 : la date tranche, jamais la préférence. Ces tests figent les deux sens.
"""


def test_cdg_plus_fraiche_gagne(ud):
    cdg = {"value": 18931.06, "chg": -0.61, "asof": "2026-08-28"}
    idb = {"value": 19046.92, "chg": 0.0, "asof": "2026-08-27", "stale": True}
    r = ud._arbitrer_masi(cdg, idb, "2026-08-28")
    assert r["value"] == 18931.06
    assert r["stale"] is False


def test_idbourse_reprend_la_main_si_cdg_retarde(ud):
    """L'arbitrage doit fonctionner DANS LES DEUX SENS, sinon c'est une préférence."""
    cdg = {"value": 18000.0, "chg": 0.0, "asof": "2026-08-26"}
    idb = {"value": 19046.92, "chg": 0.3, "asof": "2026-08-28", "stale": False}
    assert ud._arbitrer_masi(cdg, idb, "2026-08-28")["value"] == 19046.92


def test_cdg_gagne_a_egalite_de_date(ud):
    """À date égale, la société de bourse agréée prime sur l'agrégateur."""
    cdg = {"value": 18931.06, "chg": -0.61, "asof": "2026-08-28"}
    idb = {"value": 18931.00, "chg": -0.61, "asof": "2026-08-28", "stale": False}
    assert ud._arbitrer_masi(cdg, idb, "2026-08-28")["value"] == 18931.06


def test_indice_en_retard_sur_les_cours_est_marque_perime(ud):
    cdg = {"value": 18931.06, "chg": -0.61, "asof": "2026-08-27"}
    r = ud._arbitrer_masi(cdg, None, "2026-08-28")
    assert r["stale"] is True, "un indice antérieur à la séance des cours est périmé"


def test_idbourse_seule_quand_cdg_est_muette(ud):
    idb = {"value": 19046.92, "chg": 0.0, "asof": "2026-08-27", "stale": True}
    assert ud._arbitrer_masi(None, idb, "2026-08-28") == idb


def test_stale_est_calcule_chez_nous_jamais_repris_de_la_source(ud):
    """Leçon du 14/08 : le `stale` d'IDBourse veut dire « pas en direct ».

    Il vaut vrai dès la clôture — donc en permanence pour un produit publié
    avant l'ouverture. S'y fier allumait l'alerte en permanence, et une alarme
    toujours allumée n'alerte plus.
    """
    cdg = {"value": 18931.06, "chg": -0.61, "asof": "2026-08-28"}
    idb = {"value": 19046.92, "chg": 0.0, "asof": "2026-08-27", "stale": True}
    assert ud._arbitrer_masi(cdg, idb, "2026-08-28")["stale"] is False
