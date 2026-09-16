"""Le graphique, le bandeau, le retour en arrière — et les red flags.

HUIT DEMANDES DE NOURE, LE 16/09/2026
────────────────────────────────────
Ce fichier couvre celles qui se vérifient sans navigateur. Les autres ont été
mesurées au navigateur avant livraison ; le relevé est dans la demande de
fusion, pas ici : un test qui exige Chromium ne tournerait pas en intégration
continue, et un test qui ne tourne pas ne protège rien.

CE QUI ÉTAIT CASSÉ, ET COMMENT ON LE SAIT
─────────────────────────────────────────
« Sur le graphique y a toujours affiché historique indisponible même avec des
bougies, cette mention prend beaucoup d'espace. »

Mesuré au navigateur : le message était bien présent, **haut de 220 pixels**,
au-dessus de **trois graphiques qui fonctionnaient**. La cause tenait en une
ligne : l'indisponibilité s'écrivait en `innerHTML` DANS le conteneur du
graphique, et rien ne l'effaçait — `createChart` ajoutait ensuite le graphique
SOUS le message.

D'où la règle testée ici : **le conteneur du graphique ne reçoit jamais de
texte**. Ce qui est de l'état d'interface se rend en React, à côté, sur 34
pixels, et distingue « en cours de chargement » d'« indisponible » — deux
choses que l'ancien code disait de la même façon.

⚠️ Les tests qui EXÉCUTENT du JavaScript le font sous node, sur le code
réellement publié, extrait du fichier. L'attendu ne vient jamais de ce code :
il est construit ici.
"""

import json
import re
import shutil
import subprocess
import textwrap
from pathlib import Path

import pytest

from conftest import chemin_data_json  # noqa: E402

RACINE = Path(__file__).resolve().parent.parent
FRONT = RACINE / "index.html"


def _source():
    return FRONT.read_text(encoding="utf-8")


def _bloc(src, debut):
    """Le texte d'une construction JS, de `debut` à son accolade fermante.

    ⚠️ L'accolade du CORPS n'est pas la première rencontrée. `const
    StockChart=({r})=>{` en porte une dans sa liste de paramètres : compter à
    partir d'elle rend la signature seule, et tous les contrôles passent au
    vert sur une chaîne de vingt caractères. On ne retient donc que les
    accolades ouvertes hors parenthèses.
    """
    i = src.index(debut)
    par = 0
    j = None
    for k in range(i, len(src)):
        c = src[k]
        if c == "(":
            par += 1
        elif c == ")":
            par -= 1
        elif c == "{" and par == 0:
            j = k
            break
    assert j is not None, f"corps introuvable après {debut!r}"
    p = 0
    for k in range(j, len(src)):
        if src[k] == "{":
            p += 1
        elif src[k] == "}":
            p -= 1
            if p == 0:
                return src[i:k + 1]
    raise AssertionError(f"accolade non refermée après {debut!r}")


def _instruction(src, debut):
    i = src.index(debut)
    p = 0
    for k in range(i, len(src)):
        c = src[k]
        if c in "([{":
            p += 1
        elif c in ")]}":
            p -= 1
        elif c == ";" and p == 0:
            return src[i:k + 1]
    raise AssertionError(f"instruction non terminée après {debut!r}")


def _node(script):
    node = shutil.which("node")
    if not node:                                    # pragma: no cover
        pytest.skip("node absent de cette machine")
    r = subprocess.run([node, "-e", script], capture_output=True, text=True,
                       timeout=60)
    assert r.returncode == 0, f"node a échoué :\n{r.stderr}"
    return json.loads(r.stdout)


# ── 1. Le message d'indisponibilité ne s'écrit plus dans le graphique ────────

def test_le_conteneur_du_graphique_ne_recoit_jamais_de_texte():
    """Aucun `innerHTML` non vide sur les conteneurs de graphique.

    C'est LA règle qui empêche le défaut de revenir. Un message écrit dans le
    conteneur survit à la création du graphique : il n'est pas remplacé, il est
    poussé vers le haut, et il y reste pour de bon.
    """
    chart = _bloc(_source(), "const StockChart=({r})=>{")
    ecritures = re.findall(r"ref(?:Main|Vol|Macd)\.current\.innerHTML\s*=\s*([^;]+);",
                           chart)
    assert ecritures, "plus aucune remise à zéro des conteneurs : le graphique "
    for e in ecritures:
        assert e.strip() in ('""', "''"), (
            f"le conteneur du graphique reçoit du contenu : {e.strip()[:80]} — "
            "c'est ainsi que « Données historiques non disponibles » est resté "
            "collé au-dessus d'un graphique qui marchait")


