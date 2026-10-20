"""Grille bancaire (20/10/2026) : bilan bancaire et coefficient d'exploitation
des 7 banques. Décrit le CODE (grilles, renormalisation, recalcul) et relit les
FAITS sur pièce (pipeline/faits_financiers.json › _grille_bancaire)."""
import json
import sys
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

from pipeline import ratios_financiers as RF  # noqa: E402
from pipeline.smart_money import fond_score as F  # noqa: E402

BANQUES = ("ATW", "BCP", "BOA", "CIH", "CDM", "CFGB", "BMC")
FAITS = json.loads((RACINE / "pipeline" / "faits_financiers.json").read_text(encoding="utf-8"))
FOND = json.loads((RACINE / "fondamentaux.json").read_text(encoding="utf-8"))
GB = FAITS["_grille_bancaire"]["titres"]


# ── les grilles ──
@pytest.mark.parametrize("nom,x,attendu", [
    ("solvabilite_globale", 11.99, 1.5),   # sous le minimum BAM
    ("solvabilite_globale", 12.0, 4.0),
    ("solvabilite_globale", 12.99, 4.0),
    ("solvabilite_globale", 13.0, 5.5),
    ("solvabilite_globale", 14.0, 7.0),
    ("solvabilite_globale", 14.5, 8.5),
    ("cout_du_risque_encours", 0.5, 8.5),
    ("cout_du_risque_encours", 0.51, 7.0),
    ("cout_du_risque_encours", 1.0, 7.0),
    ("cout_du_risque_encours", 2.0, 5.5),
    ("cout_du_risque_encours", 2.01, 4.0),
    ("couverture_bucket3", 85.0, 8.5),
    ("couverture_bucket3", 84.9, 7.0),
    ("couverture_bucket3", 65.0, 7.0),
    ("couverture_bucket3", 45.0, 5.5),
    ("couverture_bucket3", 44.9, 4.0),
    ("coefficient_exploitation", 45.0, 8.5),
    ("coefficient_exploitation", 50.0, 7.0),
    ("coefficient_exploitation", 55.0, 5.5),
    ("coefficient_exploitation", 55.01, 4.0),
])
def test_paliers(nom, x, attendu):
    assert F.grille_bancaire(nom, x) == attendu


def test_minimum_bam_cite_sur_piece():
    m = FAITS["_grille_bancaire"]["minimum_solvabilite_bam"]
    assert m["valeur"] == F.SOLVABILITE_MIN_BAM == 12.0
    assert len(m["pieces"]) >= 2 and all(p.get("page") and "12" in p["note"] for p in m["pieces"])


def test_seuils_figes():
    """Stabilité avant tout (20/10/2026) : les seuils ne dérivent pas avec la
    distribution. Les changer est une décision (R8), pas un recalcul."""
    assert {k: v[:2] for k, v in F.PALIERS_BANCAIRES.items()} == {
        "solvabilite_globale": ("haut", (2.5, 2.0, 1.0)),
        "cout_du_risque_encours": ("bas", (0.5, 1.0, 2.0)),
        "couverture_bucket3": ("haut", (85.0, 65.0, 45.0)),
        "coefficient_exploitation": ("bas", (45.0, 50.0, 55.0)),
    }
    assert F.TAUX_BUCKET3_MIN_NOTE == 2.0 and F.NOTES_QUARTS == (8.5, 7.0, 5.5, 4.0)
    assert all(len(v[2]) > 40 for v in F.PALIERS_BANCAIRES.values())   # justification écrite


def test_couverture_non_notee_sous_deux_pour_cent_de_bucket3():
    """CFGB : Bucket 3 à 1,46 % de l'encours brut — couverture retirée, réserve gardée."""
    b = _detail("CFGB")["composantes"]["bilan"]
    cov = [s for s in b["sous_mesures"] if s["nom"] == "couverture_bucket3"][0]
    assert cov["note"] is None and cov["taux_bucket3"] == 1.46
    assert b["note"] == round((F.grille_bancaire("solvabilite_globale", 18.66)
                               + F.grille_bancaire("cout_du_risque_encours", 0.233)) / 2, 2)
    assert "sous le seuil de 2 %" in b["reserve"] and "1,46 %" in b["reserve"]
    for s in BANQUES:
        if s != "CFGB":
            c = [x for x in _detail(s)["composantes"]["bilan"]["sous_mesures"] if x["nom"] == "couverture_bucket3"][0]
            assert c["note"] is not None and c["taux_bucket3"] >= 2.0


