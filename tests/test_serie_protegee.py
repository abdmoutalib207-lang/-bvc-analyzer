#!/usr/bin/env python3
"""Une série réceptionnée ne se fait pas écraser par un import.

⚠️ CE QUI EST ARRIVÉ, ET EN COMBIEN DE TEMPS
────────────────────────────────────────────
    14/09/2026 19h38   la série CMT réceptionnée entre dans `main`
                       681 séances, dernière cotation le 16/07 à 4 350 DH
    14/09/2026 19h55   `collect_history_bvcscrap.py` retélécharge l'historique
                       et réécrit `pipeline/candles/CMT.json` : 536 séances

Dix-sept minutes. À partir de là, les contrôles bloquants ont refusé de publier
— ce qui est leur rôle — et `data.json` est resté figé sur la séance du 14/09
pendant que le moteur tournait sans rien pouvoir livrer. Le site servait une
donnée juste ; c'est la SUIVANTE qui ne partait plus.

⚠️ CE QUE CETTE GARDE N'EST PAS
───────────────────────────────
Elle ne rend pas le moteur publié « protégé ». `collect_history_bvcscrap.py`
identifie toujours les sociétés par NOM (`MANUAL_MAP`) et écrit les chandelles
des 73 autres titres sans contrôle d'identité. Cette garde ne couvre QUE les
titres dont une série a été explicitement réceptionnée.

⚠️ ELLE FIGE LE TITRE FACE AUX IMPORTS, PAS FACE AU MARCHÉ. Tant que le fichier
est dans `datasets/series_acceptees/`, aucun import en masse ne réécrit ce
titre. La séance du jour, elle, continue d'entrer par l'étape 6c du moteur : le
gel protège l'historique réceptionné, il n'empêche pas le titre de coter.

⚠️ CE PARAGRAPHE DISAIT L'INVERSE JUSQU'AU 16/09, et il se trompait deux fois.
Il affirmait qu'« aucune séance nouvelle n'entre » et qu'il faudrait « retirer
le fichier le jour où le titre reprend ». Minière Touissit a repris ce jour-là :
la 682e séance est entrée sans qu'on touche à rien, et retirer le fichier aurait
au contraire rouvert l'historique à l'importateur qui l'avait écrasé le 14/09.
Ce qu'il fallait corriger était ailleurs — dans `appliquer_serie.py`, qui
réécrivait le fichier ENTIER et aurait effacé la reprise. Voir les deux tests en
fin de fichier.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE / "pipeline"))


# ── Le fait, sur le dépôt ───────────────────────────────────────────────────

def test_cmt_porte_bien_une_serie_receptionnee():
    import collect_history_bvcscrap as C
    assert C.serie_acceptee("CMT") is True
    assert C.serie_acceptee("MSA") is False, (
        "MSA n'a PAS de série réceptionnée : ses 22 remplacements sont encore "
        "candidats. Si ce test rougit, une proposition est devenue une "
        "instruction sans passer par la revue.")


def test_les_deux_ecrivains_partagent_la_meme_regle():
    """⚠️ Trois programmes écrivent dans `pipeline/candles/`. En protéger un
    seul ne protège rien : c'est exactement ainsi que le 14/09 est arrivé."""
    import collect_history_bvcscrap as C
    import generate_candles as G
    assert C.serie_acceptee("CMT") is G.serie_acceptee("CMT") is True
    assert C.SERIES_ACCEPTEES.resolve() == G.SERIES_ACCEPTEES.resolve()


def test_le_dossier_decide_pas_le_nom_du_fichier(tmp_path):
    """La garde lit un DOSSIER, pas une liste en dur : une série réceptionnée
    demain n'exige aucune modification du code."""
    import collect_history_bvcscrap as C
    (tmp_path / "XYZ.json").write_text("{}", encoding="utf-8")
    assert C.serie_acceptee("XYZ", dossier=tmp_path) is True
    assert C.serie_acceptee("ABC", dossier=tmp_path) is False


# ── Le comportement : l'import s'arrête AVANT de télécharger ───────────────

