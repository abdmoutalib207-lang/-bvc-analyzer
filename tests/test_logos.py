"""Les logos : pris sur le site officiel, relus, tracés — 30/09/2026.

Chaque logo publié doit figurer au registre avec son site et une empreinte
identique au fichier ; la liste du terminal doit être exactement celle des
fichiers ; un logo refusé à la relecture ne doit pas être publié.
"""

import hashlib
import json
import re
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
REG = json.loads((RACINE / "datasets" / "logos" / "registre.json").read_text(encoding="utf-8"))
FICHIERS = sorted(f.stem for f in (RACINE / "logos").glob("*.png"))
SRC = (RACINE / "terminal.src.html").read_text(encoding="utf-8")


def test_chaque_logo_est_trace_au_registre():
    for s in FICHIERS:
        e = REG.get(s) or {}
        assert e.get("site"), f"{s} : site officiel absent du registre"
        octets = (RACINE / "logos" / f"{s}.png").read_bytes()
        assert e.get("sha256") == hashlib.sha256(octets).hexdigest(), f"{s} : fichier modifié hors outil"


def test_le_terminal_liste_exactement_les_fichiers():
    m = re.search(r"const LOGOS=new Set\(\[(.*?)\]\);", SRC)
    assert m
    assert sorted(re.findall(r'"([A-Z0-9]+)"', m.group(1))) == FICHIERS


def test_aucun_logo_refuse_n_est_publie():
    refuses = [s for s, e in REG.items() if e.get("refuse")]
    assert refuses, "la relecture n'a rien consigné"
    assert not set(refuses) & set(FICHIERS)
    # Les cas établis le 30/09 : logo d'un groupe ou d'un partenaire.
    assert {"SMI", "SRM", "DAR", "HAL", "MIC", "SAF"} <= set(refuses)


def test_le_logo_se_cherche_par_notre_symbole():
    """Le classement affiche le code officiel (TGC) ; le fichier est TGCC.png."""
    assert "logo={r.symbol}" in SRC and "LOGOS.has(cle)" in SRC
    assert "TGCC" in FICHIERS


def test_miniatures_legeres():
    for s in FICHIERS:
        assert (RACINE / "logos" / f"{s}.png").stat().st_size < 12_000, s
