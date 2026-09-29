"""La liste des dépôts du régulateur — lue, rattachée, jamais devinée.

Extraits RÉELS de la page https://www.ammc.ma/fr/communiques-presse-emetteurs
relevés le 29/09/2026.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pipeline.depots_ammc import (depots_par_ticker, fusionner,  # noqa: E402
                                  parser_page, resoudre_emetteur)
from pipeline.fondamentaux_frais import par_ticker  # noqa: E402

LI = ('<li class="actualites-row"><div class="views-field views-field-field-date"><h6 class="field-content label">'
      '<time datetime="2026-09-29T16:25:28Z">29/09/2026</time> </h6></div><div class="views-field views-field-title">'
      '<span class="field-content">CMGP Group - CP relatif aux résultats du 1er semestre 2026</span></div>'
      '<div class="views-field views-field-field-fichier-joindre- margin-25"><div class="field-content">'
      '<span class="file"><a href="/sites/default/files/CP_CMGP_S1_26.pdf" type="application/pdf">CP_CMGP_S1_26.pdf</a>'
      '</span></div></div></li>')


def test_une_entree_de_la_liste():
    e = parser_page("<ul>" + LI + "</ul>")
    assert e == [{"date": "2026-09-29",
                  "titre": "CMGP Group - CP relatif aux résultats du 1er semestre 2026",
                  "url": "https://www.ammc.ma/sites/default/files/CP_CMGP_S1_26.pdf"}]


@pytest.mark.parametrize("nom,ticker", [
    ("CMGP Group", "CMGP"),       # nom normalisé exact
    ("SBM", "SBS"),               # code officiel BVC : SBM est NOTRE SBS
    ("SMI", "SMI"),
    ("Marsa Maroc", "MSA"),       # alias relevé sur la liste
    ("LabelVie", "LBV"),
    ("Eqdom", "EQD"),
])
def test_rattachement(nom, ticker):
    assert resoudre_emetteur(nom) == ticker


@pytest.mark.parametrize("nom", ["OCP", "ADM", "TMPA", "Saham Bank", "Crédit Agricole du Maroc"])
def test_un_emetteur_d_obligations_n_est_pas_un_titre(nom):
    assert resoudre_emetteur(nom) is None


def test_le_depot_le_plus_recent_et_l_avertissement():
    e = [{"date": "2026-09-20", "titre": "Promopharm - Résultats 2025", "url": "a"},
         {"date": "2026-09-25", "titre": "Promopharm - CP relatif à la publication d'un profit warning sur les résultats du 1er semestre 2026", "url": "b"},
         {"date": "2026-09-28", "titre": "Promopharm - Convocation à l'assemblée", "url": "c"}]
    d = depots_par_ticker(e)["PPM"]
    assert d["url"] == "b" and d["avertissement"] is True


def test_le_cache_accumule_sans_doublon():
    a = [{"date": "2026-09-28", "titre": "x", "url": "u1"}]
    n = [{"date": "2026-09-29", "titre": "y", "url": "u2"}, {"date": "2026-09-28", "titre": "x", "url": "u1"}]
    assert [z["url"] for z in fusionner(a, n)] == ["u2", "u1"]


def test_le_detecteur_voit_ce_que_les_actualites_ont_manque():
    """Le cas du 29/09 : CMGP a déposé, aucune actualité étiquetée ne le dit."""
    titres = [{"symbol": "CMGP", "_meta": {"fond_asof": "2026-06-18"}}]
    assert par_ticker(titres, []) == {}
    r = par_ticker(titres, [], {"CMGP": {"date": "2026-09-29", "titre": "t", "url": "u"}})
    assert r["CMGP"]["retard_jours"] == 103


def test_des_indicateurs_trimestriels_ne_sont_pas_des_comptes():
    """RDS, 29/09 : un chiffre d'affaires trimestriel, pas un résultat."""
    e = [{"date": "2026-09-29", "titre": "RDS - CP relatif aux indicateurs du 2ème trimestre 2026", "url": "u"}]
    assert depots_par_ticker(e) == {}
