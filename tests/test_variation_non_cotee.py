"""Un titre dont le cours ne date pas de la dernière séance n'affiche pas
« 0,00 % » mais « n.c. » (constat B2, 14/10/2026 ; R9).

Le moteur publie `chg = 0.0` pour ces titres et le briefing le neutralise
déjà (`reellement_cote`). Le terminal, lui, l'affichait comme une stabilité
observée, et la carte des secteurs comptait ces zéros dans sa moyenne.
"""
from pathlib import Path

SRC = (Path(__file__).resolve().parent.parent / "terminal.src.html").read_text(encoding="utf-8")


def test_variation_nulle_pour_un_cours_perime():
    assert "const varSeance=r=>meta(r).stale?null:r.chg;" in SRC


def test_classement_et_bandeau_affichent_non_cote():
    assert SRC.count("varSeance(r)==null?NON_COTE:") == 2


def test_moyenne_sectorielle_ignore_les_titres_non_cotes():
    assert "rs.map(varSeance).filter(v=>v!=null)" in SRC
    assert "rs.reduce((s,r)=>s+(r.chg||0),0)/rs.length" not in SRC


def test_tri_par_variation_range_les_non_cotes_en_fin():
    assert 'if(sort==="var") return (varSeance(b)??-Infinity)' in SRC
