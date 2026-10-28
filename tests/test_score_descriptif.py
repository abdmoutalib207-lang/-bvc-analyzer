"""Score descriptif (référentiel BVC Nour) — mode fantôme, 28/10/2026.

Quatre familles ici, une cinquième à côté :
  1. cas limites de la formule, attendus calculés À LA MAIN (bornes 45 et 70 du
     RSI, rapport de volume 0,8 et 3, liquidité 1 et 5 MDH, ROE 5 et 12 %,
     couverture 70, cours égal à la moyenne) ;
  2. états : stale / suspendu → NON_CALCULABLE ; historique court, liquidité
     non établie, reprise récente → PARTIEL et valeur nulle ;
  3. FIDÉLITÉ À NOUR : la formule est comparée, sur 3 000 tirages, à une copie
     littérale de `canonical_score` (nour-quant-v1) ;
  4. égalité avec NOTRE moteur : masque des séances échangées et RSI incrémental
     identiques à `clotures_echangees` / `calc_rsi` ;
  5. (voir `test_score_descriptif_fantome.py`) le branchement en mode fantôme.
"""
import copy
import json
import random
import sys
from pathlib import Path

import pandas as pd
import pytest

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))
sys.path.insert(0, str(RACINE / "pipeline"))

from pipeline import score_descriptif as sd  # noqa: E402
from pipeline.seance import clotures_echangees  # noqa: E402


def entrees(**sur):
    """Une situation de référence : tout favorable sauf la liquidité (2 MDH) et le ROE (8 %)."""
    base = dict(prix=100.0, ma20=90.0, ma50=95.0, rsi=50.0, ratio_volume=1.0,
                montant_median=2_000_000.0, liquidite_prete=True, roe=8.0)
    base.update(sur)
    return base


def points(r, nom):
    return r["facteurs"][nom]["points"]


# ── 1. la formule, à la main ────────────────────────────────────────────────

def test_cas_de_reference_calcule_a_la_main():
    # 20 + 15 + 15 + 10 + 10 (2 MDH) + 10 (ROE 8 %) = 80 sur 100
    r = sd.score_descriptif(**entrees())
    assert (r["etat"], r["valeur"], r["couverture_pct"]) == ("CALCULABLE", 80.0, 100)
    assert [points(r, n) for n in ("tendance20", "tendance50", "momentum", "activité",
                                   "liquidité", "rentabilité")] == [20, 15, 15, 10, 10, 10]


def test_sans_rentabilite_le_facteur_n_herite_d_aucun_poids():
    # 70 points sur 80 couverts → 87,5 ; surtout PAS 70 sur 100.
    r = sd.score_descriptif(**entrees(roe=None))
    assert (r["couverture_pct"], r["valeur"]) == (80, 87.5)    # (20+15+15+10+10)=70 → 70/80
    assert r["facteurs"]["rentabilité"]["points"] is None
    assert r["facteurs"]["rentabilité"]["poids"] == 20          # le poids nominal reste lisible


@pytest.mark.parametrize("prix,ma,attendu", [(100.01, 100.0, 20), (100.0, 100.0, 0), (99.99, 100.0, 0)])
def test_tendance_est_strictement_au_dessus(prix, ma, attendu):
    assert points(sd.score_descriptif(**entrees(prix=prix, ma20=ma)), "tendance20") == attendu


@pytest.mark.parametrize("rsi,attendu", [
    (70.0, 15), (70.01, 0), (45.0, 15), (44.99, 7.5), (30.0, 7.5), (29.99, 0), (0.0, 0), (100.0, 0)])
def test_bornes_du_rsi(rsi, attendu):
    assert points(sd.score_descriptif(**entrees(rsi=rsi)), "momentum") == attendu


@pytest.mark.parametrize("ratio,attendu", [
    (0.8, 10), (0.79, 5), (0.0, 5), (3.0, 10), (3.01, 2), (2.996, 10),   # 2,996 s'arrondit à 3,00
    (0.795, 10),                                                        # 0,795 s'arrondit à 0,80
    (0.794, 5)])
