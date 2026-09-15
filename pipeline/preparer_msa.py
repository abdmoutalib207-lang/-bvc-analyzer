#!/usr/bin/env python3
"""Construit le lot candidat MSA de 22 séances, sans écrire de donnée servie.

Les deux exports et le journal avant/après sont les preuves de ce lot précis.
Le calcul réutilise le producteur du cache à une date explicitement fixée.
"""
from __future__ import annotations

import argparse
import copy
import csv
import hashlib
import json
import math
import os
import shutil
import sys
import tempfile
from datetime import date
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
LOT = ROOT / "datasets/historiques_candidats/MSA_22"
CHAMPS = {"o": "Ouverture", "h": "Plus Haut", "l": "Plus Bas",
          "c": "Dernier Cours", "v": "Titres Échangés"}
DATES = tuple("2026-" + d for d in (
    "05-13", "05-14", "05-15", "05-18", "05-19", "05-20", "05-21",
    "05-22", "05-25", "05-26", "06-01", "06-02", "06-03", "06-04",
    "06-05", "06-08", "06-09", "06-10", "06-11", "06-12", "06-15", "06-16"))


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def ecrire_json(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2,
                                    allow_nan=False) + "\n", encoding="utf-8")


def lire_export(lot, ref, ticker):
    path = (lot / ref["fichier"]).resolve()
    if not path.is_relative_to(lot.resolve()) or sha(path) != ref["sha256"]:
        raise ValueError(f"{ticker}: empreinte ou chemin source incorrect")
    rows = {}
    with path.open(encoding="utf-8-sig", newline="") as stream:
        for row in csv.DictReader(stream, delimiter=";"):
            if (row["Ticker"].strip() != ticker or
                    row["Instrument"].strip() != ref["instrument"]):
                raise ValueError(f"{ticker}: identité source incorrecte")
            j, m, a = row["Séance"].split("/")
            d = date(int(a), int(m), int(j)).isoformat()
            if d in rows:
                raise ValueError(f"{ticker}: date source dupliquée {d}")
            rows[d] = row
    return rows


def reference(row):
    bar = {k: float(row[col]) for k, col in CHAMPS.items()}
    if not all(math.isfinite(v) and v > 0 for v in bar.values()):
        raise ValueError("référence OHLCV non finie, absente ou non positive")
    if not bar["l"] <= min(bar["o"], bar["c"]) <= max(bar["o"], bar["c"]) <= bar["h"]:
        raise ValueError("référence OHLC incohérente")
    if not bar["v"].is_integer():
        raise ValueError("quantité de titres non entière")
    bar["v"] = int(bar["v"])
    return bar


def remplacer(serie, plan, sources):
    """Valide toutes les préconditions avant de construire la copie."""
    if plan["ticker"] != "MSA" or tuple(r["d"] for r in plan["lignes"]) != DATES:
        raise ValueError("le lot doit contenir exactement les 22 dates MSA acceptées")
    dates = [b["d"] for b in serie]
    if dates != sorted(set(dates)):
        raise ValueError("la série doit avoir des dates uniques et triées")
    by_date = {b["d"]: b for b in serie}
    journal = []
    for instruction in plan["lignes"]:
        d = instruction["d"]
        if d not in by_date:
            raise ValueError(f"{d}: bougie initiale absente")
        before = by_date[d]
        proposed = reference(sources["MSA"][d])
        if instruction["propose"] != proposed:
            raise ValueError(f"{d}: proposition différente de l'export Marsa Maroc")
        old = {k: before.get(k) for k in CHAMPS}
        if old != instruction["ancien"]:
            raise ValueError(f"{d}: état initial différent du journal accepté")
        if old["c"] != float(sources["MUT"][d]["Dernier Cours"]):
            raise ValueError(f"{d}: contamination par Mutandis non reproduite")
        turnover = float(sources["MSA"][d]["Volume (MAD)"])
        if not math.isfinite(turnover) or turnover <= 0:
            raise ValueError(f"{d}: montant MAD invalide")
        journal.append({"d": d, "ancien": copy.deepcopy(before),
                        "propose": {**before, **proposed},
                        "volume_mad_source": turnover,
                        "unite_v_propose": "titres échangés",
                        "identite_source": "SODEP-Marsa Maroc",
                        "source_sha256": plan["sources"]["MSA"]["sha256"]})
    replacements = {r["d"]: r["propose"] for r in journal}
    candidate = [copy.deepcopy(replacements.get(b["d"], b)) for b in serie]
    return candidate, journal


