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


def _titre(sym, prix, chg, asof, conf=5, stale=False, sig="ATTENDRE", v53=5.0,
           bvc=50.0, etat="CALCULABLE", suspendu=False):
    """`sig` et `v53` restent posés — le moteur les publie encore au lot 1 —
    pour prouver que le bulletin ne les lit plus (06/11/2026)."""
    return {"symbol": sym, "name": sym, "price": prix, "chg": chg,
            "sig": sig, "v53": v53,
            "score_bvc": {"valeur": bvc if etat == "CALCULABLE" else None, "etat": etat,
                          "couverture_pct": 100 if etat == "CALCULABLE" else 0,
                          "version": "bvc-score-v1", "facteurs": {}, "motif": None},
            "_meta": {"prix_asof": asof, "stale": stale, "confidence": conf,
                      **({"suspendu": True} if suspendu else {})}}


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


def test_un_score_faiblement_etaye_n_est_pas_mis_en_avant():
    """Remplace « un signal faiblement étayé n'est pas relayé » (06/11/2026).

    Le terminal grise un score à confiance ≤ 1. Le courriel n'a pas
    d'indicateur visible : y mettre ce score en avant le présenterait comme
    plus sûr qu'il ne l'est. À 2, le terminal l'affiche (tuile d'accueil
    « confiance ≥ 2 ») : le courriel aussi.
    """
    titres = [_titre("FAIBLE", 100, 1.0, "2026-09-02", conf=1, bvc=99.0),
              _titre("DEUX", 100, 1.0, "2026-09-02", conf=2, bvc=98.0)]
    titres += [_titre(f"A{i}", 100, 1.0, "2026-09-02") for i in range(50)]
    a = bm.analyser({"masi": {}}, titres)
    retenus = [x["symbol"] for x in a["score_bvc"]]
    assert "FAIBLE" not in retenus and retenus[0] == "DEUX"
    assert "FAIBLE" in [x["symbol"] for x in a["insuffisants"]]


def test_suspendu_perime_ou_non_calculable_ne_sont_pas_mis_en_avant():
    titres = [_titre("SUSP", 100, 0.0, "2026-09-02", bvc=99.0, suspendu=True),
              _titre("PERIME", 100, 0.0, "2026-09-01", stale=True, bvc=99.0),
              _titre("NC", 100, 1.0, "2026-09-02", etat="NON_CALCULABLE"),
              _titre("PART", 100, 1.0, "2026-09-02", etat="PARTIEL"),
              _titre("HORS", 100, 1.0, "2026-09-02", bvc=140.0)]
    titres += [_titre(f"A{i}", 100, 1.0, "2026-09-02") for i in range(50)]
    a = bm.analyser({"masi": {}}, titres)
    retenus = {x["symbol"] for x in a["score_bvc"]}
    assert not retenus & {"SUSP", "PERIME", "NC", "PART", "HORS"}
    assert {"NC", "PART", "HORS"} <= {x["symbol"] for x in a["sans_score"]}
    assert "NC, PART, HORS" in bm.ligne_sans_score(a) and bm.ligne_sans_score(a) in bm.texte(a)


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


# ── ⚠️ Un seul score : le Score BVC publié par le moteur ─────────────────

def test_un_score_calcule_EST_mis_en_avant_par_valeur_decroissante():
    """Remplace « un achat étayé EST relayé » (06/11/2026). Le pendant du
    test de la confiance faible : sans lui, un bulletin qui ne retient plus
    RIEN passerait tous les tests."""
    titres = [_titre("MOY", 100, 1.0, "2026-09-02", bvc=61.0),
              _titre("HAUT", 100, 1.0, "2026-09-02", conf=4, bvc=88.5)]
    titres += [_titre(f"A{i}", 100, 1.0, "2026-09-02", bvc=30.0) for i in range(50)]
    a = bm.analyser({"masi": {}}, titres)
    assert [x["symbol"] for x in a["score_bvc"]][:2] == ["HAUT", "MOY"]
    assert a["repartition"] == {"≥ 75": 1, "60–74": 1, "40–59": 0, "< 40": 50}
    t = bm.texte(a)
    assert "88,5/100" in t and "≥ 75" in t and "61/100" in t
    assert "88,5/100" in bm.html(a)


