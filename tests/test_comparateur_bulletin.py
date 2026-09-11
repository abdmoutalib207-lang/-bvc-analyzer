"""Le comparateur de bulletins doit savoir dire « je n'ai rien mesuré ».

POURQUOI CE FICHIER
───────────────────
Le 11/09/2026, la revue externe a demandé de justifier que le bulletin
intitulé « 9 septembre » décrive bien la séance du 8. En le vérifiant, le
comparateur a rendu **« 0 écart » contre les séances du 08, du 09 ET du 10**.

Cause : `comparer()` passait en silence chaque titre dont la chandelle du jour
manquait. « 0 écart » pouvait donc signifier « 0 comparaison ».

**Un contrôle qui réussit en ne mesurant rien est pire qu'un contrôle absent :
il produit une preuve apparente.** J'ai moi-même publié, sur cette base, une
affirmation vide — « séance du 10/09 recoupée, 0 écart sur 61 titres » — alors
qu'aucun titre n'avait été comparé.

La revue a ensuite relevé que le compteur ne suffisait pas : la fonction
affichait le bon message mais la commande sortait quand même en succès. Un
script appelant traitait donc « je n'ai rien mesuré » comme « tout concorde ».

TROIS VERDICTS, TROIS CODES DE SORTIE
─────────────────────────────────────
    CONCORDANCE     0    des titres ont été comparés, aucun écart au-delà
                         de la tolérance
    DISCORDANCE     1    des titres ont été comparés, des écarts subsistent
    NON CONCLUANT   2    aucun titre n'a pu être comparé
"""

import json
import subprocess
import sys
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parent.parent
OUTIL = RACINE / "pipeline" / "parse_cdg_bulletin.py"


def _module():
    return OUTIL.read_text(encoding="utf-8")


# ── la tolérance doit être nommée, pas enfouie ──────────────────────────

def test_la_tolerance_est_une_constante_nommee():
    """« Aucun écart » ne veut rien dire sans le seuil qui le définit.

    La revue externe a demandé que la formulation exacte soit « aucun écart
    dépassant 0,1 % », et non « aucun écart ».
    """
    s = _module()
    assert "TOLERANCE = 0.1" in s, "le seuil est enfoui dans le code"
    assert "abs(e) > TOLERANCE" in s, "le seuil n'est pas celui appliqué"


# ── l'état structuré ────────────────────────────────────────────────────

def test_l_etat_porte_les_six_informations_demandees():
    """Sans elles, un « verdict » n'est pas auditable."""
    s = _module()
    for cle in ("titres_admissibles", "titres_compares", "titres_non_compares",
                "motifs_non_comparaison", "ecarts", "verdict", "tolerance_pct"):
        assert f'"{cle}"' in s, f"l'état ne porte pas `{cle}`"


def test_les_trois_verdicts_existent():
    s = _module()
    for v in ("CONCORDANCE", "DISCORDANCE", "NON CONCLUANT"):
        assert f'"{v}"' in s, f"verdict `{v}` absent"


def test_une_absence_de_mesure_ne_sort_pas_en_succes():
    """LE point de la revue : la fonction affichait le bon message, la commande
    sortait quand même en succès."""
    s = _module()
    assert 'if etat["verdict"] == "NON CONCLUANT":' in s
    assert "raise SystemExit(2)" in s, (
        "une vérification sans comparaison sort encore avec le même code "
        "qu'un contrôle concluant")
    assert "raise SystemExit(1)" in s, "une discordance n'est pas signalée"


# ── comportement, sur des cas construits ────────────────────────────────

@pytest.fixture
def comparer():
    sys.path.insert(0, str(RACINE / "pipeline"))
    import importlib
    mod = importlib.import_module("parse_cdg_bulletin")
    return mod


def _bulletin(cours: dict):
    """Cotations au format interne de l'outil, pour un jeu construit."""
    return {c: {"cours": v, "variation": 0.0} for c, v in cours.items()}


