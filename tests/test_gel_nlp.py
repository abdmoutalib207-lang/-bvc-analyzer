"""Le pilier NLP a été gelé (29/09/2026), puis retiré du moteur (28/10/2026).

LE PROBLÈME D'ORIGINE
─────────────────────
Le 25/09/2026 le poids du pilier NLP est passé à zéro. Le sentiment entrait
pourtant encore dans la note par d'autres portes : six bonus lisant le corpus
(convergence, convergence baissière, divergence, Smart Money, Contrarian,
alpha négatif), la condition « taux de réussite ≥ 80 % » du palier ACHAT FORT,
et trois modulateurs de pondération tirés du corpus (`ticker_coverage`,
`smart_money_active`, `hype_spike`) qui redécoupaient fondamental et technique.

Un pilier « gelé » qui déplace la note n'est pas gelé.

LA RECETTE, PUIS LE RETRAIT
───────────────────────────
Jusqu'au 28/10/2026, ce fichier faisait varier le sentiment entre ses
EXTRÊMES et exigeait que la note, le signal, la pondération et les bonus
restent identiques — l'invariance. Depuis le retrait (décision d'Abd
Moutalib : « le corpus à supprimer et tout ce qui est NLP », lot 2), il n'y a
plus de sentiment à faire varier : `compute_v53` ne lit plus que les deux
notes de pilier et le contexte de marché. L'invariance devient structurelle —
le nom du titre, y compris celui d'un ancien titre du corpus, ne change rien —
et le reste des gardes du gel est conservé. Garde du retrait lui-même :
tests/test_retrait_nlp.py.

⚠️ 06/11/2026 — retrait de la note v5.3 (lot 2) : `compute_v53`, ses bonus et
ses paliers, et la seconde formule de `collect_financial_data.py` n'existent
plus. Les tests d'invariance de la note sont archivés dans
`archive/tests/test_gel_nlp_lot2_2026-11-06.py`. Reste le garde-fou : aucun
modulateur tiré du corpus ne réapparaît dans le moteur.
"""

from __future__ import annotations

import ast
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent


def test_le_contexte_de_ponderation_ne_lit_plus_le_corpus():
    """Les modulateurs tirés du corpus étaient construits dans la boucle
    principale, pas dans `compute_v53`. On vérifie que plus aucun dictionnaire
    du moteur ne les fabrique, et que `get_weights` ne les lit plus — par
    l'arbre syntaxique, pas par recherche de texte, les commentaires citant
    ces noms."""
    arbre = ast.parse((RACINE / "update_data.py").read_text(encoding="utf-8"))
    interdits = {"ticker_coverage", "smart_money_active", "hype_spike", "comportemental"}
    trouves = {
        n.value
        for n in ast.walk(arbre)
        if isinstance(n, ast.Constant) and n.value in interdits
    }
    assert not trouves, f"modulateurs ou pilier issus du corpus encore présents : {trouves}"