def test_les_quatre_etats_du_graphique_sont_distingues():
    """« En chargement » n'est pas « indisponible », et « trop court » non plus.

    L'ancien code rendait le même message dans les trois cas. Un utilisateur qui
    lit « indisponible » pendant que ça charge conclut que le titre n'a pas
    d'historique.
    """
    chart = _bloc(_source(), "const StockChart=({r})=>{")
    for etat in ("chargement", "court", "vide"):
        assert f'"{etat}"' in chart or f"'{etat}'" in chart, (
            f"l'état « {etat} » a disparu du graphique")
    assert "MESSAGES" in chart, "les trois messages ne sont plus distincts"
    # Et le message ne doit plus occuper la hauteur d'un graphique : il en
    # faisait 220, autant que le graphique lui-même.
    hauteur = re.search(r"msg&&\(\s*<div style=\{\{height:(\d+)", chart)
    assert hauteur and int(hauteur.group(1)) <= 60, (
        "le bandeau d'état reprend la hauteur d'un graphique")


# ── 2. Les moyennes ne sont plus tracées par défaut ──────────────────────────

def test_les_moyennes_sont_eteintes_au_premier_affichage():
    """MA20, MA50 et MA200 partent éteintes — la demande de Noure.

    ⚠️ On EXÉCUTE l'initialiseur publié, avec un `localStorage` vide, plutôt
    que de relire le code : « il existe un `false` quelque part » ne dit pas
    que l'état de départ est éteint.
    """
    init = _instruction(_source(), "const [mas,setMas]=useState(")
    corps = init[init.index("useState(") + len("useState("):init.rindex(")")]
    script = textwrap.dedent("""
        const localStorage = {getItem: () => null, setItem: () => {}};
        const f = %s;
        console.log(JSON.stringify(f()));
    """) % corps
    etat = _node(script)
    assert etat == {"20": False, "50": False, "200": False}, (
        f"les moyennes ne partent pas éteintes : {etat}")


def test_le_choix_des_moyennes_est_relu_quand_il_existe():
    """Un choix mémorisé est repris — sinon le réglage se referait sans cesse."""
    init = _instruction(_source(), "const [mas,setMas]=useState(")
    corps = init[init.index("useState(") + len("useState("):init.rindex(")")]
    script = textwrap.dedent("""
        const stock = {"20": true, "50": false, "200": true};
        const localStorage = {getItem: () => JSON.stringify(stock), setItem: () => {}};
        const f = %s;
        console.log(JSON.stringify(f()));
    """) % corps
    assert _node(script) == {"20": True, "50": False, "200": True}


def test_les_trois_moyennes_sont_proposees():
    """MA200 n'était tracée nulle part alors que la fiche l'affiche en chiffre."""
    chart = _bloc(_source(), "const StockChart=({r})=>{")
    assert "calcMA(closes,200)" in chart, "la MA200 n'est toujours pas calculée"
    for p in (20, 50, 200):
        assert f">MA{p}<" in chart, f"pas de bouton MA{p}"


# ── 3. Fibonacci, au même rang que les autres indicateurs ────────────────────

def test_fibonacci_se_trace_sur_le_graphique():
    """Le titre promettait « Fibonacci » et le graphique n'en portait aucun.

    Il devient un interrupteur comme BB, ICHI et S/R, et il se calcule sur la
    FENÊTRE AFFICHÉE — pas sur les 90 jours figés du tableau de la fiche. Les
    deux plages ne peuvent pas coïncider dès qu'on regarde autre chose que
    trois mois, et les confondre tromperait l'œil.
    """
    chart = _bloc(_source(), "const StockChart=({r})=>{")
    assert "showFib" in chart and ">FIB<" in chart, "pas d'interrupteur Fibonacci"
    bloc_fib = chart[chart.index("if(showFib)"):]
    assert "calcFib(" in bloc_fib[:600], "Fibonacci n'est pas calculé"
    assert "createPriceLine" in bloc_fib[:600], "Fibonacci n'est pas tracé"
    assert "c.y[1]" in bloc_fib[:600] and "c.y[2]" in bloc_fib[:600], (
        "Fibonacci ne se calcule pas sur les extrêmes des chandelles affichées")


