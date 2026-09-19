import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "bvc_recalculer_cache_test", ROOT / "pipeline" / "recalculer_cache.py"
)
RC = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(RC)
_fusion_candles_cache = RC._fusion_candles_cache


def test_append_preserve_la_bougie_pivot_deja_corrigee():
    cache = [
        {"d": "2026-09-15", "o": 10, "h": 11, "l": 9, "c": 10, "v": 1},
        # Correction déjà réceptionnée dans le cache : haut=12.
        {"d": "2026-09-16", "o": 10, "h": 12, "l": 9, "c": 11, "v": 2},
    ]
    calculees = [
        # Le brut garde encore l'ancienne valeur erronée haut=99.
        {"d": "2026-09-16", "o": 10, "h": 99, "l": 9, "c": 11, "v": 2},
        {"d": "2026-09-18", "o": 11, "h": 13, "l": 10, "c": 12, "v": 3},
    ]
    resultat = _fusion_candles_cache(cache, calculees, "2026-09-16", False)
    par_date = {x["d"]: x for x in resultat}
    assert par_date["2026-09-16"]["h"] == 12
    assert par_date["2026-09-18"]["c"] == 12


def test_remplacement_du_pivot_remplace_bien_la_derniere_bougie():
    cache = [{"d": "2026-09-18", "o": 10, "h": 11, "l": 9, "c": 10, "v": 1}]
    calculees = [{"d": "2026-09-18", "o": 10, "h": 12, "l": 9, "c": 11, "v": 2}]
    resultat = _fusion_candles_cache(cache, calculees, "2026-09-18", True)
    assert resultat == calculees
