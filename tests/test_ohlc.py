"""Invariant OHLC : une bougie ne peut pas ouvrir hors de sa fourchette.

Défaut trouvé le 04/09/2026 en recoupant nos chandelles ADI avec la page
officielle `casablanca-bourse.com/market-data/cours`, imprimée par Abd Moutalib
depuis un poste marocain. Les dix séances affichées et leurs dix ouvertures
concordaient exactement avec les nôtres — mais plusieurs de nos bougies
portaient un plus haut INFÉRIEUR à leur ouverture :

    ADI 24/08  o=430,00  h=439,90  l=436,20  c=436,20   ← bas > ouverture
    ADI 28/08  o=438,00  h=434,10  l=430,00  c=430,00   ← haut < ouverture

Cause : l'étape 6c d'`update_data.py` amorçait `h` et `l` sur la seule clôture
(`"h": c_price, "l": c_price`), puis ne les étendait qu'avec les cours des runs
suivants. L'ouverture, qui vient d'une autre source, n'entrait jamais dans la
fourchette. Dès que o ≠ c, la bougie naissait impossible.

Portée mesurée avant correctif : **3 238 bougies sur 32 677 (9,9 %), 73 tickers
sur 74**. Le défaut vivait là depuis l'origine ; aucun test ne regardait la
cohérence interne d'une bougie, seulement ses dates et ses ruptures de prix.

⚠️ La réparation n'invente rien. Le titre a coté à `o` et à `c`, donc son vrai
plus haut valait au moins `max(o, c)`. Les bornes réparées restent des
minorants de l'amplitude réelle — c'est le seul élargissement démontrable sans
donnée intraday, et il est strictement plus juste que l'état d'avant.
"""

from seance import reparer_ohlc


def _b(d, o, h, l, c, v=100):
    return {"d": d, "o": o, "h": h, "l": l, "c": c, "v": v}


def _relire(dossier, ticker):
    import json
    return json.loads((dossier / f"{ticker}.json").read_text(encoding="utf-8"))


def test_haut_inferieur_a_l_ouverture_est_corrige(dossier_chandelles):
    """Le cas ADI du 28/08 : le titre a baissé, le haut est resté sous l'open."""
    d = dossier_chandelles({"ADI": [_b("2026-08-28", 438.0, 434.1, 430.0, 430.0)]})
    n, fichiers = reparer_ohlc(candles_dir=d)
    assert (n, fichiers) == (1, 1)
    b = _relire(d, "ADI")[0]
    assert b["h"] == 438.0, "le plus haut doit au moins atteindre l'ouverture"
    assert b["l"] == 430.0, "le plus bas était déjà correct, il ne bouge pas"


def test_bas_superieur_a_l_ouverture_est_corrige(dossier_chandelles):
    """Le cas ADI du 24/08 : le titre a monté, le bas est resté au-dessus."""
    d = dossier_chandelles({"ADI": [_b("2026-08-24", 430.0, 439.9, 436.2, 436.2)]})
    n, _ = reparer_ohlc(candles_dir=d)
    assert n == 1
    b = _relire(d, "ADI")[0]
    assert b["l"] == 430.0
    assert b["h"] == 439.9, "un plus haut déjà supérieur n'est pas rabaissé"


def test_une_bougie_coherente_n_est_pas_touchee(dossier_chandelles):
    """Le correctif ne doit rien réécrire quand l'invariant tient déjà."""
    d = dossier_chandelles({"OK": [_b("2026-09-03", 100.0, 105.0, 98.0, 102.0),
                                   _b("2026-09-02", 100.0, 100.0, 100.0, 100.0)]})
    n, fichiers = reparer_ohlc(candles_dir=d)
    assert (n, fichiers) == (0, 0)


def test_simulation_n_ecrit_pas(dossier_chandelles):
    """`--dry-run` doit compter sans modifier — on l'utilise pour mesurer."""
    d = dossier_chandelles({"ADI": [_b("2026-08-28", 438.0, 434.1, 430.0, 430.0)]})
    n, _ = reparer_ohlc(candles_dir=d, dry_run=True)
    assert n == 1
    assert _relire(d, "ADI")[0]["h"] == 434.1, "le fichier ne doit pas bouger"


def test_bougie_incomplete_est_ignoree_sans_planter(dossier_chandelles):
    """Une bougie sans `h` ne doit pas faire tomber le balayage.

    L'historique contient des points venus de sources qui ne publient que la
    clôture. Les écarter est correct ; planter dessus ne l'est pas.
    """
    d = dossier_chandelles({"PARTIEL": [{"d": "2026-09-01", "c": 100.0},
                                        _b("2026-09-02", 50.0, 40.0, 40.0, 40.0)]})
    n, _ = reparer_ohlc(candles_dir=d)
    assert n == 1, "la bougie complète est corrigée, l'incomplète ignorée"
    assert _relire(d, "PARTIEL")[0] == {"d": "2026-09-01", "c": 100.0}


def test_le_correctif_est_idempotent(dossier_chandelles):
    """Relancer le balayage ne doit plus rien trouver — sinon il dérive."""
    d = dossier_chandelles({"ADI": [_b("2026-08-28", 438.0, 434.1, 430.0, 430.0)]})
    reparer_ohlc(candles_dir=d)
    n, _ = reparer_ohlc(candles_dir=d)
    assert n == 0


def test_les_extremes_restent_des_minorants(dossier_chandelles):
    """⚠️ Le contrat : on élargit, on ne rétrécit jamais.

    Un plus haut supérieur à `max(o, c)` est une vraie mesure intraday. Le
    ramener à `max(o, c)` détruirait de l'information — et fausserait
    Bollinger et le Stochastique, qui lisent ces bornes.
    """
    d = dossier_chandelles({"LARGE": [_b("2026-09-03", 100.0, 130.0, 70.0, 102.0)]})
    reparer_ohlc(candles_dir=d)
    b = _relire(d, "LARGE")[0]
    assert (b["h"], b["l"]) == (130.0, 70.0)
