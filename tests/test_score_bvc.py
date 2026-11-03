"""Score BVC unique (Nour + Boursenews) — mode fantôme, 03/11/2026.

Cas limites à la main, égalité du MACD avec `calc_macd`, branchement fantôme
(R8), et affichage (source du terminal). La méthode de Boursenews n'étant pas
publiée, rien ici ne prétend la reproduire.
"""
import copy
import json
import re
import sys
from pathlib import Path

import pandas as pd
import pytest

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))
sys.path.insert(0, str(RACINE / "pipeline"))

from pipeline import score_bvc as sb  # noqa: E402
from pipeline import score_descriptif as sd  # noqa: E402


def e(**sur):
    base = dict(prix=100.0, ma20=90.0, ma50=95.0, ma200=80.0, rsi=50.0, macd=1.0, macd_signal=0.5,
                hist=0.5, hist_prec=0.2, ratio_volume=1.0, montant_median=6e6, liquidite_prete=True,
                roe=13.0)
    base.update(sur)
    return base


def pts(r, k):
    return r["facteurs"][k]["points"]


def test_poids_somment_a_100_et_sous_poids_a_35():
    assert sum(sb.POIDS.values()) == 100 and sum(w for _, w in sb.SOUS_MM) == 35


def test_tout_plein_vaut_100():
    r = sb.score_bvc(**e())
    assert (r["valeur"], r["etat"], r["couverture_pct"]) == (100.0, "CALCULABLE", 100)


def test_moyennes_mobiles_une_famille_trois_sous_poids():
    assert pts(sb.score_bvc(**e(ma20=110)), "moyennes_mobiles") == 20        # MM20 perdue : 35 − 15
    assert pts(sb.score_bvc(**e(ma50=100)), "moyennes_mobiles") == 25
    assert pts(sb.score_bvc(**e(ma200=100)), "moyennes_mobiles") == 25
    assert pts(sb.score_bvc(**e(ma20=100.0)), "moyennes_mobiles") == 20      # égalité : pas au-dessus
    r = sb.score_bvc(**e(ma200=None))
    assert r["facteurs"]["moyennes_mobiles"]["poids"] == 25 and pts(r, "moyennes_mobiles") == 25
    assert r["couverture_pct"] == 90 and r["valeur"] == 100.0                 # MM200 absente : pas de poids hérité


def test_macd_trois_niveaux():
    assert pts(sb.score_bvc(**e()), "macd") == 10
    assert pts(sb.score_bvc(**e(hist=0.2, hist_prec=0.2)), "macd") == 5          # histogramme stable
    assert pts(sb.score_bvc(**e(hist=0.1, hist_prec=0.2)), "macd") == 5
    assert pts(sb.score_bvc(**e(macd=0.4, macd_signal=0.5)), "macd") == 0
    assert pts(sb.score_bvc(**e(macd=0.5)), "macd") == 0                         # égalité : pas au-dessus
    assert pts(sb.score_bvc(**e(macd=None)), "macd") is None


def test_couverture_70_et_65():
    # sans ROE (15) ni MACD (10) : 75 ; sans ROE, MACD, activité (10) : 65
    assert sb.score_bvc(**e(roe=None, macd=None))["couverture_pct"] == 75
    r = sb.score_bvc(**e(roe=None, macd=None, ratio_volume=None))
    assert (r["couverture_pct"], r["etat"], r["valeur"]) == (65, "PARTIEL", None)
    r = sb.score_bvc(**e(roe=None, macd=None, ma200=None, ratio_volume=None))  # 100−15−10−10−10 = 55
    assert r["etat"] == "PARTIEL"


@pytest.mark.parametrize("d", ["SUSPENDU", "INDISPONIBLE"])
def test_suspendu_et_perime_non_calculables(d):
    r = sb.score_bvc(**e(), decision=d)
    assert (r["etat"], r["valeur"], r["couverture_pct"], r["facteurs"]) == ("NON_CALCULABLE", None, 0, {})


def test_limite_donne_partiel_meme_complet():
    r = sb.score_bvc(**e(), decision="LIMITÉ", motif="x")
    assert (r["etat"], r["valeur"], r["couverture_pct"]) == ("PARTIEL", None, 100)


def test_momentum_reprend_la_regle_de_nour_sans_la_toucher():
    for rsi, att in ((70.0, 15), (70.01, 0), (45.0, 15), (44.99, 7.5), (30.0, 7.5), (29.99, 0)):
        assert pts(sb.score_bvc(**e(rsi=rsi)), "momentum") == att


def test_serie_macd_egale_calc_macd(ud):
    for t in ("ADH", "IAM", "BCP", "MNG"):
        b = json.loads((RACINE / "pipeline" / "candles" / f"{t}.json").read_text(encoding="utf-8"))
        cl = pd.Series([x["c"] for x in b])
        for k in range(40, len(cl), 97):
            m = sb.serie_macd(cl[:k + 1].tolist())[-1]
            assert tuple(round(x, 4) for x in m) == ud.calc_macd(cl[:k + 1]), (t, k)
    assert sb.serie_macd([1.0] * 34)[-1] is None and sb.serie_macd([1.0] * 35)[-1] is not None


