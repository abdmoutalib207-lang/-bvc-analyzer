#!/usr/bin/env python3
"""Le briefing ne retient que les titres RÉELLEMENT cotés dans la séance.

⚠️ LE DÉFAUT — briefing de clôture du 29/09/2026
Il listait en « activité inhabituelle » DAR, M2M et MGL, qui n'avaient pas
coté : BMCE rediffusait leur dernière transaction en la datant du jour
(famille 24 d'ERRORS.md). Leur `prix_asof` portait la séance ; le moteur les
avait pourtant marqués `stale: true`. Le briefing ne regardait que la date.

Les attendus sont écrits à la main, jamais produits par la fonction testée.
"""

from __future__ import annotations

import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

from pipeline import briefing as bf  # noqa: E402

SEANCE = "2026-09-29"


def _t(sym, stale, asof=SEANCE, vol=20, med=1, price=100.0, h52=None, l52=None):
    return {"symbol": sym, "name": sym, "price": price, "chg": 0.0, "vol": vol,
            "h52w": h52, "l52w": l52,
            "_meta": {"prix_asof": asof, "stale": stale, "vol_median20": med,
                      "n_candles": 400}}


def test_un_titre_perime_n_est_pas_cote():
    assert bf.reellement_cote(_t("DAR", True), SEANCE) is False
    assert bf.reellement_cote(_t("SGTM", False), SEANCE) is True
    # ⚠️ Sans drapeau, on ne présume pas la péremption : c'est la date qui juge.
    x = _t("ARD", False)
    del x["_meta"]["stale"]
    assert bf.reellement_cote(x, SEANCE) is True
    assert bf.reellement_cote(_t("ARD", False, asof="2026-09-28"), SEANCE) is False


def test_la_rediffusion_du_29_09_ne_passe_plus_en_volume_inhabituel():
    """Reprise des trois lignes du 29/09 : DAR 20 titres pour une médiane de
    1 (20×), M2M 51 pour 9, MGL 20 pour 5 — toutes `stale`. Seul ARD, réellement
    coté (28 035 pour 789), doit rester."""
    titres = [_t("DAR", True, vol=20, med=1), _t("M2M", True, vol=51, med=9),
              _t("MGL", True, vol=20, med=5),
              _t("ARD", False, vol=28035, med=789)]
    v = bf.volumes_inhabituels(titres, SEANCE)
    assert [x["symbol"] for x in v] == ["ARD"]


def test_un_cours_rediffuse_n_est_pas_un_extreme_de_douze_mois():
    titres = [_t("NEJ", True, price=5621.0, h52=5621.0, l52=4000.0),
              _t("IAM", False, price=120.0, h52=119.0, l52=90.0)]
    e = bf.extremes_annuels(titres, SEANCE)
    assert [x["symbol"] for x in e["plus_hauts"]] == ["IAM"]
