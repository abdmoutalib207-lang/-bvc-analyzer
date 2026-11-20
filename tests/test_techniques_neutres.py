"""Indicateurs techniques sans couleur de signal — lot 1.4, suite de #372 (20/11/2026).

LA RÈGLE
────────
Le vert (#00e5a0) et le rouge (#ff4f5a) disent le SENS D'UNE VARIATION DE
COURS — et les flèches de variation. Un indicateur technique se DÉCRIT (sa
valeur, sa position par rapport à un seuil), il ne se colore pas comme un
signal : un RSI bas peint du vert des hausses se lit comme une invitation.
Les libellés interprétatifs (« suracheté », « survendu », « haussier »,
« baissier », « BEAR », « BULL ») deviennent descriptifs. Valeurs, seuils et
Score BVC inchangés (R8).

Mesuré au navigateur le 20/11/2026 (`data.json` du 19/11, classement + fiches
IAM, ADH, BAL, IBM, plis ouverts) AVANT ce lot : 1 élément technique en
vert/rouge au classement, 14, 15, 14 et 16 sur les quatre fiches ; 8 mots
interprétatifs visibles. Le détail est dans la description de la branche.

CE QUI EST VÉRIFIÉ
──────────────────
Pour chaque zone qui peint un indicateur : ni #00e5a0 ni #ff4f5a, aucun mot
interprétatif écrit ; les nouvelles étiquettes, exécutées sous node, disent
la bonne position ; le texte recoloré se lit (contraste ≥ 4,5:1). Chaque
contrôle a son contrôle négatif sur le code d'avant ce lot.
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parent.parent
SRC = (RACINE / "terminal.src.html").read_text(encoding="utf-8")
NODE = pytest.mark.skipif(not shutil.which("node"), reason="node absent")

SIGNAL = ("#00e5a0", "#ff4f5a", "#ff1744", "0,229,160", "255,79,90")
MOTS = re.compile(r"surachet|survend|surachat|survente|haussi|baissi|\bbull\b|\bbear\b", re.I)
FONDS = {"page": "#080d1a", "carte": "#0d1829", "case": "#0a1220"}


def _bloc(debut: str, fin: str, src: str = SRC) -> str:
    i = src.index(debut)
    return src[i:src.index(fin, i + len(debut))]


def _sans_commentaires(code: str) -> str:
    """Le code exécuté et affiché, sans les commentaires qui racontent l'avant."""
    code = re.sub(r"\{/\*.*?\*/\}", "", code, flags=re.S)
    code = re.sub(r"/\*.*?\*/", "", code, flags=re.S)
    return re.sub(r"(?m)^\s*//.*$", "", code)


def _textes(code: str) -> str:
    """Ce qui peut s'afficher : chaînes JS et texte JSX entre balises."""
    code = _sans_commentaires(code)
    chaines = re.findall(r'"([^"\n]*)"|`([^`]*)`', code)
    jsx = re.findall(r">([^<>{}]+)<", code)
    return " ".join([a or b for a, b in chaines] + jsx)


def controle(code: str) -> list[str]:
    """Défauts d'une zone : couleur de signal, ou mot interprétatif affichable."""
    c = _sans_commentaires(code).lower().replace(" ", "")
    defauts = [f"couleur {x}" for x in SIGNAL if x.replace(" ", "") in c]
    defauts += [f"mot « {m} »" for m in MOTS.findall(_textes(code))]
    return defauts


# ── Contraste WCAG ──────────────────────────────────────────────────────────

