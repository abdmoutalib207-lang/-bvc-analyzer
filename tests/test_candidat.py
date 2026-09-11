#!/usr/bin/env python3
"""Import contrôlé, journal des différences, et les correctifs du lot 1D.

⚠️ Ces tests portent sur des défauts RÉELLEMENT reproduits par la revue.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))
sys.path.insert(0, str(RACINE / "pipeline"))

from fenetre import (  # noqa: E402
    longueur_minimale, operations_dans_la_fenetre, qualifier_fenetre,
    raccordement_etabli,
)
from importer_export import ABSENCES, lire_nombre  # noqa: E402
from indicateurs import macd, rsi_wilder  # noqa: E402
from journal_differences import diagnostiquer_volume, tronque_vers  # noqa: E402

CANDIDAT = RACINE / "datasets" / "candidat"
TITRES = ["ADH", "CSR"]


def charger(t):
    return json.loads((CANDIDAT / f"{t}.json").read_text(encoding="utf-8"))


def journal(t):
    return json.loads((CANDIDAT / f"journal_{t}.json").read_text(encoding="utf-8"))


# ═══ A. L'IMPORT NE FABRIQUE JAMAIS DE ZÉRO ════════════════════════════════

def test_le_tiret_devient_absent_jamais_zero():
    """⚠️ Le rendu transformait « - » en 0,00. Une absence n'est pas un zéro."""
    for marqueur in ("-", "", "  ", "n/a"):
        v, etat = lire_nombre(marqueur)
        assert v is None and etat == "absent", marqueur
    assert lire_nombre("0")[0] == 0.0, "un vrai zéro doit rester un zéro"
    assert lire_nombre("0")[1] == "mesuré"


def test_une_valeur_illisible_est_comptee_pas_ignoree():
    v, etat = lire_nombre("douze")
    assert v is None and etat == "illisible"


def test_csr_conserve_ses_deux_absences():
    """L'export CSR porte « - » sur deux séances. Elles doivent survivre."""
    d = charger("CSR")
    assert d["champs_absents"]["volume_mad"] == 2
    absents = [o["date"] for o in d["observations"]
               if o["etats"]["volume_mad"] == "absent"]
    assert absents == ["2023-11-08", "2024-03-21"], absents


@pytest.mark.parametrize("t", TITRES)
def test_l_import_controle_ce_qu_il_annonce(t):
    c = charger(t)["controles"]
    assert c["lignes_lues"] > 700
    assert c["dates_illisibles"] == [] and c["doublons"] == []
    assert c["ticker_inattendu"] == [] and c["valeurs_illisibles"] == []


@pytest.mark.parametrize("t", TITRES)
def test_montants_et_quantites_restent_separes(t):
    """⚠️ Aucune conversion : le champ `v` ne garde pas le même contenu."""
    d = charger(t)
    for o in d["observations"][:50]:
        assert "volume_mad" in o and "titres_echanges" in o
    assert "SÉPARÉS" in d["_les_deux_grandeurs_restent_separees"] or \
           "DISTINCTS" in d["_les_deux_grandeurs_restent_separees"]


# ═══ B. TROIS HYPOTHÈSES, TENUES SÉPARÉES ══════════════════════════════════

def cand(m=None, t=None, em="mesuré", et="mesuré", date="2026-06-15"):
    return {"date": date, "volume_mad": m, "titres_echanges": t,
            "etats": {"volume_mad": em, "titres_echanges": et}}


def test_hypothese_unite_le_champ_suit_l_autre_colonne():
    assert diagnostiquer_volume(500.0, cand(m=9999.0, t=500.0), [])["hypothese"] \
        == "concordant"


def test_hypothese_date_cherchee_sur_LES_DEUX_colonnes():
    """⚠️ DÉFAUT RELEVÉ : le décalage n'était cherché que sur les MONTANTS,
    précisément là où le champ n'avait pas changé. Sur les QUANTITÉS, la revue
    en a trouvé plusieurs, formant des chaînes consécutives."""
    veille = cand(m=1.0, t=6406.0, date="2026-06-11")
    d = diagnostiquer_volume(6406.0, cand(m=2.0, t=78743.0), [veille])
    assert d["hypothese"] == "date différente"
    assert "quantité" in d["detail"] and "2026-06-11" in d["detail"]


def test_hypothese_valeur_quand_rien_ne_correspond():
    d = diagnostiquer_volume(12345.0, cand(m=1.0, t=2.0), [cand(m=3.0, t=4.0)])
    assert d["hypothese"] == "valeur différente"


def test_non_comparable_n_est_pas_un_ecart():
    d = diagnostiquer_volume(202.0, cand(em="absent", et="absent"), [])
    assert d["hypothese"] == "non comparable"
    assert "IMPOSSIBLE" in d["detail"]


def test_troncature_reconnue_comme_transformation():
    """CSR : 196,80 → 196 et 399,70 → 399. Pas « une autre valeur »."""
    assert tronque_vers(196, 196.80) and tronque_vers(399, 399.70)
    assert not tronque_vers(196, 196.0), "sans décimales, ce n'est pas une troncature"
    d = diagnostiquer_volume(196.0, cand(m=196.80, t=1.0), [])
    assert d["hypothese"] == "transformation"


