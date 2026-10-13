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

import _echelle  # noqa: E402  (contrôles relatifs)
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


def _verifier_pire_ecart(c, cache_t):
    """Les contrôles portés par UN titre du dossier (testables sans le dossier)."""
    m = cache_t["ma200"]
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
    # décrit un passé. Le problème, c'est une MA200 publiée sur une série
    # de moins de 200 séances — un fait de structure, pas un écart de prix.
    #
    # ⚠️ 11/10/2026 : ce test exigeait `|ma200 / cours − 1| > 10 %` en
    # direct. C'est un seuil sur le niveau du marché : un cours qui se
    # rapproche de sa moyenne (une simple remontée du titre) faisait
    # échouer le test, donc bloquait la publication, sans qu'aucune donnée
    # ne soit fausse. L'écart de la MESURE reste contrôlé plus haut et
    # plus bas (recalcul à partir du cours que la mesure cite, écart > 20 %
    # à la date du relevé) ; ici on ne regarde que si le défaut existe.
    assert (cache_t.get("n_candles") or 0) < 200, (
        f"{c['ticker']} : la série compte désormais 200 séances ou plus — "
        "régénérer le dossier avec `python pipeline/mesurer_arbitrages.py "
        "--ecrire` plutôt que de laisser un constat périmé")
    assert m is not None
    assert abs(c["ecart_pct"]) > 20


def test_les_ecarts_annonces_sont_recalculables(mesures):
    """Les pires écarts cités — jusqu'à +56 % — doivent se retrouver au centime
    près depuis le cache et le fichier servi."""
    cache = json.loads((RACINE / "pipeline" / "historical_data.json")
                       .read_text(encoding="utf-8"))
    pires = mesures["arbitrage_1_la_moyenne_200_jours"]["_les_pires_ecarts"]
    if not pires:
        assert mesures["arbitrage_1_la_moyenne_200_jours"].get("_resolu") is True
        return
    for c in pires:
        _verifier_pire_ecart(c, cache[c["ticker"]])


def test_controle_negatif_et_positif_du_constat_de_ma200_courte():
    """⚠️ Le dossier est aujourd'hui RÉSOLU (aucun pire écart) : la boucle
    ci-dessus ne s'exécute pas. Ce test fait vivre la logique sur un cas fabriqué.

    - positif : le contrôle ne reçoit plus le cours du jour — il ne PEUT donc
      plus rougir parce que le titre a rejoint sa MA200 (avant : `|écart| >
      10 %` exigé en direct). Tant que la série compte moins de 200 séances,
      le constat tient ;
    - négatif : la série atteint 250 séances, la MA200 est devenue vraie → le
      dossier décrit un passé, le test doit échouer.
    """
    c = {"ticker": "XXX", "ma200_affichee": 100.0, "cours": 70.0, "ecart_pct": 42.9}
    assert round((100.0 / 70.0 - 1) * 100, 1) == c["ecart_pct"]
    _verifier_pire_ecart(c, {"ma200": 100.0, "n_candles": 150})   # passe, quel que soit le cours
    with pytest.raises(AssertionError, match="200 séances ou plus"):
        _verifier_pire_ecart(c, {"ma200": 100.0, "n_candles": 250})


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
    # ⚠️ 11/10/2026 : plus AUCUN seuil fixe de volume. `max < 100 000` puis
    # `médiane < 100 000` dataient le niveau des échanges d'ADI : une hausse
    # durable et réelle du volume aurait bloqué la publication. Le défaut
    # surveillé est un changement d'ÉCHELLE (titres <-> montant en dirhams, soit
    # un facteur égal au cours, ~400) entre les 60 dernières séances et les 240
    # précédentes ; voir `_echelle.defauts_volume` et ses contre-épreuves.
    # Limite assumée : une série ENTIÈREMENT convertie, sans saut, n'est pas
    # distinguée d'une série d'origine — c'est l'objet de la réception sur
    # pièce, pas d'un test sur la série seule.
    if (receptions / "ADI.json").exists():
        assert _echelle.defauts_volume(serie) == [], (
            "ADI porte une réception d'historique, mais l'échelle de ses "
            "volumes saute — l'import n'a pas pris, ou un montant en dirhams "
            "s'est glissé dans la série")
    else:
        assert _echelle.defauts_volume(serie) == [], (
            "les volumes d'ADI changent d'échelle sans export pour l'établir : "
            "l'arbitrage a été tranché sans être posé")


def test_les_trois_options_restent_ouvertes(mesures):
    """Un dossier d'arbitrage doit présenter les options avec leur COÛT, pas
    une seule habillée en évidence."""
    for cle in ("arbitrage_1_la_moyenne_200_jours", "arbitrage_2_l_unite_du_champ_volume"):
        options = mesures[cle]["_options"]
        assert len(options) == 3
        for nom, texte in options.items():
            assert "Coût" in texte or "coût" in texte, (
                f"{cle}/{nom} ne dit pas ce qu'elle coûte")
