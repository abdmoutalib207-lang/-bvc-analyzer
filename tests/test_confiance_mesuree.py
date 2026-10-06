"""Confiance 0–5 sans le corpus gelé, et sociétés qui cotent sans comptes.

06/10/2026 — chasse aux échecs silencieux : deux points de confiance lisaient
le corpus WhatsApp arrêté au 02/07 (32 titres bloqués à 2/5), et IB Maroc,
sans compte déposé depuis 2023 et en redressement judiciaire, affichait 5,2 et
ATTENDRE sans un mot. Attendus écrits à la main.
"""
import json
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

import update_data as ud  # noqa: E402
from bvc_config import TICKERS_ALL, sans_comptes  # noqa: E402


def test_comptes_deposes_selon_la_source_du_bpa():
    assert ud._comptes_deposes({"bpa": 73.39, "source": "resultats_officiels"})
    assert ud._comptes_deposes({"bpa": 5.0, "source": "RFA 2025 AMMC (p.17)"})
    assert not ud._comptes_deposes({"bpa": 104.21, "source": "casablancabourse_derive"})
    assert not ud._comptes_deposes({"bpa": 1.1, "source": None})      # STK, MDP
    assert not ud._comptes_deposes(None)


def test_le_corpus_ne_donne_plus_de_point():
    """Mêmes données, corpus riche ou vide : même confiance."""
    riche = {"mentions": 5000, "win": 70}
    vide = {"mentions": 0, "win": None}
    a = ud._meta_ticker("ATW", "cdg", ud.IDB_ASOF or "2026-10-06", riche, None,
                        comptes_deposes=True)["confidence"]
    b = ud._meta_ticker("ATW", "cdg", ud.IDB_ASOF or "2026-10-06", vide, None,
                        comptes_deposes=True)["confidence"]
    assert a == b


def test_les_comptes_deposes_comptent_un_point():
    m1 = ud._meta_ticker("ATW", "cdg", "2026-10-06", {}, None, comptes_deposes=True)
    m0 = ud._meta_ticker("ATW", "cdg", "2026-10-06", {}, None, comptes_deposes=False)
    assert m1["confidence"] == m0["confidence"] + 1


def test_ib_maroc_sans_comptes_est_plafonne_et_motive():
    c = sans_comptes("IBM")
    assert c["dernier_depot"] == "2023-10-31" and "redressement" in c["motif"]
    m = ud._meta_ticker("IBM", "cdg", "2026-10-06", {}, None, comptes_deposes=True)
    assert m["confidence"] <= 1 and m["comptes_absents"]["dernier_depot"] == "2023-10-31"
    assert ud._meta_ticker("ATW", "cdg", "2026-10-06", {}, None)["comptes_absents"] is None


def test_bpa_json_ne_contient_que_nos_tickers():
    bpa = json.loads((RACINE / "bpa.json").read_text(encoding="utf-8"))
    assert set(bpa) <= set(TICKERS_ALL), sorted(set(bpa) - set(TICKERS_ALL))
