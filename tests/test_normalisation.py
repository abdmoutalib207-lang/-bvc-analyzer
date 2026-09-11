#!/usr/bin/env python3
"""Tests de COMPORTEMENT de la couche normalisée.

⚠️ RÈGLE DE CONSTRUCTION DE CES TESTS
─────────────────────────────────────
    « N'écris pas l'attendu en réutilisant la fonction que tu cherches à
      tester. »  — revue externe

Les attendus sont écrits en dur, tirés du diagnostic et des sources. La seule
comparaison machine-à-machine est l'IDENTITÉ des valeurs entre l'instantané et
la couche dérivée — et c'est le point : la couche dérivée ne modifie rien.

    « Les erreurs métier doivent faire tomber les tests correspondants. Évite
      les tests qui valident seulement l'existence du nom d'un contrôle. »

Chaque défaut relevé en revue a donc ici un test qui le REPRODUIT sur une
donnée construite, et qui échouerait si le défaut revenait. Aucun test ne se
contente de vérifier qu'une clé porte le bon nom.
"""

from __future__ import annotations

import hashlib
import json
import math
import sys
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))
sys.path.insert(0, str(RACINE / "pipeline"))

from normaliser import (  # noqa: E402
    Preuve, admissibilite, comptabilite_coherente, diagnostic_base,
    diagnostic_quantites, quantite_comparable,
)
from qualification import (  # noqa: E402
    Seance, Volume, mediane_admissible, qualifier_bougie, qualifier_prix,
    qualifier_volume,
)
from regimes_variation import (  # noqa: E402
    Amplitude, Conformite, borne_amplitude, evaluer_amplitude,
    evaluer_conformite, source_couvre,
)

LOT1A = RACINE / "datasets" / "lot1a"
LOT1B = RACINE / "datasets" / "lot1b"

TITRES = ["ADH", "ADI", "CSR", "MNG", "CMT", "TQA", "SOT"]

LIGNES = {"ADH": 797, "ADI": 797, "CSR": 794, "MNG": 797,
          "CMT": 514, "TQA": 65, "SOT": 542}

NIVEAUX = {"ADH": "état inconnu", "ADI": "état inconnu", "CSR": "état inconnu",
           "CMT": "état inconnu", "TQA": "état inconnu",
           "MNG": "ajustement probable, à confirmer",
           "SOT": "base incohérente ou suspecte"}

SPLIT_SOT = "2026-05-05"
SOT_0505 = {"o": 1700.0, "h": 1700.0, "l": 369.0, "c": 369.0}

BOUGIE_SAINE = {"o": 100.0, "h": 104.0, "l": 98.0, "c": 102.0, "v": 500.0}


def charger(dossier: Path, ticker: str):
    return json.loads((dossier / f"{ticker}.json").read_text(encoding="utf-8"))


def juger(bougie, ticker="ADH", jour="2026-01-05", statut=Seance.NEGOCIEE,
          diag=None, diag_qte=None):
    """Passe une bougie construite dans le contrat d'admissibilité."""
    d = diag if diag is not None else diagnostic_base(ticker)
    dq = diag_qte if diag_qte is not None else diagnostic_quantites(ticker)
    amp = evaluer_amplitude(bougie, ticker, jour)
    return admissibilite(statut, d, bougie, amp, ticker, jour, dq)


def tout_documente(ticker="ZZZ"):
    """Diagnostics prix ET quantités au niveau « documenté »."""
    return ({**diagnostic_base("MNG"), "niveau": Preuve.DOCUMENTE.value},
            {**diagnostic_quantites(ticker), "niveau": Preuve.DOCUMENTE.value})


# ═══ A. LES TROIS CONTRE-EXEMPLES DE LA REVUE ══════════════════════════════
#
# Chacun décrivait un comportement RÉELLEMENT constaté avant correction.

def test_ouverture_et_cloture_absentes_n_autorisent_rien():
    """Défaut relevé : volume positif ⇒ prix, volume, indicateur ET exécution.

    Un volume numérique et positif n'est pas un passeport. Sans clôture, il n'y
    a rien à valoriser.
    """
    v = juger({"o": None, "h": 11.0, "l": 9.0, "c": None, "v": 500.0})
    assert "prix_analyse" not in v["admissible_pour"]
    assert "indicateur" not in v["admissible_pour"]
    assert "execution" not in v["admissible_pour"]
    assert "clôture absente" in v["refus"]["prix_analyse"]


