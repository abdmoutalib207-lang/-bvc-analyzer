"""Le lecteur de résultats semestriels — ce qu'il lit, et ce qu'il refuse de lire.

Les lignes sont RECOPIÉES des dépôts AMMC du 29/09/2026 ; les attendus sont
ceux relevés à la main dans le même document. Les pièges rencontrés en le
construisant sont figés ici pour ne pas revenir.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pipeline.lecture_resultats import en_mdh, lire, lire_ligne, lire_prose  # noqa: E402

RNPG = r"r[ée]sultat net\s*[-–(]?\s*part du groupe\)?"


@pytest.mark.parametrize("ligne,attendu", [
    # Managem : l'écart publié (3 397) tranche entre les lectures possibles.
    ("Résultat net part du Groupe 3 778 380 3 397", (3778, 380)),
    # Sothema : le « +11 % » est lu à part, pas pris pour une colonne.
    ("Résultat net part du Groupe 215 194 +11 %", (215, 194)),
    # CMT : deux montants au dirham, une seule lecture possible.
    ("Résultat net (part du groupe) 187 165 227 74 751 639", (187165227, 74751639)),
])
def test_lecture_des_tableaux(ligne, attendu):
    assert lire_ligne(ligne, RNPG) == attendu


def test_le_pourcentage_publie_departage():
    # SGTM : 793 ÷ 739 − 1 = +7,3 %, comme publié.
    assert lire_ligne("Résultat net 793 739 +7,3%", r"r[ée]sultat net\b") == (793, 739)


def test_la_prose_du_communique():
    t = ("Le Résultat Net Part du Groupe RNPG à fin juin 2026 ressort ainsi à "
         "333 MDh, comparé à 387 MDh à fin juin 2025.")
    assert lire_prose(t, RNPG) == (333, 387)


def test_le_piege_de_risma_la_phrase_suivante_ne_compte_pas():
    """« RNPG Juin 2026 » en fin de phrase, puis l'ENDETTEMENT NET dans la
    suivante : la première version lisait 1 029 contre 1 968 comme un
    résultat. Faux, cohérent, et invisible sans ce test."""
    t = ("Cessions Impôts RNPG Juin 2026 Une structure financière profondément "
         "renforcée › Au 30 juin 2026, l’endettement net s’établit à 1 029 MDH, "
         "contre 1 968 MDH au 31 décembre 2025.")
    assert lire_prose(t, r"\bRNPG\b") is None


def test_l_unite_se_deduit_de_la_capitalisation():
    # HPS : 34 811 645 DH pour une capitalisation de 4 555 MDH → 34,8 MDH.
    assert round(en_mdh(34811645, 4555), 3) == 34.812
    # Sans capitalisation, on ne devine pas.
    assert en_mdh(34811645, None) is None


def test_une_ligne_sans_controle_et_ambigue_ne_donne_rien():
    # Trois montants, aucun écart ni pourcentage qui les relie : plusieurs
    # lectures plausibles, donc aucune.
    assert lire_ligne("Résultat net part du groupe 120 118 97", RNPG) is None


def test_lire_un_document_entier():
    t = ("Chiffre d’affaires 852 628 224\nRésultat net 243 108 136\n")
    r = lire(t, cap_mdh=10364)
    assert r["resultat"] == (243.0, 108.0) and r["ca"] == (852.0, 628.0)
