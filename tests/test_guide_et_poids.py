"""L'onglet POIDS dit la pondération EN VIGUEUR, et le guide existe.

CE QUI ÉTAIT FAUX, LE 07/10/2026
────────────────────────────────
L'onglet POIDS affichait encore « Fondamental 47 % · NLP 28 % · Technique
25 % », la formule d'avant le 25/09, et un tableau de contextes dont trois
(Hype spike, Smart Money Tier 1, Titre peu suivi) lisent un corpus gelé et
sont retirés du moteur depuis le 29/09. Ce que le moteur applique : base
65,28 / 34,72, NLP à 0, modulée par le marché, technique à 0 sur les titres
peu liquides ou au fixing.

D'où les deux règles testées ici, sans navigateur :

1. Les pourcentages affichés sont CEUX QUE REND `get_weights()` — l'attendu
   est calculé en appelant le moteur, pas recopié de l'écran.
2. La page « Comment lire l'écran » existe, est atteignable depuis l'en-tête,
   et dit en clair ce que l'outil ne fait pas. Ses seuils sont ceux du code.
"""

import re
from pathlib import Path

from update_data import get_weights

RACINE = Path(__file__).resolve().parent.parent
SRC = (RACINE / "terminal.src.html").read_text(encoding="utf-8")
COMPILE = (RACINE / "index.html").read_text(encoding="utf-8")
MOTEUR = (RACINE / "update_data.py").read_text(encoding="utf-8")


def _entre(src, debut, fin):
    i = src.index(debut)
    return src[i:src.index(fin, i)]


ONGLET_POIDS = _entre(SRC, "const POIDS_CTX=[", "// ── COMMENT LIRE L'ÉCRAN")
GUIDE = _entre(SRC, "const Guide=(", "\n};\n")


def _pct(x):
    """0.6528 → « 65,28 % » ; 1.0 → « 100 % » ; 0.0 → « 0 % »."""
    v = round(x * 100, 2)
    if v == int(v):
        return f"{int(v)} %"
    return f"{v:.2f}".replace(".", ",") + " %"


def _ligne(situation):
    """La ligne du tableau POIDS_CTX qui commence par `situation`."""
    m = re.search(r'\["' + re.escape(situation) + r'","([^"]+)","([^"]+)","([^"]+)"',
                  ONGLET_POIDS)
    assert m, f"ligne absente de l'onglet POIDS : {situation!r}"
    return m.groups()


# ── 1. Plus de 47 / 28 / 25 présentés comme poids en vigueur ────────────────

def test_onglet_poids_ne_presente_plus_47_28_25():
    for ancien in ("47%", "47 %", "28%", "28 %", "25%", "25 %"):
        assert f'"{ancien}"' not in ONGLET_POIDS, (
            f"{ancien} présenté comme un poids dans l'onglet POIDS")


def test_onglet_poids_affiche_la_base_rendue_par_le_moteur():
    w = get_weights({"market_status": "OPEN"})
    assert w["comportemental"] == 0.0
    assert f'["Fondamental","{_pct(w["fondamental"])}"' in ONGLET_POIDS
    assert f'["Technique","{_pct(w["technique"])}"' in ONGLET_POIDS
    assert '["NLP Comportemental","0 %"' in ONGLET_POIDS
    assert _ligne("Séance ouverte — base")[:2] == (
        _pct(w["fondamental"]), _pct(w["technique"]))


def test_chaque_contexte_actif_correspond_a_get_weights():
    cas = {
        "Hors séance (fermé, pré-ouverture)": {"market_status": "CLOSED"},
        "MASI < −5 % depuis janvier": {"market_status": "OPEN", "masi_ytd": -6.0},
        "MASI > +10 % depuis janvier": {"market_status": "OPEN", "masi_ytd": 11.0},
        "Titre peu liquide ou au fixing": {"market_status": "CLOSED", "masi_ytd": -6.0,
                                           "tech_non_fiable": {"motif": "x"}},
        "Publication de résultats": {"market_status": "OPEN", "has_results": True},
    }
    for situation, ctx in cas.items():
        w = get_weights(ctx)
        assert w["comportemental"] == 0.0
        f, t, _ = _ligne(situation)
        assert (f, t) == (_pct(w["fondamental"]), _pct(w["technique"])), situation
    # Le cumul hors séance + MASI baissier, cité dans la justification.
    w = get_weights({"market_status": "CLOSED", "masi_ytd": -6.0})
    assert f'{_pct(w["fondamental"])} / {_pct(w["technique"])}' in ONGLET_POIDS


def test_contextes_morts_marques_retires():
    for situation in ("Hype spike (>2σ NLP)", "Smart Money Tier 1",
                      "Titre peu suivi (NLP)"):
        assert _ligne(situation) == ("—", "—", "retiré le 29/09")
    # `has_results` n'est fourni par aucun appelant : le dire inactif.
    assert '"has_results"' not in _entre(MOTEUR, "mkt_ctx_base = {", "}")
    assert _ligne("Publication de résultats")[2] == "inactif"


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


def test_seuils_du_signal_sont_ceux_du_moteur():
    v53 = _entre(MOTEUR, "def compute_v53(", "\ndef ")
    for seuil, libelle in (("6.5", "ACHETER ★★"), ("5.5", "SURVEILLER ★"),
                           ("4.5", "ATTENDRE"), ("3.5", "ÉVITER")):
        assert re.search(rf'final >= {re.escape(seuil)}:\s*\n\s*sig = "{libelle}"', v53), seuil
        assert seuil.replace(".", ",") in GUIDE


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
    assert "non vérifié" in GUIDE
