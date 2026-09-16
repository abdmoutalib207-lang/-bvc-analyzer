#!/usr/bin/env python3
"""Aucune étape d'`update_bvc` ne s'exécute sans dépôt.

⚠️ LE DÉFAUT, ET SA SIGNATURE
─────────────────────────────
La porte « Vérifier session BVC » décide s'il y a du travail. Quand elle dit
non, le `checkout` est sauté — et deux étapes s'exécutaient quand même, sur un
runner vide :

    Suite de tests   ERROR: Could not open requirements file: requirements_dev.txt
    Contrôle séance  python: can't open file '.../pipeline/verifier_seance.py'

La seconde n'est pas `continue-on-error`, et elle transforme un code non nul en
`exit 1` dès 17h00 UTC. Le run passait donc au rouge.

Mesuré le 15/09/2026 sur les 100 derniers runs : **18 échecs** de cette nature,
tous entre 17h et 23h UTC — la fenêtre exacte de cette condition, sans une
seule exception. Ils voisinaient 11 échecs réels dans la même liste, sans rien
pour les distinguer.

⚠️ Ce qui est en cause n'est pas la sévérité du contrôle : c'est qu'il se
prononçait sur un dépôt absent. Une alarme qui se déclenche sans motif finit
ignorée puis désactivée — la leçon du drapeau `stale` du 14/08.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
# ⚠️ IMPORT FERME, pas `importorskip` : c'est en CI que ce test doit parler.
import yaml

RACINE = Path(__file__).resolve().parent.parent
CHEMIN = RACINE / ".github" / "workflows" / "update_bvc.yml"

# La porte, et elle seule, a le droit de tourner sans dépôt : c'est elle qui
# décide s'il y en aura un.
# Les étapes qui précèdent la décision, et qui n'ont donc pas à la citer.
#
# ⚠️ « checkout » y est entré le 16/09. La porte lit désormais `data.json` et
# importe `pipeline/porte_rattrapage.py` : elle ne peut plus se prononcer sur un
# runner vide. Le dépôt passe donc devant, et sans condition.
#
# Ce n'est pas un affaiblissement de la règle des 18 rouges du 15/09 — « aucune
# étape ne se prononce sur un dépôt absent » — c'est son extension : la porte
# elle-même en bénéficie. Ce qui reste protégé, et que les tests ci-dessous
# exigent toujours, c'est que TOUT LE TRAVAIL reste conditionné à la porte.
PORTE = "vérifier session bvc"
AVANT_LA_PORTE = {PORTE, "checkout"}


@pytest.fixture(scope="module")
def etapes() -> list:
    w = yaml.safe_load(CHEMIN.read_text(encoding="utf-8"))
    return w["jobs"]["update-bvc-data"]["steps"]


def _nom(e) -> str:
    return (e.get("name") or "").strip().lower()


def _sans_commentaires(script: str) -> str:
    """Le script shell, commentaires ôtés — on éprouve ce qui S'EXÉCUTE.

    ⚠️ Ce projet est tombé quatre fois dans le même piège : une recherche
    textuelle trouve le mot dans le COMMENTAIRE qui explique qu'on l'a retiré.
    Le commentaire de l'étape bloquante cite littéralement
    `tests/test_workflow_tests.py` — sans ce filtrage, le test ci-dessous
    rougissait sur sa propre documentation.
    """
    return "\n".join(re.sub(r"(?<!\S)#.*$", "", l) for l in script.splitlines())


def test_la_porte_existe_et_porte_l_identifiant_attendu(etapes):
    """Les conditions des autres étapes citent `steps.gate` : si l'`id` change
    sans qu'elles suivent, elles deviennent toutes vraies en silence."""
    porte = [e for e in etapes if _nom(e) == PORTE]
    assert len(porte) == 1, "la porte de session doit exister, une seule fois"
    assert porte[0].get("id") == "gate"


