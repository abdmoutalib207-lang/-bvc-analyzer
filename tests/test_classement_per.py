"""Classement par PER — 03/11/2026, demande d'Abd Moutalib.

Ce qui est vérifié :
1. la vue existe et se rejoint (onglet, menu, adresse, route, lien depuis le
   classement) ;
2. le VRAI `classerPER` publié, exécuté sous node, n'admet parmi les classés
   que des PER positifs et ≤ 100 : une perte, un PER absent, un PER au-delà de
   100 (BPA quasi nul), des comptes absents ou une cotation suspendue vont dans
   « non classés », avec un motif ;
3. l'ordre et la médiane de secteur, attendus calculés ICI en Python ;
4. sur le data.json publié, la partition est complète et chaque titre classé
   l'est par son `pe` publié.
"""

import json
import re
import shutil
import statistics
import subprocess
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parent.parent
SRC = (RACINE / "terminal.src.html").read_text(encoding="utf-8")


def _bloc(src: str, debut: str) -> str:
    i = src.index(debut)
    j = src.index("{", i)
    p = 0
    for k in range(j, len(src)):
        if src[k] == "{":
            p += 1
        elif src[k] == "}":
            p -= 1
            if p == 0:
                return src[i:k + 1]
    raise AssertionError(f"accolade non refermée après {debut!r}")


