"""Supports et résistances du graphique : des séances passées, comptées et datées.

CE QUI ÉTAIT FAUX, ET COMMENT ON LE SAIT (21/10/2026)
─────────────────────────────────────────────────────
`calcSR` prenait ses sommets et ses creux sur TOUTES les séances. Or 8 588 des
58 334 séances de pipeline/candles/ ont un volume nul, et 8 581 d'entre elles
sont plates (o=h=l=c) : jour sans échange, ou séance refaite depuis la seule
clôture du bulletin. Leur plus-bas n'a été atteint par personne, et il
fabriquait des creux. Mesuré sur la fenêtre 3M des 78 titres qui ont un
graphique : DAR (38 séances sur 45 sans échange) passait de 4 niveaux à 0,
SRM perdait ses deux supports.

Le calcul ne comptait pas non plus les contacts : un niveau tiré d'une seule
séance se dessinait comme les autres.

Second passage, même jour : compter les contacts PAR SÉANCE donnait
« touché 19 fois » sur 57 séances pour IAM — les voisines d'un sommet tombent
presque toujours dans la tolérance. Un contact est désormais un ÉPISODE, la
tenue ne se compte que dans le bon rôle, et le mot (Support, Résistance) suit
la position du niveau par rapport à la dernière clôture.

Troisième passage, même jour (lot 1 bis) : les niveaux étaient les 3 creux et
les 3 sommets les plus PROCHES du cours, à ±3 %. Sur 78 titres en 3A, ils
couvraient 13 % de la plage bas–haut de la fenêtre (médiane) et 138 paires
tracées étaient à moins de 1,2 % l'une de l'autre. Ils sont désormais choisis
par nombre de contacts sur toute la fenêtre, espacés d'au moins 1 ATR(14)
relatif (plancher 2,4 %), et la légende date les inversions de rôle.

⚠️ Les attendus sont construits ICI, à la main, sur des séances fabriquées —
jamais recopiés d'une sortie du code testé. Le code est extrait du fichier
servi et exécuté sous node.
"""

import json
import re
from pathlib import Path

from test_graphique_interactif import _bloc, _instruction, _node

RACINE = Path(__file__).resolve().parent.parent
SRC = (RACINE / "terminal.src.html").read_text(encoding="utf-8")
COMPILE = (RACINE / "index.html").read_text(encoding="utf-8")

JOUR = 86_400_000


def _code():
    consts = "\n".join(_instruction(SRC, c) for c in
                       ("const SR_TOL=", "const srCotee=", "const srAtrRel="))
    return f"{consts}\n{_bloc(SRC, 'function calcSR(')}\n"


def _sr(candles, prix, minimum=None):
    arg = "" if minimum is None else f",{minimum}"
    return _node(_code() + f"console.log(JSON.stringify(calcSR("
                 f"{json.dumps(candles)},{prix}{arg})));")


def _hauts(out):
    """Les résistances au-dessus du bruit de base (plus-hauts à 101)."""
    return [L["niveau"] for L in out["res"] if L["niveau"] > 105]


def _serie(n=16, base=(100, 101, 99, 100), vol=10):
    return [{"x": i * JOUR, "y": list(base), "vol": vol} for i in range(n)]


# ── 1. Séances écartées ──────────────────────────────────────────────────────

def test_une_seance_sans_echange_ne_fabrique_pas_de_creux():
    c = _serie()
    c[7] = {"x": 7 * JOUR, "y": [95, 95, 95, 95], "vol": 0}
    c[8] = {"x": 8 * JOUR, "y": [95, 95, 95, 95], "vol": 0}
    out = _sr(c, 100, 1)      # la détection, pas le seuil de contacts
    assert [L["niveau"] for L in out["sup"]] == [99], out
    assert out["ecartees"] == 2


def test_une_seance_plate_avec_volume_est_un_vrai_echange():
    c = _serie()
    c[7] = {"x": 7 * JOUR, "y": [95, 95, 95, 95], "vol": 3}
    c[8] = {"x": 8 * JOUR, "y": [95, 95, 95, 95], "vol": 5}
    out = _sr(c, 100, 1)
    assert 95 in [L["niveau"] for L in out["sup"]], out
    assert out["ecartees"] == 0


