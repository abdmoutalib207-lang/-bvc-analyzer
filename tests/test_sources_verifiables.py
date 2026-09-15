#!/usr/bin/env python3
"""Chaque correction doit être vérifiable depuis le dépôt, seul.

⚠️ DEUX DÉFAUTS DE MON PROPRE TRAVAIL, TROUVÉS EN VOULANT LES PRÉVENIR
─────────────────────────────────────────────────────────────────────

1. NEUF LOTS CITAIENT UNE SOURCE ABSENTE DE `main`.
   Les exports d'ADH, CIM, CSR, HAL, HPS, MNG, MUT, SOT et STK vivaient sur la
   branche de recherche. Je les lisais par `git show` pour construire les lots,
   et le dépôt publié gardait une référence vers un fichier qu'il ne contenait
   pas. Un relecteur n'avait aucun moyen de refaire la mesure.

2. TREIZE LOTS SUR SEIZE PORTAIENT UNE EMPREINTE QUI N'IDENTIFIAIT RIEN.
   Je calculais `sha256(texte.encode())` après avoir relu le fichier avec
   `encoding="utf-8-sig"` — ce qui RETIRE le marqueur d'ordre d'octets. Le
   condensat décrivait donc un texte, pas le fichier archivé, et il ne
   concordait avec rien.

   ⚠️ Une empreinte qui ne permet pas de retrouver la pièce est pire qu'une
   empreinte absente : elle donne l'apparence de la vérifiabilité.

Ce fichier interdit les deux.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parent.parent
CORR = RACINE / "datasets" / "corrections_acceptees"


def _lots():
    return sorted(f.stem for f in CORR.glob("*.json"))


def _doc(t):
    return json.loads((CORR / f"{t}.json").read_text(encoding="utf-8"))


def test_il_y_a_bien_des_lots_a_controler():
    """⚠️ Un contrôle qui ne trouve rien à contrôler passe pour vert."""
    assert len(_lots()) >= 16


@pytest.mark.parametrize("t", _lots())
def test_la_source_de_chaque_lot_existe_dans_le_depot(t):
    """⚠️ Neuf lots citaient un fichier resté sur la branche de recherche."""
    src = RACINE / _doc(t)["source"]["fichier"]
    assert src.exists(), f"{t} : source absente du dépôt — {src}"


@pytest.mark.parametrize("t", _lots())
def test_l_empreinte_identifie_les_OCTETS_du_fichier(t):
    """⚠️ LE DÉFAUT EXACT, FIGÉ EN TEST.

    Le condensat doit porter sur les OCTETS. Calculé sur le texte relu sans
    BOM, il décrivait autre chose que la pièce archivée.
    """
    d = _doc(t)
    src = RACINE / d["source"]["fichier"]
    assert hashlib.sha256(src.read_bytes()).hexdigest() == d["source"]["sha256"], (
        f"{t} : l'empreinte déclarée n'identifie pas le fichier archivé")


@pytest.mark.parametrize("t", _lots())
def test_l_identite_declaree_se_retrouve_dans_la_source(t):
    """L'identité annoncée par le lot doit être celle que porte CHAQUE ligne de
    cours de l'export — pas une ligne, toutes."""
    d = _doc(t)
    src = RACINE / d["source"]["fichier"]
    lignes = list(csv.DictReader(
        io.StringIO(src.read_text(encoding="utf-8-sig")), delimiter=";"))
    ids = {(r["Ticker"].strip(), r["Instrument"].strip()) for r in lignes
           if r.get("Ticker")}
    assert len(ids) == 1, f"{t} : identité non constante dans la source — {ids}"
    code, nom = ids.pop()
    declaree = d["source"]["identite_portee_sur_chaque_ligne_de_cours"]
    assert code in declaree and nom in declaree, (
        f"{t} : le lot déclare « {declaree} », la source porte « {code} / {nom} »")


@pytest.mark.parametrize("t", _lots())
def test_chaque_valeur_corrigee_se_retrouve_dans_la_source(t):
    """⚠️ LE CONTRÔLE DE FOND. Une correction doit venir de la source citée, et
    d'elle seule.

    Les lots qui appliquent un coefficient — Sothema divisée par 5, HPS par 10
    — ne peuvent pas être comparés valeur à valeur : le rapport est vérifié à
    la place, et il doit être CONSTANT sur tout le lot.
    """
    d = _doc(t)
    src = RACINE / d["source"]["fichier"]
    ops = {}
    for r in csv.DictReader(io.StringIO(src.read_text(encoding="utf-8-sig")),
                            delimiter=";"):
        try:
            j, m, a = r["Séance"].split("/")
        except (ValueError, KeyError):
            continue
        ops[f"{a}-{m}-{j}"] = r

    def f(x):
        x = (x or "").strip()
        return None if x in ("", "-", "--") else float(x)

    rapports = set()
    absentes = []
    debut_source = min(ops) if ops else "9999"
    for l in d["lignes"]:
        r = ops.get(l["d"])
        if r is None:
            # ⚠️ UNE SEULE RAISON ACCEPTABLE : la séance PRÉCÈDE la couverture
            # de l'export, et la ligne le DIT. C'est le cas des 67 séances de
            # HPS antérieures au 13/09/2023, dont les valeurs viennent de notre
            # propre série divisée par le ratio mesuré. Sans cette déclaration,
            # une correction sortirait de nulle part.
            if l["d"] < debut_source and "notre propre série" in l.get("_preuve", ""):
                continue
            absentes.append(l["d"])
            continue
        c_src, c_corr = f(r["Dernier Cours"]), l["corrige"]["c"]
        if c_src and c_corr:
            rapports.add(round(c_src / c_corr, 3))
    assert absentes == [], (
        f"{t} : séances corrigées ni dans la source ni déclarées comme "
        f"antérieures à sa couverture — {absentes[:5]}")
    assert rapports, f"{t} : aucune clôture confrontée"
    # ⚠️ Un seul rapport, ou deux quand un coefficient ne s'applique qu'à une
    # partie du lot (HPS : ×10 avant le fractionnement, ×1 après).
    assert len(rapports) <= 2, (
        f"{t} : les clôtures corrigées ne suivent pas la source — rapports "
        f"observés : {sorted(rapports)[:6]}")
    for rap in rapports:
        assert rap in (1.0, 5.0, 10.0) or abs(rap - 1) < 0.01, (
            f"{t} : rapport inattendu entre la source et la correction — {rap}")