def test_bornes_du_rapport_de_volume(ratio, attendu):
    assert points(sd.score_descriptif(**entrees(ratio_volume=ratio)), "activité") == attendu


@pytest.mark.parametrize("montant,attendu", [
    (5_000_000, 20), (4_999_999, 10), (1_000_000, 10), (999_999, 0), (0, 0)])
def test_bornes_de_la_liquidite(montant, attendu):
    assert points(sd.score_descriptif(**entrees(montant_median=montant)), "liquidité") == attendu


@pytest.mark.parametrize("roe,attendu", [(12.0, 20), (11.99, 10), (5.0, 10), (4.99, 0), (-38.0, 0)])
def test_bornes_du_roe(roe, attendu):
    assert points(sd.score_descriptif(**entrees(roe=roe)), "rentabilité") == attendu


def test_la_liquidite_non_etablie_retire_le_facteur():
    r = sd.score_descriptif(**entrees(liquidite_prete=False), decision="LIMITÉ",
                            motif="liquidité insuffisante")
    assert r["facteurs"]["liquidité"]["points"] is None


# ── 2. couverture et états ──────────────────────────────────────────────────

def test_couverture_exactement_70_est_publiee():
    # ni ROE (20) ni rapport de volume (10) : 100 − 30 = 70 ; points 20+15+15+10 = 60 → 85,71
    r = sd.score_descriptif(**entrees(roe=None, ratio_volume=None))
    assert (r["couverture_pct"], r["etat"], r["valeur"]) == (70, "CALCULABLE", 85.71)


def test_couverture_65_donne_partiel_et_valeur_nulle():
    # ni ROE (20) ni MM50 (15) : couverture 65 < 70
    r = sd.score_descriptif(**entrees(roe=None, ma50=None))
    assert (r["couverture_pct"], r["etat"], r["valeur"]) == (65, "PARTIEL", None)
    assert "65" in r["motif"]


def test_couverture_complete_mais_titre_non_observable_reste_partiel():
    for decision in ("LIMITÉ",):
        r = sd.score_descriptif(**entrees(), decision=decision, motif="historique limité")
        assert (r["couverture_pct"], r["etat"], r["valeur"]) == (100, "PARTIEL", None)


@pytest.mark.parametrize("decision", ["SUSPENDU", "INDISPONIBLE"])
def test_suspendu_et_indisponible_sont_non_calculables(decision):
    r = sd.score_descriptif(**entrees(), decision=decision, motif="x")
    assert (r["etat"], r["valeur"], r["couverture_pct"], r["facteurs"]) == ("NON_CALCULABLE", None, 0, {})


def test_etat_donnees_suspendu_prime_sur_tout():
    assert sd.etat_donnees(suspendu=True, stale=True, prix=None)[0] == "SUSPENDU"


def test_etat_donnees_stale_donne_indisponible():
    d, motif = sd.etat_donnees(stale=True, prix=100.0, n_seances=500, liquidite_prete=True)
    assert d == "INDISPONIBLE" and "stale" in motif


@pytest.mark.parametrize("prix", [None, 0, -1, float("nan")])
def test_etat_donnees_sans_cours_valide(prix):
    assert sd.etat_donnees(prix=prix, n_seances=500, liquidite_prete=True)[0] == "INDISPONIBLE"


def test_etat_donnees_cloture_en_desaccord_est_indisponible():
    assert sd.etat_donnees(prix=100.0, cloture_coherente=False, n_seances=500,
                           liquidite_prete=True)[0] == "INDISPONIBLE"


@pytest.mark.parametrize("sur,attendu", [
    (dict(reprise_recente=True), "LIMITÉ"),
    (dict(n_seances=49), "LIMITÉ"),
    (dict(liquidite_prete=False), "LIMITÉ"),
    (dict(n_seances=50), "OBSERVABLE")])
def test_etat_donnees_limite_et_observable(sur, attendu):
    kw = dict(prix=100.0, n_seances=500, liquidite_prete=True)
    kw.update(sur)
    assert sd.etat_donnees(**kw)[0] == attendu


# ── 3. fidélité à Nour ──────────────────────────────────────────────────────

