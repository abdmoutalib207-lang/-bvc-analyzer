#!/usr/bin/env python3
"""La coupure entre ce qui serait publié et ce qui est retenu tient-elle ?

⚠️ CE QUE CES TESTS PROTÈGENT
Un candidat de fusion limité repose sur une affirmation : le lot mis en ligne
ne dépend pas du lot retenu. Si elle est fausse, l'arbre fusionné ne démarre
pas — et on ne s'en apercevrait qu'en production, sur le run du matin.

L'affirmation est donc vérifiée ici, sur l'arbre syntaxique, à chaque suite.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE / "pipeline"))

from candidat_fusion import (  # noqa: E402
    HISTORIQUE_CONSERVE, LOT_A, MODULES_LOT_B, verifier_independance,
)


def test_le_lot_publie_n_importe_rien_du_lot_retenu():
    r = verifier_independance()
    assert r["fichiers_absents"] == [], \
        f"le lot A cite des fichiers qui n'existent pas : {r['fichiers_absents']}"
    assert r["independant"], \
        f"le lot A dépend de la couche retenue : {r['imports_interdits']}"


def test_la_verification_attrape_vraiment_un_import_interdit(tmp_path):
    """⚠️ Un contrôle qui ne peut pas échouer ne contrôle rien.

    On lui soumet un fichier qui importe la couche retenue : il doit le voir.
    """
    faute = tmp_path / "faux_module.py"
    faute.write_text("from identites import autoriser_ecriture\n", encoding="utf-8")
    import candidat_fusion as cf
    ancien = cf.RACINE
    try:
        cf.RACINE = tmp_path
        r = cf.verifier_independance(["faux_module.py"])
    finally:
        cf.RACINE = ancien
    assert not r["independant"]
    assert r["imports_interdits"][0]["importe"] == "identites"


def test_une_mention_en_commentaire_n_est_pas_un_import(tmp_path):
    """Le contrôle lit la syntaxe, pas le texte : citer « identites » dans un
    commentaire ne doit pas faire échouer une livraison."""
    sain = tmp_path / "sain.py"
    sain.write_text("# ce module NE dépend PAS de identites ni de contamination\n"
                    "import json\n", encoding="utf-8")
    import candidat_fusion as cf
    ancien = cf.RACINE
    try:
        cf.RACINE = tmp_path
        r = cf.verifier_independance(["sain.py"])
    finally:
        cf.RACINE = ancien
    assert r["independant"]


def test_l_historique_n_est_pas_repris(): 
    """⚠️ LA CORRECTION DEMANDÉE PAR LA REVUE.

    Une version antérieure importait `historical_data.json` depuis la branche
    et « résolvait » un conflit qui n'existait pas dans cette méthode de
    construction : en partant de main par reprise de fichiers, il suffit de ne
    pas y toucher.

    Le patch ne changeait d'ailleurs aucune valeur — il ajoutait un bloc
    `_resolution` déclarant quatre arbitrages d'extrema que la revue n'a pas
    validés. Déclarer « la fenêtre a glissé, les deux valeurs sont justes » est
    une affirmation, pas une mesure.

    Historique existant conservé, assainissement hors périmètre.
    """
    assert HISTORIQUE_CONSERVE not in LOT_A


def test_aucune_piece_de_la_couche_retenue_n_entre_dans_le_lot_publie():
    """La coupure n'a plus d'exception. S'il en faut une un jour, elle devra
    être nommée ici, pas glissée dans la liste."""
    remontees = [f for f in LOT_A if Path(f).stem in MODULES_LOT_B]
    assert remontees == [], (
        f"des pièces de la couche retenue sont entrées dans le lot publié : "
        f"{remontees}")


def test_le_resolveur_est_bien_hors_perimetre():
    """⚠️ Nommément : la revue a demandé son retrait, et un retrait se vérifie."""
    assert "resoudre_historique" in MODULES_LOT_B
    assert not any("resoudre_historique" in f for f in LOT_A)


def test_tous_les_fichiers_du_lot_publie_existent_et_sont_lisibles():
    for rel in LOT_A:
        p = RACINE / rel
        assert p.exists(), f"{rel} est annoncé au lot A mais absent du dépôt"
        if rel.endswith(".py"):
            ast.parse(p.read_text(encoding="utf-8"))   # ne doit pas lever


# ═══ LE POINT D'ENTRÉE VERS LE FICHIER PUBLIÉ DOIT ÊTRE LE SEUL ═══════════

def test_aucun_test_ne_lit_data_json_en_direct():
    """⚠️ UN MÉCANISME À MOITIÉ BRANCHÉ EST PIRE QUE PAS DE MÉCANISME.

    `BVC_DATA_JSON` désigne le fichier publié soumis aux contrôles. S'il ne
    vaut que pour une partie des tests, une relecture hors ligne juge un
    mélange : trois fichiers lisent la livraison, les autres le dépôt — et le
    résultat ne décrit plus rien.

    Le projet a déjà payé cette faute cette semaine, avec un garde-fou défini
    et appelé de nulle part. On la refuse ici par construction.
    """
    fautifs = []
    for f in sorted((RACINE / "tests").glob("test_*.py")):
        src = f.read_text(encoding="utf-8")
        for n in ast.walk(ast.parse(src)):
            # `<quelque chose> / "data.json"` — la lecture en dur du dépôt.
            if isinstance(n, ast.BinOp) and isinstance(n.op, ast.Div) \
                    and isinstance(n.right, ast.Constant) \
                    and n.right.value == "data.json":
                # `tmp_path / "data.json"` est légitime : c'est un fichier jetable.
                gauche = getattr(n.left, "id", None) or getattr(n.left, "attr", None)
                if gauche != "tmp_path":
                    fautifs.append(f"{f.name}:{n.lineno}")
    assert fautifs == [], (
        f"ces tests lisent data.json en dur au lieu de chemin_data_json() : "
        f"{fautifs}")


def test_le_point_d_entree_refuse_un_fichier_absent(tmp_path, monkeypatch):
    """⚠️ Ne pas trouver le fichier désigné ne doit pas faire retomber la suite
    sur celui du dépôt : elle rendrait un vert sur un autre fichier que celui
    qu'on croit juger."""
    import pytest
    from conftest import chemin_data_json
    monkeypatch.setenv("BVC_DATA_JSON", str(tmp_path / "inexistant.json"))
    with pytest.raises(FileNotFoundError):
        chemin_data_json()
