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
        "score_fond": 7.25, "score_tech": 5.2,
        "poids": {"f": 65, "t": 35}, "sig": "ACHETER ★★",
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


def test_sans_pilier_nlp_le_contrat_de_colonnes_tient():
    """⚠️ 29/10/2026 — pilier NLP retiré du moteur. Les colonnes restent (le
    format est positionnel) ; `poids_n` écrit 0, le poids réellement
    appliqué, et `score_nlp` None, même si un vieux flux portait encore une
    note ou un poids NLP."""
    vieux = dict(_titre(), score_nlp=5.0, poids={"f": 52, "t": 20, "n": 28})
    for t in (_titre(), vieux):
        l = sh.ligne_ticker(t)
        assert len(l) == len(sh.COLONNES)
        assert sh.valeur(l, "poids_n") == 0
        assert sh.valeur(l, "score_nlp") is None


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


# ── ⚠️ Le Score BVC au journal — 06/11/2026 (lot 1 du retrait de v5.3) ─────

def _bvc(valeur=72.5, etat="CALCULABLE", version="bvc-score-v1"):
    return {"valeur": valeur, "etat": etat, "couverture_pct": 100, "version": version,
            "facteurs": {}, "motif": None}


def test_les_colonnes_du_score_bvc_sont_ajoutees_en_fin():
    """Attendu écrit à la main : les douze colonnes d'origine restent à leur
    place, les deux nouvelles viennent APRÈS."""
    assert sh.COLONNES[:12] == ["symbol", "v53", "score_fond", "score_tech", "score_nlp",
                                "poids_f", "poids_t", "poids_n", "sig", "conf", "prix", "prix_asof"]
    assert sh.COLONNES[12:] == ["score_bvc", "etat_bvc"]


def test_la_ligne_porte_le_score_bvc_et_son_etat():
    l = sh.ligne_ticker(dict(_titre(), score_bvc=_bvc()))
    assert sh.valeur(l, "score_bvc") == 72.5 and sh.valeur(l, "etat_bvc") == "CALCULABLE"
    assert sh.valeur(l, "v53") == 6.5, "la note v5.3 reste journalisée au lot 1"
    p = sh.ligne_ticker(dict(_titre(), score_bvc=_bvc(None, "PARTIEL")))
    assert sh.valeur(p, "score_bvc") is None and sh.valeur(p, "etat_bvc") == "PARTIEL"


def test_un_titre_qui_n_a_plus_que_son_score_bvc_est_enregistre():
    """⚠️ LE CAS DU LOT 2 : le moteur ne publiera plus `v53`, `poids`, `sig`.
    La ligne doit exister, garder sa longueur, et porter None — jamais un 0
    qui passerait pour un poids appliqué."""
    t = {"symbol": "ATW", "price": 694.6, "score_bvc": _bvc(90.0),
         "_meta": {"confidence": 5, "prix_asof": "2026-11-05"}}
    l = sh.ligne_ticker(t)
    assert l is not None and len(l) == len(sh.COLONNES)
    for c in ("v53", "score_fond", "score_tech", "score_nlp", "poids_f", "poids_t", "poids_n", "sig"):
        assert sh.valeur(l, c) is None, c
    assert sh.valeur(l, "score_bvc") == 90.0 and sh.valeur(l, "conf") == 5
    nc = sh.ligne_ticker(dict(t, score_bvc=_bvc(None, "NON_CALCULABLE")))
    assert nc is not None and sh.valeur(nc, "etat_bvc") == "NON_CALCULABLE"


def test_une_ligne_d_avant_le_score_bvc_se_relit_sans_lever():
    ancienne = ["ADH", 6.5, 7.25, 5.2, None, 65, 35, 0, "ACHETER ★★", 4, 37.2, "2026-09-24"]
    assert sh.valeur(ancienne, "score_bvc") is None and sh.valeur(ancienne, "etat_bvc") is None


def test_le_journal_publie_se_relit_avec_les_nouvelles_colonnes():
    """Relit le VRAI journal : toutes ses lignes, plus courtes, se lisent."""
    j = json.loads((RACINE / "pipeline" / "score_history.json").read_text(encoding="utf-8"))
    n = 0
    for s in j["seances"].values():
        for l in s["tickers"]:
            assert sh.valeur(l, "etat_bvc") in (None, "CALCULABLE", "PARTIEL", "NON_CALCULABLE")
            n += 1
    assert n > 0


def test_le_releve_porte_la_version_du_score_bvc(journal):
    j = sh.enregistrer("2026-11-05", [dict(_titre(sym=s), score_bvc=_bvc()) for s in ("ADH", "ATW")])
    assert j["seances"]["2026-11-05"]["score_bvc_version"] == "bvc-score-v1"
    j = sh.enregistrer("2026-11-05", [dict(_titre(sym="ADH"), score_bvc=_bvc()),
                                      dict(_titre(sym="ATW"), score_bvc=_bvc(version="bvc-score-v2"))])
    assert j["seances"]["2026-11-05"]["score_bvc_version"] == ["bvc-score-v1", "bvc-score-v2"]
    assert json.loads(journal.read_text(encoding="utf-8"))["_colonnes"][-2:] == ["score_bvc", "etat_bvc"]


def test_le_backtest_reproductible_ecarte_une_ligne_sans_note_v53(journal):
    """Le lecteur du journal le plus exposé : une ligne du lot 2 (v53 et sig
    vides) se relit sans lever. ⚠️ Lot 2 (06/11/2026) : elle est écartée DÈS LA
    LECTURE — ce n'est pas une observation de la note v5.3 —, plutôt que
    comptée « signal sans palier » dans les écarts du backtest. Une ligne
    ancienne sans note (sig « Données insuffisantes ») reste lue."""
    sys.path.insert(0, str(RACINE / "pipeline"))
    import backtest_reproductible as br
    t = {"symbol": "ATW", "price": 694.6, "score_bvc": _bvc(90.0),
         "_meta": {"confidence": 5, "prix_asof": "2026-11-05"}}
    sh.enregistrer("2026-11-05", [t])
    ancien = {"symbol": "IBM", "price": 10.0, "v53": None, "sig": "Données insuffisantes", "score_bvc": _bvc(40.0),
              "_meta": {"confidence": 1, "prix_asof": "2026-11-04"}}
    sh.enregistrer("2026-11-04", [ancien])
    notes, _ = br.notes_score_history(journal)
    assert [(n["date"], n["t"], n["sig"]) for n in notes] == [("2026-11-04", "IBM", "Données insuffisantes")]
    assert br.palier(None) is None
