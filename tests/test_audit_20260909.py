"""Les défauts trouvés par l'audit externe du 09/09/2026.

CE QUE CET AUDIT A TROUVÉ QUE NOUS N'AVIONS PAS VU
──────────────────────────────────────────────────
Quatre défauts, tous reproduits ici avant correction. Aucun n'était couvert
par les 295 tests existants — et c'est le vrai enseignement : une suite verte
mesure ce qu'on a pensé à vérifier, pas ce qui est juste.

  1. ZÉRO PRIS POUR UNE ABSENCE. `BPA_DATA[t].get("div_dh")` teste une VALEUR,
     pas une présence. En Python `0.0` est faux : un dividende de zéro, vérifié
     dans le rapport annuel, retombait sur le rendement figé de FOND_DATA. CMT
     publiait 0,5 % de rendement là où la société n'a rien versé. Dix titres
     concernés, pas un.

  2. LE MÊME PIÈGE AILLEURS. `float(f.get("dette_nette_ebitda") or 1.0)` : une
     société SANS DETTE — le meilleur bilan possible — héritait d'un ratio de
     1,0, donc de 7,0/10 au lieu de 8,5. Le défaut pénalisait exactement les
     bilans les plus sains. L'audit avait raison de dire qu'il dépassait le
     seul dividende.

  3. UN GAIN COMPTÉ DEUX FOIS DANS LE BACKTEST. À la vente, le code multipliait
     un capital DÉJÀ composé jour après jour par le rendement TOTAL depuis
     l'achat. Acheter à 100, monter à 110, vendre à 120 rendait 132 au lieu de
     120. La fonction annonçait +20 % de rendement de transaction tout en
     traçant une courbe finissant à +32 % : elle se contredisait elle-même.
     Trois stratégies touchées.

  4. UN STATUT HORS CONTRAT. « SUSPENDU », émis depuis le 09/09, n'était pas
     dans le vocabulaire admis par test_contrat_data_json. La suite passait au
     vert parce que `data.json` n'avait pas encore été régénéré : le test
     relisait des données ANTÉRIEURES au code qu'il décrit. Au premier run
     publiant CMT, l'intégration continue cassait.

LA LEÇON COMMUNE
────────────────
Les défauts 1 et 2 sont la famille 9 d'ERRORS retournée : non plus combler une
absence, mais **prendre une valeur réelle pour une absence**. Le remède est le
même dans les deux sens — tester la PRÉSENCE, jamais la valeur.

Le défaut 4 dit autre chose, et de plus dérangeant : un test qui relit les
données publiées ne protège rien tant que ces données n'ont pas traversé le
code neuf. Il donne l'illusion inverse.
"""

import json
import re
import sys
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parent.parent


# ── 1. Zéro n'est pas une absence ────────────────────────────────────────

def test_un_dividende_de_zero_ne_retombe_pas_sur_la_table_figee():
    """Le test doit porter sur `is not None`, jamais sur la valeur."""
    s = (RACINE / "update_data.py").read_text(encoding="utf-8")
    assert 'BPA_DATA[ticker].get("div_dh") is not None' in s, (
        "le rendement teste encore la VALEUR du dividende : un zéro vérifié "
        "sera repris pour une absence et remplacé par FOND_DATA")


def test_aucun_dividende_verifie_a_zero_ne_serait_ecrase():
    """Reproduit la condition du moteur sur les données réelles."""
    b = json.loads((RACINE / "bpa.json").read_text(encoding="utf-8"))
    zeros = [t for t, e in b.items() if e.get("div_dh") == 0]
    assert zeros, "aucun dividende à zéro — le cas de test a disparu"
    for t in zeros:
        present = b[t].get("div_dh") is not None
        assert present, f"{t} : un zéro vérifié serait pris pour une absence"


def test_le_bilan_ne_penalise_pas_une_societe_sans_dette():
    """`or 1.0` transformait « aucune dette » en « une fois l'EBITDA »."""
    s = (RACINE / "pipeline" / "smart_money" / "fond_score.py").read_text(encoding="utf-8")
    assert 'f.get("dette_nette_ebitda") or 1.0' not in s, (
        "une société sans dette nette hérite encore d'un ratio de 1,0")
    assert "_dne = f.get(\"dette_nette_ebitda\")" in s
    assert "float(_dne) if _dne is not None else 1.0" in s


