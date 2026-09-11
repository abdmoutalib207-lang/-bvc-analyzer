#!/usr/bin/env python3
"""Ruptures observées, registre des opérations, conservation des sources.

Ce que ces tests doivent empêcher :

  · qu'un chiffre soit annoncé sans pouvoir être recalculé ;
  · qu'une rupture soit lue comme la preuve d'une opération sur titres ;
  · qu'une pièce datée serve à justifier un ajustement automatique ;
  · qu'une absence de recherche passe pour un historique certifié ;
  · qu'un analyseur de format soit figé avant d'avoir vu un fichier réel.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))
sys.path.insert(0, str(RACINE / "pipeline"))

from import_source import ANALYSEURS, empreinte, inspecter, inventaire  # noqa: E402
from ruptures import SEUIL, marquer_allers_retours, mesurer  # noqa: E402

REGISTRE = RACINE / "pipeline" / "operations_titres.json"


# ═══ A. LES RUPTURES SONT REPRODUCTIBLES ═══════════════════════════════════

def test_le_chiffre_annonce_se_recalcule():
    """⚠️ « 13 ruptures sur 9 titres » avait été annoncé depuis un calcul
    jetable, jamais reproduit. Une commande le rend maintenant.
    """
    m = mesurer()
    assert m["ruptures"] == len(m["observations"])
    assert m["ruptures"] == m["allers_retours"] + m["sens_unique"]
    assert m["ruptures"] == m["avec_piece"] + m["sans_piece"]
    assert len(m["titres_concernes"]) == len({o["titre"] for o in m["observations"]})


def test_la_regle_de_detection_est_publiee_avec_chaque_observation():
    for o in mesurer()["observations"]:
        assert str(SEUIL) in o["regle_de_detection"]


def test_le_seuil_depasse_tout_regime_connu():
    """Sous ±20 %, deux clôtures consécutives ne s'écartent que d'un facteur 1,20."""
    assert SEUIL > 1.20


def test_chaque_rupture_porte_ses_pieces_de_lecture():
    """Titre, dates encadrantes, prix, rapport, volumes, règle — tous exigés."""
    for o in mesurer()["observations"]:
        for champ in ("titre", "date_avant", "date_apres", "cloture_avant",
                      "cloture_apres", "rapport_observe", "volume_avant",
                      "volume_apres", "regle_de_detection",
                      "jours_calendaires_entre_les_deux"):
            assert champ in o, champ
        assert o["bougie_avant"] and o["bougie_apres"]


def test_observation_hypothese_et_conclusion_restent_distinctes():
    """Une rupture est une ALERTE. La conclusion reste vide sans pièce."""
    for o in mesurer()["observations"]:
        assert len(o["hypotheses_compatibles"]) >= 4
        if o["piece_couvrant_la_date"] is None:
            assert o["conclusion"] is None, o["titre"]


def test_une_piece_n_etablit_que_l_evenement():
    """⚠️ Même documentée, une opération ne dit pas comment NOTRE fichier l'a
    traitée. La conclusion doit le rappeler, sinon elle autorise un ajustement.
    """
    avec = [o for o in mesurer()["observations"] if o["piece_couvrant_la_date"]]
    assert avec, "aucune rupture couverte par une pièce — le test ne prouverait rien"
    for o in avec:
        assert "PAS la manière dont notre fichier" in o["conclusion"]


# ═══ B. LE TRI ALLER-RETOUR / SENS UNIQUE ══════════════════════════════════

def rupture(titre, avant, apres, rapport):
    return {"titre": titre, "date_avant": avant, "date_apres": apres,
            "rapport_observe": rapport, "aller_retour": None}


def test_un_aller_retour_est_reconnu():
    """Une opération sur titres NE REVIENT JAMAIS. Chute puis remontée au même
    niveau décrit une valeur injectée, pas un événement de marché."""
    r = [rupture("X", "2026-06-05", "2026-06-08", 0.2),
         rupture("X", "2026-06-16", "2026-06-18", 5.0)]
    marquer_allers_retours(r)
    assert r[0]["aller_retour"] and r[1]["aller_retour"]
    assert r[0]["aller_retour"]["produit_des_rapports"] == pytest.approx(1.0)


def test_une_chute_sans_retour_reste_sens_unique():
    """C'est la forme d'une vraie division d'action."""
    r = [rupture("X", "2023-10-06", "2023-10-09", 0.1028)]
    marquer_allers_retours(r)
    assert r[0]["aller_retour"] is None


def test_deux_ruptures_trop_eloignees_ne_s_apparient_pas():
    r = [rupture("X", "2024-01-05", "2024-01-08", 0.2),
         rupture("X", "2025-06-16", "2025-06-18", 5.0)]
    marquer_allers_retours(r)
    assert r[0]["aller_retour"] is None


def test_deux_titres_differents_ne_s_apparient_pas():
    r = [rupture("X", "2026-06-05", "2026-06-08", 0.2),
         rupture("Y", "2026-06-16", "2026-06-18", 5.0)]
    marquer_allers_retours(r)
    assert r[0]["aller_retour"] is None


def test_le_tri_reduit_reellement_le_champ():
    """Le tri doit servir à quelque chose : il reste moins de candidates."""
    m = mesurer()
    candidates = [o for o in m["observations"]
                  if not o["aller_retour"]
                  and not o["aucune_transaction_de_part_et_d_autre"]]
    assert len(candidates) < m["ruptures"], "le tri n'écarte rien"


# ═══ C. LE REGISTRE DES OPÉRATIONS ═════════════════════════════════════════

def registre() -> dict:
    return json.loads(REGISTRE.read_text(encoding="utf-8"))


