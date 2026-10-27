"""Lot A « moteur » — corrections des audits du 22/10/2026, sans effet sur la note.

Chaque test décrit le CODE (première famille) : il ne relit pas data.json.

1. R9 — un titre non coté à la séance de référence publie `chg` et `open` nuls
   (None), `vol` 0 motivé par `_meta.motif_vol`.
2. Extrêmes glissants ancrés à MINUIT, bord inclus, quelle que soit l'heure.
3. Capitalisation : une décimale sous 100 MDHS.
4. `_meta.cap_releve_age_j` mesuré à la date d'analyse (jamais négatif).
5. ROE vérifiés : chaque valeur se recalcule depuis sa formule.
6. `_meta.source_fond` : plus de « table_figee » mensonger.
7. `financial_data.json` ne publie plus la table figée `fallback_data.json`.
"""
import json
import re
import sys
from pathlib import Path

import pandas as pd
import pytest

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))
sys.path.insert(0, str(RACINE / "pipeline"))

import update_data as ud  # noqa: E402


# ── 1. R9 : titre non coté à la séance ─────────────────────────────────────

def test_non_cote_a_la_seance():
    assert ud.non_cote_a_la_seance("2026-10-12", "2026-10-21") is True
    assert ud.non_cote_a_la_seance("2026-10-21", "2026-10-21") is False
    # Sans l'une des deux dates, on ne conclut pas.
    assert ud.non_cote_a_la_seance(None, "2026-10-21") is False
    assert ud.non_cote_a_la_seance("2026-10-12", "") is False


def test_motif_du_volume_nul():
    assert ud.motif_volume("2026-10-12", "2026-10-21") == "pas d'échange à la séance du 21/10"
    assert ud.motif_volume("2026-10-21", "2026-10-21") is None
    assert ud.volume_de_seance(56, "2026-10-12", "2026-10-21") == 0


def test_le_motif_et_la_variation_absente_sont_publies_dans_meta(monkeypatch):
    monkeypatch.setattr(ud, "IDB_ASOF", "2026-01-05")
    m = ud._meta_ticker("XXX", "candles", "2026-01-02", {}, None, chg=None, vol=0,
                        motif_vol=ud.motif_volume("2026-01-02", "2026-01-05"))
    assert m["motif_vol"] == "pas d'échange à la séance du 05/01"
    assert m["stale"] is True


def test_la_boucle_publie_null_et_non_zero():
    """Garde de forme sur la boucle de `run()` : la variation et l'ouverture
    d'un titre non coté sont `None`, et leur publication le supporte."""
    s = (RACINE / "update_data.py").read_text(encoding="utf-8")
    assert "if non_cote_a_la_seance(prix_asof, IDB_ASOF):\n            chg = opn = None" in s
    assert '"chg":    round(chg, 2) if chg is not None else None' in s
    assert '"open":   round(opn, 2) if opn is not None else None' in s
    assert '"chg_alert": chg is not None and' in s
    assert "motif_vol=motif_volume(prix_asof, IDB_ASOF)" in s


# ── 2. Extrêmes glissants : minuit, bord inclus ────────────────────────────

def _serie_bord():
    """Un plus-haut pile 52 semaines avant le 21/10/2026, et un plus-bas pile
    90 jours avant — la configuration de STK (137,0) et de ZLD (197,95)."""
    jours = pd.bdate_range("2025-09-01", "2026-10-21")
    lignes = [{"date": d, "open": 100.0, "high": 101.0, "low": 99.0,
               "close": 100.0, "volume": 10} for d in jours]
    for l in lignes:
        if l["date"] == pd.Timestamp("2025-10-22"):
            l["high"] = 137.0
        if l["date"] == pd.Timestamp("2026-07-23"):
            l["low"] = 80.0
    return pd.DataFrame(lignes)


@pytest.mark.parametrize("heure", ["2026-10-21", "2026-10-21T00:00:01",
                                   "2026-10-21T19:30:16.660663+00:00",
                                   "2026-10-21T23:59:59"])
def test_compute_indicators_ne_depend_pas_de_l_heure(heure):
    import collect_history_bvcscrap as m
    ind = m.compute_indicators(_serie_bord(), as_of=heure)
    assert ind["h52w"] == 137.0 and ind["l90"] == 80.0


@pytest.mark.parametrize("heure", ["2026-10-21", "2026-10-21T23:59:59"])
def test_extremes_glissants_meme_convention(heure):
    import recalculer_cache as rc
    df = _serie_bord()
    bougies = [{"d": str(r.date)[:10], "h": r.high, "l": r.low} for r in df.itertuples()]
    ext = rc.extremes_glissants(bougies, maintenant=heure)
    assert ext["h52w"] == 137.0 and ext["l90"] == 80.0


def test_indicateurs_depuis_candles_meme_convention(monkeypatch):
    monkeypatch.setattr(ud, "date_analyse", lambda: "2026-10-21")
    df = _serie_bord().rename(columns={"date": "d", "open": "o", "high": "h",
                                       "low": "l", "close": "c", "volume": "v"})
    df["d"] = df["d"].dt.strftime("%Y-%m-%d")
    out = ud._indicateurs_depuis_candles(df)
    assert out["h52w"] == 137.0 and out["l90"] == 80.0


# ── 3. Capitalisation sous 100 MDHS ────────────────────────────────────────

def test_arrondi_de_la_capitalisation():
    assert ud._arrondi_cap(27.6543) == 27.7
    assert ud._arrondi_cap(99.94) == 99.9
    assert ud._arrondi_cap(4783.4) == 4783
    assert ud._arrondi_cap(None) is None


