"""Schéma de datasets/etats_financiers/<TICKER>.json (voir le README du dossier).

Règle vérifiée : AUCUNE valeur non nulle sans document + page + citation ;
AUCUN null sans raison ; les valeurs calculées citent leurs composantes.
"""
import json
import re
from pathlib import Path

import pytest

DOSSIER = Path(__file__).resolve().parent.parent / "datasets" / "etats_financiers"
FICHIERS = sorted(DOSSIER.glob("*.json"))
PERIODES = [f"FY{y}" for y in range(2016, 2026)] + [f"H1-{y}" for y in range(2019, 2027)]
CLES = {"chiffre_affaires", "ebe", "resultat_exploitation", "resultat_net_ensemble", "resultat_net_part_groupe",
        "interets_minoritaires", "capitaux_propres_part_groupe", "dette_nette", "flux_exploitation",
        "flux_investissement", "nombre_actions", "dividende_par_action_propose"}
CONTROLES = {"concordant", "ecart", "non_verifie", "absent_ms", "ms_indique_non_publie"}


def _cellules(doc):
    for per, p in doc["periodes"].items():
        for cle, c in p["donnees"].items():
            yield per, cle, c


def _valide_pointeur(doc, c, ou):
    assert c.get("document") in doc["documents"], f"{ou}: document absent du registre"
    assert isinstance(c.get("page"), int) and c["page"] >= 1, f"{ou}: page manquante"
    assert (c.get("citation") or "").strip(), f"{ou}: citation manquante"
    assert c.get("perimetre"), f"{ou}: périmètre manquant"
    assert c.get("statut"), f"{ou}: statut manquant"


def test_le_dossier_contient_les_titres_du_lot():
    assert FICHIERS, "aucun fichier d'états financiers"


@pytest.mark.parametrize("chemin", FICHIERS, ids=lambda p: p.stem)
def test_schema(chemin):
    doc = json.loads(chemin.read_text(encoding="utf-8"))
    assert doc["ticker"] == chemin.stem
    assert doc["unite"] == "MDH"
    assert set(doc["periodes"]) == set(PERIODES)
    for fn, d in doc["documents"].items():
        assert re.fullmatch(r"[0-9a-f]{64}", d["sha256"]), f"{fn}: sha256"
        assert d["url"].startswith("https://"), f"{fn}: url"
        assert d["pages"] >= 1
    n_non_nulles = 0
    for per, cle, c in _cellules(doc):
        ou = f"{chemin.stem} {per} {cle}"
        assert cle in CLES, ou
        v = c.get("valeur_mdh")
        if v is None:
            assert (c.get("raison_null") or "").strip(), f"{ou}: null sans raison"
            continue
        n_non_nulles += 1
        assert isinstance(v, (int, float)), ou
        if c.get("composantes"):
            assert c.get("formule"), ou
            for k, comp in c["composantes"].items():
                _valide_pointeur(doc, comp, f"{ou} / {k}")
        else:
            _valide_pointeur(doc, c, ou)
        ctl = c.get("controle_ms", {})
        assert ctl.get("resultat") in CONTROLES, f"{ou}: contrôle ms-screener"
        if ctl["resultat"] == "ecart":
            assert c.get("arbitrage") or ctl.get("arbitrage"), f"{ou}: écart non arbitré"
    assert n_non_nulles > 0
    assert doc["couverture"]["remplies"] == n_non_nulles
