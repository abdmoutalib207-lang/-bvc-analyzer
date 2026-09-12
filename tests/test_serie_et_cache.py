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
    from recalculer_cache import INDICATEURS_COMPLETS
    cache = json.loads((RACINE / "pipeline" / "historical_data.json")
                       .read_text(encoding="utf-8"))
    champs = {k for k in cache["CMT"] if not k.startswith("_")}
    manquants = champs - set(INDICATEURS_COMPLETS)
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
    # ⚠️ Deux fonctions, et deux seulement : `compute_indicators` pour le
    # recalcul complet, `calc_rsi` pour le recalcul RSI seul. Tout autre appel
    # au collecteur rouvrirait une collecte.
    assert depuis_collecteur <= {"compute_indicators", "calc_rsi"}, (
        f"le recalcul appelle autre chose : {depuis_collecteur}")


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


# ═══ UN RECALCUL RSI SEUL NE TOUCHE À RIEN D'AUTRE ════════════════════════

def _copie_bac(tmp_path, tickers):
    """Un cache et des chandelles jetables.

    ⚠️ LE CACHE VIENT DE `origin/main`, PAS DU DÉPÔT COURANT.
    Ma première version copiait le cache déjà corrigé : le recalcul rendait
    alors la même valeur, aucune écriture n'avait lieu, et le test ne
    démontrait rien — la mutation ne le faisait pas tomber. Un bac de test doit
    partir de l'état d'AVANT.
    """
    import shutil
    import subprocess
    (tmp_path / "pipeline" / "candles").mkdir(parents=True)
    try:
        cache = json.loads(subprocess.check_output(
            ["git", "show", "origin/main:pipeline/historical_data.json"],
            text=True, cwd=RACINE, stderr=subprocess.DEVNULL))
    except subprocess.CalledProcessError:
        pytest.skip("origin/main absent de ce clone")
    garde = {k: v for k, v in cache.items() if k.startswith("_") or k in tickers}
    # ⚠️ ON FORCE LE CHEMIN D'ÉCRITURE POUR CHAQUE TITRE DU BAC.
    # Le recalcul sort avant d'écrire quand le RSI ne change pas. SOT est dans
    # ce cas — et c'est précisément SOT qui doit démontrer que `h52w` n'est pas
    # touché. Sans cette perturbation, la mutation qui transforme le recalcul
    # RSI en recalcul complet passait inaperçue : le test ne l'atteignait pas.
    for t in tickers:
        if t in garde:
            garde[t] = dict(garde[t])
            garde[t]["rsi"] = -1.0       # valeur impossible : l'écriture aura lieu
    (tmp_path / "pipeline" / "historical_data.json").write_text(
        json.dumps(garde, ensure_ascii=False), encoding="utf-8")
    for t in tickers:
        shutil.copy(RACINE / "pipeline" / "candles" / f"{t}.json",
                    tmp_path / "pipeline" / "candles" / f"{t}.json")
    return tmp_path / "pipeline" / "historical_data.json"


