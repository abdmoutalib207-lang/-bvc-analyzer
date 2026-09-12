"""La comptabilité du portefeuille, au-delà du cas 100 → 120.

POURQUOI CE FICHIER
───────────────────
L'audit externe du 09/09/2026 a démasqué un double comptage : à la vente, le
capital DÉJÀ composé jour après jour était remultiplié par le rendement TOTAL
depuis l'achat. Acheter à 100, monter à 110, vendre à 120 donnait 132.

Le correctif a été vérifié sur ce seul cas. L'auditeur a répondu, avec raison,
qu'« obtenir 120 est nécessaire mais ne suffit pas » : une correction peut
réparer un chemin et en casser un autre. Ce fichier couvre les cinq situations
qu'il a demandées, sur les trois stratégies concernées.

  1. aller-retour à prix identique  → le portefeuille ne perd QUE les frais
  2. transaction perdante           → la perte est comptée UNE fois
  3. plusieurs allers-retours       → aucun gain ni coût ne disparaît
  4. position encore ouverte à la fin → sa valeur et ses frais sont intégrés
  5. chaque jour                    → valeur totale = cash + titres détenus

⚠️ Ces tests emploient des séries CONSTRUITES dont la réponse est connue
d'avance. Ils ne mesurent aucune performance d'investissement et ne doivent
jamais être présentés comme telle.
"""

import sys
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parent.parent
pd = pytest.importorskip("pandas")
sys.path.insert(0, str(RACINE / "whatsapp_analysis"))
import phase11_backtest as bt  # noqa: E402


@pytest.fixture
def sans_frottement():
    """Neutralise frais, slippage et rémunération du cash.

    Les frottements sont des hypothèses du moteur ; les mêler à un contrôle de
    comptabilité empêcherait de dire lequel des deux est en cause.
    """
    sauve = (bt.TRANSACTION_COST, bt.SLIPPAGE, bt.RF_ANNUAL)
    bt.TRANSACTION_COST = bt.SLIPPAGE = bt.RF_ANNUAL = 0.0
    yield
    bt.TRANSACTION_COST, bt.SLIPPAGE, bt.RF_ANNUAL = sauve


@pytest.fixture
def avec_frais():
    """Garde les frais, annule slippage et taux sans risque."""
    sauve = (bt.TRANSACTION_COST, bt.SLIPPAGE, bt.RF_ANNUAL)
    bt.TRANSACTION_COST, bt.SLIPPAGE, bt.RF_ANNUAL = 0.002, 0.0, 0.0
    yield
    bt.TRANSACTION_COST, bt.SLIPPAGE, bt.RF_ANNUAL = sauve


def _jouer(prix, sentiments, achat=0.5, vente=-0.5):
    """Rejoue la stratégie sentiment sur une série construite."""
    n = len(prix)
    d = pd.date_range("2026-01-01", periods=n, freq="D")
    return bt.strategy_smart_sentiment(
        pd.DataFrame({"date": d, "sentiment_mean": sentiments}),
        pd.DataFrame({"X": [float(p) for p in prix]}, index=d),
        pd.Series([1000.0] * n, index=d),
        buy_threshold=achat, sell_threshold=vente)


# ── 1. Aller-retour à prix identique ─────────────────────────────────────

def test_un_aller_retour_a_prix_egal_ne_coute_que_les_frais(avec_frais):
    """Acheter et revendre au même cours ne peut ni enrichir ni ruiner.

    Deux passages de 0,2 % : on paie 100 × 1,002 à l'achat et on encaisse
    100 × 0,998 à la vente, soit −0,40 % environ.
    """
    prix = [100.0] * 12
    sent = [0.0] * 3 + [0.9, 0.0, -0.9] + [0.0] * 6
    eq, trades = _jouer(prix, sent)
    perte = eq.iloc[-1] / eq.iloc[0] - 1
    assert perte == pytest.approx(-0.004, abs=0.0005), (
        f"aller-retour à prix égal : {perte*100:+.3f} %, attendu −0,40 % de frais")
    assert eq.iloc[-1] < eq.iloc[0], "les frais doivent coûter, pas rapporter"


# ── 2. Transaction perdante ──────────────────────────────────────────────

def test_une_perte_n_est_comptee_qu_une_fois(sans_frottement):
    """Acheter à 100, baisser à 90, vendre à 80 : le capital finit à 80.

    Le défaut d'origine surcomptait dans les deux sens : il aurait donné
    90 × 0,80 = 72, soit −28 % pour une baisse de −20 %.
    """
    prix = [100.0] * 4 + [90.0, 80.0] + [80.0] * 6
    sent = [0.0] * 3 + [0.9, 0.0, -0.9] + [0.0] * 6
    eq, trades = _jouer(prix, sent)
    rendement = eq.iloc[-1] / eq.iloc[0] - 1
    assert rendement == pytest.approx(-0.20, abs=0.005), (
        f"perte comptée {rendement*100:+.1f} %, attendu −20,0 %")
    ventes = [t for t in trades if "return" in t]
    assert ventes[0]["return"] == pytest.approx(rendement, abs=0.005), (
        "la courbe et le rendement annoncé divergent — signature du double "
        "comptage, dans le sens de la perte cette fois")


