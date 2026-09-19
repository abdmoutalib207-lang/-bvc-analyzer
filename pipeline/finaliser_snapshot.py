#!/usr/bin/env python3
"""Rattrape data.json quand les chandelles validées sont plus fraîches.

Le collecteur écrit d'abord data.json puis les chandelles de la séance. Si une
source live est en retard, le premier passage peut donc publier J-2 alors que la
bougie J vient d'être validée quelques secondes plus tard. Ce finaliseur fait un
second calcul *sans écriture de collecte* (``run(dry_run=True)``), puis ne
remplace que les tickers dont data.json était réellement en retard.

Aucune chandelle n'est créée ici et aucune séance annulée n'est prise comme
référence. Le fichier courant reste intact si le recalcul n'arrive pas au moins
à la date déjà prouvée par les chandelles locales.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Callable

RACINE = Path(__file__).resolve().parent.parent
DATA = RACINE / "data.json"
CANDLES = RACINE / "pipeline" / "candles"


def _seance_annulee(date_iso: str) -> bool:
    try:
        if str(RACINE) not in sys.path:
            sys.path.insert(0, str(RACINE))
        from bvc_config import seance_annulee
        return bool(seance_annulee(date_iso))
    except Exception:
        return False


def _derniere_date_valide(fichier: Path) -> str:
    try:
        serie = json.loads(fichier.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return ""
    dates = sorted({str(b.get("d") or "")[:10] for b in (serie or [])
                    if b.get("d") and not _seance_annulee(str(b.get("d"))[:10])})
    return dates[-1] if dates else ""


def retards_snapshot(data_path: Path = DATA, candles_dir: Path = CANDLES) -> dict[str, str]:
    """Renvoie {ticker: date_chandelle} quand data.json est derrière le brut validé."""
    try:
        data = json.loads(data_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    actuels = {str(x.get("symbol") or "").upper():
               str((x.get("_meta") or {}).get("prix_asof") or "")[:10]
               for x in data.get("tickers", [])}
    retards: dict[str, str] = {}
    if not candles_dir.exists():
        return retards
    for f in candles_dir.glob("*.json"):
        ticker = f.stem.upper()
        derniere = _derniere_date_valide(f)
        if derniere and derniere > actuels.get(ticker, ""):
            retards[ticker] = derniere
    return dict(sorted(retards.items()))


def _masi_candidat_sain(candidat: dict, actuel: dict) -> bool:
    if not isinstance(candidat, dict) or not candidat.get("value"):
        return False
    d_c = str(candidat.get("asof") or "")[:10]
    d_a = str((actuel or {}).get("asof") or "")[:10]
    if not d_c or _seance_annulee(d_c):
        return False
    return not d_a or d_c >= d_a


def finaliser(data_path: Path = DATA, candles_dir: Path = CANDLES,
              runner: Callable[[], dict | None] | None = None) -> dict:
    """Répare uniquement les tickers en retard et renvoie un rapport."""
    retards = retards_snapshot(data_path, candles_dir)
    if not retards:
        rapport = {"modifie": False, "retards": {}, "message": "snapshot déjà aligné"}
        print(json.dumps(rapport, ensure_ascii=False))
        return rapport

    courant = json.loads(data_path.read_text(encoding="utf-8"))
    if runner is None:
        # Exécuté comme ``python pipeline/finaliser_snapshot.py`` : Python place
        # ``pipeline/`` en tête de sys.path, pas la racine où vit update_data.py.
        # On ajoute explicitement la racine avant l'import tardif.
        if str(RACINE) not in sys.path:
            sys.path.insert(0, str(RACINE))
        import update_data
        runner = lambda: update_data.run(dry_run=True)

    candidat = runner()
    if not isinstance(candidat, dict):
        raise RuntimeError("le recalcul local n'a produit aucun snapshot")

    candidats = {str(x.get("symbol") or "").upper(): x
                  for x in candidat.get("tickers", [])}
    non_resolus: dict[str, dict] = {}
    remplacements: dict[str, dict] = {}
    for ticker, cible in retards.items():
        ligne = candidats.get(ticker)
        asof = str(((ligne or {}).get("_meta") or {}).get("prix_asof") or "")[:10]
        if not ligne or not asof or asof < cible:
            non_resolus[ticker] = {"cible": cible, "obtenu": asof or None}
        else:
            remplacements[ticker] = ligne
    if non_resolus:
        raise RuntimeError(
            "rattrapage incomplet — data.json laissé intact : " +
            json.dumps(non_resolus, ensure_ascii=False, sort_keys=True))

    sortie = dict(courant)
    sortie["tickers"] = [remplacements.get(str(x.get("symbol") or "").upper(), x)
                         for x in courant.get("tickers", [])]
    for cle in ("updated", "date_analyse", "market_status"):
        if candidat.get(cle) is not None:
            sortie[cle] = candidat[cle]
    if _masi_candidat_sain(candidat.get("masi") or {}, courant.get("masi") or {}):
        sortie["masi"] = candidat["masi"]

    # Écriture atomique : aucune demi-écriture si le runner est interrompu.
    data_path.parent.mkdir(parents=True, exist_ok=True)
    fd, nom = tempfile.mkstemp(prefix=data_path.name + ".", suffix=".tmp",
                               dir=str(data_path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as h:
            json.dump(sortie, h, ensure_ascii=False, indent=2)
        Path(nom).replace(data_path)
    finally:
        try:
            Path(nom).unlink(missing_ok=True)
        except OSError:
            pass

    rapport = {
        "modifie": True,
        "retards": retards,
        "remplaces": sorted(remplacements),
        "n_remplaces": len(remplacements),
    }
    print(json.dumps(rapport, ensure_ascii=False, indent=2))
    return rapport


if __name__ == "__main__":
    finaliser()
