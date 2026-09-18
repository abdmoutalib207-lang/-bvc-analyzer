#!/usr/bin/env python3
"""Le troisième écrivain de candles ne peut plus contourner les corrections reçues."""
from __future__ import annotations

import json
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))
sys.path.insert(0, str(RACINE / "pipeline"))

import candle_write_policy as politique  # noqa: E402
import update_data as moteur  # noqa: E402


def _b(d="2026-09-16", c=100.0):
    return {"d": d, "o": c, "h": c, "l": c, "c": c, "v": 1}


def test_contrat_stable_sans_lot():
    serie = [_b()]
    sortie, rapport = politique.appliquer_corrections_avant_ecriture(
        "TICKER_SANS_LOT", serie)
    assert sortie == serie
    assert rapport["corrections"] == 0
    assert rapport["refus"] == []
    assert rapport["seances_absentes"] == []


def test_refus_conserve_le_fichier_intraday(tmp_path, monkeypatch):
    cible = tmp_path / "ZZZ.json"
    ancien = [_b(c=90.0)]
    cible.write_text(json.dumps(ancien, separators=(",", ":")), encoding="utf-8")
    empreinte = cible.read_bytes()

    def refuser(sym, serie):
        return serie, {
            "ticker": sym,
            "corrections": 0,
            "refus": [{"seance": "2026-09-16", "motif": "essai"}],
        }

    monkeypatch.setattr(
        moteur, "appliquer_corrections_avant_ecriture", refuser)

    assert moteur._ecrire_candles_sous_garde("ZZZ", [_b(c=101.0)], cible) is False
    assert cible.read_bytes() == empreinte


def test_correction_reimposee_avant_ecriture(tmp_path, monkeypatch):
    cible = tmp_path / "ZZZ.json"
    cible.write_text(json.dumps([_b(c=90.0)]), encoding="utf-8")
    corrigee = [_b(c=100.0)]

    def corriger(sym, serie):
        return corrigee, {
            "ticker": sym,
            "corrections": 1,
            "refus": [],
        }

    monkeypatch.setattr(
        moteur, "appliquer_corrections_avant_ecriture", corriger)

    assert moteur._ecrire_candles_sous_garde("ZZZ", [_b(c=999.0)], cible) is True
    assert json.loads(cible.read_text(encoding="utf-8")) == corrigee


def test_update_data_necrit_plus_directement_la_serie_intraday():
    src = (RACINE / "update_data.py").read_text(encoding="utf-8")
    bloc = src[src.index("# 6c. Bougie de la séance cotée"):]
    assert "_ecrire_candles_sous_garde(sym, existing, cfp)" in bloc
    assert 'cfp.write_text(json.dumps(existing' not in bloc


def test_les_trois_ecrivains_passent_par_la_meme_politique():
    """Une seule porte logique pour les trois producteurs de candles."""
    import ast

    attendus = {
        "update_data.py": "appliquer_corrections_avant_ecriture",
        "pipeline/generate_candles.py": "appliquer_corrections_avant_ecriture",
        "pipeline/collect_history_bvcscrap.py": "appliquer_corrections",
    }
    for chemin, appel in attendus.items():
        arbre = ast.parse((RACINE / chemin).read_text(encoding="utf-8"))
        imports = {
            n.module for n in ast.walk(arbre)
            if isinstance(n, ast.ImportFrom) and n.module
        }
        assert any(
            m == "candle_write_policy" or m.endswith(".candle_write_policy")
            for m in imports
        ), f"{chemin} contourne la politique commune"
        appels = {
            getattr(n.func, "id", "")
            for n in ast.walk(arbre) if isinstance(n, ast.Call)
        }
        assert appel in appels, f"{chemin} importe la politique sans l'appeler"
