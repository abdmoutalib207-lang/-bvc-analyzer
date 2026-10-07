"""Le terminal n'écrit plus de recommandation : la note et sa couleur — 07/10/2026.

LA DEMANDE
──────────
Abd Moutalib : « au lieu d'afficher une recommandation sur le score, se
contenter de couleurs ». Le produit ne prédit pas et ne recommande pas
(CLAUDE.md, Vision produit). Les libellés ACHETER, SURVEILLER, ATTENDRE,
ÉVITER et ACHAT FORT ne s'affichent plus : la note /10 porte une pastille de
couleur, selon les MÊMES paliers que `compute_v53`.

Le moteur, lui, ne change pas : `sig` reste calculé et publié dans data.json
(traçabilité, tests, R8). Seul l'écran change.

CE QUI EST VÉRIFIÉ, SANS NAVIGATEUR
───────────────────────────────────
1. Aucun mot d'action dans une chaîne AFFICHABLE du terminal.

   La règle porte sur `index.html`, le fichier servi, et non sur la source :
   Babel y a compilé le JSX (le texte des balises devient une chaîne) et
   retiré tous les commentaires JavaScript (`comments: false` dans
   tools/compiler_terminal.js). Ce qui reste est donc du code ou du texte
   que le navigateur peut afficher. Les commentaires HTML sont retirés ici.

   Ne comptent PAS :
   - les identifiants de code — un mot collé à une lettre, un chiffre, `_`
     ou `$` (`a_surveiller`, clé de briefing.json ; `ASurveiller`, nom de
     composant). Le test cherche le mot ENTIER, insensible à la casse et à
     l'accent de « éviter » : « À surveiller » en minuscules compte, puisque
     l'écran le met en capitales ;
   - les CITATIONS DU CORPUS WhatsApp, énumérées ci-dessous une par une :
     ce sont des libellés de ce que des membres du groupe ont écrit, pas un
     jugement du produit. Les réécrire falsifierait le corpus ; leur sort
     est une décision à part, signalée dans le rapport du 07/10.

2. Les seuils de couleur du terminal sont ceux du moteur, et, titre par
   titre sur le data.json publié, la couleur lue sur la note (et le plafond
   d'illiquidité) donne le même palier que le `sig` du moteur. C'est ce qui
   garantit que « rien ne change de fond ».
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parent.parent
SRC = (RACINE / "terminal.src.html").read_text(encoding="utf-8")
COMPILE = (RACINE / "index.html").read_text(encoding="utf-8")
MOTEUR = (RACINE / "update_data.py").read_text(encoding="utf-8")

MOTS_D_ACTION = re.compile(
    r"(?<![A-Za-z0-9_$])(achat\s+fort|acheter|surveiller|attendre|[ée]viter)(?![A-Za-z0-9_$])",
    re.IGNORECASE,
)

# Citations du corpus WhatsApp (libellés de messages de membres), exclues
# NOMMÉMENT : une exclusion large masquerait un vrai libellé du produit.
CITATIONS_CORPUS = (
    # Messages de membres de l'onglet SMART MONEY, avec leur classe.
    re.compile(r"const CHAT = \[.*?\];", re.S),
    # Répartition des classes de messages du corpus (onglet NLP CORPUS).
    re.compile(r"const NLP_SIGS = \[.*?\];", re.S),
    # « Biais groupe » : la classe dominante des messages du groupe.
    re.compile(r'biais: "[^"]*"'),
)


def _decoder(t: str) -> str:
    """Babel échappe les caractères non ASCII (« É » → « \\xC9 »)."""
    t = re.sub(r"\\u\{([0-9A-Fa-f]+)\}", lambda m: chr(int(m.group(1), 16)), t)
    t = re.sub(r"\\u([0-9A-Fa-f]{4})", lambda m: chr(int(m.group(1), 16)), t)
    return re.sub(r"\\x([0-9A-Fa-f]{2})", lambda m: chr(int(m.group(1), 16)), t)


def mots_d_action_affichables(html: str) -> list[str]:
    texte = re.sub(r"<!--.*?-->", "", html, flags=re.S)
    texte = _decoder(texte)
    for motif in CITATIONS_CORPUS:
        texte = motif.sub("", texte)
    return [texte[max(0, m.start() - 60):m.end() + 30].replace("\n", " ")
            for m in MOTS_D_ACTION.finditer(texte)]


# ── 1. Aucun mot d'action à l'écran ─────────────────────────────────────────

def test_aucun_mot_d_action_dans_le_terminal_servi():
    trouves = mots_d_action_affichables(COMPILE)
    assert not trouves, "mot(s) d'action affichable(s) dans index.html :\n" + "\n".join(trouves)


def test_le_controle_voit_bien_un_mot_d_action():
    """Contrôle négatif : un contrôle jamais vu rouge ne prouve rien. Une
    étiquette, un texte JSX compilé, un mot accentué échappé par Babel, une
    minuscule mise en capitales par le CSS : tous doivent être vus."""
    for faux in ('React.createElement(Chip, { label: "ACHETER \\u2605\\u2605" })',
                 '"Verdict plafonn\\xE9 \\xE0 SURVEILLER"',
                 '"\\xC9VITER FORT"', '"Achat fort"', "\"\\xC0 surveiller aujourd'hui\"",
                 '"ATTENDRE"'):
        assert mots_d_action_affichables(f"<script>{faux}</script>"), faux
    # … et les identifiants de code ne comptent pas.
    for code in ("const a = b.a_surveiller;", "React.createElement(ASurveiller, null)",
                 "<!-- ACHETER dans un commentaire HTML -->"):
        assert not mots_d_action_affichables(code), code


def test_les_etats_restent_ecrits():
    """Ce ne sont pas des recommandations : ils disent l'état de la donnée."""
    for etat in ('label="Données insuffisantes"', 'label="SUSPENDU"',
                 "SUSPENDU depuis le ${jjmm(meta(r).suspDepuis)}"):
        assert etat in SRC, etat


