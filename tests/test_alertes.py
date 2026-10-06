"""Les alertes (« red flags ») : calculées, expliquées, sans effet sur la note.

30/09/2026 — le terminal affichait un nombre tiré d'une table écrite à la
main, sans raison enregistrée : SRM y valait 4 quand le détecteur d'origine
(archive/bvc_analyzer_v51.py) n'en justifie qu'une. Attendus écrits à la main.

06/10/2026 — audit `verificateur-finance` : les alertes ne lisent plus QUE les
ratios calculés sur comptes publiés (`ratios_publies`). ADH affichait « Dette
nette élevée 4,8× » tiré de la saisie Zonebourse alors que son dépôt AMMC rend
l'EBITDA non calculable. Un ratio absent n'est pas évalué, il est nommé.
"""

from pathlib import Path

import pytest

SRC = (Path(__file__).resolve().parent.parent / "terminal.src.html").read_text(encoding="utf-8")


def _pub(**ratios):
    return {k: {"valeur": v, "date": "2025-12-31"} for k, v in ratios.items()}


def test_chaque_alerte_porte_sa_raison_son_chiffre_et_son_seuil(ud):
    fiche = {"source": "Zonebourse", "date_maj": "2026-06-18",
             "ratios_publies": dict(_pub(dette_nette_ebitda=4.8, roic=8, cash_conversion=40),
                                    calcule_le="2026-09-30")}
    a = ud.detecter_alertes(fiche, sym="X")
    assert a["evaluable"] and a["date"] == "2026-09-30"
    assert "comptes publiés" in a["source"] and "Zonebourse" not in a["source"]
    assert [x["raison"] for x in a["liste"]] == [
        "Dette nette élevée", "La rentabilité du capital est inférieure à son coût"]
    assert a["liste"][0]["valeur"] == "4.8× l'EBITDA"
    assert a["liste"][1]["valeur"] == "ROIC 8 %" and "10 %" in a["liste"][1]["seuil"]
    assert a["non_evalues"] == ["marge nette"]


def test_cas_adh_la_dette_saisie_ne_declenche_plus_rien(ud):
    """ADH : saisie 4,8× (Zonebourse), aucun dette/EBITDA calculé sur comptes.
    Calculés : ROIC 2,7 (< 10 → alerte), conversion −1,3 (< 40 → alerte),
    marge S1 21,2 (pas d'alerte). Attendus à la main."""
    fiche = {"dette_nette_ebitda": 4.8, "roic": 8, "marge_nette": 22, "cash_conversion": 40,
             "source": "Zonebourse / Boursenews", "date_maj": "2026-09-29",
             "ratios_publies": _pub(roic=2.7, cash_conversion=-1.3, marge_nette_s1_2026=21.2)}
    a = ud.detecter_alertes(fiche, sym="ADH")
    assert [x["raison"] for x in a["liste"]] == [
        "La rentabilité du capital est inférieure à son coût",
        "Le bénéfice se convertit mal en trésorerie"]
    assert not any("EBITDA" in x["valeur"] for x in a["liste"])
    assert a["non_evalues"] == ["dette nette / EBITDA"]


def test_une_saisie_seule_n_est_pas_evaluable(ud):
    fiche = {"dette_nette_ebitda": 33.0, "roic": 4, "marge_nette": 0.85,
             "cash_conversion": 30, "source": "Zonebourse"}
    a = ud.detecter_alertes(fiche, sym="X")
    assert a["evaluable"] is False and a["liste"] == []


def test_rds_cumule_les_quatre_alertes_sur_comptes(ud):
    fiche = {"ratios_publies": _pub(dette_nette_ebitda=33.0, roic=4,
                                    marge_nette_s1_2026=0.85, cash_conversion=30)}
    a = ud.detecter_alertes(fiche, sym="X")
    assert [x["niveau"] for x in a["liste"]] == ["critique", "élevé", "moyen", "moyen"]
    assert a["liste"][2]["valeur"] == "0.85 % (S1 2026)"
    assert a["non_evalues"] == []


def test_la_marge_saisie_n_est_pas_lue(ud):
    fiche = {"marge_nette": 0.85, "ratios_publies": _pub(roic=15)}
    a = ud.detecter_alertes(fiche, sym="X")
    assert a["liste"] == [] and "marge nette" in a["non_evalues"]


def test_seuils_exclusifs(ud):
    """Au seuil exact, pas d'alerte — comme le détecteur d'origine."""
    fiche = {"ratios_publies": _pub(dette_nette_ebitda=3.0, roic=10,
                                    marge_nette_s1_2026=3.0, cash_conversion=40)}
    a = ud.detecter_alertes(fiche, rsi=80, sym="X")
    assert a["evaluable"] and a["liste"] == []


def test_sans_fondamentaux_c_est_non_evaluable_et_pas_zero(ud):
    a = ud.detecter_alertes(None)
    assert a["evaluable"] is False and a["liste"] == [] and a["source"] is None


def test_rsi_en_surchauffe(ud):
    a = ud.detecter_alertes({"ratios_publies": _pub(roic=15)}, rsi=85.2, sym="X")
    assert [x["theme"] for x in a["liste"]] == ["Technique"]


def test_le_terminal_n_affiche_plus_le_nombre_fige():
    assert "<RedFlags alertes={r.alertes}/>" in SRC
    assert "RedFlags n=" not in SRC
    assert "non évaluable" in SRC
    assert "Chiffres saisis à la main : à recouper" not in SRC
    assert "a.non_evalues" in SRC


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
    # cash_conversion saisi à 80, non calculé : non évalué, pas « sain ».
    assert "conversion en trésorerie" in a["non_evalues"]


def test_msa_en_verification_n_est_pas_evaluee(ud):
    """MSA : ratio calculé encore en vérification (RATIOS_EN_VERIFICATION), et
    la saisie n'est plus lue → non évaluable, plutôt que l'ancienne saisie."""
    fiche = {"dette_nette_ebitda": 1.0, "roic": 8, "wacc": 10,
             "ratios_publies": {"roic": {"valeur": 47.6, "date": "2025-12-31"}}}
    a = ud.detecter_alertes(fiche, sym="MSA")
    assert a["evaluable"] is False and a["liste"] == []


def test_aucune_alerte_de_la_cote_ne_vient_de_la_saisie(ud):
    """Invariant sur fondamentaux.json : toute alerte fondamentale cite les
    comptes publiés, et son chiffre est celui de `ratios_publies`."""
    import json
    racine = Path(__file__).resolve().parent.parent
    fond = json.loads((racine / "fondamentaux.json").read_text(encoding="utf-8"))
    vus = 0
    for s, f in fond.items():
        if not isinstance(f, dict):
            continue
        for x in ud.detecter_alertes(f, sym=s)["liste"]:
            if x["theme"] == "Technique":
                continue
            vus += 1
            assert x["source"] == "calculé sur les comptes publiés", (s, x)
            if x["theme"] == "Structure financière":
                v = f["ratios_publies"]["dette_nette_ebitda"]["valeur"]
                assert x["valeur"] == f"{float(v):g}× l'EBITDA", s
    assert vus > 0


def test_le_bloc_data_plus_est_dit_non_verifie_et_sans_doublon_de_roe():
    assert "export IDBourse DATA+ du" in SRC and "non vérifié</div>" in SRC
    assert "...(roeCalc?[]:[[\"ROE 2025\"" in SRC
