#!/usr/bin/env python3
"""Sept titres passés à la même moulinette, et Ciments du Maroc portait CMT.

⚠️ LE PLUS GRAVE — UNE TROISIÈME CONTAMINATION D'IDENTITÉ
─────────────────────────────────────────────────────────
Du 11/05 au 09/06/2026, la série de CIMENTS DU MAROC portait les cours de
MINIÈRE TOUISSIT : **19 clôtures sur 20 identiques à celles de CMT**, aucune à
celles que l'opérateur publie pour Ciments du Maroc.

    séance        notre CIM    CMT chez nous    opérateur (CMA)
    2026-05-11      5 071,00       5 071,00           1 700,00
    2026-06-01      5 499,00       5 499,00           1 650,00

Conséquence servie : le plus-haut 52 semaines de Ciments du Maroc valait
**5 940,00 DH** — le plus-haut de Minière Touissit — pour un titre qui en vaut
1 600. Il vaut 1 750.

C'est la troisième du même genre après Marsa Maroc / Mutandis et Sonasid /
Stokvis. Les trois paires ont des codes voisins.

⚠️ ET UNE FUITE DE LA TABLE STATIQUE
Stokvis affichait 490,00 DH sur trois séances — la valeur de
`static_fallback.json`, signalée le 01/08/2026 comme fausse. Son plus-haut
52 semaines en découlait : 490,00 pour un titre à 65. Il vaut 80.

⚠️ CE QUI N'A PAS ÉTÉ CORRIGÉ, ET POURQUOI
Managem s'écarte de l'export sur 703 séances — d'un facteur 10. Ce n'est PAS un
défaut : notre série est ajustée du regroupement du 27/07/2026, l'export de
l'opérateur ne l'est pas. Corriger pour « coller » à l'export aurait cassé une
série juste. Seules ses 10 séances rediffusées sont reprises.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE / "pipeline"))
CORR = RACINE / "datasets" / "corrections_acceptees"
LOT = ("ADH", "CIM", "CSR", "HAL", "MNG", "MUT", "STK")


def _serie(t):
    return json.loads((RACINE / "pipeline" / "candles" / f"{t}.json")
                      .read_text(encoding="utf-8"))


def _doc(t):
    return json.loads((CORR / f"{t}.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize("t", LOT)
def test_chaque_lot_est_applique_a_la_lettre(t):
    serie = {b["d"]: b for b in _serie(t)}
    for l in _doc(t)["lignes"]:
        assert {k: serie[l["d"]][k] for k in ("o", "h", "l", "c", "v")} == l["corrige"], \
            f"{t} {l['d']}"


@pytest.mark.parametrize("t", LOT)
def test_chaque_lot_declare_son_identite_et_sa_source(t):
    d = _doc(t)
    s = d["source"]
    assert s["sha256"] and s["code_operateur"]
    assert "/" in s["identite_portee_sur_chaque_ligne_de_cours"]
    assert d["_statut"].startswith("RÉCEPTIONNÉ")


@pytest.mark.parametrize("t", LOT)
def test_chaque_lot_resiste_a_une_recontamination(t):
    """⚠️ L'import réécrit les chandelles. Sans réimposition, tout revient."""
    from corrections_acceptees import appliquer
    propre = _serie(t)
    par_date = {l["d"]: l for l in _doc(t)["lignes"]}
    sale = [({**b, **par_date[b["d"]]["remplace"]} if b["d"] in par_date else dict(b))
            for b in propre]
    assert sale != propre
    out, rapport = appliquer(t, sale)
    assert rapport["corrections"] == len(par_date) and rapport["refus"] == []
    assert out == propre


# ── Ciments du Maroc ───────────────────────────────────────────────────────

def test_ciments_du_maroc_ne_porte_plus_les_cours_de_touissit():
    """⚠️ LE CONTRÔLE QUI MORD. Deux séries qui coïncident au centime sur
    dix-neuf séances ne décrivent pas deux sociétés."""
    cim = {b["d"]: b["c"] for b in _serie("CIM")}
    cmt = {b["d"]: b["c"] for b in _serie("CMT")}
    fenetre = [d for d in cim if "2026-05-11" <= d <= "2026-06-09"]
    assert fenetre, "la fenêtre contaminée a disparu de la série"
    coincident = [d for d in fenetre if d in cmt and cim[d] == cmt[d]]
    assert coincident == [], f"CIM porte encore des clôtures de CMT : {coincident[:5]}"


