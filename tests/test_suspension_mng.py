#!/usr/bin/env python3
"""Managem (MNG, MASI 1) — suspendu du 30/10 au 02/11/2026, reprise le 03/11.

CE QUI S'EST PASSÉ
──────────────────
La Bourse a suspendu Managem le 30/10/2026 « à la demande de l'AMMC [...] en
attente de publication d'informations importantes » (avis AV-2026-138). Le
communiqué de Managem du 02/11 dit l'avoir sollicitée après des rumeurs nées
de la révision du MASI, ne déclare « aucun événement significatif » et demande
la reprise au 03/11 ; l'avis AV-2026-141 du 03/11 la prononce.

Le registre ne portait pas MNG : le fichier publié le 02/11 donnait
« ACHETER ★★ » sur un titre qui ne cotait pas, avec un cours du 29/10 marqué
`stale` — exactement l'incident CMT du 09/09 (tests/test_suspension.py).

⚠️ CE N'EST PAS UNE OPÉRATION SUR CAPITAL (R11) : pas de nouvelle référence de
cours, nombre d'actions inchangé. Le jour de la reprise, la variation se calcule
sur la dernière clôture cotée et R10 s'applique sans exception — à l'inverse de
CMT, dont la référence avait été remise à 2 217 DH.

Aucun test ne touche le réseau : les pièces sont lues dans datasets/pieces_ammc/.
"""
import hashlib
import importlib.util
import json
import re
import sys
from pathlib import Path

import pandas as pd
import pytest

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

from bvc_config import SPLITS, SUSPENSIONS, est_suspendu  # noqa: E402


@pytest.fixture(scope="module")
def moteur():
    spec = importlib.util.spec_from_file_location("ud_mng", RACINE / "update_data.py")
    m = importlib.util.module_from_spec(spec)
    sys.modules["ud_mng"] = m
    spec.loader.exec_module(m)
    return m


def _mng():
    assert "MNG" in SUSPENSIONS, "la suspension du 30/10/2026 (AV-2026-138) n'est pas inscrite"
    assert len(SUSPENSIONS["MNG"]) == 1
    return SUSPENSIONS["MNG"][0]


# ── le registre ──────────────────────────────────────────────────────────

def test_les_dates_sont_celles_des_avis():
    p = _mng()
    assert p["depuis"] == "2026-10-30"
    assert p["reprise"] == "2026-11-03"
    assert "AV-2026-138" in p["source"]
    assert "AV-2026-141" in p["reprise_source"]


def test_la_reference_n_est_pas_remise_a_neuf():
    """Aucune pièce ne fixe de nouvelle référence : y en inscrire une ferait
    calculer la variation de la reprise sur un nombre inventé (R10, 2e préc.)."""
    p = _mng()
    assert "reference_impliquee" not in p
    assert "cours_de_reprise" not in p, "cours de reprise non constaté sur une séance close"


def test_le_resolveur_borne_la_periode():
    assert est_suspendu("MNG", "2026-10-29") is None, "le 29/10 Managem cotait (5 297 titres)"
    assert est_suspendu("MNG", "2026-10-30") is not None
    assert est_suspendu("MNG", "2026-11-02") is not None
    assert est_suspendu("MNG", "2026-11-03") is None, "le jour de la reprise, le titre cote"


# ── les pièces ───────────────────────────────────────────────────────────

_PIECES = [("piece", "piece_sha256", "citations"),
           ("reprise_piece", "reprise_piece_sha256", "reprise_citations"),
           ("communique_piece", "communique_piece_sha256", "communique_citations")]


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s.replace("’", "'")).strip()


@pytest.mark.parametrize("cle,cle_sha,cle_cit", _PIECES)
def test_chaque_piece_est_archivee_empreintee_et_citee(cle, cle_sha, cle_cit):
    p = _mng()
    f = RACINE / p[cle]
    assert f.exists(), f"pièce absente : {p[cle]}"
    vu = hashlib.sha256(f.read_bytes()).hexdigest()
    assert vu == p[cle_sha], f"{f.name} n'est plus la pièce citée ({vu[:16]}…)"
    pdfplumber = pytest.importorskip("pdfplumber")
    with pdfplumber.open(f) as pdf:
        pages = [_norm(pg.extract_text() or "") for pg in pdf.pages]
    assert p[cle_cit], f"{cle} : aucune citation"
    for c in p[cle_cit]:
        assert _norm(c["texte"]) in pages[c["page"] - 1], (
            f"{f.name} p.{c['page']} : citation introuvable « {c['texte'][:60]}… »")


