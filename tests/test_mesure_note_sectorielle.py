"""La mesure ancienne note / note par famille est reproductible à l'octet près
et dit, avant ses chiffres, que la comparaison avantage la nouvelle note."""
import json
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))
sys.path.insert(0, str(RACINE / "pipeline"))

import mesure_note_sectorielle as m  # noqa: E402


def test_la_mesure_est_deterministe_et_sans_commit_git():
    a = json.dumps(m.construire(), ensure_ascii=False, indent=1, sort_keys=True)
    b = json.dumps(m.construire(), ensure_ascii=False, indent=1, sort_keys=True)
    assert a == b
    res = json.loads(a)
    assert "commit_git" not in res["entrees"], "un hash de commit ruine la reproductibilité à l'octet"
    assert set(res["entrees"]["sha256"]) >= {"score_history", "fondamentaux", "bpa"}


def test_le_docstring_tranche_le_biais_en_faveur_de_la_nouvelle_note():
    doc = m.__doc__
    assert "BIAISÉE EN FAVEUR DE LA NOUVELLE NOTE" in doc
    assert "souffrent du même biais" not in doc.replace("ne « souffrent » pas du même biais", "")