def test_base_inconnue_n_autorise_pas_l_execution():
    """Défaut relevé : base « inconnu » ⇒ exécution autorisée."""
    v = juger(BOUGIE_SAINE, ticker="ADH")        # ADH : état inconnu
    assert diagnostic_base("ADH")["niveau"] == Preuve.INCONNU.value
    assert "execution_simulee" not in v["admissible_pour"]
    assert "cohérence prix × quantité" in v["refus"]["execution_simulee"]


def test_base_inconnue_autorise_quand_meme_l_exploratoire():
    """§3 de la revue : incertitude ≠ anomalie. On doit pouvoir essayer.

    Une première version bloquait tout calcul dès que la base était
    incertaine. C'était trop, et ça empêchait des essais utiles.
    """
    v = juger(BOUGIE_SAINE, ticker="ADH")
    assert "indicateur_exploratoire" in v["admissible_pour"]
    assert "indicateur" not in v["admissible_pour"]
    assert "EXPLORATOIRE" in v["refus"]["indicateur"]


def test_le_refus_de_l_indicateur_publiable_dit_ce_qu_il_interdit():
    """Un exploratoire ne doit alimenter ni signal, ni probabilité, ni perf."""
    motif = juger(BOUGIE_SAINE, ticker="ADH")["refus"]["indicateur"]
    for mot in ("signal officiel", "probabilité", "performance"):
        assert mot in motif, mot


def test_volume_infini_est_invalide():
    """Défaut relevé : +∞ classé « mesuré ».

    Le test portait sur NaN et sur la négativité. L'infini passe les deux.
    """
    for valeur in (float("inf"), float("-inf"), float("nan")):
        etat, val = qualifier_volume(valeur)
        assert etat is Volume.INVALIDE, f"{valeur} classé {etat}"
        assert val is None


def test_volume_infini_refuse_l_usage_volume():
    """Et l'invalidité doit se propager jusqu'au contrat, pas rester interne."""
    v = juger({**BOUGIE_SAINE, "v": float("inf")})
    assert "volume" not in v["admissible_pour"]
    assert "non fini" in v["refus"]["volume"]


# ═══ B. DEUX DÉFAUTS DE MÊME NATURE, TROUVÉS EN VÉRIFIANT LES SIENS ════════

def test_invariant_ohlc_rompu_refuse_les_usages():
    """Plus-bas AU-DESSUS du plus-haut : la bougie passait intégralement."""
    v = juger({"o": 10.0, "h": 5.0, "l": 99.0, "c": 10.0, "v": 5.0})
    assert v["admissible_pour"] == ["volume"]
    assert "OHLC" in v["refus"]["prix_analyse"]


def test_couverture_se_rapporte_a_la_fenetre_pas_aux_lignes_recues():
    """Une seule observation dans une fenêtre de 60 donnait 100 % de couverture.

    La médiane annoncée « sur 60 séances » était celle d'un point unique.
    """
    r = mediane_admissible([5.0], fenetre=60)
    assert r["couverture"] == pytest.approx(1 / 60, abs=1e-4)
    assert r["calculable"] is False
    assert r["valeur"] is None
    assert r["lignes_absentes_de_la_fenetre"] == 59


def test_couverture_complete_reste_calculable():
    """La correction ne doit pas rendre toute statistique incalculable."""
    r = mediane_admissible([float(i) for i in range(60)], fenetre=60)
    assert r["couverture"] == 1.0
    assert r["calculable"] is True
    assert r["valeur"] == pytest.approx(29.5)


def test_prix_nul_ou_negatif_est_invalide():
    """Zéro n'est pas un cours : l'accepter ferait diviser par zéro."""
    from qualification import Prix
    for valeur in (0, -1.0, float("inf"), float("nan"), "12", True, None):
        etat, _ = qualifier_prix(valeur)
        assert etat is not Prix.MESURE, f"{valeur!r} accepté comme prix"


# ═══ C. AMPLITUDE — CONTEXTUALISÉE, SOURCÉE, ET NON CONCLUANTE SI BESOIN ═══