# ── les ratios, recalculés depuis les faits ──
def test_couverture_recalculee_jamais_le_taux_publie():
    for b in BANQUES:
        r = RF.calculer_bancaire(GB[b])["couverture_bucket3"]
        f = GB[b]["faits"]
        assert r["valeur"] == round(f["bucket3_depreciations_30_06_2026"]["valeur"]
                                    / f["bucket3_brut_30_06_2026"]["valeur"] * 100, 2)
    # CDM publie 86,2 % (toutes dépréciations ÷ Bucket 3) : 71,68 recalculé ; CIH 56,7 % social : 48,75.
    assert FOND["CDM"]["ratios_publies"]["couverture_bucket3"]["valeur"] == 71.68
    assert FOND["CIH"]["ratios_publies"]["couverture_bucket3"]["valeur"] == 48.75
    assert "4 259" in FOND["CDM"]["ratios_publies"]["couverture_bucket3"]["reserve"]


def test_coefficient_douze_mois_une_seule_definition():
    f = GB["ATW"]["faits"]
    s = {k: f[f"{k}_2025"]["valeur"] + f[f"{k}_s1_2026"]["valeur"] - f[f"{k}_s1_2025"]["valeur"]
         for k in ("cge", "dap", "pnb")}
    r = RF.calculer_bancaire(GB["ATW"])["coefficient_exploitation"]
    assert r["valeur"] == round((s["cge"] + s["dap"]) / s["pnb"] * 100, 2) == 38.59
    assert r["date"] == "2026-06-30" and r["periode"].startswith("12 mois")


def test_un_terme_semestriel_manquant_rabat_sur_l_exercice():
    e = json.loads(json.dumps(GB["CIH"]))
    del e["faits"]["pnb_s1_2025"]
    r = RF.calculer_bancaire(e)["coefficient_exploitation"]
    assert r["date"] == "2025-12-31" and r["valeur"] == 42.93   # = recalcul du relevé (2 088 001 + 240 029) ÷ 5 422 526


def test_cout_du_risque_sur_encours_moyen_de_l_exercice():
    f = GB["BOA"]["faits"]
    r = RF.calculer_bancaire(GB["BOA"])["cout_du_risque_encours"]
    moy = (f["encours_31_12_2024"]["valeur"] + f["encours_31_12_2025"]["valeur"]) / 2
    assert r["valeur"] == round(f["cdr_2025"]["valeur"] / moy * 100, 3)
    assert "30/06/2025" in r["periode"]


def test_ratios_publies_synchrones_avec_les_faits():
    for b in BANQUES:
        r = RF.calculer_bancaire(GB[b])
        for k, v in r.items():
            assert FOND[b]["ratios_publies"][k] == v, (b, k)


# ── la note ──
def _detail(sym):
    return F.detail_fond_score(sym, FOND, per_publie=10.0, croissance_sourcee=True)


def test_renormalisation_bcp_sans_solvabilite():
    d = _detail("BCP")
    b = d["composantes"]["bilan"]
    noms = [s["nom"] for s in b["sous_mesures"]]
    assert noms == ["cout_du_risque_encours", "couverture_bucket3"]
    assert b["note"] == round(sum(s["note"] for s in b["sous_mesures"]) / 2, 2)
    assert "solvabilité retirée" in b["reserve"] and "NON PUBLIÉE" in b["reserve"]
    assert d["couverture"] == 1.0


def test_sous_mesure_absente_retiree_et_poids_renormalise():
    fd = json.loads(json.dumps(FOND))
    del fd["ATW"]["ratios_publies"]["couverture_bucket3"]
    b = F.detail_fond_score("ATW", fd, per_publie=10.0, croissance_sourcee=True)["composantes"]["bilan"]
    assert len(b["sous_mesures"]) == 2
    assert b["note"] == round((F.grille_bancaire("solvabilite_globale", 13.13)
                               + F.grille_bancaire("cout_du_risque_encours", 0.851)) / 2, 2)


def test_coefficient_dans_la_qualite_pas_dans_le_bilan():
    d = _detail("ATW")
    q, b = d["composantes"]["qualite"], d["composantes"]["bilan"]
    assert [s["nom"] for s in q["sous_mesures"]] == ["coefficient_exploitation"]
    assert "coefficient" not in b["mesure"]
    assert q["note"] == round((F._grille_spread(15.3 - 10) + 8.5) / 2, 2)


@pytest.mark.parametrize("sym", BANQUES)
def test_les_sept_banques_ont_leur_bilan_et_leur_couverture_complete(sym):
    d = _detail(sym)
    assert d["composantes"]["bilan"]["note"] is not None and d["couverture"] == 1.0


def test_une_financiere_non_bancaire_garde_son_motif():
    autres = [s for s, f in FOND.items() if isinstance(f, dict) and F.est_financiere(f) and not F.est_banque(f)]
    assert autres
    for s in autres:
        c = F.detail_fond_score(s, FOND, per_publie=10.0, croissance_sourcee=True)["composantes"]
        assert c["bilan"]["note"] is None and "équivalent bancaire non intégré" in c["bilan"]["motif"]
        assert "sous_mesures" not in c["qualite"]
