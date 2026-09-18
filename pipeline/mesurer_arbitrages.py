#!/usr/bin/env python3
"""Remesure les deux arbitrages ouverts, à partir de l'état COURANT du dépôt.

⚠️ POURQUOI UN PROGRAMME PLUTÔT QU'UN GESTE
───────────────────────────────────────────
Le dossier `datasets/historiques_candidats/ARBITRAGES/mesures.json` est une
PHOTO. Chaque lot de correction la périme : recalculer le cache d'un titre
retire sa fausse MA200 au passage, et le compte descend — 32, puis 28, puis 27.

Je l'ai remesuré à la main trois fois, et trois fois un test est tombé parce
que j'avais oublié. Un geste qu'on répète et qu'on oublie doit devenir un
programme.

    python pipeline/mesurer_arbitrages.py --ecrire

⚠️ CE PROGRAMME NE TRANCHE RIEN. Il chiffre ce que chaque option coûte ; la
décision revient au propriétaire. Les options et les avis sont écrits dans le
dossier et ne sont PAS régénérés — seuls les chiffres le sont.
"""

from __future__ import annotations

import argparse
import csv
import io
import json
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
DOSSIER = RACINE / "datasets" / "historiques_candidats" / "ARBITRAGES" / "mesures.json"


def _f(x):
    x = (x or "").strip()
    return None if x in ("", "-", "--") else float(x)


def moyennes_courtes() -> list:
    """Les titres dont la MA200 est calculée sur moins de 200 séances."""
    cache = json.loads((RACINE / "pipeline" / "historical_data.json")
                       .read_text(encoding="utf-8"))
    srv = {t["symbol"]: t for t in json.loads(
        (RACINE / "data.json").read_text(encoding="utf-8"))["tickers"]}
    out = []
    for t, v in sorted(cache.items()):
        if t.startswith("_"):
            continue
        if (v.get("n_candles") or 0) < 200 and v.get("ma200") is not None:
            p = srv.get(t, {}).get("price")
            out.append({"ticker": t, "bougies": v["n_candles"],
                        "ma200_affichee": v["ma200"], "cours": p,
                        "ecart_pct": round((v["ma200"] / p - 1) * 100, 1) if p else None})
    return out


def unites_de_volume() -> dict:
    """La convention du champ `v`, titre par titre, mesurée séance par séance."""
    out = {}
    for d in sorted((RACINE / "sources").iterdir()):
        if not d.is_dir():
            continue
        csvs = sorted(d.glob("*.csv"))
        cj = RACINE / "pipeline" / "candles" / f"{d.name}.json"
        if not csvs or not cj.exists():
            continue
        ops = {}
        for r in csv.DictReader(io.StringIO(csvs[-1].read_text(encoding="utf-8-sig")),
                                delimiter=";"):
            try:
                j, m, a = r["Séance"].split("/")
            except (ValueError, KeyError):
                continue
            ops[f"{a}-{m}-{j}"] = r
        nous = {b["d"]: b for b in json.loads(cj.read_text(encoding="utf-8"))}
        e = mad = ni = nul = 0
        for dte in set(nous) & set(ops):
            v, r = nous[dte].get("v"), ops[dte]
            ti, mo = _f(r["Titres Échangés"]), _f(r["Volume (MAD)"])
            if not v:
                nul += 1
            elif ti is not None and abs(v - ti) <= 1:
                e += 1
            elif mo and abs(v / mo - 1) < 0.02:
                mad += 1
            else:
                ni += 1
        n = max(e + mad + ni, 1)
        out[d.name] = {"seances_comparees": e + mad + ni, "nombre_de_titres": e,
                       "montant_mad": mad, "ni_l_un_ni_l_autre": ni, "v_nul": nul,
                       "convention": "TITRES" if e > n * 0.7 else
                                     ("MONTANT MAD" if mad > n * 0.7 else "MÉLANGÉE")}
    return out


def mesurer() -> dict:
    doc = json.loads(DOSSIER.read_text(encoding="utf-8"))
    courts = moyennes_courtes()
    a = doc["arbitrage_1_la_moyenne_200_jours"]
    avant = len(a.get("titres_concernes", []))
    a["titres_concernes"] = courts
    a["_les_pires_ecarts"] = sorted(
        [c for c in courts if c["ecart_pct"] and abs(c["ecart_pct"]) > 20],
        key=lambda c: -abs(c["ecart_pct"]))
    a["_resolu"] = len(courts) == 0
    if courts:
        a["_le_fait"] = (
            f"{len(courts)} titres affichent une « MA200 » calculée sur moins de "
            f"200 séances. Depuis le 15/09/2026, `calc_ma` rend une absence sous la "
            f"période : ils passeront à « — » au fil des recalculs de cache.")
    else:
        a["_le_fait"] = (
            "0 titre n'affiche désormais de « MA200 » calculée sur moins de "
            "200 séances. Le défaut mesuré le 15/09/2026 est résolu dans le "
            "cache courant ; l'historique du dossier reste conservé.")
    a["_le_compte_a_bouge"] = (
        f"⚠️ Ils étaient 32 à la première mesure, {avant} avant ce relevé, "
        f"{len(courts)} maintenant. Le compte DESCEND à mesure que les séries "
        f"sont corrigées : recalculer le cache d'un titre retire sa fausse "
        f"MA200 au passage. Ce dossier est une PHOTO — il se remesure avec "
        f"`python pipeline/mesurer_arbitrages.py --ecrire`, et un test exige "
        f"qu'il concorde avec le dépôt.")
    b = doc["arbitrage_2_l_unite_du_champ_volume"]
    unites = unites_de_volume()
    b["par_titre"] = unites
    b["_ce_qui_n_est_PAS_etabli"] = (
        f"⚠️ L'unité des {80 - len(unites)} titres dont nous n'avons pas "
        f"l'export. Rien ne permet de supposer une convention par défaut : "
        f"trois des quinze premiers mesurés n'en suivaient aucune.")
    return doc


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--ecrire", action="store_true")
    a = ap.parse_args()
    doc = mesurer()
    if a.ecrire:
        DOSSIER.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n",
                           encoding="utf-8")
    from collections import Counter
    print(json.dumps({
        "moyennes_courtes": len(doc["arbitrage_1_la_moyenne_200_jours"]["titres_concernes"]),
        "pires_ecarts": [(c["ticker"], c["ecart_pct"]) for c in
                         doc["arbitrage_1_la_moyenne_200_jours"]["_les_pires_ecarts"]],
        "conventions": dict(Counter(
            v["convention"] for v in
            doc["arbitrage_2_l_unite_du_champ_volume"]["par_titre"].values())),
        "_ecrit": bool(a.ecrire),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