def test_le_titre_du_graphique_ne_promet_plus_ce_qu_il_ne_montre_pas():
    s = _source()
    assert "Graphique Chandeliers · MA20 · MA50 · Fibonacci" not in s, (
        "le titre annonce encore des tracés devenus optionnels")


# ── 4. Le bandeau porte toute la cote ────────────────────────────────────────

def _lancer_bandeau(codes):
    src = _source()
    expr = _instruction(src, "const items=rows.filter(")
    tk = _instruction(src, "const tk=")
    lignes = [{"symbol": c, "code_bvc": c, "price": 100 + i, "chg": 0}
              for i, c in enumerate(codes)]
    script = textwrap.dedent("""
        %s
        const rows = %s;
        %s
        console.log(JSON.stringify(items.map(d => tk(d))));
    """) % (tk, json.dumps(lignes), expr)
    return _node(script)


def test_le_bandeau_ne_coupe_plus_la_cote_en_deux():
    """Les 80 titres défilent, pas 40.

    ⚠️ Le `slice(0,40)` ne montrait pas « quarante titres au hasard » : il
    montrait toujours LES MÊMES, ceux qui figurent en tête du tri du moment.
    Un bandeau de cotation qui trie est un bandeau qui cache.
    """
    codes = [f"T{i:02d}" for i in range(80)]
    vus = _lancer_bandeau(codes)
    assert len(vus) == 80, f"{len(vus)} titres sur 80 dans le bandeau"
    assert set(vus) == set(codes)


def test_le_bandeau_suit_un_ordre_stable():
    """L'ordre alphabétique, pas celui du classement — qui change à chaque run."""
    desordre = ["VCNE", "ADH", "SNA", "MSA", "CIM", "BCP"]
    assert _lancer_bandeau(desordre) == sorted(desordre)


def test_la_vitesse_du_bandeau_ne_depend_pas_du_nombre_de_titres():
    """Doubler la liste doublerait la vitesse si la durée restait fixe.

    La durée est proportionnelle au nombre d'éléments : l'allure perçue reste
    celle d'avant.
    """
    src = _source()
    m = re.search(r"animationDuration:`\$\{([^}]+)\}s`", src)
    assert m, "la durée du défilement n'est plus calculée"
    script = textwrap.dedent("""
        const f = (n) => { const items = {length: n}; return %s; };
        console.log(JSON.stringify({q40: f(40), q80: f(80)}));
    """) % m.group(1)
    d = _node(script)
    assert d["q80"] == pytest.approx(2 * d["q40"], rel=0.05), (
        f"la durée ne suit pas le nombre de titres : {d}")


# ── 5. Le retour en arrière ──────────────────────────────────────────────────

def test_la_pile_de_navigation_empile_vraiment():
    """La garde ne doit pas écarter la vue qu'on vient justement d'empiler.

    ⚠️ PREMIER JET FAUTIF, ET C'EST POURQUOI CE TEST EXÉCUTE LE CODE. La garde
    comparait la vue empilée à la vue COURANTE — or on empile toujours la vue
    courante. Elle sortait donc à chaque fois, la pile restait vide, et le
    bouton naissait grisé. Relire le source n'aurait rien montré : le code
    « avait l'air » juste.
    """
    empiler = _bloc(_source(), "const empiler=(t,sl)=>{")
    corps = empiler[empiler.index("=>") + 2:]
    script = textwrap.dedent("""
        const pile = {current: []};
        let peutRevenir = false;
        const setPeutRevenir = (v) => { peutRevenir = v; };
        let tab = "ranking", sel = "CMT";
        const empiler = (t, sl) => %s;
        empiler(tab, sel);                 // ouverture d'une fiche
        empiler(tab, sel);                 // le doublon du même geste
        tab = "detail";
        empiler(tab, sel);                 // changement de titre
        console.log(JSON.stringify({pile: pile.current, peutRevenir}));
    """) % corps
    r = _node(script)
    assert r["peutRevenir"] is True, "le bouton de retour resterait grisé"
    assert r["pile"] == [{"tab": "ranking", "sel": "CMT"},
                         {"tab": "detail", "sel": "CMT"}], (
        f"pile obtenue : {r['pile']} — le doublon d'un même geste doit être "
        "écarté, mais pas les vues distinctes")


