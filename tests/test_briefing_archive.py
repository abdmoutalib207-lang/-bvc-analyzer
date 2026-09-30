"""L'archive des lectures : un fichier par séance, figé après la séance — 30/09/2026."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pipeline.briefing import archiver  # noqa: E402


def _lire(racine, seance):
    return json.loads((racine / "briefings" / f"{seance}.json").read_text(encoding="utf-8"))


def test_les_deux_moments_d_une_seance_sont_gardes(tmp_path):
    archiver({"seance": "2026-09-30", "moment": "mi_journee", "constats": ["a"]},
             "2026-09-30", tmp_path)
    archiver({"seance": "2026-09-30", "moment": "cloture", "constats": ["b"]},
             "2026-09-30", tmp_path)
    doc = _lire(tmp_path, "2026-09-30")
    assert doc["mi_journee"]["constats"] == ["a"]
    assert doc["cloture"]["constats"] == ["b"]


def test_le_meme_jour_le_passage_suivant_remplace(tmp_path):
    archiver({"seance": "2026-09-30", "moment": "cloture", "ecrit_a": "15h45"},
             "2026-09-30", tmp_path)
    archiver({"seance": "2026-09-30", "moment": "cloture", "ecrit_a": "18h45"},
             "2026-09-30", tmp_path)
    assert _lire(tmp_path, "2026-09-30")["cloture"]["ecrit_a"] == "18h45"


def test_le_lendemain_la_lecture_est_figee(tmp_path):
    archiver({"seance": "2026-09-30", "moment": "cloture", "ecrit_a": "18h45"},
             "2026-09-30", tmp_path)
    assert archiver({"seance": "2026-09-30", "moment": "cloture", "ecrit_a": "09h40"},
                    "2026-10-01", tmp_path) is None
    assert _lire(tmp_path, "2026-09-30")["cloture"]["ecrit_a"] == "18h45"


def test_le_rattrapage_d_une_cloture_manquee_s_ecrit(tmp_path):
    # Les passages de 15h45 et 18h45 ont sauté : le lendemain matin écrit la
    # clôture, puisqu'il n'y en avait aucune.
    assert archiver({"seance": "2026-09-30", "moment": "cloture"},
                    "2026-10-01", tmp_path)
    assert "cloture" in _lire(tmp_path, "2026-09-30")


def test_une_lecture_en_seance_n_est_pas_archivee(tmp_path):
    assert archiver({"seance": "2026-09-30", "moment": "en_seance"},
                    "2026-09-30", tmp_path) is None
    assert not (tmp_path / "briefings" / "2026-09-30.json").exists()


def test_l_index_liste_les_seances_de_la_plus_recente(tmp_path):
    for s in ("2026-09-28", "2026-09-30", "2026-09-29"):
        archiver({"seance": s, "moment": "cloture"}, s, tmp_path)
    idx = json.loads((tmp_path / "briefings" / "index.json").read_text(encoding="utf-8"))
    assert idx["seances"] == ["2026-09-30", "2026-09-29", "2026-09-28"]