def test_un_recalcul_rsi_seul_ne_modifie_aucun_autre_champ(tmp_path, monkeypatch):
    """⚠️ LE CONTRÔLE DEMANDÉ PAR LA REVUE DU 12/09, ET IL PORTE SUR SOT.

    Mon recalcul COMPLET, appliqué à tous les titres, faisait passer
    `SOT.h52w` de **380** à **1 700**. La valeur venait de la bougie du
    05/05/2026 — `o = h = 1700`, `l = c = 369` — qui mêle deux bases de prix,
    avant et après le split 1:5.

    Rien dans le correctif du RSI ne justifiait de toucher à `h52w`. Un
    recalcul n'assainit pas une donnée : il la relit, anomalie comprise.
    L'assainissement de Sothema est un lot distinct.
    """
    import recalculer_cache as rc

    # ⚠️ LA LISTE COMPTE, ET MA PREMIÈRE VERSION ÉTAIT AVEUGLE.
    # Elle ne contenait que SOT, SGTM et ADH — trois titres dont le RSI ne
    # change PAS. La boucle sortait donc avant d'écrire, et la mutation qui
    # transformait ce recalcul en recalcul complet ne faisait pas tomber le
    # test : il n'empruntait jamais le chemin d'écriture.
    #
    # AKD, ALU et CIM ont un RSI qui bouge : c'est sur eux que la garantie
    # « un seul champ » se démontre. SOT reste, pour la démonstration inverse.
    tickers = ["AKD", "ALU", "CIM", "SOT", "SGTM"]
    cache_f = _copie_bac(tmp_path, tickers)
    monkeypatch.setattr(rc, "CACHE", cache_f)
    monkeypatch.setattr(rc, "CANDLES", tmp_path / "pipeline" / "candles")

    avant = json.loads(cache_f.read_text(encoding="utf-8"))
    r = rc.recalculer(complets=[], rsi_seul=tickers)
    apres = r["_nouveau"]

    for t in tickers:
        modifies = {k for k in set(avant[t]) | set(apres[t])
                    if avant[t].get(k) != apres[t].get(k)}
        assert modifies <= {"rsi"}, (
            f"{t} : un recalcul RSI seul a modifié {sorted(modifies - {'rsi'})}")

    # Le chemin d'écriture est bien emprunté, sinon le test ne prouve rien.
    ecrits = [t for t in tickers if avant[t].get("rsi") != apres[t].get("rsi")]
    assert set(ecrits) == set(tickers), (
        f"le chemin d'écriture n'est pas emprunté pour tous : {ecrits}")

    # ⚠️ La démonstration nommée : 1 700 ne revient pas.
    assert apres["SOT"]["h52w"] == avant["SOT"]["h52w"] == 380.0, (
        "le recalcul RSI seul a touché à h52w — l'anomalie du 05/05 revient")
    assert apres["SOT"]["h52w"] != 1700.0
    assert apres["SGTM"]["l52w"] == avant["SGTM"]["l52w"]


def test_le_recalcul_complet_est_reserve_aux_series_remplacees(tmp_path, monkeypatch):
    """⚠️ La contre-épreuve : en mode COMPLET, SOT reprend bien 1 700.

    Ce n'est pas un défaut du calcul — c'est ce que la bougie contient. C'est
    précisément pourquoi le mode complet ne doit viser que les titres dont la
    série a été remplacée.
    """
    import recalculer_cache as rc

    cache_f = _copie_bac(tmp_path, ["SOT"])
    monkeypatch.setattr(rc, "CACHE", cache_f)
    monkeypatch.setattr(rc, "CANDLES", tmp_path / "pipeline" / "candles")

    r = rc.recalculer(complets=["SOT"], rsi_seul=[])
    assert r["_nouveau"]["SOT"]["h52w"] == 1700.0, (
        "la contre-épreuve ne démontre plus rien : le mode complet ne reprend "
        "plus la valeur de la bougie du 05/05")


def test_les_deux_operations_sont_nommees_separement():
    """Le programme doit exposer deux portées distinctes, pas un seul mode."""
    import recalculer_cache as rc
    assert rc.INDICATEUR_RSI == ("rsi",)
    assert len(rc.INDICATEURS_COMPLETS) > 10
    src = (RACINE / "pipeline" / "recalculer_cache.py").read_text(encoding="utf-8")
    assert "--complet" in src and "--rsi-seul" in src


def test_hors_CMT_le_cache_livre_ne_differe_que_par_le_rsi():
    """⚠️ Le contrôle sur la LIVRAISON elle-même, pas sur un bac de test."""
    import subprocess
    try:
        base = json.loads(subprocess.check_output(
            ["git", "show", "origin/main:pipeline/historical_data.json"],
            text=True, cwd=RACINE, stderr=subprocess.DEVNULL))
    except subprocess.CalledProcessError:
        pytest.skip("origin/main absent de ce clone")
    livre = json.loads((RACINE / "pipeline" / "historical_data.json")
                       .read_text(encoding="utf-8"))
    fautifs = {}
    for t in (k for k in base if not k.startswith("_") and k != "CMT"):
        d = {k for k in set(base[t]) | set(livre.get(t, {}))
             if base[t].get(k) != livre.get(t, {}).get(k)}
        if d - {"rsi"}:
            fautifs[t] = sorted(d - {"rsi"})
    assert fautifs == {}, f"champs hors rsi modifiés hors CMT : {fautifs}"
