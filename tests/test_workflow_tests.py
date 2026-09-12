#!/usr/bin/env python3
"""Le workflow de tests juge-t-il le fichier qu'il prétend juger ?

⚠️ POURQUOI CE FICHIER EXISTE
─────────────────────────────
`tests.yml` générait `data.json` avec le moteur de la demande de fusion, puis
**le restaurait à l'état du dépôt** avant de lancer la suite. La suite jugeait
donc le fichier de l'ANCIEN moteur — CMT à −3,35 % — pendant que l'artefact
joint portait le fichier corrigé, à 0,00 %.

Le vert annoncé et la pièce livrée ne décrivaient pas le même objet.

J'avais annoncé le retrait de cette ligne sans le vérifier : ma substitution
n'avait pas trouvé son motif et je n'ai pas relu le résultat. La revue externe
a exécuté le workflow et l'a trouvée. Un contrôle qui repose sur ma relecture
n'en est pas un — celui-ci relit le fichier à chaque suite.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
# ⚠️ IMPORT FERME, PAS `importorskip`. Un contrôle qui s'abstient là où il
# compte ne contrôle rien : c'est en CI que ce test doit parler. La dépendance
# est donc DÉCLARÉE dans requirements_dev.txt (règle R4), et son absence est
# une erreur, pas un silence.
import yaml

RACINE = Path(__file__).resolve().parent.parent
CHEMIN = RACINE / ".github" / "workflows" / "tests.yml"


@pytest.fixture(scope="module")
def etapes() -> list:
    w = yaml.safe_load(CHEMIN.read_text(encoding="utf-8"))
    return w["jobs"]["pytest"]["steps"]


def _index(etapes, fragment: str) -> int:
    for i, e in enumerate(etapes):
        if fragment.lower() in (e.get("name") or "").lower():
            return i
    raise AssertionError(f"étape « {fragment} » absente de tests.yml")


def test_rien_ne_restaure_les_donnees_avant_le_controle(etapes):
    """⚠️ LE DÉFAUT EXACT, FIGÉ EN TEST.

    Entre la génération et la suite, aucune étape ne doit remettre un fichier
    de données à l'état du dépôt : cela ferait juger l'ancien moteur.
    """
    debut, fin = _index(etapes, "Générer"), _index(etapes, "Lancer la suite")
    fautifs = []
    for e in etapes[debut:fin + 1]:
        script = e.get("run") or ""
        for m in re.finditer(r"^\s*git\s+(checkout|restore|stash|reset|clean)\b.*$",
                             script, re.M):
            fautifs.append(f"{e.get('name')} : {m.group(0).strip()[:90]}")
    assert fautifs == [], (
        "une étape restaure les données entre la génération et le contrôle — "
        f"la suite jugerait le fichier de l'ancien moteur : {fautifs}")


def test_les_chandelles_partent_avec_le_json(etapes):
    """Les deux vont ensemble : un `data.json` sans ses chandelles ne se
    rejoue pas fidèlement."""
    gen = etapes[_index(etapes, "Générer")].get("run") or ""
    assert "candles" in gen, "les chandelles générées ne sont pas conservées"


def test_le_fichier_juge_et_le_fichier_joint_sont_compares(etapes):
    """⚠️ Le contrôle que la revue a réclamé : même empreinte, ou échec.

    Sans lui, rien n'empêche qu'une étape future réintroduise la divergence.
    """
    i = _index(etapes, "Vérifier que le fichier jugé est le fichier joint")
    assert i > _index(etapes, "Lancer la suite"), \
        "le contrôle d'empreinte doit venir APRÈS la suite"
    script = etapes[i].get("run") or ""
    assert "sha256" in script
    assert "data.json" in script and "data_teste.json" in script
    assert "sys.exit" in script, "une divergence doit FAIRE ÉCHOUER le job"
    assert etapes[i].get("if") == "always()", \
        "le contrôle doit tourner même si la suite a échoué"


def test_la_generation_precede_le_controle(etapes):
    assert _index(etapes, "Générer") < _index(etapes, "Lancer la suite")
    assert _index(etapes, "Identifier") < _index(etapes, "Lancer la suite")


def test_le_fichier_juge_et_le_fichier_joint_sont_les_memes_chemins(etapes):
    """La suite lit `data.json` à sa place habituelle ; l'artefact part de
    `.ci/data_teste.json`. Le contrôle d'empreinte ne vaut que si ce sont bien
    ces deux-là qui sont comparés."""
    suite = etapes[_index(etapes, "Lancer la suite")]
    assert "BVC_DATA_JSON" not in (suite.get("env") or {}), (
        "la suite ne doit pas être détournée vers un autre fichier en CI : "
        "elle juge celui que la génération vient d'écrire")


def test_aucun_echec_n_est_declare_attendu(etapes):
    """⚠️ Un rouge ne se contourne pas : il s'explique. Ni `continue-on-error`
    sur la suite, ni `|| true` qui avalerait le code de retour."""
    suite = etapes[_index(etapes, "Lancer la suite")]
    assert not suite.get("continue-on-error"), \
        "la suite ne doit jamais être non bloquante"
    assert "|| true" not in (suite.get("run") or "")
    assert "--exitfirst" not in (suite.get("run") or "")