def test_le_nombre_d_actions_n_a_pas_bouge():
    """R11 : le test qui sépare split et simple suspension est le NOMBRE
    D'ACTIONS. Liste officielle des émetteurs (20/10) : 118 646 760, celui du
    split du 27/07 — et aucun split postérieur au registre."""
    em = json.loads((RACINE / "datasets" / "bourse_emetteurs.json").read_text(encoding="utf-8"))
    lignes = [x for x in em["enregistrements"]
              if x.get("code") == "MNG" and x.get("type_instrument") == "Actions"]
    assert len(lignes) == 1 and lignes[0]["nombre_titres"] == 118646760
    assert all(s["date"] <= "2026-07-27" for s in SPLITS.get("MNG", []))


# ── l'effet sur le moteur ────────────────────────────────────────────────

def test_le_signal_est_suspendu_pendant_la_suspension(moteur, monkeypatch):
    """Rejeu de la publication du 02/11 : « ACHETER ★★ » devient SUSPENDU."""
    monkeypatch.setenv("BVC_DATE_ANALYSE", "2026-11-02")
    assert moteur._signal_publie("MNG", "ACHETER ★★", None, None) == ("SUSPENDU", None)


def test_a_la_reprise_le_signal_revient_sans_abstention(moteur, monkeypatch):
    """Règle du 03/11/2026 (accord R8/R11) : sans référence remise à neuf au
    registre, la reprise ne déclenche ni `reprise_recente` ni neutralisation —
    MNG retrouve son signal dès qu'il cote."""
    monkeypatch.setenv("BVC_DATE_ANALYSE", "2026-11-03")
    for dates in (["2026-10-28", "2026-10-29"], ["2026-10-29", "2026-11-03"]):
        serie = pd.DataFrame({"d": dates, "c": [1490.0, 1390.0]})
        assert moteur.reprise_trop_recente("MNG", serie) is None
    assert moteur._signal_publie("MNG", "ACHETER ★★", None, None) == ("ACHETER ★★", None)


def test_la_regle_de_reprise_ne_vise_que_la_reference_remise_a_neuf():
    from bvc_config import derniere_reprise_remise_a_neuf
    from pipeline.risque import derniere_reprise
    assert derniere_reprise_remise_a_neuf("MNG") is None
    assert derniere_reprise(SUSPENSIONS["MNG"]) is None, "la fenêtre de risque ne doit pas repartir"
    # CMT, reprise à 2 217 DH après OPA : la règle reste entière.
    assert derniere_reprise_remise_a_neuf("CMT") == "2026-09-16"
    assert derniere_reprise(SUSPENSIONS["CMT"]) == "2026-09-16"


def test_un_rejeu_pendant_la_suspension_ignore_la_reprise_future(moteur, monkeypatch):
    """Incohérence de rejeu relevée le 03/11 : `suspendu` ET `reprise_recente`
    publiés ensemble. La reprise se juge à la date d'analyse (cas CMT, le seul
    à référence remise à neuf)."""
    from bvc_config import derniere_reprise_remise_a_neuf
    assert derniere_reprise_remise_a_neuf("CMT", "2026-09-15") is None
    monkeypatch.setenv("BVC_DATE_ANALYSE", "2026-09-15")
    serie = pd.DataFrame({"d": ["2026-07-15", "2026-07-16"], "c": [4400.0, 4501.0]})
    assert moteur.reprise_trop_recente("CMT", serie) is None
    monkeypatch.setenv("BVC_DATE_ANALYSE", "2026-09-16")
    assert moteur.reprise_trop_recente("CMT", serie) == 0


def test_la_variation_sans_chg_source_ne_leve_pas(moteur, monkeypatch):
    """`chg=None` faisait lever le format du journal de `recalculer_variation`."""
    monkeypatch.setenv("BVC_DATE_ANALYSE", "2026-11-03")
    serie = pd.DataFrame({"d": ["2026-10-28", "2026-10-29"], "c": [1512.0, 1490.0]})
    assert moteur.recalculer_variation("MNG", 1390.0, None, serie, "2026-11-03", "2026-11-03") == -6.71


