"""Format des relevés de pièces (datasets/releves/*.json).

Chaque chiffre relevé porte sa source (URL), sa page, sa période, son unité,
son périmètre et sa citation ; une estimation porte en plus son auteur et sa
date, et n'est jamais rangée parmi les chiffres réalisés."""
import importlib.util
import json
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parent.parent
RELEVES = sorted((RACINE / "datasets" / "releves").glob("*.json"))


def _outil():
    spec = importlib.util.spec_from_file_location("chercher_pieces", RACINE / "tools" / "chercher_pieces.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_il_existe_des_releves():
    assert RELEVES, "aucun relevé dans datasets/releves/"


@pytest.mark.parametrize("chemin", RELEVES, ids=lambda p: p.stem)
def test_chaque_chiffre_est_source(chemin):
    releve = json.loads(chemin.read_text(encoding="utf-8"))
    assert releve["ticker"] == chemin.stem
    for ch in releve["chiffres"] + releve["estimations"]:
        for champ in ("source", "page", "periode", "unite", "perimetre", "citation"):
            assert ch.get(champ) not in (None, ""), f"{chemin.stem} {ch.get('grandeur')} : {champ}"
        assert str(ch["source"]).startswith("https://")
    for est in releve["estimations"]:
        assert est.get("auteur") and est.get("date_estimation")


@pytest.mark.parametrize("chemin", RELEVES, ids=lambda p: p.stem)
def test_verificateur_de_l_outil(chemin):
    assert _outil().verifier_releve(json.loads(chemin.read_text(encoding="utf-8"))) == []


def test_le_verificateur_refuse_un_chiffre_sans_page_ni_perimetre():
    defauts = _outil().verifier_releve({
        "ticker": "XXX", "societe": "x", "releve_le": "2026-10-16", "blocage": {},
        "pieces": [], "estimations": [],
        "chiffres": [{"grandeur": "dette_nette", "valeur": 1, "unite": "MMAD", "periode": "2025",
                      "source": "https://exemple.ma/a.pdf", "citation": "…"}],
    })
    assert any("page" in d for d in defauts) and any("perimetre" in d for d in defauts)


def test_le_verificateur_refuse_une_estimation_parmi_les_chiffres():
    ch = {"grandeur": "bpa_2026e", "valeur": 1, "unite": "DH", "periode": "2026e", "perimetre": "consolidé",
          "source": "https://exemple.ma/r.pdf", "page": 3, "citation": "…", "nature": "estimation"}
    defauts = _outil().verifier_releve({"ticker": "XXX", "societe": "x", "releve_le": "2026-10-16",
                                        "blocage": {}, "pieces": [], "estimations": [], "chiffres": [ch]})
    assert any("estimation" in d for d in defauts)


def test_les_pdf_telecharges_ne_sont_pas_commites():
    gi = (RACINE / "datasets" / "pieces" / ".gitignore").read_text(encoding="utf-8").split()
    assert "*" in gi and "!*/index.json" in gi
