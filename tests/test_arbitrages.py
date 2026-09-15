#!/usr/bin/env python3
"""Deux arbitrages, mesurés plutôt que posés en question.

⚠️ LA MÉTHODE, REPRISE DU LOT MSA
─────────────────────────────────
On ne demande pas « faut-il ? » : on chiffre ce que chaque option coûte, et la
décision se prend sur des nombres. Le dossier propose, il n'instruit pas —
AUCUNE donnée servie n'est modifiée par ce lot.

⚠️ CE QUE CES TESTS SURVEILLENT
Ils ne valident aucun choix. Ils vérifient que la mesure reste HONNÊTE : que
les chiffres avancés se retrouvent dans les données du dépôt, que les options
restent ouvertes, et qu'aucune n'a été appliquée en douce.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parent.parent
DOSSIER = RACINE / "datasets" / "historiques_candidats" / "ARBITRAGES" / "mesures.json"


@pytest.fixture(scope="module")
def mesures():
    return json.loads(DOSSIER.read_text(encoding="utf-8"))


def test_le_dossier_ne_modifie_aucune_donnee_servie(mesures):
    """⚠️ Un dossier d'arbitrage qui appliquerait son propre avis ne serait pas
    un arbitrage."""
    assert mesures["_statut"].startswith("MESURE")
    assert "AUCUNE DONNÉE SERVIE" in mesures["_statut"]
    assert not (RACINE / "datasets" / "corrections_acceptees" / "ARBITRAGES.json").exists()


# ── Arbitrage 1 : la moyenne 200 jours ────────────────────────────────────

def test_les_titres_annonces_sont_bien_ceux_du_cache(mesures):
    """⚠️ Le chiffre du dossier doit se retrouver dans le dépôt, sinon il ne
    décrit rien.

    ⚠️ ET IL BOUGE. Ils étaient 32 à la première mesure, 28 après la correction
    de CIM, HAL, MUT et STK : le recalcul de leur cache a retiré leur fausse
    MA200 au passage. Le test ne fige donc PAS un nombre — il exige que le
    dossier décrive l'état courant du dépôt, et que le mouvement soit expliqué.
    """
    cache = json.loads((RACINE / "pipeline" / "historical_data.json")
                       .read_text(encoding="utf-8"))
    reels = {t for t, v in cache.items()
             if not t.startswith("_")
             and (v.get("n_candles") or 0) < 200 and v.get("ma200") is not None}
    annonces = {c["ticker"] for c in mesures["arbitrage_1_la_moyenne_200_jours"]["titres_concernes"]}
    assert annonces == reels
    assert 0 < len(reels) < 74
    assert "Le compte DESCEND" in mesures["arbitrage_1_la_moyenne_200_jours"]["_le_compte_a_bouge"]
    # ⚠️ Le dossier se remesure par PROGRAMME, pas à la main : je l'ai oublié
    # trois fois et ce test est tombé trois fois.
    assert "mesurer_arbitrages.py" in mesures["arbitrage_1_la_moyenne_200_jours"]["_le_compte_a_bouge"]
    assert (RACINE / "pipeline" / "mesurer_arbitrages.py").exists()


def test_la_ma200_n_entre_dans_aucun_score(mesures):
    """⚠️ C'EST CE QUI REND L'ARBITRAGE FACILE. Si `ma200` pesait dans le
    score, la retirer déplacerait des signaux ; elle n'y entre pas.

    Vérifié sur le CODE, pas sur une affirmation du dossier.
    """
    import ast
    arbre = ast.parse((RACINE / "update_data.py").read_text(encoding="utf-8"))
    for nom in ("calc_score_tech", "compute_v53"):
        fn = next((f for f in ast.walk(arbre)
                   if isinstance(f, ast.FunctionDef) and f.name == nom), None)
        if fn is None:
            continue
        args = {a.arg for a in fn.args.args}
        assert "ma200" not in args, f"{nom} reçoit ma200 : l'arbitrage change les scores"
        noms = {n.id for n in ast.walk(fn) if isinstance(n, ast.Name)}
        assert "ma200" not in noms, f"{nom} lit ma200"


def test_les_ecarts_annonces_sont_recalculables(mesures):
    """Les pires écarts cités — jusqu'à +56 % — doivent se retrouver au centime
    près depuis le cache et le fichier servi."""
    cache = json.loads((RACINE / "pipeline" / "historical_data.json")
                       .read_text(encoding="utf-8"))
    srv = {t["symbol"]: t for t in json.loads(
        (RACINE / "data.json").read_text(encoding="utf-8"))["tickers"]}
    pires = mesures["arbitrage_1_la_moyenne_200_jours"]["_les_pires_ecarts"]
    assert pires, "aucun écart cité : le dossier ne montre plus le problème"
    for c in pires:
        m = cache[c["ticker"]]["ma200"]
        p = srv[c["ticker"]]["price"]
        assert m == c["ma200_affichee"]
        assert round((m / p - 1) * 100, 1) == c["ecart_pct"]
        assert abs(c["ecart_pct"]) > 20


# ── Arbitrage 2 : l'unité du volume ───────────────────────────────────────

def test_les_trois_conventions_coexistent_encore(mesures):
    """⚠️ Si une seule convention subsistait, le constat n'aurait plus d'objet.
    Tant qu'elles coexistent, le volume n'est pas comparable."""
    par_titre = mesures["arbitrage_2_l_unite_du_champ_volume"]["par_titre"]
    conventions = {t: v["convention"] for t, v in par_titre.items()}
    assert set(conventions.values()) == {"TITRES", "MONTANT MAD", "MÉLANGÉE"}
    assert conventions["ADI"] == "MONTANT MAD"
    assert conventions["SMI"] == "TITRES"


def test_l_ignorance_sur_les_autres_titres_est_declaree(mesures):
    """⚠️ 15 titres mesurés sur 80. Le dossier doit dire qu'il ne sait rien des
    65 autres — et surtout ne pas laisser supposer une convention par défaut,
    puisque trois des quinze n'en suivent aucune."""
    a = mesures["arbitrage_2_l_unite_du_champ_volume"]
    # ⚠️ Le nombre de titres non mesurés DESCEND à chaque export reçu. Le test
    # exige la RÈGLE — le dossier dit combien il ignore, et interdit d'en
    # déduire une convention par défaut — pas un chiffre figé qui rougirait à
    # chaque livraison.
    mesures_faites = len(a["par_titre"])
    assert 0 < mesures_faites < 80, "le dossier prétend tout mesurer ou rien"
    txt = a["_ce_qui_n_est_PAS_etabli"]
    assert f"{80 - mesures_faites} titres" in txt, (
        f"le dossier n'annonce pas les {80 - mesures_faites} titres qu'il ignore")
    assert "convention par défaut" in txt


