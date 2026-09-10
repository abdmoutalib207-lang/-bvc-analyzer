"""L'identité comptable du portefeuille, reconstruite indépendamment.

CE QUE CE FICHIER AJOUTE À `test_backtest_comptabilite.py`
──────────────────────────────────────────────────────────
L'auditeur externe a jugé, avec raison, que « courbe = cours en position,
plate hors position » est un raccourci insuffisant, et que vérifier la
présence d'une formule similaire dans les trois stratégies ne remplace pas
leur exécution. Il demande l'identité exacte, établie chaque jour :

    valeur du portefeuille = cash disponible + quantité détenue × cours

avec les frais intégrés à chaque opération, et des tests qui exécutent
réellement les achats et les ventes des trois stratégies.

C'est ce que fait ce fichier. La courbe produite par le moteur est comparée,
date par date, à une comptabilité tenue ICI, indépendamment, à partir du seul
journal des transactions et de la série de cours. Les deux doivent coïncider
au centime.

⚠️ Séries CONSTRUITES, réponses connues d'avance. Aucune performance
d'investissement n'est mesurée ni suggérée.
"""

import sys
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parent.parent
pd = pytest.importorskip("pandas")
sys.path.insert(0, str(RACINE / "whatsapp_analysis"))
import phase11_backtest as bt  # noqa: E402


# ── la comptabilité de référence, tenue ici ──────────────────────────────

def comptabilite_independante(cours, trades, capital=100.0, f=0.0):
    """Rejoue cash et quantité jour par jour, sans rien emprunter au moteur.

    Convention du moteur, explicitée : on achète à `p × (1 + f)` et on vend à
    `p × (1 - f)`, où `f` cumule frais et slippage. Le jour de l'achat, la
    valeur retombe donc à `cash / (1 + f)` — c'est le coût d'entrée.
    """
    par_date = {}
    for t in trades:
        par_date.setdefault(pd.Timestamp(t["date"]), []).append(t)

    cash, qty = capital, 0.0
    valeurs = {}
    for date, p in cours.items():
        for t in par_date.get(date, []):
            if str(t["action"]).upper().startswith("BUY"):
                qty = cash / (p * (1 + f))
                cash = 0.0
            else:            # SELL, SELL_CONTRARIAN… toute forme de vente
                cash = qty * p * (1 - f)
                qty = 0.0
        valeurs[date] = cash + qty * p
    return pd.Series(valeurs)


def _serie(prix):
    d = pd.date_range("2026-01-01", periods=len(prix), freq="D")
    return d, pd.DataFrame({"X": [float(x) for x in prix]}, index=d)


@pytest.fixture
def frottements():
    """Rend les frottements réglables et les restaure ensuite."""
    sauve = (bt.TRANSACTION_COST, bt.SLIPPAGE, bt.RF_ANNUAL)

    def _regler(cout=0.0, slip=0.0):
        bt.TRANSACTION_COST, bt.SLIPPAGE, bt.RF_ANNUAL = cout, slip, 0.0
        return cout + slip

    yield _regler
    bt.TRANSACTION_COST, bt.SLIPPAGE, bt.RF_ANNUAL = sauve


# ── 1. Les trois stratégies, réellement exécutées ────────────────────────

def _jouer_sentiment(prix, sent):
    d, px = _serie(prix)
    return bt.strategy_smart_sentiment(
        pd.DataFrame({"date": d, "sentiment_mean": sent}), px,
        pd.Series([1000.0] * len(prix), index=d),
        buy_threshold=0.5, sell_threshold=-0.5)


def _jouer_consensus(prix, sent):
    d, px = _serie(prix)
    return bt.strategy_achat_fort_consensus(
        pd.DataFrame({"date": d, "sentiment_mean": sent,
                      "buy_ratio": [0.9 if s > 0.5 else 0.1 for s in sent]}),
        pd.DataFrame(), px, pd.Series([1000.0] * len(prix), index=d))


def _jouer_contrarian(prix, sent):
    d, px = _serie(prix)
    fg = pd.Series([10.0 if s > 0.5 else 90.0 if s < -0.5 else 50.0 for s in sent], index=d)
    return bt.strategy_contrarian_fear_greed(
        pd.DataFrame({"date": d, "sentiment_mean": sent}), px,
        pd.Series([1000.0] * len(prix), index=d), fear_greed_series=fg)


STRATEGIES = [("sentiment", _jouer_sentiment),
              ("consensus", _jouer_consensus),
              ("contrarian", _jouer_contrarian)]


