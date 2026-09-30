"""File d'attente des comptes à lire — 30/09/2026."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pipeline.file_attente_comptes import file_attente, rapport  # noqa: E402

DEPOTS = {
    "AAA": {"date": "2026-09-20", "titre": "Aaa - Résultats financiers du 1er semestre 2026", "url": "u1"},
    "BBB": {"date": "2026-09-21", "titre": "Bbb - CP relatif aux résultats du 1er semestre 2026", "url": "u2"},
    "CCC": {"date": "2026-09-22", "titre": "Ccc - CP relatif à un profit warning sur le 1er semestre 2026",
            "url": "u3", "avertissement": True},
    "DDD": {"date": "2026-09-23", "titre": "Ddd - Résultats financiers du 1er semestre 2026", "url": "u4"},
    "EEE": {"date": "2026-04-10", "titre": "Eee - Résultats annuels 2025", "url": "u5"},
    "FFF": {"date": "2026-07-15", "titre": "Fff - Rapport financier annuel 2025", "url": "u6"},
    "GGG": {"date": "2026-09-07", "titre": "Ggg - RFS juin 2026", "url": "u7"},
}
JEU = {"titres": {"BBB": {}}, "_ecartes": {"DDD": "motif"}}


def test_repartition():
    f = file_attente(DEPOTS, JEU, "2026-06-30")
    assert [e["ticker"] for e in f["a_lire"]] == ["GGG", "AAA"]
    assert [e["ticker"] for e in f["avertissements"]] == ["CCC"]
    assert [e["ticker"] for e in f["ecartes"]] == ["DDD"]


def test_integre_absent_de_la_file():
    f = file_attente(DEPOTS, JEU, "2026-06-30")
    assert "BBB" not in {e["ticker"] for v in f.values() for e in v}


def test_annuel_n_est_pas_un_semestriel():
    # Un RFA 2025 déposé en juillet reste hors file, même postérieur à la période.
    f = file_attente(DEPOTS, JEU, "2026-06-30")
    tous = {e["ticker"] for v in f.values() for e in v}
    assert "FFF" not in tous and "EEE" not in tous


def test_rapport_lisible():
    texte = rapport(file_attente(DEPOTS, JEU, "2026-06-30"))
    assert "pas encore intégrés : 2" in texte
    assert "[Aaa - Résultats financiers du 1er semestre 2026](u1)" in texte
