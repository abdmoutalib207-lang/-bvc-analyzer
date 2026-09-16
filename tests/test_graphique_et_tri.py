"""Ce que le graphique montre, et dans quel ordre le filtre présente les titres.

DEUX DÉFAUTS SIGNALÉS PAR NOURE LE 16/09/2026
─────────────────────────────────────────────
1. « les bougies ne donnent que une année d'historique »
2. « lorsque je clique sur bouton (détail) filtrer tiker soit par ordre
   alphabétique »

CE QUI A ÉTÉ MESURÉ AVANT DE TOUCHER AU CODE
────────────────────────────────────────────
`fetchChart()` traduisait la période choisie par un nombre de jours, et sa
table s'arrêtait à `"1y":365`. Or les fichiers de `pipeline/candles/` portent
bien davantage — relevé le 16/09 sur 75 fichiers : médiane **548 séances**,
31 titres à **802** (depuis juin 2023), TGCC à **1 175** (depuis décembre
2021). **Plus de la moitié de l'historique collecté n'atteignait jamais
l'écran** : la donnée était là, la fenêtre la coupait.

Les pastilles du filtre de l'onglet DÉTAIL, elles, reprenaient l'ordre du
CLASSEMENT — donc un ordre qui change à chaque run du moteur. Chercher un
titre y demandait de le parcourir des yeux entièrement.

POURQUOI CES TESTS EXÉCUTENT LE JAVASCRIPT
──────────────────────────────────────────
Les autres tests du frontend relisent le SOURCE, faute d'outillage JS. Ici
c'est insuffisant : « il existe une entrée `max` dans une table » ne dit pas
que la série arrive entière au graphique, et « il existe un `.sort()` » ne dit
pas sur quoi il porte ni qu'il s'applique.

Ces tests extraient donc le code RÉELLEMENT PUBLIÉ — la fonction `fetchChart`
et l'expression `visRows` — et le font tourner sous node avec des dépendances
simulées. Retirer le tri, ou reborner la fenêtre, fait tomber le test : c'est
le comportement qui est vérifié, pas la présence d'un mot.

⚠️ L'attendu n'est jamais calculé par le code testé : la série d'entrée est
construite ici, et l'ordre attendu est obtenu par `sorted()` de Python.
"""

import json
import re
import shutil
import subprocess
import textwrap
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parent.parent
FRONT = RACINE / "index.html"
CANDLES = RACINE / "pipeline" / "candles"


# ── extraction du code publié ────────────────────────────────────────────────

def _source():
    return FRONT.read_text(encoding="utf-8")


def _bloc(src: str, debut: str) -> str:
    """Le texte d'une construction JS, de `debut` à son accolade fermante.

    Comptage d'accolades, pas d'expression régulière : une regex gourmande
    s'arrêterait à la première `}` venue, c'est-à-dire au milieu de la
    fonction, et le test « passerait » sur du code tronqué.
    """
    i = src.index(debut)
    j = src.index("{", i)
    p = 0
    for k in range(j, len(src)):
        if src[k] == "{":
            p += 1
        elif src[k] == "}":
            p -= 1
            if p == 0:
                return src[i:k + 1]
    raise AssertionError(f"accolade non refermée après {debut!r}")


def _instruction(src: str, debut: str) -> str:
    """Une instruction JS, de `debut` au `;` de fin (parenthèses équilibrées)."""
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


def _node(script: str):
    node = shutil.which("node")
    if not node:                                    # pragma: no cover
        pytest.skip("node absent de cette machine")
    r = subprocess.run([node, "-e", script], capture_output=True, text=True,
                       timeout=60)
    assert r.returncode == 0, f"node a échoué :\n{r.stderr}"
    return json.loads(r.stdout)


# ── 1. la fenêtre du graphique ───────────────────────────────────────────────

def _lancer_fetchchart(n_bougies: int, periodes: list[str]):
    """Exécute le vrai `fetchChart` sur une série de `n_bougies` jours.

    Les dépendances réseau sont neutralisées : `fetch` rend la série locale,
    et les deux secours Médias24 rendent du vide. Si le code publié se mettait
    à dépendre d'eux, le test le verrait — il rendrait 0 bougie.
    """
    code = _bloc(_source(), "async function fetchChart(")
    script = textwrap.dedent("""
        %s
        const N = %d;
        const serie = [];
        const j = new Date();
        for (let i = N - 1; i >= 0; i--) {
          const d = new Date(j.getTime() - i * 86400000);
          const s = d.toISOString().slice(0, 10);
          serie.push({d: s, o: 100, h: 101, l: 99, c: 100, v: 10});
        }
        globalThis.fetch = async () => ({ok: true, json: async () => serie});
        globalThis.fetchMed24Raw = async () => null;
        globalThis.fetchMed24History = async () => [];
        (async () => {
          const out = {};
          for (const p of %s) out[p] = (await fetchChart("XXX", p)).length;
          console.log(JSON.stringify(out));
        })();
    """) % (code, n_bougies, json.dumps(periodes))
    return _node(script)


