"""La couverture fondamentale doit mesurer les DONNÉES, pas les replis.

Ces tests n'imposent pas une note d'investissement. Ils empêchent seulement de
faire passer un champ absent pour un fondamental calculé et protègent le niveau
de couverture déjà atteint par les données AMMC validées.
"""
from pipeline.fundamental_coverage import coverage_for, build_report


def test_couverture_complete_exige_tous_les_champs():
    f = {
        "roic": 14, "wacc": 8,
        "croissance_bpa": 12, "croissance_ca": 9,
        "forward_per": 16,
        "dette_nette_ebitda": 1.2, "cash_conversion": 82,
    }
    c = coverage_for(f)
    assert c["coverage_pct"] == 100
    assert c["status"] == "COMPLET"
    assert c["blocks_missing"] == []


def test_absence_ne_devient_jamais_une_valeur_neutre():
    # Un forward PER seul couvre seulement le bloc valorisation (20 %).
    c = coverage_for({"forward_per": 15})
    assert c["coverage_pct"] == 20
    assert c["status"] == "PARTIEL"
    manquants = {x["bloc"] for x in c["blocks_missing"]}
    assert manquants == {"qualite", "croissance", "bilan"}


def test_fiche_vide_est_explicitement_insuffisante():
    c = coverage_for({})
    assert c["coverage_pct"] == 0
    assert c["status"] == "INSUFFISANT"


def test_le_projet_ne_regresse_pas_sur_la_couverture_deja_validee():
    r = build_report()
    s = r["summary"]
    # Relevé du 18/09/2026 avant ce lot : 34 fiches pleinement renseignées et
    # 29 P/Book calculés depuis des faits AMMC. Ces seuils peuvent monter, jamais
    # redescendre sans qu'un test rouge oblige à expliquer pourquoi.
    assert s["titres"] >= 80
    assert s["fondamentaux_complets"] >= 34
    assert s["pb_source"].get("faits_ammc", 0) >= 29
    assert s["source_fond"].get("bpa_calcule", 0) >= 57
