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
    CONFLIT, LOT_A, MODULES_LOT_B, verifier_independance,
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


def test_le_fichier_en_conflit_n_est_pas_repris_tel_quel():
    """⚠️ Il doit être RÉSOLU, jamais copié d'un côté. L'inscrire dans le lot A
    reviendrait à prendre la version de la branche sans arbitrer."""
    assert CONFLIT not in LOT_A


def test_la_piece_remontee_du_lot_retenu_est_nommee():
    """Une seule exception à la coupure, et elle doit rester explicite."""
    remontees = [f for f in LOT_A
                 if Path(f).stem in MODULES_LOT_B | {"resoudre_historique"}]
    assert remontees == ["pipeline/resoudre_historique.py"], (
        f"des pièces de la couche retenue sont entrées dans le lot publié "
        f"sans être nommées : {remontees}")


def test_tous_les_fichiers_du_lot_publie_existent_et_sont_lisibles():
    for rel in LOT_A:
        p = RACINE / rel
        assert p.exists(), f"{rel} est annoncé au lot A mais absent du dépôt"
        if rel.endswith(".py"):
            ast.parse(p.read_text(encoding="utf-8"))   # ne doit pas lever
