"""Le cadre commun du terminal — en-tête et pied (19/11/2026).

Inventaire du bruit, PR 2 : ce que l'en-tête et le pied montrent sur TOUS
les écrans. Affichage seulement — ni moteur, ni données, ni Score BVC.

1. Retraits : horloge à la seconde, point pulsant, badge « v6.4 », doublons
   du nombre de titres, bouton de menu flottant du téléphone.
2. Reformulations : date des données, état de la séance, largeur du marché,
   carte MASI 20 ; le nombre de transactions quitte le cadre.
3. Bandeau défilant masqué sur téléphone.
4. Seule la première ligne de l'en-tête reste collée.
5. Lisibilité : plancher de 12 px sur téléphone, avertissement en 13 px et
   contrasté, gris #5a6478 retiré du texte.

Les mesures en navigateur (hauteurs, part de texte sous 12 px) sont dans le
compte rendu de la PR ; ces tests verrouillent le code qui les produit.
"""
from __future__ import annotations

import re
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
SRC = (RACINE / "terminal.src.html").read_text(encoding="utf-8")


def _entre(s: str, debut: str, fin: str) -> str:
    i = s.index(debut)
    return s[i:s.index(fin, i)]


def _sans_commentaires(s: str) -> str:
    s = re.sub(r"/\*.*?\*/", " ", s, flags=re.S)
    s = re.sub(r"\{/\*.*?\*/\}", " ", s, flags=re.S)
    return re.sub(r"(?<![:\"'])//[^\n]*", " ", s)


ENTETE = _sans_commentaires(_entre(SRC, "const Header=(", "\n};\n"))
APP = _sans_commentaires(_entre(SRC, "function App(", "\nclass ErrorBoundary"))


# ── 1. Retraits ─────────────────────────────────────────────────────────────

def test_plus_d_horloge_a_la_seconde_dans_l_en_tete():
    """L'heure de l'appareil, rafraîchie chaque seconde, se lisait comme un
    temps réel que le produit n'a pas. Seule la date des données reste."""
    assert "setClock" not in ENTETE and "{clock}" not in ENTETE
    assert "setInterval" not in ENTETE, "l'en-tête ne doit plus rien animer à intervalle"
    assert 'second:"2-digit"' not in ENTETE


def test_plus_de_point_pulsant():
    assert "pulse" not in ENTETE
    assert "transition:\"background .4s\"" not in ENTETE


def test_plus_de_badge_de_version():
    code = _sans_commentaires(SRC)
    assert "v6.4 — SCORE BVC" not in code
    assert 'className="badge-version"' not in code and ".badge-version" not in code


def test_plus_de_doublons_du_nombre_de_titres():
    code = _sans_commentaires(SRC)
    assert "données: {src}" not in code
    assert "BVC · {univers" not in code and 'className="entete-droite"' not in code
    assert "Clôture · ${nLive} titres" not in code and "setSrc(" not in code
