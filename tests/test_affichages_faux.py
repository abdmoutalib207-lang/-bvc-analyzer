"""19/11/2026 — Affichages faux du terminal (inventaire du bruit, lot 1.1).

Huit formats qui disaient autre chose que le chiffre. Affichage seulement :
ni donnée, ni Score BVC, ni texte d'avertissement touchés.

1. Stochastique au-dessus de 80 écrit « survente » (le contraire).
2. En tête de fiche, le code seul : ni nom de société, ni secteur.
3. Actualités de la fiche : le même article deux fois (IAM : 2 doublons sur 6).
4. Bandeau : une variation nulle s'écrit « —0.00% », lu −0,00 %.
5. Classement : un dividende non relevé s'écrit « —% ».
6. Fiche : un dividende relevé à 0 s'écrit « — » (réservé à « non relevé »),
   et son rang dit « −100 % vs secteur ».
7. Accueil : « Tout voir › » des hausses / baisses ouvre le classement trié par
   Score BVC.
8. Menu : « Les 80 titres ».

Les fonctions de format sont pures : on les exécute sous node, extraites telles
quelles du source, comme test_per_non_significatif.py.
"""
import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parent.parent
ECRAN = (RACINE / "terminal.src.html").read_text(encoding="utf-8")
NODE = pytest.mark.skipif(not shutil.which("node"), reason="node absent")


def _bloc_formats():
    """Le bloc des fonctions de format, de `zoneStoch` à `dedoublonnerArticles`."""
    debut = ECRAN.index("const zoneStoch=")
    fin = ECRAN.index("const dedoublonnerArticles=", debut)
    return ECRAN[debut:ECRAN.index("\n", fin)]


def _node(code):
    out = subprocess.run(["node", "-e", code], capture_output=True, text=True, check=True).stdout
    return json.loads(out)


def _composant(nom):
    """Le texte d'un composant, de sa déclaration à la suivante."""
    debut = ECRAN.index(f"const {nom}=")
    fin = re.compile(r"\n(const|function) [A-Za-z]").search(ECRAN, debut + 10).start()
    return ECRAN[debut:fin]


# ── 1. Stochastique ─────────────────────────────────────────────────────────
@NODE
def test_stochastique_dit_la_zone_dans_le_bon_sens():
    cas = [100, 94.84, 80.1, 80, 50, 20, 19.9, 0, None]
    res = _node(_bloc_formats() + f"\nconsole.log(JSON.stringify({json.dumps(cas)}.map(zoneStoch)));")
    assert res == ["zone haute", "zone haute", "zone haute", "neutre", "neutre",
                   "neutre", "zone basse", "zone basse", ""]


def test_stochastique_sans_vocabulaire_interpretatif():
    assert 'r.stoch_k>80?"survente"' not in ECRAN
    assert "{zoneStoch(r.stoch_k)}" in _composant("Detail")
    ligne = next(l for l in ECRAN.splitlines() if l.startswith("const zoneStoch="))
    assert "survente" not in ligne and "surachat" not in ligne


# ── 2. Nom et secteur en tête de fiche ──────────────────────────────────────
def test_fiche_porte_le_nom_et_le_secteur_sous_le_code():
    d = _composant("Detail")
    i_code = d.index('className="fiche-cours"')
    i_id = d.index('className="fiche-identite"')
    i_ess = d.index("<EnTeteEssentiel")
    assert i_code < i_id < i_ess, "l'identité se lit sous la ligne du code, avant l'essentiel"
    bloc = d[i_id:i_ess]
    assert "r.name" in bloc and "r.sector" in bloc


# ── 3. Actualités dédoublonnées ─────────────────────────────────────────────
@NODE
def test_actualites_meme_titre_normalise_une_seule_entree():
    arts = [
        {"id": 1, "title": "Maroc Telecom: Mohamed Benchaaboun reçu par le Premier ministre mauritanien"},
        {"id": 2, "title": "Maroc Telecom: Mohamed Benchaaboun reçu par le Premier ministre mauritanien"},
        {"id": 3, "title": "Guinée: Maroc Telecom en pole position…"},
        {"id": 4, "title": "  GUINEE : Maroc  Telecom en pole position ! "},
        {"id": 5, "title": "Maroc Telecom : avis de report"},
        {"id": 6, "title": ""},
        {"id": 7, "title": None},
    ]
    res = _node(_bloc_formats() + f"\nconsole.log(JSON.stringify(dedoublonnerArticles({json.dumps(arts)}).map(a=>a.id)));")
    # la première occurrence est gardée ; un titre vide n'est pas un doublon
    assert res == [1, 3, 5, 6, 7]


