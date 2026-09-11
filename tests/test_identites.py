#!/usr/bin/env python3
"""Le contrat d'identité — empêcher qu'un titre reçoive les cours d'un autre.

⚠️ CE QUE CES TESTS PROTÈGENT
MSA a porté les cours de Mutandis pendant cinq semaines. Aucun contrôle
NUMÉRIQUE ne pouvait l'attraper : ces cours respectaient l'invariant OHLC, la
limite de variation, la continuité. Ils appartenaient à quelqu'un d'autre.

Les tests ci-dessous portent donc sur l'IDENTITÉ, jamais sur les valeurs.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))
sys.path.insert(0, str(RACINE / "pipeline"))

from contamination import SOUPCONS, fenetre_contaminee, mesurer_recouvrement  # noqa: E402
from fenetre import Verdict, qualifier_fenetre  # noqa: E402
from identites import (  # noqa: E402
    Identite, autoriser_ecriture, concordance, est_variante, etat, inventaire,
    vise_un_autre_titre,
)

LOT1B = RACINE / "datasets" / "lot1b"


# ═══ A. LE COMPORTEMENT EXIGÉ PAR LA REVUE ═════════════════════════════════

def test_mauvaise_entreprise_renvoyee_aucune_ecriture():
    """⚠️ LE SCÉNARIO DE JUIN, REJOUÉ.

    Le collecteur demande l'historique de MSA ; la source renvoie Mutandis.
    C'est exactement ce qui a mis cinq semaines de cours étrangers dans notre
    fichier. L'écriture doit être refusée.
    """
    r = autoriser_ecriture("MSA", "Mutandis SCA")
    assert r["autorise"] is False
    assert "UNE AUTRE ENTREPRISE" in r["motif"]
    assert "Mutandis" in r["motif"]


def test_identite_verifiee_import_autorise():
    """La garde ne doit pas tout bloquer : une identité qui concorde passe."""
    r = autoriser_ecriture("MSA", "Sodep-Marsa Maroc")
    assert r["autorise"] is True


def test_le_code_du_fournisseur_vaut_identite():
    """La source peut renvoyer un code plutôt qu'un nom."""
    assert autoriser_ecriture("MSA", "MSA")["autorise"] is True


def test_aucune_identite_renvoyee_aucune_ecriture():
    """⚠️ Sans identité reçue, on ne peut rien vérifier — donc rien écrire.

    Une table cohérente avec elle-même peut être fausse : c'était le cas.
    """
    r = autoriser_ecriture("ADH", None)
    assert r["autorise"] is False
    assert "aucune identité vérifiable" in r["motif"]


# ═══ B. LES DEUX DÉFAUTS ENCORE PRÉSENTS, NOMMÉS PAR LA REVUE ══════════════

def test_mrl_est_refuse_collision_avec_msa():
    """`MRL` demande « SODEP » — l'ancien nom de Marsa Maroc, qui est MSA."""
    e = etat("MRL")
    assert e["niveau"] == Identite.COLLISION.value
    assert e["vise_un_autre_titre"]["vise"][0]["ticker"] == "MSA"
    assert autoriser_ecriture("MRL", "SODEP")["autorise"] is False


def test_sbs_est_refuse_desaccord_de_fond():
    """⚠️ La « correction » de juin contredit notre propre référentiel.

    SBS = Société des Boissons du Maroc, ISIN MA0000010365. Le collecteur
    demande « Super Cereales ».
    """
    e = etat("SBS")
    assert e["niveau"] == Identite.DESACCORD_DE_FOND.value
    assert e["nom_demande_au_fournisseur"] == "Super Cereales"
    assert e["isin"] == "MA0000010365"
    assert autoriser_ecriture("SBS", "Super Cereales")["autorise"] is False


def test_on_n_a_pas_remplace_la_chaine_par_un_nom_suppose():
    """Instruction explicite : ne pas « corriger » depuis une conviction.

    Les deux entrées fautives restent en place ; c'est l'ÉCRITURE qui est
    bloquée, en attendant une réponse de fournisseur.
    """
    assert etat("SBS")["nom_demande_au_fournisseur"] == "Super Cereales"
    assert etat("MRL")["nom_demande_au_fournisseur"] == "SODEP"


# ═══ C. LE CONTRÔLE NE DOIT PAS CRIER AU LOUP ══════════════════════════════

def test_les_abreviations_ne_sont_pas_des_contradictions():
    """⚠️ Une première version signalait vingt titres, dont « BOA » pour Bank
    of Africa et « CMT ». Un contrôle qui crie au loup vingt fois n'est plus lu
    la vingt-et-unième."""
    for t in ("BOA", "CDM", "IBM", "WAF", "STR", "ADH"):
        e = etat(t)
        assert e["niveau"] != Identite.COLLISION.value, t
        assert e["niveau"] != Identite.DESACCORD_DE_FOND.value, t


def test_une_troncature_est_reconnue():
    assert est_variante("Afric Indus", "Afric Industries SA")
    assert est_variante("Total Maroc", "TotalEnergies Marketing Maroc")
    assert est_variante("BOA", "Bank of Africa")


def test_une_autre_societe_n_est_pas_une_troncature():
    assert est_variante("Super Cereales", "Société des Boissons du Maroc") is None
    assert est_variante("Mutandis", "Sodep-Marsa Maroc") is None


