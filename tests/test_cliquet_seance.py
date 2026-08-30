"""`_cliquet_seance` — une séance déjà gravée ne peut pas reculer.

Incident du 28/08/2026, 15h59. CDG a servi la séance précédente pendant une
fenêtre transitoire après la clôture ; IDBourse ayant reculé en même temps,
l'arbitrage par la date (R3) n'a rien vu — il compare les sources ENTRE ELLES.
`data.json` est passé de 73 titres à la séance à zéro, et Addoha affichait
36,95 (clôture de la veille) au lieu de 36,05.

Ces tests figent le correctif ET les trois cas où le cliquet ne doit PAS jouer.
Un cliquet trop zélé bloquerait toute nouvelle séance — le remède serait pire.
"""


def test_cas_reel_du_28_aout(ud):
    """Toutes les sources reculent d'un jour : toutes les lignes sont écartées."""
    lp = {"ADH": {"price": 36.95, "asof": "2026-08-27"},
          "IAM": {"price": 103.2, "asof": "2026-08-27"}}
    retenue = ud._cliquet_seance(lp, "2026-08-27", plancher="2026-08-28")
    assert retenue == "2026-08-28", "la séance de référence doit rester au 28"
    assert lp == {}, "les lignes périmées doivent être écartées, pas conservées"


def test_ne_joue_pas_quand_la_source_avance(ud):
    """Cas nominal : la source apporte une séance plus récente."""
    lp = {"A": {"asof": "2026-08-28"}}
    assert ud._cliquet_seance(lp, "2026-08-28", plancher="2026-08-27") == "2026-08-28"
    assert len(lp) == 1


def test_ne_joue_pas_a_egalite(ud):
    """Même séance des deux côtés : rien ne doit bouger."""
    lp = {"A": {"asof": "2026-08-28"}}
    assert ud._cliquet_seance(lp, "2026-08-28", plancher="2026-08-28") == "2026-08-28"
    assert len(lp) == 1


def test_ne_joue_pas_sans_chandelles(ud):
    """Démarrage à froid : sans plancher connu, on ne bloque rien."""
    lp = {"A": {"asof": "2026-08-27"}}
    assert ud._cliquet_seance(lp, "2026-08-27", plancher="") == "2026-08-27"
    assert len(lp) == 1


def test_ne_joue_pas_sans_seance_annoncee(ud):
    """Sources muettes sur la date : on ne peut rien conclure, donc rien jeter."""
    lp = {"A": {"asof": "2026-08-27"}}
    assert ud._cliquet_seance(lp, None, plancher="2026-08-28") is None
    assert len(lp) == 1


def test_ecarte_seulement_les_lignes_en_retard(ud):
    """Le cliquet est chirurgical : une ligne à jour survit à un lot en retard."""
    lp = {"A": {"asof": "2026-08-28"}, "B": {"asof": "2026-08-27"}}
    retenue = ud._cliquet_seance(lp, "2026-08-27", plancher="2026-08-28")
    assert retenue == "2026-08-28"
    assert list(lp) == ["A"], "seule la ligne périmée devait partir"
