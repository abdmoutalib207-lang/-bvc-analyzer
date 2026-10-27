"""Capitalisation = cours × nombre OFFICIEL d'actions de la Bourse — 20/10/2026.

Décision d'Abd Moutalib : la capitalisation se calcule ; celle d'IDBourse ne
sert plus que de comparaison. Chaîne du nombre d'actions (R3, un maillon
ajouté en tête) :
  1. liste officielle des émetteurs (datasets/bourse_emetteurs.json, datée)
  2. nombre sourcé de nos faits (opérateur, rapport)
  3. capitalisation servie ÷ cours (dernier recours)

Deux familles : les cas qui décrivent le CODE, et un contrôle qui relit les
DONNÉES PUBLIÉES (il saute tant que le moteur n'a pas tourné avec ce code).
"""
import json
import logging
import sys
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))
logging.disable(logging.CRITICAL)

from conftest import chemin_data_json  # noqa: E402


@pytest.fixture
def releve():
    return json.loads((RACINE / "datasets" / "bourse_emetteurs.json").read_text(encoding="utf-8"))


# ── Appariement : code officiel, jamais le nom ─────────────────────────────

def test_sna_est_sonasid_et_stk_est_stokvis(ud, releve):
    """Le SNA de la Bourse est Stokvis (notre STK) ; Sonasid y est SID (notre SNA)."""
    par_code = {r["code"]: r["nombre_titres"] for r in releve["enregistrements"]
                if r["type_instrument"] == "Actions"}
    assert ud.ACTIONS_BOURSE["SNA"] == par_code["SID"]
    assert ud.ACTIONS_BOURSE["STK"] == par_code["SNA"]
    assert ud.ACTIONS_BOURSE["SNA"] != ud.ACTIONS_BOURSE["STK"]


def test_un_seul_instrument_action_par_titre_et_meme_appariement_que_l_outil(ud, releve):
    sys.path.insert(0, str(RACINE / "tools"))
    import comparer_emetteurs as ce
    res = ce.comparer(releve, ce.charger_referentiel())
    outil = {a["ticker"]: a["nombre_titres_bourse"] for a in res["appariements"]
             if a["methode"] in ("isin", "code")}
    assert ud.ACTIONS_BOURSE == outil
    # Les alias d'ISIN_MAP (TGC, SON…) ne volent pas la ligne du vrai titre.
    assert "TGCC" in ud.ACTIONS_BOURSE


def test_l_appariement_par_nom_n_alimente_pas_la_capitalisation(releve):
    sys.path.insert(0, str(RACINE / "tools"))
    import comparer_emetteurs as ce
    ref = {"tickers": ["ZZZ"], "isin": {}, "code_officiel": {"ZZZ": "PAS-UN-CODE"},
           "noms": {"ZZZ": releve["enregistrements"][0]["emetteur"]}}
    assert ce.actions_officielles(releve, ref) == {}


# ── La chaîne de repli ─────────────────────────────────────────────────────

def test_maillon_1_la_liste_officielle_prime(ud, monkeypatch):
    monkeypatch.setattr(ud, "ACTIONS_BOURSE", {"XXX": 2_000_000})
    monkeypatch.setattr(ud, "FAITS_DATA", {"XXX": {"exercice": 2025, "faits": {
        "nombre_actions_au_rapport": {"valeur": 1_000_000, "page": 1}}}})
    # La valeur servie (et nos faits) disent 1 M d'actions : elle ne tranche plus.
    assert ud._capitalisation("XXX", 100.0, 100, "cdg", temoin_du_jour=True) == \
        (200, "calculee_bourse_officielle")
    # Sans valeur servie du tout : même calcul.
    assert ud._capitalisation("XXX", 100.0, None, "cdg") == (200, "calculee_bourse_officielle")