def test_aucune_conversion_de_volume_n_a_ete_appliquee(mesures):
    """⚠️ L'option A — convertir — est déconseillée dans le dossier. Ce test
    vérifie qu'elle n'a pas été appliquée malgré tout : les séries gardent
    l'unité que la mesure leur attribue."""
    assert "Je le déconseille" in \
        mesures["arbitrage_2_l_unite_du_champ_volume"]["_options"]["A_convertir"]
    # ADI reste en montant MAD : ses volumes restent d'un autre ordre de
    # grandeur que ses quantités réelles.
    serie = json.loads((RACINE / "pipeline" / "candles" / "ADI.json")
                       .read_text(encoding="utf-8"))
    recents = [b["v"] for b in serie[-60:] if b["v"]]
    assert max(recents) > 100000, (
        "les volumes d'ADI ont été convertis : l'arbitrage a été tranché sans "
        "être posé")


def test_les_trois_options_restent_ouvertes(mesures):
    """Un dossier d'arbitrage doit présenter les options avec leur COÛT, pas
    une seule habillée en évidence."""
    for cle in ("arbitrage_1_la_moyenne_200_jours", "arbitrage_2_l_unite_du_champ_volume"):
        options = mesures[cle]["_options"]
        assert len(options) == 3
        for nom, texte in options.items():
            assert "Coût" in texte or "coût" in texte, (
                f"{cle}/{nom} ne dit pas ce qu'elle coûte")
