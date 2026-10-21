"""FIG · TEND · GAP — figures, obliques et gaps sur le graphique de la fiche.

LA DEMANDE (Abd Moutalib, 21/10/2026)
─────────────────────────────────────
« Je ne vois toujours pas de boutons ETE ou oblique. » Les figures étaient
publiées dans `datasets/figures_publiees.json` (PR #297) mais rien ne les
montrait à l'écran.

CE QUE CE FICHIER GARANTIT
──────────────────────────
1. Trois boutons dans la barre du graphique, à côté de S/R et FIB.
2. Le fichier des figures n'est lu qu'au PREMIER clic, jamais à l'ouverture.
3. Vision produit : aucun mot d'annonce (objectif, cible, va, devrait,
   potentiel) dans ce qui s'affiche ; sous 30 cas, « échantillon insuffisant »
   et aucun pourcentage ; sur une figure ARMÉE, aucun pourcentage hors de la
   formule « après une cassure » — la fréquence décrit ce qui a suivi des
   cassures passées, pas la chance de la figure en cours.

⚠️ Les phrases sont PRODUITES par le code publié, exécuté sous node sur le
vrai fichier `datasets/figures_publiees.json` — les 80 titres, pas un
échantillon choisi. L'attendu (seuil, univers, sens) est relu ici dans le
fichier, jamais dans le code testé.
"""

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parent.parent
FRONT = RACINE / "terminal.src.html"
FIGS = RACINE / "datasets" / "figures_publiees.json"
CANDLES = RACINE / "pipeline" / "candles"
INTERDITS = re.compile(r"\b(objectif|objectifs|cible|cibles|va|devrait|devraient|potentiel|potentielle)\b",
                       re.IGNORECASE)


def _source():
    return FRONT.read_text(encoding="utf-8")


def _entre(src, debut, fin):
    i = src.index(debut)
    return src[i:src.index(fin, i)]


def _stockchart(src):
    return _entre(src, "const StockChart=({r})=>{", "// ── TICKER TAPE")


def _bloc_pur(src):
    """Les fonctions pures FIG · TEND · GAP (aucun JSX, aucun appel réseau)."""
    return _entre(src, "const FIG_COURT=", "/* Dessin sur le graphique")


def _node(script):
    node = shutil.which("node")
    if not node:                                    # pragma: no cover
        pytest.skip("node absent de cette machine")
    r = subprocess.run([node, "-e", script], capture_output=True, text=True, timeout=120)
    assert r.returncode == 0, f"node a échoué :\n{r.stderr}"
    return json.loads(r.stdout)


def _harnais(corps):
    src = _source()
    fmt = re.search(r"const fmtPrixFR=.*?;\n", src).group(0)
    return (fmt + _bloc_pur(src) + "\n"
            + "const fs=require('fs');\n"
            + f"const FP=JSON.parse(fs.readFileSync({json.dumps(str(FIGS))},'utf8'));\n"
            + corps)


