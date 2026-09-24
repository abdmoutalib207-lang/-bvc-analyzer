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
    a = mesures["arbitrage_1_la_moyenne_200_jours"]
    if reels:
        assert 0 < len(reels) < 74
        assert not a.get("_resolu", False)
    else:
        assert a.get("_resolu") is True, (
            "plus aucune fausse MA200 courte : le dossier doit déclarer le constat résolu")
    assert "Le compte DESCEND" in a["_le_compte_a_bouge"]
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
    if not pires:
        assert mesures["arbitrage_1_la_moyenne_200_jours"].get("_resolu") is True
        return
    for c in pires:
        m = cache[c["ticker"]]["ma200"]
        assert m == c["ma200_affichee"], (
            f"{c['ticker']} : le dossier cite une MA200 de {c['ma200_affichee']}, "
            f"le cache en porte {m}")

        # ⚠️ L'ÉCART SE RECALCULE DEPUIS LA MESURE, PAS DEPUIS LE COURS DU JOUR.
        # La mesure porte le cours qu'elle a utilisé ; le cours, lui, bouge
        # chaque séance. Ce test recalculait avec le prix servi aujourd'hui et
        # tombait donc dès le lendemain — mesuré le 16/09 : 25,7 contre 28,6
        # annoncés sur CAR, simplement parce que le titre était passé de 20,00
        # à 20,46. Et comme ce fichier est dans la garde bloquante
        # d'`update_bvc`, il n'échouait pas tout seul : il EMPÊCHAIT LA
        # PUBLICATION de la séance.
        assert round((c["ma200_affichee"] / c["cours"] - 1) * 100, 1) == c["ecart_pct"], (
            f"{c['ticker']} : la mesure ne tient pas debout toute seule")

        # Et le problème doit être ENCORE LÀ aujourd'hui, sinon le dossier
        # décrit un passé. Le seuil est plus bas que celui du relevé : un cours
        # qui se rapproche de sa moyenne réduit l'écart sans rien régler.
        aujourd_hui = round((m / srv[c["ticker"]]["price"] - 1) * 100, 1)
        assert abs(aujourd_hui) > 10, (
            f"{c['ticker']} : l'écart n'est plus que de {aujourd_hui} % — "
            "régénérer le dossier avec `python pipeline/mesurer_arbitrages.py "
            "--ecrire` plutôt que de laisser un constat périmé")
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
    """⚠️ L'option A — CONVERTIR — reste interdite, et ce test la garde.

    Le dossier la déconseille en une phrase qui dit tout : « réécrire ~670
    séances sur la foi d'une convention DÉDUITE et jamais déclarée par le
    fournisseur ». Appliquer un facteur à des volumes dont on suppose l'unité,
    c'est inventer des chiffres et leur donner l'apparence d'une correction.

    ⚠️ MAIS SUBSTITUER LA SÉRIE DE L'OPÉRATEUR N'EST PAS CONVERTIR, ET LE TEST
    CONFONDAIT LES DEUX.
    Le 24/09, l'export « Cours » d'ADI est arrivé. Sa colonne « Titres
    Échangés » DÉCLARE l'unité au lieu de la laisser deviner. La série a donc
    été remplacée, pas convertie — et le test a rougi sur une opération qu'il
    n'avait pas à interdire.

    La distinction se lit dans le dépôt, elle ne se décrète pas ici : un titre
    dont `datasets/historiques_importes/` porte la réception a été instruit
    SUR PIÈCE. Pour les autres, l'interdiction tient entière.
    """
    assert "Je le déconseille" in \
        mesures["arbitrage_2_l_unite_du_champ_volume"]["_options"]["A_convertir"]

    receptions = RACINE / "datasets" / "historiques_importes"
    serie = json.loads((RACINE / "pipeline" / "candles" / "ADI.json")
                       .read_text(encoding="utf-8"))
    recents = [b["v"] for b in serie[-60:] if b["v"]]

    if (receptions / "ADI.json").exists():
        # Instruit sur pièce : les volumes DOIVENT désormais être des titres,
        # donc d'un ordre de grandeur bien inférieur au montant en dirhams.
        assert max(recents) < 100000, (
            "ADI porte une réception d'historique, mais ses volumes gardent "
            "l'ordre de grandeur d'un montant en dirhams — l'import n'a pas "
            "pris")
    else:
        assert max(recents) > 100000, (
            "les volumes d'ADI ont été convertis : l'arbitrage a été tranché "
            "sans être posé, et sans export pour l'établir")


def test_les_trois_options_restent_ouvertes(mesures):
    """Un dossier d'arbitrage doit présenter les options avec leur COÛT, pas
    une seule habillée en évidence."""
    for cle in ("arbitrage_1_la_moyenne_200_jours", "arbitrage_2_l_unite_du_champ_volume"):
        options = mesures[cle]["_options"]
        assert len(options) == 3
        for nom, texte in options.items():
            assert "Coût" in texte or "coût" in texte, (
                f"{cle}/{nom} ne dit pas ce qu'elle coûte")
