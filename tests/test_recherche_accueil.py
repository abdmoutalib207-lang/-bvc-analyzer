"""Recherche de titre sur l'Accueil (13/11/2026).

Audit externe du 12/11/2026 : « la recherche est peu visible ». Mesuré :
l'Accueil, premier écran de chaque visite, n'avait ni champ ni bouton de
recherche ; trouver un titre demandait MENU puis Classement.

Ce qui est vérifié :
1. l'Accueil rend le champ de recherche AVANT la lecture de la séance ;
2. le classement et l'Accueil partagent une seule règle de correspondance ;
3. cette règle, exécutée sous node, ignore accents et casse, et cherche
   dans le symbole interne, le code officiel BVC et le nom.
"""
import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parent.parent
SRC = (RACINE / "terminal.src.html").read_text(encoding="utf-8")


def _ligne(motif: str) -> str:
    m = re.search(r"^" + re.escape(motif) + r".*$", SRC, re.M)
    assert m, f"{motif!r} introuvable"
    return m.group(0)


def test_accueil_commence_par_la_recherche():
    i = SRC.index("const Accueil=")
    corps = SRC[i:i + 6000]
    r = corps.index("<RechercheAccueil ")
    lecture = corps.index("Lecture de la séance")
    assert r < lecture, "la recherche doit précéder la lecture de la séance"


def test_le_champ_ouvre_la_fiche_et_se_nomme():
    i = SRC.index("const RechercheAccueil=")
    corps = SRC[i:SRC.index("const Rangee=", i)]
    assert 'aria-label="Rechercher un titre depuis l\'accueil"' in corps
    assert "ouvrir(sym)" in corps, "un résultat doit ouvrir la fiche directement"
    assert 'e.key==="Enter"' in corps
    assert "slice(0,6)" in corps


def test_une_seule_regle_pour_les_deux_recherches():
    assert SRC.count("correspondTitre(x,search)") == 1, "le classement"
    assert SRC.count("correspondTitre(x,q)") == 1, "l'Accueil"
    # l'ancienne règle du classement, sensible aux accents, a disparu
    assert "(x.name||\"\").toUpperCase().includes(q)" not in SRC


@pytest.mark.skipif(shutil.which("node") is None, reason="node absent")
def test_regle_sous_node():
    code = "\n".join([
        _ligne("const tk="), _ligne("const plier="),
        SRC[SRC.index("const correspondTitre="):SRC.index("};", SRC.index("const correspondTitre=")) + 2],
        """
const rows=[{symbol:"SBS",code_bvc:"SBM",name:"Société des Boissons du Maroc"},
            {symbol:"SLM",code_bvc:"SLF",name:"Salafin"},
            {symbol:"ADH",code_bvc:"ADH",name:"Douja Prom Addoha"}];
const q=s=>rows.filter(x=>correspondTitre(x,s)).map(x=>x.symbol);
console.log(JSON.stringify({societe:q("societe"),slf:q("slf"),slm:q("SLM"),addoha:q("ADDOHA"),vide:q("  "),rien:q("zzz")}));
"""])
    out = subprocess.run(["node", "-e", code], capture_output=True, text=True, check=True).stdout
    r = json.loads(out)
    assert r["societe"] == ["SBS"]
    assert r["slf"] == ["SLM"] and r["slm"] == ["SLM"]
    assert r["addoha"] == ["ADH"]
    assert r["vide"] == ["SBS", "SLM", "ADH"]
    assert r["rien"] == []
