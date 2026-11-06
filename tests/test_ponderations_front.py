"""Le terminal n'affiche plus la note v5.3 : le Score BVC est le score unique.

HISTOIRE
────────
Du 08/09 au 05/11/2026, ce fichier vérifiait les VUES DE PONDÉRATION (OFFICIEL,
70/30, 60/40…) : elles recalculaient la note v5.3 dans le navigateur, et la
couleur disparaissait hors de la vue officielle. Version archivée dans
`archive/tests/test_ponderations_front_v53_2026-11-06.py`.

LE 06/11/2026
─────────────
Décision d'Abd Moutalib : la note v5.3 quitte le terminal, le Score BVC
(`score_bvc` de data.json) devient le score unique. Motif : le 05/11 (MASI
+3,33 %), ADH a monté de 4,31 % et sa note v5.3 est passée de 4,59 à 4,37,
parce que la composante technique pénalise un RSI qui monte vers 70.

Les vues de pondération partent avec la note qu'elles recalculaient. Ces
tests vérifient que le retrait est COMPLET (rien à l'écran ne relit v53, sig,
leurs composantes ou leurs poids) et que le contrat de data.json n'a PAS
bougé (le moteur publie toujours v53 et sig — R8, bulletin, backtests).

⚠️ Ces tests lisent le SOURCE du frontend et exécutent certaines fonctions
extraites via node lorsqu'il est disponible.
"""

import json
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parent.parent
SRC = (RACINE / "terminal.src.html").read_text(encoding="utf-8")
MOTEUR = (RACINE / "update_data.py").read_text(encoding="utf-8")


def _sans_commentaires(s: str) -> str:
    s = re.sub(r"/\*.*?\*/", " ", s, flags=re.S)
    s = re.sub(r"\{/\*.*?\*/\}", " ", s, flags=re.S)
    return re.sub(r"(?<![:\"'])//[^\n]*", " ", s)


def _hors_fusion(s: str) -> str:
    """Le source privé de l'énumération de loadData, seul endroit où les
    champs v5.3 sont encore RECOPIÉS (transport, pas affichage)."""
    i = s.index("d.tickers.forEach(t=>{m[t.symbol]={")
    j = s.index("};});", i)
    return s[:i] + s[j:]


# ── 1. Le retrait est complet ───────────────────────────────────────────────

def test_plus_aucune_vue_de_ponderation():
    code = _sans_commentaires(SRC)
    for disparu in ("const PONDERATIONS", "computeDisplayScore", "composantesManquantes",
                    "scoreModeLabel", "poidsAffiches", "scoreMode", "customMode",
                    "SIMULATION", "MODE PERSONNALISÉ", "choix-score", "const WBar"):
        assert disparu not in code, disparu


def test_aucun_affichage_ne_lit_la_note_v53_ni_ses_composantes():
    code = _hors_fusion(_sans_commentaires(SRC))
    # r, d, x, a, b : les variables qui portent une ligne de titre (`f.poids`
    # est le poids d'un FACTEUR du Score BVC, lecture légitime).
    lus = re.findall(r"(?<![A-Za-z0-9_$])[rdxab]\.(v53|sig|poids|score_fond|score_tech|bonus|verdict_plafonne|setup)(?![A-Za-z0-9_])",
                     code)
    assert not lus, f"le terminal relit encore : {sorted(set(lus))}"


def test_plus_de_palier_v53_ni_de_mot_d_action_derive():
    code = _sans_commentaires(SRC)
    for disparu in ("const PALIERS", "palierDe", "couleurNote", "PastilleNote", "PourquoiNote",
                    "couvPartielle", "const nonComparable", "palierTexte", "Score composite / 10",
                    "Pourquoi cette note ?"):
        assert disparu not in code, disparu


def test_le_contrat_de_data_json_ne_change_pas():
    """Le moteur publie toujours v53 et sig : seul l'écran change."""
    assert re.search(r'"v53"\s*:', MOTEUR) and re.search(r'"sig"\s*:', MOTEUR)
    d = json.loads((RACINE / "data.json").read_text(encoding="utf-8"))
    t = d["tickers"]
    assert all("v53" in x and "sig" in x and "score_bvc" in x for x in t), "contrat de data.json rompu"


# ── 2. Le Score BVC prend la place ──────────────────────────────────────────

def test_l_en_tete_annonce_le_score_bvc_et_non_la_ponderation_v53():
    entete = _sans_commentaires(SRC)
    entete = entete[entete.index("const Header=("):]
    entete = entete[:entete.index("\n};\n")]
    assert "v6.4 — SCORE BVC" in entete
    assert "FOND 72" not in entete and "TECH 28" not in entete


def test_tri_par_defaut_score_bvc_et_plus_de_tri_v53():
    assert 'const [sort,setSort]=useState("bvc");' in SRC
    m = re.search(r"const SORTS=\[(.*?)\];", SRC)
    assert m and m.group(1).startswith('["bvc","SCORE BVC"]'), "le Score BVC n'est pas le premier tri"
    assert '"v53"' not in m.group(1) and "SCORE v5.3" not in SRC
    for garde in ('["az","A → Z"]', '["var","VAR%"]', '["rsi","RSI"]'):
        assert garde in m.group(1), garde
    assert 'setTab("per")' in SRC          # le tri par PER garde sa vue