def _titre():
    bg = [{"d": f"2026-{(i // 28) + 7:02d}-{(i % 28) + 1:02d}", "o": 100 + i, "h": 100 + i, "l": 100 + i,
           "c": 100.0 + i, "v": 5000.0 + i} for i in range(60)]
    rec = {"symbol": "ZZZ", "price": bg[-1]["c"], "ma20": 150.0, "ma50": 135.0, "ma200": None, "rsi": 60.0,
           "_meta": {"stale": False, "suspendu": False, "prix_asof": bg[-1]["d"]},
           "ratios_publies": {"roe_2025": {"valeur": 14.0}}}
    return rec, bg


def test_score_titre_bvc_nominal_stale_et_pas_d_effet_de_bord():
    rec, bg = _titre()
    av = copy.deepcopy((rec, bg))
    r = sb.score_titre_bvc(rec, bg)
    assert (rec, bg) == av and r["version"] == sb.VERSION and r["etat"] == "CALCULABLE"
    assert r["facteurs"]["moyennes_mobiles"]["poids_nominal"] == 35
    rec["_meta"]["stale"] = True
    assert sb.score_titre_bvc(rec, bg)["etat"] == "NON_CALCULABLE"


def test_annexer_bvc_ne_touche_que_son_champ_et_tout_ou_rien(titres):
    liste = [copy.deepcopy(t) for t in titres.values()]
    for t in liste:
        t.pop("score_bvc", None)
    av = copy.deepcopy(liste)
    f = lambda s: json.loads((RACINE / "pipeline" / "candles" / f"{s}.json").read_text(encoding="utf-8")) \
        if (RACINE / "pipeline" / "candles" / f"{s}.json").exists() else []  # noqa: E731
    sb.annexer_bvc(liste, f)
    for a, b in zip(av, liste):
        assert {k: v for k, v in b.items() if k != "score_bvc"} == a
    rec, bg = _titre()
    l2 = [rec, {**copy.deepcopy(rec), "symbol": "YYY"}]
    av2 = copy.deepcopy(l2)

    def boom(s):
        if s == "YYY":
            raise RuntimeError("x")
        return bg
    with pytest.raises(RuntimeError):
        sb.annexer_bvc(l2, boom)
    assert l2 == av2


def test_branchement_moteur_unique_apres_la_note_et_hors_note():
    src = (RACINE / "update_data.py").read_text(encoding="utf-8")
    code = re.sub(r"#.*", "", src)
    assert len(re.findall(r"score_bvc", code)) == 1
    assert src.index("note_metier_du_run(tickers_out, passe1") < src.index("_bvc_annexer(")
    for p in sorted((RACINE / "pipeline").rglob("*.py")):
        if p.name in {"score_bvc.py", "backtest_score_bvc.py"}:
            continue
        if p.name == "verifier_seance.py":
            # Seul lecteur admis : le contrôle du soir, qui compte les titres
            # publiés (avertissement non bloquant) et n'écrit rien.
            code = re.sub(r"#.*", "", p.read_text(encoding="utf-8"))
            assert code.count("score_bvc") == 1 and "ajouter(\"avertissement" in code
            continue
        assert "score_bvc" not in re.sub(r"#.*", "", p.read_text(encoding="utf-8")), p.name


def test_publie_score_bvc(titres):
    if not any("score_bvc" in t for t in titres.values()):
        pytest.skip("data.json antérieur au code qui émet `score_bvc`.")
    for s, t in titres.items():
        b = t["score_bvc"]
        assert b["version"] == sb.VERSION and b["etat"] in {"CALCULABLE", "PARTIEL", "NON_CALCULABLE"}, s
        assert (b["valeur"] is None) == (b["etat"] != "CALCULABLE"), s
        if b["valeur"] is not None:
            assert 0 <= b["valeur"] <= 100 and b["couverture_pct"] >= 70, s
        m = t.get("_meta") or {}
        if m.get("stale", True) or m.get("suspendu"):
            assert b["etat"] == "NON_CALCULABLE", s
    # v53 / sig non lus : le bloc n'est pas utilisé par la note
    assert all("score_bvc" not in (t.get("note_fond") or {}) for t in titres.values())


def test_terminal_affiche_le_score_sans_basculer_le_classement():
    src = (RACINE / "terminal.src.html").read_text(encoding="utf-8")
    assert "score_bvc:t.score_bvc" in src and "Composition du score" in src
    assert "Couverture des facteurs" in src and "sans prévision de cours" in src
    assert "proportion de points obtenus dans chaque facteur, sans prévision de rendement" in src
    assert 'useState("v53")' in src, "le tri par défaut reste v53 : la bascule n'est pas faite"
    assert '["bvc","SCORE BVC"]' in src


def test_backtest_bvc_de_bout_en_bout_meme_echantillon_et_deterministe(tmp_path, monkeypatch):
    import backtest_score_bvc as bb
    monkeypatch.setattr(bb.bs, "TIRAGES", 150)
    sorties = []
    for k in (1, 2):
        d = tmp_path / f"s{k}"
        assert bb.main(["--sortie", str(d), "--jusqu-au", "2025-06-30"]) == 0
        sorties.append((d / "score_bvc_2025-06-30.json").read_bytes())
    assert sorties[0] == sorties[1]
    a = json.loads(sorties[0].decode())
    assert a["poids"] == dict(sb.POIDS_BVC) and "test_hors_echantillon" in a
    for v in ("sans_rentabilite", "avec_roe_actuel"):
        b = a["resultats"][v]
        # même échantillon pour les deux scores
        assert b["score_bvc"]["observations_total"] == b["nour_seul"]["observations_total"] == b["observations_communes"]
    assert "_biais" in a["resultats"]["avec_roe_actuel"]
