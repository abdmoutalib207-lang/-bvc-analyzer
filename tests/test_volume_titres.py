#!/usr/bin/env python3
"""Un volume est un nombre de titres — la règle, et ses quatre violations.

⚠️ CE QUE CES TESTS EMPÊCHENT DE REVENIR
────────────────────────────────────────
Le recoupement des 27 exports de l'opérateur (23/09/2026) a mesuré
**13 636 séances** au volume exprimé en dirhams et **3 019 séances** au volume
valant le COURS. Les deux causes étaient dans le code, et aucune n'était une
faute d'inattention — chacune paraissait raisonnable là où elle était écrite.

  1. Une table faisait de « Volume » (un MONTANT) le volume, et reléguait
     « Quantité échangée » (le nombre de TITRES) en repli. Le repli n'était
     donc jamais atteint.
  2. `if col not in df.columns: df[col] = df["close"]`, appliqué en bloc à
     `high`, `low`, `open` ET `volume`. Juste pour les trois premiers — une
     bougie sans extrêmes est plate. Absurde pour le quatrième.

Ces tests décrivent la RÈGLE, pas l'état d'aujourd'hui. Ce qui les ferait
rougir demain sans que rien ne soit cassé : rien — un en-tête inconnu rend
`None`, ce qui est déjà le comportement attendu.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

from pipeline.volume_titres import (  # noqa: E402
    choisir_colonne, designe_des_titres, designe_un_montant, volume_inconnu,
)


# ── L'ordre de préférence : c'est lui, la correction ───────────────────────

def test_les_titres_l_emportent_sur_le_montant():
    """⚠️ LA GARDE CENTRALE. Les deux colonnes coexistent dans chaque export ;
    tout le défaut n°1 tient dans laquelle on retient."""
    entetes = ["Séance", "Ouverture", "Dernier Cours",
               "Volume (MAD)", "Titres Échangés"]
    assert choisir_colonne(entetes) == "Titres Échangés"


def test_l_ordre_des_colonnes_ne_change_rien():
    """Une colonne de titres gagne où qu'elle soit dans le fichier. Un choix
    fondé sur la position se retournerait au premier export réordonné."""
    assert choisir_colonne(["Titres Échangés", "Volume (MAD)"]) \
        == "Titres Échangés"
    assert choisir_colonne(["Volume (MAD)", "Titres Échangés"]) \
        == "Titres Échangés"


def test_le_cas_casabourse():
    """L'autre source, l'autre graphie — même décision.
    `cumulTitresEchanges` est publié sous « Quantité échangée »."""
    assert choisir_colonne(["Date", "Clôture", "Volume", "Quantité échangée"]) \
        == "Quantité échangée"


def test_volume_seul_est_retenu_faute_de_mieux():
    """⚠️ Le refuser partout viderait les séries des fournisseurs chez qui
    « volume » désigne bien un nombre de titres. Il n'est écarté que lorsqu'une
    colonne de titres existe — et alors la question ne se pose plus."""
    assert choisir_colonne(["date", "close", "volume"]) == "volume"


def test_aucune_colonne_de_volume_rend_none():
    """Et non une colonne au hasard : c'est `None` qui déclenche l'écriture
    d'un volume inconnu, donc zéro."""
    assert choisir_colonne(["date", "close", "high"]) is None
    assert choisir_colonne([]) is None


# ── La reconnaissance des en-têtes ─────────────────────────────────────────

@pytest.mark.parametrize("entete", [
    "Titres Échangés", "titres echanges", "TITRES ECHANGES",
    "Quantité échangée", "cumulTitresEchanges", "Nombre de titres",
    "Shares Traded",
])
def test_ces_entetes_designent_des_titres(entete):
    assert designe_des_titres(entete)


@pytest.mark.parametrize("entete", [
    "Volume (MAD)", "volume mad", "Volume DH", "volumeGlobal",
    "Montant", "Capitaux", "Turnover", "Valeur échangée",
])
def test_ces_entetes_designent_un_montant(entete):
    assert designe_un_montant(entete)


