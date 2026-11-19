"""Des couleurs qui ne recommandent pas — lot 1.4 de la feuille de route, 19/11/2026.

LA RÈGLE
────────
Le vert et le rouge sont RÉSERVÉS aux variations de cours (hausse, baisse)
et aux alertes. Avant ce lot, le Score BVC à 75 et plus était peint du même
vert que les hausses (#00e5a0), et le dégradé des tranches allait du vert à
l'orange : la couleur se lisait « bon / mauvais », ce que la mesure dément
(43 031 observations, aucune tranche ne se distingue de façon robuste, R8).

Mesuré dans un navigateur le 19/11/2026 (`data.json` du jour), AVANT ce lot :
36 éléments de score peints dans la couleur des hausses au classement
(colonnes SCORE BVC et COULEUR, 9 titres), 5 sur la fiche d'IAM (score 67),
12 sur celle de BCP (score 92). APRÈS : 0, 0, 0.

Les tranches du score passent sur une échelle NEUTRE, du gris au bleu de
plus en plus soutenu ; les couleurs évaluatives hors score (PER > 25 en
orange, PER prévisionnel > 25 en orange, dividende et rendement attendu
> 4 % en vert, rang « cher / pas cher », filtres RSI
survendu vert / suracheté rouge, bouton du briefing vert plein) deviennent
neutres. Les VALEURS, les tranches et les seuils ne changent pas (R8).

CE QUI EST VÉRIFIÉ, SANS NAVIGATEUR
───────────────────────────────────
1. Aucune couleur des hausses (#00e5a0) ni des baisses (#ff4f5a, #ff1744)
   dans les fonctions et composants qui peignent un score.
2. L'échelle est neutre (gris ou bleu, aucune teinte verte, jaune, orange ou
   rouge) et ORDONNÉE : la saturation croît de « sous 40 » à « 75 et plus ».
3. Contraste WCAG ≥ 4,5:1 de chaque couleur de tranche sur les fonds du
   terminal, y compris le fond teinté de la fiche, et du texte sombre posé
   sur la pastille pleine d'un filtre actif.
4. Lisible pour un daltonien : entre deux tranches voisines, écart perceptif
   ΔE (CIELAB) ≥ 10 en vision normale et en deutéranopie, protanopie et
   tritanopie simulées (matrices de Machado, Oliveira et Fernandes, 2009).
   L'ancienne échelle tombait à 7,7 entre 60–74 et 40–59 en protanopie.
5. Les couleurs évaluatives hors score ont disparu ; les valeurs restent.
6. « Comment lire » décrit la nouvelle échelle.
"""

from __future__ import annotations

import colorsys
import math
import re
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parent.parent
SRC = (RACINE / "terminal.src.html").read_text(encoding="utf-8")

HAUSSE = "#00e5a0"
BAISSES = ("#ff4f5a", "#ff1744")
FONDS = {"page": "#080d1a", "carte": "#0d1829", "case": "#0a1220"}


def _bloc(debut: str, fin: str) -> str:
    i = SRC.index(debut)
    return SRC[i:SRC.index(fin, i + len(debut))]


def _ligne(motif: str) -> str:
    i = SRC.index(motif)
    return SRC[SRC.rindex("\n", 0, i) + 1:SRC.index("\n", i)]


def _couleurs_tranches() -> dict[str, str]:
    bloc = _bloc("const TRANCHES_BVC=[", "];")
    nc = _bloc("const TRANCHE_NC=", ";")
    out = dict(re.findall(r'id:"(t\d+)",\s*min:[^,]+,\s*c:"(#[0-9a-fA-F]{6})"', bloc))
    out["nc"] = re.search(r'c:"(#[0-9a-fA-F]{6})"', nc).group(1)
    return out


# ── Couleurs : arithmétique WCAG et CIELAB ──────────────────────────────────

