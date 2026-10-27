"""Lot B — quatre corrections qui changent la note (accord R8 du 22/10/2026).

Audit verificateur-finance. Chaque test est construit à la main : il fixe le
CAS qui a motivé la correction, pas seulement la forme du code.

  B1  croissance absente : retirée et poids remis à l'échelle, jamais 0 %
  B2  base S1 2025 négative : pas de croissance BPA, même publiée (HPS)
  B3  T2S : le même nombre d'actions pour la capitalisation et le P/B
  B4  P/B sur les fonds propres les plus récents relevés sur pièce
"""

import json
import sys
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

from pipeline.smart_money.fond_score import detail_fond_score  # noqa: E402
from pipeline.resultats_semestriels import douze_mois  # noqa: E402


def _fiche(**kw):
    """Fiche minimale : seule la croissance est mesurée (le reste est absent)."""
    return {"X": {"secteur": "Industrie", **kw}}


def _croissance(fiche):
    return detail_fond_score("X", fiche, per_publie=None, croissance_sourcee=True)["composantes"]["croissance"]


# ── B1 ────────────────────────────────────────────────────────────────────

def test_b1_ca_absent_la_croissance_est_celle_du_bpa_seul():
    # Avant : 15,1 × 0,6 + 0 × 0,4 = 9,06 % → 5,5. Après : 15,1 % → 6,5.
    c = _croissance(_fiche(croissance_bpa=15.1, croissance_ca=None))
    assert c["note"] == 6.5
    assert "15.1 %" in c["mesure"] and "BPA seul" in c["mesure"]


def test_b1_bpa_absent_la_croissance_est_celle_du_ca_seul():
    # M2M : 0,4 × 36,5 = 14,6 % → 6,5 ; après 36,5 % → 7,5.
    c = _croissance(_fiche(croissance_bpa=None, croissance_ca=36.5))
    assert c["note"] == 7.5
    assert "CA seul" in c["mesure"]


def test_b1_un_zero_mesure_reste_un_zero():
    # Zéro n'est pas une absence : 0 % de CA garde son poids.
    c = _croissance(_fiche(croissance_bpa=15.1, croissance_ca=0.0))
    assert c["mesure"].startswith("croissance pondérée 9.06 %")
    assert c["note"] == 5.5


def test_b1_les_deux_absents_la_composante_n_est_pas_notee():
    c = _croissance(_fiche(croissance_bpa=None, croissance_ca=None))
    assert c["note"] is None and "ni croissance" in c["motif"]


def test_b1_deux_parties_formule_inchangee():
    c = _croissance(_fiche(croissance_bpa=10.0, croissance_ca=20.0))
    assert c["mesure"].startswith("croissance pondérée 14 %")


# ── B2 ────────────────────────────────────────────────────────────────────

_HPS = {"rnpg_exercice_2025": 102.0, "rnpg_s1_2026": 40.0, "rnpg_s1_2025": -47.254113,
        "actions": 7_034_940, "croissance_bpa_publiee": 173.7,
        "ca_s1_2026": 701.9, "ca_s1_2025": 615.742478}


def test_b2_base_negative_pas_de_croissance_bpa_meme_publiee():
    m = douze_mois(dict(_HPS))
    assert "croissance_bpa" not in m
    assert m["croissance_bpa_publiee_non_retenue"] == 173.7
    assert m["croissance_bpa_base_negative"] == pytest.approx(-47.254113)
    assert m["croissance_ca"] == pytest.approx(14.0, abs=0.1)


def test_b2_base_negative_sans_pourcentage_publie_meme_regle():
    t = dict(_HPS)
    t.pop("croissance_bpa_publiee")
    m = douze_mois(t)
    assert "croissance_bpa" not in m and "croissance_bpa_publiee_non_retenue" not in m


def test_b2_base_positive_la_croissance_se_calcule():
    t = dict(_HPS, rnpg_s1_2025=20.0)
    assert douze_mois(t)["croissance_bpa"] == 100.0


def test_b2_hps_publie_n_est_plus_note_sur_173_pour_cent():
    f = json.loads((RACINE / "fondamentaux.json").read_text(encoding="utf-8"))
    assert f["HPS"]["croissance_bpa"] is None
    assert f["HPS"]["croissance_bpa_non_retenue"]["publiee"] == 173.7
    for t in ("HPS", "M2M", "SNP", "UNI"):
        assert f[t].get("croissance_bpa") is None, t
        assert "base négative" in f[t]["croissance_bpa_non_retenue"]["motif"], t


# ── B3 / B4 ───────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def moteur():
    import update_data
    if not update_data.FAITS_DATA:
        update_data.FAITS_DATA = json.loads(
            (RACINE / "pipeline" / "faits_financiers.json").read_text(encoding="utf-8"))
    return update_data


def test_b3_t2s_un_seul_nombre_d_actions(moteur):
    officiel = moteur._actions_bourse("T2S")
    assert officiel == 22_584_118
    assert moteur._actions_pb("T2S") == officiel
    d = moteur._pb_detail("T2S", 100.0)
    assert d["actions"] == officiel
    assert d["pb"] == round(100.0 * officiel / (d["fonds_propres"] * 1e6), 2)


