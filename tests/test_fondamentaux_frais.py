#!/usr/bin/env python3
"""Un âge sans point de comparaison n'apprend rien.

⚠️ LA QUESTION QUE PERSONNE N'AVAIT POSÉE
─────────────────────────────────────────
Le terminal affichait « fondamentaux · 18/06/2026 (99 j) » et s'arrêtait là.
Quatre-vingt-dix-neuf jours, est-ce grave ? **On ne peut pas le dire tant
qu'on ignore si la société a publié entre-temps.**

Relevé le 25/09/2026 : **dix-sept sociétés cotées ont déposé leurs comptes du
premier semestre 2026 entre le 7 et le 24 septembre**, et ces dépôts étaient
**déjà dans notre collecte d'actualités depuis des jours**. La source
existait, nous étions à sa porte, personne n'était entré.

⚠️ CE QUE LE MODULE NE FAIT PAS, ET C'EST TESTÉ
Il ne lit pas les chiffres des rapports. Il dit QUE des comptes plus récents
existent, QUAND et OÙ. Extraire un bénéfice par action de cent rapports aux
mises en page hétérogènes produirait, mal fait, des chiffres faux là où il n'y
en avait aucun — et un lecteur retient le nombre, pas l'avertissement.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

from pipeline import fondamentaux_frais as ff  # noqa: E402


def _art(ticker="CSR", date="2026-09-23", tier="S1", type_="resultats",
         titre="Cosumar - CP relatif aux résultats du 1er semestre 2026"):
    return {"title": titre, "date": date, "source_tier": tier,
            "event_type": type_, "tickers": [ticker] if ticker else [],
            "publisher": "AMMC — publication de l’émetteur",
            "url": "https://www.ammc.ma/sites/default/files/CP.pdf"}


def _tk(sym="CSR", asof="2026-06-18"):
    return {"symbol": sym, "_meta": {"fond_asof": asof}}


# ── ⚠️ La classification vient du collecteur, pas d'ici ────────────────────

def test_seule_une_source_officielle_compte():
    """⚠️ Un article de presse qui COMMENTE des résultats n'est pas un dépôt.
    Le collecteur distingue déjà S1 (officiel) de S2 (presse) : reconstruire
    ce jugement ici créerait une seconde définition de « la société a
    publié », et deux définitions finissent par diverger."""
    d = ff.depots_officiels([_art(tier="S2")])
    assert d == {}


def test_seul_un_depot_de_RESULTATS_compte():
    """Un avis de convocation à une assemblée n'est pas une publication de
    comptes."""
    assert ff.depots_officiels([_art(type_="reglementaire")]) == {}


def test_un_emetteur_sans_ticker_est_ignore_et_non_devine():
    """⚠️ CAS RÉEL. « Saham Leasing - CP relatif aux résultats du 1er semestre
    2026 » porte `tickers: []`. Lui attribuer un ticker par ressemblance de
    nom rejouerait le piège d'`IDB_TICKER_MAP`, où le `SNA` du bulletin est
    Stokvis et non Sonasid."""
    assert ff.depots_officiels([_art(ticker=None)]) == {}


def test_le_depot_le_plus_recent_l_emporte():
    """Une société publie plusieurs fois ; c'est le dernier dépôt qui situe
    nos chiffres."""
    d = ff.depots_officiels([_art(date="2026-03-30"), _art(date="2026-09-23")])
    assert d["CSR"]["date"] == "2026-09-23"


# ── ⚠️ Ce qui fait un retard, et ce qui n'en fait pas ──────────────────────

def test_un_depot_posterieur_a_nos_chiffres_est_un_retard():
    """Attendu calculé à la main : du 18/06 au 23/09 = 97 jours."""
    r = ff.retard("2026-06-18", {"date": "2026-09-23"})
    assert r["retard_jours"] == 97


def test_un_depot_ANTERIEUR_a_nos_chiffres_n_apprend_rien():
    """⚠️ C'est probablement celui dont nos chiffres sont tirés. Le signaler
    comme un retard ferait crier au loup sur toute la cote."""
    assert ff.retard("2026-06-18", {"date": "2026-03-30"}) is None


def test_un_depot_du_meme_jour_n_est_pas_un_retard():
    """⚠️ La marge d'un jour absorbe le décalage entre la date de dépôt et
    celle de la saisie. Sans elle, un fondamental saisi le jour même du dépôt
    s'afficherait comme périmé."""
    assert ff.retard("2026-06-18", {"date": "2026-06-18"}) is None
    assert ff.retard("2026-06-18", {"date": "2026-06-19"}) is None
    assert ff.retard("2026-06-18", {"date": "2026-06-20"})["retard_jours"] == 2