def test_la_bougie_du_jour_reconstituee_ne_compte_pas():
    c = _serie()
    c[5] = {"x": 5 * JOUR, "y": [100, 110, 100, 105], "vol": 10}
    c.append({"x": 16 * JOUR, "y": [100, 110, 100, 100], "vol": 50, "live": True})
    out = _sr(c, 100)
    assert _hauts(out) == [] and out["ecartees"] == 1, out
    # La même bougie, réellement échangée, est un second contact.
    del c[-1]["live"]
    assert _hauts(_sr(c, 100)) == [110]


# ── 2. Contacts, tenue, dates ────────────────────────────────────────────────

def _niveau(out, v):
    return [L for L in out["sup"] + out["res"] if L["niveau"] == v]


def test_contacts_tenue_et_dates_d_une_resistance():
    c = _serie()
    c[5] = {"x": 5 * JOUR, "y": [100, 110, 100, 105], "vol": 10}      # tenue
    c[10] = {"x": 10 * JOUR, "y": [104, 110.5, 104, 111], "vol": 10}  # franchie
    out = _sr(c, 100)
    # 110 et 110,5 sont à 0,45 % l'un de l'autre : un seul niveau, 110,25.
    # Les deux contacts arrivent par le dessous (clôtures précédentes à 100).
    assert _niveau(out, 110.25) == [{
        "niveau": 110.25, "contacts": 2, "dansRole": 2, "tenus": 1,
        "autreRole": 0, "indetermines": 0,
        "premier": 5 * JOUR, "dernier": 10 * JOUR,
        "roles": [{"role": "résistance", "n": 2,
                   "premier": 5 * JOUR, "dernier": 10 * JOUR}]}], out


def test_des_seances_consecutives_font_un_seul_contact():
    """Une séance sans échange au milieu ne coupe pas l'épisode."""
    c = _serie()
    c[5] = {"x": 5 * JOUR, "y": [100, 110, 100, 105], "vol": 10}
    c[6] = {"x": 6 * JOUR, "y": [110, 110, 110, 110], "vol": 0}
    c[7] = {"x": 7 * JOUR, "y": [108, 110.4, 107, 109], "vol": 10}
    c[11] = {"x": 11 * JOUR, "y": [104, 110.5, 104, 111], "vol": 10}
    out = _sr(c, 100)
    # Sommets 110,4 (séance 7) et 110,5 (séance 11) : niveau 110,45.
    # Épisode 1 = séances 5 et 7, clôture de fin 109 : tenu.
    # Épisode 2 = séance 11, clôture 111 : franchi.
    assert _niveau(out, 110.45) == [{
        "niveau": 110.45, "contacts": 2, "dansRole": 2, "tenus": 1,
        "autreRole": 0, "indetermines": 0,
        "premier": 5 * JOUR, "dernier": 11 * JOUR,
        "roles": [{"role": "résistance", "n": 2,
                   "premier": 5 * JOUR, "dernier": 11 * JOUR}]}], out


def test_un_support_aborde_par_en_dessous_n_est_ni_tenu_ni_casse():
    c = _serie()
    c[4] = {"x": 4 * JOUR, "y": [96, 97, 95, 96], "vol": 10}        # par le dessus, tenu
    c[8] = {"x": 8 * JOUR, "y": [96, 97, 95, 96], "vol": 10}        # par le dessus, tenu
    c[12] = {"x": 12 * JOUR, "y": [93, 93.5, 92.5, 93], "vol": 10}  # passe sous 95
    c[13] = {"x": 13 * JOUR, "y": [93, 96, 93, 95.5], "vol": 10}    # revient par en dessous
    out = _sr(c, 100)
    # Rôles dans l'ordre : support (séances 4 et 8), puis résistance (13).
    assert _niveau(out, 95) == [{
        "niveau": 95, "contacts": 3, "dansRole": 2, "tenus": 2,
        "autreRole": 1, "indetermines": 0,
        "premier": 4 * JOUR, "dernier": 13 * JOUR,
        "roles": [{"role": "support", "n": 2, "premier": 4 * JOUR, "dernier": 8 * JOUR},
                  {"role": "résistance", "n": 1, "premier": 13 * JOUR, "dernier": 13 * JOUR}]}], out
    assert _niveau(out, 95)[0] in out["sup"]


