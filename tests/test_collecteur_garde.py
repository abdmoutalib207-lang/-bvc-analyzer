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
    # ⚠️ Le dossier `sources/` du DÉPÔT ne doit pas entrer dans un test.
    # Le jour où un export MSA y est déposé, `load_export()` le trouve et le
    # parcours change sous le test sans que le test ait bougé. Un test qui
    # dépend du contenu du dépôt ne décrit plus le code.
    monkeypatch.setattr(col, "SOURCES_DIR", tmp_path / "sources_absentes")
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

def test_une_fenetre_entierement_contaminee_ne_rend_aucun_indicateur(parcours, monkeypatch):
    """⚠️ Le collecteur calculait un RSI de 35,0 et une MA20 de 232,0 sur les
    18 observations contaminées de MSA."""
    monkeypatch.setattr(col, "load_xlsx", lambda t: pd.DataFrame({
        "date": pd.date_range("2026-05-13", periods=25, freq="B"),
        "open": [230.0] * 25, "high": [232.0] * 25, "low": [228.0] * 25,
        "close": [231.0] * 25, "volume": [100] * 25,
    }))
    res, refus = lancer(parcours, {"MSA": "Sodep-Marsa Maroc"})
    ind = res.get("MSA", {})
    for nom in ("rsi", "ma20", "ma50", "h52w"):
        assert nom not in ind, f"{nom} calculé sur une fenêtre contaminée"
    assert "APPARTENANCE" in ind.get("_pourquoi", "")


def test_une_periode_ancienne_contaminee_ne_bannit_pas_le_titre(parcours, monkeypatch):
    """⚠️ Exigence de la revue : ne pas interdire toute analyse d'un titre
    parce qu'une période ANCIENNE est contaminée."""
    monkeypatch.setattr(col, "load_xlsx", lambda t: pd.DataFrame({
        "date": pd.date_range("2026-07-01", periods=30, freq="B"),
        "open": [850.0] * 30, "high": [860.0] * 30, "low": [840.0] * 30,
        "close": [855.0] * 30, "volume": [100] * 30,
    }))
    res, refus = lancer(parcours, {"MSA": "Sodep-Marsa Maroc"})
    assert "MSA" in res and res["MSA"].get("ma20") is not None
    assert (parcours / "MSA.json").exists()


def test_le_cas_exact_de_la_revue_une_moyenne_recente_survit(parcours, monkeypatch):
    """⚠️ LE CONTRE-EXEMPLE DE LA REVUE, REJOUÉ.

    Une observation suspecte le 10 juin, puis quarante observations propres à
    partir de juillet. Le collecteur refusait TOUT le résultat parce qu'il
    passait toutes les dates au contrôle. Une moyenne sur vingt clôtures de
    juillet ne touche pourtant jamais le 10 juin.
    """
    monkeypatch.setattr(col, "load_xlsx", lambda t: pd.concat([
        pd.DataFrame({"date": [pd.Timestamp("2026-06-10")], "open": [231.0],
                      "high": [232.0], "low": [230.0], "close": [231.0],
                      "volume": [100]}),
        pd.DataFrame({
            "date": pd.date_range("2026-07-01", periods=40, freq="B"),
            "open": [850.0] * 40, "high": [860.0] * 40, "low": [840.0] * 40,
            "close": [855.0] * 40, "volume": [100] * 40}),
    ], ignore_index=True))
    res, _ = lancer(parcours, {"MSA": "Sodep-Marsa Maroc"})
    ind = res.get("MSA", {})
    assert ind.get("ma20") == 855.0, "la moyenne récente a été refusée à tort"
    # ⚠️ Et ce qui remonte jusqu'au 10 juin reste bien retiré.
    assert "h52w" not in ind and "ma200" not in ind
    assert "rsi" not in ind, "le RSI est récursif : son amorçage touche juin"


def test_les_anciennes_lignes_ne_sont_jamais_supprimees(parcours, monkeypatch):
    """⚠️ On ne « nettoie » pas une série en retirant les lignes gênantes :
    cela changerait les valeurs sans le dire. On retire l'INDICATEUR, pas la
    donnée."""
    from contamination import indicateurs_permis
    tri = indicateurs_permis("MSA", ["2026-06-10"] + ["2026-07-01"] * 40)
    assert "supprim" in tri["_convention"].lower()
    assert "JAMAIS" in tri["_convention"]


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


# ═══ LE REFUS N'EFFACE RIEN — JUSQU'AU FICHIER ÉCRIT ═══════════════════════

def test_un_refus_ne_supprime_pas_la_donnee_ancienne(parcours, tmp_path, monkeypatch):
    """⚠️ LA CONTRE-ÉPREUVE DE LA REVUE, JOUÉE DE BOUT EN BOUT.

    Elle ne s'arrêtait pas au garde-fou : elle allait jusqu'au fichier. Le
    cache commun était REMPLACÉ par les seuls résultats du run, donc un titre
    refusé à l'import disparaissait du cache — silencieusement, alors même que
    son fichier de chandelles était préservé.

    Ici : le cache contient MSA et CDM. MSA est importé (identité prouvée),
    CDM est refusé (la source renvoie une autre société). Après sauvegarde,
    CDM doit être TOUJOURS LÀ, avec ses anciennes valeurs, et MARQUÉ.
    """
    cache = tmp_path / "historical_data.json"
    cache.write_text(json.dumps({
        "_updated": "2026-06-01T00:00:00+00:00",
        "_tickers": 2,
        "MSA": {"last_close": 800.0, "rsi": 50.0},
        "CDM": {"last_close": 742.0, "rsi": 61.0},
    }), encoding="utf-8")

    res, refus = lancer(parcours,
                        {"MSA": "MSA", "CDM": "Crédit Eqdom"},
                        titres=["MSA", "CDM"])
    assert "MSA" in res and "CDM" not in res
    assert "CDM" in refus

    col.save(res, cache, refus=refus)
    apres = json.loads(cache.read_text(encoding="utf-8"))

    # ⚠️ Conservé — et avec SES valeurs, pas celles d'un autre titre.
    assert "CDM" in apres, "un refus d'import a effacé la donnée ancienne"
    assert apres["CDM"]["last_close"] == 742.0
    assert apres["CDM"]["rsi"] == 61.0

    # ⚠️ Et marqué : conserver n'est pas autoriser à relire comme récent.
    marque = apres["CDM"]["_reimport_refuse"]
    assert marque["motif"], "la donnée est conservée sans dire pourquoi"
    assert "ANCIENNE" in marque["_lecture"]
    assert "CDM" in apres["_conserves_sans_reimport"]
    assert "CDM" in apres["_refuses_ce_run"]
    assert apres["_tickers"] == 2, "le compte du cache a bougé sous un refus"

    # ⚠️ Et le titre importé, lui, est bien rafraîchi.
    assert apres["MSA"]["last_close"] != 800.0


def test_un_cache_illisible_n_est_jamais_ecrase(parcours, tmp_path):
    """⚠️ Ne pas lire un fichier n'autorise pas à le remplacer. Sans cette
    règle, une écriture interrompue effacerait 81 historiques."""
    cache = tmp_path / "historical_data.json"
    cache.write_text('{"MSA": {"last_close": 800.0}, TRONQU', encoding="utf-8")
    avant = cache.read_text(encoding="utf-8")
    res, refus = lancer(parcours, {"MSA": "MSA"})
    with pytest.raises(json.JSONDecodeError):
        col.save(res, cache, refus=refus)
    assert cache.read_text(encoding="utf-8") == avant
