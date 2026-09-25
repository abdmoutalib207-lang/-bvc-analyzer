#!/usr/bin/env python3
"""Collecter l'état du marché — et ne pas confondre « zéro » avec « on ne sait pas ».

⚠️ LE PIÈGE PRINCIPAL DE CE MODULE
──────────────────────────────────
Une séance sans aucune hausse existe : c'est un marché qui recule en bloc, et
c'est une information grave. Une séance dont la source n'a pas servi le champ
n'en est pas une.

Les confondre ferait passer une panne de fournisseur pour un krach — et, dans
l'autre sens, ferait manquer le krach quand il arrivera. D'où `None` partout où
la donnée manque, et jamais `0`.

⚠️ LE SECOND PIÈGE EST DÉJÀ ARRIVÉ AILLEURS
`masi_history` appliquait la règle « ajout seulement » : la PREMIÈRE valeur du
jour était gravée, donc celle du run de midi. Trois séances sur cinq en sont
sorties fausses, jusqu'à 256 points — 1,4 %. La même règle ici produirait le
même résultat, et ces tests l'interdisent.

⚠️ CE MODULE NE TOUCHE À AUCUN SCORE, et un test le vérifie. Faire entrer la
largeur de marché dans la note exige un backtesting et un accord (R8) — et un
historique qui n'existe pas encore.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))
sys.path.insert(0, str(RACINE / "pipeline"))

from marche_history import (  # noqa: E402
    CHAMPS, dernier, enregistrer, extraire, largeur, profondeur,
)

# La charge utile réelle du 24/09/2026, réduite aux champs qui comptent.
REPONSE = {
    "Cours": 17869.0571, "VariationP": -0.95, "VariationV": -171.6711,
    "NbrHausse": 16, "NbrBaisse": 42, "NbrInchange": 10, "NbrValeur": 68,
    "NbrTransaction": 2768, "QteEchange": 803714, "Volume": 199725886.19,
    "PlusBas": 17866.8157, "PlusHaut": 18220.7705, "CoursVeille": 18040.7282,
    "PlusHautAnnee": 19554.9716, "PlusBasAnnee": 16399.2537,
    "VariationAnneeP": -4.27, "CoursPremiereCotation": 18846.3502,
    "Capitalisation": 1051659325158.98,
    # des champs servis que l'on ne garde PAS
    "Etat": "NAUT", "PTO": "", "DateJour": "24/09/2026 23:19:16",
}


def _f(tmp_path):
    return tmp_path / "marche_history.json"


# ── ⚠️ Zéro n'est pas « on ne sait pas » ───────────────────────────────────

def test_un_champ_absent_devient_none_et_non_zero():
    """LA GARDE CENTRALE. Une source muette ne doit pas ressembler à un marché
    où rien ne monte — ce serait prendre une panne pour un krach."""
    e = extraire({"Cours": 17869.0571})
    assert e["hausses"] is None
    assert e["baisses"] is None
    assert e["ytd_pct"] is None


def test_zero_hausse_reste_zero():
    """Le cas voisin, et il est réel : un marché où tout recule. Le rendre
    `None` effacerait une séance qui mérite précisément d'être vue."""
    e = extraire({**REPONSE, "NbrHausse": 0})
    assert e["hausses"] == 0


def test_les_comptages_sont_des_entiers():
    """Un nombre de hausses ne vaut pas 16,0 — et une série qui mélange les
    deux écritures se compare mal à elle-même."""
    e = extraire(REPONSE)
    for k in ("hausses", "baisses", "inchanges", "valeurs_traitees",
              "transactions", "titres_echanges"):
        assert isinstance(e[k], int), f"{k} n'est pas un entier"


def test_une_reponse_illisible_ne_fait_pas_tomber_la_collecte():
    assert extraire(None) == {}
    assert extraire("pas un dict") == {}


# ── ⚠️ Le YTD que le moteur croyait incalculable ───────────────────────────

def test_le_ytd_est_servi_par_la_source():
    """Le WeightEngine porte : « le projet ne stocke aucun historique de
    l'indice, donc le YTD réel n'est pas calculable aujourd'hui ». Deux
    régimes de pondération en sont neutralisés depuis l'origine.

    Il était servi, simplement pas lu."""
    assert extraire(REPONSE)["ytd_pct"] == -4.27
    assert extraire(REPONSE)["cloture_annee_precedente"] == 18846.3502


# ── La largeur de marché ───────────────────────────────────────────────────