def test_un_contact_en_debut_de_fenetre_a_un_sens_inconnu():
    c = _serie()
    c[0] = {"x": 0, "y": [100, 110, 100, 105], "vol": 10}
    c[5] = {"x": 5 * JOUR, "y": [100, 110, 100, 105], "vol": 10}
    L = _niveau(_sr(c, 100), 110)
    assert L and L[0]["contacts"] == 2 and L[0]["indetermines"] == 1, L
    assert L[0]["dansRole"] == 1 and L[0]["tenus"] == 1


def test_le_mot_suit_la_position_par_rapport_a_la_derniere_cloture():
    """Cas IAM du 21/10 : un creux à 89,90 au-dessus d'une clôture à 88,40."""
    c = _serie()
    for i in (13, 14, 15):
        c[i] = {"x": i * JOUR, "y": [99, 99.5, 97.5, 98], "vol": 10}
    out = _sr(c, 98, 1)
    assert 99 in [L["niveau"] for L in out["res"]], out    # creux, mais au-dessus
    assert 99 not in [L["niveau"] for L in out["sup"]], out


def test_un_niveau_touche_une_seule_fois_n_est_pas_trace():
    c = _serie()
    c[5] = {"x": 5 * JOUR, "y": [100, 110, 100, 105], "vol": 10}
    assert _hauts(_sr(c, 100)) == []
    assert _hauts(_sr(c, 100, 1)) == [110]
    # 99, 101 et 110 : chacun n'est touché que par UN épisode (les séances de
    # base se suivent toutes dans la tolérance de 99 et de 101).
    assert _sr(c, 100)["retires"] == 3


# ── 3. Sélection par importance (lot 1 bis, 21/10/2026) ─────────────────────
#
# Avant : les 3 creux et les 3 sommets les plus PROCHES du cours, à ±3 %.
# Mesuré sur 78 titres en 3A : 13 % de la plage bas–haut couverte (médiane),
# 138 paires tracées à moins de 1,2 % l'une de l'autre. ADH : 6 lignes entre
# 35,25 et 36,62 pour une plage de 14 à 48.

def _plat(n, prix=100, vol=10):
    return [{"x": i * JOUR, "y": [prix] * 4, "vol": vol} for i in range(n)]


def _poser(c, seances, bougie):
    for i in seances:
        c[i] = {"x": i * JOUR, "y": list(bougie), "vol": 10}
    return c


def test_les_niveaux_sont_choisis_par_contacts_et_non_par_proximite():
    """Quatre niveaux sous le cours, trois places : le moins touché sort.

    Bandes de contact (±1,2 %) calculées à la main :
    · 100 (la base) — coupée par les plongées à 80 et à 90 : 6 épisodes ;
    · 80 — séances 5, 15, 25 : 3 contacts, à 20 % sous le cours ;
    · 97 — séances 30, 34 : 2 contacts, le dernier à la séance 34 ;
    · 90 — séances 10, 20 : 2 contacts, le dernier à la séance 20.
    97 et 90 sont à égalité : le contact le plus récent départage. L'ancien
    calcul gardait 90, 97 et 100 — les plus proches — et jamais 80.
    """
    c = _plat(40)
    _poser(c, (5, 15, 25), (85, 86, 80, 85))
    _poser(c, (10, 20), (91, 92, 90, 91))
    _poser(c, (30, 34), (98, 99, 97, 98))
    out = _sr(c, 100)
    assert [L["niveau"] for L in out["sup"]] == [80, 97, 100], out
    assert out["res"] == [] and out["ecartes"] == 0
    assert [L["contacts"] for L in out["sup"]] == [3, 2, 6]


def test_deux_niveaux_traces_sont_espaces_d_au_moins_l_ecart_minimal():
    """90 et 92 sont à 2,2 % : au-delà de la tolérance (deux niveaux), en deçà
    du plancher de 2,4 % (un seul tracé). 92 est touché 5 fois — ses bandes
    accrochent aussi les plongées à 90 — contre 3 : 90 est écarté.

    ATR(14) à la main, séances 26 à 39 : étendues vraies 8 et 7 deux fois
    (plongée à 92 depuis 100, puis retour), zéro ailleurs — 30 / 14 = 2,14 %,
    sous le plancher.
    """
    c = _plat(40)
    _poser(c, (5, 12, 19), (91, 92, 90, 91))
    _poser(c, (26, 33), (93, 94, 92, 93))
    out = _sr(c, 100)
    assert [L["niveau"] for L in out["sup"]] == [92, 100], out
    assert [L["contacts"] for L in out["sup"]] == [5, 6]
    assert out["ecartes"] == 1
    assert abs(out["atr"] - 30 / 14 / 100) < 1e-12
    assert out["ecart"] == 0.024