def test_la_tranche_se_lit_sur_la_valeur_exacte():
    """74,5 est dans la tranche 60–74 ; un arrondi l'écrirait « 75 »."""
    assert bm.tranche_bvc(74.5) == "60–74" and bm._score(74.5) == "74,5"
    assert bm.tranche_bvc(75) == "≥ 75" and bm.tranche_bvc(39.99) == "< 40"
    assert bm.tranche_bvc(40) == "40–59" and bm.tranche_bvc(0) == "< 40"


def test_les_tranches_sont_celles_du_backtest_et_du_terminal():
    """Trois copies d'une même règle (courriel sans dépendance, backtest sous
    pandas, terminal en JS) : elles ne doivent pas diverger."""
    import re
    import pytest
    bornes = sorted(b for _, b in bm.TRANCHES_BVC if b != float("-inf"))
    assert bornes == [40, 60, 75]
    try:
        sys.path.insert(0, str(RACINE / "pipeline"))
        import backtest_score_descriptif as bsd
    except ImportError:                       # pandas absent : seule cette ligne saute
        bsd = None
    if bsd is not None:
        assert sorted(lo for _, lo, _hi in bsd.TRANCHES if lo) == bornes
    src = (RACINE / "terminal.src.html").read_text(encoding="utf-8")
    bloc = src[src.index("const TRANCHES_BVC=["):src.index("];", src.index("const TRANCHES_BVC=["))]
    assert sorted(int(x) for x in re.findall(r"min:(\d+)", bloc)) == bornes
    if bsd is None:
        pytest.skip("pandas absent : TRANCHES du backtest non relues")


def test_v53_sig_et_la_table_de_juin_n_ont_plus_aucun_effet():
    """Remplace « la table de juin n'a plus aucun effet » (29/09/2026), étendu
    le 06/11/2026 : injecter une décision différente dans `sigBvc`, `sig` ET
    `v53` ne change RIEN au bulletin — ni la liste, ni le texte."""
    base = [_titre(f"T{i}", 100, 1.0, "2026-09-02", conf=5,
                   sig=("ACHETER ★★" if i % 3 == 0 else "ATTENDRE"), v53=5 + i / 10,
                   bvc=20 + i) for i in range(60)]
    a1 = bm.analyser({"masi": {}}, base)
    avant = [x["symbol"] for x in a1["score_bvc"]]

    import copy
    trafique = copy.deepcopy(base)
    for i, x in enumerate(trafique):
        x["sigBvc"] = "ACHETER" if i % 3 else "EVITER"
        x["sig"] = "ÉVITER FORT" if i % 3 == 0 else "ACHETER ★★"
        x["v53"] = 10 - i / 10
    a2 = bm.analyser({"masi": {}}, trafique)
    assert avant and avant == [x["symbol"] for x in a2["score_bvc"]], (
        "modifier v53 / sig / sigBvc change la sélection du bulletin")
    assert bm.texte(a1) == bm.texte(a2) and bm.html(a1) == bm.html(a2)


def test_aucun_mot_d_action_dans_le_courriel():
    """Une tranche situe un score, elle ne dit pas quoi faire. Vérifié sur le
    courriel composé depuis le data.json publié, texte ET HTML."""
    import re
    d, t = bm.charger()
    a = bm.analyser(d, t)
    for corps in (bm.texte(a), bm.html(a)):
        trouves = re.findall(r"\b(ACHETER|ACHAT|ÉVITER|EVITER|VENDRE|SURVEILLER|ATTENDRE)\b", corps)
        assert not trouves, trouves
        assert "pas une prévision" in corps
        # une note sur 10 (« note 7,69/10 ») ; « 09/10 » est une date, hors motif
        assert not re.search(r"\d,\d\d/10\b", corps), "une note sur 10 subsiste"
        assert "NOTES VERTES" not in corps.upper()


def test_la_mesure_citee_est_celle_de_l_artefact():
    """R12 : chaque chiffre de la phrase de mesure est relu dans le fichier
    daté, pas recopié à la main."""
    m = bm.mesure_score_bvc()
    if m is None:
        import pytest
        pytest.skip("artefact du backtest absent")
    brut = json.loads(bm.MESURE_SCORE_BVC.read_text(encoding="utf-8"))
    r = brut["resultats"]["sans_rentabilite"]["score_bvc"]
    assert m["n"] == r["observations_total"] == sum(x["n"] for x in r["tranches"].values())
    p = bm.phrase_mesure(m)
    assert bm._nb(r["observations_total"], 0) in p
    for cle, tr in r["tranches"].items():
        assert bm._pc(tr["frequence_surperformance"]) in p, cle
    assert bm._pc(r["taux_de_base_global"]) in p
    assert "sans le facteur rentabilité" in p and "pas une promesse" in p