def test_le_nombre_de_refus_reste_proportionne():
    """Sept refus sur 81 : assez rares pour être lus, assez nombreux pour
    couvrir les cas nommés par la revue."""
    inv = inventaire()
    refus = len(inv["collisions"]) + len(inv["desaccords_de_fond"])
    assert 1 <= refus <= 12, f"{refus} refus sur {inv['titres']}"
    noms = {e["ticker"] for e in inv["collisions"] + inv["desaccords_de_fond"]}
    assert {"MRL", "SBS"} <= noms


def test_aucune_identite_n_est_declaree_verifiee():
    """⚠️ Le dépôt ne conserve aucune réponse de fournisseur : rien ne peut
    l'être. Une entrée « vérifiée » sans charge utile serait une conviction
    déguisée en preuve."""
    from identites import IDENTITES_VERIFIEES
    assert IDENTITES_VERIFIEES == {}
    assert all(e["niveau"] != Identite.VERIFIEE.value
               for e in inventaire()["etats"])


# ═══ D. L'INVENTAIRE DES CONTAMINATIONS ════════════════════════════════════

def test_la_table_msa_mut_est_reproductible():
    """18 correspondances sur 18 — le chiffre doit se recalculer."""
    m = mesurer_recouvrement("MSA", "MUT", "2026-05-13", "2026-06-16")
    assert m["dates_communes"] == 18
    assert m["identiques"] == 18
    assert m["taux"] == 1.0


def test_une_absence_de_recouvrement_n_est_pas_une_infirmation():
    """⚠️ HAL et BMC n'ont pas de données sur la période suspecte. Leur
    silence ne disculpe ni n'accuse — la revue l'a rappelé."""
    for t, s in (("ATL", "HAL"), ("CFGB", "BMC")):
        m = mesurer_recouvrement(t, s, "2026-05-13", "2026-06-16")
        assert m["dates_communes"] == 0
        assert "ni une confirmation ni une infirmation" in m["_lecture"]


def test_les_niveaux_de_preuve_sont_distincts():
    niveaux = {s["titre"]: s["niveau"] for s in SOUPCONS}
    assert niveaux["MSA"] == "établi par la mesure"
    assert "NON reproduit" in niveaux["ATL"]
    assert "aucune fenêtre datée" in niveaux["SBS"]


def test_chaque_soupcon_dit_ce_qui_lui_manque():
    for s in SOUPCONS:
        assert s["ce_qui_manque"] and len(s["ce_qui_manque"]) > 30, s["titre"]


def test_les_trois_horloges_sont_declarees():
    """Date de séance, date d'écriture, date du correctif — jamais confondues."""
    from contamination import inventaire as inv_cont
    t = inv_cont()["_trois_horloges"]
    assert "SÉANCE" in t and "écrite" in t and "corrigé" in t


def test_aucune_reconstitution_n_est_proposee():
    """⚠️ Ne pas déduire les cours de Marsa Maroc de ceux de Mutandis."""
    from contamination import inventaire as inv_cont
    assert "NE JAMAIS déduire" in inv_cont()["_interdit"]


# ═══ E. LA PROTECTION EMPÊCHE L'ALIMENTATION SILENCIEUSE ═══════════════════

def test_une_fenetre_contaminee_est_reconnue():
    assert fenetre_contaminee("MSA", "2026-06-01", "2026-06-30")
    assert fenetre_contaminee("MSA", "2026-05-20", "2026-05-25")


def test_une_fenetre_hors_periode_ne_l_est_pas():
    assert fenetre_contaminee("MSA", "2026-08-01", "2026-08-31") == []
    assert fenetre_contaminee("ADH", "2026-06-01", "2026-06-30") == []


def test_la_qualification_refuse_une_fenetre_contaminee():
    """⚠️ C'est le point : un indicateur ne doit pas être alimenté en silence
    par des cours appartenant à une autre société.

    Éprouvé sur les VRAIES bougies de MSA, pas sur une donnée construite : MSA
    ne fait pas partie des sept séries figées, on lit donc ses chandelles.
    """
    f = RACINE / "pipeline" / "candles" / "MSA.json"
    assert f.exists(), "MSA doit exister pour que ce test prouve quelque chose"
    obs = [{"date": str(b["d"])[:10],
            "prix_etats": {"cloture": "mesuré"}, "volume_etat": "mesuré",
            "admissible_pour": ["prix_analyse", "volume",
                                "indicateur_exploratoire"],
            "amplitude": {"statut": "compatible avec l'enveloppe testée"}}
           for b in json.loads(f.read_text(encoding="utf-8")) if b.get("c")]
    q = qualifier_fenetre(obs, "sma", "2026-06-01", "2026-06-16",
                          periode=5, ticker="MSA")
    assert q["verdict"] == Verdict.REFUSE.value
    assert any("contamination" in m for m in q["motifs"])
    assert any("APPARTENANCE" in m for m in q["motifs"])


def test_le_motif_dit_que_les_valeurs_sont_bien_formees():
    """Sinon on chercherait le défaut du mauvais côté."""
    obs = [{"date": "2026-06-10", "prix_etats": {"cloture": "mesuré"},
            "volume_etat": "mesuré", "admissible_pour": ["prix_analyse", "volume"],
            "amplitude": {"statut": "compatible avec l'enveloppe testée"}}]
    q = qualifier_fenetre(obs, "sma", "2026-06-01", "2026-06-30", ticker="MSA")
    assert any("bien formées" in m for m in q["motifs"])
