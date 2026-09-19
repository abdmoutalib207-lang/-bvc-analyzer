#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
P = ROOT / "pipeline"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(P))

spec = importlib.util.spec_from_file_location("rc_diag", P / "recalculer_cache.py")
rc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rc)
m = rc._collecteur()
cache = json.loads((P / "historical_data.json").read_text(encoding="utf-8"))

def calc(serie):
    df = pd.DataFrame([{"date": b["d"], "open": b.get("o"), "high": b.get("h"),
                        "low": b.get("l"), "close": b.get("c"), "volume": b.get("v", 0)}
                       for b in serie])
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    return m.compute_indicators(df)

ok, divergents, invalides = [], {}, {}
for t, entree in sorted(cache.items()):
    if t.startswith("_"):
        continue
    f = P / "candles" / f"{t}.json"
    if not f.exists():
        invalides[t] = "pas de candles"
        continue
    serie = json.loads(f.read_text(encoding="utf-8"))
    date = str(entree.get("last_date") or "")[:10]
    prefixe = [b for b in serie if str(b.get("d") or "")[:10] <= date]
    if not date or not prefixe or prefixe[-1].get("d") != date:
        invalides[t] = f"last_date={date!r} absent du préfixe"
        continue
    try:
        attendu = calc(prefixe)
    except Exception as e:
        invalides[t] = f"calcul: {e}"
        continue
    ecarts = []
    for k in rc.INDICATEURS_COMPLETS:
        if entree.get(k) != attendu.get(k):
            ecarts.append(k)
    if not ecarts:
        ok.append(t)
    else:
        divergents[t] = ecarts

print(json.dumps({
    "reproductibles": len(ok), "tickers_reproductibles": ok,
    "divergents": len(divergents), "details_divergents": divergents,
    "invalides": invalides,
}, ensure_ascii=False, indent=2))
