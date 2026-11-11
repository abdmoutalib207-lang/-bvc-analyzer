"""La carte « États financiers » de la fiche — 11/11/2026.

Le fichier compact (pipeline/etats_publies.py, tests/test_etats_publies.py)
est lu À LA DEMANDE par la fiche. Ce fichier garantit, côté écran :

1. la carte est branchée dans la fiche, lit l'index avant tout fichier de titre
   (jamais de fichier absent demandé) et porte la clé de cache `vpub()` ;
2. les fonctions pures de la carte, EXÉCUTÉES sous node sur les VRAIS fichiers
   publiés (cinq titres, deux vues, toutes les cases), disent pour chaque case
   sa valeur, son statut, sa source et ses réserves ; une case vide dit « — »
   et sa raison ; aucune variation n'est écrite sur une base nulle ou négative ;
3. libellés imposés, mention de pied, aucun mot d'action, aucune bibliothèque
   nouvelle ; le tableau défile dans la carte.

L'attendu est relu ici dans les fichiers publiés, pas dans le code testé.
"""
import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parent.parent
ECRAN = (RACINE / "terminal.src.html").read_text(encoding="utf-8")
PUBLIES = RACINE / "datasets" / "etats_publies"
TITRES = json.loads((PUBLIES / "index.json").read_text(encoding="utf-8"))["titres"]
PIED = "Chiffres relus dans les documents officiels ; rien n'entre dans le Score BVC."


def _entre(debut, fin):
    i = ECRAN.index(debut)
    return ECRAN[i:ECRAN.index(fin, i)]


CARTE = _entre("// ── FICHE : « ÉTATS FINANCIERS »", "// ── TICKER NEWS")
PUR = _entre("const efCouvert=", "const EfSource=")


def _node(corps):
    node = shutil.which("node")
    if not node:                                    # pragma: no cover
        pytest.skip("node absent de cette machine")
    nfr = re.search(r"const nfr=.*?;\n", ECRAN).group(0)
    script = (nfr + PUR + "\nconst fs=require('fs');\n"
              + f"const lire=t=>JSON.parse(fs.readFileSync({json.dumps(str(PUBLIES))}+'/'+t+'.json','utf8'));\n"
              + corps)
    r = subprocess.run([node, "-e", script], capture_output=True, text=True, timeout=120)
    assert r.returncode == 0, f"node a échoué :\n{r.stderr}"
    return json.loads(r.stdout)


@pytest.fixture(scope="module")
def details():
    """efDetail pour TOUTES les cases publiées, telles que l'écran les écrit."""
    return _node(f"""
const out=[];
for(const t of {json.dumps(TITRES)}){{const e=lire(t);
  for(const vue of Object.keys(e.vues)) for(const l of e.lignes) e.vues[vue].cellules[l.cle].forEach((c,i)=>
    out.push({{t,vue,cle:l.cle,i,case:efCase(c.v,l.unite),marque:efMarque(c),d:efDetail(e,vue,l.cle,i)}}));}}
console.log(JSON.stringify(out));""")


def _publie(t):
    return json.loads((PUBLIES / f"{t}.json").read_text(encoding="utf-8"))


# ── 1. branchement, chargement à la demande ─────────────────────────────────

def test_carte_branchee_dans_la_fiche_et_chargee_a_la_demande():
    assert "<EtatsFinanciers sym={sym}/>" in ECRAN
    charger = _entre("const chargerEtats=", "/* Fonctions pures")
    assert 'fetch("datasets/etats_publies/index.json?t="+vpub())' in charger
    assert "fetch(`datasets/etats_publies/${sym}.json?t=`+vpub())" in charger
    # L'index d'abord : sans lui, ou pour un titre qu'il ne cite pas, aucun fichier de titre n'est demandé.
    assert charger.index("index.json") < charger.index("efCouvert(ix,sym)") < charger.index("${sym}.json")
    # Rien n'est lu au démarrage du terminal : le seul appel est dans la carte.
    assert ECRAN.count("chargerEtats(") == 1 and "chargerEtats(sym).then" in CARTE
    # Jamais les chiffres du titre précédent pendant un changement de fiche.
    assert "charge.ticker===sym" in CARTE
    # La fusion de data.json n'en porte rien (fichiers hors data.json).
    i = ECRAN.find("d.tickers.forEach(t=>{m[t.symbol]={")
    assert "etats" not in ECRAN[i:ECRAN.find("};});", i)]


