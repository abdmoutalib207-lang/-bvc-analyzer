"""Le bulletin quotidien — ce qu'il dit, et surtout ce qu'il refuse de dire.

Un courriel qui arrive tous les matins finit par être lu sans vérification.
Celui-ci doit donc refuser de partir plutôt que de porter une séance que la
collecte n'a pas établie : un bulletin absent se remarque, un bulletin faux
non.
"""

import importlib.util
import json
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("bm", RACINE / "pipeline" / "bulletin_mail.py")
bm = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bm)


def _titre(sym, prix, chg, asof, conf=5, stale=False, sig="ATTENDRE", v53=5.0):
    return {"symbol": sym, "name": sym, "price": prix, "chg": chg,
            "sigBvc": sig, "v53": v53,
            "_meta": {"prix_asof": asof, "stale": stale, "confidence": conf}}


def test_les_valeurs_non_cotees_sont_comptees_sur_l_univers_entier():
    """⚠️ Le défaut corrigé le 02/09 : le bulletin annonçait « 0 valeur n'a pas

    coté » alors qu'il y en avait 19. Une valeur non cotée garde le
    `prix_asof` de la séance précédente — elle sort donc du lot du jour, et
    l'écart `du_jour - cotées` n'en voyait aucune.
    """
    titres = ([_titre(f"A{i}", 100, 1.0, "2026-09-02") for i in range(60)]
              + [_titre(f"B{i}", 100, 0.0, "2026-09-01", stale=True) for i in range(19)])
    a = bm.analyser({"masi": {"value": 18000, "change_pct": 0.5}}, titres)
    assert a["cotes"] == 60
    assert a["non_cotes"] == 19


def test_refus_d_envoi_si_la_collecte_est_pauvre(tmp_path, capsys):
    """Mieux vaut pas de courriel qu'un courriel qui invente une séance."""
    d = {"masi": {"value": 18000, "change_pct": 0.1}, "updated": "2026-09-02T04:00:00+01:00",
         "tickers": [_titre(f"A{i}", 100, 1.0, "2026-09-02") for i in range(10)]}
    f = tmp_path / "data.json"
    f.write_text(json.dumps(d), encoding="utf-8")
    sys.argv = ["bulletin_mail.py", str(f)]
    assert bm.main() == 2, "moins de 40 titres à la séance : l'envoi doit être refusé"


def test_un_signal_faiblement_etaye_n_est_pas_relaye(tmp_path):
    """Le terminal grise un signal sous confiance 3. Le courriel, lui, n'a pas

    d'indicateur visible : y relayer un signal faible le présenterait comme
    plus sûr qu'il ne l'est.
    """
    titres = [_titre("SUR", 100, 1.0, "2026-09-02", conf=2, sig="ACHETER", v53=9.0)]
    titres += [_titre(f"A{i}", 100, 1.0, "2026-09-02") for i in range(50)]
    a = bm.analyser({"masi": {}}, titres)
    assert "SUR" not in [x["symbol"] for x in a["achats"]]


def test_le_bulletin_porte_toujours_l_avertissement_legal():
    titres = [_titre(f"A{i}", 100, 1.0, "2026-09-02") for i in range(50)]
    a = bm.analyser({"masi": {"value": 18000, "change_pct": 0.1}}, titres)
    for corps in (bm.texte(a), bm.html(a)):
        assert "AMMC" in corps
        assert "conseil en investissement" in corps


def test_le_sujet_porte_la_seance_pas_la_date_du_jour(tmp_path):
    """Un lundi matin, la dernière séance est celle du vendredi. C'est la bonne

    réponse pour un produit J+1, pas un retard — et le sujet doit le dire pour
    qu'un doublon se reconnaisse au premier coup d'œil.
    """
    d = {"masi": {"value": 18000, "change_pct": 0.1},
         "tickers": [_titre(f"A{i}", 100, 1.0, "2026-08-28") for i in range(50)]}
    f = tmp_path / "d.json"
    f.write_text(json.dumps(d), encoding="utf-8")
    import os
    cwd = os.getcwd()
    os.chdir(tmp_path)
    try:
        sys.argv = ["bulletin_mail.py", str(f)]
        assert bm.main() == 0
        assert "28 août 2026" in (tmp_path / "bulletin_out" / "sujet.txt").read_text(encoding="utf-8")
    finally:
        os.chdir(cwd)
