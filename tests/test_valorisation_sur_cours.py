"""Les ratios de valorisation suivent le cours — 02/10/2026.

Demande d'Abd Moutalib : PER et rendement « calculés sur le cours actuel,
et reflétant chaque changement du cours ». Aucun ne retombe plus sur une
valeur figée de FOND_DATA ; sans donnée de comptes, le ratio est absent.
"""

import json
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
SRC = (RACINE / "update_data.py").read_text(encoding="utf-8")


def test_aucun_ratio_de_valorisation_ne_lit_la_table_figee():
    assert 'else fd.get("div"))' not in SRC
    assert 'fd.get("pe"))' not in SRC


def test_rendement_et_per_publies_sont_ceux_du_cours():
    """Sur le fichier publié : rendement = dividende ÷ cours, PER = cours ÷ BPA.
    Attendus recalculés ici, à la main, depuis les deux termes publiés."""
    d = json.loads((RACINE / "data.json").read_text(encoding="utf-8"))
    for t in d["tickers"]:
        p = t.get("price")
        if t.get("div") is not None and t.get("div_dh") is not None and p:
            assert abs(t["div"] - round(t["div_dh"] / p * 100, 2)) <= 0.01, t["symbol"]
        b = t.get("bpa_12m") if t.get("bpa_12m") is not None else t.get("bpa")
        if t.get("pe") is not None and b and b > 0 and p:
            assert abs(t["pe"] - round(p / b, 1)) <= 0.1, t["symbol"]