def test_couverture_index_et_titre_sans_releve():
    r = _node(f"""const ix=JSON.parse(fs.readFileSync({json.dumps(str(PUBLIES / 'index.json'))},'utf8'));
console.log(JSON.stringify({{iam:efCouvert(ix,'IAM'),cmt:efCouvert(ix,'CMT'),nul:efCouvert(null,'IAM'),vide:efCouvert({{}},'IAM')}}));""")
    assert r == {"iam": True, "cmt": False, "nul": False, "vide": False}


# ── 2. les fonctions pures, sur les fichiers publiés ────────────────────────

def test_chaque_case_dit_valeur_statut_source_ou_raison(details):
    assert len(details) > 1000
    pubs = {t: _publie(t) for t in TITRES}
    n_src = n_vide = 0
    for x in details:
        e = pubs[x["t"]]
        c = e["vues"][x["vue"]]["cellules"][x["cle"]][x["i"]]
        d, ou = x["d"], f"{x['t']} {x['vue']} {x['cle']} {x['i']}"
        texte = json.dumps(d, ensure_ascii=False)
        assert not re.search(r"undefined|NaN|\[object", texte), ou
        if "v" not in c:
            n_vide += 1
            assert x["case"] == "—" and d["vide"] and d["valeur"] == "—", ou
            assert d["raison"] == e["textes"][c["n"]] and len(d["raison"]) > 20, ou
            assert d["statut"] is None and "source" not in d, ou
            continue
        assert d["statut"] == e["statuts"][c["s"]] and not d["vide"] and d["raison"] is None, ou
        if c["s"] in ("p", "c"):
            n_src += 1
            s = d["source"]
            assert s["u"] == e["documents"][c["d"]]["u"] and s["u"].startswith("https://"), ou
            assert s["f"].lower().endswith(".pdf") and s["page"] == c["p"] and s["citation"] == c["c"], ou
            assert s["imprime"].startswith(c["i"]) and "(" in s["imprime"], f"{ou} : jeton et unité imprimés"
        elif c["s"] == "k":
            assert d["formule"] and len(d["composantes"]) == len(c["k"]), ou
            for k in d["composantes"]:
                assert k["libelle"] and k["source"]["u"].startswith("https://") and k["source"]["citation"], ou
        else:
            assert c["s"] == "m" and "÷" in d["calcul"] and "× 100 =" in d["calcul"], ou
        assert d["reserves"] == [e["textes"][j] for j in c.get("r", [])], ou
        # une réserve se voit dans le tableau même
        if c.get("r") or c["s"] == "c":
            assert x["marque"] and x["marque"][0] in ("°", "⚠"), ou
    assert n_src > 500 and n_vide > 200


def test_aucune_variation_ecrite_sur_base_nulle_ou_negative(details):
    pubs = {t: _publie(t) for t in TITRES}
    n = ns = 0
    for x in details:
        v = pubs[x["t"]]["vues"][x["vue"]]
        cs = v["cellules"][x["cle"]]
        c = cs[x["i"]]
        if "g" not in c:
            assert "variation" not in x["d"]
            continue
        an = int(v["periodes"][x["i"]]["cle"][-4:])
        j = next(k for k, p in enumerate(v["periodes"]) if int(p["cle"][-4:]) == an - 1)
        txt = x["d"]["variation"]
        assert v["periodes"][j]["libelle"] in txt
        if cs[j]["v"] <= 0:
            ns += 1
            assert c["g"] == "ns" and "n.s." in txt and "base nulle ou négative" in txt and "%" not in txt
        else:
            n += 1
            assert re.search(r"[+−]?\d[\d ]*,\d %", txt) and "calculé" in txt and "n.s." not in txt
    assert n > 300 and ns >= 5