def test_actualites_dedoublonnees_avant_la_coupe_a_six():
    tn = _composant("TickerNews")
    assert re.search(r"dedoublonnerArticles\([^;]*\.includes\(sym\)\)\)\.slice\(0,6\)", tn), \
        "le dédoublonnage doit précéder slice(0,6), sinon un doublon prend la place d'un article"


# ── 4. Bandeau : variation nulle ────────────────────────────────────────────
@NODE
def test_bandeau_variation_nulle_sans_tiret():
    res = _node(_bloc_formats() + "\nconsole.log(JSON.stringify([0,-0,1.2,-0.54].map(varBandeau)));")
    assert res == ["0,00 %", "0,00 %", "▲1.20%", "▼0.54%"]


def test_bandeau_utilise_le_format():
    tape = _composant("TickerTape")
    assert "varBandeau(r.chg)" in tape
    assert ':"—"}{Math.abs(r.chg||0)' not in tape


# ── 5. Classement : dividende absent ────────────────────────────────────────
@NODE
def test_classement_dividende_absent_et_nul():
    res = _node(_bloc_formats() + "\nconsole.log(JSON.stringify([null,undefined,0,4.49].map(divClassement)));")
    assert res == ["—", "—", "0.0%", "4.5%"]


def test_classement_utilise_le_format():
    assert '{r.div?.toFixed(1)||"—"}%' not in ECRAN
    assert "{divClassement(r.div)}</td>" in _composant("Ranking")


# ── 6. Fiche : dividende relevé à zéro ──────────────────────────────────────
@NODE
def test_fiche_dividende_zero_n_est_pas_non_releve():
    res = _node(_bloc_formats() + "\nconsole.log(JSON.stringify([0,null,undefined,3.13].map(divFiche)));")
    assert res == ["0 %", "—", "—", "3.1%"]


def test_fiche_dividende_zero_sans_rang_secteur():
    d = _composant("Detail")
    assert '["Dividende",divFiche(r.div),' in d
    i_rang = d.index("const e=(r.rang_secteur||{})[ratio];")
    i_garde = d.index('if(ratio==="div"&&+r.div===0) return null;', i_rang)
    assert i_garde < d.index("vs secteur", i_rang), "la garde précède l'affichage du rang"


# ── 7. Accueil : « Tout voir » dans l'ordre de la rangée ────────────────────
def test_tout_voir_ouvre_le_classement_trie_par_variation():
    acc = _composant("Accueil")
    assert re.search(r'<Rangee titre="Plus fortes hausses"[^>]*tri="var"[^>]*setSort=\{setSort\}', acc)
    assert re.search(r'<Rangee titre="Plus fortes baisses"[^>]*tri="var_asc"[^>]*setSort=\{setSort\}', acc)
    assert "onClick={()=>{if(tri&&setSort)setSort(tri);setTab(vers);}}" in _composant("Rangee")
    assert re.search(r"<Accueil [^\n]*setSort=\{setSort\}/>", ECRAN)


@NODE
def test_tri_croissant_par_variation_non_cotes_en_fin():
    rk = _composant("Ranking")
    debut = rk.index("[...filtered].sort((a,b)=>{") + len("[...filtered].sort(")
    fin = rk.index("}),[filtered,sort]);")
    cmp = rk[debut:fin + 1]
    code = (
        "const varSeance=r=>r.chg; const valeurBVC=r=>r.bvc;\n"
        "const rows=[{symbol:'A',chg:1.2},{symbol:'B',chg:null},{symbol:'C',chg:-3},{symbol:'D',chg:0},{symbol:'E',chg:-0.5}];\n"
        "const tri=sort=>[...rows].sort(" + cmp + ").map(r=>r.symbol);\n"
        "console.log(JSON.stringify([tri('var'),tri('var_asc')]));"
    )
    desc, asc = _node(code)
    assert desc == ["A", "D", "E", "C", "B"]
    assert asc == ["C", "E", "D", "A", "B"]


# ── 8. Menu ─────────────────────────────────────────────────────────────────
def test_menu_ne_compte_plus_80_titres():
    rub = ECRAN[ECRAN.index("const RUBRIQUES=["):ECRAN.index("const Marque=")]
    assert "Les 80 titres" not in rub
    assert 'aide:"Tous les titres cotés, leur Score BVC et sa tranche"' in rub
