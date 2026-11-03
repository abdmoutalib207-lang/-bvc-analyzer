#!/usr/bin/env python3
"""Les séances de suspension apparaissent sur le graphique, sans bougie.

Demande d'Abd Moutalib (03/11/2026) : « sur le graphique il faut afficher les
jours même si suspendu ». L'axe du graphique (Lightweight Charts) ne compte que
les dates qu'une série porte ; un titre suspendu n'a pas de bougie, et R11
interdit d'en inventer. Le moteur publie donc `_meta.suspensions` — chaque
période du registre avec les séances où LE MARCHÉ a coté — et le terminal les
marque d'une bande grise sur une échelle cachée.
"""
import json
import re
import sys
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))
sys.path.insert(0, str(RACINE / "tests"))

from bvc_config import SUSPENSIONS  # noqa: E402
from conftest import chemin_data_json  # noqa: E402
from pipeline.seance import suspensions_publiees  # noqa: E402

CAL = ["2026-10-28", "2026-10-29", "2026-10-30", "2026-11-02", "2026-11-03"]


def test_les_seances_couvertes_sont_celles_du_marche():
    p = suspensions_publiees(SUSPENSIONS["MNG"], CAL, premiere="2023-01-02", jusqu_au="2026-11-03")
    assert len(p) == 1 and p[0]["seances"] == ["2026-10-30", "2026-11-02"]
    assert p[0]["depuis"] == "2026-10-30" and p[0]["reprise"] == "2026-11-03"
    assert "AV-2026-138" in p[0]["source"]


def test_rien_avant_la_premiere_bougie_ni_apres_la_date_d_analyse():
    assert suspensions_publiees(SUSPENSIONS["MNG"], CAL, premiere="2026-11-01")[0]["seances"] == ["2026-11-02"]
    assert suspensions_publiees(SUSPENSIONS["MNG"], CAL, jusqu_au="2026-10-30")[0]["seances"] == ["2026-10-30"]
    assert suspensions_publiees(SUSPENSIONS["MNG"], CAL, jusqu_au="2026-10-29") == []
    # Sans bougie (DIS, DLM) : la période est publiée, sans séance à marquer.
    assert suspensions_publiees(SUSPENSIONS["DIS"], CAL, premiere="9999-12-31")[0]["seances"] == []


def test_un_jour_ferie_n_est_pas_une_seance_de_suspension():
    """Le calendrier vient des chandelles du marché : un férié n'y figure pas,
    il n'est donc pas marqué (14/08/2026 pendant la suspension de CMT)."""
    cal = ["2026-08-13", "2026-08-17"]
    s = suspensions_publiees(SUSPENSIONS["CMT"], cal)[0]["seances"]
    assert s == ["2026-08-13", "2026-08-17"]


def test_le_moteur_publie_le_champ():
    src = (RACINE / "update_data.py").read_text(encoding="utf-8")
    assert '["suspensions"] = _susp_pub(' in src
    assert "suspendu_le=date_analyse()" in src, (
        "le risque doit juger la suspension à la date d'analyse, pas à la veille")


def test_le_fichier_publie_porte_les_seances_de_suspension():
    f = chemin_data_json()
    if not f.exists():
        pytest.skip("data.json absent")
    titres = {t["symbol"]: t for t in json.loads(f.read_text(encoding="utf-8"))["tickers"]}
    if "suspensions" not in (titres.get("MNG", {}).get("_meta") or {}):
        pytest.skip("fichier publié antérieur au champ `_meta.suspensions`")
    for t in SUSPENSIONS:
        if t in titres:
            assert isinstance(titres[t]["_meta"].get("suspensions"), list), f"{t} : champ absent"
    mng = titres["MNG"]["_meta"]["suspensions"][0]["seances"]
    assert mng[:2] == ["2026-10-30", "2026-11-02"]
    serie = {b["d"] for b in json.loads((RACINE / "pipeline" / "candles" / "MNG.json").read_text(encoding="utf-8"))}
    assert not serie & set(mng), "une séance de suspension porte une bougie (R11)"


def test_le_terminal_marque_l_axe_sans_inventer_de_cours():
    s = (RACINE / "terminal.src.html").read_text(encoding="utf-8")
    assert "(r._meta||{}).suspensions" in s, "le terminal ne lit pas _meta.suspensions"
    assert "Suspendu (AMMC/Bourse)" in s, "la légende ne nomme pas la suspension"
    assert re.search(r'addHistogramSeries\(\{priceScaleId:"susp"', s), "pas de bande sur échelle cachée"
    # Les deux cadres (cours et MACD) portent les mêmes créneaux : axes alignés.
    assert "bandeSusp(main);" in s and "bandeSusp(macdChart);" in s
    # Les chandeliers restent les seules bougies : `cs.setData(lwData)`, où
    # lwData ne vient que des chandelles.
    assert "cs.setData(lwData);" in s
    # La vue, la légende et les figures passent par l'axe commun.
    assert "vueEntiere(main,nAxe)" in s and "const dates=axe.length?axe:" in s
