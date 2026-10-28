"""Backtest du score descriptif (`pipeline/backtest_score_descriptif.py`) — 28/10/2026.

Ce que ces tests protègent, dans l'ordre où une erreur coûterait le plus :
  1. AUCUN REGARD VERS L'AVENIR : modifier les séances futures ne change pas
     le score d'une séance passée ;
  2. le panel rejoue EXACTEMENT ce que calcule le moteur (`score_titre`) ;
  3. les fenêtres qui traversent une rupture, un split ou une reprise sont
     écartées, et les indicateurs lus sur une série rompue aussi ;
  4. la statistique : Newey-West et p-valeur recalculés à la main ; aucun t
     publié sous les seuils d'effectif ;
  5. de bout en bout : un artefact complet, daté de la dernière séance, à
     l'octet près d'une exécution à l'autre.
"""
import json
import math
import random
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))
sys.path.insert(0, str(RACINE / "pipeline"))

import backtest_score_descriptif as bs  # noqa: E402
from pipeline import score_descriptif as sd  # noqa: E402


# ── outils ──────────────────────────────────────────────────────────────────

def jours(n, debut="2025-01-06"):
    """n jours ouvrés consécutifs (lundi-vendredi), sans fériés : suffit pour un banc d'essai."""
    d = pd.Timestamp(debut)
    out = []
    while len(out) < n:
        if d.weekday() < 5:
            out.append(d.strftime("%Y-%m-%d"))
        d += pd.Timedelta(days=1)
    return out


def serie(n=160, graine=7, saut=None):
    """Une marche aléatoire échangée chaque jour. `saut=(i, facteur)` : rupture au jour i."""
    rng = random.Random(graine)
    ds = jours(n)
    c, bars = 100.0, []
    for i, d in enumerate(ds):
        c = round(c * (1 + rng.uniform(-.02, .021)), 2)
        if saut and i == saut[0]:
            c = round(c * saut[1], 2)
        bars.append({"d": d, "o": c, "h": round(c * 1.004, 2), "l": round(c * .996, 2), "c": c,
                     "v": float(rng.randint(2000, 9000))})
    # ouverture/extrêmes cohérents (invariant OHLC)
    for b in bars:
        b["h"] = max(b["h"], b["o"], b["c"])
        b["l"] = min(b["l"], b["o"], b["c"])
    return ds, bars


def panel(bars, ds, masi=None, divs=(), roe=8.0, ticker="ZZZ"):
    cal = list(ds)
    cal_pos = {d: i for i, d in enumerate(cal)}
    masi = masi if masi is not None else {d: 1000.0 * (1 + .0005 * i) for i, d in enumerate(cal)}
    return pd.DataFrame(bs.panel_titre(ticker, bars, roe, cal_pos, cal, masi, list(divs)))


COLONNES_SCORE = ("sans", "avec", "decision", "montant", "prete", "rsi", "etat_sans", "etat_avec",
                  "pts_tendance20", "pts_tendance50", "pts_momentum", "pts_activité", "pts_liquidité")


@pytest.fixture
def sans_fichier(monkeypatch):
    """`serie_propre.charger` lit pipeline/candles : pour un titre fictif, pas de fichier."""
    monkeypatch.setattr(bs, "charger", lambda chemin, fin=None: None)


# ── 1. aucun regard vers l'avenir ───────────────────────────────────────────

