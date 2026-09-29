"""Un seul verdict par titre — le « score canonique », 29/09/2026.

Jusqu'à cette date, `data.json` publiait à côté de la note calculée (`v53`,
`sig`) une « note BVC de référence » (`bvc`), l'écart à cette note (`delta`)
et un « signal communauté » (`sigBvc`). Ni l'une ni l'autre n'étaient
calculées : deux tables saisies à la main le 03/06, jamais rafraîchies, 21
titres sur 80 à 5,00 par défaut. Au 29/09, `sig` et `sigBvc` se
contredisaient sur 38 titres sur 80, et le classement comme la fiche
affichaient « vs BVC » comme s'il s'agissait d'une référence.

Ces tests figent la règle : une note, un signal, une version de formule, lus
à l'identique par l'écran, le bulletin et le journal des scores.
"""

from __future__ import annotations

import ast
import json
import re
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parent.parent
SRC = (RACINE / "terminal.src.html").read_text(encoding="utf-8")
MOTEUR = (RACINE / "update_data.py").read_text(encoding="utf-8")


def test_le_terminal_ne_lit_plus_la_note_figee():
    # ⚠️ Les commentaires CITENT `r.bvc` entre accents graves pour expliquer
    # son retrait : une mention n'est pas une lecture.
    lus = re.findall(r"(?<!`)\br\.(bvc|delta|sigBvc)\b(?!`)", SRC)
    assert not lus, f"le terminal lit encore : {sorted(set(lus))}"
    assert "sigBvc:t.sigBvc" not in SRC and "bvc:t.bvc" not in SRC


def test_le_classement_n_a_plus_de_colonne_bvc_ni_delta():
    heads = re.search(r"const HEADS=\[(.*?)\];", SRC).group(1)
    assert '"BVC"' not in heads and '"Δ"' not in heads
    assert '["bvc","BVC"]' not in SRC and '["delta","DELTA"]' not in SRC
    assert "vs BVC" not in SRC


def _cles_publiees() -> set[str]:
    """Les clés littérales des dictionnaires du moteur contenant `v53`."""
    cles = set()
    for n in ast.walk(ast.parse(MOTEUR)):
        if isinstance(n, ast.Dict):
            k = {c.value for c in n.keys if isinstance(c, ast.Constant)}
            if "v53" in k:
                cles |= k
    return cles


def test_le_moteur_ne_publie_plus_bvc_delta_sigbvc_et_publie_la_version():
    cles = _cles_publiees()
    assert not {"bvc", "delta", "sigBvc"} & cles, {"bvc", "delta", "sigBvc"} & cles
    assert "score_version" in cles
    assert "SIG_BVC" not in re.sub(r"#.*", "", MOTEUR), "SIG_BVC est archivé, plus lu"


def test_la_version_est_declaree_une_seule_fois():
    from bvc_config import SCORE_VERSION
    assert SCORE_VERSION.startswith("v5.3")
    assert 'SCORE_VERSION = "' not in MOTEUR, "la version vit dans bvc_config.py"


def test_le_journal_enregistre_la_version_et_le_meme_signal(tmp_path, monkeypatch):
    from pipeline import score_history as sh
    monkeypatch.setattr(sh, "CHEMIN", tmp_path / "h.json")
    t = {"symbol": "ADH", "v53": 6.1, "sig": "SURVEILLER ★",
         "score_version": "v5.3-essai", "_meta": {}}
    j = sh.enregistrer("2026-09-29", [t])
    s = j["seances"]["2026-09-29"]
    assert s["score_version"] == "v5.3-essai"
    assert sh.valeur(s["tickers"][0], "sig") == "SURVEILLER ★"


def test_deux_versions_dans_un_run_sont_gardees_toutes(tmp_path, monkeypatch):
    """Un mélange est une anomalie : on ne choisit pas en silence."""
    from pipeline import score_history as sh
    monkeypatch.setattr(sh, "CHEMIN", tmp_path / "h.json")
    ts = [{"symbol": "A", "v53": 5, "score_version": "x"},
          {"symbol": "B", "v53": 5, "score_version": "y"}]
    assert sh.enregistrer("2026-09-29", ts)["seances"]["2026-09-29"]["score_version"] == ["x", "y"]


def test_la_penalite_upside_suit_la_note_calculee():
    """« Upside négatif avec signal positif » : le signal positif est désormais
    NOTRE note avant bonus, plus la table saisie le 03/06 (accord R8, 29/09).

    Attendus à la main, pondération 65,28 / 34,72 : 6×0,3472 + 7×0,6528 =
    6,65 ≥ 5,5 → pénalisé ; 4×0,3472 + 5×0,6528 = 4,65 < 5,5 → épargné.
    """
    import update_data as u
    ctx = {"market_status": "CLOSED", "masi_ytd": 0.0}
    haut = u.compute_v53("ZZTEST", 6.0, 7.0, 0, -20.0, dict(ctx))
    bas = u.compute_v53("ZZTEST", 4.0, 5.0, 0, -20.0, dict(ctx))
    assert "-Upside négatif -0.20" in haut["bonus"]
    assert "-Upside négatif -0.20" not in bas["bonus"]
    assert "bvc" not in haut and "delta" not in haut


def test_la_note_figee_n_est_plus_lue():
    assert "BVC_SCORES_BASE" not in re.sub(r"#.*", "", MOTEUR)
