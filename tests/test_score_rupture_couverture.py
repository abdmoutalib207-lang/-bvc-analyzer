"""Audit externe du 12/11/2026, point 5 : la portée du score se lit dans le classement.

- T2S : 80,6/100 avec 90 % de couverture (MM200 indisponible, points ramenés à
  100) — la couverture n'était visible qu'au survol.
- CMT : 100 % de couverture alors que ses MM50 et MM200 incorporent des cours
  d'avant la reprise du 16/09/2026, où l'AMMC a remis la référence à neuf.
La mention ne change aucun point du score (R8).
"""
import json
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

from pipeline import score_bvc as sb  # noqa: E402

ECRAN = (RACINE / "terminal.src.html").read_text(encoding="utf-8")


def _b(dates):
    return [{"d": d, "c": 100.0, "v": 10} for d in dates]


def test_rupture_vient_du_registre_et_compte_les_seances():
    avant = [f"2026-06-{j:02d}" for j in range(1, 30)]
    apres = [f"2026-09-{j:02d}" for j in range(16, 31)] + [f"2026-10-{j:02d}" for j in range(1, 31)]
    r = sb.rupture_de_reference("CMT", _b(avant + apres))
    assert r == {"reprise": "2026-09-16", "seances": len(apres), "moyennes": ["MM50", "MM200"]}


def test_registre_illisible_se_signale_sans_casser_le_score(monkeypatch, capsys):
    # R5 : un registre qui ne s'importe plus ne doit pas effacer la mention de
    # CMT en silence. sys.modules[...] = None fait lever ImportError à l'import.
    monkeypatch.setitem(sys.modules, "bvc_config", None)
    monkeypatch.setattr(sb, "_RUPTURE_SIGNALEE", [])
    assert sb.rupture_de_reference("CMT", _b(["2026-09-16"])) is None
    assert sb.rupture_de_reference("ADH", _b(["2026-09-16"])) is None
    err = capsys.readouterr().err
    assert "rupture_de_reference" in err and "CMT" in err and "SUSPENSIONS" in err
    assert err.count("rupture_de_reference") == 1, "un seul message par run, pas un par titre"


def test_une_suspension_sans_reference_neuve_n_est_pas_une_rupture():
    # MNG : suspension de deux séances (rumeurs), référence inchangée
    assert sb.rupture_de_reference("MNG", _b(["2026-11-03", "2026-11-04"])) is None
    assert sb.rupture_de_reference("ATW", _b(["2026-11-03"])) is None


def test_la_mention_ne_change_aucun_point():
    data = json.loads((RACINE / "data.json").read_text(encoding="utf-8"))
    cmt = next(t for t in data["tickers"] if t["symbol"] == "CMT")
    bg = json.loads((RACINE / "pipeline" / "candles" / "CMT.json").read_text(encoding="utf-8"))
    bg = bg.get("candles", bg) if isinstance(bg, dict) else bg
    s = sb.score_titre_bvc(cmt, bg)
    mm = s["facteurs"]["moyennes_mobiles"]
    assert mm["rupture"]["moyennes"] == ["MM50", "MM200"]
    assert "référence remise à neuf" in mm["mesure"]
    assert s["valeur"] == cmt["score_bvc"]["valeur"]


def test_le_classement_montre_couverture_et_rupture():
    assert "couv. ${s.couverture_pct} %" in ECRAN
    assert '"⚠ rupture"' in ECRAN
