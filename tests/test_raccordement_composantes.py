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

from conftest import chemin_data_json  # noqa: E402

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

def _fonctions_js(*noms: str) -> str:
    """Le source JavaScript de ces fonctions, prêt à être exécuté par node."""
    s = _front()
    out = []
    for nom in noms:
        m = re.search(r"function " + nom + r"\(.*?\) \{.*?\n\}", s, re.S)
        assert m, f"{nom} introuvable dans index.html"
        out.append(m.group(0))
    return "\n".join(out)


def _machinerie() -> str:
    """Les trois fonctions du score personnalisé, prises ensemble.

    ⚠️ Une version antérieure de ces contrôles lisait le seul corps de
    `computeDisplayScore`. Déplacer la lecture des composantes dans une
    fonction voisine les faisait échouer alors que rien de fautif n'avait été
    introduit — ils décrivaient un DÉCOUPAGE, pas une propriété. On prend
    désormais l'ensemble de la machinerie.

    ⚠️ LES COMMENTAIRES SONT ÔTÉS. Sans cela, le contrôle échoue sur la phrase
    qui EXPLIQUE le retrait de `r.bvc` — une mention n'est pas une lecture. Le
    projet a déjà rencontré ce piège sur `_updated` dans le résolveur.
    """
    s = _front()
    corps = []
    for nom in ("composantesScore", "composantesManquantes", "computeDisplayScore"):
        m = re.search(r"function " + nom + r"\(.*?\) \{(.*?)\n\}", s, re.S)
        assert m, f"{nom} introuvable"
        corps.append(m.group(1))
    code = "\n".join(corps)
    code = re.sub(r"/\*.*?\*/", " ", code, flags=re.S)       # blocs /* … */
    code = re.sub(r"//[^\n]*", " ", code)                    # lignes //
    return code


def test_le_fondamental_ne_lit_plus_la_note_bvc():
    """`r.bvc` est la note BVC de référence, pas la note fondamentale."""
    corps = _machinerie()
    assert "r.bvc" not in corps, (
        "le score personnalisé lit encore la note BVC : le mode changerait "
        "les ingrédients, pas seulement les poids")
    assert "r.score_fond" in corps, "la note fondamentale n'est pas utilisée"


def test_le_repli_rsi_ne_masque_plus_le_score_technique():
    """⚠️ Le repli RSI/10 n'est plus un dernier recours : il n'existe plus.

    Une note approchée ressemble à une note. Pendant la fenêtre qui suit une
    fusion, `score_tech` est absent de l'ancien `data.json` et le repli
    reprenait la main en silence.
    """
    corps = _machinerie()
    assert "r.score_tech" in corps, "le score technique du moteur n'est pas lu"
    assert "rsi" not in corps.lower(), (
        "un repli RSI subsiste dans le score personnalisé — une valeur "
        "approchée doit être refusée, pas fabriquée")


def test_une_composante_requise_absente_rend_le_score_indisponible():
    """⚠️ LE CONTRÔLE DEMANDÉ PAR LA REVUE DU 11/09.

    Si une composante nécessaire manque, la fonction ne doit rendre NI `bvc`,
    NI une approximation, mais `null` — un état indisponible explicite.
    """
    corps = _machinerie()
    assert re.search(r"composantesManquantes\(r,\s*p\)\.length[\s\S]{0,40}return null",
                     corps), (
        "aucun refus explicite : une composante absente doit rendre `null`")


def test_une_composante_de_poids_nul_n_est_pas_requise():
    """En 70/30, l'absence de NLP ne doit rien bloquer : son poids est nul."""
    corps = _machinerie()
    assert re.search(r"\(p\.n\s*\|\|\s*0\)\s*>\s*0", corps), (
        "l'exigence ne tient pas compte du poids : un pilier non pondéré "
        "bloquerait le calcul sans raison")


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
    # ⚠️ LES TROIS FONCTIONS, pas une seule. `computeDisplayScore` appelle
    # désormais `composantesManquantes` et `composantesScore` : n'extraire que
    # la première produisait un « ReferenceError » — et ce test s'abstenant
    # tant que les composantes manquent au dépôt, la casse ne se serait vue
    # qu'en CI, où le fichier EST généré.
    script_fn = _fonctions_js("composantesScore", "composantesManquantes",
                              "computeDisplayScore")

    poids = {"f": 100 if vue == "fondamental" else 0, "n": 0,
             "t": 100 if vue == "technique" else 0}
    script = (script_fn + "\n"
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
    d = json.loads(chemin_data_json().read_text(encoding="utf-8"))
    for t in d["tickers"]:
        if all(t.get(k) is not None for k in ("score_tech", "score_fond", "bvc")):
            return t
    pytest.skip("aucun titre publié ne porte encore les trois composantes")


# ── 4. Les deux situations : ancien fichier, nouveau fichier ─────────────
#
# ⚠️ Exigence de la revue du 11/09. Le correctif doit tenir dans les DEUX
# états que le site traversera : celui d'avant le run qui suit la fusion, et
# celui d'après. Ces contrôles exécutent la fonction, ils ne la relisent pas.

def _executer_js(script: str) -> str:
    node = shutil.which("node")
    if not node:
        pytest.skip("node absent : la fonction ne peut pas être exécutée")
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False) as f:
        f.write(script)
        chemin = f.name
    try:
        r = subprocess.run([node, chemin], capture_output=True, text=True, timeout=20)
    finally:
        Path(chemin).unlink(missing_ok=True)
    assert r.returncode == 0, f"node a échoué : {r.stderr[:400]}"
    return r.stdout.strip()


