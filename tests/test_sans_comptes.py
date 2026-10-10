"""Registre des sociétés cotées sans comptes déposés (bvc_config.SANS_COMPTES).

Un titre qui ne publie plus de comptes n'a pas de pilier fondamental : la
confiance est plafonnée à 1 et le signal devient « Données insuffisantes ».
Le fait se CONSTATE sur pièce (R11) : chaque entrée cite son dernier dépôt.
"""
import re

import bvc_config as b


def test_chaque_entree_cite_son_dernier_depot_et_sa_piece():
    for t, e in b.SANS_COMPTES.items():
        assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", e["dernier_depot"]), t
        assert e["motif"] and "AMMC" in e["source"], t


def test_dis_et_dlm_sont_sans_comptes_mais_pas_radiees():
    """10/10/2026 : aucune décision de radiation trouvée — ni AMMC, ni Bourse.
    Les deux restent cotées (suspendues), donc hors de VALEURS_RADIEES."""
    for t in ("DIS", "DLM", "IBM"):
        assert b.sans_comptes(t), t
    assert not set(b.SANS_COMPTES) & set(b.VALEURS_RADIEES)
    assert b.SUSPENSIONS.get("DIS") and b.SUSPENSIONS.get("DLM")