def test_le_terminal_ne_lit_plus_le_sig_pour_l_afficher():
    """La couleur se lit sur la note publiée ; `sig` n'est plus qu'un champ
    transmis (mergeLive). Ni étiquette, ni filtre, ni export ne le lisent."""
    for lecture in ("label={r.sig}", "SS(r.sig)", "SS(d.sig)", "(r.sig||\"\")",
                    "x.sig||", "r.sig||\"\"}`"):
        assert lecture not in SRC, lecture
    assert "<PastilleNote r={r}/>" in SRC          # classement
    assert "<PastilleNote r={r} sz={12}/>" in SRC  # fiche


def test_le_plafond_d_illiquidite_est_dit_en_texte_neutre():
    assert "titre peu échangé" in SRC
    assert "plafonne=!!r.verdict_plafonne&&i===0" in SRC
    # Le texte publié par le moteur (« ACHETER plafonné : … ») n'est pas affiché.
    assert "{r.verdict_plafonne}" not in SRC and "r.verdict_plafonne}" not in SRC


def test_les_filtres_portent_sur_un_palier_de_note():
    assert "const [palierFiltre,setPalierFiltre]=useState(null);" in SRC
    assert "palierDe(computeDisplayScore(x,scoreMode))===palierFiltre" in SRC
    assert "sigFilter" not in SRC


# ── 2. Rien ne change de fond ───────────────────────────────────────────────

def _seuils_terminal() -> list[float]:
    bloc = SRC[SRC.index("const PALIERS=["):SRC.index("];", SRC.index("const PALIERS=["))]
    return [float(x) for x in re.findall(r"\{min:\s*([0-9.]+)", bloc)]


def _seuils_moteur() -> list[float]:
    v53 = MOTEUR[MOTEUR.index("def compute_v53("):]
    v53 = v53[:v53.index("\ndef ")]
    return [float(x) for x in re.findall(r"final >= ([0-9.]+):\s*\n\s*sig = ", v53)]


def test_les_seuils_de_couleur_sont_ceux_du_moteur():
    assert _seuils_moteur() == [6.5, 5.5, 4.5, 3.5]
    assert _seuils_terminal() == _seuils_moteur()
    # Cinq paliers : quatre seuils et le dernier, ouvert vers le bas.
    assert "{min:-Infinity," in SRC


def _palier_couleur(v53: float, plafonne: bool, seuils: list[float]) -> int:
    """Réplique de `couleurNote` (terminal) en Python."""
    i = next((k for k, s in enumerate(seuils) if v53 >= s), len(seuils))
    return 1 if (plafonne and i == 0) else i


_PALIER_DU_SIG = {"ACHETER ★★": 0, "SURVEILLER ★": 1, "ATTENDRE": 2,
                  "ÉVITER": 3, "ÉVITER FORT": 4}


def test_la_couleur_donne_le_palier_du_sig_publie_pour_chaque_titre():
    """Famille « données publiées » : relit data.json tel qu'il est servi."""
    titres = json.loads((RACINE / "data.json").read_text(encoding="utf-8"))["tickers"]
    seuils = _seuils_terminal()
    ecarts, vus = {}, 0
    for t in titres:
        sig, v53 = t.get("sig"), t.get("v53")
        if sig not in _PALIER_DU_SIG or v53 is None:
            continue        # états (SUSPENDU, Données insuffisantes) : pas de couleur
        vus += 1
        lu = _palier_couleur(v53, bool(t.get("verdict_plafonne")), seuils)
        if lu != _PALIER_DU_SIG[sig]:
            ecarts[t.get("symbol")] = (v53, sig, lu)
    if not vus:
        pytest.skip("aucun titre coloré dans data.json")
    assert not ecarts, f"couleur ≠ palier du moteur : {ecarts}"


# ── 3. Le guide ─────────────────────────────────────────────────────────────

def test_le_guide_explique_la_couleur_et_non_un_signal():
    guide = SRC[SRC.index("const Guide=("):]
    guide = guide[:guide.index("\n};\n")]
    assert '<L titre="Couleur de la note">' in guide
    assert '<L titre="Signal">' not in guide
    for nom in ("vert", "vert-jaune", "jaune", "orange", "rouge",
                "titre peu échangé", "Données insuffisantes", "SUSPENDU"):
        assert nom in guide, nom
    assert "ne dit pas quoi faire" in guide
