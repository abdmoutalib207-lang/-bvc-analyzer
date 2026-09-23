#!/usr/bin/env python3
"""La suite doit se déclencher sur ce qu'elle surveille.

⚠️ CE QUE CE FICHIER EMPÊCHE DE REVENIR
───────────────────────────────────────
Constaté le 23/09/2026 : le déclencheur `pull_request` de `tests.yml` ne
listait que `**.py` et `tests/**`. Une pull request qui ne contient QUE des
données — des chandelles réécrites, un document de réception — ne lançait donc
**aucun test**.

C'est le cas où ils servent le plus. La moitié de la suite relit les DONNÉES
PUBLIÉES, et `test_hors_series_corrigees…` n'existe que pour refuser une
livraison qui touche trop de séries d'un coup. **Il ne se déclenchait pas sur
une livraison de séries.**

Mesuré sur la PR du lot 3/3 : neuf séries réécrites, aucun `.py` touché, aucun
pytest lancé. La livraison était saine — vérifiée en local — mais rien dans la
chaîne ne l'établissait, et c'est ce « rien » qui est le défaut. Un garde-fou
qui ne s'arme pas vaut son absence, à la fausse tranquillité près.

⚠️ Le contrôle porte sur les chemins que des TESTS EXISTANTS lisent. Il n'est
pas une liste de souhaits : chaque entrée ci-dessous correspond à un fichier
qu'au moins un test ouvre pour juger une livraison.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

WORKFLOW = RACINE / ".github" / "workflows" / "tests.yml"

# Chemins qu'une livraison peut ne contenir QUE, et que la suite juge.
SURVEILLES = [
    "data.json",                      # le flux publié — plusieurs tests le relisent
    "pipeline/candles/**",            # les séries — garde-fou d'opération de masse
    "pipeline/historical_data.json",  # le cache d'indicateurs
    "datasets/**",                    # réceptions, corrections, séances retirées
]


@pytest.fixture(scope="module")
def declencheur_pull_request() -> list[str]:
    """Les `paths` du déclencheur `pull_request`, lus dans le YAML.

    ⚠️ Lu avec PyYAML plutôt qu'à la ligne : un `paths` indenté sous
    `pull_request` et un autre sous `push` se ressemblent trait pour trait dans
    le texte, et c'est justement celui de `pull_request` qui était en cause.
    """
    yaml = pytest.importorskip("yaml")
    doc = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    # ⚠️ `on:` est lu par PyYAML comme le booléen True (YAML 1.1) — le piège
    # classique des fichiers GitHub Actions. On accepte les deux clés.
    declencheurs = doc.get("on") if "on" in doc else doc.get(True)
    assert declencheurs, "tests.yml : aucun déclencheur lisible"
    pr = declencheurs.get("pull_request")
    assert pr is not None, "tests.yml ne se déclenche plus sur les pull requests"
    return list(pr.get("paths") or [])


@pytest.mark.parametrize("chemin", SURVEILLES)
def test_une_livraison_de_donnees_declenche_la_suite(declencheur_pull_request,
                                                     chemin):
    """⚠️ Sans cela, une PR de pur data passe sans qu'aucun test ne l'ait vue."""
    assert chemin in declencheur_pull_request, (
        f"une pull request ne touchant que `{chemin}` ne lancerait aucun test")


def test_le_code_reste_surveille(declencheur_pull_request):
    """Le resserrement ne doit pas se faire au prix de ce qui marchait déjà."""
    for chemin in ("**.py", "tests/**"):
        assert chemin in declencheur_pull_request


def test_le_workflow_lui_meme_est_surveille(declencheur_pull_request):
    """⚠️ Sinon une PR qui RESTREINT ce déclencheur ne déclencherait rien — pas
    même ce test-ci. C'est le cas qui se referme sur lui-même."""
    assert ".github/workflows/tests.yml" in declencheur_pull_request
