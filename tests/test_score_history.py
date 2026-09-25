#!/usr/bin/env python3
"""Le journal doit survivre à ses propres évolutions — c'est tout son intérêt.

⚠️ CE QUE CES TESTS DÉFENDENT
─────────────────────────────
Un journal en ajout n'a de valeur que sur la durée. Les défauts qui le tuent
ne se voient donc pas le jour où on l'écrit, mais des mois plus tard :

  · une colonne insérée au milieu décale la lecture de TOUT l'historique ;
  · une ligne ancienne, plus courte, lève `IndexError` à la relecture ;
  · un run qui échoue efface ce qui était enregistré ;
  · un run du matin écrase la clôture avec un cours de milieu de séance.

Aucun de ces quatre défauts ne se voit à l'écriture. Tous se payent au moment
précis où le journal devait servir.

⚠️ POURQUOI CE JOURNAL EXISTE
Le 25/09/2026, la décision de geler le pilier NLP n'a pu s'appuyer que sur
13 jours et 194 observations, alors que 87 jours de `v53` étaient disponibles :
les notes par pilier n'étaient publiées que depuis le 12/09. Le backtest ne
peut déterrer que ce qui avait été enterré.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

from pipeline import score_history as sh  # noqa: E402


@pytest.fixture
def journal(tmp_path, monkeypatch):
    """Un journal vierge, hors du dépôt."""
    monkeypatch.setattr(sh, "CHEMIN", tmp_path / "score_history.json")
    return tmp_path / "score_history.json"


def _titre(sym="ADH", v53=6.5, conf=4, asof="2026-09-24"):
    return {
        "symbol": sym, "v53": v53, "price": 37.2,
        "score_fond": 7.25, "score_tech": 5.2, "score_nlp": 5.0,
        "poids": {"f": 65, "t": 35, "n": 0}, "sig": "ACHETER ★★",
        "_meta": {"confidence": conf, "prix_asof": asof},
    }


# ── ⚠️ Le contrat de forme ─────────────────────────────────────────────────

def test_l_ordre_des_colonnes_est_le_contrat():
    """⚠️ LE PIÈGE DU FORMAT POSITIONNEL. Les lignes sont des tableaux : une
    colonne insérée AILLEURS QU'À LA FIN décalerait la lecture de tout
    l'historique déjà écrit, en silence et sans erreur.

    Ce test fige donc le DÉBUT de la liste. Ajouter une colonne à la fin le
    laisse vert ; en insérer une au milieu le fait rougir.

    L'attendu est écrit à la main, jamais dérivé de `COLONNES`.
    """
    assert sh.COLONNES[:5] == [
        "symbol", "v53", "score_fond", "score_tech", "score_nlp"]
    assert sh.COLONNES[5:8] == ["poids_f", "poids_t", "poids_n"]


def test_une_ligne_ancienne_plus_courte_se_relit_sans_lever():
    """⚠️ Le jour où une colonne sera ajoutée, l'historique entier sera plus
    court que `COLONNES`. Le lire par index sans garde lèverait `IndexError`
    sur des mois de journal — et des mois après le changement, quand plus
    personne ne fait le lien."""
    courte = ["ADH", 6.5]           # une ligne d'avant l'ajout des piliers
    assert sh.valeur(courte, "symbol") == "ADH"
    assert sh.valeur(courte, "v53") == 6.5
    assert sh.valeur(courte, "prix_asof") is None   # absente, pas une erreur
    assert sh.valeur(courte, "colonne_inexistante") is None


def test_la_ligne_porte_les_poids_reellement_appliques():
    """⚠️ Pas ceux de référence. Le WeightEngine module par titre : sans les
    poids du jour, la note publiée n'est pas reconstituable après coup, et
    c'est précisément ce qu'on voudra faire."""
    l = sh.ligne_ticker(_titre())
    assert sh.valeur(l, "poids_f") == 65
    assert sh.valeur(l, "poids_n") == 0
    assert sh.valeur(l, "sig") == "ACHETER ★★"


def test_un_titre_sans_note_n_est_pas_enregistre():
    assert sh.ligne_ticker({"symbol": "ADH"}) is None
    assert sh.ligne_ticker({"v53": 6.5}) is None
    assert sh.ligne_ticker("pas un dictionnaire") is None


def test_un_titre_peu_fiable_EST_enregistre():
    """⚠️ C'est même le cas le plus intéressant : il permettra de vérifier
    plus tard que le produit a eu raison de ne pas conclure."""
    l = sh.ligne_ticker(_titre(conf=1))
    assert l is not None and sh.valeur(l, "conf") == 1


# ── ⚠️ Le comportement en ajout ────────────────────────────────────────────

def test_le_dernier_run_de_la_journee_l_emporte(journal):
    """Le run de 15h45 fixe le cours ; celui de 9h30 publiait un cours de
    milieu de séance. Garder le premier ferait mesurer un terminal que
    personne n'a lu à la clôture."""
    sh.enregistrer("2026-09-24", [_titre(v53=5.0)])
    sh.enregistrer("2026-09-24", [_titre(v53=6.5)])
    lignes = sh.lire()["seances"]["2026-09-24"]["tickers"]
    assert len(lignes) == 1
    assert sh.valeur(lignes[0], "v53") == 6.5


