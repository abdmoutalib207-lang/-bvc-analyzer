"""17/11/2026 — deux trous comblés sans rien inventer.

1. NRJ (introduite le 16/11) n'avait pas de capitalisation : absente du relevé
   de la Bourse du 20/10 et sans comptes relevés. Le nombre d'actions d'après
   l'opération est au registre des introductions, avec sa pièce.
2. ENK publie ses comptes en dinars : la capitalisation convertie exige le taux
   BCT du jour du cours (règle g). Il n'était relevé qu'à la main — le dernier
   datait du 19/10. Le moteur le relève désormais à chaque passage.
"""
import json
import logging
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))
logging.disable(logging.CRITICAL)

import update_data as ud  # noqa: E402


def test_nrj_prend_le_nombre_d_actions_de_l_introduction(monkeypatch):
    monkeypatch.setattr(ud, "FAITS_DATA", {})
    assert ud._actions_sourcees("NRJ") == 13_125_000
    assert round(13_125_000 * 171.55 / 1e6) == 2252          # recoupement MASI Screener
    # contrôle négatif : un titre ni au relevé ni introduit n'a toujours rien
    assert ud._actions_sourcees("ZZZ") is None


def test_le_taux_du_jour_du_cours_est_releve_et_range(monkeypatch, tmp_path):
    from pipeline import change_bct
    fichier = tmp_path / "change.json"
    fichier.write_text(json.dumps({"taux": {}}), encoding="utf-8")
    monkeypatch.setattr(change_bct, "TAUX", fichier)
    vus = []

    def relever(d):
        vus.append(d)
        return {"date": d, "tnd_par_mad": 0.30517, "source": "BCT"} if d == "2026-11-13" else None
    monkeypatch.setattr(change_bct, "relever", relever)
    monkeypatch.setattr(ud, "FAITS_DATA", {"ENK": {"devise": "TND"}, "IAM": {}})
    monkeypatch.setattr(ud, "_TAUX_MAD_TND", {})
    assert ud._completer_taux_bct({"ENK": {"asof": "2026-11-13"}, "IAM": {"asof": "2026-11-13"}}) == ["2026-11-13"]
    assert ud._TAUX_MAD_TND["2026-11-13"]["tnd_par_mad"] == 0.30517
    assert json.loads(fichier.read_text())["taux"]["2026-11-13"]["tnd_par_mad"] == 0.30517
    # un seul relevé : seul ENK publie en dinars
    assert vus == ["2026-11-13"]


def test_controle_negatif_journee_non_publiee_et_taux_deja_connu(monkeypatch, tmp_path):
    from pipeline import change_bct
    fichier = tmp_path / "change.json"
    fichier.write_text(json.dumps({"taux": {}}), encoding="utf-8")
    monkeypatch.setattr(change_bct, "TAUX", fichier)
    monkeypatch.setattr(change_bct, "relever", lambda d: None)
    monkeypatch.setattr(ud, "FAITS_DATA", {"ENK": {"devise": "TND"}})
    monkeypatch.setattr(ud, "_TAUX_MAD_TND", {})
    assert ud._completer_taux_bct({"ENK": {"asof": "2026-11-17"}}) == []
    assert ud._TAUX_MAD_TND == {} and json.loads(fichier.read_text())["taux"] == {}
    # déjà connu : aucun appel à la BCT
    monkeypatch.setattr(change_bct, "relever", lambda d: (_ for _ in ()).throw(AssertionError("appel inutile")))
    monkeypatch.setattr(ud, "_TAUX_MAD_TND", {"2026-11-13": {"tnd_par_mad": 0.3}})
    assert ud._completer_taux_bct({"ENK": {"asof": "2026-11-13"}}) == []


def test_une_panne_reseau_ne_bloque_pas(monkeypatch, tmp_path):
    from pipeline import change_bct
    monkeypatch.setattr(change_bct, "TAUX", tmp_path / "change.json")

    def panne(d):
        raise OSError("réseau")
    monkeypatch.setattr(change_bct, "relever", panne)
    monkeypatch.setattr(ud, "FAITS_DATA", {"ENK": {"devise": "TND"}})
    monkeypatch.setattr(ud, "_TAUX_MAD_TND", {})
    assert ud._completer_taux_bct({"ENK": {"asof": "2026-11-17"}}) == []
