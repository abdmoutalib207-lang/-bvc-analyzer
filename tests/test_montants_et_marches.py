"""Demandes d'Abd Moutalib du 14/10/2026 : montant échangé en entier, MASI et
argent dans les marchés mondiaux."""
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))
SRC = (RACINE / "terminal.src.html").read_text(encoding="utf-8")


def test_masi_et_argent_releves():
    from pipeline.marches_mondiaux import GROUPES
    tickers = {t for _, att in GROUPES for t, _ in att}
    assert {"CSEMA:MASI", "COMEX:SI1!"} <= tickers


def test_volume_en_montant_entier():
    assert "const montantCourt=montantEntier;" in SRC
    assert "/1e6,1)} M DH" not in SRC
    assert "volume_mad/1e9" not in SRC
