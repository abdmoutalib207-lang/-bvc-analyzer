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
s'il se cite (phrase explicite, ou tableau dont la ligne est vide et le nombre
retenu égal au capital — dit dans `lecture`).
"""

import json
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="module")
def faits():
    return json.loads((RACINE / "pipeline" / "faits_financiers.json")
                      .read_text(encoding="utf-8"))


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
            assert "explicite" in f["lecture"] or "ligne vide" in f["lecture"], (
                f"{t} : un zéro doit dire d'où il vient")


def test_les_autodetenues_sont_inferieures_au_nombre_d_actions(faits):
    for t, f in sorted(_releves(faits).items()):
        e = faits[t]["faits"]
        na = (e.get("nombre_actions_existant") or e.get("nombre_actions_au_rapport")
              or e.get("nombre_actions_retenu_pour_le_bpa"))
        if na:
            assert f["valeur"] < na["valeur"], f"{t} : plus d'actions propres que de titres"