def test_un_montant_n_est_jamais_pris_pour_des_titres():
    """⚠️ Le sens même du défaut n°1. Si « Volume (MAD) » passait pour une
    colonne de titres, l'ordre de préférence ne servirait à rien."""
    for entete in ("Volume (MAD)", "volumeGlobal", "Montant", "Capitaux"):
        assert not designe_des_titres(entete)


def test_la_ponctuation_et_les_accents_ne_comptent_pas():
    """« Titres Échangés » et « titres_echanges » sont le même en-tête. Sans
    normalisation, chaque source imposerait sa graphie."""
    for variante in ("Titres Échangés", "titres_echanges", "TITRES-ECHANGES",
                     "  titres   echanges  "):
        assert designe_des_titres(variante), variante


def test_un_entete_qui_contient_volume_sans_l_etre_n_est_pas_retenu():
    """« vol » est un fragment, pas un sens : `elif "vol" in colonne` attrapait
    « Volume (MAD) ». On exige la correspondance entière d'un motif connu."""
    assert choisir_colonne(["date", "close", "volatilite"]) is None


# ── Un volume inconnu vaut zéro, jamais le cours ───────────────────────────

def test_un_volume_inconnu_vaut_zero():
    """⚠️ Cette fonction d'une ligne porte tout le défaut n°2. Elle existe
    pour qu'on ne puisse pas réécrire `df["volume"] = df["close"]` sans le
    voir."""
    assert volume_inconnu() == 0


# ── Les quatre points d'appel : la règle doit y être BRANCHÉE ──────────────

def _appels_du_module(chemin: Path) -> set[str]:
    """Les fonctions appelées dans ce fichier, lues par l'AST.

    ⚠️ Pas une recherche de texte : ces fichiers CITENT le code fautif dans
    leurs commentaires pour expliquer pourquoi il a disparu. Un test écrit à
    la ligne accuserait l'explication.
    """
    arbre = ast.parse(chemin.read_text(encoding="utf-8"))
    noms = set()
    for n in ast.walk(arbre):
        if isinstance(n, ast.Call):
            f = n.func
            noms.add(f.attr if isinstance(f, ast.Attribute)
                     else getattr(f, "id", ""))
    return noms


@pytest.mark.parametrize("chemin", [
    ".github/scripts/fetch_bvc_history.py",
    "pipeline/collect_history_bvcscrap.py",
])
def test_les_collecteurs_passent_par_la_regle(chemin):
    """⚠️ Une règle juste qu'aucun collecteur n'appelle ne corrige rien. C'est
    exactement ce qui est arrivé à `_colonne_de_volume` : la cause était
    comprise et écrite dans un document, sans jamais atteindre le code."""
    assert "choisir_colonne_volume" in _appels_du_module(RACINE / chemin), (
        f"{chemin} choisit son volume sans passer par la règle commune")


def test_le_cours_n_est_plus_verse_dans_le_volume():
    """⚠️ Le repli `df[col] = df["close"]` doit porter sur `high`, `low` et
    `open` — et sur eux seuls. Ce test lit la LISTE de ce repli dans l'AST :
    y voir réapparaître « volume » est précisément la régression à empêcher."""
    arbre = ast.parse(
        (RACINE / ".github/scripts/fetch_bvc_history.py")
        .read_text(encoding="utf-8"))
    fautives = []
    for n in ast.walk(arbre):
        if not isinstance(n, ast.For) or not isinstance(n.iter, ast.List):
            continue
        valeurs = [e.value for e in n.iter.elts
                   if isinstance(e, ast.Constant) and isinstance(e.value, str)]
        if "volume" not in valeurs:
            continue
        # Une boucle qui nomme `volume` n'est fautive que si elle lui applique
        # le repli sur la clôture.
        corps = ast.dump(ast.Module(body=n.body, type_ignores=[]))
        if "'close'" in corps:
            fautives.append(valeurs)
    assert not fautives, (
        f"le cours est de nouveau versé dans le volume : {fautives}")