def test_amplitude_faible_ne_vaut_pas_conformite_reglementaire():
    """CONTRE-EXEMPLE DE LA REVUE — le plus sérieux du lot.

    Référence 100 · ouverture et plus-bas 200 · plus-haut 201 · clôture 200.
    Le rapport h/l vaut 1,005 : amplitude minuscule. Sous ±20 % autour de 100,
    ces prix sont pourtant TOUS hors bornes.

    L'ancienne version répondait « conforme — licite sous tous les régimes
    connus ». Elle rendait un verdict réglementaire sans jamais recevoir le
    cours de référence.
    """
    b = {"o": 200.0, "h": 201.0, "l": 200.0, "c": 200.0}
    a = evaluer_amplitude(b, "XXX", "2026-07-01")

    # l'amplitude reste compatible — ce n'est pas ce qui est faux
    assert a["statut"] == Amplitude.COMPATIBLE.value
    # mais aucune conformité n'est affirmée, et il est dit pourquoi
    assert a["conformite_reglementaire"]["statut"] == Conformite.NON_VERIFIABLE.value
    assert any("référence" in m for m in a["conformite_reglementaire"]["ce_qui_manque"])

    # et le contrôle qui DISPOSE de la référence, lui, tranche
    c = evaluer_conformite(b, cours_reference=100.0,
                           nom_regime="admission_cinq_premieres_seances",
                           date_iso="2026-07-01")
    assert c["statut"] == Conformite.NON_CONFORME.value
    assert {h["champ"] for h in c["hors_bornes"]} == {
        "ouverture", "plus_haut", "plus_bas", "cloture"}


def test_aucun_resultat_d_amplitude_n_affirme_la_conformite():
    """Garde-fou général, pas seulement sur le contre-exemple."""
    for b in ({"o": 100.0, "h": 101.0, "l": 99.0, "c": 100.0},
              {"o": 100.0, "h": 400.0, "l": 80.0, "c": 100.0},
              {"o": 100.0, "h": 130.0, "l": 100.0, "c": 120.0},
              {"h": None, "l": None}):
        a = evaluer_amplitude(b, "XXX", "2026-07-01")
        assert a["conformite_reglementaire"]["statut"] == \
            Conformite.NON_VERIFIABLE.value, b
        assert "NE VAUT PAS conformité" in \
            a["conformite_reglementaire"]["_avertissement"]


def test_conformite_non_verifiable_sans_ses_trois_pieces():
    b = {"o": 100.0, "h": 101.0, "l": 99.0, "c": 100.0}
    sans_ref = evaluer_conformite(b, None, "continu", "2026-07-01")
    sans_reg = evaluer_conformite(b, 100.0, "", "2026-07-01")
    hors_periode = evaluer_conformite(b, 100.0, "continu", "2023-07-01")
    for r in (sans_ref, sans_reg, hors_periode):
        assert r["statut"] == Conformite.NON_VERIFIABLE.value
        assert r["ce_qui_manque"]


def test_conformite_accepte_des_prix_dans_les_bornes():
    """Le contrôle doit rester ACCORDABLE, sinon il ne dit plus rien."""
    r = evaluer_conformite({"o": 100.0, "h": 109.0, "l": 92.0, "c": 105.0},
                           cours_reference=100.0, nom_regime="continu",
                           date_iso="2026-07-01")
    assert r["statut"] == Conformite.CONFORME.value
    assert r["hors_bornes"] == []


def test_periode_de_validite_de_la_source_est_respectee():
    """La circulaire du 25/06/2026 ne régit pas une séance de 2023.

    ⚠️ 3 999 de nos 4 306 observations lui sont antérieures : l'étiquette
    réglementaire portait sur des données que le texte ne couvre pas.
    """
    assert source_couvre("2026-07-01") is True
    assert source_couvre("2023-07-01") is False
    ancienne = evaluer_amplitude({"h": 101.0, "l": 99.0}, "XXX", "2023-07-01")
    assert ancienne["source_dans_sa_periode_de_validite"] is False
    assert any("vigueur" in m
               for m in ancienne["conformite_reglementaire"]["ce_qui_manque"])


def test_alerte_extreme_vaut_a_toute_periode():
    """Elle ne s'appuie sur aucun texte : elle ne dépend donc d'aucune date."""
    for jour in ("2023-01-05", "2026-05-05", "2026-08-01"):
        r = evaluer_amplitude({"h": 1700.0, "l": 369.0}, "SOT", jour)
        assert r["statut"] == Amplitude.HORS_ENVELOPPE.value, jour


