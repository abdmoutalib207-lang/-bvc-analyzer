#!/usr/bin/env python3
"""Chaque entrée du cache décrit une séance qui existe — 30/09/2026.

⚠️ CE QUI EST ARRIVÉ
Le 30/09 à 01h, douze bougies fantômes du 29/09 (BMCE rediffusait la veille)
ont été retirées de `pipeline/candles/` — mais pas de
`pipeline/historical_data.json`, qui annonçait toujours `last_date` au 29/09.
Rien n'a bougé tant que ces titres ne cotaient pas. À 15h45, M2M a coté : la
synchronisation du cache a cherché la séance du 29/09 dans la série, ne l'a
pas trouvée, et le moteur s'est arrêté (« ancienne date 2026-09-29
absente »). Huit runs de suite, la clôture du 30/09 non publiée.

La garde du moteur avait raison. Ce qui manquait est ce contrôle-ci, qui
aurait fait rougir la PR du nettoyage AVANT sa fusion. Généralisation, à tous
les titres, de la règle posée pour CMT dans `test_serie_et_cache.py`.
"""

from __future__ import annotations

import json
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent


def test_la_derniere_seance_du_cache_existe_dans_les_chandelles():
    cache = json.loads((RACINE / "pipeline" / "historical_data.json")
                       .read_text(encoding="utf-8"))
    fautifs = []
    for t, e in sorted(cache.items()):
        if t.startswith("_") or not isinstance(e, dict) or not e.get("last_date"):
            continue
        f = RACINE / "pipeline" / "candles" / f"{t}.json"
        if not f.exists():
            continue
        serie = json.loads(f.read_text(encoding="utf-8"))
        jusqu_ici = [b for b in serie if b["d"] <= e["last_date"]]
        if not jusqu_ici or jusqu_ici[-1]["d"] != e["last_date"]:
            fautifs.append(f"{t} : {e['last_date']} absent des chandelles")
        elif e.get("n_candles") != len(jusqu_ici):
            fautifs.append(f"{t} : {e.get('n_candles')} séances annoncées, "
                           f"{len(jusqu_ici)} dans la série")
    assert not fautifs, ("cache et chandelles divergent — le moteur refusera "
                         "d'écrire dès que ces titres coteront :\n  "
                         + "\n  ".join(fautifs))
