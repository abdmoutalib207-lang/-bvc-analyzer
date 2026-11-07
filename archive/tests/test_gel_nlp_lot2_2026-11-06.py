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
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

import update_data as u  # noqa: E402

CONTEXTES = [
    {"market_status": "OPEN", "masi_ytd": 3.0},
    {"market_status": "CLOSED", "masi_ytd": -8.0},
    {"market_status": "CLOSED", "masi_ytd": 12.0, "has_results": True},
]

# (score_tech, score_fond, red_flags, upside) — note haute, note basse, et
# des malus figés qui ne doivent plus rien produire.
CAS = [
    (9.5, 9.8, 0, 20.0),
    (2.0, 1.5, 0, 5.0),
    (6.0, 6.0, 0, 0.0),
    (5.0, 7.0, 4, -20.0),
]

# Ce que rend `compute_v53`, et rien d'autre : plus aucun champ du pilier.
CHAMPS_RENDUS = {"v53", "score_tech", "score_fond", "sig", "bonus", "poids"}


@pytest.mark.parametrize("cas", CAS)
@pytest.mark.parametrize("contexte", CONTEXTES)
def test_le_titre_ne_change_ni_la_note_ni_le_signal(cas, contexte):
    """MNG et CMT portaient les sentiments les plus extrêmes de l'ancienne
    table ; ZZTEST n'y figurait pas. Mêmes notes, même contexte : même sortie."""
    st, sf, flags, upside = cas
    sorties = [u.compute_v53(t, st, sf, flags, upside, dict(contexte))
               for t in ("ZZTEST", "MNG", "CMT")]
    assert sorties[0] == sorties[1] == sorties[2]


def test_compute_v53_ne_rend_plus_aucun_champ_du_pilier():
    r = u.compute_v53("MNG", 6.0, 7.0, 0, 0.0, dict(CONTEXTES[0]))
    assert set(r) == CHAMPS_RENDUS, sorted(set(r) ^ CHAMPS_RENDUS)
    assert set(r["poids"]) == {"f", "t"}


def test_achat_fort_est_suspendu():
    """Note au plafond : l'ancien palier ACHAT FORT (note ≥ 7,5 ET smart money
    ≥ 80 %) aurait été servi. Il ne l'est plus — il n'a jamais été mesuré sans
    le corpus."""
    r = u.compute_v53("MNG", 10.0, 10.0, 0, 30.0, dict(CONTEXTES[0]))
    assert r["v53"] >= 7.5
    assert "ACHAT FORT" not in r["sig"]
    assert r["sig"].startswith("ACHETER")


def test_plus_aucun_bonus_ni_malus_ne_reste():
    """⚠️ Ce test vérifiait l'INVERSE jusqu'au 30/09/2026 : que « Red flags »
    et « Upside négatif » survivent au gel du corpus, puisqu'ils ne le
    lisaient pas. Ils lisaient en revanche une table écrite en dur
    (FOND_DATA) ; ils sont gelés à leur tour, avec accord (R8). Les alertes
    sont désormais calculées et affichées à part (test_alertes.py)."""
    r = u.compute_v53("ZZTEST", 5.0, 7.0, 4, -20.0, dict(CONTEXTES[0]))
    assert r["bonus"] == []


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


def test_le_second_pipeline_ne_sert_pas_achat_fort_non_plus():
    """R8 : les deux points d'application du score bougent ENSEMBLE. Le
    second servait ACHAT FORT dès 7,5, sans condition. On exécute sa fonction
    `sig` telle qu'écrite, extraite par l'arbre syntaxique."""
    src = (RACINE / "pipeline" / "collect_financial_data.py").read_text(encoding="utf-8")
    fonctions = [n for n in ast.walk(ast.parse(src))
                 if isinstance(n, ast.FunctionDef) and n.name == "sig"]
    assert len(fonctions) == 1
    espace = {}
    exec(compile(ast.Module(body=[fonctions[0]], type_ignores=[]), "sig", "exec"), espace)
    for note in (7.5, 8.9, 10.0):
        assert espace["sig"](note).startswith("ACHETER"), note