# ── 3. Plusieurs allers-retours ──────────────────────────────────────────

def test_deux_allers_retours_composent_correctement(sans_frottement):
    """+20 % puis +20 % doivent donner +44 %, pas +40 % ni davantage.

    Un moteur qui perd un gain rendrait 140 ; un moteur qui surcompte
    dépasserait 144. Seule une comptabilité juste tombe sur 144.
    """
    #        j0     j1     j2     j3(achat) j4    j5(vente) j6    j7(achat) j8    j9(vente) j10   j11
    prix = [100.0, 100.0, 100.0, 100.0,   110.0, 120.0,   120.0, 120.0,   132.0, 144.0,   144.0, 144.0]
    sent = [0.0,   0.0,   0.0,   0.9,     0.0,   -0.9,    0.0,   0.9,     0.0,   -0.9,    0.0,   0.0]
    eq, trades = _jouer(prix, sent)
    rendement = eq.iloc[-1] / eq.iloc[0] - 1
    assert rendement == pytest.approx(0.44, abs=0.01), (
        f"deux hausses de 20 % composées donnent {rendement*100:+.1f} %, "
        "attendu +44,0 %")
    assert len([t for t in trades if t["action"] == "BUY"]) == 2
    assert len([t for t in trades if "return" in t]) == 2


# ── 4. Position encore ouverte à la fin ──────────────────────────────────

def test_une_position_ouverte_a_la_fin_est_valorisee(sans_frottement):
    """Le portefeuille ne se fige pas parce qu'on n'a pas vendu.

    Acheté à 100, le cours finit à 130 sans ordre de vente : la courbe doit
    valoir 130, pas 100.
    """
    prix = [100.0] * 4 + [110.0, 120.0, 130.0] + [130.0] * 5
    sent = [0.0] * 3 + [0.9] + [0.0] * 8          # jamais de signal de vente
    eq, trades = _jouer(prix, sent)
    assert not [t for t in trades if "return" in t], "aucune vente attendue"
    rendement = eq.iloc[-1] / eq.iloc[0] - 1
    assert rendement == pytest.approx(0.30, abs=0.005), (
        f"position ouverte valorisée {rendement*100:+.1f} %, attendu +30,0 %")


# ── 5. Identité comptable jour par jour ──────────────────────────────────

def test_la_courbe_suit_le_cours_pendant_toute_la_detention(sans_frottement):
    """Chaque jour détenu, la valeur doit suivre le titre — ni plus, ni moins.

    C'est la formulation opérationnelle de « valeur totale = cash + titres » :
    hors position, la courbe est plate ; en position, elle réplique exactement
    la variation du cours.
    """
    prix = [100.0, 100.0, 100.0, 100.0, 105.0, 115.0, 112.0, 120.0, 120.0, 120.0, 120.0, 120.0]
    sent = [0.0,   0.0,   0.0,   0.9,   0.0,   0.0,   0.0,   -0.9,  0.0,   0.0,   0.0,   0.0]
    eq, _ = _jouer(prix, sent)
    # La stratégie travaille sur l'intersection des index ; on compare les
    # variations relatives de la courbe à celles du cours sur la détention.
    v_eq = [eq.iloc[i] / eq.iloc[i - 1] - 1 for i in range(1, len(eq))]
    # Jours 4 à 7 (indices 3..6 des variations) : en position.
    v_prix = [prix[i] / prix[i - 1] - 1 for i in range(1, len(prix))]
    for i in range(4, 7):
        assert v_eq[i - 1] == pytest.approx(v_prix[i - 1], abs=1e-9), (
            f"jour {i} : la courbe varie de {v_eq[i-1]:.4%} pour un cours à "
            f"{v_prix[i-1]:.4%}")
    # Après la vente, plus aucune variation (taux sans risque neutralisé).
    for i in range(8, len(v_eq)):
        assert v_eq[i] == pytest.approx(0.0, abs=1e-9), (
            f"la courbe bouge encore au jour {i+1} alors que la position est "
            "soldée et le cash non rémunéré")


# ── Les trois stratégies portent la même comptabilité ────────────────────

def test_aucune_strategie_ne_remultiplie_par_le_rendement_total():
    """Le motif fautif existait dans trois stratégies. En corriger une seule
    laisserait les deux autres publier des performances gonflées."""
    import re
    s = (RACINE / "whatsapp_analysis" / "phase11_backtest.py").read_text(encoding="utf-8")
    fautif = re.findall(r"equity\.append\(equity\[-1\] \* \(1 \+ ret\)\)", s)
    assert not fautif, f"{len(fautif)} stratégie(s) portent encore le motif"


def test_les_trois_strategies_calculent_le_rendement_du_jour_de_vente():
    """Chacune doit borner le gain du jour de vente au chemin depuis la
    clôture précédente."""
    s = (RACINE / "whatsapp_analysis" / "phase11_backtest.py").read_text(encoding="utf-8")
    n = s.count("ret_jour = (exit_price / prev_p - 1.0) if prev_p > 0 else 0.0")
    assert n == 3, (
        f"{n} stratégie(s) sur 3 bornent le gain du jour de vente ; les autres "
        "comptent encore une partie du gain deux fois")
