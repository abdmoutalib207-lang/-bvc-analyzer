#!/usr/bin/env python3
"""Non-régression du cycle 16/09 valide → 17/09 annulé → 18/09 réel.

Le défaut n'apparaît qu'une fois la séance réelle du 18 déjà écrite : un repli
non borné qui traite encore l'annulation du 17 peut alors voyager dans le futur.
Ces tests figent le contrat : pour une séance annulée D, tout repli est < D ;
la séance réelle suivante reste dans les chandelles ; et le cache est remis à
niveau avant la garde bloquante puis inclus dans le commit de données.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))
sys.path.insert(0, str(RACINE / "pipeline"))


@pytest.fixture(scope="module")
def moteur():
    spec = importlib.util.spec_from_file_location("ud_ann_e2e", RACINE / "update_data.py")
    m = importlib.util.module_from_spec(spec)
    sys.modules["ud_ann_e2e"] = m
    spec.loader.exec_module(m)
    return m


def _bougie(jour: str, cours: float):
    return {"d": jour, "o": cours, "h": cours, "l": cours, "c": cours, "v": 10}


def test_repli_du_17_reste_au_16_meme_si_le_18_existe_deja(moteur, tmp_path, monkeypatch):
    import seance as S

    dossier = tmp_path / "candles"
    dossier.mkdir()
    serie = [_bougie("2026-09-16", 100), _bougie("2026-09-17", 101),
             _bougie("2026-09-18", 102)]
    for ticker in ("SNA", "STK"):
        (dossier / f"{ticker}.json").write_text(json.dumps(serie), encoding="utf-8")

    monkeypatch.setattr(S, "CANDLES_DIR", dossier)
    live = {
        "SNA": {"price": 101.0, "asof": "2026-09-17", "src": "bmce"},
        "STK": {"price": 101.0, "asof": "2026-09-17", "src": "bmce"},
    }

    retenue = moteur._ecarter_seances_annulees(live, "2026-09-17")

    assert retenue == "2026-09-16", (
        "un repli de la séance annulée du 17/09 a utilisé une séance >= 17/09")
    assert live == {}, "les lignes juridiquement annulées doivent être écartées"
    assert S.derniere_seance_connue(dossier, avant="2026-09-17") == "2026-09-16"
    assert S.derniere_seance_connue(dossier) == "2026-09-18"

    _, retirees, _ = S.purger_seances_annulees(candles_dir=dossier)
    assert retirees == 2
    for ticker in ("SNA", "STK"):
        jours = [b["d"] for b in json.loads((dossier / f"{ticker}.json").read_text())]
        assert jours == ["2026-09-16", "2026-09-18"], (
            "la purge du 17/09 ne doit jamais emporter la vraie séance du 18/09")


def test_masi_du_17_ne_peut_pas_reprendre_un_data_json_du_18(moteur, tmp_path, monkeypatch):
    precedent_futur = tmp_path / "data.json"
    precedent_futur.write_text(json.dumps({
        "masi": {"value": 18123.45, "change_pct": 0.77,
                 "asof": "2026-09-18", "stale": False}
    }), encoding="utf-8")
    monkeypatch.setattr(moteur, "OUTPUT", precedent_futur)

    masi = {"value": 17953.096, "chg": -0.17,
            "asof": "2026-09-17", "stale": False}
    moteur._ecarter_masi_annule(masi)

    assert masi["asof"] and masi["asof"] < "2026-09-17", (
        f"le MASI annulé du 17/09 a voyagé vers {masi['asof']}")
    assert masi["stale"] is True
    assert masi.get("chg") is None, (
        "une séance annulée ne doit reprendre aucune variation, même d'un repli valide")


def test_cache_historique_est_recalcule_avant_la_garde_et_commite():
    workflow = (RACINE / ".github" / "workflows" / "update_bvc.yml").read_text(
        encoding="utf-8")
    nom_sync = "Synchroniser le cache historique des chandelles modifiées"
    nom_garde = "Contrôles bloquants sur le fichier généré"
    assert nom_sync in workflow, "le cache n'est pas synchronisé après écriture des candles"
    assert workflow.index(nom_sync) < workflow.index(nom_garde), (
        "le cache est recalculé après les tests : la garde voit encore un état incohérent")
    assert "pipeline/recalculer_cache.py --complet" in workflow
    assert "git add pipeline/historical_data.json" in workflow, (
        "un cache recalculé mais non commité disparaîtrait à la fin du runner")
