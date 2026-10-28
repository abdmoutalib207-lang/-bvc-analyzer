"""Les actions autodétenues relevées au rapport — convention du 10/10/2026.

Règle de l'art (IFRS, IAS 32) : les actions propres sont DÉDUITES des capitaux
propres ; le P/B se calcule sur les actions EN CIRCULATION, c'est-à-dire le
nombre d'actions moins les actions autodétenues, y compris celles que détient
une filiale consolidée (Wafa Assurance dans Attijariwafa : 13 602 015).

Ce fichier ne vérifie PAS que le chiffre est le bon (aucun test ne lit un
PDF) : il vérifie que chaque fait porte sa page, sa citation et qu'il est
cohérent avec le nombre d'actions du même rapport.

Branchement au P/B (27/10/2026, accord R8 d'Abd Moutalib pour ATW) :
`update_data._actions_autodetenues_pb` — le dénominateur par action du P/B
est le nombre de la capitalisation MOINS les autodétenues citées. Ni la
capitalisation ni le BPA ne changent. Tests de régression en fin de fichier.

Absence d'un fait = « non trouvé », jamais « zéro ». Un zéro n'est écrit que
si le rapport l'ÉNONCE : une phrase explicite citée (« ne détient pas d'actions
propres »). Une ligne de tableau vide, ou un nombre retenu égal au capital, ne
prouvent rien (revue d'Abd Moutalib sur la PR #232, 11/10/2026 : SNA retiré,
consigné sous `_non_publie.actions_autodetenues` de l'entrée, sans valeur).

Un nombre MOYEN PONDÉRÉ du BPA n'est pas un nombre détenu : LHM le consigne
sous `nombre_moyen_pondere_bpa`, la détention à la clôture se lit à l'état C1.
"""

import json
import re
import sys
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))


@pytest.fixture(scope="module")
def faits():
    return json.loads((RACINE / "pipeline" / "faits_financiers.json")
                      .read_text(encoding="utf-8"))


_NEGATION = re.compile(
    r"ne\s+d[ée]tien(?:t|nent)\s+pas|n[’']a\s+pas\s+d[’']actions|"
    r"aucune\s+action|n[’']a\s+aucune|ne\s+poss[èe]de\s+pas", re.I)


def _zero_est_cite(f):
    """Un zéro n'est accepté que s'il cite une phrase explicite de négation.

    Une ligne vide, un nombre retenu égal au capital, un rapprochement : non.
    """
    if "ligne vide" in (f.get("lecture") or "").lower():
        return False
    citations = re.findall(r"«([^»]*)»", f.get("note") or "")
    return ("explicite" in (f.get("lecture") or "")
            and any(_NEGATION.search(c) and re.search(r"actions?", c, re.I)
                    for c in citations))


def _releves(faits):
    return {t: e["faits"]["actions_autodetenues"] for t, e in faits.items()
            if not t.startswith("_") and isinstance(e, dict)
            and "actions_autodetenues" in (e.get("faits") or {})}


def test_le_releve_n_est_pas_vide(faits):
    r = _releves(faits)
    assert {"ATW", "LHM"} <= set(r), "ATW et LHM portent des actions autodétenues"
    assert r["ATW"]["valeur"] == 13_602_015 and r["LHM"]["valeur"] == 111_651


def test_chaque_fait_a_sa_page_sa_citation_et_sa_lecture(faits):
    for t, f in sorted(_releves(faits).items()):
        assert isinstance(f.get("valeur"), int) and f["valeur"] >= 0, t
        assert f.get("valeur_au_rapport") == f["valeur"], t
        assert f.get("unite_au_rapport") == "actions", t
        assert isinstance(f.get("page"), int), f"{t} : sans page"
        note = f.get("note") or ""
        assert "«" in note and "»" in note, f"{t} : pas de citation"
        assert f.get("lecture"), f"{t} : la forme de la preuve n'est pas dite"
        if f["valeur"] == 0:
            assert _zero_est_cite(f), (
                f"{t} : un zéro doit citer une phrase explicite du rapport")
        assert "moyen pondéré" not in (f.get("base") or "").lower(), t


