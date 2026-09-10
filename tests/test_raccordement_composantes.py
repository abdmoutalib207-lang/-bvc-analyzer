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
"""

import json
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parent.parent


def _front():
    return (RACINE / "index.html").read_text(encoding="utf-8")


# ── 1. Le moteur publie-t-il les composantes ? ───────────────────────────

def test_le_moteur_emet_score_fond():
    """Sans lui, le frontend ne PEUT pas afficher la note fondamentale : elle
    n'existe nulle part dans le fichier publié."""
    s = (RACINE / "update_data.py").read_text(encoding="utf-8")
    assert re.search(r'"score_fond":\s*v53\.get\("score_fond"', s), (
        "update_data.py ne publie pas score_fond dans l'enregistrement du "
        "ticker — le mode personnalisé ne peut que deviner")


def test_le_moteur_emet_les_trois_composantes(candidat):
    """Les trois piliers de la formule v5.3 doivent être lisibles séparément.
    Publier la note sans ses composantes rend le calcul invérifiable."""
    manquants = [k for k in ("score_tech", "score_fond", "score_nlp")
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
    for c in ("score_tech", "score_fond", "score_nlp"):
        assert c in champs, f"{c} n'est pas transporté vers la ligne affichée"


# ── 3. Le critère de l'auditeur, littéralement ───────────────────────────

def test_le_fondamental_ne_lit_plus_la_note_bvc():
    """`r.bvc` est la note BVC de référence, pas la note fondamentale."""
    m = re.search(r"function computeDisplayScore\(r, p\) \{(.*?)\n\}", _front(), re.S)
    assert m, "computeDisplayScore introuvable"
    corps = m.group(1)
    assert "const sf = r.bvc" not in corps, (
        "le fondamental personnalisé lit encore la note BVC : le mode change "
        "les ingrédients, pas seulement les poids")
    assert "r.score_fond" in corps, "la note fondamentale n'est pas utilisée"


def test_le_repli_rsi_ne_masque_plus_le_score_technique():
    """Le repli RSI/10 doit rester un DERNIER recours, jamais le chemin normal.
    Il l'était devenu parce que score_tech n'arrivait pas."""
    corps = re.search(r"function computeDisplayScore\(r, p\) \{(.*?)\n\}",
                      _front(), re.S).group(1)
    assert "r.score_tech != null" in corps, (
        "le score technique du moteur n'est plus consulté en priorité")


@pytest.mark.parametrize("vue,champ", [("technique", "score_tech"),
                                       ("fondamental", "score_fond")])
def test_une_vue_a_cent_pour_cent_egale_sa_composante(candidat, vue, champ):
    """LE test demandé par l'auditeur, exécuté sur les données publiées.

    On construit une pondération extrême — 100 % d'un seul pilier — et la note
    doit alors être EXACTEMENT la composante correspondante. Toute différence
    signale que la fonction ne combine pas ce qu'elle prétend combiner.
    """
    node = shutil.which("node")
    if not node:
        pytest.skip("node absent : la fonction ne peut pas être exécutée")
    s = _front()
    fn = re.search(r"function computeDisplayScore\(r, p\) \{.*?\n\}", s, re.S)
    assert fn, "computeDisplayScore introuvable"

    poids = {"f": 100 if vue == "fondamental" else 0, "n": 0,
             "t": 100 if vue == "technique" else 0}
    script = (fn.group(0) + "\n"
              + f"const r = {json.dumps(candidat)};\n"
              + f"const p = {json.dumps(poids)};\n"
              + "console.log(computeDisplayScore(r, p));\n")
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False) as f:
        f.write(script)
        chemin = f.name
    try:
        sortie = subprocess.run([node, chemin], capture_output=True, text=True,
                                timeout=20)
    finally:
        Path(chemin).unlink(missing_ok=True)
    assert sortie.returncode == 0, f"node a échoué : {sortie.stderr[:300]}"

    obtenu = float(sortie.stdout.strip())
    attendu = float(candidat[champ])
    assert obtenu == pytest.approx(attendu, abs=0.01), (
        f"vue 100 % {vue} sur {candidat['symbol']} : la note vaut {obtenu}, "
        f"alors que {champ} vaut {attendu}. La fonction ne combine pas les "
        "composantes qu'elle annonce.")


@pytest.fixture(scope="module")
def candidat():
    """Un titre du fichier publié portant les trois composantes.

    On prend un cas réel plutôt qu'un objet fabriqué : un test sur des données
    inventées ne dirait rien de ce que le terminal affiche vraiment.
    """
    d = json.loads((RACINE / "data.json").read_text(encoding="utf-8"))
    for t in d["tickers"]:
        if all(t.get(k) is not None for k in ("score_tech", "score_fond", "bvc")):
            return t
    pytest.skip("aucun titre publié ne porte encore les trois composantes")
