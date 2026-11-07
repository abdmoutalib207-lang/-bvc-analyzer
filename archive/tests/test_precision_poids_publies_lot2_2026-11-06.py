"""La précision publiée doit permettre de recomposer la note sans la modifier."""
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
    out = u.compute_v53('MUT', 7.2, 1.9, 0, 0, context)
    # Deux piliers : le pilier NLP (`n`) est retiré du moteur le 28/10/2026.
    expected = {short: round(weights[key] * 100, 2) for short, key in
                [('f', 'fondamental'), ('t', 'technique')]}
    assert out['poids'] == expected
    for short, key in [('f', 'fondamental'), ('t', 'technique')]:
        assert out['poids'][short] / 100 == pytest.approx(weights[key], abs=1e-12)
    # Le moteur garde sa formule originale : seule sa description est précisée.
    assert out['v53'] == round(1.9 * weights['fondamental'] + 7.2 * weights['technique'], 2)
    recomposed = (out['score_fond'] * expected['f'] + out['score_tech'] * expected['t']) / 100
    assert abs(out['v53'] - recomposed) <= .005000001
    assert out['bonus'] == []


# ⚠️ 03/11/2026 — pondération sans heure (accord R8 d'Abd Moutalib). Le
# contexte des trois cas du 16/10 (séance ouverte, MASI < −5 % depuis janvier)
# donnait 71,43 / 28,57 ; le bonus « marché fermé » s'appliquant désormais à
# toute heure, il donne 77,92 / 22,08 et les notes 3,41 · 3,30 · 6,84
# deviennent 3,07 · 2,98 · 7,11 — celles que publiait déjà le run du soir.
# Le contrôle « les entiers 71/29 dépassaient la tolérance de l'audit »
# portait sur l'ancienne pondération ; il n'a plus d'objet et sort du test.
# Reste ce qui compte : deux décimales publiées recomposent la note à
# l'arrondi près.
@pytest.mark.parametrize('symbol,fundamental,technical,score', [
    ('MUT', 1.9, 7.2, 3.07), ('CAR', 1.9, 6.8, 2.98), ('SMI', 8.05, 3.8, 7.11),
])
@pytest.mark.parametrize('statut', ['OPEN', 'CLOSED', 'PRE_MARKET'])
def test_regression_des_trois_cas_bloquants_du_16_octobre(symbol, fundamental, technical, score, statut):
    out = u.compute_v53(symbol, technical, fundamental, 0, 0,
                        {'market_status': statut, 'masi_ytd': -6})
    assert out['poids'] == {'f': 77.92, 't': 22.08}
    assert out['v53'] == score
    exact = (fundamental * out['poids']['f'] + technical * out['poids']['t']) / 100
    assert abs(exact - score) <= .005000001