def test_la_piece_hps_est_conservee_et_son_empreinte_concorde():
    """Une référence à une URL ne prouve rien : la copie doit être là."""
    op = registre()["operations"]["HPS"][0]
    copie = RACINE / op["piece"]["copie_conservee"]
    assert copie.exists(), "la pièce citée n'est pas dans le dépôt"
    attendue = hashlib.sha256(copie.read_bytes()).hexdigest()
    assert op["piece"]["empreinte_sha256"] == attendue


def test_la_piece_hps_porte_les_faits_du_document():
    """Relevés dans le PDF lu directement, pas dans le message qui le relayait."""
    op = registre()["operations"]["HPS"][0]
    assert op["ratio"] == 10
    assert op["date_effet"] == "2023-10-09"
    assert op["date_decision"] == "2023-09-20"
    assert op["valeur_nominale"] == {"avant": 100, "apres": 10, "devise": "MAD"}
    assert op["nombre_actions"] == {"avant": 740619, "apres": 7406190}
    assert op["piece"]["lu_par_nous"] is True


def test_le_document_se_recoupe_par_l_arithmetique():
    """740 619 × 10 = 7 406 190. Deux sources peuvent se tromper ensemble ;
    une identité qui se recoupe par le calcul, non."""
    n = registre()["operations"]["HPS"][0]["nombre_actions"]
    r = registre()["operations"]["HPS"][0]["ratio"]
    assert n["avant"] * r == n["apres"]


def test_le_registre_separe_l_evenement_de_son_traitement():
    t = registre()["operations"]["HPS"][0]["traitement_dans_notre_serie"]
    assert t["niveau"].startswith("non ajusté")
    assert "hypothèse" in t["niveau"]
    assert t["fait_observe"] and t["hypothese"] and t["ce_qui_manque"]
    assert t["hypothese"] != t["fait_observe"]


def test_le_registre_interdit_l_ajustement_automatique():
    assert "JAMAIS réappliquer" in registre()["_ce_qu_une_piece_etablit"]


def test_une_absence_de_recherche_n_est_pas_un_certificat():
    """« Aucune opération retrouvée » n'est pas « historique certifié »."""
    r = registre()
    assert "n'est PAS" in r["_ce_qu_une_absence_n_etablit_pas"]
    for titre, f in r["fenetres_examinees"].items():
        assert f["periode"] and f["sources_consultees"]
        assert f["incertitudes_restantes"], titre
        assert "PAS certifiée" in f["conclusion"] or "certifi" in f["conclusion"]


def test_le_registre_se_sait_perissable():
    assert "au fil de l'eau" in registre()["_entretien"]


# ═══ D. CONSERVATION DES SOURCES ═══════════════════════════════════════════

def test_l_analyseur_n_est_pas_fige_avant_d_avoir_vu_un_fichier():
    """⚠️ Deviner un schéma produit un analyseur qui décrit ce qu'on imaginait.

    Aucun export de cours n'a encore été reçu : il n'y a rien à déclarer.
    """
    assert ANALYSEURS == {}


def test_l_inspection_ne_suppose_aucun_schema():
    r = inspecter(REGISTRE)
    assert r["empreinte_sha256"] and r["taille_octets"] > 0
    assert r["colonnes_apparentes"] is None
    assert "Aucun schéma n'est supposé" in r["_reserve"]


def test_l_enveloppe_de_provenance_accompagne_le_fichier():
    inv = inventaire()
    assert inv["fichiers_conserves"] >= 1, "aucune source conservée"
    for f in inv["fichiers"]:
        chemin = RACINE / "sources" / f["titre"] / f["fichier"]
        assert chemin.exists(), chemin
        assert empreinte(chemin) == f["empreinte_sha256"]
        assert f["url"] and f["recupere_le"]


def test_l_unite_n_est_jamais_deduite_des_nombres():
    """⚠️ L'ordre de grandeur d'une colonne ne dit pas son unité."""
    for f in inventaire()["fichiers"]:
        u = f["unites_declarees"]
        assert "jamais déduite" in u["_note"]
        if not f.get("periode_etablie"):
            assert u["prix"] == "non déclarée"


def test_conserver_un_fichier_n_etablit_pas_son_exactitude():
    for f in inventaire()["fichiers"]:
        assert "n'établit NI l'exactitude" in f["_ce_qui_ne_l_est_pas"]


# ═══ E. L'UNITÉ DES VOLUMES ════════════════════════════════════════════════

def test_l_unite_des_volumes_est_mesuree_pas_supposee():
    """⚠️ « unite_etablie: False » n'était qu'une précaution de principe.

    La mesure la fonde : une unité unique « nombre de titres » est
    incompatible avec les montants qu'elle impliquerait.
    """
    from unites_volume import mesurer as mesurer_unites
    m = mesurer_unites()
    assert m["series_mesurees"] > 50
    assert m["series_invraisemblables"] >= 1, (
        "aucune série invraisemblable — la réserve sur l'unité perd son appui")
    assert m["amplitude_des_montants"]["facteur"] > 1000


def test_la_mesure_ne_conclut_pas_sur_ce_que_v_est():
    """Montrer qu'une unité est incompatible ne dit pas laquelle est la bonne."""
    from unites_volume import mesurer as mesurer_unites
    assert "ne dit PAS ce que" in mesurer_unites()["_ce_qui_n_est_pas_etabli"]


def test_la_consequence_est_tenue_dans_le_code():
    """Le registre des quantités doit rester vide tant que rien n'est établi."""
    from normaliser import BASES_QUANTITES, diagnostic_quantites
    assert BASES_QUANTITES == {}
    assert diagnostic_quantites("ADH")["unite_etablie"] is False
