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
                       ("const SR_TOL=", "const srCotee="))
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
        "premier": 5 * JOUR, "dernier": 10 * JOUR}], out


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
        "premier": 5 * JOUR, "dernier": 11 * JOUR}], out


def test_un_support_aborde_par_en_dessous_n_est_ni_tenu_ni_casse():
    c = _serie()
    c[4] = {"x": 4 * JOUR, "y": [96, 97, 95, 96], "vol": 10}        # par le dessus, tenu
    c[8] = {"x": 8 * JOUR, "y": [96, 97, 95, 96], "vol": 10}        # par le dessus, tenu
    c[12] = {"x": 12 * JOUR, "y": [93, 93.5, 92.5, 93], "vol": 10}  # passe sous 95
    c[13] = {"x": 13 * JOUR, "y": [93, 96, 93, 95.5], "vol": 10}    # revient par en dessous
    out = _sr(c, 100)
    assert _niveau(out, 95) == [{
        "niveau": 95, "contacts": 3, "dansRole": 2, "tenus": 2,
        "autreRole": 1, "indetermines": 0,
        "premier": 4 * JOUR, "dernier": 13 * JOUR}], out
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


# ── 3. Affichage ─────────────────────────────────────────────────────────────

def test_titre_court_sur_la_ligne_et_legende_datee():
    assert "title:`S ${fmtPrixFR(L.niveau)} · ${L.contacts}×`" in SRC
    assert "title:`R ${fmtPrixFR(L.niveau)} · ${L.contacts}×`" in SRC
    leg = _bloc(SRC, "const LegendeSR=(")
    for mot in ("touché", "tenu", "du ", " au ", "Support", "Résistance",
                "par le dessus", "par le dessous", "par en dessous",
                "sens inconnu"):
        assert mot in leg, mot
    assert '<LegendeSR sr={sr}' in SRC
    # Vocabulaire du produit : des faits, pas une annonce.
    for faux in ("objectif", "rebond", "va ", "cible"):
        assert faux not in leg.lower(), faux


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
                "par le dessus", "ni tenu ni cassé", "Sens inconnu"):
        assert mot in guide, mot
    assert re.search(r"SR_TOL=0\.012, SR_LB=3, SR_MIN_CONTACTS=2;", SRC), (
        "le guide écrit 1,2 %, 3 séances et 2 contacts : le code doit le dire aussi")


def test_index_compile_porte_le_nouveau_calcul():
    assert "SR_MIN_CONTACTS" in COMPILE and "LegendeSR" in COMPILE