def test_les_chaines_de_decalage_sont_dans_le_journal():
    """Le résultat réel, sur CSR : plusieurs cas consécutifs."""
    dec = [x for x in journal("CSR")["detail_volumes"]
           if x["hypothese"] == "date différente"]
    assert len(dec) >= 5, f"{len(dec)} cas — la chaîne a disparu"


# ═══ C. LES TROIS MESURES DE PRIX NE SE CONFONDENT PAS ═════════════════════

@pytest.mark.parametrize("t", TITRES)
def test_champs_dates_et_clotures_sont_comptes_separement(t):
    """⚠️ « 105 écarts » désignait des CHAMPS, pas des séances ni des clôtures."""
    p = journal(t)["prix"]
    assert p["champs_differents"] > p["dates_concernees"] > p["clotures_differentes"]


@pytest.mark.parametrize("t", TITRES)
def test_dates_internes_et_extension_sont_distinguees(t):
    """Une date postérieure à notre dernière séance n'est pas un manque."""
    d = journal(t)["dates"]
    assert d["absentes_de_l_ancien_EXTENSION"] == ["2026-09-09", "2026-09-10"]
    assert "2026-06-22" in d["absentes_de_l_ancien_INTERNES"]


def test_csr_a_six_dates_internes_manquantes():
    d = journal("CSR")["dates"]["absentes_de_l_ancien_INTERNES"]
    assert len(d) == 6, d


def test_le_detail_n_est_pas_tronque():
    """⚠️ Le rapport précédent s'arrêtait aux quarante premiers écarts."""
    j = journal("ADH")
    attendus = j["prix"]["champs_differents"] + j["prix"]["champs_non_comparables"]
    assert len(j["detail_prix"]) == attendus
    assert len(j["detail_prix"]) > 40


# ═══ D. LONGUEUR MINIMALE PAR INDICATEUR ═══════════════════════════════════

def test_le_rsi_exige_une_cloture_de_plus_que_sa_periode():
    """⚠️ n variations exigent n+1 clôtures. Mesuré : 14 clôtures ⇒ 0 point."""
    assert longueur_minimale("rsi_wilder", 14) == 15
    assert sum(1 for v in rsi_wilder([float(i) for i in range(14)], 14)
               if v is not None) == 0
    assert sum(1 for v in rsi_wilder([float(i) for i in range(15)], 14)
               if v is not None) == 1


def test_le_macd_sort_son_signal_a_trente_quatre():
    """⚠️ Le contrôle en exigeait 35 et refusait donc un cas calculable."""
    assert longueur_minimale("macd", None, (12, 26, 9)) == 34
    m = macd([float(i) for i in range(34)], 12, 26, 9)
    assert sum(1 for v in m["signal"] if v is not None) == 1


def test_une_moyenne_exige_exactement_sa_periode():
    assert longueur_minimale("sma", 20) == 20
    assert longueur_minimale("ema", 20) == 20


# ═══ E. LES DEUX REGISTRES D'OPÉRATIONS, UN SEUL CONTRÔLE ══════════════════

def test_hps_est_trouve_alors_qu_il_n_est_pas_dans_SPLITS():
    """⚠️ DÉFAUT RELEVÉ : le contrôle ne lisait que SPLITS et rendait une liste
    vide pour l'opération la mieux établie du projet."""
    import bvc_config
    assert "HPS" not in bvc_config.SPLITS
    ops = operations_dans_la_fenetre("HPS", "2023-09-01", "2023-11-01")
    assert len(ops) == 1 and ops[0]["date_effet"] == "2023-10-09"


def test_mng_reste_trouve_via_SPLITS():
    ops = operations_dans_la_fenetre("MNG", "2026-07-01", "2026-08-10")
    assert len(ops) == 1 and "SPLITS" in ops[0]["registre"]


def test_une_traversee_ne_suffit_pas_a_refuser():
    """⚠️ Un historique correctement ajusté reste comparable de part et
    d'autre. Ce qui refuse, c'est un RACCORDEMENT non établi."""
    documente = {"traitement": {"niveau": "ajustement documenté"}}
    probable = {"traitement": {"niveau": "ajustement probable, à confirmer"}}
    assert raccordement_etabli(documente) is True
    assert raccordement_etabli(probable) is False
    assert raccordement_etabli({"traitement": None}) is False


def test_le_refus_nomme_le_raccordement_pas_la_traversee():
    d = json.loads((RACINE / "datasets" / "lot1b" / "MNG.json")
                   .read_text(encoding="utf-8"))
    q = qualifier_fenetre(d["observations"], "sma", "2026-07-01", "2026-08-10",
                          periode=20, ticker="MNG")
    motif = " ".join(q["motifs"])
    assert "RACCORDEMENT" in motif
    assert "pas la traversée qui refuse" in motif