def _canonical_score_nour(quality, tech, fundamental):
    """Copie LITTÉRALE de `canonical_score` (BVC Nour, SCORE_VERSION nour-quant-v1),
    relevée le 28/10/2026 comme DONNÉE de référence. Ne pas « améliorer » : sa
    seule fonction est de dire ce que Nour calcule."""
    if quality.get("decision") in {"SUSPENDU", "INDISPONIBLE"}:
        return {"value": None, "state": "NON_CALCULABLE", "coverage_pct": 0, "contributors": {}}
    contributors = {}
    price = quality.get("price")
    if price and tech.get("sma20") is not None:
        contributors["tendance20"] = {"weight": 20, "points": 20 if price > tech["sma20"] else 0}
    if price and tech.get("sma50") is not None:
        contributors["tendance50"] = {"weight": 15, "points": 15 if price > tech["sma50"] else 0}
    if tech.get("rsi14") is not None:
        rsi = tech["rsi14"]
        contributors["momentum"] = {"weight": 15, "points": 15 if 45 <= rsi <= 70 else 7.5 if 30 <= rsi < 45 else 0}
    if tech.get("volume_vs_median20") is not None:
        ratio = tech["volume_vs_median20"]
        contributors["activité"] = {"weight": 10, "points": 10 if .8 <= ratio <= 3 else 5 if ratio < .8 else 2}
    liq = quality.get("liquidity") or {}
    if liq.get("ready") and liq.get("median_turnover_mad_estimated") is not None:
        amount = liq["median_turnover_mad_estimated"]
        contributors["liquidité"] = {"weight": 20, "points": 20 if amount >= 5e6 else 10 if amount >= 1e6 else 0}
    if fundamental.get("roe_pct") is not None:
        roe = fundamental["roe_pct"]
        contributors["rentabilité"] = {"weight": 20, "points": 20 if roe >= 12 else 10 if roe >= 5 else 0}
    coverage = sum(x["weight"] for x in contributors.values())
    value = round(sum(x["points"] for x in contributors.values()) / coverage * 100, 2) if coverage else None
    state = "CALCULABLE" if quality.get("decision") == "OBSERVABLE" and coverage >= 70 else "PARTIEL"
    if state == "PARTIEL":
        value = None
    return {"value": value, "state": state, "coverage_pct": coverage, "contributors": contributors}


def test_identique_a_nour_sur_3000_tirages():
    rng = random.Random(28102026)
    ecarts = []
    for _ in range(3000):
        prix = round(rng.uniform(5, 500), 2)
        sma20 = None if rng.random() < .1 else round(prix * rng.uniform(.8, 1.2), 2)
        sma50 = None if rng.random() < .15 else round(prix * rng.uniform(.8, 1.2), 2)
        rsi = None if rng.random() < .1 else round(rng.uniform(0, 100), 2)
        ratio = None if rng.random() < .15 else round(rng.choice([0, .79, .8, 1, 3, 3.01, 5]) + rng.random() * .02, 2)
        montant = rng.choice([0, 9e5, 1e6, 3e6, 5e6, 8e6])
        prete = rng.random() < .85
        roe = None if rng.random() < .2 else round(rng.uniform(-30, 40), 1)
        decision = rng.choice(["OBSERVABLE"] * 6 + ["LIMITÉ", "SUSPENDU", "INDISPONIBLE"])
        nour = _canonical_score_nour(
            {"decision": decision, "price": prix,
             "liquidity": {"ready": prete, "median_turnover_mad_estimated": montant}},
            {"sma20": sma20, "sma50": sma50, "rsi14": rsi, "volume_vs_median20": ratio},
            {"roe_pct": roe})
        # notre ratio brut est arrondi à 2 décimales par le module, comme chez Nour
        nous = sd.score_descriptif(prix=prix, ma20=sma20, ma50=sma50, rsi=rsi, ratio_volume=ratio,
                                   montant_median=montant, liquidite_prete=prete, roe=roe,
                                   decision=decision)
        mine = (nous["valeur"], nous["etat"], nous["couverture_pct"])
        theirs = (nour["value"], nour["state"], nour["coverage_pct"])
        if mine != theirs:
            ecarts.append((mine, theirs))
        for nom, c in nour["contributors"].items():
            assert nous["facteurs"][nom]["points"] == c["points"], nom
    assert not ecarts, ecarts[:5]


