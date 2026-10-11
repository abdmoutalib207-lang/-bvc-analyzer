"""Branchement de la note par famille dans le moteur — MODE COMPARAISON (11/10/2026).

Tant que `bvc_config.NOTE_METIER_PUBLIEE` est faux, la note par famille est
publiée À CÔTÉ (`note_fond_metier`) : `score_fond`, `v53`, `sig`, `setup`, la
confiance et le plancher restent ceux de la grille ACTUELLE. Les comportements
du mode « publié » (note remplacée, « Données insuffisantes » sans note,
confiance plafonnée, plancher de sources) restent testés avec `publier=True`
pour que la bascule, une fois décidée, ne soit pas une découverte. Les POIDS
des piliers (Fond 65,28 % / Tech 34,72 % / NLP 0) ne bougent dans aucun mode.
Les grilles elles-mêmes sont dans test_note_sectorielle.py.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import bvc_config  # noqa: E402


def _fiche(secteur="Industrie", s1=True, **ratios):
    f = {"secteur": secteur, "ratios_publies": {k: {"valeur": v, "date": "2025-12-31"}
                                                for k, v in ratios.items()}}
    if s1:
        f["source_s1_2026"] = "https://www.ammc.ma/x.pdf"
    return f


# ── 13. les poids des piliers ne bougent pas ────────────────────────────

def test_poids_des_piliers_inchanges():
    import update_data
    # Base historique 25/47/28 repliée : le pilier NLP à zéro, 47/72 et 25/72.
    w = update_data._replier_comportemental({"technique": 0.25, "fondamental": 0.47, "comportemental": 0.28})
    assert round(w["fondamental"], 4) == 0.6528 and round(w["technique"], 4) == 0.3472
    assert w["comportemental"] == 0.0
    # Pondération en vigueur, mesurée le 10/10/2026 avant le changement de note :
    # base 65,28 / 34,72 / 0 ; marché fermé 72,22 / 27,78 / 0 ; technique
    # neutralisé 100 / 0 / 0. Aucune ne dépend de la note fondamentale.
    for ctx, attendu in (({}, (0.6528, 0.3472)), ({"market_status": "OPEN"}, (0.6528, 0.3472)),
                         ({"market_status": "CLOSED"}, (0.7222, 0.2778)),
                         ({"market_status": "CLOSED", "tech_non_fiable": True}, (1.0, 0.0))):
        p = update_data.get_weights(ctx)
        assert (round(p["fondamental"], 4), round(p["technique"], 4), p["comportemental"]) == attendu + (0.0,), ctx
    src = (Path(bvc_config.__file__).parent / "pipeline" / "collect_financial_data.py").read_text(encoding="utf-8")
    assert "score_tech * 0.3472 + fond_score * 0.6528" in src


def test_v53_reste_lineaire_en_note_fondamentale_aux_memes_poids():
    import update_data
    ctx = {"market_status": "CLOSED"}
    a = update_data.compute_v53("ZZZ", 4.0, 5.0, 0, 0, ctx)
    b = update_data.compute_v53("ZZZ", 4.0, 7.0, 0, 0, ctx)
    assert a["poids"] == b["poids"]
    wf = update_data.get_weights(ctx)["fondamental"]
    assert abs((b["v53"] - a["v53"]) - 2.0 * wf) <= 0.011       # arrondis des deux notes


# ── 14. mode comparaison : rien de publié ne change ─────────────────────

def _passe1(sym, price=100.0):
    return {"score_tech": 5.0, "ctx": {"market_status": "CLOSED"}, "tech_nf": None,
            "depuis_reprise": None, "price": price, "ma20": None, "ma50": None,
            "meta_args": (sym, "cdg", "2026-10-09", {}, None, False), "meta_kw": {}}


def _fiche_sortie(sym, price=100.0):
    return {"symbol": sym, "price": price, "pb": None, "rsi": 50,
            "_meta": {"suspendu": False, "confidence": 5},
            "score_fond": 9.99, "v53": 9.99, "sig": "ACHETER ★★", "setup": "X",
            "verdict_plafonne": None}


def _fond_alu():
    return {"ALU": _fiche(roic=25.0, dette_nette_ebitda=0.3, cash_conversion=150.0)
            | {"croissance_bpa": 50.0, "croissance_ca": 50.0}}


def test_l_interrupteur_est_en_mode_comparaison_et_la_version_du_score_ne_change_pas():
    assert bvc_config.NOTE_METIER_PUBLIEE is False
    assert bvc_config.SCORE_VERSION == "v5.3-sans-saisie-2026-10-02"


def test_mode_comparaison_ne_change_ni_note_ni_signal_ni_confiance(monkeypatch):
    import copy
    import update_data
    monkeypatch.setattr(update_data, "_suspendu_maintenant", lambda t: False)
    monkeypatch.setattr(update_data, "sans_comptes", lambda t: None)
    for fond, bpa in ((_fond_alu(), {"ALU": {"bpa_12m": 10.0}}), ({}, {})):       # noté, puis sans note
        out = [_fiche_sortie("ALU")]
        avant = copy.deepcopy(out[0])
        update_data.appliquer_note_sectorielle(out, {"ALU": _passe1("ALU")}, fondamentaux=fond, bpa=bpa,
                                               faits={}, s1={})                  # défaut = interrupteur faux
        e = out[0]
        champs = ("score_fond", "v53", "sig", "setup", "verdict_plafonne", "_meta")
        assert {c: e[c] for c in champs} == {c: avant[c] for c in champs}
        assert "note_fond_metier" in e and "criteres" in e["note_fond_metier"]


def test_mode_comparaison_publie_la_note_a_cote_avec_ses_criteres(monkeypatch):
    import update_data
    monkeypatch.setattr(update_data, "_suspendu_maintenant", lambda t: False)
    monkeypatch.setattr(update_data, "sans_comptes", lambda t: None)
    out = [_fiche_sortie("ALU")]
    update_data.appliquer_note_sectorielle(out, {"ALU": _passe1("ALU")}, fondamentaux=_fond_alu(),
                                           bpa={"ALU": {"bpa_12m": 10.0}}, faits={}, s1={})
    nf = out[0]["note_fond_metier"]
    assert nf["famille"] == "autre" and nf["note"] == 9.25 and nf["poids_disponible"] == 80
    assert nf["criteres"]["valorisation"]["etat"] == "absent"
    assert nf["criteres"]["rentabilite"]["poids_effectif"] == 50.0       # 40 ÷ 80
    assert out[0]["score_fond"] == 9.99                                  # la note actuelle reste


def test_mode_comparaison_ne_bloque_jamais_la_publication(monkeypatch):
    # Sources vides : en mode publié le plancher refuserait ; en comparaison, la
    # note actuelle doit sortir quand même.
    import update_data
    monkeypatch.setattr(update_data, "_suspendu_maintenant", lambda t: False)
    out = [_fiche_sortie(s) for s in bvc_config.TICKERS_ALL]
    update_data.appliquer_note_sectorielle(out, {s: _passe1(s) for s in bvc_config.TICKERS_ALL},
                                           fondamentaux={}, bpa={}, faits={}, s1={}, publier=False)
    assert all(e["v53"] == 9.99 for e in out)


def test_le_second_pipeline_garde_la_note_actuelle_en_comparaison(monkeypatch):
    from pipeline import collect_financial_data as c
    monkeypatch.setattr(c, "noter_depuis_fichiers", lambda surcharge=None: {
        "ALU": {"famille": "autre", "note": 9.0, "poids_disponible": 100, "motif": None, "criteres": {}}})
    monkeypatch.setattr(c, "NOTE_METIER_PUBLIEE", False)
    monkeypatch.setattr(c, "compute_fond_score", lambda sym: 4.0)
    sortie = {"timestamp": "2026-10-11T00:00:00Z", "data": {"ALU": {
        "market": {"price": 100.0}, "technical": {"rsi_14": 50}, "fundamentals": {},
        "smart_money": {}, "flags": {"stale": False, "partial_data": False}}}}
    t = c.to_legacy_format(sortie)["tickers"][0]
    assert t["score_fond"] == 4.0 and t["note_fond_metier"]["note"] == 9.0


# ── 14 bis. mode publié (bascule décidée plus tard) : comportements gardés ──

def test_publie_un_titre_sans_note_ne_recoit_ni_acheter_ni_eviter(monkeypatch):
    import update_data
    monkeypatch.setattr(update_data, "_suspendu_maintenant", lambda t: False)
    monkeypatch.setattr(update_data, "sans_comptes", lambda t: None)
    out = [_fiche_sortie("ALU")]
    sources = {f"T{i}": {} for i in range(80)}
    update_data.appliquer_note_sectorielle(out, {"ALU": _passe1("ALU")}, fondamentaux=sources, bpa=sources,
                                           faits=sources, s1=sources, publier=True)
    e = out[0]
    assert e["score_fond"] is None and e["v53"] is None
    assert e["sig"] == "Données insuffisantes" and e["verdict_plafonne"] is None and e["setup"] == "NEUTRE"
    assert e["note_fond_metier"]["note"] is None


@pytest.mark.parametrize("sig", ["ACHETER ★★", "SURVEILLER ★", "ATTENDRE", "ÉVITER", "ÉVITER FORT"])
def test_signal_publie_sans_note_est_toujours_donnees_insuffisantes(monkeypatch, sig):
    import update_data
    monkeypatch.setattr(update_data, "_suspendu_maintenant", lambda t: False)
    monkeypatch.setattr(update_data, "sans_comptes", lambda t: None)
    assert update_data._signal_publie("ALU", sig, None, None, sans_note=True) == ("Données insuffisantes", None)


def test_publie_un_titre_note_recoit_la_note_de_sa_famille_et_son_v53(monkeypatch):
    import update_data
    monkeypatch.setattr(update_data, "_suspendu_maintenant", lambda t: False)
    monkeypatch.setattr(update_data, "sans_comptes", lambda t: None)
    sources = {f"T{i}": {} for i in range(80)}
    out = [_fiche_sortie("ALU")]
    update_data.appliquer_note_sectorielle(out, {"ALU": _passe1("ALU")}, fondamentaux=sources | _fond_alu(),
                                           bpa=sources | {"ALU": {"bpa_12m": 10.0}}, faits=sources, s1=sources,
                                           publier=True)
    e = out[0]
    # Aucun pair, aucune cote hors lui → valorisation absente. Sur 80 points :
    # (40×9,5 + 30×9,0 + 10×9,0) ÷ 80 = 9,25
    assert e["score_fond"] == 9.25 and e["note_fond_metier"]["famille"] == "autre"
    p = update_data.get_weights({"market_status": "CLOSED"})
    assert e["v53"] == round(min(max(5.0 * p["technique"] + 9.25 * p["fondamental"], 0), 10), 2)
    assert e["sig"].startswith("ACHETER")


def test_publie_le_second_pipeline_note_par_famille(monkeypatch):
    from pipeline import collect_financial_data as c
    monkeypatch.setattr(c, "noter_depuis_fichiers", lambda surcharge=None: {
        "AAA": {"famille": "autre", "note": None, "poids_disponible": 0, "motif": "x", "criteres": {}},
        "BBB": {"famille": "autre", "note": 6.0, "poids_disponible": 100, "motif": None, "criteres": {}}})
    monkeypatch.setattr(c, "NOTE_METIER_PUBLIEE", True)
    sortie = {"timestamp": "2026-10-10T00:00:00Z", "data": {
        s: {"market": {"price": 100.0}, "technical": {"rsi_14": 50}, "fundamentals": {},
            "smart_money": {}, "flags": {"stale": False, "partial_data": False}} for s in ("AAA", "BBB")}}
    par = {t["symbol"]: t for t in c.to_legacy_format(sortie)["tickers"]}
    assert par["AAA"]["score_fond"] is None and par["AAA"]["v53"] is None
    assert par["AAA"]["sig"] == "Données insuffisantes"
    assert par["BBB"]["score_fond"] == 6.0
    assert par["BBB"]["sig"].startswith("SURVEILLER") or par["BBB"]["sig"].startswith("ACHETER")


def test_la_confiance_est_plafonnee_a_1_sans_note_fondamentale(monkeypatch):
    import update_data
    monkeypatch.setattr(update_data, "_suspendu_maintenant", lambda t: False)
    monkeypatch.setitem(update_data._FOND_COMPUTED, "ALU", 5.0)
    avec = update_data._meta_ticker("ALU", "cdg", "2026-10-09", {}, None, False, note_fond_ok=True)
    sans = update_data._meta_ticker("ALU", "cdg", "2026-10-09", {}, None, False, note_fond_ok=False)
    assert avec["confidence"] - sans["confidence"] >= 1
    assert sans["confidence"] <= 1


def test_publie_un_titre_sans_note_a_une_confiance_au_plus_1_meme_hors_fondamentaux_json(monkeypatch):
    # T2S (confiance 4 à côté de « Données insuffisantes ») n'était pas dans
    # fondamentaux.json : la correction ne doit pas dépendre de _FOND_COMPUTED.
    import update_data
    monkeypatch.setattr(update_data, "_suspendu_maintenant", lambda t: False)
    monkeypatch.setattr(update_data, "sans_comptes", lambda t: None)
    assert "T2S" not in update_data._FOND_COMPUTED
    sources = {f"T{i}": {} for i in range(80)}
    out = [_fiche_sortie("T2S")]
    out[0]["_meta"]["confidence"] = 4
    update_data.appliquer_note_sectorielle(out, {"T2S": _passe1("T2S")}, fondamentaux=sources, bpa=sources,
                                           faits=sources, s1=sources, publier=True)
    assert out[0]["sig"] == "Données insuffisantes" and out[0]["_meta"]["confidence"] <= 1


# ── 15. plancher : panne des SOURCES seulement (11/10/2026) ─────────────────
# Abd Moutalib : bloquer uniquement sur fichiers absents, vides ou effondrés ;
# jamais sur l'abstention légitime d'un titre, MASI 1 compris.

def _sources(n=77):
    return {"fondamentaux": {f"F{i}": {} for i in range(n)}, "bpa": {f"B{i}": {} for i in range(n)},
            "faits": {f"X{i}": {} for i in range(n)}, "s1": {f"S{i}": {} for i in range(n)}}


def test_le_plancher_accepte_les_sources_mesurees_le_11_10():
    from pipeline.smart_money import fond_score_sectoriel as fs
    assert fs.problemes_sources(_sources(77), 70, 70) == []


def test_le_plancher_refuse_des_sources_vides_ou_absentes():
    from pipeline.smart_money import fond_score_sectoriel as fs
    vides = {k: {} for k in ("fondamentaux", "bpa", "faits", "s1")}
    p = fs.problemes_sources(vides)
    assert len(p) == 4 and all("absente ou vide" in x for x in p)
    assert len(fs.problemes_sources({})) == 4                      # fichiers non lus
    un = _sources(77) | {"bpa": {}}
    assert [x for x in fs.problemes_sources(un)] == ["source « bpa » absente ou vide : 0 entrées (minimum 60)"]


def test_le_plancher_refuse_un_effondrement_par_rapport_au_run_precedent():
    from pipeline.smart_money import fond_score_sectoriel as fs
    assert fs.problemes_sources(_sources(), 40, 70) == ["notes effondrées : 40 contre 70 au run précédent"]
    assert fs.problemes_sources(_sources(), 50, 70) == []          # 71 % : pas un effondrement
    assert fs.problemes_sources(_sources(), 0, None) == []         # premier run : pas de référence


def test_l_abstention_d_un_titre_ne_bloque_jamais_meme_au_masi_1(monkeypatch):
    # Sources saines, MNG sans note : aucun blocage, un simple avertissement.
    import update_data
    from pipeline.smart_money import fond_score_sectoriel as fs
    monkeypatch.setattr(update_data, "_suspendu_maintenant", lambda t: False)
    monkeypatch.setattr(update_data, "sans_comptes", lambda t: None)
    sources = {f"T{i}": {} for i in range(80)}
    out = [_fiche_sortie(s) for s in ("MNG", "ALU")]
    update_data.appliquer_note_sectorielle(out, {s: _passe1(s) for s in ("MNG", "ALU")}, fondamentaux=sources,
                                           bpa=sources, faits=sources, s1=sources, publier=True)
    assert [e["note_fond_metier"]["note"] for e in out] == [None, None]
    assert fs.masi1_sans_note(out) == [("MNG", "poids disponible 0 % < 50 %")]


def test_le_mode_publie_refuse_de_publier_sur_sources_vides(monkeypatch):
    import update_data
    monkeypatch.setattr(update_data, "_suspendu_maintenant", lambda t: False)
    out = [_fiche_sortie("ALU")]
    with pytest.raises(SystemExit) as exc:
        update_data.appliquer_note_sectorielle(out, {"ALU": _passe1("ALU")}, fondamentaux={}, bpa={},
                                               faits={}, s1={}, publier=True)
    assert "sources en panne" in str(exc.value)
    with pytest.raises(SystemExit):
        update_data.appliquer_note_sectorielle(out, {"ALU": _passe1("ALU")}, fondamentaux={f"T{i}": {} for i in range(80)},
                                               bpa={f"T{i}": {} for i in range(80)}, faits={f"T{i}": {} for i in range(80)},
                                               s1={f"T{i}": {} for i in range(80)}, publier=True,
                                               nb_notes_precedent=70)


def test_le_controle_de_seance_bloque_sur_panne_de_sources_et_avertit_pour_le_masi_1(tmp_path, monkeypatch):
    import json
    sys.path.insert(0, str(Path(bvc_config.__file__).parent / "pipeline"))
    import verifier_seance as vs
    from pipeline.smart_money import fond_score_sectoriel as fs

    def ecrire(avec_note_metier):
        fiches = [{"symbol": s, "price": 10.0, "v53": 5.0, "score_fond": 5.0, "chg": 0.0,
                   "_meta": {"prix_asof": "2026-10-09", "source_prix": "cdg"},
                   **({"note_fond_metier": {"note": None, "motif": "poids disponible 30 % < 50 %"}}
                      if avec_note_metier else {})} for s in bvc_config.TICKERS_ALL]
        (tmp_path / "data.json").write_text(json.dumps({"updated": "2026-10-09T18:00:00+0000", "tickers": fiches}))

    monkeypatch.setattr(vs, "RACINE", tmp_path)

    def resultat(debut):
        return [(ok, d) for i, ok, d in vs._controles("2026-10-09", 0) if i.startswith(debut)][0]

    ecrire(True)
    monkeypatch.setattr(fs, "charger_sources", lambda racine=None: _sources(77))
    assert resultat("fichiers de fondamentaux")[0] is True
    ok, detail = resultat("avertissement")
    assert ok is True and "MNG (poids disponible 30 % < 50 %)" in detail, "un MASI 1 sans note avertit, ne bloque pas"
    monkeypatch.setattr(fs, "charger_sources", lambda racine=None: _sources(77) | {"fondamentaux": {}})
    assert resultat("fichiers de fondamentaux")[0] is False
    monkeypatch.setattr(fs, "charger_sources", lambda racine=None: (_ for _ in ()).throw(FileNotFoundError("x")))
    assert resultat("fichiers de fondamentaux")[0] is False
    ecrire(False)
    assert resultat("avertissement")[0] is True and "sans objet" in resultat("avertissement")[1]


# ── 16. ce que data.json publie ─────────────────────────────────────────

def test_la_note_publiee_a_cote_est_compacte_et_complete():
    from pipeline.smart_money import fond_score_sectoriel as fs
    e = fs.construire_entree("ALU", _fiche(roic=20.0) | {"croissance_bpa": 5.0, "croissance_ca": 5.0},
                             {"bpa_12m": 10.0}, None, None, 100.0, None)
    e["ratios_publies_sources"] = None
    r = fs.noter(e, {"per": {"famille": {}, "marche": [("_a", 10.0), ("_b", 10.0), ("_c", 10.0)]},
                     "pb": {"famille": {}, "marche": []}, "ve_ebitda": {"famille": {}, "marche": []}})
    r["criteres"]["rentabilite"]["source"] = {"fichier": "fondamentaux.json", "piece":
        "résultat : https://www.ammc.ma/x.pdf p.4 ; capitaux propres : très long texte " * 20, "formule": "a ÷ b"}
    d = fs.detail_publie(r)
    c = d["criteres"]["rentabilite"]
    assert c["source"] == {"fichier": "fondamentaux.json", "piece": "https://www.ammc.ma/x.pdf"}
    assert {"etat", "valeur", "periode", "base", "poids_nominal", "poids_effectif", "reference"} <= set(c)
    assert len(str(d)) < 4000, "chaque titre alourdirait data.json de plus de 4 Ko"
    assert fs.detail_publie(None) is None
