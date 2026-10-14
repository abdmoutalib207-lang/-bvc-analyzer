"""Le collecteur IA des rapports annuels ne se déclenche plus seul (14/10/2026).

Il associe MRL, MSA et VCNE à d'autres sociétés et écrit sans contrôle dans
fondamentaux.json. Tant qu'il n'est pas corrigé, aucun `schedule`.
"""
from pathlib import Path

import yaml

WF = Path(__file__).resolve().parent.parent / ".github" / "workflows" / "update_fondamentaux.yml"


def test_aucun_declenchement_programme():
    d = yaml.safe_load(WF.read_text(encoding="utf-8"))
    declencheurs = d.get("on", d.get(True))
    assert "schedule" not in declencheurs
    assert "workflow_dispatch" in declencheurs
