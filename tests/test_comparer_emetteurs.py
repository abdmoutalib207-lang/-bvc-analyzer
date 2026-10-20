"""Comparateur du relevé officiel des émetteurs (tools/comparer_emetteurs.py),
sur des cas fabriqués, et format du dataset datasets/bourse_emetteurs.json."""
import importlib.util
import json
import re
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location("comparer_emetteurs", RACINE / "tools" / "comparer_emetteurs.py")
ce = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ce)


def _action(code, emetteur, nb, isin=None, statut=None, instrument=None):
    return {"emetteur": emetteur, "secteur": "X", "instrument": instrument or emetteur,
            "type_instrument": "Actions", "code": code, "code_origine": "bloc_json_embarque_de_la_page",
            "isin": isin, "nombre_titres": nb, "nombre_titres_affiche": f"{nb:,}",
            "compartiment": "Principal B", "statut": statut}


def _ref(**surcharges):
    ref = {
        "tickers": ["SNA", "STK", "AAA"],
        "noms": {"SNA": "Sonasid", "STK": "Stokvis Nord Afrique", "AAA": "Alpha Industries"},
        "isin": {"SNA": "MA0000010019", "STK": "MA0000012700", "AAA": "MA0000099999"},
        "code_officiel": {"SNA": "SID", "STK": "SNA", "AAA": "AAA"},
        "secteurs": {},
        "nb_fondamentaux": {"SNA": 3_900_000, "STK": 17_695_150, "AAA": 1_000_000},
        "nb_faits": {}, "cle_faits": {}, "statuts": {}, "splits": {},
    }
    ref.update(surcharges)
    return ref


def _releve(*actions):
    return {"enregistrements": list(actions)}


def _base():
    return [_action("SNA", "STOKVIS NORD AFRIQUE", 17_695_150),
            _action("SID", "SOCIETE NATIONALE DE SIDERURGIE SA", 3_900_000),
            _action("AAA", "ALPHA INDUSTRIES", 1_000_000)]


def test_appariement_sna_sid_croise():
    res = ce.comparer(_releve(*_base()), _ref())
    app = {a["ticker"]: a for a in res["appariements"]}
    assert app["SNA"]["code_bourse"] == "SID"          # notre SNA est Sonasid
    assert app["STK"]["code_bourse"] == "SNA"          # le SNA de la Bourse est Stokvis
    assert app["STK"]["emetteur_bourse"] == "STOKVIS NORD AFRIQUE"
    assert res["ecarts"] == []


def test_sans_traduction_le_sna_de_la_bourse_ne_va_pas_a_sonasid():
    # Si la table de traduction manquait, l'appariement par code donnerait Stokvis
    # à Sonasid : on vérifie que le test ci-dessus dépend bien de la traduction.
    ref = _ref(code_officiel={"SNA": "SNA", "STK": "STK", "AAA": "AAA"})
    app = {a["ticker"]: a for a in ce.comparer(_releve(*_base()), ref)["appariements"]}
    assert app["SNA"]["emetteur_bourse"] == "STOKVIS NORD AFRIQUE"


def test_ecart_de_titres_au_dela_de_0_5_pct():
    lignes = _base()
    lignes[2] = _action("AAA", "ALPHA INDUSTRIES", 1_010_000)   # +1 % côté Bourse
    ecarts = ce.comparer(_releve(*lignes), _ref())["ecarts"]
    assert [(e["ticker"], e["nous"], e["bourse"]) for e in ecarts] == [("AAA", 1_000_000, 1_010_000)]
    assert ecarts[0]["grandeur"].startswith("nombre de titres (fondamentaux.json")


def test_ecart_de_titres_sous_le_seuil_ignore():
    lignes = _base()
    lignes[2] = _action("AAA", "ALPHA INDUSTRIES", 1_004_000)   # 0,4 %
    assert ce.comparer(_releve(*lignes), _ref())["ecarts"] == []


def test_ecart_de_titres_faits_financiers():
    ref = _ref(nb_faits={"AAA": 900_000}, cle_faits={"AAA": "nombre_actions_au_rapport"})
    ecarts = ce.comparer(_releve(*_base()), ref)["ecarts"]
    assert len(ecarts) == 1 and "faits_financiers.json" in ecarts[0]["grandeur"]
    assert ecarts[0]["ecart_pct"] == -10.0


def test_isin_different():
    lignes = _base()
    lignes[2] = _action("AAA", "ALPHA INDUSTRIES", 1_000_000, isin="MA0000011111")
    ecarts = ce.comparer(_releve(*lignes), _ref())["ecarts"]
    assert ecarts == [{"ticker": "AAA", "grandeur": "ISIN", "nous": "MA0000099999", "bourse": "MA0000011111"}]