def test_les_autodetenues_sont_inferieures_au_nombre_d_actions(faits):
    for t, f in sorted(_releves(faits).items()):
        e = faits[t]["faits"]
        na = (e.get("nombre_actions_existant") or e.get("nombre_actions_au_rapport")
              or e.get("nombre_actions_retenu_pour_le_bpa"))
        if na:
            assert f["valeur"] < na["valeur"], f"{t} : plus d'actions propres que de titres"



def test_un_zero_ne_s_accepte_que_sur_phrase_explicite():
    """Contrôle négatif : la preuve SNA (ligne vide + égalité au capital) échoue."""
    sna_retire = {
        "valeur": 0, "lecture": "ligne vide + nombre retenu = capital",
        "note": "lignes « • d'actions d'auto-détention » laissées VIDES ; « NOMBRE "
                "D'ACTIONS RETENU 3.900.000 », égal au capital"}
    assert not _zero_est_cite(sna_retire)
    # même avec le mot « explicite » dans la lecture, sans phrase de négation citée
    assert not _zero_est_cite(dict(sna_retire, lecture="explicite (zéro)"))
    # sans guillemets : pas de citation
    assert not _zero_est_cite({"valeur": 0, "lecture": "explicite (zéro)",
                               "note": "le Groupe ne détient pas d'actions propres"})
    assert _zero_est_cite({
        "valeur": 0, "lecture": "explicite (zéro)",
        "note": "« Au 31 Décembre 2025, le Groupe ne détient pas d'actions propres. »"})


def test_sna_n_a_pas_de_zero_il_est_non_publie(faits):
    """SNA : ni valeur ni zéro ; l'état « non publié » est écrit, sans chiffre."""
    f = faits["SNA"]["faits"]
    assert "actions_autodetenues" not in f
    np_ = faits["SNA"]["_non_publie"]["actions_autodetenues"]   # hors « faits » : pas de valeur
    assert np_["etat"] == "non publié" and isinstance(np_["page"], int)
    assert "valeur" not in np_ and "valeur_au_rapport" not in np_


def test_lhm_distingue_la_detention_a_la_cloture_du_nombre_moyen_pondere(faits):
    f = faits["LHM"]["faits"]
    det, moy = f["actions_autodetenues"], f["nombre_moyen_pondere_bpa"]
    assert det["page"] == 71 and "C1" in det["note"] and "31 DÉCEMBRE 2025" in det["note"]
    assert moy["page"] == 81 and moy["retenu_pour_le_bpa"] == 23_319_589
    assert moy["emises"] - moy["auto_detention"] == moy["retenu_pour_le_bpa"]
    assert "moyen pondéré" in moy["note"]
    # état C1 : 15 156 172 + 111 651 + 8 163 417 = capital en titres
    assert 15_156_172 + det["valeur"] + 8_163_417 == f["nombre_actions_au_rapport"]["valeur"]


# ── Branchement au P/B (27/10/2026, accord R8 pour ATW) ─────────────────────

@pytest.fixture(scope="module")
def moteur():
    import update_data
    if not update_data.FAITS_DATA:
        update_data.FAITS_DATA = json.loads(
            (RACINE / "pipeline" / "faits_financiers.json").read_text(encoding="utf-8"))
    return update_data


def test_atw_le_pb_se_calcule_sur_les_actions_en_circulation(moteur):
    d = moteur._pb_detail("ATW", 670.0)
    assert d["actions"] == 215_140_839                      # celui de la capitalisation
    assert d["actions_en_circulation"] == 215_140_839 - 13_602_015 == 201_538_824
    assert d["pb"] == round(670.0 * 201_538_824 / (d["fonds_propres"] * 1e6), 2)
    # au cours de 670 DH et aux fonds propres du 30/06/2026 : 2,06 → 1,93
    assert round(670.0 * 215_140_839 / (d["fonds_propres"] * 1e6), 2) == 2.06
    assert d["pb"] == 1.93
    a = d["autodetenues"]
    assert a["nombre"] == 13_602_015 and a["page"] == 110 and a["au"] == "2025-12-31"
    assert "AWB_RFA_2025.pdf" in a["source"] and "27/10/2026" in a["accord"]


