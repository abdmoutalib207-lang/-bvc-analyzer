"""La précision publiée doit permettre de recomposer la note sans la modifier."""
from unittest.mock import patch

import pytest

import update_data as u


@pytest.mark.parametrize('context', [
    {}, {'market_status': 'CLOSED'}, {'market_status': 'PRE_MARKET'},
    {'market_status': 'OPEN', 'masi_ytd': -6},
    {'market_status': 'OPEN', 'masi_ytd': 11},
    {'market_status': 'OPEN', 'has_results': True},
    {'market_status': 'CLOSED', 'masi_ytd': -6},
    {'market_status': 'OPEN', 'tech_non_fiable': {'motif': 'fixing'}},
])
def test_export_conserve_la_precision_reelle_sans_changer_la_note(context):
    weights = u.get_weights(context)
    with patch.object(u, '_apport_actualites', return_value=0):
        out = u.compute_v53('MUT', 7.2, 1.9, 0, 0, context)
    expected = {short: round(weights[key] * 100, 2) for short, key in
                [('f', 'fondamental'), ('n', 'comportemental'), ('t', 'technique')]}
    assert out['poids'] == expected
    for short, key in [('f', 'fondamental'), ('n', 'comportemental'), ('t', 'technique')]:
        assert out['poids'][short] / 100 == pytest.approx(weights[key], abs=1e-12)
    # Le moteur garde sa formule originale : seule sa description est précisée.
    assert out['v53'] == round(1.9 * weights['fondamental'] + 7.2 * weights['technique'], 2)
    recomposed = (out['score_fond'] * expected['f'] + out['score_tech'] * expected['t']) / 100
    assert abs(out['v53'] - recomposed) <= .005000001
    assert out['bonus'] == []


@pytest.mark.parametrize('symbol,fundamental,technical,score', [
    ('MUT', 1.9, 7.2, 3.41), ('CAR', 1.9, 6.8, 3.30), ('SMI', 8.05, 3.8, 6.84),
])
def test_regression_des_trois_cas_bloquants_du_16_octobre(symbol, fundamental, technical, score):
    with patch.object(u, '_apport_actualites', return_value=0):
        out = u.compute_v53(symbol, technical, fundamental, 0, 0,
                            {'market_status': 'OPEN', 'masi_ytd': -6})
    assert out['poids'] == {'f': 71.43, 'n': 0.0, 't': 28.57}
    assert out['v53'] == score
    exact = (fundamental * out['poids']['f'] + technical * out['poids']['t']) / 100
    assert abs(exact - score) <= .005000001
    # Les entiers antérieurs dépassaient la tolérance de l'audit (0,02).
    assert abs((fundamental * 71 + technical * 29) / 100 - score) > .02