def test_format_francais_et_geometrie_des_barres():
    r = _node("""console.log(JSON.stringify({
  a:efNombre(36699,'MDH'),b:efNombre(-437.128,'MDH'),c:efNombre(4.9,'%'),d:efNombre(null,'MDH'),e:efNombre(13.5,'DH'),
  f:efCase(879095340,'actions'),g:efAvecUnite(879095340,'actions'),h:efAvecUnite(-8819,'MDH'),i:efAvecUnite(16.5,'%'),
  v1:efVar(3.2),v2:efVar(-47.8),v3:efVar(0),v4:efVar('ns'),v5:efVar(undefined),k1:efCourt(36699),k2:efCourt(-437.1),
  m1:efMarque({s:'c',r:[1]}),m2:efMarque({s:'p',r:[2]}),m3:efMarque({s:'k'}),m4:efMarque({s:'p'}),m5:efMarque({n:3}),
  b1:efBarres([{v:100},{n:0},{v:50}],100),b2:efBarres([{v:100},{v:-50}],90),b3:efBarres([{n:0},{n:1}],100),b4:efBarres([{v:-20},{v:-80}],80)}));""")
    assert (r["a"], r["b"], r["c"], r["d"], r["e"]) == ("36 699", "−437,1", "4,9 %", "—", "13,50")
    assert (r["f"], r["g"], r["h"], r["i"]) == ("879,10", "879 095 340 actions", "−8 819 MDH", "16,5 %")
    assert (r["v1"], r["v2"], r["v3"], r["v4"], r["v5"]) == ("+3,2 %", "−47,8 %", "0,0 %", "n.s.", None)
    assert (r["k1"], r["k2"]) == ("36,7 Md", "−437")
    assert r["m1"][0] == "°" and r["m2"][0] == "⚠" and r["m3"][0] == "∑" and r["m4"] is None and r["m5"] is None
    # Barres : zéro dans le cadre, période non relevée = pas de barre, négatif sous la ligne.
    b1 = r["b1"]
    assert b1["zero"] == 100 and b1["barres"][1] is None and b1["dernier"] == 2
    assert (b1["barres"][0]["y"], b1["barres"][0]["h"]) == (0, 100) and (b1["barres"][2]["y"], b1["barres"][2]["h"]) == (50, 50)
    b2 = r["b2"]
    assert b2["zero"] == 60 and b2["barres"][0] == {"y": 0, "h": 60, "neg": False} and b2["barres"][1] == {"y": 60, "h": 30, "neg": True}
    assert r["b3"] is None
    assert r["b4"]["zero"] == 0 and r["b4"]["barres"][1] == {"y": 0, "h": 80, "neg": True}


def test_dette_nette_les_deux_valeurs_nommees_cote_a_cote(details):
    """IAM 2024 : 22 436 publiée par l'émetteur, 22 463 calculée par nous (relevé)."""
    par = {(x["t"], x["vue"], x["cle"], x["i"]): x["d"] for x in details}
    i = [p["cle"] for p in _publie("IAM")["vues"]["annuel"]["periodes"]].index("FY2024")
    pub, calc = par[("IAM", "annuel", "dette_nette_publiee", i)], par[("IAM", "annuel", "dette_nette", i)]
    assert pub["titre"] == "Dette nette publiée par l'émetteur · 2024" and pub["valeur"] == "22 436 MDH"
    assert pub["pendant"] == "Dette nette calculée par BVC Analyzer, même période : 22 463 MDH."
    assert calc["titre"] == "Dette nette calculée par BVC Analyzer · 2024" and calc["valeur"] == "22 463 MDH"
    assert calc["pendant"] == "Dette nette publiée par l'émetteur, même période : 22 436 MDH."
    assert [k["signe"] for k in calc["composantes"]] == ["+", "+", "−"]
    assert "à ne pas confondre avec la dette nette publiée par l'émetteur" in calc["formule"]
    # Banque : aucune ligne de dette nette, PNB et RBE nommés.
    titres_atw = {x["d"]["titre"].split(" · ")[0] for x in details if x["t"] == "ATW"}
    assert not any("ette nette" in t for t in titres_atw)
    assert {"Produit net bancaire (PNB)", "Résultat brut d'exploitation (RBE)"} <= titres_atw


# ── 3. textes imposés, aucun mot d'action, pas de bibliothèque nouvelle ─────

def test_textes_de_la_carte():
    assert PIED in CARTE
    assert "non relevé" in CARTE and "jamais estimée" in CARTE
    assert "EBE" not in CARTE, "le libellé vient du fichier : « EBITDA ajusté (indicateur de gestion, non audité) »"
    for mot in ("ACHETER", "VENDRE", "ÉVITER", "acheter", "vendre", "renforcer", "alléger", "va monter",
                "va baisser", "objectif de cours", "prévision", "devrait", "potentiel", "ms-screener"):
        assert mot not in CARTE[CARTE.index("let ETATS_IDX"):], mot      # le code, sans son en-tête
    # Bascule et graphique : boutons à état, SVG simple, aucune bibliothèque de graphique.
    assert '["annuel","Annuel"],["semestriel","Semestriel"]' in CARTE and "aria-pressed={vue===k}" in CARTE
    assert "<svg" in CARTE and "LightweightCharts" not in CARTE and "ApexCharts" not in CARTE
    # Le tableau défile DANS la carte, la colonne des grandeurs reste en place.
    css = ECRAN[:ECRAN.index("</style>")]
    assert re.search(r"\.ef-defile\{width:0;min-width:100%;overflow-x:auto", css)
    assert re.search(r"\.ef-t \.ef-lib\{position:sticky;left:0", css)
    assert ".ef-c::after{inset:0!important}" in css           # zone tactile contenue dans la case
    assert ".ef-ombre .ef-lib{" in css                         # colonnes cachées signalées
    assert 'className={"ef-defile"+(ombre?" ef-ombre":"")}' in CARTE


