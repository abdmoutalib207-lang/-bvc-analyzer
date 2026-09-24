#!/usr/bin/env python3
"""Apparier un émetteur de l'AMMC à notre ticker — sans jamais le deviner.

⚠️ LE RISQUE DE CE MODULE EST UNE VIEILLE CONNAISSANCE DU PROJET
────────────────────────────────────────────────────────────────
Rapprocher deux référentiels par ressemblance de noms, c'est la manœuvre qui a
fait hériter Sonasid des cotations de Stokvis — 74 DH au lieu de 2 000, avec
les volumes de l'autre société. Le projet s'en est remis, et la règle qui en
reste tient en une ligne : **vérifier l'identité effectivement retournée par le
fournisseur, jamais la supposer**.

D'où deux voies, et aucune approximation entre les deux :

  1. le CODE entre parenthèses, que l'émetteur pose lui-même — « Alliances
     Développement Immobilier (ADI) ». C'est une identité déclarée ;
  2. à défaut, le nom normalisé, en correspondance ENTIÈRE.

Un nom qui ressemble sans correspondre est refusé. Une société non appariée
n'est pas une perte : c'est une ligne à traiter à la main, et elle est comptée.

⚠️ CE QUE CES TESTS NE PEUVENT PAS GARANTIR
Que l'AMMC et nous employons un code dans le même sens. Le projet a déjà vu un
opérateur appeler `SNA` ce que nous appelons `STK`. Le contrôle sur
`TICKERS_ALL` écarte les codes hors de notre univers ; il ne détecte pas une
collision de sens. Aucun test hors ligne ne le peut — seul un recoupement de
chiffres le ferait.
"""

from __future__ import annotations

import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))
sys.path.insert(0, str(RACINE / "pipeline"))

from ammc_etats_financiers import (  # noqa: E402
    code_entre_parentheses, collecter, normaliser, par_societe, parser_page,
    resoudre,
)

LIGNE = ('<tr><td>{nom}</td><td>{an}</td><td>{ty}</td>'
         '<td><a href="/fr/espace-emetteurs/etats-financiers/{slug}">voir</a>'
         '</td></tr>')


def _page(*lignes):
    return "<table>" + "".join(
        LIGNE.format(nom=n, an=a, ty=t, slug=s) for n, a, t, s in lignes
    ) + "</table>"


# ── ⚠️ L'identité déclarée ─────────────────────────────────────────────────

def test_le_code_entre_parentheses_fait_foi():
    """C'est la meilleure preuve disponible : l'émetteur pose son code
    lui-même dans son nom déposé."""
    assert code_entre_parentheses("Alliances Développement Immobilier (ADI)") == "ADI"
    assert code_entre_parentheses("Bank of Africa - Groupe BMCE (BOA)") == "BOA"


def test_un_code_hors_de_notre_univers_est_refuse():
    """⚠️ L'AMMC couvre aussi des émetteurs qui ne sont pas des actions de la
    cote : l'Agence Nationale des Ports émet des obligations. Accepter son
    code créerait un ticker qui n'existe pas chez nous."""
    assert code_entre_parentheses("Agence Nationale des Ports (ANP)") is None
    assert code_entre_parentheses("Crédit Agricole du Maroc (CAM)") is None


def test_un_code_ailleurs_que_dans_les_parentheses_finales_ne_compte_pas():
    """Trois lettres majuscules au milieu d'un nom ne sont pas une
    déclaration. Sans cette exigence, « BCP Securities Ltd » serait apparié."""
    assert code_entre_parentheses("(ADI) Alliances") is None
    assert code_entre_parentheses("Société ADI Immobilier") is None


# ── La seconde voie : le nom, en correspondance entière ────────────────────

def test_un_nom_identique_apparie():
    assert resoudre("MAROC TELECOM") == "IAM"


def test_la_casse_et_les_accents_ne_comptent_pas():
    assert resoudre("maroc telecom") == "IAM"
    assert resoudre("Maroc Télécom") == "IAM"


def test_la_forme_sociale_ne_bloque_pas():
    """« TGCC SA » et « TGCC S.A » désignent la même société."""
    assert resoudre("TGCC S.A") == "TGCC"


def test_un_nom_qui_ressemble_sans_correspondre_est_refuse():
    """⚠️ LA GARDE CENTRALE. « Crédit du Maroc » et « Crédit Eqdom » partagent
    un mot ; les marier donnerait à l'un les comptes de l'autre."""
    assert resoudre("Crédit") is None
    assert resoudre("Crédit du") is None


def test_un_nom_inconnu_rend_none_et_non_un_voisin():
    assert resoudre("Société Inexistante du Maroc") is None
    assert resoudre("") is None


