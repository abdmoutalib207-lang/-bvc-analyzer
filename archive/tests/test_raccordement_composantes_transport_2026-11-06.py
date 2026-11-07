"""Le mode personnalisé doit combiner les VRAIES composantes.

LE CRITÈRE, TEL QUE L'AUDITEUR L'A FORMULÉ
──────────────────────────────────────────
    « à 100 % technique, la note doit égaler score_tech ;
      à 100 % fondamental, elle doit égaler score_fond. »

C'est le bon critère parce qu'il ne se satisfait d'aucune approximation : si
la note affichée à 100 % technique diffère de `score_tech`, c'est qu'elle ne
combine pas ce qu'elle annonce combiner.

CE QUI ÉTAIT CASSÉ (constaté le 09/09 par l'audit externe, vérifié ici)
──────────────────────────────────────────────────────────────────────
Deux défauts distincts, tous deux dans `computeDisplayScore` et son
alimentation :

  1. `score_tech` EXISTE dans data.json mais n'était pas transporté par
     `loadData`. La fonction retombait donc sur son repli `RSI / 10`, qui
     n'est pas la même formule — le moteur tient aussi compte des moyennes
     mobiles et de la position dans la fourchette de prix.
         ADI 7,50 → 5,72 · ADH 6,70 → 4,99 · Taqa 6,70 → 4,80

  2. Le « fondamental » personnalisé lisait `r.bvc`, la note BVC de référence,
     et non la note fondamentale calculée par `fond_score.py`.
         ADH 4,28 au lieu de 6,15 · HPS 7,15 au lieu de 6,40

  3. Découvert en corrigeant : `score_fond` n'était **émis nulle part** dans
     data.json. Le moteur le calcule pour composer v5.3 et ne le publie pas.
     Le frontend ne pouvait donc pas l'utiliser même en le voulant.

Le mode personnalisé ne changeait ainsi pas seulement les POIDS, mais les
INGRÉDIENTS — ce qui rend toute comparaison entre deux vues trompeuse.

⚠️ Ces tests lisent le source du frontend, faute d'outillage JavaScript en
intégration continue, et exécutent la fonction extraite via node lorsqu'il est
disponible. Voir `run-tests` pour la compilation JSX.

⚠️ 06/11/2026 — LE SCORE PERSONNALISÉ EST RETIRÉ DU TERMINAL. Décision d'Abd
Moutalib : la note v5.3 quitte l'écran, le Score BVC devient le score unique,
et les vues de pondération qui recalculaient la note v5.3 partent avec elle.
Les tests de `computeDisplayScore` (critère de l'auditeur, situations A/B,
tri d'une note absente, export) sont archivés dans
`archive/tests/test_raccordement_composantes_v53_2026-11-06.py` ; le tri d'un
score absent et l'export sont repris pour le Score BVC dans
`tests/test_ponderations_front.py`.
Restent ici, inchangés : le moteur publie `score_fond` et `score_tech`, et
`loadData` les transporte (contrat de data.json, `tools/audit_chaine.py`).
"""

import json
import re
from pathlib import Path

import pytest

from conftest import chemin_data_json  # noqa: E402

RACINE = Path(__file__).resolve().parent.parent


def _front():
    return (RACINE / "terminal.src.html").read_text(encoding="utf-8")


# ── 1. Le moteur publie-t-il les composantes ? ───────────────────────────

def test_le_moteur_emet_score_fond():
    """Sans lui, le frontend ne PEUT pas afficher la note fondamentale : elle
    n'existe nulle part dans le fichier publié."""
    s = (RACINE / "update_data.py").read_text(encoding="utf-8")
    assert re.search(r'"score_fond":\s*v53\.get\("score_fond"', s), (
        "update_data.py ne publie pas score_fond dans l'enregistrement du "
        "ticker — le mode personnalisé ne peut que deviner")


def test_le_moteur_emet_les_trois_composantes(candidat):
    """Les piliers de la formule v5.3 doivent être lisibles séparément.
    Publier la note sans ses composantes rend le calcul invérifiable.
    (28/10/2026 : deux piliers — `score_nlp` n'est plus publié.)"""
    manquants = [k for k in ("score_tech", "score_fond")
                 if candidat.get(k) is None]
    assert not manquants, (
        f"composantes absentes du fichier publié : {manquants}")


# ── 2. Le frontend transporte-t-il ces composantes ? ─────────────────────

def test_load_data_transporte_les_composantes():
    """⚠️ LE défaut n°1 : `score_tech` existait dans data.json et n'arrivait
    jamais jusqu'à la ligne affichée."""
    s = _front()
    m = re.search(r"const CHAMPS_SCORE\s*=\s*\[(.*?)\]", s, re.S)
    assert m, ("aucune liste explicite des champs de score à transporter — "
               "sans elle, un champ oublié retombe silencieusement sur un repli")
    champs = set(re.findall(r'"([a-z_0-9]+)"', m.group(1)))
    for c in ("score_tech", "score_fond"):
        assert c in champs, f"{c} n'est pas transporté vers la ligne affichée"
    # 28/10/2026 : pilier NLP retiré, il ne doit plus être transporté.
    assert "score_nlp" not in champs


@pytest.fixture(scope="module")
def candidat():
    """Un titre du fichier publié portant les trois composantes.

    On prend un cas réel plutôt qu'un objet fabriqué : un test sur des données
    inventées ne dirait rien de ce que le terminal affiche vraiment.
    """
    d = json.loads(chemin_data_json().read_text(encoding="utf-8"))
    for t in d["tickers"]:
        if all(t.get(k) is not None for k in ("score_tech", "score_fond", "bvc")):
            return t
    pytest.skip("aucun titre publié ne porte encore les trois composantes")