@pytest.mark.parametrize("nom,jouer", STRATEGIES)
@pytest.mark.parametrize("cout,slip", [(0.0, 0.0), (0.002, 0.0),
                                       (0.0, 0.001), (0.002, 0.001), (0.01, 0.005)])
def test_identite_cash_plus_titres(frottements, nom, jouer, cout, slip):
    """LE test demandé : chaque jour, valeur = cash + quantité × cours.

    La courbe du moteur est confrontée à une comptabilité tenue ici, à partir
    du seul journal des transactions. Toute divergence signale que le capital
    ne correspond plus à ce que le portefeuille détient réellement.

    Cinq niveaux de frottement, dont le slippage seul et le cumul des deux :
    un correctif juste sans frais peut être faux avec.
    """
    f = frottements(cout, slip)
    prix = [100.0] * 4 + [110.0, 120.0, 118.0, 130.0] + [130.0] * 6
    sent = [0.0] * 3 + [0.9, 0.0, -0.9, 0.0, 0.9] + [0.0] * 4 + [-0.9, 0.0]
    eq, trades = jouer(prix, sent)
    if eq.empty or not trades:
        pytest.skip(f"{nom} : aucune transaction sur ce jeu")

    d, px = _serie(prix)
    attendu = comptabilite_independante(px["X"], trades, capital=eq.iloc[0], f=f)
    attendu = attendu.reindex(eq.index)
    for date in eq.index:
        assert eq[date] == pytest.approx(attendu[date], rel=1e-9), (
            f"{nom} (f={f}) au {date.date()} : le moteur porte {eq[date]:.6f}, "
            f"la comptabilité cash+titres donne {attendu[date]:.6f}")


# ── 2. La formule exacte des frais, pas son arrondi ──────────────────────

@pytest.mark.parametrize("cout,slip", [(0.002, 0.0), (0.002, 0.001),
                                       (0.005, 0.0), (0.01, 0.005), (0.0, 0.003)])
def test_aller_retour_a_prix_egal_suit_la_formule_exacte(frottements, cout, slip):
    """capital final = capital initial × (1 − f) / (1 + f), avec f = frais + slippage.

    ⚠️ L'auditeur a relevé que 0,2 % à l'aller et au retour ne donnent pas
    −0,40 % mais −0,3992 % : on paie sur un prix majoré et on encaisse sur un
    prix minoré. Contrôler l'affichage arrondi laisserait passer une erreur de
    convention. On vérifie donc la formule elle-même, au 1e-12 près.
    """
    f = frottements(cout, slip)
    prix = [100.0] * 12
    sent = [0.0] * 3 + [0.9, 0.0, -0.9] + [0.0] * 6
    eq, trades = _jouer_sentiment(prix, sent)
    assert [t for t in trades if "return" in t], "aucune vente : cas de test invalide"

    attendu = (1 - f) / (1 + f)
    obtenu = eq.iloc[-1] / eq.iloc[0]
    assert obtenu == pytest.approx(attendu, rel=1e-12), (
        f"f={f} : obtenu {obtenu:.10f}, attendu {attendu:.10f} "
        f"(soit {(obtenu-1)*100:+.4f} % contre {(attendu-1)*100:+.4f} %)")


def test_la_convention_des_frais_est_bien_asymetrique(frottements):
    """Le cas nommé par l'auditeur, vérifié au chiffre près : 0,998 / 1,002."""
    frottements(0.002, 0.0)
    eq, _ = _jouer_sentiment([100.0] * 12, [0.0] * 3 + [0.9, 0.0, -0.9] + [0.0] * 6)
    assert eq.iloc[-1] / eq.iloc[0] == pytest.approx(0.998 / 1.002, rel=1e-12)
    perte = (eq.iloc[-1] / eq.iloc[0] - 1) * 100
    assert perte == pytest.approx(-0.399202, abs=1e-5), (
        f"perte {perte:.6f} % — la valeur exacte est −0,399202 %, que l'on "
        "affiche −0,40 % sans jamais la tester sous cette forme")


def test_sans_frottement_un_aller_retour_est_neutre(frottements):
    """Garde-fou du garde-fou : à frais nuls, l'opération ne doit rien coûter.
    Un test des frais qui passerait aussi à zéro ne mesurerait rien."""
    frottements(0.0, 0.0)
    eq, _ = _jouer_sentiment([100.0] * 12, [0.0] * 3 + [0.9, 0.0, -0.9] + [0.0] * 6)
    assert eq.iloc[-1] == pytest.approx(eq.iloc[0], rel=1e-12)
