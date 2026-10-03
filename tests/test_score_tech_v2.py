"""Nouveau pilier technique (v2), en mode ombre.

Attendus écrits en dur à partir de la recette (`pipeline/technical/score_v2.py`),
jamais recalculés par la fonction testée.
"""
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE / "pipeline"))

from technical.score_v2 import regime, score_v2, signaux_titre  # noqa: E402


def test_recette_en_tendance():
    assert score_v2(True, False, False, False, None) == 5.0
    assert score_v2(True, True, False, False, None) == 7.0        # + 2 cassure
    assert score_v2(True, True, True, False, None) == 8.5         # + 1,5 surachat
    assert score_v2(True, True, True, True, None) == 9.5          # + 1 pullback


def test_recette_hors_tendance():
    assert score_v2(False, True, True, False, 0.5) == 5.0         # cassure et surachat ignorés
    assert score_v2(False, False, False, True, 0.5) == 4.0        # pullback − 1
    assert score_v2(False, False, False, False, 1.0) == 6.5       # momentum + 1,5
    assert score_v2(False, False, False, False, 0.0) == 3.5       # momentum − 1,5
    assert score_v2(False, False, False, False, None) == 5.0      # momentum inconnu


def _bougies(prix, volumes):
    return [{"d": f"2026-{1 + i // 28:02d}-{1 + i % 28:02d}", "o": p, "h": p, "l": p,
             "c": p, "v": v} for i, (p, v) in enumerate(zip(prix, volumes))]


def test_une_cassure_avec_volume_est_vue():
    prix = [100.0] * 120 + [110.0]
    vol = [1_000] * 120 + [5_000]
    s = signaux_titre(_bougies(prix, vol))
    assert s["cassure_recente"] is True


def test_une_cassure_sans_volume_n_est_pas_vue():
    prix = [100.0] * 120 + [110.0]
    vol = [1_000] * 121
    assert signaux_titre(_bougies(prix, vol))["cassure_recente"] is False


def test_regime_tendance_exige_le_masi_et_la_largeur():
    masi = {f"2026-{1 + i // 28:02d}-{1 + i % 28:02d}": 1000.0 + i for i in range(250)}
    assert regime(masi, [0.1] * 10)["tendance"] is True
    assert regime(masi, [0.1] * 4 + [-0.1] * 6)["tendance"] is False   # 40 % seulement
    baisse = {k: 2000.0 - v for k, v in masi.items()}
    assert regime(baisse, [0.1] * 10)["tendance"] is False


def test_le_mode_ombre_n_entre_pas_dans_la_note():
    """Le moteur publie `score_tech_v2` à côté de l'ancien pilier, sans le lire."""
    code = (RACINE / "update_data.py").read_text(encoding="utf-8")
    debut = code.index("NOUVEAU PILIER TECHNIQUE EN MODE OMBRE")
    bloc = code[debut:code.index("except Exception as _e:", debut)]
    assert "v53" not in bloc and "compute_v53" not in bloc and "score_tech\"]" not in bloc
