#!/usr/bin/env python3
"""Cinq exports de plus, quatre lots de cours rediffusés — et une confirmation.

⚠️ CE QUE LA CONFRONTATION A TROUVÉ
───────────────────────────────────
CMGP, Vicenne, Risma et Stroc portaient chacune des séances où NOTRE volume est
NUL — donc « aucun échange » — alors que l'opérateur enregistre des
transactions et publie un autre cours. Le prix n'avait pas été mesuré : il
avait été rediffusé. 27 séances au total.

⚠️ AUCUNE CONTAMINATION D'IDENTITÉ, AUCUNE MARCHE D'ÉCHELLE sur ces cinq
titres : les écarts d'ordre de grandeur sont à zéro partout.

⚠️ ET UNE CONFIRMATION QUI COMPTE
L'export FRAIS de Ciments du Maroc — celui du 15/09, postérieur à la
correction — ne trouve plus AUCUN écart d'ordre de grandeur ni séance
rediffusée. La contamination par Minière Touissit, corrigée quelques heures
plus tôt sur la foi d'un export plus ancien, est confirmée résolue par un
second fichier.

⚠️ CE QUI RESTE OUVERT, ET QUI N'EST PAS DE CE RESSORT
Nos séries sont bien plus courtes que les exports : Stroc 62 séances contre
734, Ciments du Maroc 79 contre 734, Risma 570 contre 734. Ces séances
manquantes ne peuvent pas être AJOUTÉES par cette couche — elle corrige des
bougies fausses et refuse d'en fabriquer.
"""

from __future__ import annotations

import csv
import io
import json
import sys
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE / "pipeline"))
CORR = RACINE / "datasets" / "corrections_acceptees"
LOT = ("CMGP", "VCNE", "RIS", "STR")
NOUVEAUX = ("CIM", "CMGP", "VCNE", "RIS", "STR")


def _serie(t):
    return json.loads((RACINE / "pipeline" / "candles" / f"{t}.json")
                      .read_text(encoding="utf-8"))


def _doc(t):
    return json.loads((CORR / f"{t}.json").read_text(encoding="utf-8"))


def _export(t):
    src = sorted((RACINE / "sources" / t).glob("*.csv"))[-1]
    out = {}
    for r in csv.DictReader(io.StringIO(src.read_text(encoding="utf-8-sig")),
                            delimiter=";"):
        j, m, a = r["Séance"].split("/")
        out[f"{a}-{m}-{j}"] = r
    return out


# ── Les archives ──────────────────────────────────────────────────────────

@pytest.mark.parametrize("t", NOUVEAUX)
def test_chaque_export_est_archive_avec_sa_provenance(t):
    """⚠️ Le code de l'opérateur n'est pas le nôtre. La provenance doit porter
    les DEUX, sinon un fichier reclassé rejouerait juin 2026."""
    prov = sorted((RACINE / "sources" / t).glob("*.provenance.json"))
    assert prov, f"aucune provenance pour {t}"
    p = json.loads(prov[-1].read_text(encoding="utf-8"))
    assert p["titre"] == t
    assert p["code_operateur"] and p["instrument_porte_par_chaque_ligne"]
    assert p["empreinte_sha256"]


@pytest.mark.parametrize("t", NOUVEAUX)
def test_l_identite_est_constante_sur_chaque_ligne_de_cours(t):
    """Rien n'est comparé tant que l'identité n'est pas établie SUR LA LIGNE
    DU COURS — l'ordre qui manquait en juin 2026."""
    ids = {(r["Ticker"].strip(), r["Instrument"].strip())
           for r in _export(t).values()}
    assert len(ids) == 1, f"{t} : identité non constante — {ids}"


# ── Les quatre lots ───────────────────────────────────────────────────────

@pytest.mark.parametrize("t", LOT)
def test_chaque_lot_est_applique_a_la_lettre(t):
    serie = {b["d"]: b for b in _serie(t)}
    for l in _doc(t)["lignes"]:
        assert {k: serie[l["d"]][k] for k in ("o", "h", "l", "c", "v")} == l["corrige"]


@pytest.mark.parametrize("t", LOT)
def test_plus_aucune_seance_ne_dit_zero_echange_a_tort(t):
    """⚠️ LE CONTRÔLE QUI MORD. Un volume nul affirme « personne n'a échangé ».
    L'opérateur dit le contraire sur ces séances."""
    serie = {b["d"]: b for b in _serie(t)}
    ops = _export(t)
    def f(x):
        x = (x or "").strip()
        return None if x in ("", "-", "--") else float(x)
    fautives = [d for d in serie if d in ops and not serie[d]["v"]
                and (f(ops[d]["Titres Échangés"]) or 0) > 0]
    assert fautives == [], f"{t} : {len(fautives)} séances encore à volume nul"


@pytest.mark.parametrize("t", LOT)
def test_chaque_lot_resiste_a_une_recontamination(t):
    from corrections_acceptees import appliquer
    propre = _serie(t)
    par_date = {l["d"]: l for l in _doc(t)["lignes"]}
    sale = [({**b, **par_date[b["d"]]["remplace"]} if b["d"] in par_date else dict(b))
            for b in propre]
    assert sale != propre
    out, rapport = appliquer(t, sale)
    assert rapport["corrections"] == len(par_date) and rapport["refus"] == []
    assert out == propre


# ── Ciments du Maroc : la confirmation par un second export ───────────────

def test_l_export_frais_confirme_que_ciments_est_assainie():
    """⚠️ LA CONFIRMATION QUI COMPTE.

    La contamination par Minière Touissit a été corrigée sur la foi d'un export
    daté du 12/09. Celui du 15/09 — un FICHIER DIFFÉRENT, plus récent — ne
    trouve plus aucun écart d'ordre de grandeur. Deux fichiers qui concordent
    valent mieux qu'un seul qu'on croit.
    """
    serie = {b["d"]: b for b in _serie("CIM")}
    ops = _export("CIM")
    def f(x):
        x = (x or "").strip()
        return None if x in ("", "-", "--") else float(x)
    gros = [d for d in serie if d in ops
            and f(ops[d]["Dernier Cours"]) and serie[d]["c"]
            and not (0.67 < f(ops[d]["Dernier Cours"]) / serie[d]["c"] < 1.5)]
    assert gros == [], f"écarts d'ordre de grandeur persistants : {gros[:5]}"
    cmt = {b["d"]: b["c"] for b in _serie("CMT")}
    coincident = [d for d in serie if d in cmt and serie[d]["c"] == cmt[d]]
    assert coincident == [], f"CIM porte encore des clôtures de CMT : {coincident[:5]}"


# ── Ce qui reste ouvert ───────────────────────────────────────────────────

def test_les_series_plus_courtes_que_les_exports_sont_un_constat_pas_un_lot():
    """⚠️ Stroc : 62 séances chez nous contre 734 dans l'export. Ces séances
    manquantes ne sont PAS ajoutées — cette couche corrige des bougies fausses
    et refuse d'en fabriquer. Le constat est figé ici pour qu'il ne se perde
    pas."""
    manques = {}
    for t in NOUVEAUX:
        n, e = len(_serie(t)), len(_export(t))
        if e > n:
            manques[t] = e - n
    assert manques, "si plus rien ne manque, ce test n'a plus d'objet"
    assert manques.get("STR", 0) > 600
    for t, m in manques.items():
        assert not (CORR / f"{t}.json").exists() or all(
            l["d"] in {b["d"] for b in _serie(t)} for l in _doc(t)["lignes"]), (
            f"{t} : une correction porte sur une séance absente de la série")