def test_une_seance_nouvelle_n_efface_pas_les_precedentes(journal):
    sh.enregistrer("2026-09-23", [_titre(v53=5.0)])
    sh.enregistrer("2026-09-24", [_titre(v53=6.5)])
    assert sh.seances() == ["2026-09-23", "2026-09-24"]


def test_un_run_sans_titre_n_efface_rien(journal):
    """⚠️ Un run qui échoue à collecter ne doit pas vider le journal.
    C'est le jour de la panne qu'on a le plus besoin de l'historique."""
    sh.enregistrer("2026-09-23", [_titre()])
    sh.enregistrer("2026-09-24", [])
    sh.enregistrer("2026-09-24", [{"symbol": "X"}])   # aucune note
    assert sh.seances() == ["2026-09-23"]


def test_un_journal_illisible_ne_fait_pas_echouer_le_run(journal):
    """⚠️ Le journal est une commodité pour plus tard, jamais une dépendance
    du bulletin du matin."""
    journal.write_text("{ ceci n'est pas du json", encoding="utf-8")
    assert sh.lire() == {}
    sh.enregistrer("2026-09-24", [_titre()])          # ne lève pas
    assert sh.seances() == ["2026-09-24"]


# ── ⚠️ L'appariement, la raison d'être du module ───────────────────────────

def test_l_etat_du_marche_est_apparie_a_l_ecriture(journal):
    """⚠️ Rapprocher deux fichiers APRÈS COUP obligerait à supposer qu'ils
    parlent de la même séance. Les écrire ensemble l'établit.

    C'est ce qui rendra mesurable, vers fin octobre, la question laissée
    ouverte : la largeur de marché a-t-elle une valeur prédictive ?
    """
    sh.enregistrer("2026-09-24", [_titre()],
                   {"hausses": 16, "baisses": 42, "ytd_pct": -4.27,
                    "valeurs_traitees": 68, "champ_non_retenu": 1})
    m = sh.lire()["seances"]["2026-09-24"]["marche"]
    assert m["hausses"] == 16 and m["baisses"] == 42 and m["ytd_pct"] == -4.27
    assert "champ_non_retenu" not in m


def test_un_etat_de_marche_absent_ne_bloque_pas(journal):
    """Une séance sans largeur reste enregistrée : les scores valent d'être
    gardés même si l'indice n'a pas répondu."""
    sh.enregistrer("2026-09-24", [_titre()], None)
    assert "marche" not in sh.lire()["seances"]["2026-09-24"]


def test_les_colonnes_sont_declarees_dans_le_fichier(journal):
    """Un fichier positionnel qui ne dit pas ses colonnes est illisible par
    quiconque n'a pas le code sous les yeux."""
    sh.enregistrer("2026-09-24", [_titre()])
    assert json.loads(journal.read_text(encoding="utf-8"))["_colonnes"] == sh.COLONNES


# ── Le branchement dans le moteur ──────────────────────────────────────────

def test_le_moteur_ecrit_le_journal():
    """⚠️ Un module juste qui n'est branché nulle part n'historise rien.
    Lu par l'AST : le fichier cite son propre nom dans ses commentaires."""
    import ast
    arbre = ast.parse((RACINE / "update_data.py").read_text(encoding="utf-8"))
    importe = any(
        isinstance(n, ast.ImportFrom) and (n.module or "").endswith("score_history")
        for n in ast.walk(arbre))
    assert importe, "le moteur n'appelle pas le journal — rien ne s'historise"


def test_le_moteur_date_le_journal_sur_la_seance_pas_sur_le_run():
    """⚠️ Un run du matin porte la clôture de la VEILLE. L'étiqueter du jour
    ferait comparer un score à un rendement décalé d'une séance — un biais
    silencieux, du bon côté par construction."""
    src = (RACINE / "update_data.py").read_text(encoding="utf-8")
    i = src.find("from pipeline.score_history import")
    bloc = src[i:i + 700]
    assert "prix_asof" in bloc, (
        "le journal serait daté de la date du run, pas de la séance des cours")
