"""19/11/2026 — PER non significatif affiché « n.s. » partout, comme MASI Screener.

RDS affichait un PER de 251,9 au classement et sur la fiche, alors que l'onglet
PER le classait déjà « non significatif » (seuil 100x). Une seule règle,
`perNS`, sert désormais les trois écrans. Affichage seulement."""
import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parent.parent
ECRAN = (RACINE / "terminal.src.html").read_text(encoding="utf-8")


def test_une_seule_regle_pour_tous_les_ecrans():
    assert "const PER_MAX_NS=100;" in ECRAN
    # l'onglet PER garde son littéral (extrait seul par test_classement_per) : même valeur
    assert "const SEUIL_NS=100," in ECRAN
    assert ECRAN.count("perTxt(r.pe,r.bpa_12m??r.bpa)") >= 2      # classement + fiche
    assert 'r.pe?.toFixed(1)||"—"' not in ECRAN                    # plus d'affichage brut


@pytest.mark.skipif(not shutil.which("node"), reason="node absent")
def test_la_regle_se_comporte_comme_annonce():
    debut = ECRAN.index("const fmt=(n,d=2)")
    fin = ECRAN.index("const perTxt=", debut)
    fin = ECRAN.index("\n", fin)
    code = ECRAN[debut:fin] + """
const cas=[[251.9,0.68],[100,1],[100.1,1],[18.5,4],[null,-1.85],[null,null],[-3,1]];
console.log(JSON.stringify(cas.map(([p,b])=>perTxt(p,b))));"""
    out = subprocess.run(["node", "-e", code], capture_output=True, text=True, check=True).stdout
    assert json.loads(out) == ["n.s.", "100.0", "n.s.", "18.5", "n.s.", "—", "n.s."]


def test_le_rang_sectoriel_ecarte_un_per_non_significatif():
    from pipeline import rang_sectoriel as rs
    assert rs._valeur({"pe": 251.9}, "pe") is None
    assert rs._valeur({"pe": 100.0}, "pe") == 100.0      # contrôle : le seuil est inclus
    assert rs._valeur({"pb": 251.9}, "pb") == 251.9      # contrôle : seul le PER est concerné
    assert 'if(ratio==="pe"&&perNS(r.pe,r.bpa_12m??r.bpa)) return null;' in ECRAN
