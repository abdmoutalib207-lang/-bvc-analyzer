"""Le pilier NLP est gelé — et ce gel se vérifie par INVARIANCE.

LE PROBLÈME
───────────
Le 25/09/2026 le poids du pilier NLP est passé à zéro. Le sentiment entrait
pourtant encore dans la note par d'autres portes : six bonus lisant le corpus
(convergence, convergence baissière, divergence, Smart Money, Contrarian,
alpha négatif), la condition « taux de réussite ≥ 80 % » du palier ACHAT FORT,
et trois modulateurs de pondération tirés du corpus (`ticker_coverage`,
`smart_money_active`, `hype_spike`) qui redécoupaient fondamental et technique.

Un pilier « gelé » qui déplace la note n'est pas gelé.

LA RECETTE
──────────
On ne vérifie pas que tel bonus a disparu — on en oublierait un. On fait
varier le sentiment entre ses EXTRÊMES et l'on exige que la note, le signal,
la pondération et les bonus restent identiques au centième. C'est la recette
de l'audit indépendant du 26/09 : injecter l'inverse et constater que rien ne
bouge.

Ce qui PEUT changer, et doit changer : `nlp`, `score_nlp`, `nlp_corpus` — le
pilier reste calculé et publié, à poids nul, pour garder la trace de ce qu'il
valait.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

import update_data as u  # noqa: E402

TICKER = "ZZTEST"

# Deux sentiments aussi opposés que le corpus peut les produire.
EUPHORIE = {"smart": 1.0, "hype": 1.0, "alpha": 50.0, "win": 1.0,
            "mentions": 5000, "biais": "ACHAT FORT", "contrarian": True}
PANIQUE = {"smart": -1.0, "hype": 0.0, "alpha": -50.0, "win": 0.0,
           "mentions": 0, "biais": "VENTE", "contrarian": False}

CONTEXTES = [
    {"market_status": "OPEN", "masi_ytd": 3.0},
    {"market_status": "CLOSED", "masi_ytd": -8.0},
    {"market_status": "CLOSED", "masi_ytd": 12.0, "has_results": True},
]

# (score_tech, score_fond, bvc_score, red_flags, upside) — note haute, note
# basse, BVC sous et au-dessus de 5,5 (le seuil des bonus de convergence).
CAS = [
    (9.5, 9.8, 7.5, 0, 20.0),
    (2.0, 1.5, 3.0, 0, 5.0),
    (6.0, 6.0, 5.0, 0, 0.0),
    (5.0, 7.0, 6.0, 4, -20.0),
]

# `delta` retiré le 29/09/2026 : il n'est plus publié (score canonique).
CHAMPS_GELES = ("v53", "sig", "poids", "bonus", "warn", "conv")


def _calcul(monkeypatch, sentiment, apport_news, cas, contexte):
    monkeypatch.setitem(u.SENTIMENT, TICKER, dict(sentiment))
    monkeypatch.setattr(u, "_apport_actualites", lambda _t: apport_news)
    st, sf, bvc, flags, upside = cas
    return u.compute_v53(TICKER, st, sf, bvc, flags, upside, dict(contexte))


@pytest.mark.parametrize("cas", CAS)
@pytest.mark.parametrize("contexte", CONTEXTES)
def test_le_sentiment_extreme_ne_change_ni_la_note_ni_le_signal(monkeypatch, cas, contexte):
    haut = _calcul(monkeypatch, EUPHORIE, +1.0, cas, contexte)
    bas = _calcul(monkeypatch, PANIQUE, -1.0, cas, contexte)
    for champ in CHAMPS_GELES:
        assert haut[champ] == bas[champ], (
            f"{champ} dépend encore du sentiment : {haut[champ]!r} ≠ {bas[champ]!r}")


def test_le_pilier_reste_publie_et_bouge_lui(monkeypatch):
    """Garde contre un test vide : si le sentiment n'atteignait plus le
    calcul, l'invariance serait triviale. Le pilier, lui, DOIT bouger."""
    haut = _calcul(monkeypatch, EUPHORIE, +1.0, CAS[0], CONTEXTES[0])
    bas = _calcul(monkeypatch, PANIQUE, -1.0, CAS[0], CONTEXTES[0])
    assert haut["score_nlp"] == 10.0 and bas["score_nlp"] == 0.0
    assert haut["poids"]["n"] == 0


def test_achat_fort_est_suspendu(monkeypatch):
    """Note au plafond ET smart money à 100 % : l'ancien palier ACHAT FORT
    aurait été servi. Il ne l'est plus — il n'a jamais été mesuré sans le
    corpus."""
    r = _calcul(monkeypatch, EUPHORIE, +1.0, (10.0, 10.0, 9.0, 0, 30.0), CONTEXTES[0])
    assert r["v53"] >= 7.5
    assert "ACHAT FORT" not in r["sig"]
    assert r["sig"].startswith("ACHETER")


def test_les_bonus_fondamentaux_restent_actifs(monkeypatch):
    """Le gel ne doit pas emporter ce qui ne lit pas le corpus."""
    r = _calcul(monkeypatch, PANIQUE, 0.0, (5.0, 7.0, 6.0, 4, -20.0), CONTEXTES[0])
    assert any(b.startswith("-Red flags") for b in r["bonus"])
    assert any(b.startswith("-Upside négatif") for b in r["bonus"])


def test_le_contexte_de_ponderation_ne_lit_plus_le_corpus():
    """Les modulateurs tirés du corpus étaient construits dans la boucle
    principale, pas dans `compute_v53` : l'invariance ci-dessus ne les voit
    pas. On vérifie donc que plus aucun dictionnaire du moteur ne les
    fabrique — par l'arbre syntaxique, pas par recherche de texte, les
    commentaires citant ces noms."""
    arbre = ast.parse((RACINE / "update_data.py").read_text(encoding="utf-8"))
    interdits = {"ticker_coverage", "smart_money_active", "hype_spike"}
    trouves = {
        k.value
        for n in ast.walk(arbre) if isinstance(n, ast.Dict)
        for k in n.keys if isinstance(k, ast.Constant) and k.value in interdits
    }
    assert not trouves, f"modulateurs issus du corpus encore construits : {trouves}"


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
