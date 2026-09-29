"""La version téléphone du terminal — 29/09/2026.

Les règles CSS masquent les colonnes du classement PAR POSITION (nth-child).
Si les colonnes sont réordonnées, le téléphone cacherait le score à la place
du volume, sans qu'aucune erreur ne se voie. Ce test lie les positions
supposées par le CSS à la liste réelle des en-têtes.
"""

from __future__ import annotations

import re
from pathlib import Path

SRC = (Path(__file__).resolve().parent.parent / "terminal.src.html").read_text(encoding="utf-8")

# Positions (1-indexées) que la règle mobile laisse visibles.
GARDEES = {2: "TICKER", 4: "CLÔT.", 5: "VAR%", 10: "scoreColLabel", 16: "SIGNAL"}


def _entetes() -> list[str]:
    m = re.search(r"const HEADS=\[(.*?)\];", SRC)
    assert m, "liste HEADS introuvable"
    return [x.strip().strip('"') for x in m.group(1).split(",")]


def test_les_colonnes_gardees_sur_telephone_sont_les_bonnes():
    h = _entetes()
    for pos, nom in GARDEES.items():
        assert h[pos - 1] == nom, f"colonne {pos} : {h[pos - 1]!r} au lieu de {nom!r}"


def test_les_regles_mobiles_existent():
    css = SRC[SRC.index("VERSION TÉLÉPHONE"):SRC.index("</style>")]
    for regle in (".entete{position:static", ".onglets{flex-wrap:nowrap",
                  ".classement{min-width:0", ".bandeau-masi{flex-wrap:wrap"):
        assert regle in css, regle
    # Les classes utilisées par le CSS sont bien posées dans le JSX.
    for classe in ("entete", "onglets", "classement", "bandeau-masi",
                   "badge-version", "choix-score", "entete-droite",
                   "nom-societe", "secteur-societe"):
        assert f'className="{classe}"' in SRC, classe