def test_le_plus_haut_annuel_de_ciments_redevient_plausible():
    """5 940,00 était le plus-haut de Minière Touissit, servi comme celui de
    Ciments du Maroc — un titre à 1 600 DH."""
    cache = json.loads((RACINE / "pipeline" / "historical_data.json")
                       .read_text(encoding="utf-8"))
    assert cache["CIM"]["h52w"] == 1750.0
    assert cache["CIM"]["h52w"] < 2500, "un plus-haut au-delà de 2 500 serait encore CMT"


# ── Stokvis ────────────────────────────────────────────────────────────────

def test_stokvis_ne_porte_plus_la_valeur_de_la_table_statique():
    """490,00 DH vient de `static_fallback.json`, signalée fausse le
    01/08/2026. Trois séances la portaient comme une cotation."""
    serie = _serie("STK")
    assert [b["d"] for b in serie if b["c"] == 490.0] == []
    cache = json.loads((RACINE / "pipeline" / "historical_data.json")
                       .read_text(encoding="utf-8"))
    assert cache["STK"]["h52w"] == 80.0
    assert cache["STK"]["h52w"] < 200, "490 revient par le plus-haut annuel"


# ── Managem : ce qui n'est PAS corrigé ────────────────────────────────────

def test_managem_n_est_pas_aligne_sur_l_export_brut():
    """⚠️ 703 séances de Managem s'écartent de l'export d'un facteur 10. Ce
    n'est pas un défaut : notre série est ajustée du regroupement du
    27/07/2026, l'export ne l'est pas.

    Corriger pour « coller » à l'export aurait cassé une série juste. Ce test
    vérifie qu'on ne l'a pas fait — et que la série reste continue.
    """
    serie = _serie("MNG")
    marches = [(a["d"], b["d"], a["c"], b["c"]) for a, b in zip(serie, serie[1:])
               if a["c"] and (b["c"] / a["c"] > 5 or b["c"] / a["c"] < 0.2)]
    assert marches == [], f"une marche est apparue dans Managem : {marches}"
    anciens = [b["c"] for b in serie if b["d"] < "2026-07-27"]
    assert max(anciens) < 2500, (
        "les cours antérieurs au regroupement sont repassés à la base brute")
    d = _doc("MNG")
    assert all("rediffusé" in l["motif"] for l in d["lignes"]), (
        "Managem ne doit porter QUE des corrections de cours rediffusé")


# ── L'unité du volume : suivie, pas unifiée ───────────────────────────────

@pytest.mark.parametrize("t", LOT + ("HPS",))
def test_chaque_lot_suit_la_convention_de_volume_de_son_titre(t):
    """⚠️ Écrire un nombre de titres dans une série qui compte en dirhams
    rendrait ces séances incohérentes avec le reste. Chaque lot déclare la
    convention qu'il suit — la suivre n'est pas l'approuver : l'unification
    entre titres reste un arbitrage ouvert (voir ARBITRAGES/mesures.json)."""
    d = _doc(t)
    u = d["_unite_du_champ_v"]
    # ⚠️ La convention SUIVIE est celle annoncée en tête. Le texte peut citer
    # l'autre ensuite — celui de HPS raconte la rectification d'unité que j'ai
    # dû faire — mais c'est la première qui engage le lot.
    assert u.startswith(("MONTANT EN DIRHAMS", "NOMBRE DE TITRES")), u[:60]
    assert "arbitrage ouvert" in u


def test_hps_garde_la_trace_de_mon_erreur_d_unite():
    """⚠️ J'avais écrit le NOMBRE DE TITRES sur les six séances rediffusées de
    HPS, dont la série compte en dirhams. Le lot porte les deux états
    successifs plutôt que de réécrire l'histoire."""
    d = _doc("HPS")
    rect = [l for l in d["lignes"] if "_remplace_initial" in l]
    assert len(rect) == 6
    for l in rect:
        assert l["_remplace_initial"]["v"] == 0
        assert l["remplace"]["v"] != l["corrige"]["v"]