def test_maillon_2_quand_le_titre_manque_a_la_liste(ud, monkeypatch):
    """Un nombre officiel absent fait passer au maillon suivant, jamais à zéro."""
    monkeypatch.setattr(ud, "ACTIONS_BOURSE", {})
    monkeypatch.setattr(ud, "FAITS_DATA", {"XXX": {"exercice": 2025, "faits": {
        "nombre_actions_au_rapport": {"valeur": 1_000_000, "page": 1}}}})
    assert ud._capitalisation("XXX", 100.0, 100, "cdg", temoin_du_jour=True) == \
        (100, "calculee_recoupee")
    for vide in (0, None):
        monkeypatch.setattr(ud, "ACTIONS_BOURSE", {"XXX": vide})
        cap, src = ud._capitalisation("XXX", 100.0, 100, "cdg", temoin_du_jour=True)
        assert cap == 100 and src == "calculee_recoupee"


def test_maillon_3_la_valeur_servie_en_dernier_recours(ud, monkeypatch):
    monkeypatch.setattr(ud, "ACTIONS_BOURSE", {})
    monkeypatch.setattr(ud, "FAITS_DATA", {})
    assert ud._capitalisation("XXX", 100.0, 1234, "cdg") == (1234, "servie")
    d = ud._cap_detail("XXX", "servie", 1234, 1234)
    assert d["cap_actions_source"] == "capitalisation_servie"


def test_un_releve_illisible_ne_casse_rien(ud, tmp_path):
    p = tmp_path / "x.json"
    p.write_text("{pas du json", encoding="utf-8")
    assert ud._charger_actions_bourse(p) == ({}, None)
    assert ud._charger_actions_bourse(tmp_path / "absent.json") == ({}, None)


def test_cours_sans_cotation_du_jour(ud, monkeypatch):
    """Titre qui n'a pas coté (cours des chandelles) : le produit est publié
    s'il concorde avec la valeur servie, ou s'il n'y en a pas. S'il la
    contredit, c'est le cas CMT du 16/09 (référence remise à neuf, notre
    cours figé) : la valeur servie est gardée."""
    monkeypatch.setattr(ud, "ACTIONS_BOURSE", {"CMT": 1_681_233})
    assert ud._capitalisation("CMT", 4350.0, 7313, "candles") == (7313, "calculee_bourse_officielle")
    assert ud._capitalisation("CMT", 4350.0, None, "candles") == (7313, "calculee_bourse_officielle")
    assert ud._capitalisation("CMT", 4350.0, 3727, "candles") == (3727, "servie")


# ── Splits postérieurs au relevé (R11) ─────────────────────────────────────

def test_un_split_posterieur_au_releve_est_applique(ud, monkeypatch):
    monkeypatch.setattr(ud, "ACTIONS_BOURSE", {"XXX": 1_000})
    monkeypatch.setattr(ud, "RELEVE_BOURSE_DATE", "2026-10-20")
    monkeypatch.setitem(ud.SPLITS, "XXX", [{"date": "2026-11-02", "ratio": 10}])
    assert ud._actions_bourse("XXX") == 10_000
    monkeypatch.setitem(ud.SPLITS, "XXX", [{"date": "2026-07-27", "ratio": 10}])
    assert ud._actions_bourse("XXX") == 1_000        # déjà dans le relevé


def test_managem_n_est_pas_redivise(ud):
    """Split MNG du 27/07, antérieur au relevé : 118 646 760 tel quel."""
    assert ud._actions_bourse("MNG") == 118_646_760


# ── Fraîcheur ──────────────────────────────────────────────────────────────

def test_garde_fou_de_fraicheur(ud, monkeypatch):
    monkeypatch.setattr(ud, "RELEVE_BOURSE_DATE", "2026-10-20")
    assert ud.RELEVE_BOURSE_MAX_JOURS == 45
    frais = ud._cap_detail("ADI", "calculee_bourse_officielle", 100, 100, "2026-12-04")
    assert frais["cap_releve_age_j"] == 45 and frais["cap_releve_perime"] is False
    vieux = ud._cap_detail("ADI", "calculee_bourse_officielle", 100, 100, "2026-12-05")
    assert vieux["cap_releve_age_j"] == 46 and vieux["cap_releve_perime"] is True
    assert vieux["cap_releve_bourse"] == "2026-10-20"
    # Utilisé quand même : la fraîcheur se signale, elle n'éteint pas le maillon.
    monkeypatch.setattr(ud, "ACTIONS_BOURSE", {"ADI": 1_000_000})
    assert ud._capitalisation("ADI", 100.0, None, "cdg")[1] == "calculee_bourse_officielle"


