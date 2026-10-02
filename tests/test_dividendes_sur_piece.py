"""Chaque dividende publié a sa pièce — 02/10/2026.

L'agent verificateur-finance a établi sur pièce (avis d'AG, communiqués
post-AG, rapports annuels déposés à l'AMMC) le dividende par action des 80
titres. Deux étaient faux : TMA (156,57 = 89,57 de 2026 + 67 d'un
exceptionnel versé en décembre 2025) et ADH (0,50 = le dividende versé en
2025 ; l'AGO 2026 n'a rien distribué).
"""

import json
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
BPA = json.loads((RACINE / "bpa.json").read_text(encoding="utf-8"))
TICKERS = {t["symbol"] for t in json.loads((RACINE / "data.json").read_text(encoding="utf-8"))["tickers"]}


def test_aucun_dividende_publie_sans_piece():
    sans = [s for s in TICKERS if (BPA.get(s) or {}).get("div_dh") is not None
            and "dividende_piece" not in BPA[s]]
    assert not sans, sans


def test_les_deux_erreurs_sont_corrigees():
    # TMA : 802 547 200 MAD ÷ 8 960 000 actions = 89,57 (avis rectificatif AGO 04/06/2026, p.3)
    assert BPA["TMA"]["div_dh"] == 89.57 and BPA["TMA"]["div_dh_avant_2026_10_02"] == 156.57
    assert BPA["ADH"]["div_dh"] == 0.0


def test_une_absence_de_dividende_etablie_vaut_zero():
    for s in ("ZLD", "STR", "FNB", "INV", "REB", "STK", "UNI", "MDP", "CAR"):
        assert BPA[s]["div_dh"] == 0.0, s
