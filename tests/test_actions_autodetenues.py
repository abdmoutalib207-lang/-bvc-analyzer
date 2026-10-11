"""Les actions autodétenues relevées au rapport — convention du 10/10/2026.

Règle de l'art (IFRS, IAS 32) : les actions propres sont DÉDUITES des capitaux
propres ; le P/B se calcule sur les actions EN CIRCULATION, c'est-à-dire le
nombre d'actions moins les actions autodétenues, y compris celles que détient
une filiale consolidée (Wafa Assurance dans Attijariwafa : 13 602 015).

Ce fichier ne vérifie PAS que le chiffre est le bon (aucun test ne lit un
PDF) : il vérifie que chaque fait porte sa page, sa citation et qu'il est
cohérent avec le nombre d'actions du même rapport. Le branchement du calcul
dans `update_data.py` est un autre chantier : rien ici ne le suppose.

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
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parent.parent


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