def test_bougie_120_80_n_est_plus_declaree_impossible():
    """Contre-exemple de la revue : licite sous le régime ±20 % de l'admission.

    L'ancienne règle la déclarait « amplitude impossible, mélange de bases ».

    ⚠️ Cette bougie tombe EXACTEMENT sur la borne, et la borne calculée en
    virgule flottante vaut 1.4999999999999998 quand le rapport vaut 1.5. Sans
    tolérance relative, une bougie pile à la limite réglementaire ressortait
    suspecte. Le contre-exemple visait juste deux fois.
    """
    r = evaluer_amplitude({"h": 120.0, "l": 80.0}, "XXX", "2026-07-01")
    assert r["rapport_h_l"] == pytest.approx(1.5)
    assert r["statut"] == Amplitude.INDETERMINE.value
    assert "AUCUNE conclusion" in r["motif"]


def test_borne_se_deduit_de_la_limite():
    """(1+s)/(1−s), calculée — jamais recopiée à la main."""
    assert borne_amplitude(0.10) == pytest.approx(1.10 / 0.90)
    assert borne_amplitude(0.20) == pytest.approx(1.50)
    assert borne_amplitude(0.06) == pytest.approx(1.06 / 0.94)


def test_amplitude_conforme_sous_tous_les_regimes():
    """En deçà du régime le plus strict, la conclusion ne dépend plus du régime."""
    r = evaluer_amplitude({"h": 103.0, "l": 100.0}, "XXX", "2026-07-01")
    assert r["statut"] == Amplitude.COMPATIBLE.value
    assert "Compatible ne veut pas dire conforme" in r["motif"]


def test_amplitude_suspecte_au_dela_de_tous_les_regimes():
    """4,607 : aucun régime connu ne la rend licite."""
    r = evaluer_amplitude({"h": 1700.0, "l": 369.0}, "SOT", SPLIT_SOT)
    assert r["statut"] == Amplitude.HORS_ENVELOPPE.value
    assert r["rapport_h_l"] == pytest.approx(4.607, abs=0.001)
    assert "N'établit NI la cause, NI une illégalité" in r["motif"]


def test_amplitude_ne_nomme_jamais_la_cause():
    """« Suspecte » qualifie l'amplitude, pas ce qui l'a produite.

    ⚠️ L'ancienne version concluait « la bougie mêle des prix de bases
    différentes » — un diagnostic de cause rendu par un contrôle de forme.
    """
    r = evaluer_amplitude({"h": 1700.0, "l": 369.0}, "SOT", SPLIT_SOT)
    texte = json.dumps(r, ensure_ascii=False).lower()
    for mot in ("base", "split", "opération", "ajust"):
        assert mot not in texte, f"le contrôle d'amplitude nomme une cause : {mot}"


def test_seuils_portent_leur_source_et_leur_niveau_de_preuve():
    """Une règle réglementaire sans source n'est pas vérifiable.

    ⚠️ Les seuils sont RELAYÉS par la revue et non vérifiés sur le texte
    original. Le dire est la condition pour s'en servir.
    """
    from regimes_variation import SOURCE_SEUILS
    assert SOURCE_SEUILS["verifie_sur_source_primaire"] is False
    assert SOURCE_SEUILS["en_vigueur_depuis"] == "2026-06-23"
    assert SOURCE_SEUILS["ce_qui_manque"]


def test_amplitude_non_evaluable_sur_valeur_absente():
    assert evaluer_amplitude({"h": 100.0, "l": None})["statut"] == \
        Amplitude.NON_EVALUABLE.value
    assert evaluer_amplitude({"h": 100.0, "l": 0})["statut"] == \
        Amplitude.NON_EVALUABLE.value


def test_non_concluant_ne_refuse_pas_l_indicateur():
    """Ignorer le régime n'est pas une preuve que la bougie est mauvaise.

    ⚠️ J'avais d'abord fait refuser l'indicateur sur « non concluant ». C'était
    convertir notre ignorance en verdict.
    """
    b = {"o": 100.0, "h": 120.0, "l": 80.0, "c": 110.0, "v": 500.0}
    dp, dq = tout_documente()
    v = juger(b, ticker="ZZZ", diag=dp, diag_qte=dq)
    assert evaluer_amplitude(b, "ZZZ", "2026-01-05")["statut"] == \
        Amplitude.INDETERMINE.value
    assert "indicateur" in v["admissible_pour"]


# ═══ D. ANALYSE ET EXÉCUTION SÉPARÉES ══════════════════════════════════════