@pytest.fixture(scope="module")
def publie():
    return json.loads(FIGS.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def phrases():
    """Toutes les lignes de légende, pour les 80 titres, telles que l'écran les écrit."""
    return _node(_harnais("""
const an=(FP.derniere_seance_du_marche||'').slice(0,4),out=[];
for(const [t,v] of Object.entries(FP.titres)){
  const liq=!!v.liquide;
  (v.figures||[]).forEach(e=>out.push({t,k:'figures',type:e.type,statut:e.statut,liq,txt:figLegende(e,FP,liq,an)}));
  (v.lignes||[]).forEach(e=>out.push({t,k:'lignes',type:e.type,statut:e.statut,liq,txt:ligneLegende(e,FP,liq,an)}));
  (v.gaps||[]).forEach(e=>out.push({t,k:'gaps',type:e.type,statut:e.statut,liq,txt:gapLegende(e,FP,liq,an)}));
}
console.log(JSON.stringify(out));
"""))


# ── 1. Les trois boutons ─────────────────────────────────────────────────────

@pytest.mark.parametrize("bouton", ["FIG", "TEND", "GAP"])
def test_les_trois_boutons_sont_dans_la_barre_du_graphique(bouton):
    chart = _stockchart(_source())
    m = re.search(r'<Btn on=\{show\w+\} c="#[0-9a-f]{6}" titre="([^"]+)" '
                  r'onClick=\{\(\)=>basculeFig\(setShow\w+\)\}>' + bouton + r"</Btn>", chart)
    assert m, f"bouton {bouton} absent de la barre du graphique"
    # Même composant que S/R et FIB, juste après eux.
    assert chart.index(">FIB</Btn>") < m.start()
    titre = m.group(1)
    assert len(titre) > 60, f"{bouton} : l'infobulle doit nommer en clair ce que trace le bouton"
    assert not INTERDITS.search(titre), f"{bouton} : mot interdit dans l'infobulle"


def test_l_infobulle_fig_nomme_les_figures_en_toutes_lettres():
    chart = _stockchart(_source())
    titre = re.search(r'titre="([^"]+)" onClick=\{\(\)=>basculeFig\(setShowFig\)\}', chart).group(1)
    for nom in ("épaule-tête-épaule", "ETE inversée", "double creux", "double sommet", "triangles",
                "tasse avec anse", "Fibonacci"):
        assert nom in titre, f"l'infobulle FIG ne nomme pas « {nom} »"


def test_les_trois_boutons_sont_eteints_a_l_ouverture():
    chart = _stockchart(_source())
    for v in ("showFig", "showTend", "showGap"):
        assert re.search(r"const \[" + v + r",set\w+\]=useState\(false\);", chart), v


# ── 2. Chargement à la demande ───────────────────────────────────────────────

def test_le_fichier_des_figures_n_est_lu_qu_au_premier_clic():
    src = _source()
    # Une seule lecture du fichier dans tout le terminal : dans chargerFigures.
    assert src.count('fetch("datasets/figures_publiees.json') == 1
    charge = re.search(r"const chargerFigures=\(\)=>FIG_PUB_P\|\|\(FIG_PUB_P=fetch\(\"datasets/figures_publiees\.json", src)
    assert charge, "chargerFigures doit mémoriser sa promesse (un seul téléchargement)"
    # chargerFigures() n'est appelé QUE dans le gestionnaire de clic.
    appels = [m.start() for m in re.finditer(r"chargerFigures\(\)\.", src)]
    assert len(appels) == 1, appels
    bascule = _entre(src, "const basculeFig=set=>{", "\n  };")
    assert "chargerFigures()" in bascule
    # Et le gestionnaire n'est branché que sur les trois boutons.
    assert len(re.findall(r"basculeFig\(", _stockchart(src))) == 3


def test_le_chargement_garde_le_meme_chemin_relatif_que_les_autres_jeux():
    src = _source()
    # Même convention que datasets/frequences_publiees.json : chemin relatif,
    # cache rompu à l'heure (le fichier change au plus une fois par soir).
    assert 'fetch("datasets/frequences_publiees.json?t="+Math.floor(Date.now()/3600000))' in src
    assert 'fetch("datasets/figures_publiees.json?t="+Math.floor(Date.now()/3600000))' in src


# ── 3. Vision produit : ce que les phrases disent, et ne disent pas ──────────

def test_aucun_mot_d_annonce_dans_ce_qui_s_affiche(phrases):
    src = _source()
    textes = [p["txt"] for p in phrases]
    textes.append(_entre(src, "const LegendeFigures=", "const StockChart="))
    textes += re.findall(r'<L titre="(?:FIG|TEND|GAP) — [^"]+">(.*?)</L>', src, re.S)
    textes += re.findall(r'titre="([^"]+)" onClick=\{\(\)=>basculeFig', _stockchart(src))
    for t in textes:
        m = INTERDITS.search(t)
        assert not m, f"mot interdit « {m.group(0)} » dans : {t[:160]}"


def test_echantillon_insuffisant_sans_aucun_pourcentage(publie):
    refs = [(r, u) for r, f in publie["frequences"].items() if "sens_teste" in f
            for u in ("tous", "liquides") if f["univers"][u]["statut"] != "publie"]
    assert refs, "le fichier n'a aucune fréquence sous le seuil : le test ne prouverait rien"
    sortie = _node(_harnais(f"""
const R={json.dumps(refs)};
console.log(JSON.stringify(R.map(([r,u])=>[r,u,figFrequence(FP,r,u==='liquides','après une cassure')])));
"""))
    for r, u, txt in sortie:
        n = publie["frequences"][r]["univers"][u]["n"]
        assert f"échantillon insuffisant ({n} cas" in txt, (r, u, txt)
        assert "%" not in txt, f"pourcentage sous le seuil : {r}/{u} — {txt}"


def test_sous_trente_cas_meme_si_le_fichier_disait_publie():
    """Ceinture et bretelles : le seuil est relu dans `methode`, pas cru sur parole."""
    sortie = _node(_harnais("""
const fp={methode:{min_cas_pour_publier:30},frequences:{x:{sens_teste:1,horizon_seances:20,
  periodes:{a:{debut:'2023-10-04',fin:'2026-10'}},
  univers:{tous:{n:12,statut:'publie',part_bon_sens_brute_pct:80}}}}};
console.log(JSON.stringify(figFrequence(fp,'x',false,'après une cassure')));
"""))
    assert sortie == "après une cassure, échantillon insuffisant (12 cas, 2023-2026, tous titres)"


def test_une_figure_armee_n_a_de_pourcentage_qu_apres_une_cassure(phrases):
    armees = [p for p in phrases if p["k"] == "figures" and p["statut"] == "armee"]
    avec_pct = [p for p in armees if "%" in p["txt"].split(" · ", 1)[-1]]
    assert avec_pct, "aucune figure armée chiffrée dans le fichier : le test serait vide"
    for p in armees:
        tete, _, freq = p["txt"].partition(" · ")
        assert "armée, pas encore cassée" in tete, p
        assert "%" not in tete.replace(p["txt"].split(" — ")[0], ""), p
        for seg in freq.split(" ; "):
            if "%" in seg:
                assert seg.startswith("après une cassure"), f"{p['t']} : « {seg} »"


def test_une_ligne_armee_ne_chiffre_que_des_cas_passes(phrases):
    for p in phrases:
        if p["k"] != "lignes" or p["statut"] != "armee":
            continue
        for seg in p["txt"].partition(" · ")[2].split(" ; "):
            if "%" in seg:
                assert seg.startswith(("après une cassure", "après un rebond")), f"{p['t']} : « {seg} »"


def test_la_phrase_d_une_figure_declenchee(publie, phrases):
    """« Double creux — cassure le 14/10 · après une cassure, sur 412 cas
    (2023-2026), 58 % ont fait mieux que le MASI à 20 séances, hors frais »."""
    vus = 0
    for p in phrases:
        if p["k"] != "figures" or p["statut"] != "declenchee" or p["type"].startswith("fibo_"):
            continue
        assert re.search(r" — cassure le \d\d/\d\d(/\d\d)?( \(volume ×[\d,]+ la médiane des 20 séances précédentes\))? · après une cassure", p["txt"]), p["txt"]
        f = publie["frequences"]
        e = next(e for e in publie["titres"][p["t"]]["figures"]
                 if e["type"] == p["type"] and e["statut"] == "declenchee"
                 and figure_txt_ok(e, p))
        ref = e["signal"]
        u = f[ref]["univers"]["liquides" if p["liq"] else "tous"]
        if u["statut"] == "publie":
            vus += 1
            pct = f"{u['part_bon_sens_brute_pct']:.1f}".rstrip("0").rstrip(".").replace(".", ",")
            sens = "moins bien" if f[ref]["sens_teste"] < 0 else "mieux"
            attendu = (f"sur {u['n']} cas (2023-2026, {'titres liquides' if p['liq'] else 'tous titres'}), "
                       f"{pct} % ont fait {sens} que le MASI à 20 séances, hors frais")
            assert attendu in p["txt"], (attendu, p["txt"])
    assert vus > 0


def figure_txt_ok(e, p):
    return e["libelle"] in p["txt"]


def test_la_phrase_d_un_gap_ouvert(publie, phrases):
    ouverts = [p for p in phrases if p["k"] == "gaps" and p["statut"] == "ouvert"]
    assert ouverts
    for p in ouverts:
        g = next(g for g in publie["titres"][p["t"]]["gaps"] if g["statut"] == "ouvert" and g["type"] == p["type"])
        c = publie["frequences"][p["type"]]["univers"]["liquides" if p["liq"] else "tous"]["h20"]["toutes_periodes"]
        s = "s" if g["age_seances"] > 1 else ""
        assert f"ouvert depuis {g['age_seances']} séance{s}" in p["txt"], p["txt"]
        if g["age_seances"] < 20:
            assert f"des {'gaps baissiers' if p['type'] == 'gap_baissier' else 'gaps haussiers'} ont été comblés en 20 séances ({c['n']} cas" in p["txt"], p["txt"]


# Horizon selon l'âge du gap (décision du 21/10/2026) : < 20 séances, taux à
# 20 ; de 20 à 59, taux à 60 ; 60 et plus, aucun taux. Un gap réel (STR,
# 36 séances) et des gaps construits pour les bornes.

def _gap(age, statut="ouvert", liq=False):
    g = {"type": "gap_baissier", "libelle": "Gap baissier", "date": "2026-08-31", "statut": statut,
         "zone_haute": 205.0, "zone_basse": 198.0, "date_retour_dans_la_zone": None,
         "date_comblement": None, "age_seances": age, "frequence_ref": ["gap_baissier"]}
    return _node(_harnais(f"console.log(JSON.stringify(gapLegende({json.dumps(g)},FP,{json.dumps(liq)},'2026')));"))


def _taux(publie, h, liq=False):
    c = publie["frequences"]["gap_baissier"]["univers"]["liquides" if liq else "tous"][h]["toutes_periodes"]
    return f"{c['pct_combles']:.1f}".rstrip("0").rstrip(".").replace(".", ","), c["n"]


def test_gap_de_moins_de_20_seances_taux_a_20(publie):
    pct, n = _taux(publie, "h20")
    for age in (0, 6, 19):
        txt = _gap(age)
        assert f"{pct} % des gaps baissiers ont été comblés en 20 séances ({n} cas, tous titres)" in txt, txt
        assert "60 séances" not in txt, txt


def test_gap_de_20_a_59_seances_taux_a_60_cas_reel_str(publie, phrases):
    g = next(g for g in publie["titres"]["STR"]["gaps"] if g["statut"] == "ouvert")
    assert g["age_seances"] == 36 and g["type"] == "gap_baissier", g   # le cas réel décrit
    liq = bool(publie["titres"]["STR"].get("liquide"))
    txt = next(p["txt"] for p in phrases if p["t"] == "STR" and p["k"] == "gaps" and p["statut"] == "ouvert")
    pct, n = _taux(publie, "h60", liq)
    assert ("ouvert depuis 36 séances · sur 2023-2026, "
            f"{pct} % des gaps baissiers ont été comblés dans les 60 séances suivant leur ouverture ({n} cas, ") in txt, txt
    assert "en 20 séances" not in txt, txt
    for age in (20, 59):                                     # les deux bornes
        assert "dans les 60 séances suivant leur ouverture" in _gap(age)
    assert "dans les 60 séances suivant leur ouverture" in _gap(36, "partiellement_comble")


def test_gap_de_60_seances_et_plus_aucun_taux():
    for age in (60, 84, 200):
        for statut in ("ouvert", "partiellement_comble"):
            txt = _gap(age, statut)
            assert txt.endswith(f"ouvert depuis {age} séances, au-delà de l'horizon mesuré (60 séances)"), txt
            assert "%" not in txt and "cas" not in txt, txt


def test_un_gap_comble_ne_porte_aucune_frequence(phrases):
    for p in phrases:
        if p["k"] == "gaps" and p["statut"] == "comble":
            assert "%" not in p["txt"] and "comblé le" in p["txt"], p["txt"]


def test_l_univers_est_ecrit_et_suit_la_liquidite(phrases):
    for p in phrases:
        if "cas (" in p["txt"] or "cas, " in p["txt"]:
            nom = "titres liquides" if p["liq"] else "tous titres"
            assert nom in p["txt"], (p["t"], p["txt"])


def test_une_figure_invalidee_ou_expiree_n_a_pas_de_frequence(phrases):
    for p in phrases:
        if p["statut"] in ("invalidee", "expiree"):
            assert "%" not in p["txt"].split(" — ", 1)[-1], p["txt"]


# ── 4. Tracé : fenêtre, titres sans rien, robustesse ─────────────────────────

def test_le_trace_ne_plante_sur_aucun_titre_ni_aucune_fenetre(publie):
    fichiers = {p.stem: str(p) for p in CANDLES.glob("*.json")}
    sortie = _node(_harnais(f"""
const F={json.dumps(fichiers)},res={{}};
for(const [t,v] of Object.entries(FP.titres)){{
  let d=[];try{{const c=JSON.parse(fs.readFileSync(F[t],'utf8'));d=(Array.isArray(c)?c:c.candles).map(x=>x.d);}}catch(e){{}}
  res[t]={{statut:v.statut_titre,par:{{}}}};
  for(const n of [5,60,250,100000]){{
    const dates=d.slice(-n);
    const el=figElements(v,dates[0],{{fig:true,tend:true,gap:true}});
    const f=figFormes(el.pris,dates,v);
    const avant=el.pris.filter(([k,e])=>figDebut(e)<dates[0]).length;
    res[t].par[n]={{pris:el.pris.length,hors:el.hors,passees:el.passees,formes:f.length,avant,
      nan:f.some(x=>JSON.stringify(x).includes('null')&&x.k==='poly'&&x.pts.some(p=>p[0]==null||p[1]==null))}};
  }}
}}
console.log(JSON.stringify(res));
"""))
    assert len(sortie) == len(publie["titres"]) == 80
    for t, r in sortie.items():
        for n, x in r["par"].items():
            assert x["avant"] == 0, f"{t}/{n} : un élément antérieur à la fenêtre est tracé"
            assert not x["nan"], f"{t}/{n} : point sans coordonnée"
            if r["statut"] != "analyse":
                assert x["pris"] == 0 and x["formes"] == 0, (t, n, x)
        # Toute la série : rien n'est caché ; un élément au moins par titre analysé qui en a.
        tout = r["par"]["100000"]
        v = publie["titres"][t]
        total = len(v["figures"]) + len(v["lignes"]) + len(v["gaps"])
        if r["statut"] == "analyse" and (CANDLES / f"{t}.json").exists():
            assert tout["pris"] + tout["hors"] + tout["passees"] == total, (t, tout, total)


def test_un_titre_inactif_ou_exclu_donne_sa_raison():
    src = _source()
    leg = _entre(src, "const LegendeFigures=", "const StockChart=")
    assert 't.statut_titre!=="analyse"' in leg and "t.raison" in leg
    assert "Ce titre n'est pas couvert par le fichier des figures." in leg
    assert "Fichier des figures indisponible" in leg


def test_le_dessin_passe_par_une_primitive_de_serie_gardee():
    src = _source()
    chart = _stockchart(src)
    assert 'if(typeof cs.attachPrimitive==="function"){try{cs.attachPrimitive(dessins);}catch(e){}}' in chart
    dessins = _entre(src, "const creerDessins=()=>{", "const LegendeFigures=")
    assert '"bottom"' in dessins and '"top"' in dessins  # zones sous les bougies, tracés au-dessus
    # Aucune série ajoutée pour les figures : l'échelle des prix reste celle des bougies.
    assert "addLineSeries" not in _bloc_pur(src) + dessins


def test_figvue_est_declare_avant_l_effet_qui_le_cite():
    """Le piège du 04/10/2026 : une constante lue avant sa déclaration casse
    tout le terminal (« Erreur de rendu »)."""
    chart = _stockchart(_source())
    assert chart.index("const figVue=useMemo(") < chart.index("},[figVue,figFocus,sym,period,liveCandles,etat,plein]);")


def test_la_legende_s_affiche_sous_le_graphique():
    chart = _stockchart(_source())
    assert chart.index("<LegendeSR ") < chart.index("<LegendeFigures ")


def test_comment_lire_a_une_entree_par_bouton():
    src = _source()
    guide = _entre(src, "Comment lire l'écran</div>", "// ── SMART MONEY")
    for titre in ("FIG — figures chartistes du graphique", "TEND — obliques et canaux", "GAP — trous de cotation"):
        m = re.search(r'<L titre="' + re.escape(titre) + r'">(.*?)</L>', guide, re.S)
        assert m, titre
        corps = m.group(1)
        assert "30 cas" in corps, f"{titre} : le seuil de 30 cas n'est pas dit"
    fig = re.search(r'<L titre="FIG — figures chartistes du graphique">(.*?)</L>', guide, re.S).group(1)
    assert "non déduits" in fig and "armée" in fig and "après la cassure" in fig


# ── 5. Dessin, d'après les captures d'ADI et d'ADH en 3A (22/10/2026) ───────
# Chaque test fait tracer TOUTES les figures et droites du fichier publié sur
# l'historique complet du titre, puis relit les formes produites.

@pytest.fixture(scope="module")
def formes(publie):
    fichiers = {p.stem: str(p) for p in CANDLES.glob("*.json")}
    return _node(_harnais(f"""
const F={json.dumps(fichiers)},res=[];
for(const [t,v] of Object.entries(FP.titres)){{
  if(v.statut_titre!=='analyse'||!F[t])continue;
  const c=JSON.parse(fs.readFileSync(F[t],'utf8')),dates=(Array.isArray(c)?c:c.candles).map(x=>x.d);
  const el=figElements(v,dates[0],{{fig:true,tend:true,gap:false,passees:true}});
  const f=figFormes(el.pris,dates,v);
  el.pris.forEach(([k,e,id])=>res.push({{t,k,id,e,der:dates.length-1,
    ic:e.date_cassure?figIndice(dates,e.date_cassure):null,
    ifin:figFin(e)?figIndice(dates,figFin(e)):null,
    piv:(e.pivots||[]).map(p=>figIndice(dates,p.date)),
    f:f.filter(x=>x.id===id)}}));
}}
console.log(JSON.stringify(res));
"""))


def test_repere_2c_sous_le_creux_le_plus_bas_et_2s_au_dessus_du_sommet_le_plus_haut(formes):
    vus = {"double_creux": 0, "double_sommet": 0}
    for x in formes:
        e = x["e"]
        if e["type"] not in vus:
            continue
        txt = [f for f in x["f"] if f["k"] == "txt"]
        assert len(txt) == 1, (x["t"], e["type"])
        r = txt[0]
        if e["type"] == "double_creux":
            cr = [(p["prix"], i) for p, i in zip(e["pivots"], x["piv"]) if p["type"] == "creux"]
            prix, i = min(cr)
            assert (r["s"], r["dessus"], r["p"], r["i"]) == ("2C", False, prix, i), (x["t"], r, cr)
        else:
            so = [(p["prix"], i) for p, i in zip(e["pivots"], x["piv"]) if p["type"] == "sommet"]
            prix, i = max(so)
            assert (r["s"], r["dessus"], r["p"], r["i"]) == ("2S", True, prix, i), (x["t"], r, so)
        vus[e["type"]] += 1
    assert all(vus.values()), vus


def test_reperes_ete_tasse_et_fibonacci_au_point_caracteristique(formes):
    vus = set()
    for x in formes:
        e, txt = x["e"], [f for f in x["f"] if f["k"] == "txt"]
        piv = list(zip(e.get("pivots") or [], x["piv"]))
        if not txt or not piv:
            continue
        if e["type"] in ("ete", "ete_inversee"):
            # Épaule gauche, tête, épaule droite : au-dessus pour l'ETE, dessous pour l'inversée.
            par = {r["s"]: r for r in txt}
            assert set(par) == {"Épaule g.", "Tête", "Épaule d."}, (x["t"], list(par))
            for nom, k in (("Épaule g.", 0), ("Tête", 2), ("Épaule d.", 4)):
                assert par[nom]["i"] == piv[k][1] and par[nom]["p"] == piv[k][0]["prix"], (x["t"], nom)
                assert par[nom]["dessus"] is (e["type"] == "ete"), (x["t"], nom)
        elif e["type"] == "tasse_anse":
            p, i = min(((p, i) for p, i in piv if p["type"] == "creux"), key=lambda z: z[0]["prix"])
            assert len(txt) == 1 and not txt[0]["dessus"] and txt[0]["i"] == i, x["t"]
        elif e["type"].startswith("fibo_"):
            assert txt[0]["i"] == piv[-1][1] and not txt[0]["dessus"], x["t"]   # le creux du rebond
        else:
            continue
        vus.add(e["type"])
    assert {"ete", "fibo_rebond_382_618"} <= vus, vus


def test_un_triangle_trace_ses_deux_bornes_et_pas_son_zigzag(formes):
    n = 0
    for x in formes:
        e = x["e"]
        if not e["type"].startswith("triangle_"):
            continue
        n += 1
        pleines = [f for f in x["f"] if f["k"] == "poly" and not f.get("tirets")]
        assert len(pleines) == 2, (x["t"], e["type"], len(pleines))
        zigzag = [[i, p["prix"]] for p, i in zip(e["pivots"], x["piv"])]
        assert all(f["pts"] != zigzag for f in x["f"] if f["k"] == "poly"), x["t"]
        so = [p["prix"] for p in e["pivots"] if p["type"] == "sommet"]
        cr = [p["prix"] for p in e["pivots"] if p["type"] == "creux"]
        haute, basse = sorted(pleines, key=lambda f: -max(p[1] for p in f["pts"]))
        # Chaque borne passe par ses deux pivots (sommets pour la haute, creux pour la basse).
        assert all(any(abs(p[1] - s) < 1e-9 for p in haute["pts"]) for s in so), (x["t"], haute)
        assert all(any(abs(p[1] - c) < 1e-9 for p in basse["pts"]) for c in cr), (x["t"], basse)
        # Le repère est entre les deux bornes.
        r = next(f for f in x["f"] if f["k"] == "txt")
        assert r.get("centre") and min(cr) - 1e-9 <= r["p"] <= max(so) + 1e-9, (x["t"], r)
    assert n > 0


def test_les_droites_s_arretent_a_la_cassure_et_seule_l_armee_se_prolonge(formes):
    vus = {"armee": 0, "declenchee": 0, "fin": 0}
    for x in formes:
        e = x["e"]
        polys = [f for f in x["f"] if f["k"] == "poly"]
        if not polys:
            continue
        fin_max = max(p[0] for f in polys for p in f["pts"])
        if e["statut"] == "armee":
            assert fin_max == x["der"], (x["t"], e["type"], fin_max, x["der"])
            vus["armee"] += 1
        elif x["ifin"] is not None:
            assert fin_max <= x["ifin"], (x["t"], e["type"], e["statut"], fin_max, x["ifin"])
            vus["fin"] += 1
        if e["statut"] == "declenchee" and x["ic"] is not None and x["k"] == "lignes":
            assert fin_max == x["ic"], (x["t"], e["type"], fin_max, x["ic"])
            croix = [f for f in x["f"] if f["k"] == "croix"]
            assert len(croix) == 1 and croix[0]["i"] == x["ic"], x["t"]
            vus["declenchee"] += 1
    assert all(vus.values()), vus


def test_une_figure_cassee_porte_une_croix_a_sa_cassure(formes):
    n = 0
    for x in formes:
        if x["k"] == "figures" and x["e"]["statut"] == "declenchee" and x["ic"] is not None:
            croix = [f for f in x["f"] if f["k"] == "croix"]
            assert len(croix) == 1 and croix[0]["i"] == x["ic"], (x["t"], x["e"]["type"])
            n += 1
    assert n > 0


def test_un_niveau_horizontal_reste_sur_l_etendue_de_sa_figure_et_dans_sa_couleur(formes):
    for x in formes:
        if x["k"] != "figures":
            continue
        tirets = [f for f in x["f"] if f["k"] == "poly" and f.get("tirets") and f["c"] != "#ffd740"]
        couleur = {f["c"] for f in x["f"] if f["k"] == "poly" and not f.get("tirets")}
        for f in tirets:
            debut, fin = min(p[0] for p in f["pts"]), max(p[0] for p in f["pts"])
            assert debut >= min(x["piv"]), (x["t"], x["e"]["type"])
            if x["e"]["statut"] != "armee" and x["ifin"] is not None:
                assert fin <= x["ifin"], (x["t"], x["e"]["type"])
            assert {f["c"]} <= couleur, (x["t"], x["e"]["type"], f["c"], couleur)


def test_les_figures_passees_sont_tracees_en_pale_et_masquables(publie):
    """Décision d'Abd Moutalib (22/10/2026) : tracées en pâle par défaut, un
    interrupteur les masque, le choix est retenu."""
    sortie = _node(_harnais("""
const r={};
for(const [t,v] of Object.entries(FP.titres)){
  const a=figElements(v,'0000',{fig:true,tend:true,gap:false,passees:false});
  const b=figElements(v,'0000',{fig:true,tend:true,gap:false,passees:true});
  const dates=[];for(let d=new Date('2023-01-02');d<=new Date('2026-10-21');d.setDate(d.getDate()+1))dates.push(d.toISOString().slice(0,10));
  const f=figFormes(b.pris,dates,v);
  const al=b.pris.filter(p=>figPassee(p[1])).map(p=>Math.max(...f.filter(x=>x.id===p[2]&&x.k==='poly').map(x=>x.al)));
  r[t]={masque:a.pris.map(p=>p[1].statut),passees:a.passees,tout:b.pris.length,al};
}
console.log(JSON.stringify(r));
"""))
    total = 0
    for t, r in sortie.items():
        assert not ({"invalidee", "expiree"} & set(r["masque"])), t
        assert len(r["masque"]) + r["passees"] == r["tout"], t
        assert all(a <= 0.4 for a in r["al"]), (t, r["al"])          # en pâle
        total += r["passees"]
    assert total > 0
    chart = _stockchart(_source())
    assert 'localStorage.getItem("bvc_fig_passees_masquees")!=="1";}catch(e){return true;}' in chart   # affichées par défaut
    assert 'localStorage.setItem("bvc_fig_passees_masquees",v?"1":"0");}catch(e){}' in chart
    leg = _entre(_source(), "const LegendeFigures=", "const StockChart=")
    assert '{passees?"Masquer":"Afficher"} les figures passées ({nbPassees})' in leg


def test_un_clic_dans_la_legende_met_l_element_en_evidence():
    sortie = _node(_harnais("""
const v=FP.titres.ADH,dates=[];
for(let d=new Date('2026-01-02');d<=new Date('2026-10-21');d.setDate(d.getDate()+1))dates.push(d.toISOString().slice(0,10));
const el=figElements(v,dates[0],{fig:true,tend:true,gap:true});
const id=el.pris[0][2],f=figFormes(el.pris,dates,v,id);
console.log(JSON.stringify({id,vu:f.filter(x=>x.id===id).map(x=>x.al),autres:f.filter(x=>x.id!==id).map(x=>x.al)}));
"""))
    assert sortie["autres"] and max(sortie["autres"]) < min(sortie["vu"]), sortie
    leg = _entre(_source(), "const LegendeFigures=", "const StockChart=")
    assert "onClick={()=>choisir&&choisir(id)}" in leg and "aria-pressed" in leg


def test_le_volume_de_cassure_est_ecrit_sans_jugement(publie, phrases):
    """`volume_cassure_ratio` (PR #300) : une information, pas un verdict."""
    n = 0
    for t, v in publie["titres"].items():
        for k in ("figures", "lignes"):
            for e in v[k]:
                r = e.get("volume_cassure_ratio")
                if r is None:
                    continue
                txt = next(p["txt"] for p in phrases if p["t"] == t and p["k"] == k and p["type"] == e["type"]
                           and p["statut"] == e["statut"] and e["date_cassure"][8:10] + "/" + e["date_cassure"][5:7] in p["txt"])
                x = f"{r:.2f}".rstrip("0").rstrip(".").replace(".", ",")  # deux décimales, comme publié
                assert f"(volume ×{x} la médiane des 20 séances précédentes)" in txt, (t, txt)
                assert not re.search(r"\b(fort|faible|confirm\w*|valid\w*|signal)\b", txt.split("(volume")[1].split(")")[0]), txt
                n += 1
    assert n > 0


def test_la_remise_a_zero_de_la_mise_en_evidence_suit_la_declaration_de_sym():
    """Vu au navigateur le 22/10/2026 : l'effet `[sym,period]` placé avant
    `const sym` → « Cannot access 'sym' before initialization », écran
    « Erreur de rendu » — invisible aux autres tests."""
    chart = _stockchart(_source())
    assert chart.index("const sym=") < chart.index("useEffect(()=>{setFigFocus(null);},[sym,period]);")


# ── 6. ETE et doubles : le dessin des références classiques, sans projection ─

def _ete(type_, statut="declenchee"):
    sommet = type_ == "ete"
    t = "sommet" if sommet else "creux"
    u = "creux" if sommet else "sommet"
    prix = [100, 90, 110, 91, 101] if sommet else [100, 110, 90, 109, 101]
    dates = ["2026-06-01", "2026-06-10", "2026-06-20", "2026-07-01", "2026-07-10"]
    return {"type": type_, "libelle": "x", "orientation_classique": "baissiere" if sommet else "haussiere",
            "statut": statut, "pivots": [{"date": d, "prix": p, "type": (t if k % 2 == 0 else u),
                                          "date_confirmation": d} for k, (d, p) in enumerate(zip(dates, prix))],
            "date_confirmation": "2026-07-14",
            "niveau_declenchement": {"forme": "oblique", "points": [{"date": dates[1], "prix": prix[1]},
                                                                     {"date": dates[3], "prix": prix[3]}],
                                     "prix_a_la_derniere_seance": prix[3]},
            "niveau_declenchement_bas": None, "niveau_invalidation": None,
            "date_cassure": "2026-07-20" if statut == "declenchee" else None, "date_fin": None,
            "signal": type_ if statut == "declenchee" else None, "frequence_ref": [type_]}


def _formes_de(e, tel=False):
    return _node(_harnais(f"""
const dates=[];for(let d=new Date('2026-05-01');d<=new Date('2026-10-21');d.setDate(d.getDate()+1))dates.push(d.toISOString().slice(0,10));
const e={json.dumps(e)};
console.log(JSON.stringify({{dates:dates.length,f:figFormes([['figures',e,'x']],dates,{{derniere_seance_echangee:'2026-10-21'}},null,{json.dumps(tel)})}}));
"""))


@pytest.mark.parametrize("type_", ["ete", "ete_inversee"])
def test_ete_ligne_de_cou_pleine_aire_translucide_et_reperes(type_):
    r = _formes_de(_ete(type_))
    f = r["f"]
    pleines = [x for x in f if x["k"] == "poly" and not x.get("tirets")]
    assert len(pleines) == 2, f                     # silhouette + ligne de cou, aucune en tirets
    aire = [x for x in f if x["k"] == "aire"]
    assert len(aire) == 1 and 0.08 <= aire[0]["al"] <= 0.12, aire
    assert {x["s"] for x in f if x["k"] == "txt"} == {"Épaule g.", "Tête", "Épaule d."}
    # La ligne de cou va de l'épaule gauche à la cassure, pas au-delà.
    dates = r["dates"]
    debut = min(p[0] for x in pleines for p in x["pts"])
    fin = max(p[0] for x in pleines for p in x["pts"])
    croix = [x for x in f if x["k"] == "croix"]
    assert len(croix) == 1 and fin == croix[0]["i"], (fin, croix)
    assert debut == min(p[0] for p in f[0]["pts"])
    # Aucune projection : rien n'est tracé après la cassure, aucune forme hors liste.
    assert {x["k"] for x in f} <= {"poly", "aire", "txt", "croix"}
    assert all(p[0] <= croix[0]["i"] for x in f if "pts" in x for p in x["pts"])


def test_ete_sur_telephone_abreviations():
    f = _formes_de(_ete("ete"), tel=True)["f"]
    assert [x["s"] for x in f if x["k"] == "txt"] == ["EG", "T", "ED"]


def test_doubles_ligne_de_declenchement_pleine_et_aire(formes):
    vus = 0
    for x in formes:
        if x["e"]["type"] not in ("double_creux", "double_sommet"):
            continue
        tirets = [f for f in x["f"] if f["k"] == "poly" and f.get("tirets")]
        assert not tirets, (x["t"], x["e"]["type"])
        aire = [f for f in x["f"] if f["k"] == "aire"]
        if x["e"]["statut"] in ("declenchee", "armee"):
            assert len(aire) == 1 and 0.08 <= aire[0]["al"] <= 0.12, (x["t"], aire)
        vus += 1
    assert vus > 0


def test_aucune_projection_d_objectif_dans_le_code_de_dessin():
    src = _source()
    dessin = _entre(src, "const FIG_COURT=", "const LegendeFigures=")
    code = re.sub(r"/\*.*?\*/", "", dessin, flags=re.S)
    code = re.sub(r"(?m)^\s*//.*$", "", code)
    assert not re.search(r"objectif|cible|hauteur_tete|projection|report", code, re.I)