def test_a_la_reprise_r10_porte_sur_la_derniere_cloture(moteur, monkeypatch):
    """Pas de référence remise à neuf : la variation du 03/11 se calcule sur la
    clôture du 29/10 (1 490), et un écart au-delà de ±10 % reste rejeté."""
    monkeypatch.setenv("BVC_DATE_ANALYSE", "2026-11-03")
    assert moteur.reference_de_reprise("MNG", "2026-11-03") is None
    serie = pd.DataFrame({"d": ["2026-10-28", "2026-10-29"], "c": [1512.0, 1490.0]})
    v = moteur.recalculer_variation("MNG", 1550.0, 0.0, serie, "2026-11-03", "2026-11-03")
    assert v == round((1550 - 1490) / 1490 * 100, 2)
    assert moteur.recalculer_variation("MNG", 1700.0, 0.0, serie, "2026-11-03", "2026-11-03") == 0.0


def test_aucune_chandelle_pendant_la_suspension():
    serie = json.loads((RACINE / "pipeline" / "candles" / "MNG.json").read_text(encoding="utf-8"))
    pendant = [b["d"] for b in serie if "2026-10-30" <= b["d"] < "2026-11-03"]
    assert not pendant, f"chandelle(s) fantôme(s) : {pendant}"
    avant = [b for b in serie if b["d"] <= "2026-10-29"]
    assert avant[-1]["d"] == "2026-10-29" and avant[-1]["v"] == 5297


def test_l_audit_reconnait_le_plafond_de_reprise():
    """Une reprise à référence remise à neuf (cas CMT) plafonne la confiance à 1
    pendant 20 séances : l'audit de la chaîne doit lire ce plafond dans
    `_meta.reprise_recente` au lieu de le déclarer « inexpliqué » — et le
    déclarer encore si le drapeau manque. (Constaté le 03/11 avec MNG, avant la
    règle qui l'exempte de cette abstention.)"""
    sys.path.insert(0, str(RACINE / "tools"))
    import audit_chaine as A
    g = [{"critere": f"g{i}", "ok": i != 0} for i in range(5)]
    t = {"_meta": {"confidence": 1, "garanties": g, "reprise_recente": True,
                   "echange_median_dh": 11_503_636}, "note_fond": {"note": 7.2}}
    codes = [x["controle"] for x in A.controler_confiance("MNG", t, set())]
    assert "confiance.plafond_inexplique" not in codes
    t["_meta"]["reprise_recente"] = False
    codes = [x["controle"] for x in A.controler_confiance("MNG", t, set())]
    assert "confiance.plafond_inexplique" in codes


def test_le_risque_juge_la_suspension_a_la_date_d_analyse():
    """Pendant la séance du 03/11, le risque s'arrête à la veille (02/11), où MNG
    était suspendu : jugée à cette date, la suspension vidait son bloc toute la
    journée de la reprise. Jugée à la date d'analyse, il est mesuré."""
    from pipeline.risque import mesurer_cote
    jours = ["2026-10-28", "2026-10-29", "2026-10-30", "2026-11-02"]
    marche = {f"T{i:02d}": [{"d": d, "o": 10, "h": 10, "l": 10, "c": 10, "v": 5} for d in jours]
              for i in range(25)}
    marche["MNG"] = [{"d": d, "o": 1500, "h": 1500, "l": 1500, "c": 1500, "v": 9} for d in jours[:2]]
    veille = mesurer_cote(marche, {}, ["MNG"], jusqu_au="2026-11-02")["MNG"]
    assert (veille["motif"] or {}).get("code") == "suspendu"
    jour = mesurer_cote(marche, {}, ["MNG"], jusqu_au="2026-11-02", suspendu_le="2026-11-03")["MNG"]
    assert (jour["motif"] or {}).get("code") != "suspendu"
    encore = mesurer_cote(marche, {}, ["MNG"], jusqu_au="2026-11-02", suspendu_le="2026-11-02")["MNG"]
    assert encore["motif"]["code"] == "suspendu"