def test_execution_exige_un_ajustement_documente():
    """Un ajustement PROBABLE ne suffit pas pour engager un montant."""
    v = juger(BOUGIE_SAINE, ticker="MNG", jour="2026-08-01")
    assert diagnostic_base("MNG")["niveau"] == Preuve.PROBABLE.value
    assert "prix_analyse" in v["admissible_pour"]     # l'analyse, oui
    assert "execution" not in v["admissible_pour"]    # l'exécution, non


def test_quantite_non_comparable_avant_une_operation():
    """Une opération change aussi le NOMBRE de titres.

    Avant le split MNG et sans ajustement documenté, la quantité n'est pas
    comparable — donc ni mesurable comme volume, ni utilisable en exécution.
    """
    inconnu = diagnostic_quantites("MNG")
    avant = quantite_comparable("MNG", "2026-01-05", inconnu)
    jour_j = quantite_comparable("MNG", "2026-07-27", inconnu)
    apres = quantite_comparable("MNG", "2026-08-01", inconnu)
    assert avant is not None and "2026-07-27" in avant
    assert jour_j is not None, "le jour de l'opération est le plus ambigu, pas le moins"
    assert apres is None


def test_quantite_comparable_si_les_QUANTITES_sont_documentees():
    """⚠️ C'est la preuve sur les QUANTITÉS qui lève la réserve, pas celle sur
    les prix. Une version antérieure acceptait le niveau des prix — la revue a
    relevé le raccourci."""
    doc = {**diagnostic_quantites("MNG"), "niveau": Preuve.DOCUMENTE.value}
    assert quantite_comparable("MNG", "2026-01-05", doc) is None


def test_une_preuve_sur_les_prix_ne_documente_pas_les_quantites():
    """Le point exact soulevé par la revue, isolé dans un test."""
    prix_documente = {**diagnostic_base("MNG"), "niveau": Preuve.DOCUMENTE.value}
    qte_inconnue = diagnostic_quantites("MNG")
    v = juger(BOUGIE_SAINE, ticker="MNG", jour="2026-01-05",
              diag=prix_documente, diag_qte=qte_inconnue)
    assert "volume" not in v["admissible_pour"]
    assert "base des quantités" in v["refus"]["volume"]


def test_les_deux_diagnostics_sont_publies_separement():
    for t in TITRES:
        d = charger(LOT1B, t)
        assert "diagnostic_base_prix" in d and "diagnostic_quantites" in d
        assert d["diagnostic_quantites"]["unite_etablie"] is False


def test_execution_n_exige_pas_des_prix_ajustes_mais_une_comptabilite_coherente():
    """§4 : ce qui est refusé, c'est le MÉLANGE, pas l'ajustement.

    Prix documentés + quantités documentées ⇒ accordé, que les prix soient
    ajustés ou non. Dès qu'un des deux côtés n'est pas établi, la comptabilité
    n'est pas cohérente.
    """
    dp, dq = tout_documente()
    assert comptabilite_coherente(dp, dq) is None
    inconnu_qte = diagnostic_quantites("ZZZ")
    motif = comptabilite_coherente(dp, inconnu_qte)
    assert motif and "quantités" in motif


def test_le_refus_d_execution_ne_se_prononce_pas_sur_le_remplissage():
    """L'admissibilité des données n'est pas la probabilité d'exécution."""
    motif = comptabilite_coherente(diagnostic_base("ADH"),
                                   diagnostic_quantites("ADH"))
    assert "liquidité" in motif and "protocole de backtest" in motif


def test_volume_mesure_nul_refuse_l_execution():
    """Aucune contrepartie constatée : on ne suppose pas un ordre exécuté."""
    dp, dq = tout_documente()
    v = juger({**BOUGIE_SAINE, "v": 0.0}, ticker="ZZZ", diag=dp, diag_qte=dq)
    assert "volume" in v["admissible_pour"]
    assert "execution_simulee" not in v["admissible_pour"]
    assert "aucune contrepartie" in v["refus"]["execution_simulee"]


def test_execution_accordee_quand_tout_est_reuni():
    """Le contrat doit rester ACCORDABLE — sinon il ne dit plus rien.

    ⚠️ Un contrat qui refuse tout est aussi inutile qu'un contrat qui accepte
    tout. Ce test prouve qu'il existe un cas passant.
    """
    dp, dq = tout_documente()
    v = juger(BOUGIE_SAINE, ticker="ZZZ", diag=dp, diag_qte=dq)
    assert v["admissible_pour"] == ["prix_analyse", "volume", "indicateur",
                                    "indicateur_exploratoire",
                                    "execution_simulee"], v["refus"]


