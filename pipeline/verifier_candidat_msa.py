#!/usr/bin/env python3
"""Comparaison hors réseau du vrai run(dry_run=True), sur 80 titres.

Les cotations sont des fixtures construites depuis data.json, pas les réponses
brutes archivées des fournisseurs. Ce contrôle d'intégration ne certifie ni
une collecte en direct ni un déploiement GitHub Actions.
"""
from __future__ import annotations

import argparse
import copy
import importlib.util
import io
import json
import shutil
import sys
import tempfile
from contextlib import ExitStack, redirect_stdout
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from pipeline.preparer_msa import differences, ecrire_json, sha


def executer(root, serie, entree_cache, instant):
    import pandas as pd
    import requests
    root = Path(root)
    frozen = datetime.fromisoformat(instant)
    if frozen.tzinfo is None:
        raise ValueError("l'instant doit porter son fuseau horaire")
    class Horloge(datetime):
        @classmethod
        def now(cls, tz=None):
            return frozen.astimezone(tz) if tz else frozen.astimezone(timezone.utc).replace(tzinfo=None)

    snapshot = json.loads((root / "data.json").read_text())
    quotes = {r["symbol"]: {"price": r["price"], "chg": r["chg"], "vol": r["vol"],
                           "open": r["open"], "cap": r["cap"],
                           "asof": r["_meta"]["prix_asof"], "src": "idb"}
              for r in snapshot["tickers"]}
    # Conserver CDG pour les lignes déclarées CDG dans le fichier publié.
    cdg = {r["symbol"]: copy.deepcopy(quotes[r["symbol"]]) for r in snapshot["tickers"]
           if r["_meta"]["source_prix"] == "cdg"}
    masi = {"value": snapshot["masi"]["value"], "chg": snapshot["masi"]["change_pct"],
            "asof": snapshot["masi"]["asof"], "stale": snapshot["masi"]["stale"]}
    with tempfile.TemporaryDirectory(prefix="msa-moteur-") as tmp:
        bac = Path(tmp)
        (bac / "pipeline/candles").mkdir(parents=True)
        for pattern in ("*.json", "pipeline/*.json", "pipeline/candles/*.json"):
            for src in root.glob(pattern):
                shutil.copyfile(src, bac / src.relative_to(root))
        cache = json.loads((bac / "pipeline/historical_data.json").read_text())
        cache["MSA"] = copy.deepcopy(entree_cache)
        ecrire_json(bac / "pipeline/historical_data.json", cache)
        ecrire_json(bac / "pipeline/candles/MSA.json", serie)
        before = {str(p.relative_to(bac)): sha(p) for p in bac.rglob("*.json")}
        with ExitStack() as stack:
            http = stack.enter_context(patch.object(requests.sessions.Session, "request",
                                                   side_effect=AssertionError("réseau interdit")))
            socket = stack.enter_context(patch("socket.create_connection",
                                               side_effect=AssertionError("réseau interdit")))
            spec = importlib.util.spec_from_file_location("msa_moteur", root / "update_data.py")
            ud = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(ud)
            ud.__file__ = str(bac / "update_data.py")
            ud.OUTPUT = bac / "data.json"
            ud.IDB_ASOF = max(q["asof"] for q in quotes.values())
            ud._cdg_lignes = []
            for name, value in (("datetime", Horloge), ("fetch_all_idb", lambda: copy.deepcopy(quotes)),
                                ("fetch_all_cdg", lambda: copy.deepcopy(cdg)),
                                ("fetch_all_bmce", lambda *_: {}),
                                ("fetch_masi", lambda: copy.deepcopy(masi)),
                                ("fetch_history", lambda *_a, **_k: pd.DataFrame()),
                                ("fetch_med24_quote", lambda *_: None)):
                stack.enter_context(patch.object(ud, name, value))
            stack.enter_context(patch.object(ud.time, "sleep", lambda *_: None))
            stack.enter_context(patch.dict("os.environ", {"BVC_MODE_AUDIT": "1",
                                                         "BVC_DATE_ANALYSE": instant[:10]}))
            with redirect_stdout(io.StringIO()):
                output = ud.run(dry_run=True, push=False)
            # Un appel réseau attrapé par un repli ne doit pas passer en silence.
            http.assert_not_called()
            socket.assert_not_called()
        after = {str(p.relative_to(bac)): sha(p) for p in bac.rglob("*.json")}
        if before != after:
            raise AssertionError("le dry-run a écrit dans le bac")
        return output