def test_la_serie_complete_atteint_le_graphique():
    """La période la plus longue ne coupe rien : elle rend TOUTE la série.

    C'est le défaut signalé. Reborner `max` à 365 jours — ou supprimer
    l'entrée — fait tomber ce test.
    """
    n = 1200
    vus = _lancer_fetchchart(n, ["max"])
    assert vus["max"] == n, (
        f"la fenêtre la plus longue rend {vus['max']} bougies sur {n} : "
        "l'historique est encore tronqué"
    )


def test_les_fenetres_restent_ordonnees_et_bornees():
    """Chaque période montre strictement plus que la précédente.

    Une fenêtre ne doit pas seulement exister : elle doit couper. Si toutes
    rendaient la série entière, le sélecteur ne servirait plus à rien — et le
    test précédent passerait quand même.
    """
    ordre = ["5J", "1M", "3M", "6M", "1A", "3A", "TOUT"]
    src = _source()
    assert re.search(r'\[' + r','.join(f'"{p}"' for p in ordre) + r'\]\.map',
                     src), "les boutons de période ne sont pas ceux attendus"

    vus = _lancer_fetchchart(1200, ["5d", "1mo", "3mo", "6mo", "1y", "3y", "max"])
    suite = [vus[p] for p in ("5d", "1mo", "3mo", "6mo", "1y", "3y", "max")]
    assert suite == sorted(suite), f"les fenêtres ne croissent pas : {suite}"
    assert len(set(suite)) == len(suite), (
        f"deux périodes montrent la même chose : {suite}"
    )
    assert suite[0] < suite[-1] // 10, (
        "la plus courte devrait être très inférieure à la plus longue"
    )


def test_aucune_borne_ne_masque_un_fichier_reellement_collecte():
    """La fenêtre la plus longue couvre le plus profond de nos fichiers.

    ⚠️ Ce test lit les DONNÉES, pas le code. Il dira « rouge » le jour où un
    historique plus ancien sera collecté sans que la fenêtre suive — c'est
    exactement ce qu'on veut savoir.
    """
    if not CANDLES.is_dir():
        pytest.skip("pipeline/candles absent")
    profondeurs = {}
    for f in CANDLES.glob("*.json"):
        try:
            c = json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            continue
        c = c if isinstance(c, list) else c.get("candles", [])
        if c:
            profondeurs[f.stem] = len(c)
    assert profondeurs, "aucune chandelle lisible"
    plus_profond = max(profondeurs.values())

    vus = _lancer_fetchchart(plus_profond, ["max"])
    assert vus["max"] == plus_profond, (
        f"le plus profond de nos fichiers porte {plus_profond} séances, "
        f"le graphique n'en montre que {vus['max']}"
    )


# ── 2. l'ordre du filtre de l'onglet DÉTAIL ──────────────────────────────────

def _lancer_visrows(codes: list[str], recherche: str = ""):
    """Exécute la vraie expression `visRows` sur des lignes fabriquées ici."""
    src = _source()
    expr = _instruction(src, "const visRows=")
    tk = _instruction(src, "const tk=")
    lignes = [{"symbol": c, "code_bvc": c, "name": f"Société {c}"} for c in codes]
    script = textwrap.dedent("""
        %s
        const rows = %s;
        const detSearch = %s;
        %s
        console.log(JSON.stringify({
          vus: visRows.map(d => tk(d)),
          classement: rows.map(d => tk(d)),
        }));
    """) % (tk, json.dumps(lignes), json.dumps(recherche), expr)
    return _node(script)


def test_le_filtre_ticker_est_alphabetique():
    """Les pastilles sortent dans l'ordre alphabétique du code affiché.

    L'attendu vient de `sorted()` de Python — jamais du code testé (on ne
    prouve rien en comparant une fonction à elle-même).
    """
    desordre = ["VCNE", "ADH", "SNA", "MSA", "CIM", "BCP", "ZLD", "T2S"]
    r = _lancer_visrows(desordre)
    assert r["vus"] == sorted(desordre), (
        f"ordre obtenu {r['vus']}, attendu {sorted(desordre)}"
    )


def test_le_tri_ne_reordonne_pas_le_classement():
    """`rows` est la liste du CLASSEMENT : la trier en place la casserait.

    Ce test tient parce que `visRows` travaille sur une COPIE. Remplacer
    `[...rows].sort(...)` par `rows.sort(...)` le fait tomber.
    """
    desordre = ["VCNE", "ADH", "SNA", "MSA", "CIM"]
    r = _lancer_visrows(desordre)
    assert r["classement"] == desordre, (
        f"le classement a été réordonné : {r['classement']}"
    )


def test_le_tri_survit_a_la_recherche():
    """Filtrer ne doit pas rendre l'ordre au hasard du classement."""
    desordre = ["VCNE", "ADH", "SNA", "MSA", "CIM", "SOT", "SMI"]
    r = _lancer_visrows(desordre, "S")
    attendu = sorted(c for c in desordre if "S" in c or "S" in f"SOCIÉTÉ {c}")
    # la recherche porte aussi sur le nom « Société XXX », qui contient S :
    # tous les codes passent donc le filtre, et seul l'ordre est en jeu.
    assert r["vus"] == sorted(desordre), (
        f"ordre obtenu {r['vus']}, attendu {sorted(desordre)}"
    )
    assert attendu  # l'attendu n'est pas vide par construction
