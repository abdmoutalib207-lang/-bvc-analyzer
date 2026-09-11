#!/usr/bin/env python3
"""L'identité doit venir des DONNÉES IMPORTÉES, pas de notre table.

⚠️ POURQUOI CE FICHIER EXISTE
Le garde-fou d'identité était branché et éprouvé, mais le parcours normal
l'appelait sans lui transmettre quoi que ce soit : les deux sources réellement
utilisées ne portent aucune identité. Un contrôle nourri par la partie
contrôlée ne contrôle rien — c'est la configuration exacte de juin 2026, où
`MANUAL_MAP` disait « MSA = Mutandis » et la source répondait obligeamment les
cours de Mutandis.

Ces tests portent sur la seule source qui transporte l'identité SUR LA LIGNE
DU COURS : l'export de l'opérateur.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

pd = pytest.importorskip("pandas")

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))
sys.path.insert(0, str(RACINE / "pipeline"))

import identite_source as ids  # noqa: E402
from identites import autoriser_ecriture  # noqa: E402

ENTETE = ("Séance;Ticker;Instrument;Ouverture;Dernier Cours;Plus Haut;"
          "Plus Bas;Volume (MAD);Titres Échangés;Nb Transactions;Capitalisation")


def ecrire(chemin: Path, lignes: list[str]) -> Path:
    chemin.parent.mkdir(parents=True, exist_ok=True)
    chemin.write_text("﻿" + ENTETE + "\n" + "\n".join(lignes) + "\n",
                      encoding="utf-8")
    return chemin


def ligne(d: str, t: str, inst: str, c: str = "35.75") -> str:
    return f"{d};{t};{inst};35.44;{c};35.75;35.12;7090429.20;199597;87;1439.50"


# ═══ CE QUE L'EXPORT PROUVE ════════════════════════════════════════════════

def test_l_identite_est_lue_sur_la_ligne_du_cours(tmp_path):
    f = ecrire(tmp_path / "ADH" / "e.csv",
               [ligne("10/09/2026", "ADH", "DOUJA PROM ADDOHA"),
                ligne("09/09/2026", "ADH", "DOUJA PROM ADDOHA")])
    lu = ids.identite_de_l_export(f)
    assert lu["identite_portee"]
    assert lu["instrument"] == "DOUJA PROM ADDOHA"
    assert lu["lignes_de_cours"] == 2


def test_un_export_qui_mele_deux_instruments_est_refuse(tmp_path):
    """⚠️ C'EST LA CONTAMINATION, VUE DEPUIS LA SOURCE.

    Aucun contrôle numérique ne peut l'attraper : les deux séries sont bien
    formées. Seule l'identité, lue ligne à ligne, la voit."""
    f = ecrire(tmp_path / "ADH" / "e.csv",
               [ligne("10/09/2026", "ADH", "DOUJA PROM ADDOHA"),
                ligne("09/09/2026", "MUT", "MUTANDIS", c="231.00")])
    lu = ids.identite_de_l_export(f)
    assert not lu["identite_portee"]
    assert "plusieurs instruments" in lu["motif"]
    assert len(lu["paires_vues"]) == 2


def test_une_identite_qui_ne_couvre_pas_tous_les_cours_est_refusee(tmp_path):
    """Une identité portée par une partie des lignes ne nomme pas les autres."""
    f = ecrire(tmp_path / "ADH" / "e.csv",
               [ligne("10/09/2026", "ADH", "DOUJA PROM ADDOHA"),
                ligne("09/09/2026", "", "")])
    lu = ids.identite_de_l_export(f)
    assert not lu["identite_portee"]
    assert "sans identité" in lu["motif"]


def test_un_fichier_sans_colonne_d_identite_ne_prouve_rien(tmp_path):
    """⚠️ Le cas de l'XLSX local : le nom du fichier est NOTRE convention."""
    f = tmp_path / "ADH" / "nu.csv"
    f.parent.mkdir(parents=True)
    f.write_text("Séance;Ouverture;Dernier Cours\n10/09/2026;35.44;35.75\n",
                 encoding="utf-8")
    lu = ids.identite_de_l_export(f)
    assert not lu["identite_portee"]
    assert "identité absentes" in lu["motif"]


def test_une_ligne_sans_cours_ne_temoigne_de_rien(tmp_path):
    """Une ligne qui ne porte pas de prix ne prouve pas l'identité des prix."""
    f = ecrire(tmp_path / "ADH" / "e.csv",
               [ligne("10/09/2026", "ADH", "DOUJA PROM ADDOHA"),
                "09/09/2026;ZZZ;AUTRE SOCIETE;-;-;-;-;-;-;-;-"])
    lu = ids.identite_de_l_export(f)
    assert lu["identite_portee"], "une ligne vide a disqualifié un export sain"
    assert lu["lignes_de_cours"] == 1


# ═══ CE QUE L'IDENTITÉ LUE PRODUIT EN AVAL ═════════════════════════════════

def test_le_nom_lu_ouvre_l_ecriture_et_un_autre_nom_la_ferme(tmp_path):
    ecrire(tmp_path / "ADH" / "e.csv", [ligne("10/09/2026", "ADH", "DOUJA PROM ADDOHA")])
    ecrire(tmp_path / "CSR" / "e.csv", [ligne("10/09/2026", "CSR", "COSUMAR")])
    recu = ids.pour_le_collecteur(tmp_path)
    assert recu == {"ADH": "DOUJA PROM ADDOHA", "CSR": "COSUMAR"}

    assert autoriser_ecriture("ADH", recu["ADH"])["autorise"]
    # ⚠️ Le contre-sens de juin : le bon ticker, le nom d'une autre société.
    faux = autoriser_ecriture("ADH", recu["CSR"])
    assert not faux["autorise"]
    assert "AUTRE ENTREPRISE" in faux["motif"]


