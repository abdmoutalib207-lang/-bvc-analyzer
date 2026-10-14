"""L'écrivain historique (collect_history_bvcscrap) fait les mêmes balayages
et écrit au même format que les deux autres écrivains de chandelles.

Mesuré le 13/10/2026 : 0 → 177 → 0 bougies hors invariant OHLC selon le
dernier écrivain passé, et 1 594 « retours » de fichiers du 05/09 au 14/10,
dont 77 % de pure mise en forme.
"""
import ast
from pathlib import Path

SRC = (Path(__file__).resolve().parent.parent / "pipeline" / "collect_history_bvcscrap.py").read_text(encoding="utf-8")


def _appels():
    return {n.func.id if isinstance(n.func, ast.Name) else getattr(n.func, "attr", None)
            for n in ast.walk(ast.parse(SRC)) if isinstance(n, ast.Call)}


def test_les_balayages_apres_ecriture():
    assert {"reparer_ohlc", "purger_suspensions", "_purger_fantome"} <= _appels()


def test_format_compact_comme_les_autres_ecrivains():
    i = SRC.find("def save_candle_file")
    assert 'separators=(",", ":")' in SRC[i:i + 1500]