def test_modifier_le_futur_ne_change_pas_le_score_passe(sans_fichier):
    ds, bars = serie()
    avant = panel(bars, ds)
    coupe = 100
    futur = [dict(b) for b in bars]
    rng = random.Random(1)
    for b in futur[coupe:]:
        b["c"] = round(b["c"] * rng.uniform(.5, 1.8), 2)
        b["o"], b["h"], b["l"] = b["c"], round(b["c"] * 1.01, 2), round(b["c"] * .99, 2)
        b["v"] = float(rng.randint(0, 50000))
    apres = panel(futur, ds)
    a, b = avant[avant["pos"] < coupe], apres[apres["pos"] < coupe]
    assert len(a) == len(b) > 40
    pd.testing.assert_frame_equal(a[list(COLONNES_SCORE)].reset_index(drop=True),
                                  b[list(COLONNES_SCORE)].reset_index(drop=True))
    # … alors que le rendement futur, lui, a bien changé : le test peut échouer
    fen = (avant["pos"] >= 85) & (avant["pos"] < coupe)           # sorties après la coupure
    assert not np.allclose(avant.loc[fen, "r"], apres.loc[fen, "r"])


def test_le_roe_actuel_ne_touche_que_la_variante_avec(sans_fichier):
    ds, bars = serie()
    a, b = panel(bars, ds, roe=30.0), panel(bars, ds, roe=-5.0)
    assert a["sans"].equals(b["sans"])                      # point-in-time : indifférent au ROE
    ok = a["avec"].notna()
    assert ok.any() and not (a.loc[ok, "avec"] == b.loc[ok, "avec"]).all()


def test_les_dividendes_n_entrent_que_dans_le_rendement(sans_fichier):
    ds, bars = serie()
    sans_div = panel(bars, ds)
    avec_div = panel(bars, ds, divs=[{"detachement": ds[70], "montant_ajuste_split": 5.0}])
    pd.testing.assert_frame_equal(sans_div[list(COLONNES_SCORE)], avec_div[list(COLONNES_SCORE)])
    # la fenêtre qui contient le détachement gagne ≈ 5 / cours ; celles qui ne le contiennent pas, rien
    i = sans_div.index[sans_div["pos"] == 60][0]
    gain = avec_div.at[i, "r"] - sans_div.at[i, "r"]
    assert gain == pytest.approx(5.0 / bars[70]["c"] * (1 + sans_div.at[i, "r"]), rel=1e-6)
    j = sans_div.index[sans_div["pos"] == 20][0]
    assert avec_div.at[j, "r"] == sans_div.at[j, "r"]


def test_rendement_et_reference_a_la_main(sans_fichier):
    ds, bars = serie()
    masi = {d: 1000.0 + i for i, d in enumerate(ds)}
    P = panel(bars, ds, masi=masi)
    ligne = P[P["pos"] == 60].iloc[0]
    assert ligne["r"] == pytest.approx(bars[80]["c"] / bars[60]["c"] - 1)
    assert ligne["rm"] == pytest.approx(masi[ds[80]] / masi[ds[60]] - 1)
    assert not P[P["pos"] >= len(ds) - bs.HORIZON]["r"].notna().any()    # horizon non atteint
    assert P[P["pos"] >= len(ds) - bs.HORIZON]["horizon_non_atteint"].all()


# ── 2. le panel rejoue le moteur ────────────────────────────────────────────

def test_le_panel_rejoue_score_titre_du_moteur(ud):
    """Même cours, MM, RSI, volumes et liquidité : même valeur, titre par titre."""
    from pipeline.seance import clotures_echangees
    fin = "2026-09-15"
    bougies = bs.charger_bougies(fin)
    cal = bs.calendrier(bougies)
    cal_pos = {d: i for i, d in enumerate(cal)}
    masi = {d: 1000.0 for d in cal}
    n = 0
    for t in ("ADH", "IAM", "BOA", "CSR", "MNG", "SOT", "CMT", "ZLD"):
        b = bougies[t]
        df = pd.DataFrame(b)
        rows = bs.panel_titre(t, b, 12.5, cal_pos, cal, masi, [])
        derniere = [r for r in rows if r["date"] == b[-1]["d"]]
        if not derniere:
            continue                       # titre non échangé ce jour-là : pas de ligne, comme en production
        rec = {"symbol": t, "price": b[-1]["c"],
               "ma20": ud.calc_ma(df["c"], 20), "ma50": ud.calc_ma(df["c"], 50),
               "rsi": ud.calc_rsi(clotures_echangees(df["c"], df["v"], df["h"], df["l"], df["o"])),
               "_meta": {"stale": False, "suspendu": False, "prix_asof": b[-1]["d"]},
               "ratios_publies": {"roe_2025": {"valeur": 12.5}}}
        moteur = sd.score_titre(rec, b)
        assert moteur["valeur"] == derniere[0]["avec"], (t, moteur["valeur"], derniere[0]["avec"], moteur["motif"])
        n += 1
    assert n >= 5


