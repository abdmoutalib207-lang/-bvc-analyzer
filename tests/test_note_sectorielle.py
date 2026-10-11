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


def test_msa_ratios_en_verification_ne_sont_pas_lus():
    # Le module fantôme publiait un ROIC de 47,6 % pour MSA.
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


def test_dette_nette_et_ebitda_passent_par_la_porte_unique():
    # Relecture du 10/10/2026 : `construire_entree` lisait encore `ratios_publies`
    # en direct pour la dette nette et l'EBITDA. MSA (en vérification) les aurait
    # fait entrer dans son bilan et dans un VE/EBITDA.
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


def test_roe_sur_fonds_propres_moyens_quand_les_deux_clotures_sont_structurees():
    # RNPG 2025 1 000 ; fonds propres 4 000 (31/12/2024) et 6 000 (31/12/2025) →
    # moyenne 5 000 → ROE 20,0 %. Sur la clôture il serait de 16,7 %.
    e = _entree("ATW", _fiche("Banque", roe_2025=16.7), {"bpa_12m": 5.0},
                {"rnpg_exercice_2025": 1000.0, "capitaux_propres_pg_31_12_2024": 4000.0,
                 "capitaux_propres_pg_31_12_2025": 6000.0})
    assert e["roe"]["valeur"] == 20.0 and "MOYENS" in e["roe"]["base"]
    assert fs.noter(e, _med())["criteres"]["rentabilite"]["note"] == 8.5      # écart 10 → 8,5


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
        assert c["rentabilite"]["etat"] == fs.SUSPENDU and "juste valeur" in c["rentabilite"]["motif"]
        assert c["rentabilite"]["valeur"] == 9.0                    # affiché, non noté
        assert c["croissance"]["note"] == 7.5 and "BPA exclu" in c["croissance"]["mesure"]
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