@pytest.fixture()
def collecteur_sans_reseau(monkeypatch):
    """Toute tentative de lecture de source lève. Un titre protégé ne doit
    donc même pas commencer son import."""
    import collect_history_bvcscrap as C

    def interdit(*a, **k):
        raise AssertionError("une source a été interrogée pour un titre "
                             "dont la série est réceptionnée")

    monkeypatch.setattr(C, "load_xlsx", interdit)
    monkeypatch.setattr(C, "fetch_bvcscrap_extension", interdit)
    ecritures = []
    monkeypatch.setattr(C, "save_candle_file",
                        lambda t, df, d: ecritures.append(t))
    C._ecritures_du_test = ecritures
    return C


def test_un_titre_receptionne_n_est_ni_retelecharge_ni_reecrit(collecteur_sans_reseau):
    """⚠️ Le test mord sur le chemin réel : sans la garde, `load_xlsx` lève."""
    C = collecteur_sans_reseau
    resultats = C.run(tickers_filter=["CMT"])
    assert C._ecritures_du_test == [], (
        f"des chandelles ont été réécrites : {C._ecritures_du_test}")
    assert "CMT" in resultats, (
        "l'entrée de cache doit être CONSERVÉE : `save()` réécrit "
        "historical_data.json à partir des seuls résultats, un titre absent "
        "disparaîtrait du fichier et le moteur perdrait ses indicateurs")


def test_l_entree_conservee_est_celle_du_depot_a_l_identique(collecteur_sans_reseau):
    """Conserver, ce n'est pas recalculer. L'entrée doit sortir telle quelle."""
    C = collecteur_sans_reseau
    cache = json.loads((RACINE / "pipeline" / "historical_data.json")
                       .read_text(encoding="utf-8"))
    resultats = C.run(tickers_filter=["CMT"])
    assert resultats["CMT"] == cache["CMT"]


def test_un_titre_ordinaire_n_est_pas_protege(monkeypatch):
    """⚠️ Contre-épreuve. Une garde qui arrêterait tout le monde arrêterait
    aussi la collecte : on exige qu'un titre sans série réceptionnée passe
    bien par ses sources."""
    import collect_history_bvcscrap as C
    appels = []
    monkeypatch.setattr(C, "load_xlsx",
                        lambda t: appels.append(t) or __import__("pandas").DataFrame())
    monkeypatch.setattr(C, "fetch_bvcscrap_extension",
                        lambda n, d: __import__("pandas").DataFrame())
    monkeypatch.setattr(C, "save_candle_file", lambda t, df, d: None)
    C.run(tickers_filter=["MSA"])
    assert appels == ["MSA"], (
        "MSA doit être importé normalement — sinon la garde ne distingue rien")


# ── La série publiée, après réparation ─────────────────────────────────────

def test_la_serie_publiee_de_cmt_est_celle_qui_a_ete_acceptee():
    """Le même contrôle que `test_serie_et_cache.py`, énoncé ici parce que
    c'est CE fichier qui explique pourquoi il a rougi le 15/09."""
    acceptee = json.loads((RACINE / "datasets" / "series_acceptees" / "CMT.json")
                          .read_text(encoding="utf-8"))
    publiee = json.loads((RACINE / "pipeline" / "candles" / "CMT.json")
                         .read_text(encoding="utf-8"))
    # ⚠️ CETTE SÉRIE AVAIT LE DROIT DE GRANDIR, ET ELLE L'A FAIT. Minière
    # Touissit a repris sa cotation le 16/09 — bulletin de l'opérateur à
    # l'appui — après deux mois de suspension pour OPA. Un test qui exige que
    # la série s'arrête au 16/07 n'énonce plus une règle : il interdit au titre
    # de coter.
    #
    # La règle, elle, ne bouge pas : les 681 séances RÉCEPTIONNÉES doivent être
    # intactes, date pour date et clôture pour clôture. Ce qui vient après leur
    # est étranger, et légitime.
    assert acceptee["seances_negociees"] == 681
    assert len(publiee) >= 681, f"série amputée : {len(publiee)} bougies"
    recu = publiee[680]
    assert recu["d"] == "2026-07-16" and recu["c"] == 4350.0, (
        "la 681e séance publiée n'est plus celle qui a été réceptionnée")