def test_la_mesure_n_est_pas_citee_pour_une_autre_formule():
    """Une mesure de `bvc-score-v1` ne décrit pas un score d'une autre version."""
    titres = [_titre(f"A{i}", 100, 1.0, "2026-09-02") for i in range(50)]
    assert bm.analyser({"masi": {}}, titres)["mesure"] is not None or bm.mesure_score_bvc() is None
    for x in titres:
        x["score_bvc"]["version"] = "bvc-score-v2"
    a = bm.analyser({"masi": {}}, titres)
    assert a["mesure"] is None and "Ce que le score a mesuré" not in bm.texte(a)
    assert bm.mesure_score_bvc("/chemin/absent.json") is None


def test_le_script_lance_comme_le_workflow_porte_la_lecture_de_seance(tmp_path):
    """⚠️ 06/11/2026 : `python pipeline/bulletin_mail.py` (la commande du
    workflow) ne trouvait pas le paquet `pipeline` ; `_briefing()` avalait
    l'erreur et le courriel partait SANS sa lecture de séance. Les autres
    tests importent le module depuis la racine et ne le voyaient pas : celui-ci
    lance le script en sous-processus, depuis un dossier vide, sans PYTHONPATH."""
    import os
    import subprocess
    env = {k: v for k, v in os.environ.items() if k != "PYTHONPATH"}
    r = subprocess.run([sys.executable, str(RACINE / "pipeline" / "bulletin_mail.py"),
                        str(RACINE / "data.json")], cwd=tmp_path, env=env,
                       capture_output=True, text=True, timeout=120)
    assert r.returncode in (0, 2), r.stderr
    if r.returncode == 2:
        import pytest
        pytest.skip("data.json publié trop pauvre pour composer un bulletin")
    corps = (tmp_path / "bulletin_out" / "corps.txt").read_text(encoding="utf-8")
    assert "LECTURE DE LA SÉANCE" in corps, (
        "le script lancé comme par le workflow compose un courriel sans sa lecture de séance")


def test_le_bulletin_ne_lit_plus_sigbvc_ni_v53_ni_sig():
    """Lu par l'AST : le fichier CITE ces champs dans ses commentaires pour
    expliquer pourquoi il ne les lit plus (sigBvc depuis le 29/09, v53 et sig
    depuis le 06/11/2026)."""
    import ast
    arbre = ast.parse((RACINE / "pipeline" / "bulletin_mail.py").read_text(encoding="utf-8"))
    lus = {n.value for n in ast.walk(arbre)
           if isinstance(n, ast.Constant) and isinstance(n.value, str)}
    for champ in ("sigBvc", "v53", "sig", "score_fond", "score_tech", "poids", "bonus"):
        assert champ not in lus, f"le bulletin lit encore `{champ}`"


def test_une_lecture_de_seance_impossible_se_signale(monkeypatch, capsys):
    """R5 : l'échec d'import de la lecture de séance a fait partir des
    courriels incomplets sans trace jusqu'au 06/11/2026. L'envoi continue,
    mais la panne s'écrit sur stderr, donc dans le journal du workflow."""
    import builtins
    vrai_import = builtins.__import__

    def import_casse(nom, *a, **k):
        if nom == "pipeline.briefing":
            raise ModuleNotFoundError("pipeline.briefing")
        return vrai_import(nom, *a, **k)

    monkeypatch.setattr(builtins, "__import__", import_casse)
    assert bm._briefing({}) == ""
    assert "lecture de séance absente" in capsys.readouterr().err


def test_une_mesure_illisible_se_signale(capsys, tmp_path):
    faux = tmp_path / "illisible.json"
    faux.write_text("{pas du json", encoding="utf-8")
    assert bm.mesure_score_bvc(faux) is None
    assert "mesure du Score BVC illisible" in capsys.readouterr().err