def test_petite_capitalisation_calculee_a_la_decimale(monkeypatch):
    monkeypatch.setattr(ud, "ACTIONS_BOURSE", {"XXX": 1_053_404})
    cap, src = ud._capitalisation("XXX", 26.25, None, "cdg")
    assert src == "calculee_bourse_officielle"
    assert cap == round(26.25 * 1_053_404 / 1e6, 1) == 27.7


# ── 4. Âge du relevé officiel ──────────────────────────────────────────────

def test_l_age_du_releve_se_mesure_a_la_date_d_analyse():
    s = (RACINE / "update_data.py").read_text(encoding="utf-8")
    appel = s[s.index("cap_detail=_cap_detail(ticker"):][:200]
    assert "date_analyse()" in appel and "prix_asof" not in appel


# ── 5. ROE vérifiés ────────────────────────────────────────────────────────

def test_chaque_roe_verifie_se_recalcule_depuis_sa_formule():
    v = json.loads((RACINE / "datasets" / "roe_verifies_2026-10-02.json").read_text(encoding="utf-8"))
    ecarts = []
    for s, cles in v["titres"].items():
        for k, e in cles.items():
            m = re.match(r"\s*([\d.]+)\s*÷\s*([\d.]+)", e["formule"])
            assert m, (s, k, e["formule"])
            calc = round(float(m.group(1)) / float(m.group(2)) * 100, 1)
            if calc != e["valeur"]:
                ecarts.append(f"{s} {k} : publié {e['valeur']}, formule {calc}")
    assert not ecarts, "\n".join(ecarts)
    assert v["titres"]["CIH"]["roe_12m"]["valeur"] == 11.0
    assert v["titres"]["WAF"]["roe_12m"]["valeur"] == 7.4


def test_la_correction_du_roe_ne_change_pas_le_palier():
    """CIH écart 1,1 → 1,0 et WAF −2,5 → −2,6 au coût des fonds propres de
    10 % : même case du barème (5,0 et 3,5)."""
    from pipeline.smart_money.fond_score import _grille_spread, COUT_FONDS_PROPRES_REF as K
    assert _grille_spread(11.1 - K) == _grille_spread(11.0 - K) == 5.0
    assert _grille_spread(7.5 - K) == _grille_spread(7.4 - K) == 3.5


# ── 6. source_fond ─────────────────────────────────────────────────────────

@pytest.mark.parametrize("kw, attendu", [
    (dict(ratios_calcules=True), "bpa_calcule"),
    (dict(ratios_calcules=False, dividende_sur_piece=True), "dividende_sur_piece"),
    (dict(ratios_calcules=False), "aucun_ratio"),
])
def test_source_des_fondamentaux_exacte(kw, attendu):
    m = ud._meta_ticker("XXX", "cdg", "2026-10-21", {}, None, **kw)
    assert m["source_fond"] == attendu


def test_plus_aucun_table_figee_emis():
    s = (RACINE / "update_data.py").read_text(encoding="utf-8")
    assert '"table_figee"' not in s


# ── 7. financial_data.json ─────────────────────────────────────────────────

def _data_json(tmp_path):
    p = tmp_path / "data.json"
    p.write_text(json.dumps({"tickers": [
        {"symbol": "ADH", "price": 36.2, "open": 35.0, "vol": 10, "chg": 2.4,
         "pe": 29.7, "pb": 1.54, "bpa": 1.1, "bpa_12m": 1.22, "div_dh": 0.0,
         "div": 0.0, "cap": 14572, "rsi": 64.4, "ma20": 33.05, "ma50": 34.55,
         "h90": 37.99, "l90": 29.1,
         "_meta": {"prix_asof": "2026-10-21", "source_fond": "bpa_calcule"}},
        {"symbol": "SAF", "price": 2885.0, "open": None, "vol": 0, "chg": None,
         "pe": None, "pb": None, "bpa": None, "div_dh": 98.0, "div": 3.4,
         "cap": 15411, "_meta": {"prix_asof": "2026-10-20"}},
    ]}), encoding="utf-8")
    return p


def test_financial_data_reprend_les_valeurs_publiees(tmp_path):
    from pipeline import collect_financial_data as c
    pub = c.charger_publie(_data_json(tmp_path))
    _, r = c.collect_ticker("ADH", pub, dry_run=True)
    f = r["fundamentals"]
    assert (f["pe_ratio_ttm"], f["eps_ttm"], f["dividend_per_share"], f["market_cap_mdh"]) == \
        (29.7, 1.22, 0.0, 14572)
    assert "data.json publié" in r["_sources"]["all"] and "2026-10-21" in r["_sources"]["all"]


def test_financial_data_met_null_ce_qui_n_est_pas_publie(tmp_path):
    from pipeline import collect_financial_data as c
    pub = c.charger_publie(_data_json(tmp_path))
    _, r = c.collect_ticker("SAF", pub, dry_run=True)
    assert r["fundamentals"]["pe_ratio_ttm"] is None and r["fundamentals"]["eps_ttm"] is None
    _, r = c.collect_ticker("ZZZ", pub, dry_run=True)
    assert all(v is None for v in r["fundamentals"].values())
    assert "non_disponible" in r["_sources"]["all"]


def test_la_table_figee_n_est_plus_lue_ni_supprimee():
    src = (RACINE / "pipeline" / "collect_financial_data.py").read_text(encoding="utf-8")
    code = "\n".join(l for l in src.splitlines() if not l.lstrip().startswith("#"))
    assert "fallback_data" not in code and "fetch_fundamentals" not in code
    assert not (RACINE / "pipeline" / "fallback_data.json").exists()
    assert (RACINE / "archive" / "fallback_data_2026-07.json").exists(), \
        "archivée, jamais supprimée (méthode de travail, point 6)"
