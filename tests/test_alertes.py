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