# ── 4. égalité avec NOTRE moteur ────────────────────────────────────────────

def _bougies_reelles(t):
    f = RACINE / "pipeline" / "candles" / f"{t}.json"
    return json.loads(f.read_text(encoding="utf-8"))


def test_volumes_equivalents_apres_split():
    b = [{"d": "2026-07-24", "c": 1250, "v": 345}, {"d": "2026-07-27", "c": 1364, "v": 4918}]
    assert sd.volumes_equivalents("MNG", b) == [3450.0, 4918.0]       # × 10 avant le 27/07, rien après
    assert sd.volumes_equivalents("IAM", b) == [345.0, 4918.0]        # sans split : inchangé
    assert sd.volumes_equivalents("MNG", [{"d": "2026-07-24", "c": 1, "v": None}]) == [0.0]


def test_mesures_liquidite_9_puis_10_seances_actives():
    closes = [10.0] * 25
    vols = [0.0] * 25
    for i in range(9):
        vols[-1 - 2 * i] = 100.0           # 9 séances échangées sur les 20 dernières
    m = sd.mesures_series(closes, vols)
    assert (m["seances_actives"], m["liquidite_prete"]) == (9, False)
    vols[-2] = 100.0                       # une dixième
    m = sd.mesures_series(closes, vols)
    assert (m["seances_actives"], m["liquidite_prete"]) == (10, True)
    assert m["montant_median"] == 1000.0   # médiane de 100 × 10 DH


def test_rapport_de_volume_mediane_nulle_ou_historique_court():
    # 21 bougies minimum ; médiane des 20 précédentes nulle → pas de rapport (Nour : None)
    assert sd.mesures_series([10.0] * 20, [5.0] * 20)["ratio_volume"] is None
    assert sd.mesures_series([10.0] * 21, [0.0] * 20 + [5.0])["ratio_volume"] is None
    assert sd.mesures_series([10.0] * 21, [4.0] * 20 + [8.0])["ratio_volume"] == 2.0
    # le jour n'entre PAS dans sa propre médiane
    assert sd.mesures_series([10.0] * 21, [4.0] * 20 + [1000.0])["ratio_volume"] == 250.0


def test_liquidite_apres_reprise_ne_regarde_que_les_seances_posterieures():
    closes = [10.0] * 30
    vols = [100.0] * 30
    assert sd.mesures_series(closes, vols, n_depuis_reprise=5)["fenetre"] == 5
    assert sd.mesures_series(closes, vols, n_depuis_reprise=5)["liquidite_prete"] is False
    assert sd.mesures_series(closes, vols, n_depuis_reprise=15)["liquidite_prete"] is True


def test_masque_echange_egal_a_clotures_echangees_sur_les_81_series():
    for f in sorted((RACINE / "pipeline" / "candles").glob("*.json")):
        b = json.loads(f.read_text(encoding="utf-8"))
        if not b:
            continue
        df = pd.DataFrame(b)
        v = df["v"].fillna(0)
        attendu = clotures_echangees(df["c"], df["v"], df["h"], df["l"], df["o"])
        m = sd.masque_echange(df["o"].tolist(), df["h"].tolist(), df["l"].tolist(),
                              df["c"].tolist(), v.tolist())
        assert df["c"][pd.Series(m)].tolist() == attendu.tolist(), f.stem


def test_serie_rsi_egale_calc_rsi_a_chaque_date(ud):
    for t in ("ADH", "IAM", "BCP", "ZLD", "MNG"):
        b = _bougies_reelles(t)
        df = pd.DataFrame(b)
        ce = clotures_echangees(df["c"], df["v"], df["h"], df["l"], df["o"]).tolist()
        inc = sd.serie_rsi(ce)
        for k in list(range(13, len(ce), 37)) + [len(ce) - 1]:
            assert inc[k] == ud.calc_rsi(pd.Series(ce[:k + 1])), (t, k)


