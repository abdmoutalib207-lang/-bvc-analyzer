"""Stockage local refusé : le terminal oublie, il ne casse pas.

CE QUI ÉTAIT CASSÉ, ET COMMENT ON LE SAIT
─────────────────────────────────────────
En navigation privée stricte, ou cookies bloqués, l'accès à `localStorage`
LÈVE une exception. Six accès n'étaient pas gardés. Mesuré au navigateur le
07/10/2026 (Chromium, `localStorage` remplacé par un accesseur qui lève) :

- lecture refusée → « Erreur de rendu » dès l'ouverture, sur tout le
  terminal : l'onglet initial (`bvc_tab`) se lisait dans l'initialisation
  de l'état ;
- écriture refusée → « Erreur de rendu » au premier clic sur ☆ :
  `toggleFav` écrivait DANS la fonction de mise à jour de l'état, donc
  pendant le rendu.

Après correctif : 0 erreur de rendu dans les deux cas, contrôle navigateur
PUBLIABLE sur les trois écrans.

LA RÈGLE TESTÉE ICI
───────────────────
Tout accès à `localStorage` se trouve dans un `try` encore ouvert. Le test
lit la source, sans navigateur, pour tourner en intégration continue.
"""

import re
from pathlib import Path

SRC = Path(__file__).resolve().parent.parent / "terminal.src.html"


def _acces_non_gardes(texte: str) -> list[int]:
    """Numéros de ligne des accès à localStorage hors d'un `try` ouvert.

    Heuristique volontairement simple : le dernier `try` qui précède l'accès,
    à moins de 400 caractères, ne doit pas avoir été refermé par un `catch`
    avant lui. Les commentaires sont ignorés.
    """
    fautes = []
    for m in re.finditer(r"localStorage\s*\.", texte):
        debut_ligne = texte.rfind("\n", 0, m.start()) + 1
        ligne = texte[debut_ligne:m.start()]
        if "//" in ligne or ligne.lstrip().startswith("*"):
            continue
        avant = texte[max(0, m.start() - 400):m.start()]
        i = max(avant.rfind("try{"), avant.rfind("try {"))
        if i < 0 or "catch" in avant[i:]:
            fautes.append(texte.count("\n", 0, m.start()) + 1)
    return fautes


def test_tout_acces_au_stockage_est_garde():
    fautes = _acces_non_gardes(SRC.read_text(encoding="utf-8"))
    assert not fautes, (
        f"localStorage non gardé aux lignes {fautes} de terminal.src.html : "
        "stockage refusé = « Erreur de rendu ». Passer par lsLire / lsEcrire."
    )


def test_le_controle_voit_un_acces_nu():
    """Contrôle négatif : un test jamais vu rouge ne prouve rien."""
    nu = 'const x=1;\nconst [t,setT]=useState(()=>localStorage.getItem("bvc_tab"));\n'
    assert _acces_non_gardes(nu) == [2]
    referme = 'try{a();}catch(e){}\nlocalStorage.setItem("k","v");\n'
    assert _acces_non_gardes(referme) == [2]
    garde = 'try{const v=localStorage.getItem("k");}catch(e){}\n'
    assert _acces_non_gardes(garde) == []