def test_zero_comparaison_donne_non_concluant(comparer, tmp_path, monkeypatch):
    """Aucune chandelle ne porte la date demandée."""
    monkeypatch.setattr(comparer, "CANDLES", tmp_path)
    _, etat = comparer.comparer(_bulletin({"ADH": 35.0}), "2099-01-01")
    assert etat["titres_compares"] == 0
    assert etat["verdict"] == "NON CONCLUANT"
    assert etat["ecarts"] == 0, (
        "zéro écart sur zéro comparaison ne doit jamais se lire comme une "
        "concordance")


def test_concordance_sur_un_jeu_construit(comparer, tmp_path, monkeypatch):
    monkeypatch.setattr(comparer, "CANDLES", tmp_path)
    (tmp_path / "ADH.json").write_text(json.dumps(
        [{"d": "2026-09-08", "o": 35.0, "h": 35.0, "l": 35.0, "c": 35.0, "v": 10}]))
    _, etat = comparer.comparer(_bulletin({"ADH": 35.0}), "2026-09-08")
    assert etat["titres_compares"] == 1
    assert etat["verdict"] == "CONCORDANCE"


def test_un_ecart_connu_est_detecte(comparer, tmp_path, monkeypatch):
    """35,00 contre 36,00 : 2,86 %, bien au-delà de la tolérance de 0,1 %."""
    monkeypatch.setattr(comparer, "CANDLES", tmp_path)
    (tmp_path / "ADH.json").write_text(json.dumps(
        [{"d": "2026-09-08", "o": 35.0, "h": 35.0, "l": 35.0, "c": 35.0, "v": 10}]))
    ecarts, etat = comparer.comparer(_bulletin({"ADH": 36.0}), "2026-09-08")
    assert etat["verdict"] == "DISCORDANCE"
    assert etat["ecarts"] == 1
    assert abs(ecarts[0][3] - (36.0 - 35.0) / 36.0 * 100) < 1e-9


def test_un_ecart_sous_la_tolerance_ne_compte_pas(comparer, tmp_path, monkeypatch):
    """35,00 contre 35,02 : 0,057 %, en deçà du seuil. Comparé, sans écart."""
    monkeypatch.setattr(comparer, "CANDLES", tmp_path)
    (tmp_path / "ADH.json").write_text(json.dumps(
        [{"d": "2026-09-08", "o": 35.0, "h": 35.0, "l": 35.0, "c": 35.0, "v": 10}]))
    _, etat = comparer.comparer(_bulletin({"ADH": 35.02}), "2026-09-08")
    assert etat["titres_compares"] == 1
    assert etat["verdict"] == "CONCORDANCE"


def test_couverture_partielle_est_comptee_et_motivee(comparer, tmp_path, monkeypatch):
    """Un titre comparé, trois non comparés pour trois raisons différentes.

    La couverture partielle ne doit pas se présenter comme une concordance
    pleine : le verdict tient, le COMPTE dit sur quoi il porte.
    """
    monkeypatch.setattr(comparer, "CANDLES", tmp_path)
    (tmp_path / "ADH.json").write_text(json.dumps(
        [{"d": "2026-09-08", "o": 35.0, "h": 35.0, "l": 35.0, "c": 35.0, "v": 10}]))
    (tmp_path / "ADI.json").write_text(json.dumps(
        [{"d": "2026-09-04", "o": 400.0, "h": 400.0, "l": 400.0, "c": 400.0, "v": 5}]))
    (tmp_path / "CSR.json").write_text(json.dumps(
        [{"d": "2026-09-08", "o": 190.0, "h": 190.0, "l": 190.0, "c": None, "v": 5}]))
    cot = _bulletin({"ADH": 35.0, "ADI": 400.0, "CSR": 190.0, "MNG": 0.0})
    _, etat = comparer.comparer(cot, "2026-09-08")
    assert etat["titres_compares"] == 1
    assert etat["titres_non_compares"] == 3
    assert etat["titres_admissibles"] == 4
    motifs = etat["motifs_non_comparaison"]
    assert "séance absente de la série" in motifs
    assert "clôture manquante" in motifs
    assert "cours absent du bulletin" in motifs
