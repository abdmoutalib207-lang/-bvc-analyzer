#!/usr/bin/env python3
"""Qualification d'une FENÊTRE DATÉE pour un indicateur précis.

Ce que ces tests doivent empêcher :

  · qu'un indicateur n'utilisant que la clôture soit refusé parce qu'une autre
    colonne manque ;
  · qu'un indicateur utilisant les volumes soit accepté sans les vérifier ;
  · qu'un résultat exploratoire soit présenté comme publiable ;
  · qu'une fenêtre traversant une anomalie non résolue soit calculée quand même.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))
sys.path.insert(0, str(RACINE / "pipeline"))

from fenetre import BESOINS, Champ, Verdict, extraire, qualifier_fenetre  # noqa: E402

LOT1B = RACINE / "datasets" / "lot1b"


def obs(date, cloture="mesuré", ouverture="mesuré", haut="mesuré",
        bas="mesuré", volume_etat="mesuré", usages=("indicateur",),
        amplitude="compatible avec l'enveloppe testée", valeurs=None):
    """Observation construite, au format de la couche normalisée."""
    base = {
        "date": date,
        "prix_etats": {"ouverture": ouverture, "plus_haut": haut,
                       "plus_bas": bas, "cloture": cloture},
        "volume_etat": volume_etat,
        "admissible_pour": list(usages),
        "amplitude": {"statut": amplitude},
        "ouverture": 10.0, "plus_haut": 11.0, "plus_bas": 9.0,
        "cloture": 10.5, "volume": 100.0,
    }
    return {**base, **(valeurs or {})}


def fenetre_saine(n=30, usages=("indicateur", "indicateur_exploratoire")):
    return [obs(f"2026-0{1 + i // 28}-{1 + i % 28:02d}", usages=usages)
            for i in range(n)]


# ═══ Besoins déclarés par indicateur ══════════════════════════════════════

def test_une_moyenne_de_clotures_n_exige_pas_les_autres_colonnes():
    """Point explicite de la revue.

    Ouverture, plus-haut et plus-bas tous absents : une SMA reste calculable.
    """
    serie = [obs(f"2026-01-{i:02d}", ouverture="inconnu", haut="inconnu",
                 bas="inconnu", volume_etat="inconnu") for i in range(1, 31)]
    q = qualifier_fenetre(serie, "sma")
    assert q["verdict"] == Verdict.QUALIFIE.value, q["motifs"]
    assert q["besoins"] == ["cloture"]


def test_un_indicateur_de_volume_verifie_les_volumes():
    """À l'inverse, OBV doit refuser quand le volume manque."""
    serie = [obs(f"2026-01-{i:02d}", volume_etat="inconnu") for i in range(1, 31)]
    q = qualifier_fenetre(serie, "obv")
    assert q["verdict"] == Verdict.REFUSE.value
    assert any("volume" in m for m in q["motifs"])


def test_atr_exige_les_trois_colonnes_de_prix():
    serie = [obs(f"2026-01-{i:02d}", haut="inconnu") for i in range(1, 31)]
    assert qualifier_fenetre(serie, "sma")["verdict"] == Verdict.QUALIFIE.value
    assert qualifier_fenetre(serie, "atr")["verdict"] == Verdict.REFUSE.value


def test_les_besoins_declares_sont_minimaux():
    """Surdéclarer refuse des calculs légitimes ; sous-déclarer calcule sur du vide."""
    assert BESOINS["sma"] == {Champ.CLOTURE}
    assert BESOINS["rsi_wilder"] == {Champ.CLOTURE}
    assert BESOINS["atr"] == {Champ.PLUS_HAUT, Champ.PLUS_BAS, Champ.CLOTURE}
    assert Champ.VOLUME in BESOINS["obv"]


def test_indicateur_inconnu_est_refuse_explicitement():
    """Mieux vaut une erreur qu'un calcul sur des besoins devinés."""
    with pytest.raises(ValueError, match="besoins"):
        qualifier_fenetre(fenetre_saine(), "indicateur_imaginaire")


# ═══ Les trois issues ═════════════════════════════════════════════════════

def test_fenetre_qualifiee_quand_la_provenance_est_etablie():
    q = qualifier_fenetre(fenetre_saine(usages=("indicateur",
                                                "indicateur_exploratoire")), "sma")
    assert q["verdict"] == Verdict.QUALIFIE.value
    assert q["reserve"] is None


def test_fenetre_exploratoire_quand_la_provenance_est_incomplete():
    """§3 de la revue : permettre l'essai, en le signalant."""
    q = qualifier_fenetre(fenetre_saine(usages=("indicateur_exploratoire",)), "sma")
    assert q["verdict"] == Verdict.EXPLORATOIRE.value
    for mot in ("signal officiel", "probabilité", "performance"):
        assert mot in q["reserve"], mot


