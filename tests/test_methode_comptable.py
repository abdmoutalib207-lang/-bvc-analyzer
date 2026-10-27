"""Registre « méthode comptable » par société (27/10/2026, accord d'Abd Moutalib).

Ce qu'il garantit :
  · chaque foncière de FAMILLES_NOTE a une méthode d'évaluation des immeubles
    au registre, et toute méthode établie porte sa pièce (url, sha256, page,
    citation) — « non_etabli » n'en exige pas, mais ne se devine pas ;
  · la note par métier ne suspend le ROE d'une foncière que si la JUSTE VALEUR
    est établie, ou par prudence si la méthode n'est pas établie ;
  · BAL (coût historique, RFA 2025 p.47) voit son ROE noté.
"""
import json
import re
import sys
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

import bvc_config as C  # noqa: E402
from pipeline.smart_money import fond_score_sectoriel as fs  # noqa: E402


def test_chaque_fonciere_est_au_registre_avec_une_methode_admise():
    for s in C.FAMILLES_NOTE["fonciere"]:
        assert s in C.METHODE_COMPTABLE, f"{s} : foncière absente du registre METHODE_COMPTABLE"
        assert C.METHODE_COMPTABLE[s]["immeubles_placement"] in C.EVALUATIONS_IMMEUBLES


def test_une_methode_etablie_porte_sa_piece():
    for s, m in C.METHODE_COMPTABLE.items():
        if m["immeubles_placement"] == "non_etabli":
            continue
        src = m["source"]
        assert src["url"].startswith("https://") and src["fichier"] in src["url"], s
        assert re.fullmatch(r"[0-9a-f]{64}", src["sha256"]), s
        objets = {c["objet"] for c in src["citations"]}
        assert {"referentiel", "immeubles_placement"} <= objets, s
        for c in src["citations"]:
            assert isinstance(c["page"], int) and c["page"] > 0 and len(c["texte"]) > 30, s
        assert m["referentiel"] and isinstance(m["exercice"], int), s


def test_les_trois_foncieres_telles_qu_etablies_le_27_10():
    assert C.immeubles_a_juste_valeur("ARD") is True        # IAS 40, p.8
    assert C.immeubles_a_juste_valeur("IMI") is True        # p.22
    assert C.immeubles_a_juste_valeur("BAL") is False       # coût historique, p.47
    assert C.immeubles_a_juste_valeur("XXX") is None        # absent : non établi, jamais deviné
    bal = C.METHODE_COMPTABLE["BAL"]["source"]["citations"]
    assert any(c["page"] == 47 and "coût historique" in c["texte"] for c in bal)
    assert "Normes Marocaines" in next(c["texte"] for c in bal if c["objet"] == "referentiel")


def test_empreinte_imi_identique_a_celle_de_l_index_des_pieces():
    idx = json.loads((RACINE / "datasets/pieces/IMI/index.json").read_text(encoding="utf-8"))
    sha = {p["fichier"]: p["sha256"] for p in idx["pieces"]}
    m = C.METHODE_COMPTABLE["IMI"]["source"]
    assert sha[m["fichier"]] == m["sha256"]


@pytest.fixture(scope="module")
def notes():
    src = fs.charger_sources()
    data = json.loads((RACINE / "data.json").read_text(encoding="utf-8"))
    t = data["tickers"]
    return fs.noter_univers([e["symbol"] for e in t], {e["symbol"]: e.get("price") for e in t},
                            {e["symbol"]: e.get("pb") for e in t}, src["fondamentaux"], src["bpa"],
                            src["s1"], src["faits"], oci=src["oci"], dividendes=src["dividendes"])


def test_bal_au_cout_a_son_roe_note(notes):
    c = notes["BAL"]["criteres"]["rentabilite"]
    assert c["etat"] == fs.PRESENT and c["note"] is not None and c["valeur"] is not None
    assert c["methode_comptable"]["immeubles_placement"] == "cout" and c["methode_comptable"]["page"] == 47
    assert "ROE suspendu" not in (c.get("motif") or "")


def test_ard_et_imi_a_la_juste_valeur_restent_suspendus(notes):
    for s in ("ARD", "IMI"):
        c = notes[s]["criteres"]["rentabilite"]
        assert c["etat"] == fs.SUSPENDU and "juste valeur" in c["motif"], s
        assert c["methode_comptable"]["immeubles_placement"] == "juste_valeur", s


def test_methode_non_etablie_garde_la_suspension_prudente(monkeypatch, notes):
    monkeypatch.delitem(C.METHODE_COMPTABLE, "BAL")
    e = notes["BAL"]["entree"]
    r = fs.noter(e, fs.calculer_medianes([x["entree"] for x in notes.values()]))
    c = r["criteres"]["rentabilite"]
    assert c["etat"] == fs.SUSPENDU and "NON ÉTABLIE" in c["motif"]
    assert c["methode_comptable"]["immeubles_placement"] == "non_etabli"


def test_hors_foncieres_le_registre_ne_change_rien(notes):
    # Le registre ne s'applique qu'aux foncières : une holding ou un promoteur
    # est noté comme avant, qu'il y figure ou non.
    for s in ("REB", "ADH"):
        assert "methode_comptable" not in notes[s]["criteres"]["rentabilite"], s
