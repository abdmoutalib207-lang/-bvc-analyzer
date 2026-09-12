#!/usr/bin/env python3
"""Appliquer une série acceptée, et recalculer un cache — sous contrôle.

⚠️ CES DEUX PROGRAMMES ÉCRIVENT DANS LES DONNÉES PUBLIÉES.
Ce sont les seuls du lot à le faire. Ce fichier éprouve ce qui les retient.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE / "pipeline"))


def test_la_serie_acceptee_est_une_instruction_pas_un_signalement():
    """⚠️ La revue a demandé que la différence soit explicite.

    `datasets/historiques_candidats/` PROPOSE ; `datasets/series_acceptees/`
    INSTRUIT. Le dossier fait la distinction, et le fichier la déclare.
    """
    f = RACINE / "datasets" / "series_acceptees" / "CMT.json"
    d = json.loads(f.read_text(encoding="utf-8"))
    assert "REMPLACEMENT PROPOSÉ" in d["_statut"]
    assert "n'est pas un signalement" in d["_ce_qui_est_propose"].lower() \
        or "N'EST PAS un signalement" in d["_ce_qui_est_propose"]


def test_aucune_bougie_negociee_apres_la_suspension():
    """⚠️ Une séance sans échange ne doit jamais entrer comme bougie : ce
    serait fabriquer une cotation le jour où le titre a cessé d'en avoir."""
    from appliquer_serie import verifier
    v = verifier("CMT")
    assert "refus" not in v, v.get("refus")
    assert v["bougies_apres_suspension"] == 0
    serie = json.loads((RACINE / "pipeline" / "candles" / "CMT.json")
                       .read_text(encoding="utf-8"))
    susp = "2026-07-17"
    assert [b["d"] for b in serie if b["d"] >= susp] == []


def test_la_serie_publiee_est_bien_celle_qui_a_ete_acceptee():
    """Le graphique lit `pipeline/candles/CMT.json` : c'est CE fichier qui doit
    porter la série réceptionnée, pas seulement le cache."""
    acceptee = json.loads((RACINE / "datasets" / "series_acceptees" / "CMT.json")
                          .read_text(encoding="utf-8"))
    publiee = json.loads((RACINE / "pipeline" / "candles" / "CMT.json")
                         .read_text(encoding="utf-8"))
    assert len(publiee) == acceptee["seances_negociees"] == 681
    assert [b["d"] for b in publiee] == [b["d"] for b in acceptee["serie"]]
    assert publiee[-1]["c"] == 4350.0 and publiee[-1]["d"] == "2026-07-16"


def test_le_refus_est_la_regle_si_une_bougie_depasse_la_suspension(tmp_path, monkeypatch):
    """⚠️ Un contrôle qui ne sait pas refuser ne contrôle rien."""
    import appliquer_serie as a
    d = json.loads((RACINE / "datasets" / "series_acceptees" / "CMT.json")
                   .read_text(encoding="utf-8"))
    d["serie"] = d["serie"] + [{"d": "2026-08-03", "o": 1, "h": 1, "l": 1,
                                "c": 1, "v": 10}]
    (tmp_path / "CMT.json").write_text(json.dumps(d), encoding="utf-8")
    monkeypatch.setattr(a, "ACCEPTEES", tmp_path)
    r = a.verifier("CMT")
    assert "refus" in r and "suspension" in r["refus"]


def test_le_cache_recalcule_TOUS_ses_indicateurs():
    """⚠️ Ma première version n'en recalculait que six sur vingt : CMT se
    retrouvait avec un RSI issu des 681 nouvelles bougies à côté d'un `h52w`
    calculé sur l'ancienne série de 514. Une entrée mélangée a l'air à jour."""
    from recalculer_cache import INDICATEURS
    cache = json.loads((RACINE / "pipeline" / "historical_data.json")
                       .read_text(encoding="utf-8"))
    champs = {k for k in cache["CMT"] if not k.startswith("_") and k != "candles"}
    manquants = champs - set(INDICATEURS)
    assert manquants == set(), (
        f"ces indicateurs du cache ne sont pas recalculés : {manquants}")


def test_le_cache_de_CMT_porte_les_valeurs_receptionnees():
    cache = json.loads((RACINE / "pipeline" / "historical_data.json")
                       .read_text(encoding="utf-8"))["CMT"]
    assert cache["rsi"] == 42.0
    assert cache["ma20"] == 4624.45
    assert cache["ma50"] == 4769.04
    assert cache["h52w"] == 5940.0
    assert cache["last_close"] == 4350.0
    assert cache["last_date"] == "2026-07-16"
    assert cache["n_candles"] == 681


def test_le_recalcul_n_interroge_aucune_source():
    """⚠️ « Ne pas relancer un import général pour obtenir ce recalcul. »
    Le programme relit les chandelles du dépôt ; il ne doit atteindre ni le
    réseau, ni les sources."""
    # ⚠️ ON CHERCHE DES APPELS, PAS DES CHAÎNES. Ma première version cherchait
    # le mot « bvcscrap » dans le fichier et le trouvait dans le NOM DU MODULE
    # importé — une mention n'est pas un accès. Quatrième fois que ce piège se
    # présente dans ce projet ; on lit l'arbre syntaxique.
    import ast
    src = (RACINE / "pipeline" / "recalculer_cache.py").read_text(encoding="utf-8")
    arbre = ast.parse(src)

    reseau = {"requests", "urllib", "http", "socket", "httpx", "aiohttp"}
    for n in ast.walk(arbre):
        noms = []
        if isinstance(n, ast.Import):
            noms = [a.name.split(".")[0] for a in n.names]
        elif isinstance(n, ast.ImportFrom) and n.module:
            noms = [n.module.split(".")[0]]
        for nom in noms:
            assert nom not in reseau, f"le recalcul importe « {nom} » (ligne {n.lineno})"

    # Aucun appel aux fonctions de COLLECTE du collecteur.
    # ⚠️ `main` et `run` sont exclus de la liste : ce module a les siens, et
    # les y inclure faisait échouer le test sur son propre point d'entrée.
    collecte = {"fetch_bvcscrap_extension", "load_xlsx", "load_export",
                "save_candle_file", "adjust_splits_df"}
    for n in ast.walk(arbre):
        if isinstance(n, ast.Call):
            cible = getattr(n.func, "attr", None) or getattr(n.func, "id", None)
            if cible in collecte:
                raise AssertionError(
                    f"le recalcul appelle « {cible} » (ligne {n.lineno}) : "
                    f"il relancerait une collecte")
    # Et il ne doit appeler du collecteur QUE `compute_indicators`.
    depuis_collecteur = {getattr(n.func, "attr", None) for n in ast.walk(arbre)
                         if isinstance(n, ast.Call)
                         and getattr(getattr(n.func, "value", None), "id", None) == "m"}
    assert depuis_collecteur <= {"compute_indicators"}, (
        f"le recalcul appelle autre chose que compute_indicators : "
        f"{depuis_collecteur}")


def test_la_selection_des_lignes_n_est_pas_generalisee():
    """⚠️ « Absence de quantité renseignée ne prouve pas absence d'échange. »

    Les 18 lignes anciennes sans quantité sont exclues DE CETTE sélection, et
    le fichier doit le dire — sans en faire une règle générale.
    """
    d = json.loads((RACINE / "datasets" / "series_acceptees" / "CMT.json")
                   .read_text(encoding="utf-8"))
    s = d["_selection"]
    assert "ne prouve pas" in s
    assert "n'est pas généralisée" in s or "pas généralisée" in s