def test_seance_non_negociee_refuse_l_execution():
    dp, dq = tout_documente()
    for statut in (Seance.SUSPENDUE, Seance.INCONNUE, Seance.MARCHE_FERME):
        v = juger(BOUGIE_SAINE, ticker="ZZZ", statut=statut, diag=dp, diag_qte=dq)
        assert "execution_simulee" not in v["admissible_pour"], statut


def test_chaque_refus_porte_un_motif_non_vide():
    """Une liste vide sans explication est inexploitable."""
    v = juger({"o": None, "h": None, "l": None, "c": None, "v": None})
    assert v["refus"], "aucun motif alors que tout est refusé"
    for usage, motif in v["refus"].items():
        assert isinstance(motif, str) and len(motif) > 15, (usage, motif)


# ═══ E. NIVEAUX DE PREUVE ══════════════════════════════════════════════════

@pytest.mark.parametrize("ticker", TITRES)
def test_niveau_de_preuve_declare(ticker):
    assert charger(LOT1B, ticker)["diagnostic_base_prix"]["niveau"] == NIVEAUX[ticker]


@pytest.mark.parametrize("ticker", TITRES)
def test_fait_hypothese_et_manque_sont_distincts(ticker):
    """Le fait observé, l'hypothèse et la pièce manquante ne se confondent plus."""
    d = charger(LOT1B, ticker)["diagnostic_base_prix"]
    assert d["fait_observe"] and d["ce_qui_manque"]
    if d["niveau"] != Preuve.INCONNU.value:
        assert d["hypothese"] and d["hypothese"] != d["fait_observe"]


def test_absence_au_registre_ne_vaut_pas_base_saine():
    """« Aucune opération connue » ne prouve rien — le défaut est « inconnu »."""
    d = diagnostic_base("ADH")
    assert d["niveau"] == Preuve.INCONNU.value
    assert "pas une preuve d'absence" in d["ce_qui_manque"]


def test_mng_n_est_plus_annonce_comme_ajuste_exactement_une_fois():
    """La continuité étaye l'hypothèse ; elle ne la démontre pas.

    ⚠️ Le lot 1B affirmait « ajusté une fois » comme un fait.
    """
    d = diagnostic_base("MNG")
    assert d["niveau"] == Preuve.PROBABLE.value
    assert "ne prouve pas" in d["ce_qui_manque"]


# ═══ F. SOT — MISE À L'ÉCART CONSERVATOIRE ═════════════════════════════════

def test_sot_jusqu_au_split_inclus_sans_aucun_usage():
    obs = charger(LOT1B, "SOT")["observations"]
    avant = [o for o in obs if o["date"] <= SPLIT_SOT]
    assert len(avant) == 487
    for o in avant:
        assert o["admissible_pour"] == [], f"SOT {o['date']}"


def test_sot_n_autorise_jamais_prix_ni_indicateur_ni_execution():
    """La mise à l'écart porte sur la SÉRIE : sa portée exacte n'est pas établie."""
    for o in charger(LOT1B, "SOT")["observations"]:
        assert "prix_analyse" not in o["admissible_pour"], o["date"]
        assert "indicateur" not in o["admissible_pour"], o["date"]
        assert "execution" not in o["admissible_pour"], o["date"]


def test_sot_bougie_du_split_relevee_a_la_main():
    obs = charger(LOT1B, "SOT")["observations"]
    b = next(o for o in obs if o["date"] == SPLIT_SOT)
    assert (b["ouverture"], b["plus_haut"], b["plus_bas"], b["cloture"]) == \
           (SOT_0505["o"], SOT_0505["h"], SOT_0505["l"], SOT_0505["c"])
    assert b["plus_bas"] <= b["ouverture"] <= b["plus_haut"]   # OHLC tenu
    assert b["amplitude"]["statut"] == Amplitude.HORS_ENVELOPPE.value


def test_une_seule_alerte_d_amplitude_sur_tout_le_lot():
    """Le contrôle ne disqualifie rien d'autre au passage."""
    trouvees = [(t, o["date"]) for t in TITRES
                for o in charger(LOT1B, t)["observations"]
                if o["amplitude"]["statut"] == Amplitude.HORS_ENVELOPPE.value]
    assert trouvees == [("SOT", SPLIT_SOT)], trouvees