def _atr(cot):
    code = _instruction(SRC, "const SR_TOL=") + "\n" + _instruction(SRC, "const srAtrRel=")
    return _node(code + f"\nconsole.log(JSON.stringify(srAtrRel({json.dumps(cot)})));")


def test_l_atr_est_la_moyenne_des_14_dernieres_etendues_vraies():
    # Étendue 6 à chaque séance, clôture 100 : 6 %.
    assert abs(_atr([{"y": [100, 103, 97, 100]}] * 16) - 0.06) < 1e-12
    # Saut de 100 à 110 : l'étendue vraie part de la clôture précédente (11),
    # pas du seul plus-haut − plus-bas (2). 11 / 110 = 10 %.
    assert abs(_atr([{"y": [100, 101, 99, 100]}, {"y": [110, 111, 109, 110]}]) - 0.1) < 1e-12
    # Seules les 14 dernières comptent : 20 séances d'étendue 20, puis 14 de 2.
    serie = [{"y": [100, 110, 90, 100]}] * 20 + [{"y": [100, 101, 99, 100]}] * 14
    assert abs(_atr(serie) - 0.02) < 1e-12
    assert _atr([{"y": [100, 101, 99, 100]}]) is None


def test_l_ecart_suit_l_atr_au_dessus_du_plancher():
    c = [{"x": i * JOUR, "y": [100, 103, 97, 100], "vol": 10} for i in range(16)]
    out = _sr(c, 100)
    assert abs(out["ecart"] - 0.06) < 1e-12 and abs(out["atr"] - 0.06) < 1e-12


def test_une_inversion_de_role_est_datee():
    """Le cours vit à 90, touche 95 deux fois par-dessous (séances 3 et 7),
    passe à 100, puis revient sur 95 trois fois par-dessus (13, 17, 21) et
    clôture au-dessus à chaque fois. 95 est sous le cours : Support."""
    c = _plat(10, 90) + [{"x": i * JOUR, "y": [100] * 4, "vol": 10} for i in range(10, 25)]
    _poser(c, (3, 7), (91, 95, 91, 91))
    _poser(c, (13, 17, 21), (99, 99.5, 95, 99))
    out = _sr(c, 100)
    assert _niveau(out, 95) == [{
        "niveau": 95, "contacts": 5, "dansRole": 3, "tenus": 3,
        "autreRole": 2, "indetermines": 0,
        "premier": 3 * JOUR, "dernier": 21 * JOUR,
        "roles": [{"role": "résistance", "n": 2, "premier": 3 * JOUR, "dernier": 7 * JOUR},
                  {"role": "support", "n": 3, "premier": 13 * JOUR, "dernier": 21 * JOUR}]}], out
    assert _niveau(out, 95)[0] in out["sup"]
    # La phrase : la date du dernier contact dans l'ancien rôle (séance 7 =
    # 08/01/1970), et le nombre de contacts de chaque rôle.
    assert _suite(_niveau(out, 95)[0], True, False) == (
        " — 5 contacts : résistance jusqu'au 08/01 (2), support depuis (3, tenu 3)")


# ── 4. Légende ───────────────────────────────────────────────────────────────

def _suite(L, support, an):
    code = "\n".join(_instruction(SRC, c) for c in ("const srJour=", "const srSuite="))
    return _node(code + f"\nconsole.log(JSON.stringify(srSuite({json.dumps(L)},"
                 f"{json.dumps(support)},{json.dumps(an)})));")