def test_la_largeur_se_lit_sur_les_trois_comptages():
    """16 hausses, 42 baisses, 10 inchangées sur 68 : (16−42)/68 = −0,382."""
    # ⚠️ Le module arrondit à quatre décimales — la tolérance doit suivre la
    # précision PUBLIÉE, pas celle du calcul. Un test plus strict que la donnée
    # rougit sur un module juste.
    l = largeur(extraire(REPONSE))
    assert abs(l["ratio"] - (16 - 42) / 68) < 1e-4
    assert "marché en repli" in l["_lecture"]


def test_les_inchanges_comptent_dans_le_denominateur():
    """⚠️ Les exclure gonflerait le ratio des séances calmes : un marché où
    rien ne bouge n'est pas un marché haussier."""
    sans = largeur({"hausses": 10, "baisses": 5, "inchanges": 0})
    avec = largeur({"hausses": 10, "baisses": 5, "inchanges": 55})
    assert avec["ratio"] < sans["ratio"]


def test_une_largeur_non_servie_ne_produit_pas_de_ratio():
    assert largeur({"hausses": None, "baisses": None})["ratio"] is None
    assert largeur({"hausses": 0, "baisses": 0, "inchanges": 0})["ratio"] is None


# ── ⚠️ La séance du jour se rafraîchit ─────────────────────────────────────

def test_la_seance_du_jour_se_rafraichit(tmp_path):
    """⚠️ L'ERREUR DÉJÀ COMMISE AILLEURS. `masi_history` gravait la première
    valeur du jour — donc celle du run de midi — et trois séances sur cinq en
    sont sorties fausses, jusqu'à 256 points d'écart."""
    f = _f(tmp_path)
    midi = {**REPONSE, "Cours": 18125.2807, "NbrHausse": 30, "NbrBaisse": 20}
    assert enregistrer(midi, "2026-09-24", f, aujourd_hui="2026-09-24") is True
    assert enregistrer(REPONSE, "2026-09-24", f, aujourd_hui="2026-09-24") is True
    s = json.loads(f.read_text())["seances"]["2026-09-24"]
    assert s["cours"] == 17869.0571
    assert s["hausses"] == 16, "la largeur de clôture doit remplacer celle de midi"


def test_une_seance_passee_est_gravee(tmp_path):
    f = _f(tmp_path)
    assert enregistrer(REPONSE, "2026-09-24", f, aujourd_hui="2026-09-25") is True
    autre = {**REPONSE, "Cours": 99999.0}
    assert enregistrer(autre, "2026-09-24", f, aujourd_hui="2026-09-25") is False
    assert json.loads(f.read_text())["seances"]["2026-09-24"]["cours"] == 17869.0571


def test_le_meme_run_rejoue_n_ecrit_rien(tmp_path):
    """L'écriture reste idempotente : le quota de publication de Pages est la
    ressource rare du projet."""
    f = _f(tmp_path)
    assert enregistrer(REPONSE, "2026-09-24", f, aujourd_hui="2026-09-24") is True
    assert enregistrer(REPONSE, "2026-09-24", f, aujourd_hui="2026-09-24") is False


def test_une_reponse_sans_cours_n_est_pas_enregistree(tmp_path):
    f = _f(tmp_path)
    assert enregistrer({"NbrHausse": 16}, "2026-09-24", f) is False
    assert profondeur(f) == 0


def test_le_dernier_etat_porte_sa_largeur(tmp_path):
    f = _f(tmp_path)
    enregistrer(REPONSE, "2026-09-24", f, aujourd_hui="2026-09-24")
    d = dernier(f)
    assert d["date"] == "2026-09-24"
    assert d["largeur"]["ratio"] is not None


# ── ⚠️ R8 : rien n'entre dans le score ─────────────────────────────────────

def test_le_module_ne_touche_a_aucun_score():
    """Il collecte et il historise. Faire entrer la largeur dans la note
    exigerait un backtesting et un accord — et un historique qui n'existe pas
    encore. On ne peut pas mesurer ce qu'on n'a pas enregistré."""
    import ast
    arbre = ast.parse((RACINE / "pipeline" / "marche_history.py")
                      .read_text(encoding="utf-8"))
    for n in ast.walk(arbre):
        if isinstance(n, ast.Constant) and isinstance(n.value, str):
            assert n.value not in {"v53", "bvc", "poids", "score_nlp",
                                   "score_tech", "score_fond"}, (
                f"le module manipule « {n.value} »")


def test_les_champs_decoratifs_ne_sont_pas_stockes():
    """⚠️ On ne garde pas les trente champs. `Etat`, `PTO`, `DateJour` ne
    décrivent pas la séance, et une série qui garde tout finit par ne plus
    rien dire."""
    e = extraire(REPONSE)
    for indesirable in ("Etat", "PTO", "DateJour"):
        assert indesirable not in e
    assert set(e) == set(CHAMPS)