def test_seances_apres_reprise_du_backtest_est_celle_du_moteur(ud):
    assert bs.SEANCES_APRES_REPRISE == ud.SEANCES_APRES_REPRISE


# ── 3. ruptures, splits, reprises ───────────────────────────────────────────

def test_une_fenetre_qui_traverse_un_saut_de_plus_de_10_pct_est_ecartee(monkeypatch):
    ds, bars = serie(saut=(120, 1.4))
    cl = np.array([b["c"] for b in bars])
    monkeypatch.setattr(bs, "charger", lambda chemin, fin=None: {"d": ds, "c": cl})
    P = panel(bars, ds)
    P = P.set_index("pos")
    for pos in range(100, 120):          # t < 120 ≤ t+20
        assert P.at[pos, "fenetre_rompue"], pos
    for pos in range(60, 100):
        assert not P.at[pos, "fenetre_rompue"], pos
    # les indicateurs lus sur une série rompue (MM50 et RSI mélangent deux régimes de prix)
    # sont écartés pendant 50 séances après le saut, jamais avant
    assert P.loc[120:159, "rupture_indic"].all() and not P.loc[:119, "rupture_indic"].any()


def test_une_reprise_inscrite_au_registre_ecarte_fenetre_et_indicateurs(monkeypatch):
    ds, bars = serie()
    cl = np.array([b["c"] for b in bars])
    reprise = ds[100]
    monkeypatch.setattr(bs, "charger", lambda chemin, fin=None: {"d": ds, "c": cl})
    monkeypatch.setattr(bs.cfg, "SUSPENSIONS", {"ZZZ": [{"depuis": ds[90], "reprise": reprise}]})
    P = panel(bars, ds).set_index("pos")
    # les séances de la suspension n'ont aucun score (suspendu)
    assert (P.loc[90:99, "decision"] == "SUSPENDU").all()
    # fenêtre qui traverse la suspension / la reprise : écartée
    assert P.loc[75:99, "fenetre_rompue"].all() and not P.loc[:69, "fenetre_rompue"].any()
    # indicateurs sur 50 séances après la rupture : écartés ; au-delà : conservés
    assert P.loc[100:139, "rupture_indic"].all() and not P.loc[150:, "rupture_indic"].any()
    # reprise récente (< 20 séances) : le moteur ne publie pas de valeur
    assert (P.loc[100:118, "decision"] == "LIMITÉ").all() and P.at[119, "decision"] == "OBSERVABLE"
    assert (P.loc[100:118, "etat_sans"] == "PARTIEL").all()


def test_un_split_declare_ecarte_les_fenetres_mais_pas_les_indicateurs():
    """MNG (10:1 le 27/07/2026) : chandelles déjà ajustées → indicateurs lisibles ; la règle
    de `serie_propre` écarte pourtant les fenêtres qui traversent la date, comme le backtest existant."""
    bougies = bs.charger_bougies("2026-10-28")
    cal = bs.calendrier(bougies)
    cal_pos = {d: i for i, d in enumerate(cal)}
    masi = {d: 1000.0 for d in cal}
    P = pd.DataFrame(bs.panel_titre("MNG", bougies["MNG"], 10.0, cal_pos, cal, masi, []))
    avant_split = P[(P["date"] >= "2026-07-01") & (P["date"] < "2026-07-27")]
    assert len(avant_split) > 10 and avant_split["fenetre_rompue"].all()
    assert not P[P["date"] < "2026-06-01"]["fenetre_rompue"].any()
    # les chandelles sont ajustées : aucun saut de 10:1 dans la série, donc rien à écarter côté indicateurs
    assert not P["rupture_indic"].any()