def test_legende_d_un_niveau_a_un_seul_role():
    L = {"contacts": 4, "dansRole": 3, "tenus": 2, "autreRole": 0, "indetermines": 1,
         "premier": 5 * JOUR, "dernier": 12 * JOUR,
         "roles": [{"role": "support", "n": 3, "premier": 6 * JOUR, "dernier": 12 * JOUR}]}
    assert _suite(L, True, False) == (
        " — 4 contacts, du 06/01 au 13/01 : 3 par-dessus, tenu 2 · 1 sens inconnu")
    # Un support touché seulement par-dessous : un seul compte, celui de l'autre côté.
    L2 = {**L, "dansRole": 0, "tenus": 0, "autreRole": 3, "indetermines": 1,
          "roles": [{"role": "résistance", "n": 3, "premier": 6 * JOUR, "dernier": 12 * JOUR}]}
    assert _suite(L2, True, True) == (
        " — 4 contacts, du 06/01/70 au 13/01/70 : 3 par-dessous · 1 sens inconnu")


def test_legende_de_roles_alternes():
    """Trois séquences : la dernière et sa date de début, puis les comptes."""
    L = {"contacts": 6, "dansRole": 2, "tenus": 1, "autreRole": 4, "indetermines": 0,
         "premier": 0, "dernier": 30 * JOUR,
         "roles": [{"role": "résistance", "n": 1, "premier": 0, "dernier": 0},
                   {"role": "support", "n": 4, "premier": 5 * JOUR, "dernier": 20 * JOUR},
                   {"role": "résistance", "n": 1, "premier": 30 * JOUR, "dernier": 30 * JOUR}]}
    assert _suite(L, False, False) == (
        " — 6 contacts, résistance depuis le 31/01 : 2 par-dessous, tenu 1 · 4 par-dessus")


def test_legende_d_une_inversion_vers_le_role_oppose_a_la_position():
    """Touché par-dessus puis par-dessous, et le cours est remonté au-dessus
    sans le retoucher : Support par la position, résistance au dernier contact.
    « tenu » s'accroche au rôle de la position, ici la première séquence."""
    L = {"contacts": 3, "dansRole": 2, "tenus": 2, "autreRole": 1, "indetermines": 0,
         "premier": 4 * JOUR, "dernier": 13 * JOUR,
         "roles": [{"role": "support", "n": 2, "premier": 4 * JOUR, "dernier": 8 * JOUR},
                   {"role": "résistance", "n": 1, "premier": 13 * JOUR, "dernier": 13 * JOUR}]}
    assert _suite(L, True, False) == (
        " — 3 contacts : support jusqu'au 09/01 (2, tenu 2), résistance depuis (1)")


def test_titre_court_sur_la_ligne_et_legende_datee():
    assert "title:`S ${fmtPrixFR(L.niveau)} · ${L.contacts}×`" in SRC
    assert "title:`R ${fmtPrixFR(L.niveau)} · ${L.contacts}×`" in SRC
    leg = _bloc(SRC, "const LegendeSR=(")
    suite = _instruction(SRC, "const srSuite=")
    assert "srSuite(L,nom===\"Support\",an)" in leg
    for mot in ("Support", "Résistance", "pctFR(sr.ecart)", "SR_PAR_COTE",
                "les plus touchés"):
        assert mot in leg, mot
    for mot in ("contact", "tenu", "du ", " au ", "par-dessus", "par-dessous",
                "sens inconnu", "jusqu'au", "depuis"):
        assert mot in suite, mot
    assert '<LegendeSR sr={sr}' in SRC
    # Vocabulaire du produit : des faits, pas une annonce.
    for faux in ("objectif", "rebond", "va ", "cible", "achet", "vend"):
        assert faux not in (leg + suite).lower(), faux


def test_la_legende_passe_a_10_px_sur_telephone():
    """Trois lignes par niveau à 390 px avant ; deux au plus visé."""
    assert "@media (max-width:640px){.legende-sr .sr-ligne{font-size:10px;}" in SRC
    assert ".legende-sr{padding-left:6px!important;padding-right:6px!important;}" in SRC
    assert 'className="sr-ligne"' in _bloc(SRC, "const LegendeSR=(")


def test_le_resultat_est_declare_avant_l_effet_qui_le_lit():
    """« Cannot access … before initialization » a déjà cassé tout le terminal."""
    chart = _bloc(SRC, "const StockChart=({r})=>{")
    assert chart.index("const sr=useMemo(") < chart.index(",mas,sr]);")