def test_appariement_par_isin_prime_sur_le_code():
    lignes = _base()
    # Le code AAA est porté par une autre ligne ; l'ISIN désigne la bonne.
    lignes[2] = _action("AAA", "AUTRE", 5, isin="MA0000000001")
    lignes.append(_action("ZZZ", "ALPHA BIS", 1_000_000, isin="MA0000099999"))
    res = ce.comparer(_releve(*lignes), _ref())
    app = {a["ticker"]: a for a in res["appariements"]}
    assert app["AAA"]["methode"] == "isin" and app["AAA"]["code_bourse"] == "ZZZ"


def test_present_d_un_seul_cote():
    lignes = _base()[:2] + [_action("NEW", "NOUVELLE COTEE", 10)]
    ecarts = ce.comparer(_releve(*lignes), _ref())["ecarts"]
    assert {e["grandeur"] for e in ecarts} == {"présent chez nous seulement", "présent à la Bourse seulement"}
    assert next(e for e in ecarts if e["grandeur"] == "présent chez nous seulement")["ticker"] == "AAA"


def test_appariement_par_nom_normalise_en_dernier_recours():
    lignes = _base()
    lignes[2] = _action(None, "ALPHA INDUSTRIES S.A", 1_000_000)
    app = {a["ticker"]: a for a in ce.comparer(_releve(*lignes), _ref())["appariements"]}
    assert app["AAA"]["methode"] == "nom"


def test_statut_chez_nous_sans_statut_a_la_bourse():
    ref = _ref(statuts={"AAA": ["suspendu depuis 2023-10-03"]})
    ecarts = ce.comparer(_releve(*_base()), ref)["ecarts"]
    assert ecarts == [{"ticker": "AAA", "grandeur": "statut", "nous": "suspendu depuis 2023-10-03",
                       "bourse": "aucun statut affiché"}]


def test_les_droits_et_obligations_ne_s_apparient_pas():
    droit = dict(_action("ASIDA", "SOCIETE NATIONALE DE SIDERURGIE SA", 3_900_000), type_instrument="Droits")
    res = ce.comparer(_releve(droit, *_base()), _ref())
    assert res["ecarts"] == [] and res["n_actions_bourse"] == 3


def test_le_comparateur_n_ecrit_rien(tmp_path, monkeypatch):
    """Lecture seule : aucun open() en écriture pendant la comparaison."""
    import builtins
    vrai_open = builtins.open

    def garde(f, mode="r", *a, **k):
        assert not any(c in mode for c in "wax+"), f"écriture tentée : {f}"
        return vrai_open(f, mode, *a, **k)
    monkeypatch.setattr(builtins, "open", garde)
    ce.comparer(_releve(*_base()), _ref())


# ── format du dataset publié ─────────────────────────────────────────────────
DATASET = RACINE / "datasets" / "bourse_emetteurs.json"
CHAMPS = {"emetteur", "secteur", "instrument", "type_instrument", "code", "code_origine", "isin",
          "nombre_titres", "nombre_titres_affiche", "compartiment", "statut"}


def test_format_du_dataset():
    d = json.loads(DATASET.read_text(encoding="utf-8"))
    assert d["url_source"].startswith("https://www.casablanca-bourse.com/")
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?Z", d["releve_le"])
    assert re.fullmatch(r"[0-9a-f]{64}", d["sha256_texte_page"])
    recs = d["enregistrements"]
    assert recs and d["n_instruments"] == len(recs)
    assert d["n_emetteurs"] == len({r["emetteur"] for r in recs}) == len(d["emetteurs"])
    for r in recs:
        assert set(r) == CHAMPS, r
        assert r["emetteur"] and r["instrument"] and r["type_instrument"]
        assert r["nombre_titres"] is None or (isinstance(r["nombre_titres"], int) and r["nombre_titres"] > 0)
        assert r["isin"] is None or re.fullmatch(r"MA\d{10}", r["isin"])
        assert (r["code"] is None) == (r["code_origine"] is None)
    # Le nombre affiché et le nombre relevé disent la même chose.
    for r in recs:
        if r["nombre_titres"] is not None:
            assert int(r["nombre_titres_affiche"].replace(",", "")) == r["nombre_titres"]
    # Un émetteur annonce autant d'instruments qu'il en déplie.
    for e in d["emetteurs"]:
        assert e["instruments_annonces"] == e["instruments_deplies"], e