def test_colonnes_entieres_jamais_un_chiffre_coupe():
    """11/11/2026 : « 16 373 » se lisait « 6 373 », à moitié sous la colonne figée.
    Pour toute largeur de cadre de 260 à 1 400 px et 8 ou 10 périodes : colonnes
    de période égales, au moins aussi larges que la case la plus large mesurée
    (55,1 px + marges), un nombre ENTIER visible, la colonne figée prenant le
    reste — donc toute accroche et la position initiale (n − k)·W tombent sur
    une limite de colonne. Le défilement s'accroche par colonne et s'ouvre calé
    sur cette position, avant le premier affichage."""
    r = _node("""const out=[];for(const n of [8,10])for(let C=260;C<=1400;C++){const g=efColonnes(C,n);out.push([C,n,g.k,g.W,g.L]);}
console.log(JSON.stringify(out));""")
    for C, n, k, W, L in r:
        ou = f"C={C} n={n}"
        assert isinstance(W, int) and isinstance(L, int) and L + k * W == C, ou
        assert 1 <= k <= n and W >= 62 and 120 <= L < 164 + W, ou
        if k < n:
            assert C - (124 if C < 480 else 164) < (k + 1) * 62, ou   # pas une colonne entière de plus
    g = {(C, n): (k, W, L) for C, n, k, W, L in r}
    assert g[(336, 10)] == (3, 70, 126)          # téléphone 390 px : trois exercices entiers
    assert g[(744, 10)][0] == 10                 # ordinateur 1440 px : les dix exercices
    assert 'scrollSnapType:"x mandatory",scrollPaddingLeft:geo.L' in CARTE
    assert 'style={{scrollSnapAlign:"start"}}' in CARTE
    assert "tableLayout:\"fixed\",width:geo.L+n*geo.W" in CARTE
    assert "el.scrollLeft=(m-g.k)*g.W" in CARTE and "React.useLayoutEffect" in CARTE
    assert "direction:rtl" not in ECRAN


def test_aucune_bibliotheque_ajoutee():
    scripts = re.findall(r'<script src="([^"]+)"', ECRAN)
    assert len(scripts) == 4 and not any("chart.js" in s or "d3" in s or "recharts" in s for s in scripts), scripts


def test_index_compile_contient_la_carte():
    idx = (RACINE / "index.html").read_text(encoding="utf-8")
    assert "Chiffres relus dans les documents officiels ; rien n'entre dans le Score BVC." in idx
    assert "datasets/etats_publies/index.json?t=" in idx and "EtatsFinanciers" in idx


def test_dette_nette_calculee_jamais_seule_dans_la_lecture_du_graphique(details):
    """Règle (relecture du 11/11/2026) : la dette nette calculée ne s'affiche
    jamais seule quand l'émetteur publie la sienne. La ligne de lecture du
    graphique porte l'autre valeur de la même période, ou « non relevée »."""
    lecture = _entre('<div aria-live="polite" style={{fontSize:11', "<svg")
    assert "{lu.pendant&&" in lecture and "lu=bi>=0?efDetail(e,vue,g.cle,bi)" in CARTE
    vus = {"chiffre": 0, "non_relevee": 0}
    for x in details:
        if x["cle"] not in ("dette_nette", "dette_nette_publiee") or x["d"]["vide"]:
            continue
        if not any(l["cle"] == "dette_nette_publiee" for l in _publie(x["t"])["lignes"]):
            continue
        autre = ("Dette nette publiée par l'émetteur" if x["cle"] == "dette_nette"
                 else "Dette nette calculée par BVC Analyzer")
        pend = x["d"].get("pendant") or ""
        assert pend.startswith(autre + ", même période : "), (x["t"], x["vue"], x["i"], pend)
        assert pend.endswith(" MDH.") or pend.endswith("non relevée."), pend
        vus["non_relevee" if pend.endswith("non relevée.") else "chiffre"] += 1
    assert vus["chiffre"] >= 20 and vus["non_relevee"] >= 5, vus
