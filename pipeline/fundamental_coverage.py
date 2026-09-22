#!/usr/bin/env python3
"""Audit reproductible de la couverture fondamentale du terminal.

Ce module ne modifie ni la formule v5.3 ni les notes. Il répond à une question
plus simple et plus importante : quelle part du bloc fondamental repose sur des
données présentes, et quelle part vient encore de valeurs de repli ?

Il distingue trois niveaux :
- ratios affichés dans data.json (PER, P/Book, dividende) ;
- provenance du bloc fondamental publié (BPA calculé ou table figée) ;
- couverture des quatre blocs utilisés par pipeline.smart_money.fond_score.

Une absence reste une absence. Aucun zéro, moyenne ou valeur neutre n'est
inventé pour améliorer artificiellement la couverture.
"""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data.json"
FOND = ROOT / "fondamentaux.json"
BPA = ROOT / "bpa.json"
FAITS = ROOT / "pipeline" / "faits_financiers.json"

# Pondérations du score fondamental v5.3.
BLOCKS = {
    "qualite": (40, ("roic", "wacc")),
    "croissance": (30, ("croissance_bpa", "croissance_ca")),
    "valorisation": (20, ("forward_per",)),
    "bilan": (10, ("dette_nette_ebitda", "cash_conversion")),
}


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def coverage_for(entry: dict | None) -> dict:
    """Couverture d'une fiche fondamentaux.json, sans aucune valeur de repli."""
    f = entry or {}
    pct = 0
    covered: list[str] = []
    missing: list[dict] = []
    for block, (weight, fields) in BLOCKS.items():
        absent = [field for field in fields if f.get(field) is None]
        if absent:
            missing.append({"bloc": block, "poids": weight, "champs": absent})
        else:
            pct += weight
            covered.append(block)
    return {
        "coverage_pct": pct,
        "status": "COMPLET" if pct == 100 else ("PARTIEL" if pct else "INSUFFISANT"),
        "blocks_covered": covered,
        "blocks_missing": missing,
    }


def build_report(data: dict | None = None, fondamentaux: dict | None = None,
                 bpa: dict | None = None, faits: dict | None = None) -> dict:
    data = data if data is not None else _load(DATA)
    fondamentaux = fondamentaux if fondamentaux is not None else _load(FOND)
    bpa = bpa if bpa is not None else _load(BPA)
    faits = faits if faits is not None else _load(FAITS)

    rows = data.get("tickers") or []
    details = {}
    source_fond = Counter()
    pb_source = Counter()
    missing_pe: list[str] = []
    missing_pb: list[str] = []
    missing_div: list[str] = []
    coverage_dist = Counter()

    for row in rows:
        sym = row.get("symbol") or row.get("ticker")
        if not sym:
            continue
        meta = row.get("_meta") or {}
        cov = coverage_for(fondamentaux.get(sym))
        coverage_dist[cov["coverage_pct"]] += 1
        src = meta.get("source_fond") or "non_indiquee"
        pbs = meta.get("pb_source") or "non_indiquee"
        source_fond[src] += 1
        pb_source[pbs] += 1

        if row.get("pe") is None:
            missing_pe.append(sym)
        if row.get("pb") is None:
            missing_pb.append(sym)
        if row.get("div") is None:
            missing_div.append(sym)

        details[sym] = {
            **cov,
            "score_fond_publie": row.get("score_fond"),
            "source_fond": src,
            "pb_source": pbs,
            "pe_disponible": row.get("pe") is not None,
            "pb_disponible": row.get("pb") is not None,
            "dividende_disponible": row.get("div") is not None,
            "bpa_verifie": sym in bpa,
            "faits_ammc": sym in faits,
        }

    complete = sorted(s for s, d in details.items() if d["coverage_pct"] == 100)
    partial = sorted(s for s, d in details.items() if 0 < d["coverage_pct"] < 100)
    insufficient = sorted(s for s, d in details.items() if d["coverage_pct"] == 0)
    absent_fond = sorted(s for s in details if s not in fondamentaux)

    return {
        "summary": {
            "titres": len(details),
            "fondamentaux_complets": len(complete),
            "fondamentaux_partiels": len(partial),
            "fondamentaux_insuffisants": len(insufficient),
            "absents_de_fondamentaux_json": len(absent_fond),
            "per_manquants": len(missing_pe),
            "pb_manquants": len(missing_pb),
            "dividendes_manquants": len(missing_div),
            "source_fond": dict(sorted(source_fond.items())),
            "pb_source": dict(sorted(pb_source.items())),
            "coverage_distribution": {str(k): coverage_dist[k] for k in sorted(coverage_dist)},
        },
        "lists": {
            "complets": complete,
            "partiels": partial,
            "insuffisants": insufficient,
            "absents_de_fondamentaux_json": absent_fond,
            "per_manquants": sorted(missing_pe),
            "pb_manquants": sorted(missing_pb),
            "dividendes_manquants": sorted(missing_div),
        },
        "tickers": details,
    }


def main() -> int:
    report = build_report()
    out = ROOT / "fundamentals_coverage.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    s = report["summary"]
    print(
        f"Fondamentaux: {s['fondamentaux_complets']}/{s['titres']} complets · "
        f"{s['fondamentaux_partiels']} partiels · "
        f"{s['fondamentaux_insuffisants']} insuffisants · "
        f"PB manquants {s['pb_manquants']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