def test_aucune_execution_accordee_dans_tout_le_lot():
    """Constat, pas objectif : aucune série ne porte de comptabilité établie."""
    for t in TITRES:
        for o in charger(LOT1B, t)["observations"]:
            assert "execution_simulee" not in o["admissible_pour"], (t, o["date"])


# ═══ G. LA COUCHE NE MODIFIE RIEN ══════════════════════════════════════════

@pytest.mark.parametrize("ticker", TITRES)
def test_aucune_valeur_modifiee(ticker):
    brut = charger(LOT1A, ticker)
    norm = charger(LOT1B, ticker)["observations"]
    assert len(brut) == len(norm) == LIGNES[ticker]
    for i, (b, o) in enumerate(zip(brut, norm)):
        assert str(b["d"])[:10] == o["date"], f"{ticker}[{i}]"
        assert b.get("o") == o["ouverture"], f"{ticker}[{i}]"
        assert b.get("h") == o["plus_haut"], f"{ticker}[{i}]"
        assert b.get("l") == o["plus_bas"], f"{ticker}[{i}]"
        assert b.get("c") == o["cloture"], f"{ticker}[{i}]"


@pytest.mark.parametrize("ticker", TITRES)
def test_volume_inconnu_ne_devient_jamais_zero(ticker):
    brut = charger(LOT1A, ticker)
    norm = charger(LOT1B, ticker)["observations"]
    for b, o in zip(brut, norm):
        if b.get("v") is None:
            assert o["volume"] is None and o["volume_etat"] == "inconnu"
        elif math.isfinite(b["v"]) and b["v"] >= 0:
            assert o["volume"] == float(b["v"])


@pytest.mark.parametrize("ticker", TITRES)
def test_empreinte_source_concorde(ticker):
    attendue = hashlib.sha256((LOT1A / f"{ticker}.json").read_bytes()).hexdigest()
    assert charger(LOT1B, ticker)["empreinte_source"] == attendue


def test_la_couche_livree_est_reproductible_par_le_code():
    """L'artefact commité doit être ce que le code produit aujourd'hui.

    ⚠️ CE TEST N'EST PAS CIRCULAIRE : il ne fabrique pas un attendu avec la
    fonction testée, il compare un ARTEFACT COMMITÉ à une régénération. Il
    comble un angle mort mesuré par mutation : seuil neutralisé, un seul test
    sur 46 tombait, les autres relisant un fichier déjà produit.
    """
    from normaliser import charger_calendrier, normaliser as regenerer
    cal = charger_calendrier()
    for ticker in TITRES:
        attendu = regenerer(ticker, cal)
        livre = charger(LOT1B, ticker)
        assert livre["observations"] == attendu["observations"], ticker
        assert livre["diagnostic_base_prix"] == attendu["diagnostic_base_prix"]


# ═══ H. CALENDRIER — L'IMMOBILITÉ DES COURS NE PROUVE PAS LA FERMETURE ═════

def test_le_14_aout_n_est_plus_declare_ferme_sur_des_cours_immobiles():
    """Défaut relevé : le raisonnement écarté était revenu sous forme de source."""
    cal = json.loads((RACINE / "pipeline" / "calendrier_bvc.json")
                     .read_text(encoding="utf-8"))
    j = cal["jours"]["2026-08-14"]
    assert j["statut"] == "non_confirme"
    assert j["source"] is None
    assert j["piece_qui_trancherait"]
    assert all(i["vaut_preuve"] is False for i in j["indices"])


def test_aucune_entree_fermee_ne_s_appuie_sur_des_prix():
    """Règle générale, pas seulement le cas du 14 août."""
    cal = json.loads((RACINE / "pipeline" / "calendrier_bvc.json")
                     .read_text(encoding="utf-8"))
    for jour, e in cal["jours"].items():
        if e["statut"] in ("ferme", "ouvert"):
            src = (e.get("source") or "").lower()
            assert src, f"{jour} : statut tranché sans source"
            assert "identiques" not in src, (
                f"{jour} : la fermeture est déduite de l'immobilité des cours")


def test_une_date_absente_du_calendrier_reste_indecise():
    """Absente ⇒ ni ouverte ni fermée. Le défaut ne penche d'aucun côté."""
    from normaliser import charger_calendrier, marche_ferme
    assert marche_ferme("2026-03-17", charger_calendrier()) is None


