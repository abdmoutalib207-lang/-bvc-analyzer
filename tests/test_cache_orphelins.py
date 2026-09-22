#!/usr/bin/env python3
"""Une entrée de cache ne disparaît pas parce que le collecteur ignore le titre.

⚠️ CE QUI EST ARRIVÉ — T2S, DEUX FOIS
─────────────────────────────────────
    19/09  T2S est ajouté à `historical_data.json` : c'était le seul titre
           ayant des chandelles sans entrée de cache, et son absence faisait
           échouer `recalculer_cache.py --sync-ajouts` en code 2.
    21/09  `collect_history_bvcscrap.py` tourne et réécrit le cache.
           T2S n'est ni dans les exports XLSX ni dans `MANUAL_MAP`, donc
           jamais parcouru, donc jamais conservé → **effacé**.
    22/09  le moteur recalcule ses indicateurs à la volée ; le contrôle qui
           compare cache et recalcul diverge d'un centime sur `ma20`
           (229,75 contre 229,76) et BLOQUE la publication.

Deux jours de bulletin perdus pour une entrée absente.

⚠️ LA GARDE QUI EXISTAIT NE SUFFISAIT PAS
─────────────────────────────────────────
`run()` relit bien le cache avant la boucle et conserve l'entrée d'un titre
ÉCARTÉ pendant celle-ci. Mais `all_tickers` vaut `xlsx ∪ MANUAL_MAP` : un
titre absent des deux n'entre jamais dans la boucle. La garde le protégeait
d'un écartement ; elle ne le protégeait pas d'une absence.

C'est la différence entre « je passe mon tour sur ce titre » et « ce titre
n'existe pas pour moi ». Le second efface.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))
sys.path.insert(0, str(RACINE / "pipeline"))


# Une série plus courte que 14 séances ne permet pas de calculer un RSI, et le
# producteur REFUSE alors d'écrire une entrée — à raison. C'est le même seuil
# que celui du score de confiance (« +1 RSI calculable — au moins 14 chandelles
# réelles »). Ces titres-là n'ont légitimement pas d'entrée : ce sont des séries
# tout juste ouvertes par un import de bulletin, une ou deux séances.
_SEANCES_MIN_POUR_INDICATEURS = 14


def test_les_series_exploitables_ont_toutes_une_entree_de_cache():
    """⚠️ L'INVARIANT SUR LE DÉPÔT — c'est lui qui a manqué.

    Tout titre dont la série permet de calculer des indicateurs doit avoir son
    entrée de cache. Sans quoi le moteur recalcule à la volée et le contrôle de
    reproductibilité diverge sur le dernier centime — c'est exactement ce qui a
    bloqué la publication du 22/09.

    ⚠️ Le seuil n'est pas une commodité : en dessous, le producteur REFUSE
    d'écrire une entrée, et il a raison. Exiger l'entrée quand même rendrait ce
    test impossible à satisfaire, donc bon à désactiver — le contraire du but.
    """
    cache = json.loads((RACINE / "pipeline" / "historical_data.json")
                       .read_text(encoding="utf-8"))
    connus = {k for k in cache if not k.startswith("_")}
    manquantes = []
    for f in sorted((RACINE / "pipeline" / "candles").glob("*.json")):
        if f.stem.startswith(".") or f.stem in connus:
            continue
        serie = json.loads(f.read_text(encoding="utf-8"))
        if len(serie) >= _SEANCES_MIN_POUR_INDICATEURS:
            manquantes.append(f"{f.stem} ({len(serie)} séances)")
    assert not manquantes, (
        f"{len(manquantes)} titre(s) ont une série exploitable sans entrée de "
        f"cache : {manquantes}. `--sync-ajouts` refusera en code 2 et la "
        f"publication sera bloquée dès que leur bougie du jour changera.")


def test_une_entree_inconnue_de_la_collecte_est_conservee():
    """Le comportement, sur la fonction qui décide."""
    import collect_history_bvcscrap as C
    cache = {"_updated": "x", "_tickers": 2,
             "HORS": {"ma20": 229.76}, "DEDANS": {"ma20": 10.0}}
    results = {"DEDANS": {"ma20": 11.0}}          # ce run n'a produit que DEDANS
    conserves = C.conserver_orphelins(results, cache)
    assert conserves == ["HORS"]
    assert results["HORS"] == {"ma20": 229.76}


def test_la_conservation_n_ecrase_jamais_un_resultat_frais():
    """⚠️ Contre-épreuve indispensable : conserver ne doit pas faire RECULER.
    Un titre que ce run vient de recalculer garde sa valeur neuve."""
    import collect_history_bvcscrap as C
    cache = {"T": {"ma20": 1.0, "last_date": "2026-09-18"}}
    results = {"T": {"ma20": 2.0, "last_date": "2026-09-21"}}
    assert C.conserver_orphelins(results, cache) == []
    assert results["T"]["last_date"] == "2026-09-21"


def test_les_clefs_techniques_ne_deviennent_pas_des_titres():
    """`_updated`, `_source`, `_tickers` décrivent le fichier, pas un titre."""
    import collect_history_bvcscrap as C
    cache = {"_updated": "x", "_source": "y", "_tickers": 0}
    results = {}
    assert C.conserver_orphelins(results, cache) == []
    assert results == {}


def test_un_cache_vide_ou_illisible_ne_fait_rien():
    import collect_history_bvcscrap as C
    results = {"A": {"ma20": 1.0}}
    assert C.conserver_orphelins(results, {}) == []
    assert results == {"A": {"ma20": 1.0}}
