"""L'onglet POIDS dit ce qui compose le score AFFICHÉ, et le guide existe.

CE QUI ÉTAIT FAUX, LE 07/10/2026
────────────────────────────────
L'onglet POIDS affichait encore « Fondamental 47 % · NLP 28 % · Technique
25 % », la formule d'avant le 25/09, et un tableau de contextes dont trois
(Hype spike, Smart Money Tier 1, Titre peu suivi) lisaient un corpus gelé.
Le test comparait alors l'écran à `update_data.get_weights()`.

06/11/2026 — LE SCORE AFFICHÉ CHANGE
────────────────────────────────────
Décision d'Abd Moutalib : la note v5.3 quitte le terminal, le Score BVC
devient le score unique. L'onglet POIDS présente donc ses six facteurs, et
c'est à `pipeline/score_bvc.py` (`POIDS_BVC`) et `pipeline/score_descriptif.py`
(seuils) que l'écran est comparé. Les tests qui confrontaient l'onglet à
`get_weights()` sont remplacés, pas supprimés en silence : ils vérifiaient
l'affichage d'une pondération que le terminal n'affiche plus. La pondération
v5.3 reste vérifiée côté moteur (tests/test_ponderation_*, test_score_*).

Règles testées ici, sans navigateur :

1. Les poids et les seuils affichés sont CEUX DU MOTEUR du Score BVC —
   l'attendu est lu dans le module, pas recopié de l'écran.
2. Les fréquences ne sont plus écrites dans l'écran : il les LIT dans
   datasets/backtests/score_bvc_mesure_courante.json (lot 1.7) ; la
   synchronisation avec l'artefact daté est gardée par
   tests/test_mesure_synchronisee.py.
3. La page « Comment lire l'écran » existe, est atteignable depuis l'en-tête,
   et dit en clair ce que l'outil ne fait pas.
"""

import json
import re
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))
sys.path.insert(0, str(RACINE / "pipeline"))

from pipeline import score_bvc as sb  # noqa: E402
from pipeline import score_descriptif as sd  # noqa: E402

SRC = (RACINE / "terminal.src.html").read_text(encoding="utf-8")
COMPILE = (RACINE / "index.html").read_text(encoding="utf-8")
MOTEUR = (RACINE / "update_data.py").read_text(encoding="utf-8")
ARTEFACT = json.loads((RACINE / "datasets/backtests/score_bvc_2026-11-03.json").read_text(encoding="utf-8"))  # gel hors échantillon (frais, horizon)


def _entre(src, debut, fin):
    i = src.index(debut)
    return src[i:src.index(fin, i)]


ONGLET_POIDS = _entre(SRC, "const FACTEURS_BVC=[", "// ── COMMENT LIRE L'ÉCRAN")
GUIDE = _entre(SRC, "const Guide=(", "\n};\n")


def _fr(x):
    """7.5 → « 7,5 » ; 15.0 → « 15 »."""
    return (f"{x:g}").replace(".", ",")


# ── 1. L'onglet POIDS : les six facteurs du moteur ──────────────────────────

def test_onglet_poids_affiche_les_poids_du_moteur():
    lus = dict((k, int(w)) for k, w in re.findall(r'\["([^"]+)","[^"]+",(\d+),', ONGLET_POIDS))
    assert lus == dict(sb.POIDS_BVC), lus
    assert sum(lus.values()) == 100


def test_onglet_poids_ne_presente_plus_la_ponderation_v53():
    for ancien in ("72,22 %", "27,78 %", "POIDS_CTX", "get_weights", "MODULATION DE LA PONDÉRATION"):
        assert ancien not in ONGLET_POIDS.replace("update_data.get_weights()", ""), ancien
    assert "const POIDS_CTX" not in SRC


def test_onglet_poids_les_seuils_sont_ceux_du_moteur():
    # Sous-poids des moyennes mobiles
    for nom, w in sb.SOUS_MM:
        assert f"{nom} → {w}" in ONGLET_POIDS or f"de sa {nom} → {w}" in ONGLET_POIDS, nom
    # Momentum : bornes RSI et demi-poids
    w = sb.POIDS["momentum"]
    for x in (sd.RSI_MIN, sd.RSI_MAX, sd.RSI_BAS):
        assert _fr(x) in ONGLET_POIDS
    assert f"→ {_fr(w * 0.5)}" in ONGLET_POIDS
    # Activité : [0,8 ; 3] → 1 ; < 0,8 → 0,5 ; > 3 → 0,2 (part du poids)
    w = sb.POIDS["activité"]
    assert sd.points_activite(1.0) == 1 and sd.points_activite(0.5) == 0.5 and sd.points_activite(4) == 0.2
    assert f"de 0,8 à 3 → {_fr(w)} · sous 0,8 → {_fr(w * 0.5)} · au-delà de 3 → {_fr(w * 0.2)}" in ONGLET_POIDS
    # Liquidité et rentabilité : seuils haut / bas
    wl, wr = sb.POIDS["liquidité"], sb.POIDS["rentabilité"]
    assert f"≥ {_fr(sd.LIQ_HAUT / 1e6)} MDH → {_fr(wl)} · ≥ {_fr(sd.LIQ_BAS / 1e6)} MDH → {_fr(wl * 0.5)}" in ONGLET_POIDS
    assert f"≥ {_fr(sd.ROE_HAUT)} % → {_fr(wr)} · ≥ {_fr(sd.ROE_BAS)} % → {_fr(wr * 0.5)}" in ONGLET_POIDS
    # Couverture minimale
    assert f"au moins {sb.COUVERTURE_MIN} % du poids" in ONGLET_POIDS


