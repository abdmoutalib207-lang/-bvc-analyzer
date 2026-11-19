"""19/11/2026 — les trois injections des audits externes (Manus, GPT) sont
désormais refusées par le contrôle de chaîne (bloquant en CI et avant
publication). Avant ce maillon, toutes passaient."""
import copy
import sys
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))
sys.path.insert(0, str(RACINE / "tools"))

import audit_chaine as ac  # noqa: E402


@pytest.fixture(scope="module")
def entrees():
    e = ac.charger(RACINE)
    if not (e["data"] or {}).get("tickers"):
        pytest.skip("data.json absent")
    return e


def _codes(entrees, sym, muter):
    data = copy.deepcopy(entrees["data"])
    t = next(x for x in data["tickers"] if x["symbol"] == sym)
    muter(t)
    data["tickers"] = [t]
    return {i["controle"] for i in ac.controler_arithmetique(sym, t, entrees["bpa"].get(sym))}


def test_le_fichier_publie_est_coherent(entrees):
    bad = [i for t in entrees["data"]["tickers"]
           for i in ac.controler_arithmetique(t["symbol"], t, entrees["bpa"].get(t["symbol"]))]
    assert bad == [], bad[:5]


def test_injection_manus_per_iam(entrees):
    t0 = next(x for x in entrees["data"]["tickers"] if x["symbol"] == "IAM")
    if t0.get("pe") is None:
        pytest.skip("IAM sans PER publié")
    assert "arith.pe" in _codes(entrees, "IAM", lambda t: t.update(pe=37.2))


def test_injection_manus_variation_mng(entrees):
    def muter(t):
        t["reference"] = (t.get("price") or 100) * 1.01      # cours SOUS la référence
        t["chg"] = 6.0
    assert "arith.chg" in _codes(entrees, "MNG", muter)


def test_injection_gpt_dividende_mox_multiplie_par_dix(entrees):
    def muter(t):
        t["div_dh"] = 40.0
        t["div"] = round(40.0 / t["price"] * 100, 2)          # rendement recalculé, cohérent
    codes = _codes(entrees, "MOX", muter)
    assert "arith.div_dh_source" in codes


def test_controle_negatif_rien_sur_une_fiche_intacte(entrees):
    for sym in ("IAM", "MNG", "MOX"):
        assert _codes(entrees, sym, lambda t: None) == set()
