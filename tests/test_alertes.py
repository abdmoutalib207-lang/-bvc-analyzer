"""Les alertes (« red flags ») : calculées, expliquées, sans effet sur la note.

30/09/2026 — le terminal affichait un nombre tiré d'une table écrite à la
main, sans raison enregistrée : SRM y valait 4 quand le détecteur d'origine
(archive/bvc_analyzer_v51.py) n'en justifie qu'une. Attendus écrits à la main.
"""

from pathlib import Path

import pytest

SRC = (Path(__file__).resolve().parent.parent / "terminal.src.html").read_text(encoding="utf-8")


def test_chaque_alerte_porte_sa_raison_son_chiffre_et_son_seuil(ud):
    fiche = {"dette_nette_ebitda": 4.8, "roic": 8, "wacc": 10, "marge_nette": 22,
             "cash_conversion": 40, "source": "Zonebourse", "date_maj": "2026-06-18"}
    a = ud.detecter_alertes(fiche)
    assert a["evaluable"] and a["source"] == "Zonebourse" and a["date"] == "2026-06-18"
    assert [x["raison"] for x in a["liste"]] == [
        "Dette nette élevée", "La rentabilité du capital est inférieure à son coût"]
    assert a["liste"][0]["valeur"] == "4.8× l'EBITDA"
    assert a["liste"][1]["valeur"] == "ROIC 8 %" and "10 %" in a["liste"][1]["seuil"]


def test_rds_cumule_les_quatre_alertes(ud):
    fiche = {"dette_nette_ebitda": 33.0, "roic": 4, "wacc": 10,
             "marge_nette": 0.85, "cash_conversion": 30}
    a = ud.detecter_alertes(fiche)
    assert [x["niveau"] for x in a["liste"]] == ["critique", "élevé", "moyen", "moyen"]


def test_seuils_exclusifs(ud):
    """Au seuil exact, pas d'alerte — comme le détecteur d'origine."""
    a = ud.detecter_alertes({"dette_nette_ebitda": 3.0, "roic": 10, "wacc": 10,
                             "marge_nette": 3.0, "cash_conversion": 40}, rsi=80)
    assert a["evaluable"] and a["liste"] == []


def test_sans_fondamentaux_c_est_non_evaluable_et_pas_zero(ud):
    a = ud.detecter_alertes(None)
    assert a == {"evaluable": False, "liste": [], "source": None, "date": None}


def test_rsi_en_surchauffe(ud):
    a = ud.detecter_alertes({"roic": 15, "wacc": 10}, rsi=85.2)
    assert [x["theme"] for x in a["liste"]] == ["Technique"]


def test_le_terminal_n_affiche_plus_le_nombre_fige():
    assert "<RedFlags alertes={r.alertes}/>" in SRC
    assert "RedFlags n=" not in SRC
    assert "non évaluable" in SRC


def test_l_alerte_lit_le_ratio_des_comptes_publies(ud):
    """Audit externe du 01/10 : ADI affichait « dette critique 5,5× » (saisie)
    pendant que sa note lisait 2,26× (comptes 2025). Attendus à la main :
    2,26 < 3 → aucune alerte de dette ; ROIC 9,4 < WACC 10 → alerte."""
    fiche = {"dette_nette_ebitda": 5.5, "roic": 13, "wacc": 10, "cash_conversion": 80,
             "source": "IDBourse — vérifié 16/05/2026", "date_maj": "2026-09-29",
             "ratios_publies": {
                 "dette_nette_ebitda": {"valeur": 2.26, "date": "2025-12-31"},
                 "roic": {"valeur": 9.4, "date": "2025-12-31"}}}
    a = ud.detecter_alertes(fiche, sym="ADI")
    assert [x["raison"] for x in a["liste"]] == [
        "La rentabilité du capital est inférieure à son coût"]
    assert a["liste"][0]["valeur"] == "ROIC 9.4 %"
    assert a["liste"][0]["source"] == "calculé sur les comptes publiés"
    assert a["liste"][0]["date"] == "2025-12-31"


def test_msa_garde_sa_saisie_dans_l_alerte_comme_dans_la_note(ud):
    fiche = {"dette_nette_ebitda": 1.0, "roic": 8, "wacc": 10,
             "ratios_publies": {"roic": {"valeur": 47.6, "date": "2025-12-31"}}}
    a = ud.detecter_alertes(fiche, sym="MSA")
    assert a["liste"][0]["valeur"] == "ROIC 8 %"


def test_alertes_et_note_lisent_la_meme_valeur_sur_toute_la_cote(ud):
    """Invariant : pour chaque titre, le chiffre de dette affiché dans une
    alerte est celui que lit la note — jamais un autre."""
    import json
    from pipeline.smart_money.fond_score import ratio_effectif
    racine = Path(__file__).resolve().parent.parent
    fond = json.loads((racine / "fondamentaux.json").read_text(encoding="utf-8"))
    for s, f in fond.items():
        if not isinstance(f, dict):
            continue
        for x in ud.detecter_alertes(f, sym=s)["liste"]:
            if x["theme"] == "Structure financière":
                v = ratio_effectif(f, s, "dette_nette_ebitda")["valeur"]
                assert x["valeur"] == f"{v:g}× l'EBITDA", s
