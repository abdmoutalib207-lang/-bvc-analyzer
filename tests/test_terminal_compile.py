"""index.html est la COMPILATION de terminal.src.html — et rien d'autre.

⚠️ Depuis le 29/09/2026, le terminal est précompilé : le navigateur ne
télécharge plus Babel (2,85 Mo) et ne recompile plus 250 000 caractères à
chaque ouverture — 4,9 s → 0,8 s sur ordinateur, 14,8 s → 2,6 s sur un
téléphone moyen, mesuré sur copie locale.

Le risque nouveau est la DÉRIVE : une source modifiée sans recompiler, ou un
index.html retouché à la main. Ce test recompile et exige l'égalité octet
pour octet.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parent.parent


def _babel_disponible() -> bool:
    return (RACINE / "node_modules" / "@babel" / "standalone").is_dir() or bool(os.environ.get("NODE_PATH"))


def test_index_est_la_compilation_exacte_de_la_source():
    if not shutil.which("node") or not _babel_disponible():
        if os.environ.get("GITHUB_ACTIONS"):
            pytest.fail("la CI doit installer node et @babel/standalone")
        pytest.skip("compilateur absent en local")
    env = dict(os.environ)
    env.setdefault("NODE_PATH", str(RACINE / "node_modules"))
    sortie = subprocess.run(["node", "tools/compiler_terminal.js", "--stdout"],
                            cwd=RACINE, capture_output=True, text=True, env=env)
    assert sortie.returncode == 0, sortie.stderr
    assert sortie.stdout == (RACINE / "index.html").read_text(encoding="utf-8"), (
        "index.html ne correspond pas à terminal.src.html — lancer "
        "`node tools/compiler_terminal.js`, et ne jamais modifier index.html à la main")


def test_le_fichier_servi_ne_charge_plus_babel():
    servi = (RACINE / "index.html").read_text(encoding="utf-8")
    assert 'type="text/babel"' not in servi
    assert "@babel/standalone" not in servi
    assert "FICHIER GÉNÉRÉ" in servi