ANCIEN = {"symbol": "ADH", "bvc": 4.28, "v53": 5.82, "rsi": 52.3, "nlp": 0.03}
NOUVEAU = dict(ANCIEN, score_fond=6.15, score_tech=6.70, score_nlp=5.0)
P7030 = {"f": 70, "n": 0, "t": 30}


def test_situation_A_ancien_fichier_la_note_est_indisponible():
    """⚠️ LA FENÊTRE QUI SUIT LA FUSION.

    Avec l'ancien `data.json`, les composantes sont absentes. La fonction
    rendait alors 5,01 — calculé sur `r.bvc`, la valeur que l'audit du 09/09
    avait signalée. Elle doit désormais rendre `null`.
    """
    sortie = _executer_js(
        _fonctions_js("composantesScore", "composantesManquantes",
                      "computeDisplayScore")
        + f"\nconsole.log(JSON.stringify(computeDisplayScore({json.dumps(ANCIEN)}, {json.dumps(P7030)})));"
        + f"\nconsole.log(JSON.stringify(composantesManquantes({json.dumps(ANCIEN)}, {json.dumps(P7030)})));")
    note, manque = sortie.splitlines()
    assert note == "null", f"une note approchée est encore produite : {note}"
    assert json.loads(manque) == ["Fondamental", "Technique"]


def test_situation_B_nouveau_fichier_la_note_est_calculee():
    sortie = _executer_js(
        _fonctions_js("composantesScore", "composantesManquantes",
                      "computeDisplayScore")
        + f"\nconsole.log(computeDisplayScore({json.dumps(NOUVEAU)}, {json.dumps(P7030)}));")
    assert float(sortie) == pytest.approx((6.15 * 70 + 6.70 * 30) / 100, abs=0.01)


def test_une_note_indisponible_ne_se_confond_pas_avec_une_note_de_zero():
    """⚠️ LA FRONTIÈRE QUI DISCRIMINE VRAIMENT — et une erreur de ma part.

    J'avais d'abord éprouvé ce tri sur un titre absent face à des notes
    élevées. Ce cas ne prouve rien : JavaScript coerce `null` en `0` dans une
    soustraction, si bien que l'ancien code plaçait déjà les absents en fin.
    La mutation ne faisait pas tomber le test, et je l'ai vu au lieu de
    l'annoncer vert.

    La différence se joue à la seule frontière où elle existe : face à un
    titre dont la note VAUT zéro. Par coercition, les deux sont à égalité et
    l'ordre d'entrée décide — l'absent peut donc passer DEVANT un titre noté.
    Avec la règle explicite, il sort toujours par le bas.
    """
    s = _front()
    m = re.search(r'if\(sort==="v53"\)\{(.*?)\n    \}', s, re.S)
    assert m, "la branche de tri sur v53 est introuvable"
    tri = m.group(1)
    zero = dict(NOUVEAU, symbol="ZERO", score_fond=0.0, score_tech=0.0)
    script = (
        _fonctions_js("composantesScore", "composantesManquantes",
                      "computeDisplayScore")
        + "\nconst scoreMode = " + json.dumps(P7030) + ";"
        + "\nfunction comparer(a, b){" + tri + "\n}"
        # ⚠️ L'absent est placé EN PREMIER à l'entrée : si le tri ne tranche
        # pas, un tri stable le laisse devant le titre noté zéro.
        + "\nconst lignes = ["
        + f"{json.dumps(dict(ANCIEN, symbol='ABSENT'))},"
        + f"{json.dumps(zero)},"
        + f"{json.dumps(dict(NOUVEAU, symbol='HAUT', score_fond=9.0))}];"
        + "\nconsole.log(lignes.sort(comparer).map(x=>x.symbol).join(','));")
    assert _executer_js(script) == "HAUT,ZERO,ABSENT", (
        "une note indisponible se classe à égalité avec une note de zéro : "
        "elle peut alors passer devant un titre réellement noté")


def test_l_export_csv_n_ecrit_jamais_une_note_absente_comme_un_nombre():
    """⚠️ `computeDisplayScore(...).toFixed(2)` levait une exception sur une
    note absente : l'export entier échouait. Et l'écrire `0.00` serait pire —
    un chiffre faux voyage plus loin qu'une erreur."""
    s = _front()
    m = re.search(r"const rows_csv=.*?\]\);", s, re.S)
    assert m, "la construction du CSV est introuvable"
    ligne = m.group(0)
    assert "computeDisplayScore(r,scoreMode).toFixed" not in ligne, (
        "l'export appelle toFixed sans garde : une note absente le fait lever")
    assert "indisponible" in ligne, (
        "l'export doit nommer l'état indisponible, pas écrire un nombre")
