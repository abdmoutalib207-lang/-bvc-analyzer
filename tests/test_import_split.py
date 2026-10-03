"""L'export de l'opérateur publie des cours BRUTS : l'import doit appliquer
le registre SPLITS, comme tout téléchargement frais (R11).

⚠️ Mesuré le 03/10/2026 : l'export MNG donne 12 500 le 24/07/2026 et 1 364
le 27/07, jour du split 1:10. Sans ajustement, la série chutait de 89 %."""
import json
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE / "pipeline"))


def test_l_import_ajuste_les_cours_bruts_d_avant_le_split():
    import importer_export_bvc as imp
    assert "officielles = adjust_splits(ticker, officielles)" in \
        (RACINE / "pipeline" / "importer_export_bvc.py").read_text(encoding="utf-8")
    assert imp.adjust_splits is not None


def test_mng_n_a_plus_de_marche_au_split():
    b = {x["d"]: x for x in json.loads(
        (RACINE / "pipeline" / "candles" / "MNG.json").read_text(encoding="utf-8"))}
    # 12 500 brut dans l'export ÷ 10, écrit en dur — pas recalculé par adjust_splits.
    assert b["2026-07-24"]["c"] == 1250.0
    assert b["2026-07-27"]["c"] == 1364.0
