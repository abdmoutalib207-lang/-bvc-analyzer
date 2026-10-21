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
        assert re.search(r" — cassure le \d\d/\d\d(/\d\d)? · après une cassure", p["txt"]), p["txt"]
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
    res[t].par[n]={{pris:el.pris.length,hors:el.hors,formes:f.length,avant,
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
            assert tout["pris"] + tout["hors"] == total, (t, tout, total)


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
    assert chart.index("const figVue=useMemo(") < chart.index("},[figVue,sym,period,liveCandles,etat,plein]);")


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