def test_cmt_apres_la_reprise_du_16_09_est_limite_puis_les_indicateurs_restent_ecartes():
    bougies = bs.charger_bougies("2026-10-28")
    cal = bs.calendrier(bougies)
    cal_pos = {d: i for i, d in enumerate(cal)}
    masi = {d: 1000.0 for d in cal}
    P = pd.DataFrame(bs.panel_titre("CMT", bougies["CMT"], 21.8, cal_pos, cal, masi, []))
    apres = P[P["date"] >= "2026-09-16"]
    assert len(apres) >= 20
    dix_neuf = [b["d"] for b in bougies["CMT"] if b["d"] >= "2026-09-16"][:19]
    assert (apres[apres["date"].isin(dix_neuf)]["decision"] == "LIMITÉ").all()   # reprise récente
    assert apres["rupture_indic"].all()                             # 50 séances : MM50 mélange deux régimes
    assert not P[P["date"] < "2026-07-01"]["rupture_indic"].any()


# ── 4. la statistique ───────────────────────────────────────────────────────

def test_newey_west_calcule_a_la_main():
    # S = [2, 0, 2, 0], n = 1 : Δ = 1, u = [1, −1, 1, −1], γ0 = 4, γ1 = −3, retard 1,
    # poids de Bartlett 1 − 1/2 : V = 4 + 2·0,5·(−3) = 1, var = V / N² = 1/16, t = 1 / 0,25 = 4.
    r = bs.hac_ratio(np.array([2., 0., 2., 0.]), np.ones(4), lag=1)
    assert r["delta"] == 1.0 and r["t"] == pytest.approx(4.0)
    assert r["p"] == pytest.approx(math.erfc(4 / math.sqrt(2)))


def test_p_normal_au_seuil_classique():
    assert bs._p_normal(1.959964) == pytest.approx(0.05, abs=1e-5)
    assert bs._p_normal(None) is None and bs._p_normal(float("nan")) is None


def test_ratio_sans_observation_ne_plante_pas():
    assert bs.hac_ratio(np.zeros(10), np.zeros(10)) == {"delta": None, "t": None, "p": None}


def _groupe(n_dates, par_date, p_gagne, graine=3):
    """n_dates × par_date observations, issue ~ Bernoulli(p_gagne), base = taux global."""
    rng = random.Random(graine)
    lignes = []
    for d in range(n_dates):
        for k in range(par_date):
            g = float(rng.random() < p_gagne)
            lignes.append({"pos": d, "t": f"T{k}", "gagne": g, "ex": 0.01 if g else -0.03})
    return pd.DataFrame(lignes)


def test_sous_les_seuils_aucun_t_n_est_publie():
    df = _groupe(16, 20, .4)          # 16 dates : < 20 dates, < 10 blocs de 20 séances
    T = 40
    base = np.full(T, .4)
    r = bs.ligne_groupe(df, base, T, bs._tirages(T), "gagne", "ex")
    assert r["conclusion_autorisee"] is False
    assert r["t_newey_west"] is None and r["p_newey_west"] is None and r["p_bootstrap_blocs"] is None
    assert r["ecart_apparie_ic95_blocs_pts"] == [None, None] and r["non_chevauchant"] is None
    assert r["lecture"].startswith("insuffisant")
    assert r["n"] == 320 and r["dates"] == 16        # les effectifs, eux, restent publiés