# ═══ I. MANIFESTE ══════════════════════════════════════════════════════════

def test_manifeste_1a_ne_dit_plus_donnees_brutes_fournisseur():
    m = json.loads((LOT1A / "MANIFESTE.json").read_text(encoding="utf-8"))
    assert "INSTANTANÉ" in m["_quoi"]
    assert "brutes fournisseur" in m["_ce_que_ce_n_est_pas"]
    assert len(m["_commit_depot"]) == 40
    for t, s in m["series"].items():
        assert len(s["commit_source_complet"]) == 40, t


# ═══ J. LE BILAN EST MESURÉ, PAS RECOPIÉ ═══════════════════════════════════

def test_le_bilan_publie_correspond_aux_artefacts():
    """⚠️ J'ai écrit « cinq titres sur sept » quand les fichiers en montraient six.

    Un chiffre énoncé de mémoire à côté d'un fichier qui dit autre chose. Le
    bilan est désormais généré ; ce test vérifie qu'il n'a pas vieilli.
    """
    from bilan_lot import mesurer, rendre
    publie = (RACINE / "docs" / "BILAN_LOT1B.md").read_text(encoding="utf-8")
    assert publie.strip() == rendre(mesurer()).strip(), (
        "docs/BILAN_LOT1B.md a vieilli — relancer pipeline/bilan_lot.py --ecrire")


def test_le_bilan_compte_les_titres_comme_les_fichiers():
    """Le comptage doit se déduire des artefacts, pas d'une constante."""
    from bilan_lot import mesurer
    m = mesurer()
    sans_publiable = sum(1 for t in TITRES
                         if not any("indicateur" in o["admissible_pour"]
                                    for o in charger(LOT1B, t)["observations"]))
    assert m["titres_sans_indicateur_publiable"] == sans_publiable
    assert m["titres"] == len(TITRES)


def test_aucun_document_n_annonce_un_compte_perime():
    """Garde-fou textuel contre la formulation exacte qui était fausse."""
    for chemin in ("ROADMAP.md", "docs/JOURNAL_TRANSFORMATIONS.md",
                   "docs/BILAN_LOT1B.md"):
        texte = (RACINE / chemin).read_text(encoding="utf-8").lower()
        assert "cinq titres sur sept" not in texte, chemin


def test_la_portee_sot_est_dite_sur_toute_la_serie():
    """⚠️ J'avais écrit « historique antérieur » alors que le contrat écarte tout."""
    obs = charger(LOT1B, "SOT")["observations"]
    assert all("prix_analyse" not in o["admissible_pour"] for o in obs)
    bilan = (RACINE / "docs" / "BILAN_LOT1B.md").read_text(encoding="utf-8")
    assert "toute la série" in bilan


# ═══ K. DÉFAUTS REPRODUITS PAR LA REVUE SUR LE LOT PRÉCÉDENT ═══════════════

def test_une_bougie_vide_n_est_pas_conforme():
    """⚠️ DÉFAUT RELEVÉ : une bougie sans AUCUN prix ressortait « conforme ».

    La liste des dépassements restait vide, faute de champ à examiner, et le
    code lisait cette absence comme une conformité. Ne rien examiner n'est pas
    constater une conformité — c'est ne rien constater.
    """
    r = evaluer_conformite({}, cours_reference=100.0, nom_regime="continu",
                           date_iso="2026-07-01")
    assert r["statut"] == Conformite.NON_VERIFIABLE.value
    assert r["champs_examines"] == []
    assert any("aucun prix exploitable" in m for m in r["ce_qui_manque"])


def test_une_bougie_partiellement_remplie_est_examinee_sur_ce_qu_elle_porte():
    """La garde ne doit pas refuser une bougie qui porte une clôture seule."""
    r = evaluer_conformite({"c": 102.0}, cours_reference=100.0,
                           nom_regime="continu", date_iso="2026-07-01")
    assert r["statut"] == Conformite.CONFORME.value
    assert r["champs_examines"] == ["cloture"]


def test_les_champs_examines_sont_publies():
    """Savoir SUR QUOI un verdict porte fait partie du verdict."""
    r = evaluer_conformite({"o": 100.0, "c": 102.0}, 100.0, "continu",
                           "2026-07-01")
    assert set(r["champs_examines"]) == {"ouverture", "cloture"}
