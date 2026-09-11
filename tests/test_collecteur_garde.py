#!/usr/bin/env python3
"""Le refus d'écriture, éprouvé dans le PARCOURS QUI ÉCRIT RÉELLEMENT.

⚠️ POURQUOI CE FICHIER EXISTE
Le garde-fou était défini et n'était appelé de nulle part. `run()` allait
jusqu'à l'écriture sans jamais le consulter. La revue externe l'a éprouvé dans
un dossier temporaire, avec une source simulée et un garde-fou remplacé par une
fonction qui refuse tout : **zéro appel, trois fichiers créés, indicateurs
renvoyés pour les trois**.

Mes tests d'alors interrogeaient `autoriser_ecriture()` directement. Ils
vérifiaient une fonction, pas une promesse. Une promesse non branchée ne
protège rien, et un test qui n'emprunte pas le parcours ne peut pas s'en
apercevoir.

Les tests ci-dessous LANCENT le parcours d'import, avec une réponse fournisseur
contrôlée, et regardent ce qui atterrit sur le disque.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

pd = pytest.importorskip("pandas")

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))
sys.path.insert(0, str(RACINE / "pipeline"))

import collect_history_bvcscrap as col  # noqa: E402


def serie_factice(n: int = 40, base: float = 100.0) -> "pd.DataFrame":
    """Une série bien formée — le défaut n'est JAMAIS dans les nombres."""
    return pd.DataFrame({
        "date": pd.date_range("2026-01-05", periods=n, freq="B"),
        "open": [base + i * 0.1 for i in range(n)],
        "high": [base + i * 0.1 + 1 for i in range(n)],
        "low": [base + i * 0.1 - 1 for i in range(n)],
        "close": [base + i * 0.1 for i in range(n)],
        "volume": [1000 + i for i in range(n)],
    })


@pytest.fixture
def parcours(tmp_path, monkeypatch):
    """Le vrai `run()`, avec une source simulée et un dossier jetable."""
    monkeypatch.setattr(col, "XLSX_DIR", tmp_path / "xlsx")
    monkeypatch.setattr(col, "MANUAL_MAP",
                        {"MSA": "Marsa Maroc", "CDM": "Crédit du Maroc"})
    monkeypatch.setattr(col, "load_xlsx", lambda t: serie_factice())
    monkeypatch.setattr(col, "adjust_splits_df", lambda t, df: df)
    monkeypatch.setattr(col, "time", type("T", (), {"sleep": staticmethod(lambda s: None)}))
    return tmp_path / "candles"


def lancer(dossier, identites, titres=None):
    return col.run(tickers_filter=titres or ["MSA"], identites_recues=identites,
                   rendre_refus=True, candles_dir=dossier)


# ═══ IDENTITÉ ERRONÉE OU ABSENTE — AUCUNE ÉCRITURE ═════════════════════════

def test_identite_erronee_aucun_fichier_cree(parcours):
    """Le scénario de juin : on demande MSA, la source renvoie Mutandis."""
    res, refus = lancer(parcours, {"MSA": "Mutandis SCA"})
    assert not parcours.exists() or list(parcours.glob("*.json")) == []
    assert "MSA" not in res, "un indicateur a été produit depuis une réponse refusée"
    assert "MSA" in refus and "AUTRE ENTREPRISE" in refus["MSA"]["motif"]


def test_identite_absente_aucun_fichier_cree(parcours):
    """Sans identité reçue, il n'y a rien à vérifier — donc rien à écrire."""
    res, refus = lancer(parcours, {})
    assert not parcours.exists() or list(parcours.glob("*.json")) == []
    assert res == {}
    assert "MSA" in refus


def test_un_import_refuse_laisse_intact_ce_qui_existait(parcours):
    """⚠️ Exigence explicite de la revue : un refus ne doit rien détruire."""
    parcours.mkdir(parents=True)
    ancien = parcours / "MSA.json"
    contenu = json.dumps([{"d": "2025-01-02", "o": 1, "h": 2, "l": 1,
                           "c": 1.5, "v": 10}])
    ancien.write_text(contenu, encoding="utf-8")

    res, refus = lancer(parcours, {"MSA": "Mutandis SCA"})
    assert ancien.read_text(encoding="utf-8") == contenu, \
        "l'import refusé a modifié un fichier existant"
    assert "MSA" not in res


def test_une_ressemblance_n_ouvre_pas_le_parcours(parcours):
    """Contre-exemple de la revue : « Crédit Eqdom » pour « Crédit du Maroc ».

    Le mot commun « Crédit » donnait 50 % de concordance, au-dessus du seuil.
    Une ressemblance appelle une vérification, jamais une autorisation.
    """
    res, refus = lancer(parcours, {"CDM": "Crédit Eqdom"}, ["CDM"])
    assert list(parcours.glob("*.json")) == [] if parcours.exists() else True
    assert "CDM" not in res
    assert "CDM" in refus