def test_atw_la_capitalisation_ne_change_pas(moteur):
    assert moteur._actions_pb("ATW") == 215_140_839


def test_sans_fait_cite_le_denominateur_est_inchange(moteur):
    for t in ("T2S", "TMA", "IAM"):
        d = moteur._pb_detail(t, 100.0)
        if d is None:
            continue
        assert d["autodetenues"] is None and d["actions_en_circulation"] == d["actions"], t
        assert moteur._trace_autodetenues_pb(t) is None, t


def test_un_fait_sans_page_ou_sans_citation_n_est_pas_deduit(moteur, monkeypatch):
    base = moteur.FAITS_DATA["ATW"]
    f = dict(base["faits"]["actions_autodetenues"])
    for retrait in ({"page": None}, {"note": "13 602 015 sans guillemets"}, {"lecture": None},
                    {"valeur": 13_602_015.0}, {"base": "nombre moyen pondéré"}):
        entree = dict(base, faits=dict(base["faits"], actions_autodetenues=dict(f, **retrait)))
        monkeypatch.setitem(moteur.FAITS_DATA, "ATW", entree)
        assert moteur._actions_autodetenues_pb("ATW") is None, retrait
        d = moteur._pb_detail("ATW", 670.0)
        assert d["actions_en_circulation"] == d["actions"] == 215_140_839, retrait


def test_absence_n_est_pas_zero(moteur, monkeypatch):
    base = moteur.FAITS_DATA["ATW"]
    faits_sans = {k: v for k, v in base["faits"].items() if k != "actions_autodetenues"}
    monkeypatch.setitem(moteur.FAITS_DATA, "ATW", dict(base, faits=faits_sans))
    assert moteur._actions_autodetenues_pb("ATW") is None
    assert moteur._trace_autodetenues_pb("ATW") is None


def test_un_zero_enonce_est_lu_sans_changer_le_ratio(moteur):
    assert moteur._actions_autodetenues_pb("BOA")["nombre"] == 0
    d = moteur._pb_detail("BOA", 100.0)
    assert d["autodetenues"] is None and d["actions_en_circulation"] == d["actions"]


def test_sans_accord_nominatif_le_pb_ne_change_pas(moteur):
    """L'accord nominatif ne couvre qu'ATW : un fait cité ailleurs (LHM) est lu
    mais ne touche ni le P/B ni la trace publiée."""
    assert set(moteur.ACCORD_AUTODETENUES_PB) == {"ATW"}
    for t in moteur.TICKERS_ALL:
        a = moteur._actions_autodetenues_pb(t)
        if a and t not in moteur.ACCORD_AUTODETENUES_PB:
            assert a["accord"] is None, t
            d = moteur._pb_detail(t, 100.0)
            if d:
                assert d["actions_en_circulation"] == d["actions"], t
            assert moteur._trace_autodetenues_pb(t) is None, t
    assert moteur._actions_autodetenues_pb("LHM") is not None


def test_ni_la_capitalisation_ni_le_bpa_ne_lisent_les_autodetenues():
    src = (RACINE / "update_data.py").read_text(encoding="utf-8")
    appels = re.findall(r"_actions_autodetenues_pb\(ticker\)", src)
    assert len(appels) == 1, "la déduction ne vit qu'au dénominateur du P/B (_pb_detail)"
    corps = re.search(r"def _pb_detail.*?\n\ndef ", src, re.S).group(0)
    assert "_actions_autodetenues_pb(ticker)" in corps
