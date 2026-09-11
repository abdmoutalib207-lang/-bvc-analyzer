#!/usr/bin/env python3
"""Calculer UN indicateur sur UNE fenêtre identifiée, avec sa qualité visible.

CE QUE CE SCRIPT DÉMONTRE
─────────────────────────
    « Un premier indicateur correctement calculé, sur une fenêtre identifiée,
      avec une qualité visible et un usage clairement défini. »  — revue externe

Il enchaîne les trois couches sans en sauter aucune :

    datasets/lot1b   la couche normalisée, qui dit ce que vaut chaque ligne
    fenetre.py       qui décide si la fenêtre permet CET indicateur
    indicateurs.py   qui calcule, et ne comble rien

Le résultat porte TOUJOURS son verdict et sa réserve. Un fichier de sortie sans
ces deux champs serait inutilisable — on ne saurait pas s'il a le droit d'être
lu comme un signal.

USAGE
    python pipeline/calculer_indicateur.py --titre ADH --indicateur sma \\
        --periode 20 --depuis 2026-06-01
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))
sys.path.insert(0, str(RACINE / "pipeline"))
from fenetre import BESOINS, Champ, Verdict, qualifier_fenetre  # noqa: E402
from indicateurs import atr, bollinger, ema, macd, obv, rsi_wilder, sma  # noqa: E402

LOT1B = RACINE / "datasets" / "lot1b"


def calculer(nom: str, obs: list, periode: int, macd_params=(12, 26, 9)):
    """Applique l'indicateur demandé aux champs qu'il déclare utiliser.

    ⚠️ Le MACD ne prend PAS `periode` : il en a trois. Une version antérieure
    inscrivait `periode` dans la sortie tout en appelant `macd(c)` avec ses
    valeurs par défaut — le fichier annonçait donc un paramètre qui n'avait
    servi à rien. Les trois périodes sont maintenant passées et publiées.
    """
    c = [o.get(Champ.CLOTURE.value) for o in obs]
    if nom == "sma":
        return {"valeurs": sma(c, periode)}
    if nom == "ema":
        return {"valeurs": ema(c, periode)}
    if nom == "rsi_wilder":
        return {"valeurs": rsi_wilder(c, periode)}
    if nom == "bollinger":
        return bollinger(c, periode)
    if nom == "macd":
        court, long, signal = macd_params
        return macd(c, court, long, signal)
    if nom == "atr":
        return {"valeurs": atr([o.get(Champ.PLUS_HAUT.value) for o in obs],
                               [o.get(Champ.PLUS_BAS.value) for o in obs],
                               c, periode)}
    if nom == "obv":
        return {"valeurs": obv(c, [o.get(Champ.VOLUME.value) for o in obs])}
    raise ValueError(f"indicateur « {nom} » non branché ici")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--titre", required=True)
    ap.add_argument("--indicateur", required=True, choices=sorted(BESOINS))
    ap.add_argument("--periode", type=int, default=20)
    ap.add_argument("--macd", default="12,26,9",
                    help="périodes du MACD : court,long,signal")
    ap.add_argument("--depuis", default="")
    ap.add_argument("--jusqu-a", default="")
    ap.add_argument("--sortie", type=Path, default=RACINE / "datasets" / "lot2")
    a = ap.parse_args()

    serie = json.loads((LOT1B / f"{a.titre}.json").read_text(encoding="utf-8"))
    obs = [o for o in serie["observations"]
           if (not a.depuis or o["date"] >= a.depuis)
           and (not a.jusqu_a or o["date"] <= a.jusqu_a)]

    macd_params = tuple(int(x) for x in a.macd.split(","))
    if a.indicateur == "macd":
        # La longueur requise d'un MACD est celle de sa plus longue moyenne,
        # augmentée de la période du signal.
        periode_effective = macd_params[1] + macd_params[2]
    else:
        periode_effective = a.periode
    q = qualifier_fenetre(serie["observations"], a.indicateur,
                          a.depuis, a.jusqu_a, longueur_requise=len(obs),
                          periode=periode_effective, ticker=a.titre)

    resultat = {
        "_quoi": f"{a.indicateur} sur {a.titre}, fenêtre identifiée.",
        "_avertissement": None,
        "titre": a.titre,
        "indicateur": a.indicateur,
        "periode": a.periode,
        "periode_effective_pour_la_qualification": periode_effective,
        "macd_periodes": list(macd_params) if a.indicateur == "macd" else None,
        "genere_le": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "source": f"datasets/lot1b/{a.titre}.json",
        "empreinte_source_lot1a": serie["empreinte_source"],
        "diagnostic_base_prix": serie["diagnostic_base_prix"]["niveau"],
        "diagnostic_quantites": serie["diagnostic_quantites"]["niveau"],
        "qualification_fenetre": q,
        "usage_autorise": None,
        "valeurs": None,
    }

    if q["verdict"] == Verdict.REFUSE.value:
        resultat["_avertissement"] = (
            "CALCUL NON EFFECTUÉ. La fenêtre ne permet pas cet indicateur.")
        resultat["usage_autorise"] = "aucun"
    else:
        calc = calculer(a.indicateur, obs, a.periode, macd_params)
        resultat["valeurs"] = {
            k: [{"date": o["date"], "valeur": v} for o, v in zip(obs, serie_v)]
            for k, serie_v in calc.items() if isinstance(serie_v, list)
        }
        resultat["points_calcules"] = {
            k: sum(1 for p in v if p["valeur"] is not None)
            for k, v in resultat["valeurs"].items()
        }
        if q["verdict"] == Verdict.QUALIFIE.value:
            resultat["usage_autorise"] = (
                "publiable dans le périmètre documenté de la fenêtre")
            resultat["_avertissement"] = None
        else:
            resultat["usage_autorise"] = "EXPLORATOIRE UNIQUEMENT"
            resultat["_avertissement"] = (
                "⚠️ RÉSULTAT EXPLORATOIRE. Il n'alimente NI le signal "
                "officiel, NI une probabilité, NI une performance présentée "
                "comme validée. " + (q.get("reserve") or ""))

    a.sortie.mkdir(parents=True, exist_ok=True)
    cible = a.sortie / f"{a.titre}_{a.indicateur}_{a.periode}.json"
    cible.write_text(json.dumps(resultat, ensure_ascii=False, indent=1),
                     encoding="utf-8")

    print(f"{a.titre} · {a.indicateur}({a.periode})")
    print(f"  fenêtre   {q['debut']} → {q['fin']}  ({q['lignes']} lignes)")
    print(f"  besoins   {', '.join(q['besoins'])}")
    print(f"  verdict   {q['verdict']}")
    print(f"  usage     {resultat['usage_autorise']}")
    if resultat.get("points_calcules"):
        print(f"  calculés  {resultat['points_calcules']}")
    for m in q["motifs"]:
        print(f"  ⚠️ {m}")
    print(f"→ {cible.relative_to(RACINE)}")


if __name__ == "__main__":
    main()
