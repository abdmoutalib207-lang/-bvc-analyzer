"""Note fondamentale par secteur (fantôme) — 30/09/2026.

Ce qui est vérifié : l'abstention remplace toute valeur supposée, la
rentabilité suit la famille, la valorisation est relative au secteur. Les
attendus sont calculés à la main ci-dessous, jamais par le module testé.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pipeline.smart_money import fond_score_sectoriel as fs  # noqa: E402


def _r(**kw):
    return {"ratios_publies": {k: {"valeur": v} for k, v in kw.items()}}


def test_familles():
    assert fs.famille("ATW", "Banque") == "banque"
    assert fs.famille("AFM", "Assurance") == "assurance"
    assert fs.famille("EQD", "Finance") == "credit"
    assert fs.famille("ARD", "Immobilier") == "fonciere"
    assert fs.famille("ADH", "Immobilier") == "autre"


def test_sans_donnee_pas_de_note():
    # Aucune donnée : pas de note, et surtout pas une note par défaut.
    assert fs.composantes("X", {}, {}, 100.0, "autre", 17.0) == {}
    assert fs.note({}) is None


def test_moins_de_la_moitie_du_poids_s_abstient():
    # Valorisation seule = 20 % du poids : insuffisant.
    comp = fs.composantes("X", {}, {"bpa_12m": 10.0}, 100.0, "autre", 10.0)
    assert set(comp) == {"valorisation"}
    assert fs.note(comp) is None


def test_poids_repartis_sur_les_criteres_presents():
    # ROIC 20 % → 8,5 ; PER 10 / médiane 10 = 1,0 → 7,0.
    # (0,40 × 8,5 + 0,20 × 7,0) ÷ 0,60 = (3,4 + 1,4) ÷ 0,6 = 8,0
    comp = fs.composantes("X", _r(roic=20.0), {"bpa_12m": 10.0}, 100.0, "autre", 10.0)
    assert comp["rentabilite"]["note"] == 8.5
    assert comp["valorisation"]["note"] == 7.0
    assert fs.note(comp) == 8.0


def test_banque_lit_le_roe_jamais_le_roic_ni_la_dette():
    fiche = _r(roic=30.0, roe_2025=15.0, dette_nette_ebitda=-1.0)
    comp = fs.composantes("B", fiche, {}, None, "banque", None)
    assert comp["rentabilite"]["mesure"] == "ROE 15.0 %"
    assert comp["rentabilite"]["note"] == 7.0
    assert "bilan" not in comp


def test_roe_12_mois_prefere_a_l_exercice():
    comp = fs.composantes("B", _r(roe_2025=5.0, roe_12m=20.0), {}, None, "banque", None)
    assert comp["rentabilite"]["note"] == 8.5


def test_perte_note_basse_sans_per():
    comp = fs.composantes("X", {}, {"bpa_12m": -3.0}, 100.0, "autre", 17.0)
    assert comp["valorisation"] == {"mesure": "perte sur 12 mois", "note": 1.5}


def test_croissance_seulement_si_depot_s1():
    saisie = {"croissance_bpa": 50.0, "croissance_ca": 50.0}
    assert "croissance" not in fs.composantes("X", saisie, {}, None, "autre", None)
    depot = dict(saisie, source_s1_2026="https://www.ammc.ma/x.pdf")
    # 0,6 × 50 + 0,4 × 50 = 50 → palier ≥ 50 : 9,0
    assert fs.composantes("X", depot, {}, None, "autre", None)["croissance"]["note"] == 9.0


def test_mediane_sectorielle_exige_trois_titres():
    bpa = {s: {"bpa_12m": 1.0} for s in "ABCDE"}
    prix = {"A": 10.0, "B": 20.0, "C": 30.0, "D": 40.0, "E": 50.0}
    sect = {"A": "S1", "B": "S1", "C": "S1", "D": "S2", "E": "S2"}
    med, marche = fs.medianes_per("ABCDE", bpa, prix, sect)
    assert marche == 30.0          # médiane de 10, 20, 30, 40, 50
    assert med["S1"] == 20.0       # 10, 20, 30
    assert med["S2"] == 30.0       # deux titres seulement : repli sur le marché
