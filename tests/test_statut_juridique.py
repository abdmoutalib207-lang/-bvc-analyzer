"""Statut juridique écrit en clair — décision d'Abd Moutalib du 20/10/2026.

DIS reste dans l'univers avec la mention « Liquidée », DLM avec « Liquidation
judiciaire ». Les deux restent suspendus et sans comptes : pas de signal.
"""
import os
import sys

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RACINE)
import bvc_config  # noqa: E402


def test_mentions_au_registre():
    assert bvc_config.sans_comptes("DIS")["statut_juridique"] == "Liquidée"
    assert bvc_config.sans_comptes("DLM")["statut_juridique"] == "Liquidation judiciaire"
    assert "statut_juridique" not in bvc_config.sans_comptes("IBM")


def test_toujours_suspendus_et_dans_l_univers():
    for t in ("DIS", "DLM"):
        assert t in bvc_config.SUSPENSIONS
        assert t in bvc_config.TICKERS_ALL


def test_meta_et_terminal_transportent_la_mention():
    src = open(os.path.join(RACINE, "update_data.py"), encoding="utf-8").read()
    assert '"statut_juridique": (sans_comptes(ticker) or {}).get("statut_juridique")' in src
    term = open(os.path.join(RACINE, "terminal.src.html"), encoding="utf-8").read()
    assert term.count("meta(r).statut_juridique") >= 2