def test_onglet_poids_lit_la_mesure_dans_le_fichier_publie():
    """Lot 1.7 : plus aucun chiffre de mesure dans l'onglet ; il lit le fichier
    publié (voir tests/test_mesure_synchronisee.py pour l'exactitude)."""
    assert "let MESURE_BVC=null" in ONGLET_POIDS
    assert "datasets/backtests/score_bvc_mesure_courante.json" in ONGLET_POIDS
    assert "useMesureBVC()" in ONGLET_POIDS
    assert "Mesure indisponible" in ONGLET_POIDS
    assert ARTEFACT["frais_aller_retour"] == 0.02 and ARTEFACT["horizon_seances"] == 20
    assert "M.conclusion.texte" in ONGLET_POIDS
    # Les tranches affichées sont celles du backtest
    tr = re.search(r"TRANCHES = \((.*?)\)\n", (RACINE / "pipeline/backtest_score_descriptif.py").read_text(encoding="utf-8"))
    assert [int(x) for x in re.findall(r'\("[^"]+", (\d+),', tr.group(1))] == [0, 40, 60, 75]
    assert [int(x) for x in re.findall(r'\{id:"t\d+",min:(\d+)', SRC)] == [75, 60, 40]


# ── 2. Le guide ────────────────────────────────────────────────────────────

def test_guide_dit_ce_que_l_outil_ne_fait_pas():
    for phrase in ("ne prédit pas", "conseil en investissement", "J+1",
                   "pas de temps réel"):
        assert phrase in GUIDE, phrase
    # Compilé aussi : c'est index.html qui est servi. Babel y échappe les
    # caractères non ASCII (« é » → « \xE9 »).
    assert "ne pr\\xE9dit pas" in COMPILE
    assert "conseil en investissement" in COMPILE


def test_guide_atteignable_depuis_l_en_tete():
    assert '{id:"guide",label:"? COMMENT LIRE"}' in SRC
    assert 'onClick={()=>setTab("guide")}' in _entre(SRC, "const Header=(", "\n};\n")
    assert '{tab==="guide"    &&<Guide setTab={changeTab}/>}' in SRC
    assert '{id:"guide",icone:"?"' in SRC     # menu latéral (téléphone)


def test_le_guide_decrit_le_score_bvc_et_non_la_note_v53():
    """06/11/2026 — remplace `test_seuils_du_signal_sont_ceux_du_moteur`, qui
    vérifiait que le guide citait les seuils de `compute_v53` (6,5 · 5,5 ·
    4,5 · 3,5) : le guide n'explique plus la note v5.3, que le terminal
    n'affiche plus. Les seuils v5.3 restent testés côté moteur."""
    for nom, w in sb.POIDS_BVC:
        assert re.search(rf"{re.escape(nom.replace('_', ' '))}</T> {w}\b", GUIDE, re.I), nom
    assert "Score descriptif, pas une prévision" in GUIDE
    assert f"sous {sb.COUVERTURE_MIN} % du poids" in GUIDE
    # La mesure est lue dans le fichier publié, pas écrite dans le guide.
    assert "useMesureBVC()" in GUIDE and "M.tranches.map" in GUIDE and "M.conclusion.texte" in GUIDE
    assert "Mesure indisponible" in GUIDE
    for ancien in ("Note /10", "≈ 72 %", "≈ 28 %", "6,5", "Note non comparable"):
        assert ancien not in GUIDE, ancien


def test_criteres_de_confiance_sont_ceux_du_moteur():
    meta = _entre(MOTEUR, "def _meta_ticker(", "\ndef ")
    assert "n_echangees >= 15" in meta
    assert ">= 100_000" in meta
    assert "confiance = min(confiance, 2)" in meta       # plafond peu liquide
    for critere in ("prix de la dernière séance", "fondamentaux réels",
                    "≥ 15 séances échangées", "comptes déposés à l'AMMC",
                    "100 000 DH", "2/5 au plus"):
        assert critere in GUIDE, critere
    # Les critères gelés du corpus ne réapparaissent pas.
    assert "mentions" not in GUIDE and "smart money" not in GUIDE.lower()


def test_guide_explique_les_frequences_et_non_verifie():
    assert "% gagnants" in GUIDE and "n cas" in GUIDE and "IC" in GUIDE
    assert "60 séances" in GUIDE        # horizon de la carte Signaux techniques
    assert "60 séances après le signal" in SRC
    # 20/11/2026 (lot 1.6) : « non vérifié » et « ⚠ jj/mm » sont deux entrées
    # du GLOSSAIRE, que le guide rend dans sa section « Glossaire ».
    assert '"non vérifié"' in _entre(SRC, "const GLOSSAIRE={", "\n};\n")
    assert "Object.entries(GLOSSAIRE)" in GUIDE
