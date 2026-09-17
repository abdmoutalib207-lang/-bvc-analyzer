#!/usr/bin/env python3
"""La séance du 14/09 confrontée au bulletin de l'opérateur, pièce jointe.

⚠️ POURQUOI CE FICHIER, ET CE QU'IL NE PROUVE PAS
─────────────────────────────────────────────────
Le bulletin « Indices » de CDG Capital Bourse est archivé dans
`pipeline/bulletins/`. Ce test le relit à chaque suite et refait la
comparaison, pour qu'une affirmation portée dans un rapport ne repose pas sur
une exécution que personne ne peut rejouer.

⚠️ Ce n'est PAS un contrôle extérieur au fournisseur : nos cours viennent
majoritairement de CDG, même éditeur que ce bulletin. Ce qui est vérifié ici
est la chaîne — traduction des codes, arbitrage par la date, écriture des
chandelles — pas l'exactitude du marché.

⚠️ ET CE TEST DOIT POUVOIR DIRE « JE N'AI RIEN MESURÉ ».
Le 11/09, `comparer()` rendait « 0 écart » contre trois séances différentes
parce qu'elle passait en silence les titres sans chandelle. Le nombre de
comparaisons est donc exigé explicitement, et il est exigé ÉLEVÉ : un jour où
la lecture du PDF se casserait, « 0 écart sur 0 titre » ne passerait pas.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE / "pipeline"))

BULLETIN = RACINE / "pipeline" / "bulletins" / "CDG_indices_2026-09-14.pdf"
SEANCE = "2026-09-14"
# Empreinte de la pièce reçue. Si elle change, ce n'est plus le même document
# et les chiffres ci-dessous ne le décrivent plus.
SHA256 = "5afe25e5af340bd198ac2a390239c547f41a47cecb9b43f6f92bdb8a6421795b"

pdfplumber = pytest.importorskip(
    "pdfplumber",
    reason="déclarée dans requirements.txt, donc présente en CI ; absente, ce "
           "test s'abstient plutôt que de faire échouer une suite locale")


@pytest.fixture(scope="module")
def cotations():
    from parse_cdg_bulletin import parse_cotations
    return parse_cotations(BULLETIN)


def test_la_piece_jointe_est_bien_celle_qui_a_ete_mesuree():
    import hashlib
    assert BULLETIN.exists(), "le bulletin cité doit être joint, pas seulement cité"
    assert hashlib.sha256(BULLETIN.read_bytes()).hexdigest() == SHA256


def test_le_bulletin_se_lit_et_couvre_la_cote(cotations):
    assert len(cotations) == 81
    assert sum(1 for v in cotations.values() if v["cours"]) == 69


def test_la_seance_du_14_concorde_avec_nos_chandelles(cotations):
    """⚠️ Le nombre de comparaisons est exigé, pas seulement le nombre d'écarts.
    « 0 écart » sur 0 titre comparé serait une preuve apparente."""
    from parse_cdg_bulletin import comparer
    ecarts, etat = comparer(cotations, SEANCE)
    assert etat["titres_compares"] >= 60, f"seulement {etat['titres_compares']} comparés"
    assert ecarts == [], f"écarts avec le bulletin : {ecarts[:5]}"
    assert etat["verdict"] == "CONCORDANCE"


def test_le_controle_sait_discriminer_une_autre_seance(cotations):
    """⚠️ CONTRE-ÉPREUVE, et c'est elle qui donne son sens au test précédent.

    Un comparateur qui concorde avec n'importe quelle date ne date rien. Contre
    la séance du 11/09, le même bulletin doit MASSIVEMENT diverger — c'est ce
    qui établit qu'il décrit bien le 14 et non le 11, indépendamment de son
    titre.
    """
    from parse_cdg_bulletin import comparer
    ecarts_11, etat_11 = comparer(cotations, "2026-09-11")
    assert etat_11["titres_compares"] >= 30
    assert etat_11["verdict"] == "DISCORDANCE"
    assert len(ecarts_11) > etat_11["titres_compares"] / 2, (
        "le bulletin concorde aussi avec le 11/09 : il ne date plus rien")


def test_les_codes_officiels_sont_traduits_et_non_lus_tels_quels(cotations):
    """⚠️ Le piège qui a coûté le plus cher à ce projet, figé ici.

    `SNA` est STOKVIS à la Bourse de Casablanca ; Sonasid y est `SID`. Lu sans
    traduction, le bulletin donne 65,60 DH à Sonasid — l'inversion de juin.
    """
    from parse_cdg_bulletin import vers_nos_tickers
    assert cotations["SNA"]["cours"] == 65.6
    assert cotations["SID"]["cours"] == 1900.0
    chez_nous = vers_nos_tickers(cotations)
    assert chez_nous["STK"]["cours"] == 65.6, "Stokvis doit recevoir le SNA officiel"
    assert chez_nous["SNA"]["cours"] == 1900.0, "Sonasid doit recevoir le SID officiel"


def test_cmt_n_a_pas_cote_et_le_bulletin_le_dit_en_creux(cotations):
    """CDG laisse les champs VIDES quand un titre n'a pas coté, au lieu de
    rediffuser la veille. C'est la confirmation extérieure de la variation
    nulle que nous publions sur un titre suspendu depuis le 17/07."""
    cmt = cotations["CMT"]
    assert cmt["cours"] == 0.0 and cmt["qte"] == 0
    assert not cmt["heure"].startswith(("0", "1", "2")), (
        f"une heure de dernier échange sur CMT : {cmt['heure']}")


def test_quatre_titres_sont_cotes_sans_que_nous_ayons_le_moindre_historique(cotations):
    """⚠️ Un fait, pas un correctif. MDP, PPM, SLM et T2S n'ont aucun fichier
    de chandelles : leur RSI publié vaut 50, qui est la valeur NEUTRE par
    défaut et non une mesure. Le bulletin, lui, les cote.

    Ce test tombera le jour où l'un d'eux recevra un historique — et ce sera
    une bonne nouvelle, à traiter en retirant son nom d'ici.

    ⚠️ C'EST ARRIVÉ LE 15/09/2026 : T2S a reçu ses 30 séances et a quitté la
    liste. Son nom est retiré ici, délibérément, plutôt que d'assouplir
    l'égalité en « au moins trois » — chaque départ doit rester une
    modification consciente, pas un effet de bord.
    """
    from parse_cdg_bulletin import vers_nos_tickers
    chez_nous = vers_nos_tickers(cotations)
    sans_histoire = sorted(
        t for t, v in chez_nous.items()
        if v["cours"] and not (RACINE / "pipeline" / "candles" / f"{t}.json").exists())
    assert sans_histoire == ["MDP", "SLM"]
    # T2S est désormais servi avec son historique : c'est ce que ce bulletin
    # avait permis d'établir, et ce qui a été fait le soir même.
    assert (RACINE / "pipeline" / "candles" / "T2S.json").exists()
    assert chez_nous["T2S"]["cours"] == 225.0
    # ⚠️ ET PROMOPHARM A QUITTÉ LA LISTE LE 17/09/2026, par le même chemin :
    # Abd Moutalib a fourni son export 3 ans. Le titre passe de ZÉRO bougie à
    # 735, et son RSI cesse d'être le 50 par défaut que ce test dénonçait.
    assert (RACINE / "pipeline" / "candles" / "PPM.json").exists()
