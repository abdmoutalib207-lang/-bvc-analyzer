#!/usr/bin/env python3
"""Une séance corrigée doit survivre au réimport du lendemain.

⚠️ CE QUE LA MESURE A MONTRÉ AVANT D'APPLIQUER QUOI QUE CE SOIT
───────────────────────────────────────────────────────────────
    data/historique/MSA.xlsx   s'arrête au 12/05/2026
    première séance contaminée    13/05/2026

Les 22 séances en cause ne viennent donc PAS du fichier figé : elles viennent
de l'extension BVCscrap, qui identifie les sociétés par NOM — la voie même par
laquelle les cours de Mutandis sont entrés. Et dans `_run()`, les chandelles
stockées ne sont reprises que pour les dates POSTÉRIEURES à ce qui vient d'être
téléchargé.

Corriger le fichier et s'arrêter là, c'était donc poser une correction qui
serait défaite au premier import — sans bruit, la valeur fausse revenant seule.
C'est la leçon de CMT, écrasée dix-sept minutes après sa réception, appliquée
avant l'incident plutôt qu'après.

⚠️ CE QUE CETTE COUCHE N'EST PAS
Ce n'est pas un contrôle d'identité : elle ne vérifie rien sur les autres
titres ni sur les autres séances. Et ce n'est pas `series_acceptees`, qui fige
le titre — MSA cote tous les jours.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE / "pipeline"))

DOSSIER = RACINE / "datasets" / "corrections_acceptees"
DATES = ("2026-05-13", "2026-06-16")


@pytest.fixture(scope="module")
def recu():
    return json.loads((DOSSIER / "MSA.json").read_text(encoding="utf-8"))


# ── Le document réceptionné ────────────────────────────────────────────────

def test_le_lot_msa_porte_22_seances_et_son_identite(recu):
    assert recu["ticker"] == "MSA" and recu["instrument"] == "SODEP-Marsa Maroc"
    assert recu["seances"] == len(recu["lignes"]) == 22
    assert [l["d"] for l in recu["lignes"]] == sorted(l["d"] for l in recu["lignes"])
    assert recu["lignes"][0]["d"] == DATES[0]
    assert recu["lignes"][-1]["d"] == DATES[1]


def test_chaque_ligne_porte_son_ancien_etat_et_son_niveau_de_preuve(recu):
    """⚠️ Une correction sans son état antérieur n'est pas vérifiable, et sans
    son niveau de preuve elle se lit comme une certitude."""
    for l in recu["lignes"]:
        assert set(l["corrige"]) == set(l["remplace"]) == {"o", "h", "l", "c", "v"}
        assert l["niveau_de_preuve"] == "etabli_par_la_mesure"
        assert l["motif"]


def test_le_montant_en_dirhams_n_est_pas_ecrit_dans_v(recu):
    """Les deux colonnes de l'opérateur restent DISTINCTES : `v` est un nombre
    de titres, jamais un montant."""
    for l in recu["lignes"]:
        assert "NOMBRE DE TITRES" in l["_v"]
        assert isinstance(l["corrige"]["v"], int)


# ── La série publiée ───────────────────────────────────────────────────────

def test_la_serie_publiee_porte_les_22_corrections(recu):
    serie = {b["d"]: b for b in json.loads(
        (RACINE / "pipeline" / "candles" / "MSA.json").read_text(encoding="utf-8"))}
    for l in recu["lignes"]:
        b = serie[l["d"]]
        assert {k: b[k] for k in ("o", "h", "l", "c", "v")} == l["corrige"], l["d"]
    # ⚠️ Et les cours de Mutandis ne sont plus là.
    assert serie["2026-05-13"]["c"] == 843.0
    assert serie["2026-06-16"]["c"] == 868.0


def test_le_plus_bas_52_semaines_n_est_plus_un_cours_de_mutandis():
    """225,00 DH était la clôture de Mutandis du 26/05, prise pour un plancher
    de Marsa Maroc. Le cache doit désormais porter le vrai."""
    cache = json.loads((RACINE / "pipeline" / "historical_data.json")
                       .read_text(encoding="utf-8"))["MSA"]
    assert cache["l52w"] == 702.1

    # ⚠️ NE PAS COMPARER À LA LONGUEUR D'AUJOURD'HUI. Le fichier de chandelles
    # et le cache ne sont pas écrits par le même programme : `update_data.py`
    # ajoute la séance du jour à chaque run, `historical_data.json` n'est
    # réécrit que par `collect_history_bvcscrap.py`. Le premier est donc
    # légitimement EN AVANCE sur le second.
    #
    # Ce test comparait les deux longueurs. Il tenait tant que les deux
    # programmes venaient de passer, et tombait dès que le moteur ajoutait une
    # séance — 571 contre 572, mesuré le 16/09 en intégration continue. Or ce
    # test est dans la GARDE BLOQUANTE d'`update_bvc` : il n'échouait pas tout
    # seul, il EMPÊCHAIT LA PUBLICATION de la séance.
    #
    # Ce qu'il faut vérifier est ailleurs : `n_candles` doit décrire la série
    # SOURCE et non la liste tronquée à 250 points (le piège `_CHAMPS_SERIE`
    # du 14/08, qui faisait retomber 784 à 249). On compare donc au nombre de
    # séances du fichier JUSQU'À la date du cache — exact, et qui ne vieillit
    # pas.
    serie = json.loads((RACINE / "pipeline" / "candles" / "MSA.json")
                       .read_text(encoding="utf-8"))
    jusqu_au_cache = [b for b in serie if b["d"] <= cache["last_date"]]
    assert cache["n_candles"] == len(jusqu_au_cache), (
        f"le cache annonce {cache['n_candles']} séances au {cache['last_date']}, "
        f"le fichier en porte {len(jusqu_au_cache)} à cette date")
    assert cache["n_candles"] > len(cache["candles"]), (
        "n_candles est retombé sur la liste tronquée — le défaut du 14/08")


# ── Le comportement : la correction résiste au réimport ────────────────────

def test_une_serie_recontaminee_est_recorrigee(recu):
    """⚠️ LE TEST QUI COMPTE.

    On simule ce que fait l'extension BVCscrap : elle rend les cours de
    Mutandis sur les 22 séances. La couche doit les réécrire.
    """
    from corrections_acceptees import appliquer
    serie = json.loads((RACINE / "pipeline" / "candles" / "MSA.json")
                       .read_text(encoding="utf-8"))
    recontaminee = [dict(b) for b in serie]
    par_date = {l["d"]: l for l in recu["lignes"]}
    for b in recontaminee:
        if b["d"] in par_date:
            b.update(par_date[b["d"]]["remplace"])
    assert recontaminee != serie, "la simulation n'a rien contaminé"

    out, rapport = appliquer("MSA", recontaminee)
    assert rapport["corrections"] == 22
    assert rapport["refus"] == [] and rapport["seances_absentes"] == []
    assert out == serie, "la série recorrigée doit être celle du dépôt"


def test_la_seance_du_jour_passe_intacte(recu):
    """⚠️ La couche ne doit toucher QUE les séances nommées — sinon elle ferait
    ce que fait `series_acceptees` : figer un titre qui cote."""
    from corrections_acceptees import appliquer
    serie = json.loads((RACINE / "pipeline" / "candles" / "MSA.json")
                       .read_text(encoding="utf-8"))
    demain = serie + [{"d": "2026-09-16", "o": 1.0, "h": 2.0, "l": 0.5, "c": 1.5, "v": 42}]
    out, rapport = appliquer("MSA", demain)
    assert rapport["corrections"] == 0 and rapport["deja_conformes"] == 22
    assert out[-1] == demain[-1]
    assert len(out) == len(serie) + 1


def test_une_seance_absente_est_signalee_jamais_fabriquee(tmp_path, recu):
    """⚠️ Une correction dit « cette bougie est fausse », pas « cette bougie
    devrait exister ». Fabriquer une cotation serait pire que le défaut."""
    from corrections_acceptees import appliquer
    serie = [b for b in json.loads((RACINE / "pipeline" / "candles" / "MSA.json")
                                   .read_text(encoding="utf-8"))
             if b["d"] != DATES[0]]
    out, rapport = appliquer("MSA", serie)
    assert rapport["seances_absentes"] == [DATES[0]]
    assert DATES[0] not in [b["d"] for b in out]


def test_un_etat_inconnu_est_refuse_et_rien_n_est_ecrase(recu):
    """⚠️ Si la série a changé depuis la réception, l'appliquer à l'aveugle
    écraserait un travail que nous ne connaissons pas."""
    from corrections_acceptees import appliquer
    serie = [dict(b) for b in json.loads(
        (RACINE / "pipeline" / "candles" / "MSA.json").read_text(encoding="utf-8"))]
    for b in serie:
        if b["d"] == DATES[0]:
            b["c"] = 777.0
    out, rapport = appliquer("MSA", serie)
    assert len(rapport["refus"]) == 1
    assert rapport["refus"][0]["seance"] == DATES[0]
    assert next(b for b in out if b["d"] == DATES[0])["c"] == 777.0, (
        "un refus ne doit rien écrire")


def test_un_titre_sans_correction_traverse_sans_rien_subir():
    from corrections_acceptees import appliquer
    serie = json.loads((RACINE / "pipeline" / "candles" / "CMT.json")
                       .read_text(encoding="utf-8"))
    out, rapport = appliquer("CMT", serie)
    assert rapport["corrections"] == 0
    assert out == serie


def test_un_document_au_mauvais_ticker_est_refuse(tmp_path):
    from corrections_acceptees import charger
    (tmp_path / "XYZ.json").write_text(
        json.dumps({"ticker": "ABC", "lignes": []}), encoding="utf-8")
    with pytest.raises(ValueError, match="ticker"):
        charger("XYZ", dossier=tmp_path)


def test_le_collecteur_appelle_bien_la_couche():
    """⚠️ Le garde-fou du 11/09 : une pièce qui n'est appelée de nulle part ne
    protège rien. Lu sur l'ARBRE SYNTAXIQUE — une mention en commentaire ne
    compte pas, ce projet s'y est laissé prendre cinq fois.
    """
    import ast
    arbre = ast.parse((RACINE / "pipeline" / "collect_history_bvcscrap.py")
                      .read_text(encoding="utf-8"))
    importe = any(isinstance(n, ast.ImportFrom) and n.module == "corrections_acceptees"
                  for n in ast.walk(arbre))
    appele = any(isinstance(n, ast.Call) and getattr(n.func, "id", "") ==
                 "appliquer_corrections" for n in ast.walk(arbre))
    assert importe, "collect_history_bvcscrap n'importe pas la couche"
    assert appele, "la couche est importée mais jamais appelée"
