"""Le nom de la société de bourse qui sert la synthèse de séance n'est plus
affiché (demande d'Abd Moutalib, 13/10/2026).

La provenance exacte reste tracée dans les fichiers internes et dans les
commentaires du code ; ce qui est PUBLIÉ — textes du briefing, libellés du
terminal — dit la nature de la source, pas son nom.
"""
import ast
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))


def _chaines_hors_docstrings(chemin: Path) -> list[str]:
    arbre = ast.parse(chemin.read_text(encoding="utf-8"))
    docs = set()
    for n in ast.walk(arbre):
        if isinstance(n, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            if n.body and isinstance(n.body[0], ast.Expr) and isinstance(n.body[0].value, ast.Constant):
                docs.add(id(n.body[0].value))
    return [n.value for n in ast.walk(arbre)
            if isinstance(n, ast.Constant) and isinstance(n.value, str) and id(n) not in docs]


def test_le_briefing_ne_publie_pas_le_nom():
    fautives = [c for c in _chaines_hors_docstrings(RACINE / "pipeline" / "briefing.py") if "CDG" in c]
    assert fautives == []


def test_la_source_publiee_garde_sa_nature():
    from pipeline import briefing as bf
    assert "société de bourse agréée" in bf.SOURCE_SEANCE


def test_le_terminal_n_affiche_plus_les_anciens_libelles():
    html = (RACINE / "index.html").read_text(encoding="utf-8")
    for ancien in ("Indices sectoriels CDG", "CDG synthèse", "Classification CDG",
                   "synthèse CDG absente", "volume CDG (écart", "(servi par CDG)"):
        assert ancien not in html, ancien


def test_les_lectures_deja_publiees_sont_traduites_a_l_affichage():
    """Les archives de briefings/ portent l'ancien texte : le terminal le
    traduit au chargement plutôt que de réécrire les archives."""
    html = (RACINE / "index.html").read_text(encoding="utf-8")
    assert "sansNomCourtier" in html
    assert html.count(".then(sansNomCourtier)") >= 2
