"""RSI sur les séances RÉELLEMENT ÉCHANGÉES — 30/09/2026 (accord d'Abd Moutalib).

Un jour sans transaction n'est pas une cotation. Mesuré contre TradingView
(77 titres à clôture identique) : sur toutes les séances, 6 titres peu
liquides s'écartaient de plus de 5 points ; sur les seules séances
échangées, aucun. ⚠️ La raison est la définition, pas la coïncidence.
"""

import json
from pathlib import Path

import pandas as pd

from pipeline.seance import clotures_echangees

RACINE = Path(__file__).resolve().parent.parent


def test_ecarte_les_jours_sans_volume_et_les_recopies():
    c = [10, 10, 11, 11, 12]
    v = [5, 0, 3, 3, 4]
    assert list(clotures_echangees(c, v, c, c, c)) == [10, 11, 12]


def test_meme_cours_autre_quantite_est_une_vraie_seance():
    c = [10, 10]
    assert list(clotures_echangees(c, [5, 7], c, c, c)) == [10, 10]


def test_sans_information_de_volume_on_ne_juge_pas():
    assert list(clotures_echangees([1, 2, 3], None)) == [1, 2, 3]
    assert list(clotures_echangees([1, 2, 3], [0, 0, 0])) == [1, 2, 3]


def test_les_quatre_calculs_du_rsi_appliquent_la_regle():
    for f in ("update_data.py", "pipeline/collect_history_bvcscrap.py",
              "pipeline/recalculer_cache.py"):
        src = (RACINE / f).read_text(encoding="utf-8")
        assert "clotures_echangees(" in src, f
    moteur = (RACINE / "update_data.py").read_text(encoding="utf-8")
    assert moteur.count("calc_rsi(clotures_echangees(") == 2
    assert "1 if n_echangees >= 15 else 0" in moteur


def _rsi_wilder_echangees(ticker):
    """Wilder sur les seules séances échangées, écrit à part du moteur."""
    b = json.loads((RACINE / "pipeline" / "candles" / f"{ticker}.json").read_text(encoding="utf-8"))
    ech = list(clotures_echangees([x["c"] for x in b], [x.get("v") for x in b],
                                  [x.get("h") for x in b], [x.get("l") for x in b],
                                  [x.get("o") for x in b]))
    if len(ech) < 15:
        return None
    d = [ech[i] - ech[i - 1] for i in range(1, len(ech))]
    g = [max(x, 0) for x in d]; p = [max(-x, 0) for x in d]
    ag, ap = sum(g[:14]) / 14, sum(p[:14]) / 14
    for i in range(14, len(d)):
        ag = (ag * 13 + g[i]) / 14; ap = (ap * 13 + p[i]) / 14
    return 100 - 100 / (1 + ag / ap)


def test_dar_n_a_pas_de_rsi_fabrique():
    """DAR valait 76,8 sur 70 bougies dont 8 échangées : RSI fabriqué.
    Depuis l'export de l'opérateur (03/10/2026) : 736 bougies, 104 échangées —
    le RSI redevient calculable, mais sur les seules séances échangées."""
    h = json.loads((RACINE / "pipeline" / "historical_data.json").read_text(encoding="utf-8"))
    attendu = _rsi_wilder_echangees("DAR")
    rsi = (h.get("DAR") or {}).get("rsi")
    if attendu is None:
        assert rsi is None
    else:
        assert rsi is not None and abs(rsi - attendu) < 0.1


def test_rsi_de_bal_sur_ses_seances_echangees():
    """BAL : 63,9 sur toutes les séances, 50,7 sur les séances échangées
    (TradingView : 50,7). Recalculé ici par une formule de Wilder écrite à part."""
    b = json.loads((RACINE / "pipeline" / "candles" / "BAL.json").read_text(encoding="utf-8"))
    ech = list(clotures_echangees([x["c"] for x in b], [x.get("v") for x in b],
                                  [x.get("h") for x in b], [x.get("l") for x in b],
                                  [x.get("o") for x in b]))
    d = [ech[i] - ech[i - 1] for i in range(1, len(ech))]
    g = [max(x, 0) for x in d]; p = [max(-x, 0) for x in d]
    ag, ap = sum(g[:14]) / 14, sum(p[:14]) / 14
    for i in range(14, len(d)):
        ag = (ag * 13 + g[i]) / 14; ap = (ap * 13 + p[i]) / 14
    attendu = 100 - 100 / (1 + ag / ap)
    h = json.loads((RACINE / "pipeline" / "historical_data.json").read_text(encoding="utf-8"))
    assert abs(h["BAL"]["rsi"] - attendu) < 0.1