def test_le_code_prime_sur_le_nom():
    """Quand les deux voies existent, la déclarée gagne : elle vient de
    l'émetteur, l'autre d'un rapprochement que nous faisons."""
    assert resoudre("Un Nom Qui Ne Correspond À Rien (ADI)") == "ADI"


# ── La lecture de la liste ─────────────────────────────────────────────────

def test_une_ligne_est_lue_entierement():
    e = parser_page(_page(("MAROC TELECOM", "2026", "Rapports 1er semestre",
                           "maroc-telecom-rfs-juin-2026")))
    assert len(e) == 1
    assert e[0]["emetteur_ammc"] == "MAROC TELECOM"
    assert e[0]["annee"] == "2026"
    assert e[0]["type"] == "Rapports 1er semestre"
    assert e[0]["fiche"].endswith("/maroc-telecom-rfs-juin-2026")


def test_une_ligne_sans_lien_est_ignoree():
    """Les en-têtes de tableau n'ont pas de fiche, et ne sont pas des
    rapports."""
    assert parser_page("<tr><td>Émetteur</td><td>Année</td></tr>") == []


def test_une_page_vide_ne_fait_pas_tomber_la_lecture():
    assert parser_page("") == []
    assert parser_page("<html><body>rien</body></html>") == []


# ── La collecte, sans réseau ───────────────────────────────────────────────

def test_la_collecte_s_arrete_sur_une_page_vide():
    """⚠️ Insister sur une liste finie — ou sur un site qui a changé de
    forme — n'apporte rien et martèle un service public."""
    pages = {0: _page(("A (ADI)", "2026", "Rapports 1er semestre", "a"))}

    def faux(url):
        import re
        n = int(re.search(r"page=(\d+)", url).group(1)) if "page=" in url else 0
        return pages.get(n, "")

    assert len(collecter(pages=30, get=faux)) == 1


def test_les_doublons_ne_sont_comptes_qu_une_fois():
    """Le site rend deux liens par ligne — un sur le titre, un sur l'icône."""
    p = _page(("MAROC TELECOM", "2026", "Rapports 1er semestre", "a"),
              ("MAROC TELECOM", "2026", "Rapports 1er semestre", "a"))
    assert len(collecter(pages=1, get=lambda _u: p)) == 1


def test_une_erreur_reseau_rend_ce_qui_a_ete_lu():
    """⚠️ Une collecte partielle vaut mieux qu'une exception : on publie ce
    qu'on a pu lire, et le compte dit combien."""
    def faux(url):
        if "page=" in url:
            raise OSError("coupure")
        return _page(("A (ADI)", "2026", "Rapports 1er semestre", "a"))

    assert len(collecter(pages=10, get=faux)) == 1


# ── Le classement par société ──────────────────────────────────────────────

def test_le_plus_recent_l_emporte():
    e = [{"emetteur_ammc": "X (ADI)", "annee": "2024", "type": "Rapports annuels",
          "fiche": "u1"},
         {"emetteur_ammc": "X (ADI)", "annee": "2026", "type": "Rapports annuels",
          "fiche": "u2"}]
    assert par_societe(e)["par_ticker"]["ADI"]["annee"] == "2026"


def test_a_annee_egale_le_semestriel_est_plus_recent():
    """Le semestriel d'un exercice paraît après l'annuel de l'exercice
    précédent, et porte des chiffres plus frais."""
    e = [{"emetteur_ammc": "X (ADI)", "annee": "2026", "type": "Rapports annuels",
          "fiche": "u1"},
         {"emetteur_ammc": "X (ADI)", "annee": "2026",
          "type": "Rapports 1er semestre", "fiche": "u2"}]
    assert par_societe(e)["par_ticker"]["ADI"]["type"] == "Rapports 1er semestre"


def test_les_non_apparies_sont_comptes_et_non_tus():
    """⚠️ Une société non appariée n'est pas absente de l'AMMC : elle est
    absente de NOTRE table de noms. C'est une information sur nous."""
    e = [{"emetteur_ammc": "SOCIÉTÉ INCONNUE", "annee": "2026",
          "type": "Rapports annuels", "fiche": "u"}]
    r = par_societe(e)
    assert r["par_ticker"] == {}
    assert r["non_apparies"] == {"SOCIÉTÉ INCONNUE": 1}


def test_la_normalisation_est_stable():
    assert normaliser("Maroc Télécom") == normaliser("MAROC TELECOM")
    assert normaliser("TGCC S.A") == normaliser("TGCC SA")
    assert normaliser("") == ""