def test_au_dessus_des_seuils_la_frequence_et_l_ecart_sont_recalculables():
    """Deux sous-groupes de même loi (50 %) : l'écart au taux de base est nul, à l'aléa près."""
    T = 300
    rng = random.Random(5)
    lignes = []
    for d in range(T):
        for k in range(6):
            g = float(rng.random() < .5)
            lignes.append({"pos": d, "t": f"T{k}", "gagne": g, "ex": 0.01 if g else -0.03, "grp": k < 3})
    df = pd.DataFrame(lignes)
    base = df.groupby("pos")["gagne"].mean().reindex(range(T)).to_numpy()
    sous = df[df["grp"]]
    r = bs.ligne_groupe(sous, base, T, bs._tirages(T), "gagne", "ex")
    assert r["conclusion_autorisee"] is True
    assert r["n"] == 900 and r["dates"] == 300 and r["titres"] == 3
    assert r["frequence_surperformance"] == pytest.approx(sous["gagne"].mean(), abs=1e-4)
    attendu = (sous["gagne"].to_numpy() - base[sous["pos"].to_numpy()]).mean() * 100
    assert r["ecart_apparie_pts"] == pytest.approx(attendu, abs=1e-2)
    assert abs(r["ecart_apparie_pts"]) < 4
    assert r["ecart_significatif_5pct"] is False
    assert r["mediane_ecart_net_frais_pct"] == pytest.approx(sous["ex"].median() * 100)
    lo, hi = r["frequence_ic95_blocs"]
    assert lo < r["frequence_surperformance"] < hi


def test_ecart_nul_par_construction_ne_donne_pas_de_t():
    """Si la base est la fréquence de la tranche elle-même, il n'y a rien à tester."""
    df = _groupe(300, 5, .5)
    base = df.groupby("pos")["gagne"].mean().reindex(range(300)).to_numpy()
    r = bs.ligne_groupe(df, base, 300, bs._tirages(300), "gagne", "ex")
    assert r["ecart_apparie_pts"] == pytest.approx(0.0, abs=1e-9)
    assert r["t_newey_west"] is None and r["ecart_significatif_5pct"] is False


def test_un_ecart_reel_est_detecte():
    T = 400
    rng = random.Random(11)
    lignes = []
    for d in range(T):
        for k in range(6):
            p = .65 if k < 3 else .30          # tranche « haute » : 65 % ; reste : 30 %
            g = float(rng.random() < p)
            lignes.append({"pos": d, "t": f"T{k}", "tranche": "haut" if k < 3 else "bas", "gagne": g, "ex": 0})
    df = pd.DataFrame(lignes)
    base = df.groupby("pos")["gagne"].mean().reindex(range(T)).to_numpy()
    haut = bs.ligne_groupe(df[df["tranche"] == "haut"], base, T, bs._tirages(T), "gagne", "ex")
    assert haut["ecart_apparie_pts"] > 10 and haut["ecart_significatif_5pct"] is True
    assert haut["p_newey_west"] < 1e-6 and haut["p_bootstrap_blocs"] < .01


def test_le_tirage_par_blocs_est_deterministe_et_couvre_le_calendrier():
    a, b = bs._tirages(100), bs._tirages(100)
    assert a.shape == (bs.TIRAGES, 100) and (a == b).all() and a.min() >= 0 and a.max() < 100


