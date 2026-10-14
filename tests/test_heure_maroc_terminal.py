"""Le terminal applique le MÊME registre d'heure légale que le moteur
(bvc_config.DECALAGES_MAROC) au lieu de la base de fuseaux du navigateur, qui
peut ignorer le passage à UTC+0 du 20/09/2026 (14/10/2026)."""
import re
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))
SRC = (RACINE / "terminal.src.html").read_text(encoding="utf-8")


def test_le_registre_du_terminal_est_celui_du_moteur():
    from bvc_config import DECALAGES_MAROC
    m = re.search(r"const DECALAGES_MAROC=\[(.*?)\];", SRC)
    assert m, "registre absent du terminal"
    js = re.findall(r'\["(\d{4}-\d{2}-\d{2})",(-?\d+)\]', m.group(1))
    assert [(d, int(o)) for d, o in js] == [(e["depuis"], e["offset"]) for e in DECALAGES_MAROC]


def test_plus_aucune_heure_demandee_au_navigateur():
    assert 'timeZone:"Africa/Casablanca"' not in SRC