# ═══ IDENTITÉ ÉTABLIE — L'IMPORT SE FAIT ═══════════════════════════════════

def test_identite_exacte_import_realise(parcours):
    """La garde ne doit pas tout bloquer : une identité prouvée passe."""
    res, refus = lancer(parcours, {"MSA": "Sodep-Marsa Maroc"})
    assert (parcours / "MSA.json").exists(), "aucun fichier écrit"
    assert "MSA" in res and res["MSA"]["rsi"] is not None
    assert refus == {}


def test_identifiant_fournisseur_suffit(parcours):
    res, _ = lancer(parcours, {"MSA": "MSA"})
    assert (parcours / "MSA.json").exists()


def test_isin_suffit(parcours):
    import bvc_config as cfg
    res, _ = lancer(parcours, {"MSA": cfg.ISIN_MAP["MSA"]})
    assert (parcours / "MSA.json").exists()


# ═══ CONTAMINATION — SUR LES DATES RÉELLEMENT UTILISÉES ════════════════════

def test_une_fenetre_contaminee_ne_produit_aucun_indicateur(parcours, monkeypatch):
    """⚠️ Le collecteur calculait un RSI de 35,0 et une MA20 de 232,0 sur les
    18 observations contaminées de MSA. Le contrôle n'était branché que sur les
    nouveaux chemins de qualification."""
    monkeypatch.setattr(col, "load_xlsx", lambda t: pd.DataFrame({
        "date": pd.date_range("2026-05-13", periods=25, freq="B"),
        "open": [230.0] * 25, "high": [232.0] * 25, "low": [228.0] * 25,
        "close": [231.0] * 25, "volume": [100] * 25,
    }))
    res, refus = lancer(parcours, {"MSA": "Sodep-Marsa Maroc"})
    assert "MSA" not in res, "un indicateur a été calculé sur une fenêtre contaminée"
    assert "contamination" in refus["MSA"]
    assert "APPARTENANCE" in refus["MSA"]["motif"]
    assert list(parcours.glob("*.json")) == [] if parcours.exists() else True


def test_une_periode_ancienne_contaminee_ne_bannit_pas_le_titre(parcours, monkeypatch):
    """⚠️ Exigence de la revue : ne pas interdire toute analyse d'un titre
    parce qu'une période ANCIENNE est contaminée. Un indicateur qui ne regarde
    que des séances postérieures ne touche pas la fenêtre de mai."""
    monkeypatch.setattr(col, "load_xlsx", lambda t: pd.DataFrame({
        "date": pd.date_range("2026-07-01", periods=30, freq="B"),
        "open": [850.0] * 30, "high": [860.0] * 30, "low": [840.0] * 30,
        "close": [855.0] * 30, "volume": [100] * 30,
    }))
    res, refus = lancer(parcours, {"MSA": "Sodep-Marsa Maroc"})
    assert "MSA" in res, "le titre est banni alors que la fenêtre est propre"
    assert (parcours / "MSA.json").exists()


# ═══ LA PROPOSITION DE FUSION DIT CE QUE LE SITE LIT VRAIMENT ══════════════

def test_le_frontend_lit_aussi_les_chandelles():
    """⚠️ J'avais écrit que le site ne sert que data.json et news.json.

    `fetchChart()` charge `./pipeline/candles/${sym}.json` en direct. La
    proposition de fusion doit le dire, sinon elle sous-estime les dépendances.
    """
    html = (RACINE / "index.html").read_text(encoding="utf-8")
    assert "pipeline/candles/" in html
    doc = (RACINE / "docs" / "PROPOSITION_FUSION.md").read_text(encoding="utf-8")
    assert "fetchChart" in doc and "pipeline/candles" in doc


def test_la_proposition_ne_promet_plus_l_absence_de_risque():
    """⚠️ « fusionnables sans risque » et « une barrière, pas un risque »
    retirés : un contrôle peut interrompre une actualisation légitime."""
    doc = (RACINE / "docs" / "PROPOSITION_FUSION.md").read_text(encoding="utf-8")
    assert "sans risque" not in doc
    assert "pas un risque" not in doc
    assert "peut être interrompue" in doc


def test_la_proposition_n_annonce_plus_un_recul_certain():
    """⚠️ La fusion d'essai garde la version de main : le recul n'était pas
    établi, et l'ancienneté d'un fichier ne le démontre pas."""
    doc = (RACINE / "docs" / "PROPOSITION_FUSION.md").read_text(encoding="utf-8")
    assert "Aucun recul" in doc
    assert "ne démontre pas son" in doc or "ne démontre pas" in doc
    assert "CONFLIT" in doc, "le conflit réel doit être annoncé"