def test_colonnes_du_classement():
    heads = re.search(r"const HEADS=\[(.*?)\];", SRC).group(1)
    cols = [x.strip().strip('"') for x in heads.split(",")]
    assert cols == ["#", "TICKER", "OUVERT", "CLÔT.", "VAR%", "VOLUME", "PE", "DIV%", "SCORE BVC", "RSI", "COULEUR"]


def test_l_export_csv_porte_le_score_bvc_et_plus_v53_ni_sig():
    m = re.search(r"const cols=\[(.*?)\];\s*const rows_csv=(.*?);\n", SRC, re.S)
    assert m, "construction du CSV introuvable"
    cols, lignes = m.groups()
    for c in ('"SCORE_BVC"', '"ETAT_SCORE_BVC"', '"COUVERTURE_PCT"', '"TRANCHE"', '"VERSION_SCORE_BVC"'):
        assert c in cols, c
    for c in ('"SCORE"', '"PONDERATION"', '"COULEUR_NOTE"', '"VERSION_SCORE"'):
        assert c not in cols, c
    assert "valeurBVC(r)" in lignes and "v53" not in lignes and "sig" not in lignes
    # ⚠️ Une valeur absente s'écrit vide, jamais 0 : un chiffre faux voyage plus loin qu'une erreur.
    assert 'v==null?"":String(v)' in lignes


# ── 3. Exécutés : tri et tranches ───────────────────────────────────────────

def _consts_js(*noms: str) -> str:
    out = []
    for nom in noms:
        # jusqu'à la prochaine ligne de tête — un `];` ou `};` de fermeture
        # appartient encore à la constante.
        m = re.search(r"^const " + nom + r"=.*?(?=^[^\s\]\})])", SRC, re.S | re.M)
        assert m, f"const {nom} introuvable"
        out.append(m.group(0))
    return "\n".join(out)


def _executer_js(script: str) -> str:
    node = shutil.which("node")
    if not node:
        pytest.skip("node absent : la fonction ne peut pas être exécutée")
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False) as f:
        f.write(script)
        chemin = f.name
    try:
        r = subprocess.run([node, chemin], capture_output=True, text=True, timeout=20)
    finally:
        Path(chemin).unlink(missing_ok=True)
    assert r.returncode == 0, f"node a échoué : {r.stderr[:400]}"
    return r.stdout.strip()


def test_un_score_absent_se_classe_apres_un_score_de_zero():
    """⚠️ La frontière qui discrimine : face à un score qui VAUT zéro. Par
    coercition `null - x` vaudrait `-x` et l'absent pourrait passer devant.
    L'absent est placé en premier à l'entrée : si le tri ne tranche pas, un
    tri stable le laisse devant."""
    m = re.search(r'if\(sort==="bvc"\)\{(.*?)\n    \}', SRC, re.S)
    assert m, "la branche de tri sur le Score BVC est introuvable"
    lignes = [{"symbol": "ABSENT", "score_bvc": {"valeur": None, "etat": "NON_CALCULABLE"}},
              {"symbol": "PARTIEL", "score_bvc": {"valeur": None, "etat": "PARTIEL"}},
              {"symbol": "ZERO", "score_bvc": {"valeur": 0, "etat": "CALCULABLE"}},
              {"symbol": "SANS"},
              {"symbol": "HAUT", "score_bvc": {"valeur": 77, "etat": "CALCULABLE"}},
              {"symbol": "MOYEN", "score_bvc": {"valeur": 52.5, "etat": "CALCULABLE"}}]
    script = (_consts_js("valeurBVC") + "\nfunction comparer(a, b){" + m.group(1) + "\n}"
              + "\nconst lignes = " + json.dumps(lignes) + ";"
              + "\nconsole.log(lignes.sort(comparer).map(x=>x.symbol).slice(0,3).join(','));")
    assert _executer_js(script) == "HAUT,MOYEN,ZERO"


def test_les_tranches_et_la_partie_entiere():
    """Bornes du backtest : [0,40) · [40,60) · [60,75) · [75,100]. Le nombre
    affiché au classement (partie entière) tombe toujours dans sa tranche :
    74,5 s'écrit 74 et reste dans 60–74 (un arrondi aurait écrit 75)."""
    cas = [74.5, 75, 59.99, 60, 40, 39.9, 0, None]
    script = (_consts_js("TRANCHES_BVC", "TRANCHE_NC", "valeurBVC", "trancheBVC", "entierBVC")
              + "\nconst cas = " + json.dumps(cas) + ";"
              + "\nconsole.log(JSON.stringify(cas.map(v=>{const r={score_bvc:{valeur:v}};"
              + "return [trancheBVC(r).id, entierBVC(valeurBVC(r))];})));")
    assert json.loads(_executer_js(script)) == [
        ["t60", "74"], ["t75", "75"], ["t40", "59"], ["t60", "60"], ["t40", "40"],
        ["t0", "39"], ["t0", "0"], ["nc", "—"]]
