"""Format de datasets/previsions_emetteurs.json — projections publiées par les émetteurs.

Ce fichier ne contient QUE des estimations futures publiées par la société elle-même
(guidance, plan stratégique, budget, business plan de prospectus visé AMMC). Il ne
nourrit ni la note ni les chiffres réalisés. Ce test vérifie que chaque projection
porte ce qui permet de la relire : la source, la page, l'horizon et la citation, et
qu'elle reste marquée « estimation future ».
"""
import json
import math
import re
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parent.parent
FICHIER = RACINE / "datasets" / "previsions_emetteurs.json"
REGLE = "estimation future publiée par la société — jamais fondue dans les chiffres réalisés, hors note"
META = {"releve_le", "agent"}
DATE = re.compile(r"^\d{4}(-\d{2}(-\d{2})?)?$")


def _charger():
    return json.loads(FICHIER.read_text(encoding="utf-8"))


def _titres(d):
    return {k: v for k, v in d.items() if not k.startswith("_") and k not in META}


def _projections(d):
    for t, v in _titres(d).items():
        for p in v.get("projections", []):
            yield t, p


def _index(t):
    p = RACINE / "datasets" / "pieces" / t / "index.json"
    return {x["fichier"]: x for x in json.loads(p.read_text(encoding="utf-8"))["pieces"]} if p.exists() else {}


def test_entete():
    d = _charger()
    assert d["_quoi"].strip()
    assert d["_regle"] == REGLE
    assert DATE.match(d["releve_le"]) and len(d["releve_le"]) == 10


def test_titres_connus_et_couverture_complete():
    d = _charger()
    connus = {r["symbol"] for r in json.loads((RACINE / "data.json").read_text(encoding="utf-8"))["tickers"]}
    titres = _titres(d)
    assert set(titres) <= connus, set(titres) - connus
    assert set(titres) == connus, f"titres absents : {sorted(connus - set(titres))}"


def test_chaque_titre_a_des_projections_ou_aucune():
    for t, v in _titres(_charger()).items():
        assert bool(v.get("projections")) != bool(v.get("aucune")), t
        assert v.get("pieces_consultees"), f"{t} : aucune pièce consultée déclarée"
        for x in v["pieces_consultees"]:
            assert x["url"].startswith("https://") and len(x["sha256"]) == 64, (t, x)


@pytest.mark.parametrize("champ", ["grandeur", "unite", "horizon", "source", "page", "citation",
                                   "perimetre", "piece", "sha256", "type", "statut"])
def test_champs_obligatoires(champ):
    manquants = [(t, p.get("id")) for t, p in _projections(_charger())
                 if p.get(champ) in (None, "", [])]
    assert not manquants, f"{champ} absent : {manquants[:10]}"


def test_forme_des_champs():
    ids = set()
    for t, p in _projections(_charger()):
        q = p["id"]
        assert q not in ids, q
        ids.add(q)
        assert p["statut"] == "estimation future", q
        assert p["source"].startswith("https://"), q
        assert isinstance(p["page"], int) and p["page"] >= 1, q
        assert len(p["citation"].strip()) >= 10, q
        assert "date_publication" in p, q
        assert p["date_publication"] is None or DATE.match(p["date_publication"]), q
        if p["date_publication"] is None:
            assert p.get("date_publication_note"), f"{q} : date inconnue sans explication"
        v = p.get("valeur")
        if v is None:
            assert p.get("valeur_texte"), f"{q} : ni valeur ni valeur_texte"
        else:
            assert isinstance(v, (int, float)) and math.isfinite(v), q
        if p.get("valeur_max") is not None:
            assert v is not None and p["valeur_max"] >= v, q
        assert "conditions" in p, q


def test_piece_inscrite_a_l_index_avec_la_meme_empreinte():
    for t, p in _projections(_charger()):
        idx = _index(t)
        assert p["piece"] in idx, (t, p["piece"])
        assert idx[p["piece"]]["sha256"] == p["sha256"], p["id"]
        assert idx[p["piece"]]["url"] == p["source"], p["id"]


def test_confrontations_recalculables():
    for t, p in _projections(_charger()):
        c = p.get("confrontation")
        if not c:
            continue
        for k in ("realise", "unite", "periode", "source", "page", "citation", "ecart_pct", "formule"):
            assert c.get(k) not in (None, ""), (p["id"], k)
        assert c["piece"] in _index(t), (p["id"], c["piece"])
        if p.get("valeur"):
            ecart = (c["realise"] - p["valeur"]) / abs(p["valeur"]) * 100
            assert abs(ecart - c["ecart_pct"]) < 0.15, (p["id"], round(ecart, 2), c["ecart_pct"])


def test_les_previsions_ne_fuient_pas_dans_les_faits_realises():
    """Le fichier des faits réalisés ne cite aucune pièce de prévision comme réalisé."""
    faits = (RACINE / "pipeline" / "faits_financiers.json").read_text(encoding="utf-8")
    assert "estimation future" not in faits
