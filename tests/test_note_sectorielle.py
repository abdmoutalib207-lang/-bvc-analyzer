"""Note fondamentale PAR FAMILLE — publiée depuis le 10/10/2026.

Ce qui est vérifié : les familles sont des listes explicites ; chaque famille
lit ses indicateurs ; les garde-fous AFM / MSA ne sont plus contournés ; un
critère sans donnée s'abstient ; moins de la moitié du poids = pas de note ;
les paliers [G] sont ceux de la grille d'origine ; les poids des piliers ne
bougent pas ; un titre sans note ne reçoit jamais ACHETER ni ÉVITER.

Les attendus sont calculés à la main ci-dessous, jamais par le module testé.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import bvc_config  # noqa: E402
from pipeline.smart_money import fond_score as fg  # noqa: E402
from pipeline.smart_money import fond_score_sectoriel as fs  # noqa: E402


# ── fabriques ────────────────────────────────────────────────────────────

def _fiche(secteur="Industrie", s1=True, **ratios):
    """Une fiche de fondamentaux : les ratios sont des `ratios_publies`."""
    f = {"secteur": secteur, "ratios_publies": {k: {"valeur": v, "date": "2025-12-31"}
                                                for k, v in ratios.items()}}
    if s1:
        f["source_s1_2026"] = "https://www.ammc.ma/x.pdf"
    return f


def _entree(sym, fiche=None, bpa=None, s1=None, faits=None, prix=None, pb=None, **kw):
    return fs.construire_entree(sym, fiche, bpa, s1, faits, prix, pb, **kw)


def _med(per=None, pb=None, ve=None):
    """Valeurs de référence factices, au format de `calculer_medianes` :
    chaque ratio est {"marche": [valeurs], "famille": {famille: [valeurs]}}."""
    def bloc(x):
        x = x or {}
        return {"famille": {f: [(f"_{f}{i}", v) for i, v in enumerate(vs)]
                            for f, vs in x.get("famille", {}).items()},
                "marche": [(f"_m{i}", v) for i, v in enumerate(x.get("marche", []))]}
    return {"per": bloc(per), "pb": bloc(pb), "ve_ebitda": bloc(ve)}


# ── 1. familles : listes explicites ──────────────────────────────────────

def test_les_familles_sont_des_listes_explicites_sans_doublon():
    tous = [t for v in bvc_config.FAMILLES_NOTE.values() for t in v]
    assert len(tous) == len(set(tous)), "un titre est rangé dans deux familles"
    assert not [t for t in tous if t not in bvc_config.TICKERS_ALL], "ticker inconnu"
    assert {bvc_config.famille_note(t) for t in bvc_config.TICKERS_ALL} <= \
        set(bvc_config.FAMILLES_NOTE) | {bvc_config.FAMILLE_NOTE_PAR_DEFAUT}


@pytest.mark.parametrize("fam,titres", [
    ("banque", "ATW BCP BMC BOA CDM CFGB CIH"),
    ("assurance", "ATL WAF SAF"),
    ("financement", "EQD MGL MRL SLM"),
    ("paiement", "CASH"),
    ("holding", "REB"),
    ("fonciere", "ARD IMI BAL"),
    ("promoteur", "ADH ADI RDS"),
    ("btp", "JET SGTM TGCC"),
    ("mines", "CMT MNG SMI"),
    ("telecom", "IAM"),
    ("utility", "TQA"),
    # Courtiers : « Assurance » au référentiel, mais traités en services.
    ("autre", "AFM AGM DHO ZLD MSA CTM TMA GAZ"),
])
def test_affectation_des_familles(fam, titres):
    for t in titres.split():
        assert bvc_config.famille_note(t) == fam, t


def test_les_familles_ne_se_deduisent_pas_du_secteur():
    # « Immobilier » réunit foncières ET promoteurs ; « Finance » réunit crédit,
    # crédit-bail et paiement : le préfixe de secteur ne peut pas trancher.
    imm = {bvc_config.famille_note(t) for t, s in bvc_config.COMPANY_SECTORS.items() if s == "Immobilier"}
    fin = {bvc_config.famille_note(t) for t, s in bvc_config.COMPANY_SECTORS.items() if s == "Finance"}
    assert imm == {"fonciere", "promoteur"}
    assert {"financement", "paiement"} <= fin


# ── 2. paliers [G] épinglés sur la grille d'origine ─────────────────────

def _fond(fiche, **kw):
    return fg.compute_fond_score("ZZZ", {"ZZZ": fiche}, **kw)


@pytest.mark.parametrize("roic", [-8, -3.1, 6.99, 7, 9.99, 10, 11.99, 12, 14.99, 15, 19.99, 20, 24.99, 25, 60])
def test_palier_de_rentabilite_identique_a_la_grille_d_origine(roic):
    # Grille d'origine isolée : croissance 0 → 4,5 ; PER 15 → 7,0 ; bilan 7,0.
    # score = 0,4 q + 0,3 × 4,5 + 0,2 × 7,0 + 0,1 × 7,0 = 0,4 q + 3,45
    score = _fond({"ratios_publies": {"roic": {"valeur": roic}}})
    q = (score - 3.45) / 0.4
    assert fs.note_ecart_rentabilite(roic, fg.WACC_REF) == pytest.approx(q, abs=0.02)


@pytest.mark.parametrize("g", [-30, -10.01, -10, -0.4, 0, 0.1, 4.99, 5, 9.99, 10, 24.99, 25, 49.99, 50, 99.9, 100, 400])
def test_palier_de_croissance_identique_a_la_grille_d_origine(g):
    # q = 5,0 (ROIC absent → 10 → écart 0) ; v = 7,0 ; bs = 7,0
    score = _fond({"croissance_bpa": g, "croissance_ca": g})
    gg = (score - (0.4 * 5.0 + 0.2 * 7.0 + 0.1 * 7.0)) / 0.3
    assert fs.note_croissance(g) == pytest.approx(gg, abs=0.02)


@pytest.mark.parametrize("dne", [-2, -0.01, 0, 0.49, 0.5, 1.49, 1.5, 2.49, 2.5, 3.49, 3.5, 4.99, 5, 12])
@pytest.mark.parametrize("cc", [30, 70, 90])
def test_palier_de_bilan_identique_a_la_grille_d_origine(dne, cc):
    score = _fond({"ratios_publies": {"dette_nette_ebitda": {"valeur": dne},
                                      "cash_conversion": {"valeur": cc}}})
    bs = (score - (0.4 * 5.0 + 0.3 * 4.5 + 0.2 * 7.0)) / 0.1
    assert fs.note_bilan_industriel(dne, cc) == pytest.approx(bs, abs=0.1)


def test_le_saut_de_croissance_a_zero_est_un_palier_pas_un_defaut():
    # Signalé, laissé : le saut à zéro (−0,4 % → 3,0 ; +0,1 % → 4,5) vaut 1,5
    # point, comme ceux de +50 % et de −10 %. Une marche de l'échelle d'origine,
    # pas une anomalie documentable (spécification, point 4).
    assert fs.note_croissance(-0.4) == 3.0 and fs.note_croissance(0.1) == 4.5
    marches = {s: round(b - a, 2) for s, a, b in
               [(-10, fs.note_croissance(-10.01), fs.note_croissance(-10)),
                (0, fs.note_croissance(-0.01), fs.note_croissance(0)),
                (50, fs.note_croissance(49.99), fs.note_croissance(50))]}
    assert set(marches.values()) == {1.5}


@pytest.mark.parametrize("ratio,attendu", [
    (0.6, 9.5), (0.61, 8.5), (0.8, 8.5), (0.81, 7.0), (1.0, 7.0),
    (1.01, 5.5), (1.25, 5.5), (1.26, 4.0), (1.6, 4.0), (1.61, 2.5)])
def test_paliers_relatifs(ratio, attendu):
    assert fs.note_relatif(ratio) == attendu


# ── 3. garde-fous : une seule porte ──────────────────────────────────────

def test_afm_roe_sans_objet_n_est_plus_contourne():
    # Le module fantôme lisait `ratios_publies` en direct : AFM publiait 103,7.
    e = _entree("AFM", _fiche("Assurance", roe_2025=103.7, roe_12m=103.7),
                {"bpa_12m": 78.0, "rnpg_12m": 78.0}, {"capitaux_propres_pg_31_12_2025": 70.0,
                                                      "capitaux_propres_pg_30_06_2026": 75.0})
    assert e["roe"]["etat"] == fs.SUSPENDU and "sans objet" in e["roe"]["motif"]
    r = fs.noter(e, _med(per={"marche": [15.0] * 3}))
    assert "rentabilite" not in r["composantes"]
    assert r["criteres"]["rentabilite"]["etat"] == fs.SUSPENDU and r["criteres"]["rentabilite"]["poids_effectif"] == 0


def test_ratios_en_verification_ne_sont_pas_lus(monkeypatch):
    # Le module fantôme publiait un ROIC de 47,6 % pour MSA ; le titre a été
    # recoupé le 15/10/2026, le mécanisme est éprouvé sur une entrée d'essai.
    monkeypatch.setitem(fs.RATIOS_EN_VERIFICATION, "MSA", "motif d'essai")
    e = _entree("MSA", _fiche("Transport", roic=47.6, roe_2025=39.2, roe_12m=41.0,
                              dette_nette_ebitda=0.3, cash_conversion=167.0))
    assert e["roic"] is None and e["dne"] is None and e["cc"] is None
    assert e["roe"]["etat"] == fs.SUSPENDU
    comp = fs.noter(e, _med())["composantes"]
    assert "rentabilite" not in comp and "bilan" not in comp


def test_aucune_saisie_n_est_lue():
    # `ratio_effectif` retombe sur la saisie ; cette grille ne la lit pas.
    fiche = {"secteur": "Industrie", "roic": 30.0, "dette_nette_ebitda": 0.1,
             "cash_conversion": 200.0, "ratios_publies": {}}
    e = _entree("ALU", fiche)
    assert e["roic"] is None and e["dne"] is None and e["cc"] is None


def test_dette_nette_et_ebitda_passent_par_la_porte_unique(monkeypatch):
    # Relecture du 10/10/2026 : `construire_entree` lisait encore `ratios_publies`
    # en direct pour la dette nette et l'EBITDA. Un titre en vérification les aurait
    # fait entrer dans son bilan et dans un VE/EBITDA (essai sur MSA, recoupé le 15/10).
    monkeypatch.setitem(fs.RATIOS_EN_VERIFICATION, "MSA", "motif d'essai")
    msa = _dossier_ve("MSA")
    assert msa["gearing"] is None and msa["dette_nette"] is None
    assert msa["ve"]["etat"] == fs.ABSENT
    assert _dossier_ve("ALU")["ve"]["etat"] == fs.PRESENT


def test_aucun_acces_direct_a_ratios_publies_dans_le_code():
    import ast
    arbre = ast.parse(Path(fs.__file__).read_text(encoding="utf-8"))
    directs = [n.lineno for n in ast.walk(arbre)
               if isinstance(n, ast.Constant) and n.value == "ratios_publies"]
    assert not directs, f"lecture directe de ratios_publies (ligne {directs}) : passer par la porte unique"


# ── 4. exclusions ────────────────────────────────────────────────────────

def test_sans_comptes_n_a_pas_de_note_et_sort_des_medianes():
    e = _entree("IBM", _fiche(roic=20.0), {"bpa_12m": 5.0}, prix=100.0, sans_comptes=True)
    r = fs.noter(e, _med(per={"marche": [15.0] * 3}))
    assert r["note"] is None and r["composantes"] == {}
    assert e["hors_mediane"]


def test_fonds_propres_negatifs_sortent_des_medianes_mais_sont_notes():
    # STR, STK : fonds propres négatifs. Le titre garde ce que ses comptes disent
    # (ici une perte et une dette), mais son PER ne sert pas de référence aux pairs.
    faits = {"faits": {"capitaux_propres_consolides": {"valeur": -340.9}}}
    e = _entree("STR", _fiche(dette_nette_ebitda=9.4), {"bpa_12m": -10.86}, faits=faits, prix=153.0)
    assert e["hors_mediane"] == "fonds propres négatifs" and e["sans_note"] is None
    sains = [_entree(s, _fiche(), {"bpa_12m": 10.0}, prix=p) for s, p in (("AFI", 100.0), ("ALU", 200.0), ("CIM", 300.0))]
    med = fs.calculer_medianes(sains + [_entree("STK", _fiche(), {"bpa_12m": 1.0}, faits=faits, prix=1000.0)])
    assert sorted(v for _, v in med["per"]["marche"]) == [10.0, 20.0, 30.0], "le PER de STK (1000) fausserait la médiane"


def test_titre_suspendu_sort_des_medianes():
    e = _entree("CMT", _fiche(), {"bpa_12m": 10.0}, prix=50.0, suspendu=True)
    assert fs.calculer_medianes([e])["per"]["marche"] == []


# ── 5. abstention ────────────────────────────────────────────────────────

def test_sans_donnee_pas_de_note():
    e = _entree("ALU", {}, {}, prix=100.0)
    r = fs.noter(e, _med())
    assert r["note"] is None and r["composantes"] == {} and r["poids_disponible"] == 0


def test_moins_de_la_moitie_du_poids_s_abstient():
    # Valorisation seule = 20 % : insuffisant, même si le PER est excellent.
    e = _entree("ALU", {}, {"bpa_12m": 10.0}, prix=100.0)
    r = fs.noter(e, _med(per={"marche": [10.0] * 3}))
    assert set(r["composantes"]) == {"valorisation"} and r["poids_disponible"] == 20
    assert r["note"] is None and "Données" not in r["motif"] and "20" in r["motif"]


def test_la_moitie_exacte_du_poids_suffit():
    # croissance 30 + valorisation 20 = 50 : « moins de la moitié » est faux.
    e = _entree("ALU", _fiche(croissance_bpa=50.0, croissance_ca=50.0) | {"croissance_bpa": 50.0, "croissance_ca": 50.0},
                {"bpa_12m": 10.0}, prix=100.0)
    r = fs.noter(e, _med(per={"marche": [10.0] * 3}))
    assert r["poids_disponible"] == 50
    # croissance 50 → 9,0 ; PER 10 ÷ 10 = 1,0 → 7,0 ; (30×9 + 20×7) ÷ 50 = 8,2
    assert r["note"] == 8.2


def test_poids_repartis_sur_les_criteres_presents():
    # ROIC 20 → écart 10 → 8,5 ; PER 10 ÷ 10 = 1,0 → 7,0 ; (40×8,5 + 20×7,0) ÷ 60 = 8,0
    e = _entree("ALU", _fiche(roic=20.0), {"bpa_12m": 10.0}, prix=100.0)
    r = fs.noter(e, _med(per={"marche": [10.0] * 3}))
    assert r["composantes"]["rentabilite"]["note"] == 8.5
    assert r["composantes"]["valorisation"]["note"] == 7.0
    assert r["note"] == 8.0


def test_croissance_seulement_si_depot_s1():
    donnees = dict(croissance_bpa=50.0, croissance_ca=50.0)
    sans = _fiche(s1=False) | donnees
    avec = _fiche(s1=True) | donnees
    assert "croissance" not in fs.noter(_entree("ALU", sans), _med())["composantes"]
    # 0,6 × 50 + 0,4 × 50 = 50 → palier ≥ 50 : 9,0
    assert fs.noter(_entree("ALU", avec), _med())["composantes"]["croissance"]["note"] == 9.0


# ── 6. médianes ──────────────────────────────────────────────────────────

def test_la_reference_exclut_le_titre_note_leave_one_out():
    # Relecture du 10/10/2026 : un titre médian se comparait à lui-même (CMT
    # 22,7/22,7, ARD 1,00/1,00) et obtenait 7,0 par construction.
    famille = [_entree(s, _fiche("Banque"), {"bpa_12m": 1.0}, prix=p)
               for s, p in (("ATW", 10.0), ("BCP", 12.0), ("BOA", 14.0), ("CDM", 16.0))]
    med = fs.calculer_medianes(famille)
    # Médiane des 4 : 13,0. Sans ATW : 12, 14, 16 → 14,0 ; sans BOA : 10, 12, 16 → 12,0.
    assert fs._reference(med, "per", "banque", "ATW")[0] == 14.0
    assert fs._reference(med, "per", "banque", "BOA")[0] == 12.0
    # Le titre noté n'a PAS besoin d'être dans la liste : rien n'est exclu.
    assert fs._reference(med, "per", "banque", "CIH")[0] == 13.0
    # Le titre du milieu n'obtient plus 7,0 par construction.
    r = fs.noter(famille[1], med)["composantes"]["valorisation"]
    assert "autres titres de la famille" in r["mesure"] and "= 14.0" in r["mesure"]
    assert r["note"] == fs.note_relatif(12.0 / 14.0)                  # 0,857 → 7,0 ; recalculé, pas postulé
    assert fs.noter(famille[0], med)["composantes"]["valorisation"]["note"] == fs.note_relatif(10.0 / 14.0)  # 8,5


def test_moins_de_trois_pairs_la_reference_est_la_cote_entiere_etiquetee_non_sectorielle():
    banques = [_entree(s, _fiche("Banque"), {"bpa_12m": 1.0}, prix=p)
               for s, p in (("ATW", 10.0), ("BCP", 20.0), ("BOA", 30.0))]
    autres = [_entree(s, _fiche(), {"bpa_12m": 1.0}, prix=p)
              for s, p in (("AFI", 40.0), ("ALU", 50.0))]
    med = fs.calculer_medianes(banques + autres)
    # ATW : 2 pairs seulement (BCP, BOA) → cote entière hors ATW : 20, 30, 40, 50 → 35,0
    ref, lib, det = fs._reference(med, "per", "banque", "ATW")
    assert ref == 35.0 and "COTE ENTIÈRE hors ATW" in lib and "NON sectorielle" in lib
    assert det == {"type": "cote_entiere", "n": 4, "mediane": 35.0, "pairs_famille": 2}
    c = fs.noter(banques[0], med)["criteres"]["valorisation"]
    assert "NON sectorielle" in c["mesure"] and c["reference"]["type"] == "cote_entiere"
    # Un P/B ne se compare pas à la cote : pas de repli, abstention.
    assert fs._reference(med, "pb", "banque", "ATW", repli_marche=False) == (None, None, None)


def test_la_dependance_a_la_cote_est_mesuree_en_points_de_note():
    # Règle 6 : combien de points de note tiennent à une comparaison NON sectorielle ?
    banques = [_entree(s, _fiche("Banque", roe_2025=15.0) | {"croissance_bpa": 10.0, "croissance_ca": 10.0},
                       {"bpa_12m": 1.0}, prix=p) for s, p in (("ATW", 10.0), ("BCP", 20.0), ("BOA", 30.0))]
    autres = [_entree(s, _fiche(), {"bpa_12m": 1.0}, prix=p) for s, p in (("AFI", 40.0), ("ALU", 50.0))]
    med = fs.calculer_medianes(banques + autres)
    r = fs.noter(banques[0], med)
    d = r["dependance_cote"]
    assert d["criteres"] == ["valorisation"]
    # Avec la cote : PER 10 ÷ 35 = 0,29 → 9,5. Sans la cote : valorisation absente.
    # rentabilité ROE 15 → écart 5 → 7,0 ; croissance 10 → 6,5 ; (40×7 + 30×6,5 + 20×9,5) ÷ 90 = 7,39
    assert r["note"] == 7.39
    assert d["note_sans_cote"] == round((40 * 7.0 + 30 * 6.5) / 70, 2) == 6.79
    assert d["ecart_points"] == 0.6
    # Un titre noté contre ses pairs ne dépend pas de la cote.
    quatre = [_entree(s, _fiche("Banque"), {"bpa_12m": 1.0}, prix=p)
              for s, p in (("ATW", 10.0), ("BCP", 12.0), ("BOA", 14.0), ("CDM", 16.0))]
    assert fs.noter(quatre[0], fs.calculer_medianes(quatre))["dependance_cote"]["criteres"] == []


def test_les_poids_effectifs_apres_abstentions_somment_a_cent():
    e = _entree("ALU", _fiche(roic=20.0) | {"croissance_bpa": 5.0, "croissance_ca": 5.0}, {"bpa_12m": 10.0}, prix=100.0)
    r = fs.noter(e, _med(per={"marche": [10.0] * 3}))
    eff = {k: c["poids_effectif"] for k, c in r["criteres"].items()}
    assert eff == {"rentabilite": 44.44, "croissance": 33.33, "valorisation": 22.22, "bilan": 0.0}
    assert round(sum(eff.values())) == 100
    assert r["criteres"]["bilan"]["etat"] == fs.ABSENT and r["criteres"]["bilan"]["poids_nominal"] == 10


# ── 7. banques, assurances, financement, paiement ───────────────────────

def test_roe_une_seule_convention_exercice_2025_sur_cloture_etiquetee():
    # Règle 5 : ROE de l'EXERCICE 2025 ; fonds propres de clôture 31/12/2025
    # quand ceux de 2024 ne sont pas structurés ; la base est DITE.
    e = _entree("ATW", _fiche("Banque", roe_2025=15.3, roe_12m=14.0), {"bpa_12m": 5.0, "rnpg_12m": 1000.0},
                {"capitaux_propres_pg_30_06_2026": 6000.0})
    assert e["roe"]["etat"] == fs.PRESENT and e["roe"]["valeur"] == 15.3
    assert "CLÔTURE 31/12/2025" in e["roe"]["base"] and e["roe"]["periode"] == "exercice 2025"
    c = fs.noter(e, _med())["criteres"]["rentabilite"]
    assert c["base"] == e["roe"]["base"] and c["periode"] == "exercice 2025"
    assert c["note"] == 7.0                                       # écart 5,3 → 7,0


def test_roe_12_mois_est_un_remplacement_etiquete_jamais_un_melange_silencieux():
    e = _entree("ATW", _fiche("Banque", roe_12m=15.0))
    assert e["roe"]["etat"] == fs.REMPLACEMENT and "REMPLACEMENT" in e["roe"]["base"]
    c = fs.noter(e, _med())["criteres"]["rentabilite"]
    assert c["etat"] == fs.REMPLACEMENT and "12 mois" in c["periode"]
    # L'exercice prime : avec les deux, jamais le 12 mois.
    both = _entree("ATW", _fiche("Banque", roe_12m=15.0, roe_2025=9.0))
    assert both["roe"]["valeur"] == 9.0 and both["roe"]["etat"] == fs.PRESENT


def test_banque_ni_bilan_ni_roic_ni_dette():
    fiche = _fiche("Banque", roic=30.0, dette_nette_ebitda=-1.0, cash_conversion=50.0, roe_2025=15.0)
    e = _entree("ATW", fiche, {"bpa_12m": 5.0}, prix=60.0)
    r = fs.noter(e, _med(per={"marche": [12.0] * 3}))
    assert r["composantes"]["rentabilite"]["mesure"].startswith("ROE 15")
    assert "bilan" not in r["composantes"] and r["criteres"]["bilan"]["etat"] == fs.SUSPENDU


def test_banque_valorisation_per_relatif_a_la_famille():
    banques = [_entree(s, _fiche("Banque"), {"bpa_12m": 1.0}, prix=p)
               for s, p in (("ATW", 10.0), ("BCP", 12.0), ("BOA", 14.0))]
    med = fs.calculer_medianes(banques)
    e = _entree("CIH", _fiche("Banque"), {"bpa_12m": 1.0}, prix=18.0)
    # médiane 12 → 18 ÷ 12 = 1,5 → 4,0
    assert fs.noter(e, med)["composantes"]["valorisation"]["note"] == 4.0


def test_banque_pb_comptable_remplace_le_per_seulement_si_le_resultat_est_une_perte():
    famille = [_entree(s, _fiche("Banque"), {"bpa_12m": 1.0}, prix=10.0, pb=1.0) for s in ("ATW", "BCP", "BOA")]
    med = fs.calculer_medianes(famille)
    perte = _entree("CIH", _fiche("Banque"), {"bpa_12m": -2.0}, prix=10.0, pb=0.5)
    c = fs.noter(perte, med)["criteres"]["valorisation"]
    assert c["note"] == 9.5 and "P/B comptable" in c["mesure"] and c["etat"] == fs.REMPLACEMENT
    gain = _entree("CIH", _fiche("Banque"), {"bpa_12m": 1.0}, prix=10.0, pb=0.5)
    c = fs.noter(gain, med)["criteres"]["valorisation"]
    assert "PER" in c["mesure"] and c["pb_comptable_affiche"] == 0.5 and c["etat"] == fs.PRESENT
    inconnu = _entree("CIH", _fiche("Banque"), {}, prix=10.0, pb=0.5)       # absent ≠ perte
    assert fs.noter(inconnu, med)["criteres"]["valorisation"]["etat"] == fs.ABSENT


# ── 8. foncières et holding ──────────────────────────────────────────────

def _faits(pg, cons=None, **autres):
    f = {"capitaux_propres_part_groupe": {"valeur": pg}}
    if cons is not None:
        f["capitaux_propres_consolides"] = {"valeur": cons}
    f |= {k: {"valeur": v} for k, v in autres.items()}
    return {"exercice": 2025, "faits": f}


def _dossier_ve(titre="SMI", prix=100.0, endettement=None, cp30=None, actions=10_000_000,
                nb_actions=10_000_000, date_ebitda="2025-12-31", cons=2000.0, pg=2000.0, dn=1000.0,
                ebitda=500.0, exercice=2025):
    """Un dossier VE/EBITDA COHÉRENT, que chaque test dégrade d'une seule condition.
    VE = 100 × 10 M ÷ 1e6 (1 000) + 1 000 + 0 = 2 000 ; ÷ 500 = 4,0."""
    fiche = {"secteur": "Mines", "nb_actions": nb_actions, "source_s1_2026": "x",
             "ratios_publies": {"dette_nette": {"valeur": dn, "date": "2025-12-31"},
                                "ebitda": {"valeur": ebitda, "date": date_ebitda}}}
    faits = {"exercice": exercice, "faits": {}}
    if cons is not None:
        faits["faits"]["capitaux_propres_consolides"] = {"valeur": cons}
    if pg is not None:
        faits["faits"]["capitaux_propres_part_groupe"] = {"valeur": pg}
    if endettement is not None:
        faits["faits"]["endettement_net"] = {"valeur": endettement}
    s1 = {"actions": actions}
    if cp30 is not None:
        s1["capitaux_propres_pg_30_06_2026"] = cp30
    return _entree(titre, fiche, {"bpa_12m": 10.0}, s1, faits, prix, None)


def test_fonciere_p_b_comptable_jamais_utilisable_avec_trois_foncieres():
    # LIMITE ANNONCÉE (règle 2) : 3 foncières → 2 pairs chacune → le P/B ne
    # peut jamais contribuer. Avec ROE et bilan suspendus, il ne reste que la
    # croissance du CA (30 %) : PAS DE NOTE, et c'est le résultat attendu.
    fiches = {"ARD": 1.0, "IMI": 0.99, "BAL": 2.6}
    entrees = [_entree(s, _fiche(roe_2025=9.0) | {"croissance_bpa": -44.0, "croissance_ca": 27.5},
                       {"bpa_12m": 1.0}, prix=10.0, pb=pb) for s, pb in fiches.items()]
    med = fs.calculer_medianes(entrees)
    for e in entrees:
        r = fs.noter(e, med)
        c = r["criteres"]
        assert c["valorisation"]["etat"] == fs.ABSENT and "actif net réévalué non disponible" in c["valorisation"]["motif"]
        assert c["croissance"]["note"] == 7.5 and "BPA exclu" in c["croissance"]["mesure"]
        if e["sym"] == "BAL":
            # 27/10/2026 : BAL tient ses immeubles au COÛT HISTORIQUE (registre METHODE_COMPTABLE,
            # RFA 2025 p.47) — son ROE est noté ; ROE 40 + croissance 30 = 70 ≥ 50 : une note.
            assert c["rentabilite"]["etat"] == fs.PRESENT and c["rentabilite"]["valeur"] == 9.0
            assert c["rentabilite"]["methode_comptable"]["immeubles_placement"] == "cout"
            assert r["poids_disponible"] == 70 and r["note"] is not None
            continue
        assert c["rentabilite"]["etat"] == fs.SUSPENDU and "juste valeur" in c["rentabilite"]["motif"]
        assert c["rentabilite"]["valeur"] == 9.0                    # affiché, non noté
        assert r["poids_disponible"] == 30 and r["note"] is None
    # Avec 4 foncières, le P/B contribuerait (3 pairs) : la règle est le nombre de pairs.
    quatre = entrees + [_entree("REB", _fiche(roe_2025=9.0), {"bpa_12m": 1.0}, prix=10.0, pb=1.0)]
    for e in quatre:
        e["famille"] = "fonciere"
    med4 = fs.calculer_medianes(quatre)
    assert fs.noter(quatre[0], med4)["criteres"]["valorisation"]["etat"] == fs.PRESENT


def test_p_b_ne_s_appelle_jamais_p_anr():
    import re
    src = Path(fs.__file__).read_text(encoding="utf-8")
    assert "P/B comptable" in src
    # « P/ANR » n'apparaît que pour dire qu'on ne le dit pas.
    for m in re.finditer(r"P/ANR", src):
        assert "jamais" in src[max(0, m.start() - 40): m.end() + 5]


def test_dette_nette_sur_fonds_propres_est_affichee_non_notee():
    # Règle 1 : aucun barème sourcé ; 100 % des fonds propres ne vaut pas 7/10.
    fiche = _fiche(roe_2025=5.0)
    fiche["ratios_publies"]["dette_nette"] = {"valeur": 1000.0, "date": "2025-12-31"}
    e = _entree("ADH", fiche, {"bpa_12m": 1.0}, faits=_faits(1000.0, 1000.0), prix=30.0, pb=1.2)
    b = fs.noter(e, _med(per={"marche": [24.0] * 3}))["criteres"]["bilan"]
    assert b["etat"] == fs.SUSPENDU and b["valeur"] == 1.0 and b["note"] is None and b["poids_effectif"] == 0
    assert "affiché, non noté" in b["mesure"] and "barème" in b["motif"]
    assert "bilan" not in fs.noter(e, _med(per={"marche": [24.0] * 3}))["composantes"]


def test_gearing_exige_la_meme_date_pour_la_dette_et_les_fonds_propres():
    fiche = _fiche(roe_12m=9.0)
    fiche["ratios_publies"]["dette_nette"] = {"valeur": 100.0, "date": "2026-06-30"}
    e = _entree("ARD", fiche, faits=_faits(1000.0))
    assert e["gearing"] is None


def test_holding_seule_de_sa_famille_ne_peut_pas_etre_valorisee_par_pb():
    e = _entree("REB", _fiche(), {"bpa_12m": 3.8}, prix=100.0, pb=0.67)
    r = fs.noter(e, fs.calculer_medianes([e]))
    c = r["criteres"]["valorisation"]
    assert c["etat"] == fs.ABSENT and c["valeur"] == 0.67 and "P/B comptable" in c["mesure"]


# ── 9. promoteurs ────────────────────────────────────────────────────────

def test_promoteur_roe_pas_roic_valorisation_per_p_b_affiche():
    fiche = _fiche(roic=30.0, roe_2025=5.0, dette_nette_ebitda=9.0, cash_conversion=-5.0)
    e = _entree("ADH", fiche, {"bpa_12m": 1.2}, prix=30.0, pb=1.27)
    r = fs.noter(e, _med(per={"marche": [24.0] * 3}))
    assert r["composantes"]["rentabilite"]["mesure"].startswith("ROE 5")
    assert r["composantes"]["rentabilite"]["note"] == 2.0       # écart −5 → 2,0
    v = r["criteres"]["valorisation"]
    assert "PER" in v["mesure"] and v["pb_comptable_affiche"] == 1.27


# ── 10. mines et VE/EBITDA ───────────────────────────────────────────────

def test_ve_ebitda_entre_dans_la_note_quand_tout_est_coherent_et_verifie():
    e = _dossier_ve()
    assert e["ve"]["etat"] == fs.PRESENT and e["ve"]["valeur"] == 4.0
    r = fs.noter(e, _med(ve={"marche": [8.0] * 3}))
    c = r["criteres"]["valorisation"]
    assert c["etat"] == fs.PRESENT and c["note"] == 9.5 and "VE/EBITDA" in c["mesure"]     # 4 ÷ 8 = 0,5


@pytest.mark.parametrize("kw,motif", [
    ({"date_ebitda": "2024-12-31"}, "périodes différentes"),
    ({"endettement": 1500.0}, "contredite par l'endettement net"),
    ({"actions": 9_000_000}, "nombre d'actions discordant"),
    ({"cp30": 2100.0}, "bilan plus récent"),
    ({"ebitda": -5.0}, "EBITDA non positif"),
    ({"cons": 1900.0}, "minoritaires négatifs"),
])
def test_ve_ebitda_est_suspendu_si_une_condition_de_coherence_manque(kw, motif):
    e = _dossier_ve(**kw)
    assert e["ve"]["etat"] == fs.SUSPENDU and motif in e["ve"]["motif"]
    # Mines : critère SUSPENDU, aucun repli vers le PER (règle générale).
    r = fs.noter(e, _med(ve={"marche": [8.0] * 3}, per={"marche": [10.0] * 3}))
    c = r["criteres"]["valorisation"]
    assert c["etat"] == fs.SUSPENDU and c["note"] is None and c["poids_effectif"] == 0
    assert "valorisation" not in r["composantes"], "aucun repli vers le PER"


def test_ve_ebitda_dette_recoupee_dans_la_tolerance_est_acceptee():
    assert _dossier_ve(endettement=1015.0)["ve"]["etat"] == fs.PRESENT       # 1,5 % d'écart
    assert _dossier_ve(endettement=1000.0)["ve"]["etat"] == fs.PRESENT


def test_managem_dette_nette_contredite_par_l_endettement_net_est_suspendu():
    # Chiffres réels : dette nette 10 933,2 (ratios publiés) contre endettement
    # net 12 674,0 (faits) — non rapprochables sur les données disponibles.
    e = _dossier_ve("MNG", dn=10933.2, endettement=12674.0, ebitda=5982.0, cons=12529.6, pg=11478.3)
    assert e["ve"]["etat"] == fs.SUSPENDU
    assert "10933.2" in e["ve"]["motif"] and "12674" in e["ve"]["motif"] and "13.7%" in e["ve"]["motif"]


def test_aucune_affirmation_sur_ebitda_et_resultat_net():
    # Le 11/10 : « EBITDA 2025 < RNPG 12 mois » ne prouve rien (périodes,
    # périmètres, exceptionnels) et n'est plus avancé comme une anomalie.
    src = Path(fs.__file__).read_text(encoding="utf-8")
    assert "surestimé" not in src
    fiche = {"secteur": "Mines", "nb_actions": 10_000_000, "source_s1_2026": "x",
             "ratios_publies": {"dette_nette": {"valeur": 1000.0, "date": "2025-12-31"},
                                "ebitda": {"valeur": 500.0, "date": "2025-12-31"}}}
    bpa = {"bpa_12m": 10.0, "rnpg_12m": 9999.0}                 # RNPG 12 mois >> EBITDA
    faits = _faits(2000.0, 2000.0)
    e = _entree("SMI", fiche, bpa, {"actions": 10_000_000}, faits, 100.0, None)
    assert e["ve"]["etat"] == fs.PRESENT and "anomalie" not in e["ve"]


def test_mines_sans_ebitda_pas_de_repli_sur_le_per():
    e = _entree("CMT", _fiche(roic=20.0), {"bpa_12m": 10.0}, prix=100.0)
    assert e["ve"]["etat"] == fs.ABSENT
    r = fs.noter(e, _med(per={"marche": [10.0] * 3}))
    assert r["criteres"]["valorisation"]["etat"] == fs.ABSENT and "valorisation" not in r["composantes"]


def test_les_medianes_ve_n_acceptent_que_les_dossiers_coherents():
    bons = [_dossier_ve(t) for t in ("SMI", "ALU", "CIM")]
    mauvais = _dossier_ve("MNG", endettement=5000.0)
    med = fs.calculer_medianes(bons + [mauvais])
    assert sorted(t for t, _ in med["ve_ebitda"]["marche"]) == ["ALU", "CIM", "SMI"]


# ── 10 bis. trois états distincts : absent, zéro confirmé, remplacement ──

def test_minoritaires_inconnus_ne_valent_pas_zero():
    # Règle 3 : si les fonds propres consolidés manquent, les minoritaires sont
    # ABSENTS — jamais 0 — et le VE/EBITDA n'est pas calculé.
    e = _dossier_ve(cons=None)
    assert e["ve"]["etat"] == fs.ABSENT and "absent n'est pas zéro" in e["ve"]["motif"]
    assert "valeur" not in e["ve"]


def test_minoritaires_nuls_sur_piece_sont_un_zero_confirme():
    e = _dossier_ve(cons=2000.0, pg=2000.0)
    assert e["ve"]["minoritaires"] == 0.0 and e["ve"]["minoritaires_etat"] == fs.ZERO
    e2 = _dossier_ve(cons=2100.0, pg=2000.0)
    assert e2["ve"]["minoritaires"] == 100.0 and e2["ve"]["minoritaires_etat"] == fs.PRESENT
    assert "-0" not in e["ve"]["mesure"]


def test_dette_ebitda_zero_confirme_contre_absent():
    zero = _entree("CIM", _fiche(dette_nette_ebitda=0.0), {})
    assert fs.noter(zero, _med())["criteres"]["bilan"]["etat"] == fs.ZERO
    assert fs.noter(zero, _med())["criteres"]["bilan"]["note"] == 8.5      # 0 < 0,5
    absent = _entree("CIM", _fiche(), {})
    b = fs.noter(absent, _med())["criteres"]["bilan"]
    assert b["etat"] == fs.ABSENT and b["note"] is None and b["valeur"] is None


def test_tresorerie_nette_sans_ebitda_est_une_categorie_jamais_un_multiple():
    fiche = _fiche(roic=12.0)
    fiche["ratios_publies"]["dette_nette"] = {"valeur": -22.5, "date": "2025-12-31"}
    b = fs.noter(_entree("DAR", fiche), _med())["criteres"]["bilan"]
    assert b["etat"] == fs.REMPLACEMENT and b["valeur"] is None, "aucun multiple affiché"
    assert "trésorerie nette" in b["mesure"] and "-1" not in b["mesure"].replace("-22.5", "")
    assert b["note"] == 9.0 and "catégorie" in b["base"]


def test_croissance_zero_sur_piece_est_un_zero_confirme_pas_une_absence():
    # 0,0 publié : valeur. Aucune croissance : absent. Jamais confondus.
    zero = _entree("ALU", _fiche() | {"croissance_bpa": 0.0, "croissance_ca": 0.0})
    c = fs.noter(zero, _med())["criteres"]["croissance"]
    assert c["etat"] == fs.PRESENT and c["valeur"] == 0.0 and c["note"] == 4.5
    absent = fs.noter(_entree("ALU", _fiche()), _med())["criteres"]["croissance"]
    assert absent["etat"] == fs.ABSENT and absent["valeur"] is None and absent["note"] is None


def test_resultat_12_mois_nul_est_un_zero_confirme_et_absent_n_est_pas_une_perte():
    nul = fs.noter(_entree("ALU", _fiche(), {"bpa_12m": 0.0}, prix=100.0), _med(per={"marche": [10.0] * 3}))
    assert nul["criteres"]["valorisation"]["etat"] == fs.ZERO and "nul" in nul["criteres"]["valorisation"]["mesure"]
    inconnu = fs.noter(_entree("ALU", _fiche(), {}, prix=100.0), _med(per={"marche": [10.0] * 3}))
    assert inconnu["criteres"]["valorisation"]["etat"] == fs.ABSENT


def test_chaque_critere_porte_etat_source_periode_poids_et_reference():
    e = _entree("ALU", _fiche(roic=20.0, dette_nette_ebitda=1.0) | {"croissance_bpa": 5.0, "croissance_ca": 5.0},
                {"bpa_12m": 10.0, "fin_12m": "2026-06-30", "source_12m": "S1 2026"}, prix=100.0)
    r = fs.noter(e, _med(per={"marche": [10.0] * 3}))
    for nom, c in r["criteres"].items():
        assert {"etat", "valeur", "source", "periode", "base", "poids_nominal", "poids_effectif",
                "reference", "note", "motif"} <= set(c), nom
        assert c["etat"] in (fs.PRESENT, fs.ABSENT, fs.ZERO, fs.REMPLACEMENT, fs.SUSPENDU)
    assert r["criteres"]["valorisation"]["reference"]["type"] == "cote_entiere"
    assert r["criteres"]["valorisation"]["periode"] == "12 mois au 2026-06-30"
    assert r["criteres"]["rentabilite"]["source"]["fichier"].startswith("fondamentaux.json")


# ── 11. grille d'origine pour industrie, BTP, télécom, utility ─────────

def test_industrie_roic_per_relatif_dette_ebitda_conversion():
    fiche = _fiche(roic=25.0, dette_nette_ebitda=0.3, cash_conversion=150.0)
    e = _entree("IAM", fiche, {"bpa_12m": 10.0}, prix=100.0)
    r = fs.noter(e, _med(per={"marche": [10.0] * 3}))
    assert r["composantes"]["rentabilite"]["note"] == 9.5       # écart 15
    assert r["composantes"]["bilan"]["note"] == 9.0             # 8,5 + 0,5 (conversion ≥ 85)
    assert r["composantes"]["valorisation"]["note"] == 7.0      # 1,0


def test_tresorerie_nette_sans_ebitda_vaut_le_meilleur_bilan():
    fiche = _fiche(roic=12.0)
    fiche["ratios_publies"]["dette_nette"] = {"valeur": -22.5, "date": "2025-12-31"}
    assert fs.noter(_entree("DAR", fiche), _med())["composantes"]["bilan"]["note"] == 9.0


def test_perte_hors_banque_note_basse_sans_per():
    e = _entree("ALU", _fiche(), {"bpa_12m": -3.0}, prix=100.0)
    assert fs.noter(e, _med(per={"marche": [17.0] * 3}))["composantes"]["valorisation"] == {
        "mesure": "perte sur 12 mois", "note": 1.5, "poids": 20}


def test_rentabilite_roe_a_defaut_de_roic_est_etiquetee():
    e = _entree("TMA", _fiche(roe_12m=47.0))
    c = fs.noter(e, _med())["composantes"]["rentabilite"]
    assert c["note"] == 9.5 and "ROE à défaut" in c["mesure"]


# ── 12. le dividende n'entre dans aucun critère ─────────────────────────

def test_le_dividende_ne_change_pas_la_note():
    base = _fiche("Banque", roe_12m=15.0) | {"croissance_bpa": 10.0, "croissance_ca": 10.0}
    def note(div):
        f = dict(base) | {"div_yield": div, "dps_2025": div, "dps_2026": div, "dy_24": div}
        b = {"bpa_12m": 5.0, "div_dh": div, "dividende_exceptionnel": div * 10}
        return fs.noter(_entree("ATW", f, b, prix=60.0), _med(per={"marche": [12.0] * 3}))["note"]
    assert note(0.0) == note(25.0) == note(900.0)


# ── 13. grandeur contestée ⇒ tout critère qui la consomme est suspendu ──────

def _fiche_dn(dn=1000.0, roic=15.0, dne=2.0, ebitda=500.0, roe_2025=None, secteur="Mines"):
    """Une fiche dont ROIC et dette/EBITDA CITENT la dette nette dans leurs pièces."""
    rp = {"dette_nette": {"valeur": dn, "date": "2025-12-31"},
          "ebitda": {"valeur": ebitda, "date": "2025-12-31"},
          "roic": {"valeur": roic, "date": "2025-12-31", "sources": {"dette_nette": "ratios_publies.dette_nette"}},
          "dette_nette_ebitda": {"valeur": dne, "date": "2025-12-31",
                                 "sources": {"dette_nette": "ratios_publies.dette_nette", "ebitda": "ratios_publies.ebitda"}}}
    if roe_2025 is not None:
        rp["roe_2025"] = {"valeur": roe_2025, "date": "2025-12-31"}
    return {"secteur": secteur, "source_s1_2026": "x", "nb_actions": 10_000_000, "ratios_publies": rp,
            "croissance_bpa": 10.0, "croissance_ca": 10.0}


def _entree_dn(sym, endettement, **kw):
    return _entree(sym, _fiche_dn(**kw), {"bpa_12m": 10.0}, {"actions": 10_000_000},
                   _faits(2000.0, 2000.0, endettement_net=endettement), 100.0, None)


def test_dette_nette_contestee_suspend_roic_dette_ebitda_et_ve():
    e = _entree_dn("SMI", 1500.0, roe_2025=20.0)                    # 1 000 contre 1 500 : 33 %
    assert "grandeur contestée" in e["dette_nette_contestee"]
    r = fs.noter(e, _med(per={"marche": [10.0] * 3}))
    for nom in ("rentabilite", "bilan", "valorisation"):
        c = r["criteres"][nom]
        assert c["etat"] == fs.SUSPENDU and c["note"] is None and c["poids_effectif"] == 0, nom
    assert "grandeur contestée" in r["criteres"]["rentabilite"]["motif"]
    assert r["criteres"]["rentabilite"]["valeur"] == 15.0 and "affiché, non noté" in r["criteres"]["rentabilite"]["mesure"]
    assert "grandeur contestée" in r["criteres"]["bilan"]["motif"] and r["criteres"]["bilan"]["valeur"] == 2.0
    # Le ROE ne remplace JAMAIS un ROIC contesté (même s'il existe).
    assert r["criteres"]["rentabilite"]["etat"] == fs.SUSPENDU


def test_dette_nette_recoupee_ne_suspend_rien():
    e = _entree_dn("SMI", 1010.0)                                   # 1 % : dans la tolérance
    assert e["dette_nette_contestee"] is None
    r = fs.noter(e, _med(per={"marche": [10.0] * 3}))
    assert r["criteres"]["rentabilite"]["etat"] == fs.PRESENT and r["criteres"]["bilan"]["etat"] == fs.PRESENT


def test_dette_nette_contestee_s_applique_a_toutes_les_familles_qui_la_consomment():
    # Famille « autre » : ROIC et dette/EBITDA ; promoteur : le bilan DN/FP.
    r = fs.noter(_entree_dn("ALU", 1500.0), _med(per={"marche": [10.0] * 3}))
    assert r["criteres"]["rentabilite"]["etat"] == fs.SUSPENDU and r["criteres"]["bilan"]["etat"] == fs.SUSPENDU
    prom = _entree_dn("ADI", 1500.0, roe_2025=10.0)
    p = fs.noter(prom, _med(per={"marche": [10.0] * 3}))
    assert p["criteres"]["rentabilite"]["etat"] == fs.PRESENT, "le ROE d'un promoteur ne consomme pas la dette"
    assert "grandeur contestée" in p["criteres"]["bilan"]["motif"]


def test_ratio_qui_ne_cite_pas_la_dette_nette_n_est_pas_suspendu():
    fiche = _fiche_dn()
    fiche["ratios_publies"]["roic"].pop("sources")
    e = _entree("SMI", fiche, {"bpa_12m": 10.0}, {"actions": 10_000_000},
                _faits(2000.0, 2000.0, endettement_net=1500.0), 100.0, None)
    assert fs.noter(e, _med())["criteres"]["rentabilite"]["etat"] == fs.PRESENT


def test_aucun_critere_ne_reste_note_sur_une_grandeur_contestee_dans_les_donnees_reelles():
    # Invariant sur les 80 titres réels : si la dette nette est contestée, ni le
    # ROIC ni la dette/EBITDA qui la citent ne sont notés.
    res = fs.noter_depuis_fichiers()
    contestes = [s for s, r in res.items() if r["entree"]["dette_nette_contestee"]]
    assert contestes, "le recoupement dette nette / endettement net doit échouer pour au moins un titre"
    for s in contestes:
        r = res[s]
        e = r["entree"]
        if e["roic"] and fs._consomme_dette_nette(e["roic"]) and r["famille"] not in (
                "banque", "assurance", "financement", "paiement", "fonciere", "holding", "promoteur"):
            assert r["criteres"]["rentabilite"]["etat"] == fs.SUSPENDU, s
        if r["famille"] not in ("banque", "assurance", "financement", "paiement"):
            assert r["criteres"]["bilan"]["etat"] == fs.SUSPENDU, s


# ── 14. remplacement de la valorisation : règle de FAMILLE ────────────────

BPA_VERIFIE = {"bpa_12m": 10.0, "fin_12m": "2026-06-30", "source_12m": "S1 : https://www.ammc.ma/x.pdf p.1"}


def _mine(sym, endettement=None, ebitda=500.0, bpa=None):
    fiche = _fiche_dn(ebitda=ebitda) if ebitda else _fiche(roic=15.0)
    return _entree(sym, fiche, bpa if bpa is not None else BPA_VERIFIE, {"actions": 10_000_000},
                   _faits(2000.0, 2000.0, **({"endettement_net": endettement} if endettement else {})),
                   100.0, None)


def test_le_per_remplace_la_valorisation_suspendue_par_regle_de_famille():
    med = _med(per={"marche": [20.0] * 3}, ve={"marche": [8.0] * 3})
    for sym, endett in (("MNG", 1500.0), ("CMT", None)):             # VE contesté ; VE sans EBITDA
        e = _mine(sym, endettement=endett, ebitda=500.0 if sym == "MNG" else None)
        v = fs.noter(e, med)["criteres"]["valorisation"]
        assert v["etat"] == fs.REMPLACEMENT, sym
        assert "REMPLACEMENT du VE/EBITDA" in v["mesure"] and "règle de famille « mines »" in v["mesure"]
        assert v["reference"]["type"] == "cote_entiere" and "BPA vérifié" in v["base"]
        assert v["note"] == fs.note_relatif(10.0 / 20.0)            # PER 10 ÷ 20 = 0,5
    # Une famille hors de la table n'a AUCUN remplacement.
    pose = {}
    fs._remplacer_par_per(_mine("IAM"), "telecom", med, True, lambda nom, etat, **kw: pose.update(etat=etat, **kw),
                          fs.SUSPENDU, "VE suspendu")
    assert pose["etat"] == fs.SUSPENDU and "non déclaré pertinent" in pose["motif"]


def test_le_remplacement_exige_un_bpa_verifie_par_un_depot_et_une_periode():
    med = _med(per={"marche": [20.0] * 3})
    for bpa in ({"bpa_12m": 10.0, "fin_12m": "2026-06-30", "source_12m": "casabourse.app"},       # pas un dépôt
                {"bpa_12m": 10.0, "source_12m": "https://www.ammc.ma/x.pdf"},                    # période absente
                {"bpa_12m": 10.0, "fin_12m": "2026-06-30"}):                                       # pièce absente
        e = _mine("CMT", ebitda=None, bpa=bpa)
        v = fs.noter(e, med)["criteres"]["valorisation"]
        assert v["etat"] == fs.ABSENT and "aucun remplacement : BPA 12 mois non vérifié" in v["motif"]


def test_le_remplacement_exige_des_comparables_et_un_per_defini():
    e = _mine("CMT", ebitda=None)
    sans = fs.noter(e, _med())["criteres"]["valorisation"]
    assert sans["etat"] == fs.ABSENT and "aucun comparable identifié" in sans["motif"]
    perte = _mine("CMT", ebitda=None, bpa=BPA_VERIFIE | {"bpa_12m": -3.0})
    assert "PER non défini" in fs.noter(perte, _med(per={"marche": [20.0] * 3}))["criteres"]["valorisation"]["motif"]


def test_le_remplacement_ne_concerne_ni_les_foncieres_ni_les_autres_familles():
    assert set(fs.REMPLACEMENT_PAR_PER) == {"mines"}
    # Foncière : P/B seul ; jamais de PER (le résultat intègre la juste valeur).
    e = _entree("ARD", _fiche(roe_2025=9.0), BPA_VERIFIE, prix=10.0, pb=1.0)
    v = fs.noter(e, fs.calculer_medianes([e]))["criteres"]["valorisation"]
    assert v["etat"] == fs.ABSENT and "PER" not in (v["mesure"] or "")


# ── 15. note partielle ─────────────────────────────────────────────────────

def test_une_note_sans_critere_essentiel_est_marquee_partielle():
    # Rentabilité suspendue (AFM : ROE sans objet) mais note calculée : PARTIELLE.
    e = _entree("AFM", _fiche("Assurance", roe_2025=103.0) | {"croissance_bpa": 10.0, "croissance_ca": 10.0},
                {"bpa_12m": 10.0}, prix=100.0)
    r = fs.noter(e, _med(per={"marche": [10.0] * 3}))
    assert r["note"] is not None and r["partielle"] is True
    assert r["criteres_essentiels_manquants"] == ["rentabilite"]
    # Complète : aucune marque.
    plein = _entree("ALU", _fiche(roic=20.0) | {"croissance_bpa": 10.0, "croissance_ca": 10.0},
                    {"bpa_12m": 10.0}, prix=100.0)
    rp = fs.noter(plein, _med(per={"marche": [10.0] * 3}))
    assert rp["partielle"] is False and rp["criteres_essentiels_manquants"] == []
    # Sans note : la liste des manquants reste, « partielle » est faux (il n'y a pas de note).
    vide = fs.noter(_entree("ALU", {}, {}), _med())
    assert vide["note"] is None and vide["partielle"] is False
    assert vide["criteres_essentiels_manquants"] == ["rentabilite", "valorisation"]


@pytest.mark.parametrize("actuel,simule,partielle,attendu", [
    ("ATTENDRE", "ACHETER ★★", True, "ATTENDRE"),            # plus favorable : refusé
    ("SURVEILLER ★", "ACHETER", True, "SURVEILLER ★"),
    ("ÉVITER", "ATTENDRE", True, "ÉVITER"),
    ("ATTENDRE", "ACHETER ★★", False, "ACHETER ★★"),         # note complète : libre
    ("SURVEILLER ★", "ÉVITER", True, "ÉVITER"),               # moins favorable : admis
    ("ATTENDRE", "ATTENDRE", True, "ATTENDRE"),
    ("Données insuffisantes", "ACHETER", True, "ACHETER"),    # hors échelle : non limité
    ("SUSPENDU", "SURVEILLER ★", True, "SURVEILLER ★"),
])
def test_limiter_signal_partiel(actuel, simule, partielle, attendu):
    assert fs.limiter_signal_partiel(actuel, simule, partielle) == attendu


# ── 15. dette nette contestée : rapprochement sur pièce (13/10/2026) ──────────

def _faits_avec_rapprochement(endettement=12674.0, elements=None, base=10933.2, etabli=True):
    faits = _faits(2000.0, 2000.0, endettement_net=endettement)
    faits["faits"]["endettement_net"]["rapprochement"] = {
        "etabli": etabli, "dette_nette_base": base,
        "definition_de_la_societe": {"page": 68, "citation": "(*) Endettement en intégrant le MtM ..."},
        "elements": elements if elements is not None else [
            {"poste": "derives_couverture", "libelle": "dérivés", "valeur": 1707.9, "page": 86,
             "citation": "Dont Instruments dérivés 1 707,9"},
            {"poste": "comptes_courants_associes", "libelle": "CCA", "valeur": 33.0, "page": 68,
             "citation": "CCA 554 33"}]}
    return faits


def _contestee(faits, dn=10933.2):
    return fs._dette_nette_contestee({"valeur": dn, "date": "2025-12-31"}, faits)


def test_un_rapprochement_etabli_sur_piece_leve_la_contestation():
    assert _contestee(_faits_avec_rapprochement()) is None          # 10 933,2 + 1 707,9 + 33 = 12 674,1


@pytest.mark.parametrize("kw", [
    {"etabli": False},                                               # drapeau faux
    {"base": 10000.0},                                               # la dette nette a changé : périmé
    {"elements": [{"poste": "derives_couverture", "valeur": 1000.0, "page": 86, "citation": "x"}]},  # ne boucle pas
    {"elements": [{"poste": "derives_couverture", "valeur": 1740.9, "citation": "x"}]},  # sans page
    {"elements": [{"poste": "derives_couverture", "valeur": 1740.9, "page": 86}]},       # sans citation
    {"elements": [{"valeur": 1740.9, "page": 86, "citation": "x"}]},  # poste non nommé (règle du 16/10)
    {"elements": []},
])
def test_un_rapprochement_incomplet_ou_qui_ne_boucle_pas_ne_leve_rien(kw):
    assert "grandeur contestée" in _contestee(_faits_avec_rapprochement(**kw))


def test_sans_rapprochement_la_dette_reste_contestee():
    assert "grandeur contestée" in _contestee(_faits(2000.0, 2000.0, endettement_net=12674.0))


def test_donnees_reelles_managem_rapproche_adi_et_mutandis_contestes():
    res = fs.noter_depuis_fichiers()
    contestes = {s for s, r in res.items() if r["entree"]["dette_nette_contestee"]}
    assert "MNG" not in contestes, "MNG est rapproché sur pièce (dérivés + CCA)"
    assert {"ADI", "MUT"} <= contestes, "ADI et MUT restent contestés : écart non expliqué"


def test_les_rapprochements_non_etablis_disent_pourquoi_et_ne_levent_rien():
    import json
    faits = json.loads((Path(fs.__file__).resolve().parent.parent / "faits_financiers.json")
                       .read_text(encoding="utf-8"))
    for t in ("ADI", "MUT"):
        rap = faits[t]["faits"]["endettement_net"]["rapprochement"]
        assert rap["etabli"] is False and rap["constats"] and "NON ÉTABLIE" in rap["cause"], t
    mng = faits["MNG"]["faits"]["endettement_net"]["rapprochement"]
    assert mng["etabli"] is True and all(e["page"] and e["citation"] for e in mng["elements"])
    assert abs(mng["dette_nette_base"] + sum(e["valeur"] for e in mng["elements"]) - mng["somme"]) < 0.05


# ── 16. ROE : fonds propres MOYENS (13-14/10/2026) et contrôles négatifs ───

def _roe_faits(cp25=6000.0, cp24=5000.0, page25=21, page24=21, base25=None, note24=None, **autres):
    f = {"capitaux_propres_part_groupe": {"valeur": cp25, "page": page25, "valeur_au_rapport": int(cp25 * 1000)},
         "capitaux_propres_part_groupe_2024": {"valeur": cp24, "page": page24, "valeur_au_rapport": int(cp24 * 1000),
                                               "note": note24}}
    if base25:
        f["capitaux_propres_part_groupe"]["base"] = base25
    f |= autres
    return {"exercice": 2025, "faits": f}


def _roe_entree(sym="ATW", rn=1000.0, roe25=16.7, faits=None, moyenne=True, base_roe=None, s1=None):
    fiche = _fiche("Banque", roe_2025=roe25)
    if base_roe:
        fiche["ratios_publies"]["roe_2025"]["base"] = base_roe
    return fs.construire_entree(sym, fiche, {"bpa_12m": 5.0}, {"rnpg_exercice_2025": rn} | (s1 or {}),
                                faits or _roe_faits(), 100.0, None, roe_moyenne=moyenne)


def test_roe_sur_fonds_propres_moyens_quand_tout_concorde():
    # RNPG 2025 1 000 ; fonds propres 5 000 (2024) et 6 000 (2025) : moyenne 5 500 → 18,18 %.
    # R = 6 000 − 5 000 − 1 000 = 0 : aucun mouvement hors résultat.
    e = _roe_entree()
    r = e["roe"]
    assert r["convention"] == "moyenne" and r["valeur"] == 18.18 and r["residu_mmad"] == 0.0
    assert "MOYENNE" in r["base"] and "même état financier" in r["base"]
    assert r["valeur_cloture_publiee"] == 16.7 and r["valeur_cloture_non_arrondie"] == 16.6667
    c = fs.noter(e, _med())["criteres"]["rentabilite"]
    assert c["convention"] == "moyenne" and c["note"] == 7.0 and c["moyenne_ecartee"] is None


def test_la_cloture_est_etiquetee_quand_les_fonds_propres_2024_manquent():
    f = _roe_faits()
    del f["faits"]["capitaux_propres_part_groupe_2024"]
    e = _roe_entree(faits=f)
    assert e["roe"]["convention"] == "cloture_moyenne_indisponible" and e["roe"]["valeur"] == 16.7
    assert "CLÔTURE" in e["roe"]["base"] and "moyenne indisponible" in e["roe"]["base"]
    sans_rn = fs.construire_entree("ATW", _fiche("Banque", roe_2025=16.7), {"bpa_12m": 5.0}, {}, _roe_faits(), 100.0, None)
    assert sans_rn["roe"]["convention"] == "cloture_moyenne_indisponible"
    assert _roe_entree(moyenne=False)["roe"]["valeur"] == 16.7


@pytest.mark.parametrize("sym", ["TGCC", "VCNE", "SOT", "CASH", "CIH"])
def test_la_moyenne_est_ecartee_apres_une_operation_significative_du_registre(sym):
    # Augmentation de capital / introduction en bourse dans l'exercice, apport frais
    # supérieur à 5 % des fonds propres 2024 (ou non relevé) : clôture, étiquetée.
    e = _roe_entree(sym)
    r = e["roe"]
    assert r["convention"] == "cloture_moyenne_ecartee" and r["moyenne_code"] == "registre_operation_capital"
    assert r["valeur"] == 16.7 and "moyenne écartée" in r["base"] and "(registre)" in r["moyenne_ecartee"]
    # Contrôle négatif : le même dossier, pour un titre hors registre, est sur la moyenne.
    assert _roe_entree("ATW")["roe"]["convention"] == "moyenne"


def test_sgtm_operation_non_significative_la_moyenne_tient():
    # RFA 2025 p.88-89 : 100 MMAD en numéraire + 800 MMAD d'incorporation de réserves (sans effet
    # sur les fonds propres). Apport frais 100 ÷ 2 619,799 = 3,8 % < 5 %.
    faits = _roe_faits(cp25=3550.399, cp24=2619.799)
    e = _roe_entree("SGTM", rn=1342.0, roe25=37.8, faits=faits)
    r = e["roe"]
    assert r["convention"] == "moyenne", r["moyenne_ecartee"]
    assert "NON SIGNIFICATIVE" in r["base"]
    assert 100.0 / 2619.799 < fs.SEUIL_APPORT_FP
    # Contrôle négatif : le même titre avec un apport de 6 % des fonds propres 2024 serait écarté.
    import copy
    op = copy.deepcopy(bvc_config.OPERATIONS_SUR_CAPITAL["SGTM"])
    try:
        bvc_config.OPERATIONS_SUR_CAPITAL["SGTM"] = op | {"apport_frais_mmad": 0.06 * 2619.799}
        assert _roe_entree("SGTM", rn=1342.0, roe25=37.8, faits=faits)["roe"]["moyenne_code"] == "registre_operation_capital"
    finally:
        bvc_config.OPERATIONS_SUR_CAPITAL["SGTM"] = op


def test_le_registre_des_operations_sur_le_capital_est_source():
    for t, op in bvc_config.OPERATIONS_SUR_CAPITAL.items():
        assert t in bvc_config.TICKERS_ALL
        assert op["exercice"] == 2025 and op["nature"] and "RFA 2025" in op["source"], t
        assert "apport_frais_mmad" in op, t
    assert set(bvc_config.OPERATIONS_SUR_CAPITAL) == {"TGCC", "VCNE", "SOT", "CASH", "CIH", "SGTM"}
    tg = bvc_config.OPERATIONS_SUR_CAPITAL["TGCC"]
    assert "introduction en bourse" in tg["nature"] and "PAS une introduction" in tg["nature"]
    assert "02/07/2025" in tg["nature"] and tg["date"] == "2025-07-02" and "décembre 2021" in tg["source"]
    cih = bvc_config.OPERATIONS_SUR_CAPITAL["CIH"]
    assert cih["apport_frais_mmad"] == 1500.0                       # 14/10 : 1,5 Md (p.79), pas la ligne du tableau
    assert cih["operations_sur_capital_tableau_mmad"] == 1680.619   # la ligne du tableau garde son nom
    assert "p.79" in cih["source"] and "p.181" in cih["source"] and "4 108 341" in cih["source"] and "p.26" in cih["source"]
    assert bvc_config.OPERATIONS_SUR_CAPITAL["SGTM"]["apport_frais_mmad"] == 100.0


def test_cih_fonds_propres_2024_ligne_corrigee_etiquetee():
    import json
    s1 = json.loads((Path(bvc_config.__file__).parent / "datasets" / "resultats_s1_2026.json").read_text(encoding="utf-8"))["titres"]["CIH"]
    assert s1["capitaux_propres_pg_31_12_2024"] == 7644.9 and s1["capitaux_propres_pg_31_12_2025"] == 9817.628
    assert "7 467 336" in s1["source_capitaux_propres_2024"] and "CORRIGÉE" in s1["source_capitaux_propres_2024"]
    assert s1["capitaux_propres_pg_31_12_2024_meme_base"] is True
    res = fs.noter_depuis_fichiers()
    roe = res["CIH"]["entree"]["roe"]
    assert roe["moyenne_code"] == "registre_operation_capital" and roe["fonds_propres_2024"] == 7644.9
    assert roe["valeur_moyenne"] == round(1089.362 / ((7644.9 + 9817.628) / 2) * 100, 2)


# Résidu R = FP2025 − FP2024 − RNPG2025, rapporté aux fonds propres 2024 : seul un résidu POSITIF
# au-delà de 5 % (mouvement de fonds propres hors résultat) écarte la moyenne.
@pytest.mark.parametrize("residu_pct,ecartee", [(4.9, False), (5.0, False), (5.1, True), (30.0, True),
                                                (0.0, False), (-15.7, False), (-58.7, False)])
def test_residu_de_fonds_propres_positif_au_dela_de_5_pour_cent_ecarte_la_moyenne(residu_pct, ecartee):
    cp24, rn = 5000.0, 1000.0
    cp25 = cp24 + rn + residu_pct / 100 * cp24
    e = _roe_entree(faits=_roe_faits(cp25=cp25, cp24=cp24), roe25=round(rn / cp25 * 100, 1))
    r = e["roe"]
    assert (r["convention"] == "cloture_moyenne_ecartee") is ecartee, (residu_pct, r["moyenne_ecartee"])
    assert r["residu_pct"] == pytest.approx(residu_pct, abs=0.01)
    if ecartee:
        assert r["moyenne_code"] == "residu_non_explique"
        assert "mouvement de fonds propres hors résultat non expliqué" in r["moyenne_ecartee"]
        assert "cause non établie" not in r["moyenne_ecartee"]


@pytest.mark.parametrize("cp24,cp25,rn", [(5000.0, 3600.0, -1400.0),   # SNP : ×0,72, perte
                                           (5000.0, 6600.0, 1600.0),    # S2M : ×1,32
                                           (5000.0, 6900.0, 1900.0)])   # ZLD : ×1,38
def test_une_forte_variation_des_fonds_propres_sans_residu_passe_sur_la_moyenne(cp24, cp25, rn):
    # Le résultat explique toute la variation : R = 0. L'ancien seuil symétrique de 30 % écartait
    # ces titres à tort, avec une étiquette « cause non établie » fausse.
    e = _roe_entree(faits=_roe_faits(cp25=cp25, cp24=cp24), rn=rn, roe25=round(rn / cp25 * 100, 1))
    assert e["roe"]["convention"] == "moyenne" and e["roe"]["residu_mmad"] == 0.0


def test_un_residu_dans_le_registre_garde_le_motif_du_registre():
    # TGCC : R = +104 %. Le motif est celui du REGISTRE (cause établie), pas « non expliqué ».
    e = _roe_entree("TGCC", faits=_roe_faits(cp25=4544.126, cp24=1761.218), rn=952.0, roe25=20.95)
    assert e["roe"]["moyenne_code"] == "registre_operation_capital"
    assert "non expliqué" not in e["roe"]["moyenne_ecartee"]


def test_meme_etat_se_juge_sur_la_base_des_chiffres_pas_sur_le_numero_de_page():
    # NEJ p.104 / p.106, BAL p.44 / p.84 : le bilan imprime les deux exercices sur la MÊME ligne.
    note = "« Capitaux propres (part du groupe) 132 950 333 128 892 669 » ; bilan consolidé"
    f = _roe_faits(cp25=132.950333, cp24=128.892669, page25=84, page24=44, note24=note)
    f["faits"]["capitaux_propres_part_groupe"]["valeur_au_rapport"] = 132950333.23      # décimales : 132 950 333,23
    f["faits"]["capitaux_propres_part_groupe_2024"]["valeur_au_rapport"] = 128892669
    e = _roe_entree("BAL", rn=14.634, roe25=round(14.634 / 132.950333 * 100, 1), faits=f)
    assert e["roe"]["convention"] == "moyenne", e["roe"]["moyenne_ecartee"]
    # Contrôles négatifs : pages différentes ET la ligne 2024 ne porte pas le montant 2025 → écartée.
    f2 = _roe_faits(cp25=132.950333, cp24=128.892669, page25=84, page24=44, note24="« Capitaux propres 128 892 669 »")
    e2 = _roe_entree("BAL", rn=14.634, roe25=round(14.634 / 132.950333 * 100, 1), faits=f2)
    assert e2["roe"]["moyenne_code"] == "base_non_confirmee" and "base 2024 non confirmée" in e2["roe"]["moyenne_ecartee"]
    # Même page, sans citation : accepté ; même base déclarée (relevé S1) : accepté.
    assert _roe_entree(faits=_roe_faits(page25=21, page24=21))["roe"]["convention"] == "moyenne"


def test_la_moyenne_est_ecartee_si_les_bases_sont_contradictoires():
    sociale = _roe_entree(faits=_roe_faits(base25="SOCIAL (normes marocaines), 31/12/2025"), base_roe="consolidé IFRS, part du groupe")
    assert sociale["roe"]["moyenne_code"] == "bases_contradictoires"
    meme = _roe_entree(faits=_roe_faits(base25="consolidé IFRS, 31/12/2025"), base_roe="consolidé IFRS, part du groupe")
    assert meme["roe"]["convention"] == "moyenne"


def test_la_moyenne_est_ecartee_si_le_numerateur_ne_reproduit_pas_le_roe_publie():
    e = _roe_entree(roe25=18.0)
    assert e["roe"]["moyenne_code"] == "numerateur_non_reproduit" and "ne reproduit pas le ROE" in e["roe"]["moyenne_ecartee"]
    assert _roe_entree(roe25=16.8)["roe"]["convention"] == "moyenne"             # 0,13 point : arrondi


def test_la_moyenne_est_ecartee_si_les_fonds_propres_sont_negatifs():
    e = _roe_entree(faits=_roe_faits(cp24=-50.0))
    assert e["roe"]["moyenne_code"] == "fonds_propres_non_positifs" and "négatifs" in e["roe"]["moyenne_ecartee"]


def test_l_ecart_se_mesure_contre_la_cloture_non_arrondie():
    # ROE publié 16,7 (arrondi) ; RNPG ÷ fonds propres 2025 = 16,6667. La moyenne vaut 18,18.
    r = _roe_entree()["roe"]
    assert r["valeur_cloture_publiee"] == 16.7 and r["valeur_cloture_non_arrondie"] == 16.6667
    assert round(r["valeur_moyenne"] - r["valeur_cloture_non_arrondie"], 2) == 1.51      # et non 1,48


def test_la_moyenne_porte_sa_source_et_aucune_ponderation_n_est_inventee():
    e = _roe_entree()
    assert e["roe"]["source"]["fonds_propres_2024"].startswith("faits_financiers.json")
    assert e["roe"]["source"]["rnpg_2025"].endswith("rnpg_exercice_2025")
    assert "Pondérer par la date n'est pas fait" in Path(bvc_config.__file__).read_text(encoding="utf-8")


def test_les_bases_du_roe_sont_comptees_par_convention_sur_les_donnees_reelles():
    res = fs.noter_depuis_fichiers()
    conv = {r["entree"]["roe"].get("convention") for r in res.values()}
    assert "moyenne" in conv and "cloture_moyenne_ecartee" in conv
    # Les titres du registre à apport significatif ne sont jamais sur la moyenne ; SGTM, si.
    for t in ("TGCC", "VCNE", "SOT", "CASH", "CIH"):
        assert res[t]["entree"]["roe"].get("convention") == "cloture_moyenne_ecartee", t
    assert res["SGTM"]["entree"]["roe"].get("convention") == "moyenne"
    for t in ("SNP", "S2M", "ZLD", "NEJ", "BAL"):
        assert res[t]["entree"]["roe"].get("convention") == "moyenne", t
    for t, r in res.items():
        roe = r["entree"]["roe"]
        if roe.get("convention", "").startswith("cloture"):
            assert "(moyenne" in roe["base"], f"{t} : clôture sans étiquette"
            assert "cause non établie" not in roe["base"], t


# ── 17. ROE des assurances HORS gains latents (OCI) — décision d'Abd, 14/10/2026 ──

OCI_DE_TEST = {"ATL": {"reserve_oci": {"2025": {"etat": "present", "valeur": 400.0, "page": 1, "citation": "c25"},
                                       "2024": {"etat": "present", "valeur": 100.0, "page": 1, "citation": "c24"}}},
               "ATW": {"reserve_oci": {"2025": {"etat": "present", "valeur": 400.0, "page": 1, "citation": "c25"},
                                       "2024": {"etat": "present", "valeur": 100.0, "page": 1, "citation": "c24"}}}}


def _roe_assur(sym="ATL", rn=500.0, cp25=6000.0, cp24=5000.0, oci=None, roe25=None, secteur="Assurance"):
    fiche = _fiche(secteur, roe_2025=roe25 if roe25 is not None else round(rn / cp25 * 100, 1))
    return fs.construire_entree(sym, fiche, {"bpa_12m": 5.0}, {"rnpg_exercice_2025": rn},
                                _roe_faits(cp25=cp25, cp24=cp24), 100.0, None, oci=oci)


def test_le_roe_d_une_assurance_se_calcule_hors_gains_latents():
    # RNPG 500 ; fonds propres 5 000 → 6 000 dont OCI 100 → 400. Hors OCI : 4 900 → 5 600, moyenne 5 250.
    r = _roe_assur(oci=OCI_DE_TEST)["roe"]
    assert r["oci"]["etiquette"] == "hors OCI" and r["convention"] == "moyenne"
    assert r["valeur"] == round(500 / 5250 * 100, 2) == 9.52
    assert r["oci"]["roe_avec_oci"] == {"cloture": 8.33, "moyenne": 9.09}
    assert r["oci"]["roe_hors_oci"] == {"cloture": 8.93, "moyenne": 9.52}
    assert "HORS gains latents" in r["base"] and "réserve OCI" in r["base"]
    assert r["valeur_cloture_non_arrondie"] == round(500 / 5600 * 100, 4)          # clôture hors OCI
    # Le numérateur reste le RNPG : même résultat, seul le dénominateur change.
    assert r["rnpg_2025"] == 500.0


def test_le_residu_d_une_assurance_se_calcule_hors_oci():
    # Avec OCI : R = 6 000 − 5 000 − 500 = +500 (+10 %) → écarterait la moyenne.
    # Hors OCI : R = 5 600 − 4 900 − 500 = +200 (+4,08 %) → la moyenne tient.
    r = _roe_assur(oci=OCI_DE_TEST)["roe"]
    assert r["residu_mmad"] == 200.0 and r["residu_pct"] == pytest.approx(4.08, abs=0.01)
    assert r["convention"] == "moyenne"
    # Contrôle négatif : un mouvement hors résultat ET hors OCI reste écarté (R hors OCI > 5 %).
    fort = _roe_assur(cp25=6500.0, oci=OCI_DE_TEST)["roe"]                      # R hors OCI = +700 (+14,3 %)
    assert fort["convention"] == "cloture_moyenne_ecartee" and fort["moyenne_code"] == "residu_non_explique"
    assert "hors résultat non expliqué" in fort["moyenne_ecartee"]
    assert fort["valeur"] == round(500 / (6500 - 400) * 100, 2)                 # clôture, elle aussi hors OCI


def test_sans_reserve_oci_relevee_le_roe_reste_avec_oci_etiquete():
    for oci in (None, {}, {"ATL": {"reserve_oci": {"2025": {"etat": "present", "valeur": 400.0}}}},      # 2024 manquant
                {"ATL": {"reserve_oci": {"2025": {"etat": "estime", "valeur": 400.0}, "2024": {"etat": "present", "valeur": 100.0}}}}):
        r = _roe_assur(cp25=5700.0, oci=oci)["roe"]           # R avec OCI = +200 (+4 %) : la moyenne tient
        assert r["oci"]["etiquette"] == "OCI non relevé" and r["oci"]["etat"] == "non_releve"
        assert "AVEC gains latents : OCI non relevé" in r["base"]
        assert r["valeur"] == round(500 / 5350 * 100, 2)                      # moyenne AVEC OCI : aucune estimation
        assert r["oci"]["roe_hors_oci"] == {"cloture": None, "moyenne": None}


def test_la_regle_hors_oci_ne_s_applique_pas_hors_de_la_famille_assurances():
    # NÉGATIF : le fichier contient une « réserve » pour ATW (banque), elle est ignorée.
    avec = _roe_assur("ATW", cp25=5700.0, oci=OCI_DE_TEST, secteur="Banque")["roe"]
    sans = _roe_assur("ATW", cp25=5700.0, oci=None, secteur="Banque")["roe"]
    assert avec["valeur"] == sans["valeur"] == round(500 / 5350 * 100, 2)
    assert avec["oci"]["applicable"] is False and avec["oci"]["etiquette"] is None
    assert "OCI" not in avec["base"] and "OCI" not in sans["base"]
    # Autres familles : industrie, foncière, mines, courtier AFM (famille « autre »).
    for sym in ("ALU", "ARD", "MNG", "AFM", "CIH", "TGCC"):
        assert bvc_config.famille_note(sym) not in fs.FAMILLES_ROE_HORS_OCI
    assert fs.FAMILLES_ROE_HORS_OCI == ("assurance",)
    assert set(bvc_config.FAMILLES_NOTE["assurance"]) == {"ATL", "WAF", "SAF"}


def test_waf_et_atl_sur_les_donnees_reelles():
    res = fs.noter_depuis_fichiers()
    w, a, sf = (res[t]["entree"]["roe"] for t in ("WAF", "ATL", "SAF"))
    # WAF : 10,05 % clôture / 10,35 % moyenne hors OCI (6,86 / 7,45 avec) ; résidu hors OCI −429,451 MMAD.
    assert w["oci"]["roe_hors_oci"] == {"cloture": 10.05, "moyenne": 10.35}
    assert w["oci"]["roe_avec_oci"] == {"cloture": 6.86, "moyenne": 7.45}
    assert w["convention"] == "moyenne" and w["valeur"] == 10.35 and w["residu_mmad"] == -429.451
    assert w["oci"]["reserve_2025"] == 4747.429 and w["oci"]["reserve_2024"] == 2950.462
    # ATL : réserve OCI nulle CONFIRMÉE sur pièce (aucune ligne de gains latents) : ROE inchangé.
    assert a["oci"]["etat"] == "releve" and a["oci"]["pieces"]["etats"] == {"2025": "zero_confirme", "2024": "zero_confirme"}
    assert a["convention"] == "moyenne" and a["valeur"] == 19.29 and "NULLE confirmée" in a["base"]
    # SAF : pas de ROE d'exercice, donc rien à calculer.
    assert sf["etat"] == "absent"


def test_le_fichier_des_reserves_oci_est_source_page_citation_et_boucle():
    import json
    d = json.loads((Path(bvc_config.__file__).parent / "datasets" / "reserves_oci_assurances.json").read_text(encoding="utf-8"))
    assert set(d["titres"]) == {"WAF", "ATL"} and "Aucune estimation" in d["_regle"]
    for t, e in d["titres"].items():
        assert e["url"].startswith("https://www.ammc.ma/") and e["document"]
        for an, o in e["reserve_oci"].items():
            assert o["etat"] in ("present", "zero_confirme") and o["page"] and o["citation"] and o["controle"], (t, an)
    w = d["titres"]["WAF"]["reserve_oci"]
    assert w["2025"]["page"] == 16 and w["2025"]["valeur_au_rapport"] == 4747429 and w["2024"]["valeur_au_rapport"] == 2950462
    # Les composantes bouclent sur « Capitaux propres-part du groupe » (RFA p.16, KMAD).
    assert 350_000 + 8_836_872 + 4_747_429 + 1_026_036 == 14_960_337
    assert 350_000 + 8_343_176 + 2_950_462 + 923_147 == 12_566_785
    a = d["titres"]["ATL"]["reserve_oci"]
    assert a["2025"]["etat"] == a["2024"]["etat"] == "zero_confirme" and a["2025"]["valeur"] == 0.0 and a["2025"]["page"] == 140
    assert 602_836 + 1_411_503 + 467_641 == 2_481_980 and 602_836 + 1_311_579 + 453_361 - 2_367_775 == 1   # 1 KMAD d'arrondi


def test_cih_page_des_fonds_propres_2024_corriges_renseignee():
    import json
    c = json.loads((Path(bvc_config.__file__).parent / "datasets" / "resultats_s1_2026.json").read_text(encoding="utf-8"))["titres"]["CIH"]
    assert c["capitaux_propres_pg_31_12_2024_page"] == 26 and c["capitaux_propres_pg_31_12_2025_page"] == 26
    assert "p.26" in c["source_capitaux_propres_2024"] and "7 644 900" in c["source_capitaux_propres_2024"]
    assert "à renseigner" not in c["source_capitaux_propres_2024"]
    roe = fs.noter_depuis_fichiers()["CIH"]["entree"]["roe"]
    assert roe["page_2024"] == 26 and roe["page_2025"] == 26


# ── 18. Résidu APRÈS dividende, TMA, WAF, ATL (14/10/2026, seconde contre-vérification) ──

def _paiement(montant, jour="2025-07-01", type_="Ordinaire", ajuste=None):
    return {"detachement": jour, "paiement": jour, "type": type_, "montant": montant,
            "montant_ajuste_split": montant if ajuste is None else ajuste}


def _roe_div(sym="ATW", rn=1000.0, cp24=5000.0, cp25=None, calendrier=None, actions=1_000_000, residu_apres=None,
             dividende=300.0, roe25=None):
    """Un ROE d'exercice avec calendrier de dividendes. Par défaut D = 300 MMAD (300 DH × 1 million
    d'actions) et `residu_apres` (en % des fonds propres 2024) fixe R + D : fonds propres 2025 = FP2024
    + RNPG − D + (R + D)."""
    if cp25 is None:
        cp25 = cp24 + rn - dividende + (residu_apres or 0.0) / 100 * cp24
    cal = {sym: [_paiement(dividende)]} if calendrier is None else calendrier
    faits = _roe_faits(cp25=cp25, cp24=cp24, nombre_actions_au_rapport={"valeur": actions})
    fiche = _fiche("Banque", roe_2025=roe25 if roe25 is not None else round(rn / cp25 * 100, 1))
    return fs.construire_entree(sym, fiche, {"bpa_12m": 5.0}, {"rnpg_exercice_2025": rn}, faits, 100.0, None,
                                dividendes=cal)["roe"]


@pytest.mark.parametrize("apres,ecartee", [(0.0, False), (4.9, False), (-4.9, False), (5.0, False), (-5.0, False),
                                           (5.1, True), (-5.1, True), (-20.0, True), (30.0, True)])
def test_le_residu_apres_dividende_ecarte_la_moyenne_dans_les_deux_sens(apres, ecartee):
    r = _roe_div(residu_apres=apres)
    assert r["dividende"]["mmad"] == 300.0 and r["dividende"]["origine"] == "calendrier"
    assert r["residu_apres_dividende_pct"] == pytest.approx(apres, abs=0.01)
    assert (r["convention"] == "cloture_moyenne_ecartee") is ecartee, (apres, r["moyenne_ecartee"])
    if ecartee:
        assert r["moyenne_code"] == "residu_non_explique"
        assert "mouvement hors résultat et hors dividende non expliqué" in r["moyenne_ecartee"]
        assert "cause absente du registre" in r["moyenne_ecartee"]


def test_un_residu_negatif_qui_n_est_qu_un_dividende_ne_deplace_rien():
    # R = −300 (−6 %) : avant, comme après, c'est un dividende ; R + D = 0 → la moyenne tient.
    r = _roe_div(residu_apres=0.0)
    assert r["residu_pct"] == -6.0 and r["residu_apres_dividende_pct"] == 0.0 and r["convention"] == "moyenne"


def test_sans_le_dividende_le_meme_residu_negatif_ecarte_la_moyenne():
    # NÉGATIF : même R = −20 % ; D = 0 (titre au calendrier, aucun versement dans l'exercice) →
    # rien n'explique la baisse, la moyenne est écartée. Avant le 14/10, le test ne regardait que R > 0.
    r = _roe_div(calendrier={"ATW": [_paiement(300.0, jour="2024-07-01")]}, cp25=5000.0 + 1000.0 - 1000.0)
    assert r["dividende"]["mmad"] == 0.0 and r["residu_apres_dividende_pct"] == -20.0
    assert r["convention"] == "cloture_moyenne_ecartee" and r["moyenne_code"] == "residu_non_explique"


def test_dividende_inconnu_l_ancien_test_reste_en_vigueur_et_le_dit():
    # Titre ABSENT du calendrier : D inconnu (le silence n'est pas un non-versement).
    neg = _roe_div(calendrier={"AUTRE": []}, cp25=5000.0)                   # R = −1 000 (−20 %)
    assert neg["dividende"] is None and neg["residu_apres_dividende_pct"] is None
    assert neg["convention"] == "moyenne"                                   # résidu négatif : non retenu
    assert "dividende de l'exercice non relevé" in neg["base"]
    pos = _roe_div(calendrier={"AUTRE": []}, cp25=7000.0, roe25=14.3)       # R = +1 000 (+20 %)
    assert pos["convention"] == "cloture_moyenne_ecartee" and pos["moyenne_code"] == "residu_non_explique"
    assert "dividende de l'exercice non relevé : test limité au résidu positif" in pos["moyenne_ecartee"]
    # Pas de calendrier du tout : même chose.
    assert _roe_div(calendrier={}, cp25=5000.0)["dividende"] is None
    # Le calendrier existe mais le NOMBRE D'ACTIONS manque : D inconnu aussi.
    f = _roe_faits(cp25=5000.0, cp24=5000.0)
    r = fs.construire_entree("ATW", _fiche("Banque", roe_2025=20.0), {"bpa_12m": 5.0}, {"rnpg_exercice_2025": 1000.0}, f,
                             100.0, None, dividendes={"ATW": [_paiement(300.0)]})["roe"]
    assert r["dividende"] is None


def test_le_tableau_de_variation_prime_sur_le_calendrier(monkeypatch):
    # SGTM : dividende de 500 MMAD d'avant la cotation, absent du calendrier (D = 0 au calendrier).
    monkeypatch.setitem(bvc_config.DIVIDENDES_VERSES_TABLEAU, "ATW", {
        "exercice": 2025, "montant_mmad": 300.0, "page": 9, "source": "RFA test p.9 « Dividendes (300 000) »"})
    d = fs._dividende_exercice("ATW", _roe_faits(), 2025, {"ATW": []})
    assert d["mmad"] == 300.0 and d["origine"] == "tableau_variation" and d["page"] == 9 and d["calendrier_mmad"] == 0.0
    # Et un tableau d'un AUTRE exercice ne s'applique pas.
    monkeypatch.setitem(bvc_config.DIVIDENDES_VERSES_TABLEAU, "ATW", {"exercice": 2024, "montant_mmad": 300.0,
                                                                       "page": 9, "source": "x"})
    assert fs._dividende_exercice("ATW", _roe_faits(), 2025, {"ATW": []})["origine"] == "calendrier"


def test_le_calendrier_compte_ce_qui_est_paye_dans_l_exercice_au_montant_verse():
    faits = _roe_faits(nombre_actions_au_rapport={"valeur": 11_864_676})
    cal = {"MNG": [_paiement(30.0, "2024-07-01", ajuste=3.0), _paiement(40.0, "2025-07-08", ajuste=4.0),
                   _paiement(55.0, "2026-07-24", ajuste=5.5)]}
    d = fs._dividende_exercice("XXX", faits, 2025, {"XXX": cal["MNG"]})
    # 40 DH (montant VERSÉ, avant split) × 11 864 676 = 474,587 ; le montant ajusté (4 DH) donnerait 47,5.
    assert d["mmad"] == pytest.approx(474.587, abs=0.001) and d["origine"] == "calendrier"
    assert fs._dividende_exercice("XXX", faits, 2025, {"XXX": [_paiement(30.0, "2024-07-01")]})["mmad"] == 0.0
    assert fs._dividende_exercice("XXX", faits, 2025, {"YYY": []}) is None
    assert fs._dividende_exercice("XXX", faits, 2025, None) is None


def _cause(montant, exercice=2025, tableau=None):
    c = {"exercice": exercice, "montant_mmad": montant, "page": 12, "libelle": "« Variation de périmètre »", "source": "RFA test p.12"}
    if tableau:
        c["tableau"] = tableau
    return c


def test_la_cause_portee_sur_piece_passe_le_test_du_reste(monkeypatch):
    # Résidu après dividende : −20 % = −1 000 MMAD sur 5 000. Le reste R + D − C doit tenir dans ±5 % (250).
    for montant, portee in ((-1000.0, True),     # reste 0
                            (-800.0, True),      # reste −200 (−4 %)
                            (-1250.0, True),     # reste +250 (+5,0 %) : à la borne
                            (-740.0, False),     # reste −260 (−5,2 %)
                            (-1260.0, False),    # reste +260 (+5,2 %)
                            (-200.0, False),     # reste −800 : la cause n'explique presque rien
                            (-2500.0, False)):   # reste +1 500 : elle explique trop
        monkeypatch.setitem(bvc_config.CAUSES_RESIDU_FONDS_PROPRES, "ATW", _cause(montant))
        r = _roe_div(residu_apres=-20.0)
        assert r["convention"] == "cloture_moyenne_ecartee"
        assert (r["moyenne_code"] == "residu_cause_sur_piece") is portee, (montant, r["moyenne_ecartee"])
        if portee:
            assert "cause portée sur pièce" in r["moyenne_ecartee"] and "p.12" in r["moyenne_ecartee"]
            assert "non expliqué" not in r["moyenne_ecartee"]
        else:
            assert "non expliqué" in r["moyenne_ecartee"] and "ne l'explique pas" in r["moyenne_ecartee"]
            assert "cause portée sur pièce" not in r["moyenne_ecartee"]
    # NÉGATIF : une cause d'un autre exercice est ignorée.
    monkeypatch.setitem(bvc_config.CAUSES_RESIDU_FONDS_PROPRES, "ATW", _cause(-1000.0, exercice=2024))
    r = _roe_div(residu_apres=-20.0)
    assert r["moyenne_code"] == "residu_non_explique" and "cause absente du registre" in r["moyenne_ecartee"]
    # Et une cause au registre ne sert à rien quand il n'y a pas de résidu à expliquer.
    monkeypatch.setitem(bvc_config.CAUSES_RESIDU_FONDS_PROPRES, "ATW", _cause(-1000.0))
    assert _roe_div(residu_apres=1.0)["convention"] == "moyenne"


def test_le_reste_se_juge_sur_une_seule_base_celle_du_tableau(monkeypatch):
    # Bilan : FP2024 5 000, FP2025 = 5 000 + 1 000 − 300 − 1 000 = 4 700 → R + D = −1 000 (−20 %).
    # Tableau (autre base, comme BCP) : FP 8 000 → 7 700... mais un RNPG et des fonds propres DIFFÉRENTS :
    # R_tableau = 8 000 − 8 000 − 1 000 = −1 000 ; + D 300 = −700 ; cause −700 → reste 0 sur le tableau.
    tab = {"fonds_propres_2024": 8000.0, "fonds_propres_2025": 8000.0, "rnpg": 1000.0, "page": 12}
    monkeypatch.setitem(bvc_config.CAUSES_RESIDU_FONDS_PROPRES, "ATW", _cause(-700.0, tableau=tab))
    r = _roe_div(residu_apres=-20.0)
    assert r["moyenne_code"] == "residu_cause_sur_piece"
    c = r["cause_residu"]
    assert c["base_du_reste"] == "tableau de variation p.12" and c["residu_sur_cette_base_mmad"] == -1000.0
    assert c["reste_mmad"] == 0.0
    # Le MÊME C jugé sur la base du bilan (sans `tableau`) laisserait un reste de −300 (−6 %) : non portée.
    monkeypatch.setitem(bvc_config.CAUSES_RESIDU_FONDS_PROPRES, "ATW", _cause(-700.0))
    r = _roe_div(residu_apres=-20.0)
    assert r["moyenne_code"] == "residu_non_explique" and r["cause_residu"]["reste_mmad"] == -300.0
    assert "fonds propres de la note (bilan)" in r["cause_residu"]["base_du_reste"]


def test_ctm_bcp_tma_mng_sgtm_sur_les_donnees_reelles():
    res = fs.noter_depuis_fichiers()
    roe = {t: res[t]["entree"]["roe"] for t in ("CTM", "BCP", "TMA", "MNG", "SGTM", "RIS", "WAF", "ATW")}
    # CTM : D = 30,651 (dividende NET, flux de trésorerie p.66) → R + D = −144,434 = « Autres retraitements »
    # (p.68) exactement : reste 0,00 %.
    c = roe["CTM"]
    assert c["dividende"]["mmad"] == 30.651 and c["dividende"]["origine"] == "flux_de_trésorerie" and c["dividende"]["page"] == 66
    assert c["residu_apres_dividende_mmad"] == pytest.approx(-144.434, abs=0.001)
    assert c["residu_apres_dividende_pct"] == pytest.approx(-39.86, abs=0.01) and c["convention"] == "cloture_moyenne_ecartee"
    assert c["moyenne_code"] == "residu_cause_sur_piece" and "Autres retraitements" in c["moyenne_ecartee"]
    assert "p.68" in c["moyenne_ecartee"] and c["cause_residu"]["reste_pct"] == 0.0
    # BCP : −6,6 % après dividende (base du bilan, celle des fonds propres de la note) ; le reste se juge sur
    # le TABLEAU de variation (p.12), où se lit la cause : +133,6 MMAD, +0,33 %.
    b = roe["BCP"]
    assert b["residu_apres_dividende_pct"] == pytest.approx(-6.58, abs=0.01) and b["moyenne_code"] == "residu_cause_sur_piece"
    assert "Variation de périmètre" in b["moyenne_ecartee"] and "p.12" in b["moyenne_ecartee"]
    assert b["residu_pct"] == pytest.approx(-12.34, abs=0.01)                 # avant dividende : −12,3 %
    assert b["cause_residu"]["base_du_reste"] == "tableau de variation p.12"
    assert b["cause_residu"]["reste_mmad"] == pytest.approx(133.559, abs=0.001)
    assert b["cause_residu"]["reste_pct"] == pytest.approx(0.33, abs=0.005)
    # TMA : ≈ 0 après dividende (ordinaire + exceptionnel) ; la moyenne tient.
    assert abs(roe["TMA"]["residu_apres_dividende_pct"]) < 0.05 and roe["TMA"]["convention"] == "moyenne"
    # MNG : −16,2 % après dividende, autres éléments du résultat global −1 747 MMAD (p.87) : reste +0,09 %
    # sur le tableau (arrondi à l'unité : +10 MMAD ; +10,5 sur le bilan à la décimale = +0,10 %).
    m = roe["MNG"]
    assert m["moyenne_code"] == "residu_cause_sur_piece" and m["dividende"]["mmad"] == 475.0
    assert m["cause_residu"]["reste_mmad"] == 10.0 and m["cause_residu"]["reste_pct"] == pytest.approx(0.09, abs=0.005)
    for mot in ("autres éléments du résultat global, part du groupe -1 747", "couverture -1 158", "conversion -408",
                "autres -280", "impôts +108", "actuariels -9", "p.87"):
        assert mot in m["moyenne_ecartee"], mot
    # SGTM : dividende de 500 MMAD lu au tableau (absent du calendrier) → +3,4 %, la moyenne tient.
    assert roe["SGTM"]["convention"] == "moyenne" and roe["SGTM"]["dividende"]["origine"] == "tableau_variation"
    assert roe["SGTM"]["dividende"]["calendrier_mmad"] == 0.0
    assert roe["SGTM"]["residu_apres_dividende_pct"] == pytest.approx(3.38, abs=0.01)
    # RIS : le tableau de variation (p.36) passe avant le calendrier : D = 160,289, pas 7 DH × 14 326 947 = 100,289.
    # L'écart de 60,000 MMAD est consigné (cause non établie). R + D = −162,920 + 160,289 = −2,631 (−0,17 %).
    ris = roe["RIS"]
    assert ris["dividende"]["mmad"] == 160.289 and ris["dividende"]["origine"] == "tableau_variation" and ris["dividende"]["page"] == 36
    assert ris["dividende"]["calendrier_mmad"] == pytest.approx(100.289, abs=0.001)
    assert "cause non établie" in ris["dividende"]["source"] and "60,000" in ris["dividende"]["source"]
    assert ris["residu_apres_dividende_mmad"] == pytest.approx(-2.631, abs=0.001)
    assert ris["residu_apres_dividende_pct"] == pytest.approx(-0.17, abs=0.005) and ris["convention"] == "moyenne"
    # WAF et ATW (hors OCI pour WAF seulement) : un dividende explique le résidu.
    assert abs(roe["WAF"]["residu_apres_dividende_pct"]) < 1 and abs(roe["ATW"]["residu_apres_dividende_pct"]) < 1


def test_le_registre_des_dividendes_et_des_causes_est_source_et_page():
    for t, d in bvc_config.DIVIDENDES_VERSES_TABLEAU.items():
        assert t in bvc_config.TICKERS_ALL and d["exercice"] == 2025 and d["montant_mmad"] > 0, t
        assert isinstance(d["page"], int) and ("RFA" in d["source"] or "rapport financier" in d["source"]), t
        assert "ividendes" in d["source"] and f"p.{d['page']}" in d["source"], t
        assert d.get("origine", "tableau_variation") in ("tableau_variation", "flux_de_trésorerie"), t
    for t, c in bvc_config.CAUSES_RESIDU_FONDS_PROPRES.items():
        assert t in bvc_config.TICKERS_ALL and c["exercice"] == 2025 and c["montant_mmad"] < 0, t
        assert f"p.{c['page']}" in c["source"] and c["libelle"], t
        tb = c["tableau"]                                    # la base UNIQUE du test du reste
        assert tb["page"] == c["page"] and tb["fonds_propres_2024"] > 0 and tb["fonds_propres_2025"] > 0 and tb["rnpg"] > 0, t
    assert set(bvc_config.DIVIDENDES_VERSES_TABLEAU) == {"CTM", "BCP", "MNG", "SGTM", "CIH", "RIS"}
    assert bvc_config.DIVIDENDES_VERSES_TABLEAU["RIS"]["montant_mmad"] == 160.289 and bvc_config.DIVIDENDES_VERSES_TABLEAU["RIS"]["page"] == 36
    assert set(bvc_config.CAUSES_RESIDU_FONDS_PROPRES) == {"CTM", "BCP", "MNG"}
    # Les montants du registre sont ceux des pièces lues (KMAD ÷ 1 000).
    assert bvc_config.DIVIDENDES_VERSES_TABLEAU["CTM"]["montant_mmad"] == 30.651          # net, p.66 (le brut du tableau : 31,651)
    assert bvc_config.DIVIDENDES_VERSES_TABLEAU["BCP"]["montant_mmad"] == 2134.781
    assert bvc_config.CAUSES_RESIDU_FONDS_PROPRES["CTM"]["montant_mmad"] == -144.434
    assert bvc_config.CAUSES_RESIDU_FONDS_PROPRES["BCP"]["montant_mmad"] == -2119.062


# ── TMA : dividende exceptionnel ──

def test_tma_dividende_exceptionnel_etiquete_la_moyenne_simple_reste_la_regle():
    r = fs.noter_depuis_fichiers()["TMA"]["entree"]["roe"]
    assert r["convention"] == "moyenne" and r["valeur"] == 35.98                   # la règle ne change pas
    e = r["dividende_exceptionnel"]
    assert e["roe_moyenne_simple"] == 35.98 and e["roe_moyenne_ponderee_indicatif"] == pytest.approx(32.4, abs=0.05)
    assert ("dividende exceptionnel de 67 DH payé le 11/12/2025 (600,3 MMAD, 22% des fonds propres 2024) : "
            "moyenne simple 35,98 %, pondérée ≈ 32,4 %") in e["etiquette"]
    assert e["etiquette"] in r["base"]                                              # dans la trace, pas seulement le livrable
    assert "INDICATIVE" in e["etiquette"]


def test_la_moyenne_ponderee_se_calcule_a_la_main():
    # FP 5 000 → 6 000, D = 600 versé le 11/12 (20 jours avant la fin) :
    # (5 000 + 6 000 + 600)/2 × 345/365 + 6 000 × 20/365 = 5 800 × 0,945205 + 328,767 = 5 811,0 ; ROE = 1 000/5 811.
    exc = {"mmad": 600.0, "paiement": "2025-12-11", "par_action": 67.0}
    assert fs._moyenne_ponderee_exceptionnel(1000.0, 5000.0, 6000.0, exc, 2025) == pytest.approx(17.21, abs=0.01)
    assert fs._moyenne_ponderee_exceptionnel(1000.0, 5000.0, 6000.0, {"mmad": 600.0, "paiement": "n'importe quoi"}, 2025) is None


def test_pas_d_etiquette_sans_dividende_exceptionnel_significatif():
    # Dividende ORDINAIRE : aucune étiquette. Exceptionnel de 1 % des fonds propres : aucune non plus.
    assert _roe_div(residu_apres=0.0)["dividende_exceptionnel"] is None
    petit = {"ATW": [_paiement(300.0), _paiement(50.0, "2025-12-11", "Exceptionnel")]}      # 50 = 1 % de 5 000
    r = _roe_div(calendrier=petit, dividende=350.0, residu_apres=0.0)
    assert r["convention"] == "moyenne" and r["dividende_exceptionnel"] is None
    gros = {"ATW": [_paiement(300.0), _paiement(600.0, "2025-12-11", "Exceptionnel")]}      # 12 % de 5 000
    r = _roe_div(calendrier=gros, dividende=900.0, residu_apres=0.0)
    assert r["dividende_exceptionnel"]["exceptionnels"][0]["mmad"] == 600.0
    assert "dividende exceptionnel de 600 DH payé le 11/12/2025" in r["base"]
    ecart = fs.noter_depuis_fichiers()["ATW"]["entree"]["roe"]
    assert ecart["dividende_exceptionnel"] is None


# ── WAF : formule hors OCI et proximité d'un palier ──

def test_waf_la_formule_porte_le_denominateur_hors_oci():
    r = fs.noter_depuis_fichiers()["WAF"]["entree"]["roe"]
    assert r["formule"] == "1026.036 ÷ moyenne(12566.785 − 2950.462 ; 14960.337 − 4747.429)"
    # Recalcul à la main de la formule affichée.
    assert round(1026.036 / (((12566.785 - 2950.462) + (14960.337 - 4747.429)) / 2) * 100, 2) == r["valeur"] == 10.35
    # Les autres : sans OCI, la formule n'en porte pas ; clôture écartée : un seul dénominateur.
    assert fs.noter_depuis_fichiers()["ATW"]["entree"]["roe"]["formule"].count("−") == 0
    assert fs.noter_depuis_fichiers()["CTM"]["entree"]["roe"]["formule"] == "56.204 ÷ (243.479)"


def test_waf_est_signale_a_035_point_du_seuil_de_10_pour_cent():
    f = fs.noter_depuis_fichiers()["WAF"]["entree"]["roe"]["frontiere_palier"]
    assert f["seuil"] == 10.0 and f["ecart_points"] == 0.35 and f["cote"] == "au-dessus"
    assert (f["note_au_dessus"], f["note_en_dessous"]) == (5.0, 3.5)
    assert "à 0,35 point du seuil de 10 %" in f["etiquette"]


@pytest.mark.parametrize("roe,seuil", [(10.5, 10.0), (9.5, 10.0), (12.4, 12.0), (14.6, 15.0), (7.0, 7.0), (25.0, 25.0)])
def test_la_frontiere_est_signalee_a_moins_d_un_demi_point(roe, seuil):
    assert fs._frontiere_roe(roe)["seuil"] == seuil


@pytest.mark.parametrize("roe", [10.51, 9.49, 11.0, 13.5, 17.5, 22.4, 5.0])
def test_pas_de_drapeau_au_dela_d_un_demi_point(roe):
    assert fs._frontiere_roe(roe) is None


def test_les_frontieres_du_drapeau_sont_celles_de_la_grille_de_note():
    # Le drapeau lit les mêmes paliers que `note_ecart_rentabilite` : de part et d'autre de chaque
    # frontière du drapeau, la note change réellement.
    ref = fg.COUT_FONDS_PROPRES_REF
    for ecart in fs._ECARTS_PALIERS_ROE:
        seuil = ref + ecart
        assert fs.note_ecart_rentabilite(seuil, ref) != fs.note_ecart_rentabilite(seuil - 0.001, ref), seuil


# ── ATL / WAF / ATW : ce qui ne se compare pas ──

def test_la_documentation_atl_waf_atw_est_dans_le_code():
    doc = fs._roe.__doc__
    for mot in ("ATL", "NORMES MAROCAINES", "HORS BILAN", "WAF", "IFRS 17", "ATW", "RESTE INCLUS"):
        assert mot in doc, mot
    assert "ne se comparent pas terme à terme" in doc.lower()
    assert "dividende exceptionnel" in doc.lower() and "67 DH" in doc


def test_l_oci_d_assurance_consolide_d_atw_reste_inclus():
    atw = fs.noter_depuis_fichiers()["ATW"]["entree"]["roe"]
    assert atw["oci"]["applicable"] is False and atw["oci"]["etiquette"] is None and "OCI" not in atw["base"]
    assert bvc_config.famille_note("ATW") == "banque"


def test_le_critere_publie_porte_la_formule_et_le_drapeau_de_palier():
    r = fs.noter_depuis_fichiers()["WAF"]
    c = r["criteres"]["rentabilite"]
    assert c["formule"] == "1026.036 ÷ moyenne(12566.785 − 2950.462 ; 14960.337 − 4747.429)"
    assert "à 0,35 point du seuil de 10 %" in c["drapeau_palier"]
    pub = fs.detail_publie(r)["criteres"]["rentabilite"]                      # ce que data.json publie
    assert pub["formule"] == c["formule"] and pub["drapeau_palier"] == c["drapeau_palier"]
    # Un ROE loin de toute frontière ne porte aucun drapeau.
    assert fs.noter_depuis_fichiers()["ATW"]["criteres"]["rentabilite"]["drapeau_palier"] is None


def test_la_source_du_critere_porte_la_formule_hors_oci_de_waf():
    # 14/10 : `source.formule` affichait « 1026.036 ÷ 14960.337 » (avec OCI, clôture) sous un ROE moyen hors OCI.
    s = fs.noter_depuis_fichiers()["WAF"]["criteres"]["rentabilite"]["source"]
    assert s["formule"] == "1026.036 ÷ moyenne(12566.785 − 2950.462 ; 14960.337 − 4747.429)"
    assert s["formule_roe_publie"] == "1026.036 ÷ 14960.337 (MMAD)"            # le ROE publié reste cité, étiqueté
    # Clôture écartée : la formule de la source est celle de la clôture, avec le même dénominateur que la valeur.
    assert fs.noter_depuis_fichiers()["BCP"]["criteres"]["rentabilite"]["source"]["formule"] == "4503.361 ÷ (36974.989)"


def test_ris_nombre_d_actions_2025_releve_sur_piece():
    import json
    f = json.loads((Path(fs.__file__).resolve().parent.parent / "faits_financiers.json").read_text(encoding="utf-8"))["RIS"]["faits"]
    n = f["nombre_actions_au_rapport"]
    assert n["valeur"] == 14326947 and n["page"] == 45 and "14 326 947" in n["note"] and "7 × 14 326 947 = 100,289" in n["note"]
    assert f["nombre_actions_existant"]["valeur"] == 16012132                    # le ratio par action d'aujourd'hui ne bouge pas
    assert "160 289" in n["note"]                                                # l'écart au tableau est consigné, non estimé
    d = fs._dividende_exercice("RIS", {"faits": f}, 2025, {"RIS": [_paiement(7.0, "2025-08-04")]})
    assert d["mmad"] == 160.289 and d["origine"] == "tableau_variation"        # le tableau prime (décision du 14/10)
    assert d["calendrier_mmad"] == pytest.approx(100.289, abs=0.001)          # 7 × 14 326 947 : le calendrier reste calculé


def test_la_documentation_des_trois_traitements_de_l_oci_est_dans_le_code():
    doc = fs._roe.__doc__
    assert "TROIS TRAITEMENTS DE L'OCI" in doc
    for mot in ("ASSURANCES (WAF, ATL, SAF)", "RETIRÉ", "ATW (banque-assurance)", "CONSERVÉ", "MNG (mines)", "ÉCARTE LA MOYENNE"):
        assert mot in doc, mot
    assert "4,7 Md MAD" in doc and "4,7 MMAD" not in doc