def verifier(root, candidat, instant):
    root, candidat = Path(root), Path(candidat)
    manifest = json.loads((candidat / "rapport.json").read_text())
    if instant[:10] != manifest["date_calcul"]:
        raise ValueError("la date du moteur doit correspondre à celle du recalcul")
    for key, rel in (("serie_MSA", "pipeline/candles/MSA.json"),
                     ("cache", "pipeline/historical_data.json")):
        if sha(root / rel) != manifest["empreintes_entrees"][key]:
            raise ValueError(f"{rel} a changé depuis la construction du candidat")
    for name, expected in manifest["empreintes_sorties"].items():
        if sha(candidat / name) != expected:
            raise ValueError(f"{name}: empreinte candidate incorrecte")
    serie = json.loads((root / "pipeline/candles/MSA.json").read_text())
    nouvelle = json.loads((candidat / "MSA.json").read_text())
    cache = json.loads((root / "pipeline/historical_data.json").read_text())
    recalcule = json.loads((candidat / "cache_MSA_recalcule.json").read_text())
    corrige = json.loads((candidat / "cache_MSA_candidat.json").read_text())
    states = {"A_cache_initial": executer(root, serie, cache["MSA"], instant),
              "B_recalcule_sans_correction": executer(root, serie, recalcule, instant),
              "C_candidat": executer(root, nouvelle, corrige, instant)}
    indexes = {s: {r["symbol"]: r for r in result["tickers"]} for s, result in states.items()}
    a, b, c = indexes.values()
    if not (set(a) == set(b) == set(c) and len(c) == 80):
        raise AssertionError("univers de 80 titres non préservé")
    others = [t for t in a if t != "MSA" and not a[t] == b[t] == c[t]]
    if others:
        raise AssertionError(f"autres titres modifiés : {others}")
    for field in ("price", "chg", "vol", "cap", "pe", "pb", "div", "open"):
        if not a["MSA"][field] == b["MSA"][field] == c["MSA"][field]:
            raise AssertionError(f"champ externe MSA modifié : {field}")
    report = {
        "type": "integration_hors_reseau_sur_cotations_reconstituees",
        "limite": "Fixtures issues du JSON publié ; pas un rejeu des réponses brutes, ni un run GitHub.",
        "instant_fixe": instant, "sha256_snapshot_entree": sha(root / "data.json"),
        "empreintes_code": {name: sha(root / name) for name in (
            "update_data.py", "pipeline/verifier_candidat_msa.py")},
        "titres": len(c), "autres_titres_identiques": 79,
        "ecritures_du_dry_run": 0,
        "A_vers_B": differences(a["MSA"], b["MSA"]),
        "B_vers_C": differences(b["MSA"], c["MSA"]),
        "MSA_candidat": c["MSA"],
        "controles_preservation": {"CMT_price": c["CMT"]["price"],
                                    "CMT_rsi": c["CMT"]["rsi"],
                                    "CMT_n_candles": c["CMT"]["_meta"]["n_candles"],
                                    "SOT_h52w": c["SOT"]["h52w"],
                                    "SGTM_l52w": c["SGTM"]["l52w"]},
    }
    return report


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--candidat", type=Path, required=True)
    ap.add_argument("--instant", required=True)
    args = ap.parse_args()
    report = verifier(ROOT, args.candidat, args.instant)
    # Les sorties sont uniquement un rapport, dans l'espace candidat.
    dest = args.candidat.resolve()
    if not dest.is_relative_to(ROOT / "datasets/historiques_candidats"):
        ap.error("le rapport doit rester dans l'espace candidat du dépôt")
    ecrire_json(dest / "verification_moteur.json", report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
