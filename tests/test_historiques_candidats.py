#!/usr/bin/env python3
"""La couche candidate ne doit jamais toucher aux chandelles publiées.

⚠️ POURQUOI CE FICHIER EXISTE
Proposer une correction et l'appliquer sont deux décisions distinctes. Le
projet a déjà réécrit un historique en croyant l'améliorer — les cours
pré-split de MNG, réinjectés par un run qui « rafraîchissait ». Ici, la
séparation est vérifiée, pas promise.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE / "pipeline"))
DOSSIER = RACINE / "datasets" / "historiques_candidats"
NIVEAUX = {"etabli_par_la_mesure", "etabli_par_l_absence", "hypothese_a_confirmer"}


def _propositions():
    if not DOSSIER.exists():
        pytest.skip("aucune couche candidate")
    for f in sorted(DOSSIER.glob("corrections_*.json")):
        yield f, json.loads(f.read_text(encoding="utf-8"))


def test_les_corrections_vivent_hors_des_chandelles_publiees():
    """⚠️ Une proposition qui s'écrirait dans pipeline/candles/ ne serait plus
    une proposition."""
    for f, _ in _propositions():
        assert "candles" not in f.parts, f"{f} est dans le dossier des chandelles"
    src = (RACINE / "pipeline" / "corrections_candidates.py").read_text(encoding="utf-8")
    assert "SORTIE = RACINE / \"datasets\"" in src
    for interdit in ("candles_dir", "save_candle_file", "/ \"candles\""):
        assert interdit not in src, (
            f"le générateur de propositions touche aux chandelles : {interdit}")


def test_chaque_proposition_porte_son_niveau_de_preuve():
    """Sans niveau, une hypothèse se lit comme un fait."""
    vu = 0
    for f, r in _propositions():
        for p in r["propositions"]:
            vu += 1
            assert p["preuve"] in NIVEAUX, f"{f.name} : niveau inconnu {p['preuve']}"
            assert p.get("motif"), f"{f.name} : proposition sans motif"
    assert vu, "aucune proposition à vérifier"


def test_une_hypothese_ne_propose_aucun_remplacement():
    """⚠️ Corriger sur une hypothèse, c'est réécrire l'historique sur une
    conviction. Une proposition non établie SIGNALE, elle ne remplace pas."""
    for f, r in _propositions():
        for p in r["propositions"]:
            if p["preuve"] == "hypothese_a_confirmer":
                assert p["type"] == "signaler", (
                    f"{f.name} : une proposition de niveau hypothèse prétend "
                    f"« {p['type']} »")
                assert "remplacement" not in p and "ajout" not in p


def test_le_montant_en_dirhams_ne_devient_jamais_une_quantite():
    """Les deux grandeurs restent distinctes — aucune conversion."""
    for f, r in _propositions():
        for p in r["propositions"]:
            for b in p.get("remplacement", []) + p.get("ajout", []):
                assert "_volume_mad" in b, (
                    f"{f.name} : le montant en dirhams a disparu de la bougie")
                if b["_volume_mad"] and b["v"]:
                    assert b["v"] != b["_volume_mad"], (
                        f"{f.name} · {b['d']} : « v » porte le MONTANT en "
                        f"dirhams au lieu du nombre de titres")


def test_la_contamination_de_MSA_est_etablie_et_non_supposee():
    """⚠️ LE FAIT CENTRAL. Il doit reposer sur une mesure, pas sur un récit."""
    f = DOSSIER / "corrections_MSA.json"
    if not f.exists():
        pytest.skip("MSA non confronté")
    r = json.loads(f.read_text(encoding="utf-8"))
    rempl = [p for p in r["propositions"] if p["type"] == "remplacer"]
    assert rempl, "aucune proposition de remplacement pour MSA"
    p = rempl[0]
    assert p["preuve"] == "etabli_par_la_mesure"
    assert p["nombre"] == len(p["remplacement"]) == 22
    assert "22/22" in p["motif"] and "0/22" in p["motif"], (
        "le motif ne porte pas les deux décomptes qui établissent le fait")


def test_l_identite_est_exigee_avant_tout_rapprochement():
    """Le rapprochement doit s'ARRÊTER si l'identité n'est pas portée."""
    from confronter_historique import confronter
    src = (RACINE / "pipeline" / "confronter_historique.py").read_text(encoding="utf-8")
    i_id = src.index("identite_de_l_export(chemin)")
    i_cmp = src.index("exp = lire_export(chemin)")
    assert i_id < i_cmp, "les séries sont lues avant que l'identité soit établie"
    assert "_arret" in src, "aucun arrêt prévu quand l'identité n'est pas portée"