def test_ic_et_haut_bas_masquent_leurs_t_sous_les_seuils():
    df = pd.DataFrame({"pos": [0, 0, 1, 1] * 5, "score": list(range(20)), "ex": list(range(20)),
                       "gagne": [1.0, 0.0] * 10})
    r = bs.ic_et_ecart_haut_bas(df.assign(pos=[i // 2 for i in range(20)]), "score", 5, 3,
                                "gagne", "ex", 40)
    assert r["correlation_rang_score_ecart"]["t_newey_west"] is None
    assert r["correlation_rang_score_ecart"]["conclusion_autorisee"] is False


# ── 5. de bout en bout ──────────────────────────────────────────────────────

def _nan_interdit(x):
    if isinstance(x, dict):
        return all(_nan_interdit(v) for v in x.values())
    if isinstance(x, list):
        return all(_nan_interdit(v) for v in x)
    return not (isinstance(x, float) and not math.isfinite(x))


def test_artefact_complet_date_et_deterministe(tmp_path, monkeypatch):
    monkeypatch.setattr(bs, "TIRAGES", 200)            # le test vérifie la plomberie, pas la précision
    fichiers = []
    for k in (1, 2):
        sortie = tmp_path / f"s{k}"
        assert bs.main(["--sortie", str(sortie), "--jusqu-au", "2025-06-30", "--sans-git"]) == 0
        fichiers.append(list(sortie.glob("score_descriptif_*.json")))
    assert [f[0].name for f in fichiers] == ["score_descriptif_2025-06-30.json"] * 2
    a, b = (f[0].read_bytes() for f in fichiers)
    assert a == b, "deux exécutions sur les mêmes entrées doivent donner le même fichier"
    art = json.loads(a.decode("utf-8"))
    assert _nan_interdit(art), "NaN / infini dans l'artefact"
    assert art["date_artefact"] == "2025-06-30" and art["horizon_seances"] == 20
    assert art["frais_aller_retour"] == 0.02 and art["version_score"] == sd.VERSION
    assert art["entrees"]["chandelles"]["tronque_a"] == "2025-06-30"
    assert art["entrees"]["chandelles"]["au"] == "2025-06-30"
    assert art["entrees"]["masi"]["au"] == "2025-06-30"
    for variante in ("sans_rentabilite", "avec_roe_actuel"):
        r = art["resultats"][variante]
        assert set(r["tranches"]) == {"< 40", "40 – 59", "60 – 74", "≥ 75"}
        for t in r["tranches"].values():
            assert {"n", "dates", "titres", "frequence_surperformance", "taux_de_base_memes_dates",
                    "ecart_apparie_pts", "mediane_ecart_net_frais_pct", "lecture"} <= set(t)
    assert "BIAIS D'ANTICIPATION" in art["resultats"]["avec_roe_actuel"]["_biais"]
    assert art["exclusions"]["utilisables_et_calculables_sans_roe"] > 1000
    # tranches publiées avec leur effectif : somme des tranches = observations du tableau
    r = art["resultats"]["sans_rentabilite"]
    assert sum(t["n"] for t in r["tranches"].values()) == r["observations_total"]


def test_l_artefact_publie_est_coherent_avec_ses_propres_regles():
    """L'artefact versionné respecte ses règles : aucun t sous les seuils, effectifs sommés."""
    fichiers = sorted((RACINE / "datasets" / "backtests").glob("score_descriptif_*.json"))
    if not fichiers:
        pytest.skip("aucun artefact versionné")
    art = json.loads(fichiers[-1].read_text(encoding="utf-8"))
    assert fichiers[-1].name == f"score_descriptif_{art['date_artefact']}.json"
    assert _nan_interdit(art)

    def parcourir(x):
        if isinstance(x, dict):
            if "conclusion_autorisee" in x and "t_newey_west" in x:
                if x["conclusion_autorisee"] is False:
                    assert x["t_newey_west"] is None, "t publié sous les seuils d'effectif"
                if "n" in x and x["conclusion_autorisee"]:
                    assert x["n"] >= bs.MIN_OBS and x["dates"] >= bs.MIN_DATES
            for v in x.values():
                parcourir(v)
        elif isinstance(x, list):
            for v in x:
                parcourir(v)

    parcourir(art["resultats"])
    parcourir(art["comparaison_v53"])
    for variante in ("sans_rentabilite", "avec_roe_actuel"):
        r = art["resultats"][variante]
        assert sum(t["n"] for t in r["tranches"].values()) == r["observations_total"]
    assert art["controle_panel_contre_moteur"]["statut"] in ("vérifié", "non vérifié")
    if art["controle_panel_contre_moteur"]["statut"] == "vérifié":
        assert art["controle_panel_contre_moteur"]["ecarts"] == 0