# ── 3. Le double comptage du backtest ────────────────────────────────────

def test_le_backtest_ne_compte_pas_un_gain_deux_fois():
    """LE cas de contrôle de l'audit, rejoué tel quel.

    Acheter à 100, le cours monte à 110, vendre à 120. Le capital doit finir à
    120. Avant correction il finissait à 132 — 110 × 1,20.
    """
    pd = pytest.importorskip("pandas")
    sys.path.insert(0, str(RACINE / "whatsapp_analysis"))
    import phase11_backtest as bt

    cout, slip, rf = bt.TRANSACTION_COST, bt.SLIPPAGE, bt.RF_ANNUAL
    bt.TRANSACTION_COST = bt.SLIPPAGE = bt.RF_ANNUAL = 0.0
    try:
        d = pd.date_range("2026-01-01", periods=12, freq="D")
        prix = pd.DataFrame({"X": [100.] * 4 + [110., 120.] + [120.] * 6}, index=d)
        sent = pd.DataFrame({"date": d,
                             "sentiment_mean": [0.] * 3 + [0.9, 0.0, -0.9] + [0.] * 6})
        eq, trades = bt.strategy_smart_sentiment(
            sent, prix, pd.Series([1000.] * 12, index=d),
            buy_threshold=0.5, sell_threshold=-0.5)
    finally:
        bt.TRANSACTION_COST, bt.SLIPPAGE, bt.RF_ANNUAL = cout, slip, rf

    assert len(eq) > 0, "la stratégie n'a produit aucune courbe"
    rendement = eq.iloc[-1] / eq.iloc[0] - 1
    assert rendement == pytest.approx(0.20, abs=0.005), (
        f"capital final {eq.iloc[-1]:.2f} pour un départ à {eq.iloc[0]:.2f} — "
        f"soit {rendement*100:+.1f} %, attendu +20 %")

    # Et la courbe doit CONCORDER avec le rendement annoncé du trade : c'est
    # la contradiction interne qui a permis de démasquer le défaut.
    ventes = [t for t in trades if "return" in t]
    assert ventes, "aucune vente enregistrée"
    assert ventes[0]["return"] == pytest.approx(rendement, abs=0.005), (
        "la courbe de portefeuille et le rendement de transaction se "
        "contredisent — c'est la signature du double comptage")


def test_aucune_strategie_ne_garde_le_motif_fautif():
    """Le défaut existait dans trois stratégies. En corriger une seule
    laisserait les deux autres produire des performances gonflées."""
    s = (RACINE / "whatsapp_analysis" / "phase11_backtest.py").read_text(encoding="utf-8")
    fautif = re.findall(r"equity\.append\(equity\[-1\] \* \(1 \+ ret\)\)", s)
    assert not fautif, (
        f"{len(fautif)} stratégie(s) multiplient encore le capital composé par "
        "le rendement total depuis l'achat")


# ── 4. Le contrat de data.json ───────────────────────────────────────────

def test_suspendu_appartient_au_vocabulaire_des_signaux():
    """⚠️ Le test passait au vert alors que le moteur émettait déjà SUSPENDU :
    `data.json` n'avait pas été régénéré. Un test qui relit les données
    publiées ne protège rien tant qu'elles n'ont pas traversé le code neuf."""
    s = (RACINE / "tests" / "test_contrat_data_json.py").read_text(encoding="utf-8")
    assert '"SUSPENDU"' in s, (
        "le contrat refuse un statut que le moteur émet : la CI cassera au "
        "premier run publiant un titre suspendu")


def test_le_moteur_et_le_contrat_parlent_le_meme_vocabulaire():
    """Le vrai contrôle : tout signal ÉMIS doit être ADMIS."""
    moteur = (RACINE / "update_data.py").read_text(encoding="utf-8")
    contrat = (RACINE / "tests" / "test_contrat_data_json.py").read_text(encoding="utf-8")
    m = re.search(r"connus = \{(.*?)\}", contrat, re.S)
    assert m, "vocabulaire admis introuvable"
    admis = set(re.findall(r'"([^"]+)"', m.group(1)))
    emis = set(re.findall(r'sig = "([A-ZÉÀÈ ]+)"', moteur))
    emis |= set(re.findall(r'"(SUSPENDU)"', moteur))
    manquants = {e.replace("★", "").strip() for e in emis} - admis
    assert not manquants, f"signaux émis mais hors contrat : {manquants}"