# ── Le lot instruit sur sa période, et seulement sur elle ─────────────────────

def test_reappliquer_un_lot_n_efface_pas_les_seances_qui_le_suivent(tmp_path,
                                                                    monkeypatch):
    """⚠️ LE PIÈGE QUE LA REPRISE DE CMT A RÉVÉLÉ, ET QU'IL A FALLU CHERCHER.

    `appliquer()` réécrivait le fichier de chandelles ENTIER avec la série
    acceptée. Tant que le titre était suspendu, cela ne se voyait pas : il n'y
    avait rien après. Le 16/09, Minière Touissit a repris ; une 682e séance est
    entrée. Réappliquer le lot l'aurait effacée — sans erreur, sans message, et
    en ramenant le cours affiché de 2 438 à 4 350.

    La règle : un lot réceptionné dit ce qui s'est passé JUSQU'À sa dernière
    date. Il ne dit rien de ce qui vient après, et ne peut donc pas le nier.
    """
    import appliquer_serie as mod

    acceptees, candles = tmp_path / "acc", tmp_path / "cdl"
    acceptees.mkdir(); candles.mkdir()
    lot = {"ticker": "ZZZ", "instrument": "ESSAI", "serie": [
        {"d": "2026-07-15", "o": 1, "h": 1, "l": 1, "c": 4300.0, "v": 10},
        {"d": "2026-07-16", "o": 1, "h": 1, "l": 1, "c": 4350.0, "v": 10}]}
    (acceptees / "ZZZ.json").write_text(json.dumps(lot), encoding="utf-8")

    # Sur le disque : le lot, plus une séance de reprise postérieure.
    reprise = {"d": "2026-09-16", "o": 2438.0, "h": 2438.0, "l": 2438.0,
               "c": 2438.0, "v": 1}
    (candles / "ZZZ.json").write_text(json.dumps(
        [dict(b) for b in lot["serie"]] + [reprise]), encoding="utf-8")

    monkeypatch.setattr(mod, "ACCEPTEES", acceptees)
    monkeypatch.setattr(mod, "CANDLES", candles)
    r = mod.appliquer("ZZZ")
    assert "refus" not in r, r.get("refus")

    ecrit = json.loads((candles / "ZZZ.json").read_text(encoding="utf-8"))
    assert [b["d"] for b in ecrit] == ["2026-07-15", "2026-07-16", "2026-09-16"], (
        "la séance de reprise a disparu — le lot a nié ce qui lui est postérieur")
    assert ecrit[-1]["c"] == 2438.0
    assert r["seances_conservees_apres_le_lot"] == 1
    assert r["seances_du_lot"] == 2


def test_le_lot_reste_maitre_de_sa_propre_periode(tmp_path, monkeypatch):
    """Le revers, sans lequel le test précédent suffirait à tout laisser passer.

    Conserver ce qui suit ne doit pas devenir « conserver ce qui existe » : à
    l'intérieur de la période réceptionnée, c'est le lot qui fait foi, et une
    valeur divergente sur disque doit être écrasée.
    """
    import appliquer_serie as mod

    acceptees, candles = tmp_path / "acc", tmp_path / "cdl"
    acceptees.mkdir(); candles.mkdir()
    lot = {"ticker": "ZZZ", "instrument": "ESSAI", "serie": [
        {"d": "2026-07-16", "o": 1, "h": 1, "l": 1, "c": 4350.0, "v": 10}]}
    (acceptees / "ZZZ.json").write_text(json.dumps(lot), encoding="utf-8")
    (candles / "ZZZ.json").write_text(json.dumps(
        [{"d": "2026-07-16", "o": 1, "h": 1, "l": 1, "c": 999.0, "v": 3}]),
        encoding="utf-8")

    monkeypatch.setattr(mod, "ACCEPTEES", acceptees)
    monkeypatch.setattr(mod, "CANDLES", candles)
    mod.appliquer("ZZZ")
    ecrit = json.loads((candles / "ZZZ.json").read_text(encoding="utf-8"))
    assert len(ecrit) == 1 and ecrit[0]["c"] == 4350.0, (
        "le lot ne fait plus foi sur sa propre période")