def test_on_ne_transmet_pas_notre_propre_ticker_comme_preuve():
    """⚠️ Le défaut structurel de juin, en une ligne.

    Confronter notre ticker à notre ticker rend toujours « concordant ». Ce
    qu'il faut transmettre est ce que le FOURNISSEUR affirme servir."""
    source = (RACINE / "pipeline" / "identite_source.py").read_text(encoding="utf-8")
    assert "COLONNE_INSTRUMENT" in source
    assert '"instrument"' in source


# ═══ LE PARCOURS D'IMPORT UTILISE-T-IL VRAIMENT CETTE IDENTITÉ ? ═══════════

def test_le_collecteur_importe_l_export_et_refuse_le_reste(tmp_path, monkeypatch):
    """⚠️ Le test qui manquait : ce n'est pas la fonction qu'on éprouve, c'est
    le parcours. Un titre avec export est importé ; un titre sans export est
    refusé, et rien n'est écrit pour lui."""
    import collect_history_bvcscrap as col

    sources = tmp_path / "sources"
    ecrire(sources / "ADH" / "e.csv",
           [ligne(f"{j:02d}/06/2026", "ADH", "DOUJA PROM ADDOHA")
            for j in range(1, 26)])
    monkeypatch.setattr(col, "SOURCES_DIR", sources)
    monkeypatch.setattr(col, "XLSX_DIR", tmp_path / "xlsx")
    monkeypatch.setattr(col, "MANUAL_MAP", {"ADH": "Addoha", "MSA": "Marsa Maroc"})
    monkeypatch.setattr(col, "load_xlsx", lambda t: pd.DataFrame())
    monkeypatch.setattr(col, "time", type("T", (), {"sleep": staticmethod(lambda s: None)}))

    candles = tmp_path / "candles"
    res, refus = col.run(tickers_filter=["ADH", "MSA"], identites_recues={},
                         rendre_refus=True, candles_dir=candles)

    assert "ADH" in res, "l'export porte son identité et n'a pas été importé"
    assert (candles / "ADH.json").exists()
    assert "MSA" in refus and not (candles / "MSA.json").exists()
    assert "identité" in refus["MSA"]["motif"]


def test_un_export_contamine_n_ecrit_rien(tmp_path, monkeypatch):
    """Deux instruments dans le même fichier : aucune bougie écrite."""
    import collect_history_bvcscrap as col

    sources = tmp_path / "sources"
    lignes = [ligne(f"{j:02d}/06/2026", "ADH", "DOUJA PROM ADDOHA")
              for j in range(1, 25)]
    lignes.append(ligne("25/06/2026", "MUT", "MUTANDIS", c="231.00"))
    ecrire(sources / "ADH" / "e.csv", lignes)
    monkeypatch.setattr(col, "SOURCES_DIR", sources)
    monkeypatch.setattr(col, "XLSX_DIR", tmp_path / "xlsx")
    monkeypatch.setattr(col, "MANUAL_MAP", {"ADH": "Addoha"})
    monkeypatch.setattr(col, "load_xlsx", lambda t: pd.DataFrame())
    monkeypatch.setattr(col, "time", type("T", (), {"sleep": staticmethod(lambda s: None)}))

    candles = tmp_path / "candles"
    res, refus = col.run(tickers_filter=["ADH"], identites_recues={},
                         rendre_refus=True, candles_dir=candles)
    assert "ADH" not in res
    assert not (candles / "ADH.json").exists()


def test_sous_identite_prouvee_rien_d_autre_n_est_fusionne(tmp_path, monkeypatch):
    """⚠️ Une identité prouvée pour UN fichier ne blanchit pas les lignes d'un
    autre. Sans cette règle, l'export servirait de laissez-passer à l'XLSX —
    le contrôle serait rétabli en apparence et contourné en fait."""
    import collect_history_bvcscrap as col

    sources = tmp_path / "sources"
    ecrire(sources / "ADH" / "e.csv",
           [ligne(f"{j:02d}/06/2026", "ADH", "DOUJA PROM ADDOHA")
            for j in range(1, 26)])
    monkeypatch.setattr(col, "SOURCES_DIR", sources)
    monkeypatch.setattr(col, "XLSX_DIR", tmp_path / "xlsx")
    monkeypatch.setattr(col, "MANUAL_MAP", {"ADH": "Addoha"})
    # Une source locale qui prétendrait ajouter 300 séances non identifiées.
    intrus = pd.DataFrame({
        "date": pd.date_range("2020-01-01", periods=300, freq="B"),
        "open": [9.0] * 300, "high": [9.0] * 300, "low": [9.0] * 300,
        "close": [9.0] * 300, "volume": [1] * 300,
    })
    monkeypatch.setattr(col, "load_xlsx", lambda t: intrus)
    monkeypatch.setattr(col, "time", type("T", (), {"sleep": staticmethod(lambda s: None)}))

    candles = tmp_path / "candles"
    res, _ = col.run(tickers_filter=["ADH"], identites_recues={},
                     rendre_refus=True, candles_dir=candles)
    assert res["ADH"]["n_candles"] == 25, "des lignes non identifiées ont été fusionnées"
