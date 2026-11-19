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


# ── relecture du 19/11 : les fausses alarmes à éviter ─────────────────────

def _fiche(**kw):
    t = {"symbol": "XXX", "price": 100.0, "reference": 100.0, "chg": 0.0, "_meta": {}}
    t.update(kw)
    return t


def test_titre_suspendu_reference_rediffusee_ne_bloque_pas():
    t = _fiche(price=4501.0, reference=4350.0, chg=0.0, _meta={"suspendu": True})
    assert ac.controler_arithmetique("XXX", t, None) == []


def test_jour_de_reprise_la_reference_est_celle_du_registre():
    # CMT, 16/09/2026 : reprise à 2 438 sur une référence remise à 2 217 (R11),
    # alors que l'opérateur rediffusait 4 350.
    t = _fiche(symbol="CMT", price=2438.0, reference=4350.0, chg=9.97,
               _meta={"prix_asof": "2026-09-16"})
    assert ac.controler_arithmetique("CMT", t, None) == []
    # contrôle : le lendemain, la même fiche serait une erreur de sens
    t["_meta"]["prix_asof"] = "2026-09-17"
    assert {i["controle"] for i in ac.controler_arithmetique("CMT", t, None)} == {"arith.chg"}


def test_base_bougie_differente_avertit_sans_bloquer():
    # chg calculé sur une bougie plus ancienne (séance manquante) : même sens,
    # autre grandeur → avertissement seulement.
    t = _fiche(price=103.0, reference=101.0, chg=3.0)
    inc = ac.controler_arithmetique("XXX", t, None)
    assert [(i["controle"], i["gravite"]) for i in inc] == [("arith.chg_ecart", ac.AVERT)]


def test_un_centime_sur_un_petit_cours_ne_declenche_rien():
    t = _fiche(price=19.08, reference=19.07, chg=0.0)   # cours ≈ veille à 1 centime (chg source)
    assert ac.controler_arithmetique("XXX", t, None) == []
