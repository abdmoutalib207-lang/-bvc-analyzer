import json
import pytest
from pipeline.session_candles import preparer
from pipeline.seance_source import lire_date_cdg
from pipeline.masi_history import enregistrer
from pipeline.porte_rattrapage import decider

Q = dict(open=400, high=400, low=376, price=377, vol=78887, asof='2026-09-18', src='cdg')

def test_vrais_extremes_rattrapage_sans_ecriture_et_idempotence(tmp_path):
    p = tmp_path/'ADI.json'
    serie = preparer({'ADI': Q}, '2026-09-18', '2026-09-19', tmp_path, ['ADI'])['ADI']
    assert serie == [dict(d='2026-09-18', o=400,h=400,l=376,c=377,v=78887)]
    assert not p.exists()
    p.write_text(json.dumps(serie))
    assert not preparer({'ADI': Q}, '2026-09-18', '2026-09-19', tmp_path, ['ADI'])

@pytest.mark.parametrize('patch', [{'high':None}, {'low':390}, {'vol':0}, {'vol':1.5},
                                 {'open':float('nan')}, {'src':'idbourse'}, {'asof':'2026-09-16'}])
def test_cotation_incomplete_ou_non_recevable_ne_fabrique_rien(tmp_path, patch):
    assert not preparer({'ADI':{**Q, **patch}}, '2026-09-18','2026-09-19',tmp_path,['ADI'])

def test_suspension_annulation_et_futur(tmp_path):
    assert not preparer({'CMT':{**Q,'asof':'2026-09-15'}}, '2026-09-15','2026-09-19',tmp_path,['CMT'])
    for d in ['2026-09-17','2026-09-21']:
        assert not preparer({'ADI':{**Q,'asof':d}}, d,'2026-09-19',tmp_path,['ADI'])

def test_source_exterieure_ne_prend_pas_les_chandelles_comme_reference():
    rows=[dict(DateDernierCours='18/09/2026',Cours=377,QteEchangee=1)]*30
    assert lire_date_cdg(rows,'2026-09-19')=='2026-09-18'
    with pytest.raises(ValueError): lire_date_cdg([], '2026-09-19')

def test_rattrapage_apres_minuit_si_graphiques_manquent():
    d={'updated':'2026-09-19T01:00:00+0100','tickers':[{'_meta':{'prix_asof':'2026-09-18'}}]}
    assert decider(119,'2026-09-19',d,'2026-09-18',0)[0]
    assert not decider(119,'2026-09-19',d,'2026-09-18',66)[0]

def test_masi_conserve_la_trace_du_retrait_du_17(tmp_path):
    p=tmp_path/'masi.json';trace=[{'date':'2026-09-17','motif':'annulée'}]
    p.write_text(json.dumps({'seances':{'2026-09-16':17983.9995},'_retraits':trace}))
    assert enregistrer(17592.4556,'2026-09-18',chemin=p)
    assert json.loads(p.read_text())['_retraits']==trace


# ── 05/10/2026 : une séance échue peut COMPLÉTER son volume, rien d'autre ──
# HPS, chiffres réels : CDG servait 5 851 titres à 16h55, 7 818 à 17h15
# (bulletin CDG du 05/10 : 7 818). Clôture 560 dans les deux cas.
H_PARTIEL = dict(d='2026-10-05', o=580, h=590, l=550, c=560, v=5851)
H_SOURCE = dict(open=580, high=590, low=550, price=560, vol=7818,
                asof='2026-10-05', src='cdg')


def test_le_lendemain_le_volume_d_une_seance_echue_se_complete(tmp_path):
    (tmp_path / 'HPS.json').write_text(json.dumps([H_PARTIEL]))
    serie = preparer({'HPS': H_SOURCE}, '2026-10-05', '2026-10-06', tmp_path, ['HPS'])['HPS']
    assert serie == [dict(d='2026-10-05', o=580, h=590, l=550, c=560, v=7818)]


@pytest.mark.parametrize('patch', [{'price': 561, 'high': 590},   # clôture différente
                                   {'vol': 5851},                  # volume identique
                                   {'vol': 5000},                  # volume plus petit
                                   {'src': 'bmce'}])               # autre source
def test_une_seance_echue_ne_se_reecrit_pas_autrement(tmp_path, patch):
    (tmp_path / 'HPS.json').write_text(json.dumps([H_PARTIEL]))
    assert not preparer({'HPS': {**H_SOURCE, **patch}}, '2026-10-05', '2026-10-06',
                        tmp_path, ['HPS'])


def test_une_seance_plus_ancienne_que_la_derniere_bougie_reste_immuable(tmp_path):
    (tmp_path / 'HPS.json').write_text(json.dumps(
        [H_PARTIEL, dict(d='2026-10-06', o=560, h=565, l=555, c=562, v=900)]))
    assert not preparer({'HPS': H_SOURCE}, '2026-10-05', '2026-10-07', tmp_path, ['HPS'])


def test_la_completion_ne_touche_ni_l_ouverture_ni_les_extremes(tmp_path):
    (tmp_path / 'HPS.json').write_text(json.dumps([H_PARTIEL]))
    autre = {**H_SOURCE, 'open': 575, 'high': 600, 'low': 545}
    serie = preparer({'HPS': autre}, '2026-10-05', '2026-10-06', tmp_path, ['HPS'])['HPS']
    assert serie == [{**H_PARTIEL, 'v': 7818}]


def test_une_correction_receptionnee_prime_sans_bloquer(tmp_path, monkeypatch):
    import pipeline.session_candles as sc
    monkeypatch.setattr(sc, 'appliquer_corrections_avant_ecriture',
                        lambda sym, cand: (cand, {'refus': [{'seance': '2026-10-05'}]}))
    (tmp_path / 'HPS.json').write_text(json.dumps([H_PARTIEL]))
    assert not preparer({'HPS': H_SOURCE}, '2026-10-05', '2026-10-06', tmp_path, ['HPS'])
