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
     l'écran le met en capitales.
   Les citations de l'ancien corpus, exclues nommément jusqu'au 28/10/2026,
   ont disparu avec lui : le contrôle porte sur TOUTE la page servie.

2. Jusqu'au 05/11/2026 : les seuils de couleur étaient ceux de
   `compute_v53`, et la couleur lue sur la note donnait, titre par titre, le
   palier du `sig` publié.
   ⚠️ Depuis le 06/11/2026 (décision d'Abd Moutalib), le terminal n'affiche
   plus la note v5.3 : la couleur suit la TRANCHE du Score BVC. Les bornes
   sont celles du backtest qui mesure ces tranches
   (`pipeline/backtest_score_descriptif.py::TRANCHES`), et, titre par titre
   sur data.json, la tranche lue par le terminal est celle du backtest.
   Le `sig` du moteur, toujours publié, n'est plus confronté à l'écran : ses
   seuils restent testés côté moteur.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parent.parent
SRC = (RACINE / "terminal.src.html").read_text(encoding="utf-8")
COMPILE = (RACINE / "index.html").read_text(encoding="utf-8")

MOTS_D_ACTION = re.compile(
    r"(?<![A-Za-z0-9_$])(achat\s+fort|acheter|surveiller|attendre|[ée]viter)(?![A-Za-z0-9_$])",
    re.IGNORECASE,
)

def _decoder(t: str) -> str:
    """Babel échappe les caractères non ASCII (« É » → « \\xC9 »)."""
    t = re.sub(r"\\u\{([0-9A-Fa-f]+)\}", lambda m: chr(int(m.group(1), 16)), t)
    t = re.sub(r"\\u([0-9A-Fa-f]{4})", lambda m: chr(int(m.group(1), 16)), t)
    return re.sub(r"\\x([0-9A-Fa-f]{2})", lambda m: chr(int(m.group(1), 16)), t)


def mots_d_action_affichables(html: str) -> list[str]:
    texte = re.sub(r"<!--.*?-->", "", html, flags=re.S)
    texte = _decoder(texte)
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
    """`sig` n'est plus qu'un champ transmis (mergeLive). Ni étiquette, ni
    filtre, ni export ne le lisent. Depuis le 06/11/2026, la couleur se lit
    sur la tranche du Score BVC (PastilleBVC), plus sur la note v5.3."""
    for lecture in ("label={r.sig}", "SS(r.sig)", "SS(d.sig)", "(r.sig||\"\")",
                    "x.sig||", "r.sig||\"\"}`", "r.sig==="):
        assert lecture not in SRC, lecture
    assert "<PastilleBVC r={r}/>" in SRC          # classement
    assert "<PastilleBVC r={r} sz={12}/>" in SRC  # fiche
    assert "PastilleNote" not in SRC


def test_le_plafond_d_illiquidite_v53_n_est_plus_affiche():
    """Le plafond (note ≥ 6,5 ramenée au vert-jaune, 04/10/2026) qualifiait la
    couleur de la note v5.3. Il part avec elle le 06/11/2026 : le Score BVC
    compte la liquidité dans un facteur à part entière."""
    assert "r.verdict_plafonne" not in SRC and "pastille-plafond" not in SRC
    # Le texte publié par le moteur (« ACHETER plafonné : … ») n'est pas affiché.
    assert "{r.verdict_plafonne}" not in SRC


def test_les_filtres_portent_sur_une_tranche_du_score_bvc():
    assert "const [trancheFiltre,setTrancheFiltre]=useState(null);" in SRC
    assert "trancheBVC(x).id===trancheFiltre" in SRC
    assert "[...TRANCHES_BVC,TRANCHE_NC].map(" in SRC      # ≥ 75 · 60–74 · 40–59 · < 40 · non calculé
    assert "sigFilter" not in SRC and "palierFiltre" not in SRC


# ── 2. Les tranches sont celles de la mesure ────────────────────────────────

def _bornes_terminal() -> list[float]:
    bloc = SRC[SRC.index("const TRANCHES_BVC=["):SRC.index("];", SRC.index("const TRANCHES_BVC=["))]
    return [float(x) for x in re.findall(r"min:\s*([0-9.]+)", bloc)]


def _tranches_backtest():
    src = (RACINE / "pipeline/backtest_score_descriptif.py").read_text(encoding="utf-8")
    bloc = re.search(r"TRANCHES = \((.*?)\)\n", src).group(1)
    return [(lib, float(lo), float(hi)) for lib, lo, hi in re.findall(r'\("([^"]+)", (\d+), ([\de.]+)\)', bloc)]


def test_les_bornes_de_couleur_sont_celles_du_backtest():
    """Les fréquences affichées (onglet POIDS, guide) sont mesurées sur les
    tranches du backtest : la couleur doit découper aux mêmes bornes."""
    bt = _tranches_backtest()
    assert [lo for _, lo, _ in bt] == [0, 40, 60, 75]
    assert _bornes_terminal() == [75.0, 60.0, 40.0]
    assert "min:-Infinity" in SRC[SRC.index("const TRANCHES_BVC=["):]


def _tranche(v: float | None, bornes: list[float]) -> int | None:
    """Réplique de `trancheBVC` (terminal) en Python : rang de la tranche."""
    if v is None:
        return None
    return next((k for k, s in enumerate(bornes) if v >= s), len(bornes))


def test_la_couleur_donne_la_tranche_du_backtest_pour_chaque_titre():
    """Famille « données publiées » : relit data.json tel qu'il est servi. Pour
    chaque titre, la tranche lue par le terminal est celle où le backtest
    aurait rangé la même valeur ; sans valeur (PARTIEL, NON_CALCULABLE),
    aucune couleur de tranche."""
    titres = json.loads((RACINE / "data.json").read_text(encoding="utf-8"))["tickers"]
    bornes = _bornes_terminal()
    bt = list(reversed(_tranches_backtest()))            # ≥ 75 d'abord, comme le terminal
    ecarts, vus = {}, 0
    for t in titres:
        s = t.get("score_bvc") or {}
        v = s.get("valeur")
        lu = _tranche(v, bornes)
        if v is None:
            if lu is not None:
                ecarts[t.get("symbol")] = (v, lu)
            continue
        vus += 1
        attendu = next(k for k, (_, lo, hi) in enumerate(bt) if lo <= v < hi)
        if lu != attendu:
            ecarts[t.get("symbol")] = (v, lu, attendu)
    if not vus:
        pytest.skip("aucun Score BVC publié dans data.json")
    assert not ecarts, f"tranche du terminal ≠ tranche du backtest : {ecarts}"


# ── 3. Le guide ─────────────────────────────────────────────────────────────

def test_le_guide_explique_la_couleur_et_non_un_signal():
    guide = SRC[SRC.index("const Guide=("):]
    guide = guide[:guide.index("\n};\n")]
    assert '<L titre="Couleur du score">' in guide
    assert '<L titre="Signal">' not in guide and '<L titre="Couleur de la note">' not in guide
    for nom in ("75 et plus", "60 à 74", "40 à 59", "sous 40", "non calculé",
                "Données insuffisantes", "SUSPENDU"):
        assert nom in guide, nom
    assert "ne dit pas quoi faire" in guide
