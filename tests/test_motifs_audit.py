"""19/11/2026 — motifs corrigés après l'audit externe (Manus)."""
import logging
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))
logging.disable(logging.CRITICAL)

import update_data as ud  # noqa: E402

ECRAN = (RACINE / "terminal.src.html").read_text(encoding="utf-8")


def test_dividende_au_calendrier_mais_rendement_non_publie():
    t = [{"symbol": "ENK", "div": None, "_meta": {}}, {"symbol": "IAM", "div": 4.5, "_meta": {}}]
    reg = {"ENK": [{"detachement": "2026-07-06", "montant": 2.81}],
           "IAM": [{"detachement": "2026-06-01", "montant": 4.0}]}
    assert ud.motifs_dividende(t, reg, "2026-11-19") == 1
    assert "2,81 le 06/07/2026" in t[0]["_meta"]["div_motif"]
    assert "div_motif" not in t[1]["_meta"]                  # rendement publié : rien à dire


def test_controle_negatif_detachement_trop_ancien_ou_futur():
    t = [{"symbol": "UNI", "div": None, "_meta": {}}]
    reg = {"UNI": [{"detachement": "2024-09-09", "montant": 1.0}, {"detachement": "2026-12-21", "montant": 1.0}]}
    assert ud.motifs_dividende(t, reg, "2026-11-19") == 0


def test_libelles_ecran_et_garantie():
    assert "m.div_motif||" in ECRAN
    assert "Upside Base" not in ECRAN
    assert 'r.div===0)return "Aucun dividende' in ECRAN
    src = (RACINE / "update_data.py").read_text(encoding="utf-8")
    assert "\"Comptes déposés à l'AMMC et relevés\"" in src
