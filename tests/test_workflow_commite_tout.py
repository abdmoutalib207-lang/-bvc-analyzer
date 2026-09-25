#!/usr/bin/env python3
"""Un fichier que le moteur écrit et que le workflow ne commite pas est perdu.

⚠️ LE DÉFAUT QUE CE TEST EMPÊCHE DE REVENIR — constaté le 25/09/2026
──────────────────────────────────────────────────────────────────────
`update_bvc.yml` commitait une liste NOMMÉE de quatre chemins. Le moteur en
écrivait huit. Quatre étaient donc produits à chaque run puis jetés :

    briefing.json                  la lecture de la séance
    briefing_hebdo.json            le bilan de la semaine
    pipeline/marche_history.json   l'état du marché par séance
    pipeline/score_history.json    LE JOURNAL DES SCORES

⚠️ Le dernier est le plus grave, parce que **sa raison d'être est
d'accumuler**. Écrit puis perdu à chaque run, il serait resté éternellement à
une seule séance — et la prochaine décision de pondération se serait à nouveau
appuyée sur treize jours d'archéologie git, exactement ce qu'il devait
supprimer.

⚠️ `masi_history` ET `marche_history` NE SONT PAS LE MÊME FICHIER. Le premier
est la série de l'indice, le second l'état du marché (largeur, volumes, YTD).
Un seul des deux était commité, et leurs noms se ressemblent assez pour que
personne ne s'en aperçoive.

C'est la même classe de défaut que l'énumération de champs du terminal, qui
avait rendu `rang_secteur` invisible : **une liste nommée ne suit pas ce qu'on
ajoute à côté d'elle**. Elle ne se corrige pas en étant plus attentif, elle se
corrige en étant vérifiée.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

WORKFLOW = (RACINE / ".github" / "workflows" / "update_bvc.yml").read_text(encoding="utf-8")
MOTEUR = (RACINE / "update_data.py").read_text(encoding="utf-8")


# Les fichiers que le run produit et qui doivent survivre au run.
# ⚠️ Ajouter ici tout nouveau fichier écrit par le moteur, en même temps que
# son écriture — c'est le seul moment où l'on y pense.
ECRITS_PAR_LE_MOTEUR = [
    ("data.json", "le flux publié"),
    ("pipeline/masi_history.json", "la série de l'indice"),
    ("pipeline/marche_history.json", "l'état du marché — PAS le même fichier que masi_history"),
    ("pipeline/score_history.json", "le journal des scores, dont la raison d'être est d'accumuler"),
    ("briefing.json", "la lecture de la séance, lue par l'onglet BRIEFING"),
    ("briefing_hebdo.json", "le bilan de la semaine"),
]


def _chemins_ajoutes() -> set[str]:
    """Les chemins réellement passés à `git add`, commentaires exclus.

    ⚠️ LA PREMIÈRE VERSION DE CE TEST CHERCHAIT LA CHAÎNE DANS TOUT LE
    FICHIER — et le commentaire qui explique le correctif cite justement les
    quatre chemins. Retirer `score_history.json` du `git add` laissait donc le
    test vert : il lisait la prose qui décrit le défaut, pas le code qui le
    corrige.

    C'est la troisième fois de la journée qu'un test échoue de cette façon :
    après `rang_secteur`, cherché dans index.html et trouvé dans un
    composant, et le seuil de matérialité cité dans un commentaire. **Un test
    qui lit un fichier entier lit aussi ses commentaires.**
    """
    # ⚠️ Deux pièges, et le second m'a eu aussi : les COMMENTAIRES citent les
    # chemins, et les CONTINUATIONS `\` coupent une commande en deux lignes.
    # On retire les commentaires, puis on recolle les continuations, AVANT de
    # chercher quoi que ce soit.
    propre = []
    for ligne in WORKFLOW.splitlines():
        nu = ligne.strip()
        if nu.startswith("#"):
            continue
        propre.append(nu)
    script = "\n".join(propre).replace("\\\n", " ")

    chemins = set()
    for nu in script.splitlines():
        source = None
        if "git add" in nu:
            source = nu.split("git add", 1)[1]
        elif nu.startswith("for f in "):
            # La boucle ajoute ses chemins via `$f` : sa liste fait foi.
            source = nu[len("for f in "):].split(";")[0]
        if source is None:
            continue
        for mot in source.split():
            mot = mot.strip('"\'')
            if mot.endswith(".json") or mot.endswith("/"):
                chemins.add(mot)
    return chemins


def test_chaque_fichier_ecrit_est_commite():
    """⚠️ Le contrôle central. Un fichier écrit et non commité est du travail
    fait quatre fois par jour et jeté quatre fois par jour."""
    ajoutes = _chemins_ajoutes()
    manquants = [(f, q) for f, q in ECRITS_PAR_LE_MOTEUR if f not in ajoutes]
    assert not manquants, (
        "le workflow ne passe pas ces fichiers à `git add`, ils seront perdus "
        "à chaque run : "
        + " ; ".join(f"{f} ({q})" for f, q in manquants)
        + f"  [chemins réellement ajoutés : {sorted(ajoutes)}]")


def test_les_deux_historiques_sont_distingues():
    """⚠️ `masi_history` et `marche_history` ont des noms voisins et des rôles
    différents. Le workflow doit passer LES DEUX à `git add`, pas seulement
    les citer dans un commentaire."""
    ajoutes = _chemins_ajoutes()
    assert "pipeline/masi_history.json" in ajoutes
    assert "pipeline/marche_history.json" in ajoutes


def test_le_moteur_ecrit_bien_ce_que_le_workflow_commite():
    """⚠️ Le contrôle dans l'autre sens : commiter un fichier que le moteur
    n'écrit plus laisserait croire qu'il est à jour.

    Lu sur les imports du moteur, pas sur une liste recopiée.
    """
    arbre = ast.parse(MOTEUR)
    modules = {(n.module or "") for n in ast.walk(arbre)
               if isinstance(n, ast.ImportFrom)}
    for module, fichier in (("pipeline.briefing", "briefing.json"),
                            ("pipeline.briefing_hebdo", "briefing_hebdo.json"),
                            ("pipeline.score_history", "pipeline/score_history.json"),
                            ("pipeline.marche_history", "pipeline/marche_history.json")):
        assert module in modules, (
            f"le workflow commite {fichier} mais le moteur n'importe plus "
            f"{module} — le fichier serait commité sans jamais changer")


def test_le_commit_ne_pousse_rien_quand_rien_ne_change():
    """⚠️ Le quota de publication de Pages est la ressource rare du projet.
    Un run qui commiterait sans changement le consommerait pour rien."""
    assert "git diff --cached --quiet" in WORKFLOW, (
        "le workflow commiterait même sans changement")


def test_l_ajout_est_conditionne_a_l_existence_du_fichier():
    """⚠️ `git add` sur un fichier absent fait échouer le pas entier. Un
    briefing non écrit — sa génération est volontairement non bloquante — ne
    doit pas empêcher la publication des cours."""
    i = WORKFLOW.find("for f in briefing.json")
    assert i > 0, "les nouveaux fichiers ne sont pas ajoutés"
    bloc = WORKFLOW[i:i + 400]
    assert '[ -f "$f" ]' in bloc, (
        "un fichier manquant ferait échouer le commit et donc la publication")
