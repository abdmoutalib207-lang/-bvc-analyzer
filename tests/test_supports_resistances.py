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
    out = _sr(c, 100)
    assert [L["niveau"] for L in out["sup"]] == [99], out
    assert out["ecartees"] == 2


def test_une_seance_plate_avec_volume_est_un_vrai_echange():
    c = _serie()
    c[7] = {"x": 7 * JOUR, "y": [95, 95, 95, 95], "vol": 3}
    c[8] = {"x": 8 * JOUR, "y": [95, 95, 95, 95], "vol": 5}
    out = _sr(c, 100)
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

def test_contacts_tenue_et_dates_d_une_resistance():
    c = _serie()
    c[5] = {"x": 5 * JOUR, "y": [100, 110, 100, 105], "vol": 10}      # tenue
    c[10] = {"x": 10 * JOUR, "y": [104, 110.5, 104, 111], "vol": 10}  # franchie
    out = _sr(c, 100)
    # 110 et 110,5 sont à 0,45 % l'un de l'autre : un seul niveau, 110,25.
    assert [L for L in out["res"] if L["niveau"] > 105] == [{"niveau": 110.25, "contacts": 2, "tenus": 1,
                           "premier": 5 * JOUR, "dernier": 10 * JOUR}], out


def test_un_niveau_touche_une_seule_fois_n_est_pas_trace():
    c = _serie()
    c[5] = {"x": 5 * JOUR, "y": [100, 110, 100, 105], "vol": 10}
    assert _hauts(_sr(c, 100)) == []
    assert _hauts(_sr(c, 100, 1)) == [110]
    assert _sr(c, 100)["retires"] == 1


# ── 3. Affichage ─────────────────────────────────────────────────────────────

def test_titre_court_sur_la_ligne_et_legende_datee():
    assert "title:`S ${fmtPrixFR(L.niveau)} · ${L.contacts}×`" in SRC
    assert "title:`R ${fmtPrixFR(L.niveau)} · ${L.contacts}×`" in SRC
    leg = _bloc(SRC, "const LegendeSR=(")
    for mot in ("touché", "tenu", "du ", " au ", "Support", "Résistance"):
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
    for mot in ("Contact", "Tenu", "1,2 %", "2 contacts", "volume nul",
                "Séances écartées", "restent dessinées", "3 séances"):
        assert mot in guide, mot
    assert re.search(r"SR_TOL=0\.012, SR_LB=3, SR_MIN_CONTACTS=2;", SRC), (
        "le guide écrit 1,2 %, 3 séances et 2 contacts : le code doit le dire aussi")


def test_index_compile_porte_le_nouveau_calcul():
    assert "SR_MIN_CONTACTS" in COMPILE and "LegendeSR" in COMPILE
