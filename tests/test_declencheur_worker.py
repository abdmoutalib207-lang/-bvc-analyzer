#!/usr/bin/env python3
"""Les tests du déclencheur tournent avec le reste, ou ils ne tournent pas.

⚠️ POURQUOI CE FICHIER EXISTE
─────────────────────────────
Le Worker est écrit en JavaScript ; ses tests aussi. Laissés de côté, ils
auraient une seule fin possible : pourrir. Personne ne lance à la main une
commande qu'aucune chaîne n'exécute, et un test qu'on ne lance pas est un
commentaire.

Ce fichier les branche sur `pytest`, donc sur la CI, donc sur chaque pull
request. Une seule commande couvre tout le dépôt — c'est la condition pour
qu'un garde-fou reste vivant.

⚠️ CE N'EST PAS UNE VÉRIFICATION DE PRÉSENCE. Le sous-processus exécute
vraiment les seize assertions du Worker ; son code de sortie fait foi.
« Vérifier qu'une ligne existe n'est pas vérifier qu'elle fonctionne. »
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parent.parent
DOSSIER = RACINE / "declencheur"
SUITE = DOSSIER / "worker.test.mjs"


def test_le_declencheur_est_present():
    """S'il disparaît, ce n'est pas au test JS de le dire — il ne tournerait
    plus. C'est ici que ça se voit."""
    assert (DOSSIER / "worker.js").exists()
    assert SUITE.exists()


@pytest.mark.skipif(shutil.which("node") is None,
                    reason="node absent de cette machine")
def test_la_suite_du_worker_passe():
    """⚠️ Le sous-processus exécute réellement les assertions du Worker.

    ⚠️ On vise le FICHIER, pas le dossier : `node --test declencheur/` charge
    aussi `worker.js`, qui ne contient aucun test, et le compte comme un échec.
    Piège rencontré le 23/09 — la première exécution rendait « 1 test, 1 fail »
    alors que les seize passaient.
    """
    r = subprocess.run(
        ["node", "--test", str(SUITE)],
        capture_output=True, text=True, cwd=RACINE, timeout=120,
    )
    assert r.returncode == 0, (
        "la suite du déclencheur échoue :\n"
        + "\n".join(l for l in r.stdout.splitlines()
                    if l.startswith("not ok") or "error:" in l)[:2000]
        or r.stdout[-2000:]
    )
    # Un « 0 test exécuté » sortirait aussi en 0 : le compte doit être vérifié.
    assert "# fail 0" in r.stdout
    passes = next((l for l in r.stdout.splitlines() if l.startswith("# pass ")), "")
    assert passes and int(passes.split()[-1]) >= 10, (
        f"trop peu de tests exécutés pour que ce soit une couverture : {passes}")
