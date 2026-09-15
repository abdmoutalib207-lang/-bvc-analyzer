#!/usr/bin/env python3
"""BMCE écrit parfois un CODE là où on attend un NOM — et le code ment.

⚠️ LE DÉFAUT MESURÉ LE 15/09/2026
─────────────────────────────────
Le moteur a publié Sonasid à **64,65 DH**. Sonasid cotait 1 900 la veille ;
64,65 est le cours de **Stokvis Nord Afrique**, ce jour-là, à la minute près.

La ligne fautive vient du tableau de BMCE Capital Bourse, dont la première
colonne porte tantôt une raison sociale (« Addoha », « Maroc Telecom »),
tantôt un CODE officiel BVC. Ce jour-là elle portait « SNA » — qui désigne
STOKVIS à la Bourse de Casablanca, et SONASID chez nous.

`_construire_alias()` inscrit chaque ticker du projet comme son propre alias :
la chaîne « SNA » s'appariait donc à NOTRE SNA. C'est l'inversion documentée
depuis le 10/08 (R3, `IDB_TICKER_MAP`), revenue par la porte du NOM au lieu de
celle de l'URL.

⚠️ CE QUE CES TESTS NE FONT PAS
───────────────────────────────
Ils n'appellent jamais le réseau, et ils n'écrivent pas l'attendu en
réutilisant la fonction éprouvée : le cours attendu, le ticker attendu et le
ticker interdit sont écrits en toutes lettres.
"""

from __future__ import annotations

import pytest


def _ligne(nom, heure, ouverture, cours, variation, quantite, volume, haut, bas):
    return ("<tr>" + "".join(f"<td>{c}</td>" for c in (
        nom, heure, ouverture, cours, variation, quantite, volume, haut, bas))
        + "</tr>")


PAGE = "<table>" + "".join([
    # Le piège : le libellé est le code officiel BVC de STOKVIS.
    _ligne("SNA", "11:37:59", "64,50", "65,40", "-0,30%", "2 543",
           "166 312,20", "65,58", "64,50"),
    # Une raison sociale ordinaire, qui doit continuer de s'apparier.
    _ligne("Addoha", "15:28:03", "34,50", "34,40", "-0,43%", "120 000",
           "4 128 000,00", "34,60", "34,20"),
    # Un code qui, lui, désigne bien la même société des deux côtés.
    _ligne("BCP", "15:29:41", "245,00", "245,80", "+0,33%", "3 100",
           "761 980,00", "246,00", "244,50"),
]) + "</table>"

# Libellés officiels CDG, tels que le moteur les construit : raison sociale
# normalisée → NOTRE symbole. Aucun code n'y figure — c'est bien pour cela que
# la passe suivante décidait seule du sort de « SNA ».
LIBELLES = {"SONASID": "SNA", "STOKVISNORDAFRIQUE": "STK",
            "DOUJAPROMADDOHA": "ADH", "BANQUECENTRALEPOPULAIRE": "BCP"}


@pytest.fixture()
def lu(ud):
    return ud._bmce_parser(PAGE, LIBELLES)


def test_le_cours_de_stokvis_va_a_stokvis(lu):
    """65,40 DH est le cours de Stokvis. Il doit atterrir sur STK."""
    assert "STK" in lu, "le libellé « SNA » n'a pas été traduit en Stokvis"
    assert lu["STK"]["price"] == 65.40


def test_sonasid_ne_recoit_rien_de_cette_ligne(lu):
    """⚠️ Le cœur du défaut. Sonasid vaut 1 900 DH ; lui attribuer 65,40
    affiche une chute de 96,6 % qui n'a jamais eu lieu."""
    assert "SNA" not in lu, (
        f"Sonasid a reçu {lu.get('SNA')} — c'est la cotation de Stokvis")


def test_une_raison_sociale_continue_de_s_apparier(lu):
    """La correction ne doit rien coûter à l'appariement par nom : BMCE écrit
    « Addoha » là où le libellé officiel dit « DOUJA PROM ADDOHA »."""
    assert lu["ADH"]["price"] == 34.40


def test_un_code_qui_designe_la_meme_societe_reste_inchange(lu):
    """Huit des neuf codes relevés le 15/09 coïncident avec notre symbole.
    La traduction doit les laisser exactement où ils étaient."""
    assert lu["BCP"]["price"] == 245.80


def test_le_controle_sait_echouer(ud):
    """⚠️ Contre-épreuve. Un test qui ne peut pas rougir ne prouve rien :
    on neutralise la table des codes et on exige que le défaut revienne."""
    sauve = dict(ud._CODES_OFFICIELS_BVC)
    ud._CODES_OFFICIELS_BVC.clear()
    try:
        sans = ud._bmce_parser(PAGE, LIBELLES)
    finally:
        ud._CODES_OFFICIELS_BVC.clear()
        ud._CODES_OFFICIELS_BVC.update(sauve)
    assert sans.get("SNA", {}).get("price") == 65.40, (
        "sans la traduction des codes, Sonasid devrait recevoir 65,40 — "
        "si ce n'est plus le cas, ce fichier ne teste plus le défaut qu'il "
        "prétend couvrir")
    assert "STK" not in sans


def test_la_table_des_codes_traduit_bien_l_inversion_connue(ud):
    """Les deux codes que le projet a déjà payés au prix fort (10/08/2026) :
    `SNA` officiel = Stokvis, `SID` officiel = Sonasid."""
    assert ud._CODES_OFFICIELS_BVC["SNA"] == "STK"
    assert ud._CODES_OFFICIELS_BVC["SID"] == "SNA"