def test_ecart_avec_la_valeur_servie(ud):
    d = ud._cap_detail("ADI", "calculee_bourse_officielle", 4783, 4614, "2026-10-20")
    assert d["cap_actions_source"] == "bourse_officielle"
    assert d["cap_ecart_servie_pct"] == 3.66
    assert ud._cap_detail("ADI", "calculee_bourse_officielle", 4783, None)["cap_ecart_servie_pct"] is None


# ── T2S (R11) ──────────────────────────────────────────────────────────────

def test_t2s_capitalisation_sur_la_bourse_bpa_inchange(ud):
    """22 584 118 = 21 785 174 + 798 944 (Augmentation de Capital Dirigeant,
    DR p.37 et p.258). Admises à la cote selon la liste de l'opérateur :
    la capitalisation les compte. Le P/B et le BPA (IAS 33) n'y touchent pas."""
    assert ud.ACTIONS_BOURSE["T2S"] == 22_584_118 == 21_785_174 + 798_944
    assert ud._capitalisation("T2S", 211.8, None, "cdg") == (ud._arrondi_cap(211.8 * 22_584_118 / 1e6),
                                                             "calculee_bourse_officielle")
    assert ud._actions_sourcees("T2S") != 22_584_118
    bpa = json.loads((RACINE / "bpa.json").read_text(encoding="utf-8")).get("T2S") or {}
    texte = json.dumps(bpa, ensure_ascii=False)
    assert "22584118" not in texte and "22 584 118" not in texte


# ── Le contrôle du soir ────────────────────────────────────────────────────

def test_nombres_changes_entre_deux_releves(releve):
    sys.path.insert(0, str(RACINE / "tools"))
    import comparer_emetteurs as ce
    import copy
    assert ce.nombres_changes(releve, releve) == []
    nouveau = copy.deepcopy(releve)
    t2s = next(r for r in nouveau["enregistrements"] if r["code"] == "T2S")
    t2s["nombre_titres"] += 1000
    ch = ce.nombres_changes(releve, nouveau)
    assert [(e["code"], e["nouveau"] - e["ancien"]) for e in ch] == [("T2S", 1000)]


def test_le_workflow_du_soir_releve_et_compare_sans_commit():
    w = (RACINE / ".github" / "workflows" / "verifier_seance.yml").read_text(encoding="utf-8")
    assert "releve_emetteurs_bourse.js" in w and "comparer_emetteurs.py" in w
    assert "--nouveau" in w and "GITHUB_STEP_SUMMARY" in w
    bloc = w[w.index("releve_emetteurs_bourse.js") - 1500:]
    assert "continue-on-error: true" in bloc
    assert "git commit" not in w and "git push" not in w
    assert "contents: read" in w


# ── Données publiées ───────────────────────────────────────────────────────

def test_chaque_capitalisation_officielle_vaut_cours_fois_actions(ud):
    d = json.loads(chemin_data_json().read_text(encoding="utf-8"))
    off = [t for t in d["tickers"]
           if (t.get("_meta") or {}).get("cap_source") == "calculee_bourse_officielle"]
    if not off:
        pytest.skip("data.json antérieur à la capitalisation officielle (20/10/2026)")
    # ⚠️ 22/10/2026 : une décimale sous 100 MDHS (`_arrondi_cap`).

    def attendu(t):
        return ud._arrondi_cap(t["price"] * ud._actions_bourse(t["symbol"]) / 1e6)
    fautes = [f"{t['symbol']} : {t['cap']} ≠ {t['price']} × {ud._actions_bourse(t['symbol'])}"
              for t in off
              if t["cap"] != attendu(t)]
    assert not fautes, "\n".join(fautes)
    assert all(t["_meta"].get("cap_releve_bourse") for t in off)
