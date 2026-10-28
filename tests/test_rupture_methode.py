"""Ruptures de méthode comptable (registre RUPTURES_METHODE, 27/10/2026).

  · chaque rupture porte sa pièce (url, sha256, pages, citations) et dit ce qui
    n'est plus comparable ;
  · `_meta.rupture_methode` la publie pour ces titres, None ailleurs ;
  · AUCUN effet sur la note : le registre n'est lu ni par la note par métier
    ni par la grille actuelle ;
  · ADI est examiné et NON inscrit (RFA 2025 : état des changements de
    méthodes « NÉANT ») — ne pas l'ajouter sans pièce.
"""
import re
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

import bvc_config as C  # noqa: E402

CHAMPS = ("date_effet", "premier_exercice", "nature", "application", "non_comparable")


def test_chaque_rupture_porte_sa_piece_et_ce_qui_n_est_plus_comparable():
    assert C.RUPTURES_METHODE, "registre vide"
    for t, liste in C.RUPTURES_METHODE.items():
        assert t in C.TICKERS_ALL, t
        for e in liste:
            assert all(e.get(k) for k in CHAMPS), t
            assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", e["date_effet"]), t
            src = e["source"]
            assert src["url"].startswith("https://") and src["fichier"] in src["url"], t
            assert re.fullmatch(r"[0-9a-f]{64}", src["sha256"]), t
            assert src["citations"] and all(isinstance(c["page"], int) and len(c["texte"]) > 30
                                            for c in src["citations"]), t


def test_les_ruptures_etablies_le_27_10():
    assert set(C.RUPTURES_METHODE) == {"RDS", "WAF", "SAF"}
    assert "ADI" not in C.RUPTURES_METHODE        # « NÉANT » au RFA 2025 p.32 : rien à inscrire
    assert C.RUPTURES_METHODE["RDS"][0]["date_effet"] == "2025-01-01"
    assert "IFRS 17" in C.RUPTURES_METHODE["WAF"][0]["nature"]
    assert "IFRS 17" in C.RUPTURES_METHODE["SAF"][0]["nature"]


def test_meta_publie_la_rupture_et_rien_ailleurs():
    import update_data as ud
    m = ud._meta_ticker("RDS", "cdg", "2026-10-27", {}, None)["rupture_methode"]
    assert m[0]["date_effet"] == "2025-01-01" and m[0]["pages"] == [16, 17]
    assert m[0]["source"].endswith("RDS_RFA_2025.pdf") and m[0]["non_comparable"]
    assert ud._meta_ticker("ATW", "cdg", "2026-10-27", {}, None)["rupture_methode"] is None


def test_aucun_effet_sur_la_note():
    # Le registre n'est lu que pour `_meta` : ni la note par métier, ni la grille.
    for f in ("pipeline/smart_money/fond_score_sectoriel.py", "pipeline/smart_money/fond_score.py"):
        assert "RUPTURES_METHODE" not in (RACINE / f).read_text(encoding="utf-8")
        assert "rupture_methode" not in (RACINE / f).read_text(encoding="utf-8")
    src = (RACINE / "update_data.py").read_text(encoding="utf-8")
    assert src.count("rupture_methode(") == 1


def test_le_terminal_affiche_la_rupture_depuis_meta():
    src = (RACINE / "terminal.src.html").read_text(encoding="utf-8")
    assert "rupture_methode" in src and "Changement de méthode comptable" in src