def test_b3_t2s_la_reserve_dit_que_l_introduction_n_est_pas_dans_les_fonds_propres(moteur):
    r = moteur._pb_detail("T2S", 100.0)["reserve"]
    assert "introduction en bourse" in r and "fonds propres" in r


def test_b3_le_bpa_reste_sur_le_nombre_pondere():
    b = json.loads((RACINE / "bpa.json").read_text(encoding="utf-8"))["T2S"]
    assert b.get("actions_12m") != 22_584_118


def test_b3_le_seul_titre_dont_le_nombre_change_est_t2s(moteur):
    differents = [t for t in moteur.TICKERS_ALL
                  if moteur._actions_bourse(t) and moteur._actions_sourcees(t)
                  and abs(moteur._actions_bourse(t) / moteur._actions_sourcees(t) - 1) > 1e-4]
    assert differents == ["T2S"]


def test_b4_tma_fonds_propres_du_30_06(moteur):
    fp = moteur._fonds_propres_pb("TMA")
    assert fp["date"] == "2026-06-30" and fp["valeur"] == 1468.318
    # 5,94 → 8,03 au même cours : rapport 1 984,665 ÷ 1 468,318.
    avant = moteur._actions_pb("TMA") / (1984.665 * 1e6)
    assert moteur._pb_detail("TMA", 1000.0)["pb"] / (1000.0 * avant) == pytest.approx(1984.665 / 1468.318, rel=1e-3)


def test_b4_iam_releve_au_30_06_avec_sa_citation(moteur):
    s1 = json.loads((RACINE / "datasets" / "resultats_s1_2026.json").read_text(encoding="utf-8"))["titres"]["IAM"]
    assert s1["capitaux_propres_pg_30_06_2026"] == 19409.0
    assert "p.2" in s1["source_capitaux_propres"] and "20 478 19 409" in s1["source_capitaux_propres"]
    assert moteur._fonds_propres_pb("IAM")["date"] == "2026-06-30"


def test_b4_mng_tgcc_releves_au_30_06_avec_citation_et_sha256(moteur):
    """27/10/2026 : MNG 15 439 (Managem_S1_26.pdf p.2) et TGCC 4 459,032 (TGCC_S1_26.pdf p.2)."""
    s1 = json.loads((RACINE / "datasets" / "resultats_s1_2026.json").read_text(encoding="utf-8"))["titres"]
    assert s1["MNG"]["capitaux_propres_pg_30_06_2026"] == 15439.0
    assert "15 439 11 478" in s1["MNG"]["source_capitaux_propres"] and "5bffbe9b" in s1["MNG"]["source_capitaux_propres"]
    assert s1["TGCC"]["capitaux_propres_pg_30_06_2026"] == 4459.032
    assert "4 459 032 4 544 126" in s1["TGCC"]["source_capitaux_propres"] and "29a6ba5c" in s1["TGCC"]["source_capitaux_propres"]
    for t in ("MNG", "TGCC"):
        assert moteur._fonds_propres_pb(t)["date"] == "2026-06-30"


def test_tgcc_augmentation_de_capital_constatee_le_24_07_2025():
    import bvc_config
    (m,) = bvc_config.HISTORIQUE_ACTIONS["TGCC"]["mouvements"]
    assert (m["date"], m["avant"], m["apres"]) == ("2025-07-24", 31639850, 34674332)
    assert m["apres"] - m["avant"] == 3034482 and "24 juillet 2025" in m["source"]
    assert bvc_config.actions_ponderees("TGCC", "2025-01-01", "2025-06-30", 34674332)["nombre"] == 31639850


def test_b4_sans_releve_s1_le_31_12_reste(moteur):
    s1 = json.loads((RACINE / "datasets" / "resultats_s1_2026.json").read_text(encoding="utf-8"))["titres"]
    for t, e in moteur.FAITS_DATA.items():
        if t.startswith("_") or not isinstance(e, dict):
            continue
        if (e.get("faits") or {}).get("capitaux_propres_part_groupe") and \
                not (s1.get(t) or {}).get("capitaux_propres_pg_30_06_2026"):
            assert moteur._fonds_propres_pb(t)["date"].endswith("-12-31"), t
            return
    pytest.skip("aucun titre au seul 31/12")


def test_b4_le_30_06_ne_cree_pas_de_pb(moteur):
    # CDM : fonds propres S1 relevés, aucun pour l'exercice → pas de P/B créé.
    assert moteur._pb_sourcé("CDM", 100.0) is None


def test_b4_le_libelle_dit_la_date_des_fonds_propres():
    src = (RACINE / "terminal.src.html").read_text(encoding="utf-8")
    assert "m.pb_fonds_propres_au" in src and "m.pb_reserve" in src
    moteur_src = (RACINE / "update_data.py").read_text(encoding="utf-8")
    assert '"pb_fonds_propres_au":' in moteur_src and '"pb_reserve":' in moteur_src