def test_les_regles_sont_publiees_dans_comment_lire():
    guide = SRC[SRC.index("const Guide=("):]
    guide = guide[:guide.index("\n};\n")]
    for mot in ("Contact", "épisode", "Tenu", "1,2 %", "2 contacts",
                "volume nul", "Séances écartées", "restent dessinées",
                "3 séances", "ne le coupe pas", "Le mot suit la position",
                "Par-dessus", "par-dessous", "ni tenu ni cassé", "Sens inconnu",
                # lot 1 bis
                "Niveaux retenus", "les plus touchés", "non les plus proches",
                "au plus 3 au-dessus", "Écart minimal", "ATR(14)", "2,4 %",
                "écarté, pas fusionné", "La même tolérance de 1,2 %",
                "Inversion", "jusqu'au", "alterné"):
        assert mot in guide, mot
    assert re.search(r"SR_TOL=0\.012, SR_LB=3, SR_MIN_CONTACTS=2, SR_PAR_COTE=3, SR_ATR=14;", SRC), (
        "le guide écrit 1,2 %, 3 séances, 2 contacts, 3 par côté et ATR(14) : le code doit le dire aussi")
    # Plancher de l'écart = 2 × la tolérance, écrit 2,4 % dans le guide.
    assert "Math.max(atr||0,2*SR_TOL)" in _bloc(SRC, "function calcSR(")
    # Plus de filtre à ±3 % autour du cours.
    assert "price*1.03" not in SRC and "price*0.97" not in SRC


def test_index_compile_porte_le_nouveau_calcul():
    for nom in ("SR_MIN_CONTACTS", "LegendeSR", "SR_PAR_COTE", "srAtrRel", "srSuite"):
        assert nom in COMPILE, nom


# ── 5. Les règles tiennent sur tous les titres ───────────────────────────────

def test_les_regles_tiennent_sur_les_chandelles_de_tous_les_titres():
    """Propriétés du CODE, vérifiées sur les séries réelles : au plus 3 niveaux
    de chaque côté, 2 contacts au moins, et aucune paire tracée à moins de
    l'écart minimal. Fenêtres 3M, 1A et 3A finissant à la dernière séance du
    fichier — indépendant de la date du jour."""
    script = _code() + r"""
const fs=require('fs'),path=require('path');
const dir=process.argv[1];const viol=[];let vus=0;
for(const f of fs.readdirSync(dir).filter(f=>f.endsWith('.json'))){
  let s=JSON.parse(fs.readFileSync(path.join(dir,f),'utf8'));s=Array.isArray(s)?s:(s.candles||[]);
  if(s.length<5)continue;
  const fin=new Date(s[s.length-1].d).getTime();
  for(const jours of [90,365,1095]){
    const w=s.filter(c=>new Date(c.d).getTime()>=fin-jours*86400000);
    let prev=null;
    const c=w.map(x=>{const o=x.o!=null?x.o:(prev!=null?prev:x.c);const h=x.h!=null?x.h:Math.max(o,x.c);const l=x.l!=null?x.l:Math.min(o,x.c);prev=x.c;return{x:new Date(x.d).getTime(),y:[o,h,l,x.c],vol:x.v||0};});
    if(c.length<5)continue;
    const r=calcSR(c,c[c.length-1].y[3]);vus++;
    if(r.sup.length>3||r.res.length>3)viol.push([f,jours,'plus de 3']);
    const t=[...r.sup,...r.res];
    if(t.some(L=>L.contacts<2))viol.push([f,jours,'moins de 2 contacts']);
    if(t.length&&!(r.ecart>=0.024))viol.push([f,jours,'écart sous le plancher']);
    const v=t.map(L=>L.niveau).sort((a,b)=>a-b);
    for(let i=1;i<v.length;i++)if((v[i]-v[i-1])/v[i-1]<r.ecart)viol.push([f,jours,v[i-1],v[i],r.ecart]);
  }
}
console.log(JSON.stringify({vus,viol}));
"""
    node = __import__("shutil").which("node")
    if not node:                                    # pragma: no cover
        import pytest
        pytest.skip("node absent de cette machine")
    r = __import__("subprocess").run([node, "-e", script, str(RACINE / "pipeline" / "candles")],
                                     capture_output=True, text=True, timeout=120)
    assert r.returncode == 0, r.stderr
    out = json.loads(r.stdout)
    assert out["vus"] >= 150, out["vus"]
    assert out["viol"] == [], out["viol"][:10]