def indicateurs(serie, jour):
    """Même producteur et même horloge pour la série initiale et corrigée."""
    import pandas as pd
    from pipeline.recalculer_cache import _collecteur

    with patch.object(sys, "argv", ["preparer_msa.py"]):
        collecteur = _collecteur()
    class TimestampFixe:
        @staticmethod
        def now():
            return pd.Timestamp(jour)
    class PandasFixe:
        Timestamp = TimestampFixe
        def __getattr__(self, name):
            return getattr(pd, name)
    df = pd.DataFrame([{"date": b["d"], "open": b["o"], "high": b["h"],
                        "low": b["l"], "close": b["c"], "volume": b["v"]}
                       for b in serie])
    df["date"] = pd.to_datetime(df["date"])
    with patch.object(collecteur, "pd", PandasFixe()):
        return collecteur.compute_indicators(df)


def differences(before, after):
    return {k: {"avant": before.get(k), "apres": after.get(k)}
            for k in sorted(before.keys() | after.keys())
            if k != "candles" and before.get(k) != after.get(k)}


def preparer(root, lot, sortie, jour):
    root, lot, sortie = Path(root).resolve(), Path(lot).resolve(), Path(sortie).resolve()
    date.fromisoformat(jour)
    # Toute sortie située dans le dépôt doit rester dans l'espace candidat.
    if sortie.is_relative_to(root) and not sortie.is_relative_to(root / "datasets/historiques_candidats"):
        raise ValueError("sortie interdite : choisir un dossier candidat ou extérieur au dépôt")
    if sortie.exists():
        raise ValueError("la sortie existe déjà : refus de l'écraser")
    plan = json.loads((lot / "plan.json").read_text(encoding="utf-8"))
    sources = {t: lire_export(lot, ref, t) for t, ref in plan["sources"].items()}
    path_serie = root / "pipeline/candles/MSA.json"
    path_cache = root / "pipeline/historical_data.json"
    serie = json.loads(path_serie.read_text(encoding="utf-8"))
    if serie[-1]["d"] > jour:
        raise ValueError("la date de calcul précède la dernière bougie")
    candidate, journal = remplacer(serie, plan, sources)
    cache = json.loads(path_cache.read_text(encoding="utf-8"))
    initial = cache["MSA"]
    recalcule = {**initial, **indicateurs(serie, jour)}
    corrige = {**initial, **indicateurs(candidate, jour)}
    report = {
        "statut": "candidat_non_applique", "date_calcul": jour,
        "base_git_du_journal": plan["base_git"],
        "empreintes_entrees": {"serie_MSA": sha(path_serie), "cache": sha(path_cache),
                               "plan": sha(lot / "plan.json")},
        "empreintes_code": {name: sha(ROOT / name) for name in (
            "pipeline/preparer_msa.py", "pipeline/collect_history_bvcscrap.py",
            "pipeline/recalculer_cache.py", "update_data.py")},
        "seances": len(candidate), "seances_remplacees": len(journal),
        "valeurs_ohlcv_remplacees": sum(a["ancien"][k] != a["propose"][k]
                                        for a in journal for k in CHAMPS),
        "dates_ajoutees": [], "dates_supprimees": [], "autres_titres_recalcules": [],
        "cache_initial_vers_recalcule_sans_correction": differences(initial, recalcule),
        "effet_des_22_corrections_seules": differences(recalcule, corrige),
        "cache_initial_vers_candidat": differences(initial, corrige),
        "bougies_modifiees_dans_la_copie_du_cache": sum(
            a != b for a, b in zip(recalcule["candles"], corrige["candles"])),
        "limites": ["Les autres écarts MSA restent à traiter.",
                    "L'unité de v n'est validée que sur ces 22 lignes.",
                    "Aucun coefficient d'ajustement supplémentaire n'est appliqué.",
                    "Recalculer les indicateurs ne certifie pas les bougies conservées.",
                    "Aucune donnée servie ni aucun cache global n'est écrit."],
    }
    sortie.parent.mkdir(parents=True, exist_ok=True)
    temp = Path(tempfile.mkdtemp(prefix=".msa-", dir=sortie.parent))
    try:
        for name, value in (("MSA.json", candidate), ("journal.json", journal),
                            ("cache_MSA_initial.json", initial),
                            ("cache_MSA_recalcule.json", recalcule),
                            ("cache_MSA_candidat.json", corrige)):
            ecrire_json(temp / name, value)
        report["empreintes_sorties"] = {p.name: sha(p) for p in sorted(temp.iterdir())}
        ecrire_json(temp / "rapport.json", report)
        if sortie.exists():
            raise ValueError("la sortie vient d'être créée : refus de l'écraser")
        os.rename(temp, sortie)
    finally:
        if temp.exists():
            shutil.rmtree(temp)
    return report


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--sortie", type=Path, required=True)
    ap.add_argument("--date-calcul", required=True)
    args = ap.parse_args()
    sys.path.insert(0, str(ROOT))
    r = preparer(ROOT, LOT, args.sortie, args.date_calcul)
    print(json.dumps(r, ensure_ascii=False, indent=2))
