"""La référence du backtest, et le refus de travailler sur des prix inventés.

DEUX DÉFAUTS, tous deux relevés par l'audit externe du 05/09/2026 et vérifiés
dans le code avant correction.

1. LE BACKTEST FABRIQUAIT SES PRIX QUAND IL N'EN AVAIT PAS
   `load_or_generate_market_prices()` générait, faute de panel, une série
   entièrement aléatoire — dérive de 8 % l'an, volatilité de 12 %, changements
   de régime tirés au sort, graine fixée à 42 pour que ce soit reproductible.
   Le résultat était donc stable, plausible, et vide de sens.

   ⚠️ **Un backtest qui invente ses prix produit TOUJOURS un résultat.** C'est
   ce qui le rend dangereux : rien dans la sortie ne signale que l'entrée
   était fictive. Il échoue désormais bruyamment ; la génération reste
   accessible pour une démonstration, mais il faut la demander.

2. LA RÉFÉRENCE N'ÉTAIT PAS LE MASI
   Quand un panel existait, l'« indice » était la moyenne ÉQUIPONDÉRÉE des
   titres du panel, rebasée à 1000. Deux conséquences :
   - la référence se déforme avec l'univers testé — changez les titres, vous
     changez la barre à franchir ;
   - le vrai MASI est pondéré par les capitalisations flottantes. Une
     stratégie qui surpondère les grandes valeurs « bat » mécaniquement une
     moyenne équipondérée, sans qu'aucune compétence n'entre en jeu.

   Le projet ne conservait aucun historique de l'indice, donc la correction
   n'était pas possible avant le 05/09. Elle l'est depuis
   `pipeline/masi_history.json` — 185 séances réelles, recoupées 185/185 avec
   nos propres chandelles sur le calendrier de cotation.
"""

import os

import pandas as pd
import pytest

from whatsapp_analysis.phase11_backtest import (
    MIN_SEANCES_MASI,
    PrixIndisponibles,
    charger_masi_reel,
    load_or_generate_market_prices,
)


def _panel(dates, n_titres=4):
    """Panel de prix jouet, indexé sur des dates réelles de cotation."""
    idx = pd.to_datetime(dates)
    return pd.DataFrame(
        {f"T{i}": [100 + i + j for j in range(len(idx))] for i in range(n_titres)},
        index=idx,
    )


# ── refus des prix inventés ──────────────────────────────────────────────

def test_sans_prix_le_backtest_refuse_de_tourner():
    """Le comportement le plus important du fichier.

    Avant : une série aléatoire, un résultat, aucun avertissement.
    Maintenant : une exception que personne ne peut confondre avec un chiffre.
    """
    with pytest.raises(PrixIndisponibles):
        load_or_generate_market_prices(None, None)


def test_panel_vide_vaut_absence_de_prix():
    with pytest.raises(PrixIndisponibles):
        load_or_generate_market_prices(pd.DataFrame(), None)


def test_les_prix_inventes_restent_accessibles_sur_demande_explicite():
    """On ne supprime pas le générateur : il sert à éprouver le moteur.

    Mais il faut le demander. Le défaut n'était pas son existence, c'était
    qu'il se déclenche tout seul, en silence, sur le chemin de production.
    """
    masi, prix = load_or_generate_market_prices(
        None, None, start_date="2026-01-01", end_date="2026-03-01",
        autoriser_synthetique=True)
    assert len(masi) > 30 and not prix.empty


def test_la_variable_d_environnement_autorise_aussi(monkeypatch):
    monkeypatch.setenv("BVC_PRIX_SYNTHETIQUES", "1")
    masi, _ = load_or_generate_market_prices(
        None, None, start_date="2026-01-01", end_date="2026-03-01")
    assert len(masi) > 30


def test_l_environnement_a_zero_ne_suffit_pas(monkeypatch):
    """Seul « 1 » autorise. Un garde-fou ne doit pas céder à « 0 » ou « false »."""
    for valeur in ("0", "false", "", "oui"):
        monkeypatch.setenv("BVC_PRIX_SYNTHETIQUES", valeur)
        with pytest.raises(PrixIndisponibles):
            load_or_generate_market_prices(None, None)


# ── la vraie référence ───────────────────────────────────────────────────

def test_le_vrai_masi_est_lisible():
    """Lit le fichier réellement livré, pas un cas fabriqué."""
    s = charger_masi_reel("2025-12-01", "2026-09-04")
    if s is None:
        pytest.skip("historique MASI pas encore assez profond")
    assert len(s) >= MIN_SEANCES_MASI
    assert (s > 0).all()
    assert s.index.is_monotonic_increasing


def test_le_masi_reel_est_prefere_au_proxy_equipondere():
    """Le cœur du correctif : la référence ne doit plus venir du panel.

    On construit un panel dont la moyenne équipondérée monte régulièrement.
    Si la référence retournée suivait ce panel, elle serait strictement
    croissante. Le vrai MASI, lui, monte et descend.
    """
    reel = charger_masi_reel("2025-12-01", "2026-09-04")
    if reel is None:
        pytest.skip("historique MASI pas encore assez profond")
    dates = [d.strftime("%Y-%m-%d") for d in reel.index[:60]]
    masi, _ = load_or_generate_market_prices(_panel(dates), None)
    assert masi.diff().dropna().lt(0).any(), (
        "la référence est strictement croissante comme le panel jouet : "
        "elle vient donc encore du panel, pas de l'indice")
    attendu = reel.reindex(pd.to_datetime(dates)).dropna()
    assert masi.round(2).equals(attendu.round(2))


def test_le_proxy_reste_le_repli_quand_l_indice_ne_couvre_pas_la_periode():
    """Hors couverture de l'indice, on retombe sur le proxy — pas sur du faux.

    Le repli est légitime ; ce qui ne l'est pas, c'est de le prendre pour le
    MASI. Il est journalisé en WARNING à chaque fois.
    """
    dates = pd.date_range("2019-01-01", periods=90, freq="B")
    masi, panel = load_or_generate_market_prices(_panel(dates), None)
    assert len(masi) == len(panel) == 90
    assert masi.iloc[0] == 1000.0, "le proxy est rebasé à 1000"


def test_la_reference_et_le_panel_partagent_le_meme_calendrier():
    """Une stratégie et sa référence doivent être mesurées sur les mêmes jours.

    Sans cet alignement, une séance présente d'un seul côté décale toute la
    comparaison — et c'est exactement le genre d'écart qui produit une
    surperformance imaginaire.
    """
    reel = charger_masi_reel("2025-12-01", "2026-09-04")
    if reel is None:
        pytest.skip("historique MASI pas encore assez profond")
    dates = [d.strftime("%Y-%m-%d") for d in reel.index[:50]]
    dates.append("2030-01-02")           # une séance que l'indice ne connaît pas
    masi, panel = load_or_generate_market_prices(_panel(dates), None)
    assert masi.index.equals(panel.index)
    assert pd.Timestamp("2030-01-02") not in masi.index