def test_serie_rsi_limites_de_la_definition():
    assert sd.serie_rsi([float(i) for i in range(1, 20)])[-1] == 100.0         # que des hausses
    assert sd.serie_rsi([float(i) for i in range(20, 1, -1)])[-1] == 0.0       # que des baisses
    assert sd.serie_rsi([5.0] * 20)[-1] == 50.0                                # plat : indéterminé
    assert sd.serie_rsi([1.0] * 14) == [None] * 14                             # 14 clôtures : insuffisant
    assert sd.serie_rsi([1.0, 2.0] * 8)[14] is not None                        # 15 clôtures : défini


# ── score_titre : le titre de data.json ─────────────────────────────────────

def _titre(**meta):
    """Un titre minimal, 60 séances échangées, cours au-dessus de ses moyennes."""
    bougies = [{"d": f"2026-{(i // 28) + 7:02d}-{(i % 28) + 1:02d}", "o": 100 + i, "h": 100 + i,
                "l": 100 + i, "c": 100.0 + i, "v": 5000.0 + i} for i in range(60)]
    last = bougies[-1]
    rec = {"symbol": "ZZZ", "price": last["c"], "ma20": 150.0, "ma50": 135.0, "rsi": 60.0,
           "_meta": {"stale": False, "suspendu": False, "prix_asof": last["d"], **meta},
           "ratios_publies": {"roe_2025": {"valeur": 14.0}}}
    return rec, bougies


def test_score_titre_nominal_et_sans_effet_de_bord():
    rec, b = _titre()
    avant = copy.deepcopy((rec, b))
    r = sd.score_titre(rec, b)
    assert (rec, b) == avant
    assert r["etat"] == "CALCULABLE" and r["couverture_pct"] == 100
    assert points(r, "rentabilité") == 20 and points(r, "tendance20") == 20
    assert set(r) >= {"valeur", "etat", "couverture_pct", "version", "facteurs"}
    assert r["version"] == sd.VERSION


def test_score_titre_stale_donne_non_calculable():
    rec, b = _titre(stale=True)
    r = sd.score_titre(rec, b)
    assert (r["etat"], r["valeur"]) == ("NON_CALCULABLE", None)


def test_score_titre_sans_meta_est_stale_par_defaut():
    rec, b = _titre()
    del rec["_meta"]
    assert sd.score_titre(rec, b)["etat"] == "NON_CALCULABLE"


def test_score_titre_suspendu():
    rec, b = _titre(suspendu=True)
    assert sd.score_titre(rec, b)["etat"] == "NON_CALCULABLE"


def test_score_titre_reprise_recente_est_partiel():
    rec, b = _titre(reprise_recente=True, seances_depuis_reprise=12)
    r = sd.score_titre(rec, b)
    assert (r["etat"], r["valeur"]) == ("PARTIEL", None)
    assert "reprise" in r["motif"]


def test_score_titre_historique_court_est_partiel():
    rec, b = _titre()
    r = sd.score_titre(rec, b[-30:])
    assert (r["etat"], r["valeur"]) == ("PARTIEL", None)


def test_score_titre_cours_different_de_la_derniere_cloture_est_indisponible():
    rec, b = _titre()
    rec["price"] += 5
    assert sd.score_titre(rec, b)["etat"] == "NON_CALCULABLE"


def test_score_titre_sans_chandelles():
    rec, _ = _titre()
    assert sd.score_titre(rec, None)["etat"] == "NON_CALCULABLE"
    assert sd.score_titre(rec, [])["etat"] == "NON_CALCULABLE"


def test_roe_vient_de_roe_2025_et_de_lui_seul():
    assert sd.roe_publie({"ratios_publies": {"roe_2025": {"valeur": 14.0}}}) == 14.0
    # ni le ROE glissant, ni le prévisionnel DATA+, ni la note métier ne le remplacent
    assert sd.roe_publie({"ratios_publies": {"roe_12m": {"valeur": 20.0}}, "fwd": {"roe_25": 30.0}}) is None
    assert sd.roe_publie({}) is None
    assert sd.roe_publie({"ratios_publies": {"roe_2025": {"valeur": None}}}) is None
