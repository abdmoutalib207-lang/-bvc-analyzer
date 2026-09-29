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
            # ⚠️ `sig` et non `sigBvc` depuis le 29/09 : le bulletin lit le
            # signal du moteur. Laisser l'avis dans `sigBvc` rendrait vide le
            # test de la confiance faible — il passerait pour une mauvaise
            # raison, aucun titre n'étant plus jamais sélectionné.
            "sig": sig, "v53": v53,
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


# ── ⚠️ Un seul avis : celui du moteur ─────────────────────────────────────

def test_un_achat_etaye_EST_relaye():
    """Le pendant du test de la confiance faible. Sans lui, un bulletin qui
    ne sélectionne plus RIEN passerait tous les tests."""
    titres = [_titre("OUI", 100, 1.0, "2026-09-02", conf=5, sig="ACHETER ★★", v53=7.0),
              _titre("FORT", 100, 1.0, "2026-09-02", conf=4, sig="ACHAT FORT ★★★", v53=8.0)]
    titres += [_titre(f"A{i}", 100, 1.0, "2026-09-02") for i in range(50)]
    a = bm.analyser({"masi": {}}, titres)
    assert [x["symbol"] for x in a["achats"]] == ["FORT", "OUI"]


def test_la_table_de_juin_n_a_plus_aucun_effet():
    """⚠️ LE DÉFAUT QUE CE TEST EMPÊCHE DE REVENIR — 29/09/2026.

    Le bulletin choisissait ses « SIGNAUX D'ACHAT » dans `sigBvc`, qui n'est
    pas calculé : c'est `SIG_BVC`, une table écrite à la main le 03/06/2026.
    Sur la séance du 28/09 : 14 achats selon la table, 9 selon le moteur, 4 en
    commun.

    Recette demandée par l'audit indépendant du 26/09 : injecter une décision
    différente dans l'ancien champ et vérifier que RIEN ne change.
    """
    base = [_titre(f"T{i}", 100, 1.0, "2026-09-02", conf=5,
                   sig=("ACHETER ★★" if i % 3 == 0 else "ATTENDRE"), v53=5 + i / 10)
            for i in range(60)]
    avant = [x["symbol"] for x in bm.analyser({"masi": {}}, base)["achats"]]

    import copy
    trafique = copy.deepcopy(base)
    for i, x in enumerate(trafique):
        x["sigBvc"] = "ACHETER" if i % 3 else "EVITER"     # l'inverse exact
    apres = [x["symbol"] for x in bm.analyser({"masi": {}}, trafique)["achats"]]
    assert avant and avant == apres, (
        "modifier `sigBvc` change les achats du bulletin — la table de juin "
        "décide encore")


def test_le_bulletin_ne_lit_plus_sigbvc():
    """Lu par l'AST : le fichier CITE `sigBvc` dans ses commentaires pour
    expliquer pourquoi il ne le lit plus."""
    import ast
    arbre = ast.parse((RACINE / "pipeline" / "bulletin_mail.py").read_text(encoding="utf-8"))
    lus = {n.value for n in ast.walk(arbre)
           if isinstance(n, ast.Constant) and isinstance(n.value, str)}
    assert "sigBvc" not in lus, "le bulletin lit encore la table de juin"