def test_le_depot_est_pose_avant_toute_decision(etapes):
    """Le dépôt arrive en premier, sans condition.

    ⚠️ CE TEST EXIGEAIT L'INVERSE JUSQU'AU 16/09 : le checkout était conditionné
    à la porte. Ce qui a changé, c'est la porte elle-même. Elle ne se contente
    plus de regarder l'heure : elle lit `data.json` pour savoir QUELLE SÉANCE le
    fichier porte, et appelle `pipeline/porte_rattrapage.py`. Une porte qui lit
    le dépôt ne peut pas décider s'il faut le télécharger.

    Le renversement RENFORCE la règle des 18 rouges du 15/09 au lieu de la
    défaire : plus aucune étape, porte comprise, ne se prononce sur un dépôt
    absent. Le coût est de deux secondes par passage horaire.
    """
    noms = [_nom(e) or (e.get("uses") or "").split("@")[0] for e in etapes]
    checkout = [e for e in etapes if _nom(e) == "checkout"]
    assert len(checkout) == 1, "le checkout doit exister, une seule fois"
    assert noms[0] == "checkout", (
        f"le dépôt n'est pas posé en premier : {noms[:3]}")
    assert not checkout[0].get("if"), (
        "le checkout est conditionné : la porte retrouverait un dépôt absent, "
        "et elle en a besoin pour lire data.json")


def test_aucune_etape_ne_tourne_sans_depot(etapes):
    """⚠️ LE DÉFAUT EXACT, FIGÉ EN TEST.

    Toute étape postérieure à la porte lit le dépôt — un script, un fichier de
    dépendances, `data.json`. Aucune ne doit pouvoir s'exécuter quand la porte
    a dit non, `always()` compris : `always()` répond « même en cas d'échec »,
    pas « même sans dépôt ».
    """
    fautives = [
        _nom(e) for e in etapes
        if _nom(e) not in AVANT_LA_PORTE
        and "steps.gate.outputs.run" not in str(e.get("if", ""))
    ]
    assert not fautives, (
        "ces étapes travailleraient alors que la porte a dit non : "
        + ", ".join(fautives))
    # Et la porte doit rester la seule à décider : si le travail cessait d'être
    # conditionné, le cron horaire ferait 24 runs et 24 commits par jour.
    travail = [_nom(e) for e in etapes if _nom(e) not in AVANT_LA_PORTE]
    assert len(travail) >= 6, (
        f"seulement {len(travail)} étapes de travail — le workflow a-t-il été "
        "vidé ?")


def test_le_controle_de_seance_reste_bloquant_le_soir(etapes):
    """⚠️ Contre-épreuve : on corrige QUAND il s'exécute, pas SI il échoue.

    Retirer la sévérité du soir aurait fait disparaître les 18 rouges tout
    aussi bien — et aurait supprimé l'alarme au lieu du bruit.
    """
    ctrl = [e for e in etapes if _nom(e) == "contrôle de la séance"]
    assert len(ctrl) == 1
    script = _sans_commentaires(ctrl[0]["run"])
    assert 'date -u +%H' in script and '-ge 17' in script, (
        "le contrôle doit toujours échouer sur le passage du soir")
    assert "exit 1" in script
    assert ctrl[0].get("continue-on-error") is not True, (
        "le rendre non bloquant reviendrait à débrancher l'alarme")


def test_la_suite_bloquante_avant_publication_est_toujours_la(etapes):
    """⚠️ Rien de tout ceci ne doit affaiblir le garde-fou du 10/09 : la suite
    ENTIÈRE tourne sur le fichier fraîchement écrit, AVANT le commit."""
    noms = [_nom(e) for e in etapes]
    i_ctrl = noms.index("contrôles bloquants sur le fichier généré")
    i_commit = noms.index("commit data.json si modifié")
    assert i_ctrl < i_commit
    bloquants = etapes[i_ctrl]
    assert bloquants.get("continue-on-error") is not True
    script = _sans_commentaires(bloquants["run"])
    assert "pytest" in script
    # Pas de sélection de fichiers : la suite entière, comme l'a exigé la revue
    # du 10/09 — « un échec critique ne doit pas devenir acceptable simplement
    # parce qu'il appartient à un autre fichier de tests ».
    assert "tests/" not in script