def test_le_bouton_de_retour_existe_et_se_desactive():
    s = _source()
    assert "◀ RETOUR" in s, "pas de bouton de retour"
    assert "disabled={!peutRevenir}" in s, (
        "le bouton reste cliquable quand il n'y a rien derrière")


# ── 6. Les red flags s'expliquent, et le chiffre cité reste vrai ─────────────

def test_le_panneau_red_flags_dit_d_ou_vient_le_nombre():
    """Une explication qui n'avoue pas l'origine du chiffre n'explique rien.

    Le nombre vient d'une table écrite à la main dans le moteur. Le panneau
    doit le dire, et dire aussi ce qu'il FAIT — la pénalité, elle, est
    parfaitement définie.
    """
    comp = _bloc(_source(), "const RedFlags=({n})=>{")
    assert "0,30" in comp, "la pénalité n'est pas chiffrée"
    assert re.search(r"table.{0,40}(écrite|main)", comp), (
        "le panneau ne dit pas que le nombre vient d'une table écrite à la main")
    assert "R8" in comp, "le panneau ne dit pas pourquoi ça ne se corrige pas ici"


def test_les_chiffres_cites_par_le_panneau_decrivent_les_donnees_publiees():
    """⚠️ Un texte qui cite des comptes vieillit. Celui-ci est confronté au
    `data.json` publié : s'il devient faux, ce test le dit.

    C'est la même famille que les tests qui relisent les données plutôt que le
    code. Il passera au rouge le jour où la table des red flags bougera — et ce
    jour-là, le texte devra bouger aussi.
    """
    comp = _bloc(_source(), "const RedFlags=({n})=>{")
    d = json.loads(chemin_data_json().read_text(encoding="utf-8"))
    from collections import Counter
    c = Counter(int(t.get("flags") or 0) for t in d["tickers"])
    penalises = sorted(t["symbol"] for t in d["tickers"]
                       if int(t.get("flags") or 0) >= 3)

    cite = re.search(r"(\d+) à\s*\n?\s*zéro, (\d+) à un, (\d+) à deux, (\d+) à trois, (\d+) à quatre",
                     comp.replace("\n", " ").replace("  ", " "))
    assert cite, "le panneau ne cite plus la répartition"
    attendu = [c.get(i, 0) for i in range(5)]
    obtenu = [int(x) for x in cite.groups()]
    assert obtenu == attendu, (
        f"le panneau annonce {obtenu}, les données publiées disent {attendu}")

    for t in penalises:
        assert t in comp, f"{t} est pénalisé mais absent du panneau"
    annonces = re.search(r"pénalisés\s*—\s*([A-Z, ]+)\.", comp.replace("\n", " "))
    if annonces:
        liste = sorted(x.strip() for x in annonces.group(1).split(",") if x.strip())
        assert liste == penalises, (
            f"le panneau annonce {liste}, les données disent {penalises}")


# ── 7. Agrandir, et en sortir ────────────────────────────────────────────────

def test_le_plein_ecran_existe_et_se_referme():
    """Un plein écran dont on ne sort pas est un piège, pas une fonction."""
    chart = _bloc(_source(), "const StockChart=({r})=>{")
    assert "AGRANDIR" in chart, "pas de bouton d'agrandissement"
    assert 'e.key==="Escape"' in chart, "Échap ne referme pas le plein écran"
    assert "Fermer" in chart, "aucun bouton de fermeture visible"
    assert re.search(r"plein\?Math\.max\(", chart), (
        "la hauteur du graphique ne profite pas du plein écran")


def test_le_zoom_se_reinitialise():
    """Une fois zoomé, il faut un chemin de retour autre que changer de période."""
    chart = _bloc(_source(), "const StockChart=({r})=>{")
    assert "dblclick" in chart, "le double-clic ne ramène pas à la vue entière"
    assert "reinitialiser" in chart, "pas de bouton de réinitialisation"
    assert "Molette : zoom" in chart, (
        "rien n'indique à l'écran que le graphique se manipule")
