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
CLES = {"chiffre_affaires", "ebe", "ebitda_ajuste", "resultat_exploitation_courant", "dette_nette_publiee", "resultat_exploitation", "resultat_net_ensemble", "resultat_net_part_groupe",
        "interets_minoritaires", "capitaux_propres_part_groupe", "dette_nette", "flux_exploitation",
        "flux_investissement", "nombre_actions", "dividende_par_action_propose"}
CONTROLES = {"concordant", "ecart", "non_verifie", "absent_ms", "ms_indique_non_publie"}


CIBLES = ["chiffre_affaires", "ebe", "resultat_exploitation", "resultat_net_ensemble", "resultat_net_part_groupe",
          "interets_minoritaires", "capitaux_propres_part_groupe", "dette_nette", "flux_exploitation",
          "flux_investissement", "nombre_actions", "dividende_par_action_propose"]
# facteur jeton imprimé / valeur_mdh attendu selon l'unité déclarée
FACTEUR = {"KMAD": 1e3, "MMAD": 1.0, "MDH": 1.0, "DH": 1e6, "milliards MAD": 1e-3, "actions": 1.0, "DH par action": 1.0}


def _nombre(tok):
    """Lecture d'un jeton imprimé : espaces / points / virgules de milliers ou de décimales."""
    core = re.sub(r"[()\s\u00a0\u202f]", "", tok).lstrip("-+")
    m = re.match(r"^\d[\d.,]*", core)
    if not m:
        return None
    core = m.group(0)
    if "." in core and "," in core:
        core = core.replace(".", "").replace(",", ".") if core.rfind(",") > core.rfind(".") else core.replace(",", "")
    elif re.fullmatch(r"\d{1,3}([.,]\d{3})+", core):
        core = re.sub(r"[.,]", "", core)
    else:
        core = core.replace(",", ".")
    try:
        return float(core)
    except ValueError:
        return None


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


def _valide_unite(c, ou):
    u = c.get("unite_source")
    assert u in FACTEUR, f"{ou}: unité « {u} » inconnue"
    tok = c.get("valeur_source")
    if tok is None:
        return
    n = float(re.match(r"[\d,.]+", tok).group(0).replace(",", ".")) if u == "milliards MAD" else _nombre(tok)
    assert n is not None, f"{ou}: jeton illisible {tok!r}"
    attendu = abs(c["valeur_mdh"]) * FACTEUR[u]
    assert abs(n - attendu) <= max(0.0015 * attendu, 1e-6), f"{ou}: unité {u} incohérente ({tok!r} vs {c['valeur_mdh']})"


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
                _valide_unite(comp, f"{ou} / {k}")
        else:
            _valide_pointeur(doc, c, ou)
            _valide_unite(c, ou)
        cit = c.get("citation") or ""
        if cle == "resultat_exploitation":
            assert not re.match(r"\s*r[ée]sultat d.exploitation courant", cit, re.I), f"{ou}: ligne « courant » dans resultat_exploitation"
        if cle == "resultat_exploitation_courant":
            assert re.match(r"\s*r[ée]sultat d.exploitation courant", cit, re.I), f"{ou}: courant attendu"
        if cle in ("ebitda_ajuste", "dette_nette_publiee"):
            assert c.get("nature"), f"{ou}: nature de l'indicateur non dite"
        ctl = c.get("controle_ms", {})
        assert ctl.get("resultat") in CONTROLES, f"{ou}: contrôle ms-screener"
        if ctl["resultat"] == "ecart":
            assert c.get("arbitrage") or ctl.get("arbitrage"), f"{ou}: écart non arbitré"
    assert n_non_nulles > 0
    cibles_remplies = sum(1 for _, cle, c in _cellules(doc) if cle in CIBLES and c.get("valeur_mdh") is not None)
    assert doc["couverture"]["remplies"] == cibles_remplies
