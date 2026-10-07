"""Un essai à blanc n'écrit rien sur disque.

Le 05/10/2026, `update_data.run(dry_run=True)` — lancé pour vérifier les
volumes contre le bulletin CDG — a modifié pipeline/marche_history.json : la
collecte de l'état du marché, appelée depuis la lecture du MASI, ignorait le
mode. Corrigé par `ECRITURE_AUTORISEE`, posé par `run()`.
"""
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

import update_data  # noqa: E402


def _ligne_masi():
    return {"Cours": "17267.17", "VariationP": "-0.21", "DateCotation": "05/10/2026 08:03"}


def test_la_collecte_du_marche_n_ecrit_pas_pendant_un_essai_a_blanc(monkeypatch):
    appels = []
    import pipeline.marche_history as mh
    monkeypatch.setattr(mh, "enregistrer", lambda ligne, asof: appels.append(asof) or True)
    monkeypatch.setattr(update_data, "_ligne_indice_cdg", lambda code: _ligne_masi())
    monkeypatch.setattr(update_data, "ECRITURE_AUTORISEE", False)
    r = update_data.fetch_masi_cdg()
    assert r["value"] == 17267.17 and appels == []


def test_la_collecte_du_marche_ecrit_en_run_normal(monkeypatch):
    appels = []
    import pipeline.marche_history as mh
    monkeypatch.setattr(mh, "enregistrer", lambda ligne, asof: appels.append(asof) or True)
    monkeypatch.setattr(update_data, "_ligne_indice_cdg", lambda code: _ligne_masi())
    monkeypatch.setattr(update_data, "ECRITURE_AUTORISEE", True)
    update_data.fetch_masi_cdg()
    assert appels == ["2026-10-05"]


# ── Dépôts AMMC — 07/10/2026 ────────────────────────────────────────────────
# Un essai à blanc a réécrit pipeline/depots_ammc.json : `mettre_a_jour()`
# écrit son cache, et le run l'appelait quel que soit le mode.

def _ammc_sans_reseau(monkeypatch):
    import pipeline.depots_ammc as da
    ecritures = []
    monkeypatch.setattr(da, "collecter", lambda **k: [{"date": "2026-10-07", "titre": "X", "url": "u"}])
    monkeypatch.setattr(da, "charger", lambda: [])
    monkeypatch.setattr(da.CACHE.__class__, "write_text",
                        lambda self, *a, **k: ecritures.append(str(self)))
    return ecritures


def test_les_depots_ammc_ne_s_ecrivent_pas_pendant_un_essai_a_blanc(monkeypatch):
    ecritures = _ammc_sans_reseau(monkeypatch)
    monkeypatch.setattr(update_data, "ECRITURE_AUTORISEE", False)
    entrees = update_data._entrees_depots_ammc()
    assert [e["url"] for e in entrees] == ["u"], "à blanc, la liste doit être la même"
    assert ecritures == [], f"écriture pendant un essai à blanc : {ecritures}"


def test_les_depots_ammc_s_ecrivent_en_run_normal(monkeypatch):
    ecritures = _ammc_sans_reseau(monkeypatch)
    monkeypatch.setattr(update_data, "ECRITURE_AUTORISEE", True)
    update_data._entrees_depots_ammc()
    assert any(w.endswith("depots_ammc.json") for w in ecritures)