def _classer(rows):
    node = shutil.which("node")
    if not node:                                    # pragma: no cover
        pytest.skip("node absent de cette machine")
    code = _bloc(SRC, "function classerPER(")
    script = code + "\nconst o=classerPER(%s);console.log(JSON.stringify({" \
        "classes:o.classes.map(l=>({sym:l.sym,pe:l.pe,bpa:l.bpa,anterieur:l.anterieur})),"\
        "nonClasses:o.nonClasses.map(l=>({sym:l.sym,code:l.code,motif:l.motif})),"\
        "medianes:o.medianes}));" % json.dumps(rows)
    # Par l'entrée standard : le data.json entier dépasse la longueur
    # maximale d'une ligne de commande.
    r = subprocess.run([node, "-"], input=script, capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


# ── 1. la vue existe ─────────────────────────────────────────────────────────

def test_la_vue_per_est_branchee():
    assert '{id:"per",label:"PER"}' in SRC                      # barre d'onglets
    assert '{id:"per",icone:' in SRC                            # menu
    assert re.search(r'const VUES_CONNUES=\[[^\]]*"per"', SRC)   # adresse #onglet=per
    assert re.search(r'const VUES_SUR_DONNEES=\[[^\]]*"per"', SRC)
    assert '{tab==="per"      &&<ClassementPER rows={rows}' in SRC
    assert 'onClick={()=>setTab("per")}' in SRC                 # lien depuis le classement
    assert "PER croissant ▲" in SRC and "PER décroissant ▼" in SRC
    assert 'aria-label="Filtrer par secteur"' in SRC
    assert "Un PER ne se compare qu'à celui de son secteur" in SRC


# ── 2. exclusions ────────────────────────────────────────────────────────────

def _r(sym, pe, sector="Banque", **kw):
    base = kw.pop("pe_base", "12 mois au 2026-06-30")
    return {"symbol": sym, "pe": pe, "pe_base": base, "sector": sector,
            "price": 100.0, "bpa_12m": kw.pop("bpa_12m", (100 / pe) if pe else None),
            "bpa": kw.pop("bpa", None), "_meta": kw.pop("_meta", {"prix_asof": "2026-11-03"}), **kw}


def test_negatifs_absents_et_superieurs_a_100_ne_sont_pas_classes():
    rows = [
        _r("OK1", 12.0), _r("OK2", 8.5), _r("BORD", 100.0),
        _r("PERTE", None, bpa_12m=-1.85),                       # perte : le moteur nulle le PER
        _r("NEG", -4.0, bpa_12m=-25.0),                         # défense : PER négatif servi
        _r("ABS", None, bpa_12m=None, pe_base=None),            # aucun BPA
        _r("NS", 245.6, bpa_12m=0.41),                          # BPA quasi nul
        _r("ZERO", 0.0, bpa_12m=0.0),
        _r("SANS", 9.0, _meta={"comptes_absents": {"dernier_depot": "2023-10-31"}}),
        _r("SUSP", 7.0, _meta={"suspendu": True, "statut_juridique": "Liquidation judiciaire"}),
        _r("EXO", None, pe_base="exercice 2025", bpa=-4.87, bpa_12m=None),
    ]
    o = _classer(rows)
    classes = [l["sym"] for l in o["classes"]]
    assert classes == ["OK2", "OK1", "BORD"]                    # ordre croissant, 100 inclus
    assert all(0 < l["pe"] <= 100 for l in o["classes"])
    nc = {l["sym"]: l for l in o["nonClasses"]}
    assert set(nc) == {"PERTE", "NEG", "ABS", "NS", "ZERO", "SANS", "SUSP", "EXO"}
    assert nc["PERTE"]["code"] == "perte" and "-1,85" in nc["PERTE"]["motif"]
    assert nc["NEG"]["code"] == "perte"
    assert nc["EXO"]["code"] == "perte"                         # BPA lu selon pe_base
    assert nc["ABS"]["code"] == "absent"
    assert nc["NS"]["code"] == "non_significatif" and "> 100" in nc["NS"]["motif"]
    assert nc["SANS"]["code"] == "sans_comptes" and "31/10/2023" in nc["SANS"]["motif"]
    assert nc["SUSP"]["code"] == "suspendu"
    assert all(l["motif"] for l in o["nonClasses"])


def test_le_bpa_affiche_est_celui_de_la_base():
    o = _classer([_r("A", 10.0, bpa_12m=10.0, bpa=7.0),
                  _r("B", 20.0, pe_base="exercice 2025", bpa=5.0, bpa_12m=None)])
    bpa = {l["sym"]: l["bpa"] for l in o["classes"]}
    assert bpa == {"A": 10.0, "B": 5.0}


def test_mediane_de_secteur_sur_les_seuls_classes_et_a_partir_de_4():
    rows = [_r(f"B{i}", pe) for i, pe in enumerate([8.0, 10.0, 12.0, 30.0])] + [
        _r("BNS", 300.0, bpa_12m=0.3), _r("BP", None, bpa_12m=-2.0),   # exclus de la médiane
        _r("M1", 15.0, "Mines"), _r("M2", 20.0, "Mines"), _r("M3", 25.0, "Mines")]
    o = _classer(rows)
    assert o["medianes"]["Banque"] == {"n": 4, "med": statistics.median([8, 10, 12, 30]), "hors": 0}
    assert o["medianes"]["Mines"] == {"n": 3, "med": None, "hors": 0}   # trop peu de comparables


# ── 4. data.json publié ──────────────────────────────────────────────────────

def test_partition_du_data_json_publie():
    d = json.loads((RACINE / "data.json").read_text(encoding="utf-8"))
    t = d["tickers"]
    t = t if isinstance(t, list) else list(t.values())
    o = _classer(t)
    assert len(o["classes"]) + len(o["nonClasses"]) == len(t)
    pe = {x["symbol"]: x.get("pe") for x in t}
    for l in o["classes"]:
        assert l["pe"] == pe[l["sym"]] and 0 < l["pe"] <= 100, l
    assert [l["pe"] for l in o["classes"]] == sorted(l["pe"] for l in o["classes"])
    for x in t:                                       # aucun PER absent ou > 100 classé
        if x.get("pe") is None or x["pe"] > 100:
            assert x["symbol"] in {l["sym"] for l in o["nonClasses"]}


def test_la_mediane_ne_prend_que_les_cours_de_moins_de_sept_jours():
    """Audit du 12/11/2026 : 14 PER classés sur 68 reposaient sur un cours
    antérieur à la séance, jusqu'à 32 séances (NEJ), et entraient dans les
    médianes sectorielles. Règle : sept jours au plus."""
    rows = [_r(s, pe, _meta={"prix_asof": "2026-11-12"}) for s, pe in
            (("A", 10), ("B", 12), ("C", 14), ("D", 16))]
    rows.append(_r("VIEUX", 2, _meta={"prix_asof": "2026-09-28"}))
    rows.append(_r("HIER", 13, _meta={"prix_asof": "2026-11-11", "stale": True}))
    o = _classer(rows)
    assert o["medianes"]["Banque"]["med"] == 13 and o["medianes"]["Banque"]["n"] == 5
    assert o["medianes"]["Banque"]["hors"] == 1
    assert next(c for c in o["classes"] if c["sym"] == "HIER")["anterieur"] is False
    vieux = next(c for c in o["classes"] if c["sym"] == "VIEUX")
    assert vieux["anterieur"] is True          # toujours classé, mais hors médiane


def test_sans_aucune_date_rien_n_est_ecarte():
    """Même règle qu'en Python : aucune date nulle part, aucun titre écarté."""
    rows = [_r(s, pe, _meta={}) for s, pe in (("A", 10), ("B", 12), ("C", 14), ("D", 16))]
    o = _classer(rows)
    assert o["medianes"]["Banque"]["n"] == 4 and o["medianes"]["Banque"]["hors"] == 0