def test_fenetre_refusee_si_elle_traverse_une_alerte_non_resolue():
    serie = fenetre_saine()
    serie[10]["amplitude"]["statut"] = "hors enveloppe testée — alerte de cohérence"
    q = qualifier_fenetre(serie, "sma")
    assert q["verdict"] == Verdict.REFUSE.value
    assert any("alerte" in m for m in q["motifs"])
    assert serie[10]["date"] in " ".join(q["motifs"])


def test_fenetre_refusee_sur_valeur_invalide():
    serie = fenetre_saine()
    serie[5]["prix_etats"]["cloture"] = "invalide"
    q = qualifier_fenetre(serie, "sma")
    assert q["verdict"] == Verdict.REFUSE.value
    assert any("invalide" in m for m in q["motifs"])


def test_fenetre_refusee_si_une_observation_n_a_aucun_usage():
    serie = fenetre_saine()
    serie[3]["admissible_pour"] = []
    q = qualifier_fenetre(serie, "sma")
    assert q["verdict"] == Verdict.REFUSE.value


def test_couverture_insuffisante_refuse():
    """Quinze clôtures exploitables sur une longueur requise de 30."""
    serie = fenetre_saine(30)
    for o in serie[:15]:
        o["prix_etats"]["cloture"] = "inconnu"
    q = qualifier_fenetre(serie, "sma", longueur_requise=30)
    assert q["verdict"] == Verdict.REFUSE.value
    assert q["couvertures"]["cloture"]["couverture"] == pytest.approx(0.5)


# ═══ Bornes de la fenêtre ═════════════════════════════════════════════════

def test_la_fenetre_est_datee_et_ses_bornes_sont_rendues():
    """« Qualifier une fenêtre datée sans certifier tout l'historique. »"""
    serie = fenetre_saine(30)
    q = qualifier_fenetre(serie, "sma", debut=serie[5]["date"], fin=serie[20]["date"])
    assert q["lignes"] == 16
    assert q["debut"] == serie[5]["date"] and q["fin"] == serie[20]["date"]


def test_une_anomalie_hors_fenetre_ne_bloque_pas():
    """C'est tout l'intérêt de qualifier par fenêtre plutôt que par titre."""
    serie = fenetre_saine(30)
    serie[0]["amplitude"]["statut"] = "hors enveloppe testée — alerte de cohérence"
    q = qualifier_fenetre(serie, "sma", debut=serie[1]["date"])
    assert q["verdict"] != Verdict.REFUSE.value, q["motifs"]


def test_fenetre_vide_est_refusee_sans_planter():
    q = qualifier_fenetre(fenetre_saine(), "sma", debut="2030-01-01")
    assert q["verdict"] == Verdict.REFUSE.value
    assert q["lignes"] == 0


def test_extraire_ne_comble_aucun_trou():
    serie = fenetre_saine(5)
    serie[2]["cloture"] = None
    assert extraire(serie, Champ.CLOTURE)[2] is None


# ═══ Sur les données réelles du lot ═══════════════════════════════════════

def charger(t):
    return json.loads((LOT1B / f"{t}.json").read_text(encoding="utf-8"))


def test_adh_donne_un_exploratoire_pas_un_publiable():
    """ADH est « état inconnu » : on peut essayer, pas publier."""
    q = qualifier_fenetre(charger("ADH")["observations"], "sma",
                          debut="2026-06-01")
    assert q["verdict"] == Verdict.EXPLORATOIRE.value, q["motifs"]
    assert q["lignes"] > 40


def test_csr_donne_un_exploratoire_pas_un_publiable():
    q = qualifier_fenetre(charger("CSR")["observations"], "rsi_wilder",
                          debut="2026-06-01")
    assert q["verdict"] == Verdict.EXPLORATOIRE.value, q["motifs"]


def test_sot_reste_refuse_sur_son_historique():
    """La mise à l'écart conservatoire doit tenir jusqu'ici."""
    q = qualifier_fenetre(charger("SOT")["observations"], "sma",
                          debut="2024-06-01")
    assert q["verdict"] == Verdict.REFUSE.value
    assert any("2026-05-05" in m for m in q["motifs"])


def test_aucune_fenetre_du_lot_n_est_publiable_aujourd_hui():
    """Constat mesuré, pas objectif : aucune base de prix n'est documentée."""
    for t in ("ADH", "ADI", "CSR", "MNG", "CMT", "TQA", "SOT"):
        q = qualifier_fenetre(charger(t)["observations"], "sma",
                              debut="2026-06-01")
        assert q["verdict"] != Verdict.QUALIFIE.value, t
