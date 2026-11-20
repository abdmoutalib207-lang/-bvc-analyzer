"""Le courriel cite la MÊME mesure du Score BVC que l'écran (16/11 -> 20/11/2026).

Le terminal lit `datasets/backtests/score_bvc_mesure_courante.json` (artefact
hebdomadaire, décision D2). Le courriel citait encore l'artefact QUOTIDIEN du
03/11 : deux mesures différentes pour le même score. Contrôle négatif : ce
fichier échoue sur origin/main (le courriel y cite 31,9 % / 43 031).
"""
import importlib.util
import json
import re
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
if str(RACINE) not in sys.path:
    sys.path.insert(0, str(RACINE))
spec = importlib.util.spec_from_file_location("bm", RACINE / "pipeline" / "bulletin_mail.py")
bm = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bm)

COURANT = RACINE / "datasets" / "backtests" / "score_bvc_mesure_courante.json"
POINTEUR = json.loads(COURANT.read_text(encoding="utf-8"))


def _titres(n=50):
    return [{"symbol": f"A{i}", "name": f"A{i}", "price": 100, "chg": 1.0,
             "score_bvc": {"valeur": 50.0, "etat": "CALCULABLE", "couverture_pct": 100,
                           "version": POINTEUR["version_score"], "facteurs": {}, "motif": None},
             "_meta": {"prix_asof": "2026-09-02", "stale": False, "confidence": 5}}
            for i in range(n)]


def _corps(monkeypatch, chemin=None):
    if chemin is not None:
        monkeypatch.setattr(bm, "MESURE_SCORE_BVC", chemin)
    a = bm.analyser({"masi": {}}, _titres())
    return a, bm.texte(a), bm.html(a)


def test_le_courriel_cite_exactement_les_chiffres_du_fichier_courant(monkeypatch):
    a, txt, page = _corps(monkeypatch)
    assert a["mesure"] is not None
    for corps in (txt, page.replace("&nbsp;", " ")):
        assert bm._nb(POINTEUR["observations"], 0) in corps
        assert bm._pc(POINTEUR["base_pct"]) in corps
        for t in POINTEUR["tranches"]:
            assert bm._pc(t["part_battu_masi_pct"]) in corps, t["plage"]
        assert POINTEUR["artefact"] in corps
    assert "mesure indisponible" not in txt


def test_le_courriel_ne_cite_plus_la_mesure_quotidienne(monkeypatch):
    _a, txt, page = _corps(monkeypatch)
    for corps in (txt, page):
        assert "43 031" not in corps and "31,9 %" not in corps
        assert "score_bvc_2026-11-03" not in corps


def test_fichier_absent_dit_mesure_indisponible_et_ecrit_sur_stderr(monkeypatch, capsys, tmp_path):
    _a, txt, page = _corps(monkeypatch, tmp_path / "absent.json")
    err = capsys.readouterr().err
    assert "mesure du Score BVC indisponible" in err
    for corps in (txt, page):
        assert "mesure indisponible" in corps
        assert not re.search(r"\d+,\d %\s+(sous 40|de 40 à 59)", corps)


def test_fichier_illisible_ou_d_un_autre_schema_dit_mesure_indisponible(monkeypatch, capsys, tmp_path):
    for contenu in ("{pas du json", json.dumps({"schema": "autre/9"})):
        f = tmp_path / "x.json"
        f.write_text(contenu, encoding="utf-8")
        _a, txt, _p = _corps(monkeypatch, f)
        assert "mesure indisponible" in txt
        assert "mesure du Score BVC indisponible" in capsys.readouterr().err


def test_mesure_d_une_autre_version_n_est_pas_citee_et_le_dit(monkeypatch, capsys):
    titres = _titres()
    for x in titres:
        x["score_bvc"]["version"] = "bvc-score-v2"
    a = bm.analyser({"masi": {}}, titres)
    assert a["mesure"] is None and "mesure indisponible" in bm.texte(a)
    assert "mesure non citée" in capsys.readouterr().err


def test_aucun_chiffre_de_mesure_en_dur_dans_bulletin_mail():
    src = (RACINE / "pipeline" / "bulletin_mail.py").read_text(encoding="utf-8")
    for t in POINTEUR["tranches"]:
        assert bm._pc(t["part_battu_masi_pct"]) not in src
        assert str(t["n"]) not in re.findall(r"\b\d{4,}\b", src)
    assert str(POINTEUR["observations"]) not in src
    assert "score_bvc_2026-11-03" not in src and "score_bvc_hebdo_" not in src
    assert "score_bvc_mesure_courante.json" in src


def test_la_phrase_garde_ses_reserves_et_sans_mot_d_action(monkeypatch):
    _a, txt, page = _corps(monkeypatch)
    for corps in (txt, page):
        assert "pas une promesse" in corps and "sans le facteur rentabilité" in corps
        assert not re.search(r"\b(ACHETER|ACHAT|ÉVITER|VENDRE|SURVEILLER|ATTENDRE)\b", corps)
