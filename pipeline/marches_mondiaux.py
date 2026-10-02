#!/usr/bin/env python3
"""Marchés mondiaux — indices, risque et devises, matières premières (02/10/2026).

Demande d'Abd Moutalib : une rubrique du menu avec les éléments de sa capture
(S&P 500, Dow Jones, CAC 40, Nikkei 225 ; USD/MAD, EUR/MAD, VIX, indice
dollar ; or, Brent, cuivre, charbon API2).

Source : le scanner public de TradingView (`/global/scan`), vérifié le 02/10
sur les douze symboles. Même règle que les matières du briefing
(`seance_marche.matieres`, réutilisée) : le nom affiché est celui que la
source sert, chaque valeur porte son HORODATAGE et son mode de diffusion
(« delayed_streaming_600 » = différé de 10 minutes, déclaré par la source).
Une ligne sans date est écartée ; une source muette laisse le fichier
précédent en place.

    python pipeline/marches_mondiaux.py
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

from pipeline.seance_marche import COLONNES_TV, _post, matieres  # noqa: E402

CHEMIN = RACINE / "marches_mondiaux.json"
TV_GLOBAL = "https://scanner.tradingview.com/global/scan"

GROUPES = (
    ("Indices actions", (("SP:SPX", "S&P 500"), ("DJ:DJI", "Dow Jones"),
                         ("EURONEXT:PX1", "CAC 40"), ("TVC:NI225", "Nikkei 225"))),
    ("Risque et devises", (("FX_IDC:USDMAD", "USD/MAD"), ("FX_IDC:EURMAD", "EUR/MAD"),
                           ("CBOE:VIX", "VIX"), ("TVC:DXY", "Indice dollar"))),
    ("Matières premières", (("COMEX:GC1!", "Or"), ("ICEEUR:BRN1!", "Brent"),
                            ("COMEX:HG1!", "Cuivre"), ("ICEEUR:ATW1!", "Charbon (API2)"))),
)


def assembler(reponse, releve_utc: str) -> dict:
    """Le fichier publié, depuis la réponse du scanner. Fonction pure."""
    groupes = []
    for titre, attendus in GROUPES:
        lignes = matieres(reponse, attendus)
        for x in lignes:
            x["source"] = "TradingView — scanner public"
        groupes.append({"titre": titre, "lignes": lignes})
    return {"releve_utc": releve_utc, "groupes": groupes,
            "_note": "Valeurs de la source, chacune avec son horodatage et son mode "
                     "de diffusion déclaré. Information de contexte : n'entre pas dans la note."}


def mettre_a_jour(chemin=None) -> dict:
    chemin = Path(chemin) if chemin else CHEMIN
    tickers = [t for _, att in GROUPES for t, _ in att]
    rep = _post(TV_GLOBAL, {"symbols": {"tickers": tickers, "query": {"types": []}},
                            "columns": list(COLONNES_TV)}, {})
    out = assembler(rep, datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"))
    if sum(len(g["lignes"]) for g in out["groupes"]) == 0:
        return out                      # source muette : on ne remplace rien
    chemin.write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return out


if __name__ == "__main__":
    o = mettre_a_jour()
    print({g["titre"]: len(g["lignes"]) for g in o["groupes"]})
