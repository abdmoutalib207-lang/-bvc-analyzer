"""Chaque séance réelle de l'année écoulée a sa clôture du MASI.

⚠️ 14/10/2026 : les sept séances du 07 au 15/09/2026 manquaient à
`masi_history.json` alors que nos chandelles les portaient. Le bêta publié
(#246) reposait sur 241 séances communes au lieu de 248, et le trou ne se
voyait nulle part. Rattrapé depuis les data.json publiés, chaîne recoupée aux
deux bouts. Ce test relit les DONNÉES : une séance réelle sans clôture de
l'indice, hors retrait documenté (`_retraits`), est un trou.
"""
import json
import sys
from datetime import date, timedelta
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

from pipeline.risque import calendrier_seances  # noqa: E402


def test_aucune_seance_reelle_sans_cloture_de_l_indice():
    series = {}
    for f in (RACINE / "pipeline" / "candles").glob("*.json"):
        d = json.loads(f.read_text(encoding="utf-8"))
        series[f.stem] = d if isinstance(d, list) else (d.get("candles") or d.get("data") or [])
    h = json.loads((RACINE / "pipeline" / "masi_history.json").read_text(encoding="utf-8"))
    connues = set(h["seances"]) | {r["date"] for r in h.get("_retraits", [])}
    seances = calendrier_seances(series)
    assert seances, "aucune séance réelle déduite des chandelles"
    # Fenêtre d'un an close à l'avant-dernière séance : la séance du jour
    # peut légitimement attendre le run qui fixe l'indice.
    debut = (date.fromisoformat(seances[-1]) - timedelta(days=365)).isoformat()
    manquantes = [d for d in seances[:-1] if d >= debut and d not in connues]
    assert not manquantes, f"séances sans clôture du MASI : {manquantes}"