def _lin(c: float) -> float:
    c /= 255
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def _lum(h: str) -> float:
    h = h.lstrip("#")
    r, g, b = (_lin(int(h[i:i + 2], 16)) for i in (0, 2, 4))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contraste(a: str, b: str) -> float:
    la, lb = sorted((_lum(a), _lum(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def test_l_arithmetique_du_contraste_est_juste():
    assert contraste("#ffffff", "#000000") == pytest.approx(21.0)
    assert contraste("#777777", "#ffffff") == pytest.approx(4.48, abs=0.01)


def _node(code: str):
    out = subprocess.run(["node", "-e", code], capture_output=True, text=True, check=True).stdout
    return json.loads(out)


def _formats() -> str:
    """Les fonctions de format pures, de `zoneStoch` à `dedoublonnerArticles`."""
    debut = SRC.index("const zoneStoch=")
    fin = SRC.index("const dedoublonnerArticles=", debut)
    return SRC[debut:SRC.index("\n", fin)]


# ── 1. Jauge RSI et tuiles de la fiche ──────────────────────────────────────

def _zones_fiche(src: str = SRC) -> dict[str, str]:
    i = src.index("const Detail=")
    return {
        "jauge RSI": _bloc("const RSIGauge=", "/* ── RED FLAGS", src),
        "tuiles Haut/Bas, MACD, STOCH, OBV, ADX": _bloc('["Haut 90j",', "<RSIGauge value={rsiVal}/>", src[i:]),
        # La ligne « RSI:49 · MA20:… » au-dessus du graphique : son style et
        # son texte. La pastille ● de la source directe, un état, en est exclue.
        "ligne RSI · MA du graphique": _bloc('<span style={{marginLeft:"auto",fontSize:9,color:', ">", src)
        + _bloc('RSI:{(r.rsi??r.rsi14)!=null', "</span>", src),
    }


@pytest.mark.parametrize("zone", list(_zones_fiche()))
def test_aucune_couleur_de_signal_ni_mot_interpretatif_sur_la_fiche(zone):
    assert controle(_zones_fiche()[zone]) == []


AVANT_FICHE = {
    "jauge": 'const color=v>70?"#ff4f5a":v<30?"#00e5a0":"#ffd740";\n'
             '  const label=v>70?"SURACHETÉ":v<30?"SURVENDU":"NEUTRE";',
    "macd": '<div style={{fontSize:11,color:r.macd>0?"#00e5a0":"#ff4f5a",fontWeight:700}}>{r.macd?.toFixed(2)}</div>\n'
            '<div style={{fontSize:9,color:"#8892a4"}}>{r.macd>0&&r.macd>(r.macd_signal||0)?"haussier":"baissier"}</div>',
    "extremes": '{[["Haut 90j",h90!=null?px(h90):"—","#00e5a0"],["Bas 90j",l90!=null?px(l90):"—","#ff4f5a"]]',
    "ligne": '<span style={{marginLeft:"auto",fontSize:9,color:isLive?"#00e5a0":"#8892a4"}}>',
}


@pytest.mark.parametrize("cas", list(AVANT_FICHE))
def test_le_controle_voit_le_code_d_avant(cas):
    """Contrôle négatif : chaque zone, telle qu'elle était, serait refusée."""
    assert controle(AVANT_FICHE[cas])


def test_le_controle_ignore_les_commentaires():
    assert controle('/* « SURACHETÉ » en rouge (#ff4f5a), avant */ const c="#4db8ff";') == []


@NODE
def test_la_jauge_dit_ou_est_le_rsi():
    cas = [100, 70.1, 70, 50, 30, 29.9, 0, None]
    res = _node(_formats() + f"\nconsole.log(JSON.stringify({json.dumps(cas)}.map(zoneRSI)));")
    assert res == ["AU-DESSUS DE 70", "AU-DESSUS DE 70", "ENTRE 30 ET 70", "ENTRE 30 ET 70",
                   "ENTRE 30 ET 70", "SOUS 30", "SOUS 30", ""]


@NODE
def test_le_macd_dit_sa_position_par_rapport_a_sa_moyenne():
    """IAM au 19/11 : MACD −0,25, moyenne −0,80 — l'ancienne étiquette écrivait
    « baissier » pour un MACD passé AU-DESSUS de sa moyenne."""
    cas = [[-0.251, -0.7995], [1.2417, 1.2112], [-1.3398, -1.309], [0.5, 0.5], [1, None], [None, 1]]
    res = _node(_formats() + f"\nconsole.log(JSON.stringify({json.dumps(cas)}.map(([m,s])=>positionMACD(m,s))));")
    assert res == ["au-dessus de sa moyenne", "au-dessus de sa moyenne", "au-dessous de sa moyenne",
                   "égal à sa moyenne", "", ""]


def test_les_valeurs_restent_affichees():
    z = _zones_fiche()["tuiles Haut/Bas, MACD, STOCH, OBV, ADX"]
    for v in ("{r.macd?.toFixed(2)}", "{r.stoch_k?.toFixed(0)}", "{(r.obv/1000).toFixed(0)}K",
              "{zoneStoch(r.stoch_k)}", "{positionMACD(r.macd,r.macd_signal)}",
              'px(h90)', 'px(l90)', 'px(r.h52w)', 'px(r.l52w)'):
        assert v in z, v
    j = _zones_fiche()["jauge RSI"]
    assert "{v.toFixed(0)}" in j and "{label}" in j and "const label=zoneRSI(v);" in j
    assert "[30,70].map(seuil)" in j            # les seuils sont tracés, pas peints


def test_le_texte_recolore_se_lit():
    for c in ("#c8d3e8", "#e8eef8", "#8892a4", "#4db8ff"):
        for nom, f in FONDS.items():
            assert contraste(c, f) >= 4.5, f"{c} sur {nom} : {contraste(c, f):.2f}:1"


def test_le_glossaire_definit_ce_que_disent_les_etiquettes():
    """Les étiquettes renvoient au GLOSSAIRE, qui seul porte la définition."""
    g = _bloc("const GLOSSAIRE={", "\n};")
    assert "au-dessus de 70 les hausses ont dominé, sous 30 les baisses" in g
    assert "comparé à sa moyenne sur 9 séances" in g
    j = _zones_fiche()["jauge RSI"]
    assert '<Terme id="rsi">RSI (14)</Terme>' in j


# ── 2. Graphique : supports et résistances, histogramme MACD, figures ───────

def _zones_graphique(src: str = SRC) -> dict[str, str]:
    return {
        "légende datée S/R": _bloc("const LegendeSR=", "/* ── FIG · TEND · GAP", src),
        "lignes S/R tracées": _bloc("srData.sup.forEach(", "},[sym,period", src),
        "bouton S/R": _bloc("<Btn on={showSR}", "</Btn>", src),
        "légende des tracés": _bloc("── S support", "── R résistance</span>", src),
        "histogramme MACD": _bloc("macdChart.addHistogramSeries(", ".filter(Boolean)", src),
        "niveaux établis": _bloc("{(()=>{const nv=r.niveaux;", "{cv.pivots&&", src),
    }


@pytest.mark.parametrize("zone", list(_zones_graphique()))
def test_aucune_couleur_de_signal_sur_le_graphique(zone):
    assert controle(_zones_graphique()[zone]) == []


def test_les_figures_ne_prennent_plus_la_couleur_de_leur_orientation():
    code = _sans_commentaires(SRC)
    assert "figCoul" not in code and "figSens" not in code
    assert "orientation_classique" not in code      # plus aucune lecture du champ
    assert 'const FIG_COUL="#b388ff";' in SRC
    assert code.count("FIG_COUL") == 3              # définition + tracé + légende


def test_les_gaps_gardent_le_sens_du_saut_de_cours():
    """Exception assumée : un gap est un saut de COURS constaté, à la hausse ou
    à la baisse — vert et rouge y disent un sens de variation, comme une bougie."""
    assert 'e.type==="gap_baissier"?"#ff4f5a":"#00e5a0"' in SRC


AVANT_GRAPHIQUE = {
    "S/R": 'const lignes=[...[...sr.res].reverse().map(L=>["Résistance","#ff4f5a",L]),',
    "histogramme": 'color:(macdData.hist[i]||0)>=0?"#00e5a045":"#ff4f5a45"}',
    "établis": '<div style={{fontSize:8.5,color:"#00e5a0",textTransform:"uppercase"}}>Établis</div>',
}


@pytest.mark.parametrize("cas", list(AVANT_GRAPHIQUE))
def test_le_controle_voit_le_graphique_d_avant(cas):
    assert controle(AVANT_GRAPHIQUE[cas])


def test_supports_et_resistances_restent_distingues_par_le_mot():
    z = _zones_graphique()
    assert "title:`S ${fmtPrixFR(L.niveau)}" in z["lignes S/R tracées"]
    assert "title:`R ${fmtPrixFR(L.niveau)}" in z["lignes S/R tracées"]
    assert '["Résistance",SR_COUL,L]' in z["légende datée S/R"]
    assert '["Support",SR_COUL,L]' in z["légende datée S/R"]
    c = re.search(r'const SR_COUL="(#[0-9a-f]{6})";', SRC).group(1)
    for nom, f in FONDS.items():
        assert contraste(c, f) >= 4.5, nom


# ── 3. Scénarios de prix ────────────────────────────────────────────────────
# Aucun titre n'en publie au 19/11 (objectifs retirés le 01/10/2026) : le bloc
# ne s'affiche pas, mais il reviendrait tel quel si le moteur en republiait.

def _scenarios(src: str = SRC) -> str:
    return _bloc('<Pli titre="Scénarios de prix"', "</Pli>", src)


def test_les_scenarios_ne_parient_plus():
    assert controle(_scenarios()) == []
    s = _sans_commentaires(_scenarios())
    for lbl in ('["BASSE",r.bear,', '["CENTRALE",r.base,', '["HAUTE",r.bull,'):
        assert lbl in s, lbl
    assert "linear-gradient" not in s                        # plus de rouge → vert
    assert "▲" not in s                                      # le cours n'est pas une hausse
    # Le texte qui dit pourquoi rien n'est publié reste.
    assert "les objectifs saisis à la main ont été retirés le 01/10/2026" in s


def test_le_controle_voit_les_scenarios_d_avant():
    assert controle('{[["BEAR",r.bear,"#ff4f5a",ecart(r.bear)],["BULL",r.bull,"#00e5a0",`+${upside}%`]]}'
                    '<span>Bear {px(r.bear)}</span>')


@NODE
def test_l_ecart_au_cours_porte_son_signe():
    """L'ancienne tuile « BULL » forçait un « + » : « +-3.2% » sous le cours."""
    i = SRC.index("const ecart=v=>")
    f = SRC[i:SRC.index("\n", i)]
    res = _node(f"const price=100;{f}\nconsole.log(JSON.stringify([112.34,96.8,100,null].map(ecart)));")
    assert res == ["+12.3%", "-3.2%", "0.0%", "—"]