def _rgb(h: str) -> tuple[int, int, int]:
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def _lin(c: float) -> float:
    c /= 255
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def _luminance(h: str) -> float:
    r, g, b = (_lin(x) for x in _rgb(h))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contraste(a: str, b: str) -> float:
    la, lb = sorted((_luminance(a), _luminance(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def _melange(c: str, fond: str, alpha: float) -> str:
    return "#" + "".join(f"{round(alpha * x + (1 - alpha) * y):02x}" for x, y in zip(_rgb(c), _rgb(fond)))


_MACHADO = {
    "deuteranopie": ((0.367322, 0.860646, -0.227968), (0.280085, 0.672501, 0.047413), (-0.011820, 0.042940, 0.968881)),
    "protanopie": ((0.152286, 1.052583, -0.204868), (0.114503, 0.786281, 0.099216), (-0.003882, -0.048116, 1.051998)),
    "tritanopie": ((1.255528, -0.076749, -0.178779), (-0.078411, 0.930809, 0.147602), (0.004733, 0.691367, 0.303900)),
}


def _lab(h: str, vision: str | None = None) -> tuple[float, float, float]:
    v = [_lin(x) for x in _rgb(h)]
    if vision:
        m = _MACHADO[vision]
        v = [min(1.0, max(0.0, sum(m[i][j] * v[j] for j in range(3)))) for i in range(3)]
    r, g, b = v
    x = (0.4124 * r + 0.3576 * g + 0.1805 * b) / 0.95047
    y = 0.2126 * r + 0.7152 * g + 0.0722 * b
    z = (0.0193 * r + 0.1192 * g + 0.9505 * b) / 1.08883
    f = lambda t: t ** (1 / 3) if t > 0.008856 else 7.787 * t + 16 / 116  # noqa: E731
    return 116 * f(y) - 16, 500 * (f(x) - f(y)), 200 * (f(y) - f(z))


def delta_e(a: str, b: str, vision: str | None = None) -> float:
    return math.dist(_lab(a, vision), _lab(b, vision))


def test_l_arithmetique_des_couleurs_est_juste():
    """Contrôle de l'outil avant de s'y fier : valeurs de référence WCAG."""
    assert contraste("#ffffff", "#000000") == pytest.approx(21.0)
    assert contraste("#777777", "#ffffff") == pytest.approx(4.48, abs=0.01)
    assert delta_e("#123456", "#123456") == 0
    # Un daltonien rouge-vert confond le vert et le rouge bien plus qu'une
    # vision normale : la simulation doit le montrer.
    assert delta_e("#00a000", "#c00000", "deuteranopie") < delta_e("#00a000", "#c00000") / 2


# ── 1. Aucune couleur des hausses ni des baisses sur un score ───────────────

def _zones_score() -> dict[str, str]:
    """Le code qui choisit la couleur d'un score, partout où il s'affiche."""
    return {
        "tranches et couleur du chiffre": _bloc("const TRANCHES_BVC=[", "const VC="),
        "pastille du classement et de la fiche": _bloc("const PastilleBVC=", "const Delta="),
        "composition du score (barres et légende)": _bloc("const ScoreBVC=", "const RisqueMesure="),
        "filtres de tranche": _bloc("{[...TRANCHES_BVC,TRANCHE_NC].map(p=>", "</button>);})}"),
        "chiffre et barre du classement": _bloc("{/* SCORE BVC (06/11/2026)", "{vBVC!=null&&(()=>"),
        "légende du classement": _ligne("SCORE BVC = six facteurs"),
        "teinte de la fiche": _bloc("const vBVC=valeurBVC(r);\n  const s=", "\n"),
        "comment lire": _bloc('<L titre="Couleur du score">', "</L>"),
    }


@pytest.mark.parametrize("zone", list(_zones_score()))
def test_aucun_score_dans_la_couleur_des_hausses_ou_des_baisses(zone):
    code = _zones_score()[zone].lower()
    for c in (HAUSSE, *BAISSES):
        assert c not in code, f"{zone} : {c} peint un score"


def test_le_controle_voit_bien_le_vert_des_hausses():
    """Contrôle négatif : l'ancienne table aurait été refusée."""
    ancienne = '{id:"t75",min:75,       c:"#00e5a0",plage:"≥ 75"},'
    assert HAUSSE in ancienne.lower()
    assert _teinte_interdite("#00e5a0") and _teinte_interdite("#b5e655")
    assert _teinte_interdite("#ffd740") and _teinte_interdite("#ff8f00")


# ── 2. Une échelle neutre et ordonnée ───────────────────────────────────────

def _teinte_interdite(h: str) -> bool:
    """Vert, jaune, orange ou rouge : une couleur qui juge. Un gris (saturation
    faible) ou un bleu (teinte 195°–250°) est neutre."""
    r, g, b = (x / 255 for x in _rgb(h))
    teinte, _l, sat = colorsys.rgb_to_hls(r, g, b)
    if sat < 0.25:
        return False
    return not 195 <= teinte * 360 <= 250


def test_l_echelle_du_score_est_neutre():
    coul = _couleurs_tranches()
    assert set(coul) == {"t75", "t60", "t40", "t0", "nc"}
    for tid, c in coul.items():
        assert not _teinte_interdite(c), f"{tid} = {c} : teinte qui juge"


def test_l_echelle_va_du_gris_au_bleu_soutenu():
    """Ordonnée par la chroma CIELAB : plus le score est haut, plus le bleu
    est soutenu. « non calculé » reste le gris des états."""
    coul = _couleurs_tranches()
    chroma = {t: math.hypot(*_lab(coul[t])[1:]) for t in coul}
    assert chroma["t0"] < 15 and chroma["nc"] < 15            # deux gris
    assert chroma["t0"] < chroma["t40"] < chroma["t60"] < chroma["t75"]
    assert coul["nc"].lower() == "#8892a4"                    # le gris des états, inchangé


# ── 3. Contrastes ───────────────────────────────────────────────────────────

@pytest.mark.parametrize("fond", list(FONDS))
def test_chaque_tranche_se_lit_sur_les_fonds_du_terminal(fond):
    for tid, c in _couleurs_tranches().items():
        assert contraste(c, FONDS[fond]) >= 4.5, f"{tid} {c} sur {fond} : {contraste(c, FONDS[fond]):.2f}:1"


def test_le_chiffre_se_lit_sur_la_carte_teintee_de_la_fiche():
    """`teinte(c)` pose la couleur à 10 % (suffixe « 1a ») sur la carte : le
    chiffre de la fiche et le bouton du titre actif s'y lisent."""
    assert "const teinte=c=>({bg:`${c}1a`" in SRC
    for tid, c in _couleurs_tranches().items():
        if tid == "nc":
            continue                          # sans valeur : fond NEUTRE, pas de teinte
        for nom, f in (("carte", FONDS["carte"]), ("page", FONDS["page"])):
            fond = _melange(c, f, 0x1a / 255)
            assert contraste(c, fond) >= 4.5, f"{tid} {c} sur sa teinte ({nom}) : {contraste(c, fond):.2f}:1"


def test_le_filtre_actif_se_lit():
    """Filtre de tranche actif : texte #080d1a sur la pastille pleine."""
    for tid, c in _couleurs_tranches().items():
        assert contraste("#080d1a", c) >= 4.5, tid


# ── 4. Daltonisme ───────────────────────────────────────────────────────────

@pytest.mark.parametrize("vision", [None, "deuteranopie", "protanopie", "tritanopie"])
def test_deux_tranches_voisines_se_distinguent(vision):
    coul = _couleurs_tranches()
    ordre = ["nc", "t0", "t40", "t60", "t75"]
    for a, b in zip(ordre, ordre[1:]):
        d = delta_e(coul[a], coul[b], vision)
        assert d >= 10, f"{a}/{b} en {vision or 'vision normale'} : ΔE {d:.1f}"


def test_l_ancienne_echelle_echouait_en_protanopie():
    """Contrôle négatif du test précédent, sur l'échelle d'avant ce lot."""
    assert delta_e("#b5e655", "#ffd740", "protanopie") < 10


# ── 5. Couleurs évaluatives hors score ──────────────────────────────────────

def test_la_composition_n_est_plus_verte():
    sb = _zones_score()["composition du score (barres et légende)"]
    assert "vert</span> = plein" not in sb and "jaune</span> = partiel" not in sb
    assert "= plein" in sb and "= partiel" in sb and "= 0 point" in sb
    assert '<span style={{color:ok?"#00e5a0"' not in sb        # « · CALCULABLE » n'est pas une victoire
    couleur = re.search(r"const couleur=\(pts,w\)=>(.*?);\n", sb).group(1)
    for c in re.findall(r'"(#[0-9a-fA-F]{6})"', couleur):
        assert not _teinte_interdite(c), f"barre de facteur {c}"


def test_le_per_eleve_n_est_plus_orange_et_le_dividende_eleve_plus_vert():
    for motif in (r"r\.pe>25\?", r"per_2[67]e>25\?", r"r\.div>4\?", r"dy_2[67]e>4\?"):
        assert not re.search(motif, SRC), motif
    # Les valeurs restent affichées.
    assert "{perTxt(r.pe,r.bpa_12m??r.bpa)}</td>" in SRC
    assert "{divClassement(r.div)}</td>" in SRC
    assert '["Dividende",divFiche(r.div),' in SRC
    assert '["Rendement 2026e",r.fwd.dy_26e!=null?' in SRC
    assert '["PER 2026e",fmt(r.fwd.per_26e,1),' in SRC


def test_le_rang_dans_le_secteur_ne_dit_plus_cher_ou_pas_cher():
    bloc = _bloc("const e=(r.rang_secteur||{})[ratio];", "})()}")
    assert "cher?" not in bloc and HAUSSE not in bloc and "#ff8f00" not in bloc
    assert "vs secteur" in bloc and "e.rang" in bloc and "e.ecart_pct" in bloc


def test_les_filtres_rsi_ne_jugent_plus():
    bloc = _bloc('<span style={{marginLeft:8,fontSize:10,color:"#8892a4",letterSpacing:.5}}>RSI</span>', "))}")
    assert "survendu" in bloc and "suracheté" in bloc
    for c in (HAUSSE, *BAISSES):
        assert c not in bloc.lower(), c


def test_le_bouton_du_briefing_n_est_plus_vert():
    i = SRC.index("LIRE LE BRIEFING ›")
    bouton = SRC[SRC.rindex("<button", 0, i):i]
    assert HAUSSE not in bouton.lower()
    fond = re.search(r'background:"(#[0-9a-fA-F]{6})"', bouton).group(1)
    assert not _teinte_interdite(fond)
    assert contraste("#080d1a", fond) >= 4.5


# ── 6. Comment lire ─────────────────────────────────────────────────────────

def test_comment_lire_decrit_l_echelle_neutre():
    L = _zones_score()["comment lire"]
    for mot in ("gris", "bleu", "situe le score dans sa tranche", "ne dit pas quoi faire",
                "75 et plus", "60 à 74", "40 à 59", "sous 40", "non calculé",
                "Données insuffisantes", "SUSPENDU"):
        assert mot in L, mot
    assert "hausses" in L and "baisses" in L                    # le vert et le rouge, dits réservés
    for c in ("#b5e655", "#ffd740", "#ff8f00"):                  # l'ancienne échelle
        assert c not in L.lower(), c