def test_sans_date_de_reference_le_retard_est_INCONNU_et_non_nul():
    """⚠️ CAS RÉEL — quatre titres (T2S, MDP, DLM, DIS) sont absents de
    `fondamentaux.json` et retombent sur la table figée, sans date.

    Pour eux, tout dépôt EST un retard, mais son ampleur est inconnue. Rendre
    0 ferait passer « on ne sait pas » pour « à jour ».
    """
    r = ff.retard(None, {"date": "2026-09-23"})
    assert r is not None
    assert r["retard_jours"] is None
    assert "aucune date" in r["_lecture"]


def test_une_date_illisible_ne_fait_pas_lever():
    assert ff.retard("pas une date", {"date": "2026-09-23"})["retard_jours"] is None
    assert ff.retard("2026-06-18", {"date": "n'importe quoi"}) is None
    assert ff.retard("2026-06-18", None) is None


# ── ⚠️ Le module ne lit pas les chiffres ───────────────────────────────────

def test_la_sortie_ne_contient_aucun_chiffre_de_bilan():
    """⚠️ TESTÉ, parce que c'est la limite qui tient tout le module. Publier
    un BPA extrait d'un PDF mal lu serait pire que l'absence : un lecteur
    retient le nombre et oublie l'avertissement."""
    r = ff.retard("2026-06-18", {"date": "2026-09-23", "titre": "x", "url": "y"})
    for interdit in ("bpa", "per", "pe", "resultat_net", "chiffre_affaires",
                     "dividende", "roe"):
        assert interdit not in r, f"le module publie « {interdit} »"


def test_le_module_ne_touche_a_aucun_score():
    """⚠️ R8 — c'est un avertissement de fraîcheur, pas une note."""
    import ast
    arbre = ast.parse((RACINE / "pipeline" / "fondamentaux_frais.py")
                      .read_text(encoding="utf-8"))
    for n in ast.walk(arbre):
        if isinstance(n, ast.Constant) and isinstance(n.value, str):
            assert n.value not in {"v53", "bvc", "score_fond", "score_tech",
                                   "score_nlp", "poids", "sig"}, (
                f"le module manipule « {n.value} »")


# ── Le flux et l'écran ─────────────────────────────────────────────────────

def test_le_flux_signale_les_titres_en_retard():
    f = RACINE / "data.json"
    if not f.exists():
        pytest.skip("data.json absent de ce clone")
    d = json.loads(f.read_text(encoding="utf-8"))
    r = d.get("fondamentaux_frais")
    assert r is not None, "la fraîcheur des fondamentaux n'est pas publiée"
    en_retard = [x["symbol"] for x in (d.get("tickers") or [])
                 if (x.get("_meta") or {}).get("comptes_plus_recents")]
    assert len(en_retard) == r["titres_en_retard"], (
        "le résumé et le détail ne comptent pas la même chose")


def test_l_avertissement_voyage_dans_meta():
    """⚠️ Le piège du 25/09 : `rang_secteur`, publié à la RACINE du ticker,
    n'atteignait jamais l'écran — la fusion recopie une liste nommée. Placer
    l'avertissement dans `_meta`, qui traverse en bloc, l'évite par
    construction."""
    ecran = (RACINE / "index.html").read_text(encoding="utf-8")
    assert "_meta:t._meta" in ecran, "le bloc _meta ne traverse plus la fusion"
    assert "comptes_plus_recents" in ecran, "l'écran n'affiche pas l'avertissement"


def test_l_ecran_dit_qu_il_ne_lit_pas_les_chiffres():
    """⚠️ Sans cette phrase, un lecteur croirait que le terminal a intégré les
    nouveaux comptes."""
    # ⚠️ ON VISE LA LECTURE RÉELLE, PAS LA PREMIÈRE OCCURRENCE DU MOT.
    # La première version cherchait depuis `ecran.find("comptes_plus_recents")`
    # — et le nom apparaît désormais dans un COMMENTAIRE placé plus haut, si
    # bien que le test rougissait sur du code juste. Quatrième fois de la
    # journée qu'un test lit de la prose : un fichier entier contient aussi
    # ses commentaires.
    ecran = (RACINE / "index.html").read_text(encoding="utf-8")
    i = ecran.find("meta(r).comptes_plus_recents")
    assert i > 0, "le composant ne lit pas l'avertissement"
    bloc = ecran[i:i + 1600]
    assert "n'en lit pas les chiffres" in bloc, (
        "l'écran laisse croire que les nouveaux comptes sont intégrés")
