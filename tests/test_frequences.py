"""Justesse des fréquences affichées par le terminal.

Trois familles :
  1. cas jouets, attendus calculés À LA MAIN (Wilson, test de proportions) ;
  2. RECALCUL : les quatre fréquences publiées égalent celles qu'on retrouve
     depuis les chandelles versionnées (tronquées à la fin du calibrage, donc
     stables d'une séance à l'autre) ;
  3. le terminal ne porte plus de chiffre en dur, et le suivi hors échantillon
     ne conclut rien sous 30 cas (R12).
"""
import json
import sys
from pathlib import Path

import pandas as pd
import pytest

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE / "pipeline"))

import frequences as fq  # noqa: E402
import suivi_frequences as sf  # noqa: E402

PUBLIE = RACINE / "datasets" / "frequences_publiees.json"


# ── 1. cas jouets, attendus écrits à la main ────────────────────────────

def test_wilson_5_sur_10():
    # p=0,5 ; z=1,96 : centre 0,5 ; demi-largeur 0,2634 → [0,2366 ; 0,7634]
    lo, hi = fq.wilson(5, 10)
    assert lo == pytest.approx(0.2366, abs=2e-4)
    assert hi == pytest.approx(0.7634, abs=2e-4)


def test_wilson_zero_succes():
    lo, hi = fq.wilson(0, 10)   # valeur classique : [0 ; 0,2775]
    assert lo == 0.0
    assert hi == pytest.approx(0.2775, abs=2e-4)


def test_wilson_effectif_nul():
    assert all(x != x for x in fq.wilson(0, 0))   # NaN


def test_diff_proportions_44_contre_24_sur_100():
    # pc = 0,34 ; se = sqrt(0,34 × 0,66 × 0,02) = 0,066996 ; z = 0,2/se = 2,985
    # p bilatéral = 2 × (1 − Φ(2,985)) = 0,00283
    r = fq.diff_proportions(44, 100, 24, 100)
    assert r["ecart_points"] == 20.0
    assert r["z"] == pytest.approx(2.985, abs=0.01)
    assert r["p"] == pytest.approx(0.00283, rel=0.02)


def test_diff_proportions_identiques():
    r = fq.diff_proportions(10, 20, 10, 20)
    assert r["ecart_points"] == 0.0 and r["z"] == 0.0 and r["p"] == pytest.approx(1.0)


def test_resume_cas_jouet():
    a = pd.Series([0.10, -0.05, 0.02, 0.0, -0.10, None])
    r = pd.Series([0.12, -0.03, 0.04, 0.01, -0.08, None])
    out = fq.resume(a, r)
    # 5 valeurs, 2 strictement positives (0 n'est pas un gain), moyenne -0,006,
    # médiane 0, rendement moyen 0,012 - 0,02 de frais = -0,008
    assert out["n"] == 5 and out["gagnants_k"] == 2
    assert out["pct_gagnants"] == 40.0
    assert out["alpha_moyen_pct"] == -0.6
    assert out["alpha_median_pct"] == 0.0
    assert out["rendement_net_frais_moyen_pct"] == -0.8


def test_utilite_signale_ce_qui_ne_distingue_rien():
    g = {("pullback", True): (50, 100), ("pullback", False): (48, 100),     # 50 % vs 48 %
         ("cassure90", True): (44, 100), ("cassure90", False): (24, 100),   # 44 % vs 24 %
         ("rsi_sortie_surachat", True): (50, 100), ("rsi_sortie_surachat", False): (5, 10)}
    u = {x["signal"]: x for x in fq.utilite(g)}
    assert "NE DISTINGUE PAS" in u["pullback"]["verdict"]
    assert u["cassure90"]["verdict"].startswith("distingue")
    assert "trop faible" in u["rsi_sortie_surachat"]["verdict"]   # 10 cas dans un groupe


# ── 2. le recalcul ──────────────────────────────────────────────────────

def test_les_quatre_frequences_publiees_sont_recalculables():
    publie = json.loads(PUBLIE.read_text(encoding="utf-8"))["frequences"]
    refait = fq.calculer(fq.FIN_CALIBRAGE)["frequences"]
    assert set(publie) == set(fq.DEFS) == set(refait)
    for cle, r in refait.items():
        p = publie[cle]
        assert p["n"] == r["n"], cle
        assert p["gagnants_k"] == r["gagnants_k"], cle
        for champ in ("pct_gagnants", "alpha_moyen_pct", "alpha_median_pct",
                      "rendement_net_frais_moyen_pct"):
            assert p[champ] == pytest.approx(r[champ], abs=0.051), (cle, champ)
        assert p["ic95_gagnants"] == pytest.approx(r["ic95_gagnants"], abs=0.051), cle


def test_frequences_egales_au_calibrage_du_03_10():
    """Les quatre chiffres affichés jusqu'ici en dur : n, alpha, % gagnants."""
    attendu = {"cassure": (136, 7.2, 53), "surachat": (137, 5.6, 50),
               "pullback_on": (200, 2.8, 44), "pullback_off": (58, -3.8, 24)}
    publie = json.loads(PUBLIE.read_text(encoding="utf-8"))["frequences"]
    for cle, (n, alpha, gag) in attendu.items():
        assert publie[cle]["n"] == n
        assert round(publie[cle]["alpha_moyen_pct"], 1) == alpha
        assert round(publie[cle]["pct_gagnants"]) == gag


def test_structure_et_coherence_interne():
    d = json.loads(PUBLIE.read_text(encoding="utf-8"))
    for cle, f in d["frequences"].items():
        for champ in ("libelle", "condition", "horizon_seances", "periode_mesure", "n",
                      "alpha_moyen_pct", "alpha_median_pct", "pct_gagnants", "ic95_gagnants",
                      "frais_inclus", "source"):
            assert champ in f, (cle, champ)
        assert f["source"]["fichier"] and f["source"]["commit"]
        lo, hi = fq.wilson(f["gagnants_k"], f["n"])
        assert f["ic95_gagnants"] == [round(100 * lo, 1), round(100 * hi, 1)]
        assert f["ic95_gagnants"][0] <= f["pct_gagnants"] <= f["ic95_gagnants"][1]
        assert f["frais_inclus"] is False
    assert {u["signal"] for u in d["utilite"]} == set(fq.DEFINITIONS)


def test_aucune_note_ne_lit_ce_fichier():
    """R8 : les signaux n'entrent pas dans la note."""
    for f in ("update_data.py", "pipeline/collect_financial_data.py"):
        assert "frequences_publiees" not in (RACINE / f).read_text(encoding="utf-8")


# ── 3. terminal et suivi ────────────────────────────────────────────────

def test_le_terminal_lit_le_fichier_et_ne_porte_plus_de_chiffre_en_dur():
    src = (RACINE / "terminal.src.html").read_text(encoding="utf-8")
    assert "const STATS_SIGNAUX={" not in src
    assert "datasets/frequences_publiees.json" in src
    assert "gagnants (IC" in src
    assert "datasets/frequences_publiees.json" in (RACINE / "index.html").read_text(encoding="utf-8")


def test_suivi_ne_conclut_rien_sous_30_cas():
    assert sf.jugement(0, 0, [40, 50])["dans_ic"] is None
    j = sf.jugement(5, 2, [40.0, 60.0])           # 40 % observé, 5 cas
    assert "aucune conclusion" in j["conclusion"]
    j = sf.jugement(40, 20, [40.0, 60.0])         # 50 % observé, dans l'IC
    assert j["dans_ic"] is True and "compatible" in j["conclusion"]
    j = sf.jugement(40, 4, [40.0, 60.0])          # 10 % observé, hors IC
    assert j["dans_ic"] is False and "réexaminer" in j["conclusion"]


def test_suivi_artefact_present_et_coherent():
    fichiers = sorted((RACINE / "datasets" / "suivi_frequences").glob("suivi_*.json"))
    assert fichiers
    d = json.loads(fichiers[-1].read_text(encoding="utf-8"))
    assert d["fin_calibrage"] == fq.FIN_CALIBRAGE
    assert set(d["frequences"]) == set(fq.DEFS)
    for s in d["frequences"].values():
        n = s["hors_echantillon"]["resultats_tombes_apres_fin_calibrage"].get("n", 0)
        if n < sf.SEUIL_CONCLUSION:
            assert "aucun" in s["conclusion"]
