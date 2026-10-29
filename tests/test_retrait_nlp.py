"""Le pilier NLP est RETIRÉ de ce que voit l'investisseur — 28/10/2026.

Décision d'Abd Moutalib : « le corpus à supprimer et tout ce qui est NLP ».
Le pilier pesait 0 depuis le 25/09 et ses bonus étaient gelés depuis le
29/09 ; il restait pourtant à l'écran (colonnes NLP%, SM~, ALPHA, onglets
SMART MONEY et NLP CORPUS, compteur de messages, tableaux écrits en dur tirés
du corpus) et dans data.json (`nlp`, `nlp_corpus`, `nlp_news`, `score_nlp`,
`alpha`, `win`, `biais`, `conv`, `poids.n`).

Le lot 1 retire ce que voit l'investisseur. Le lot 2 retire le moteur : la
table `SENTIMENT` et son chargement depuis `whatsapp_analysis/output/`, le
pilier de `compute_v53` / `get_weights`, le sentiment d'actualités
(`pipeline/news_sentiment.py`), `warn` / `warnMsg`, `sync_sentiment.py` et
`pipeline/smart_money/alpha.py`. `whatsapp_analysis/` part au lot 3.

⚠️ Deux tableaux en dur du terminal portaient, d'après un audit, des entrées
non pseudonymisées. Ils disparaissent avec le reste ; ce fichier ne recopie
AUCUN de leurs contenus — il ne cherche que des NOMS DE CODE et des formes
(`M####`), jamais une valeur (INCIDENT_VIE_PRIVEE.md, règle 1).

Mesure R8 (essai à blanc, même origin/main, avant/après) : v53, signaux,
confiance et rangs identiques sur 80/80 ; aucun autre champ ne bouge.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parent.parent
SRC = (RACINE / "terminal.src.html").read_text(encoding="utf-8")
COMPILE = (RACINE / "index.html").read_text(encoding="utf-8")
MOTEUR = (RACINE / "update_data.py").read_text(encoding="utf-8")

TRANSITION = "⏳ À RETIRER APRÈS LE PREMIER RUN update_bvc SUIVANT LA FUSION"

# Les champs qui ne sont plus publiés dans data.json. `warn` / `warnMsg`
# (alerte « alpha historique négatif », lue dans le corpus, toujours fausse
# depuis le 29/09) s'y ajoutent au lot 2.
CHAMPS_RETIRES = ("nlp", "nlp_corpus", "nlp_news", "score_nlp",
                  "alpha", "win", "biais", "conv", "warn", "warnMsg")


def _decoder(t: str) -> str:
    """Babel échappe les caractères non ASCII (« é » → « \\xE9 »)."""
    t = re.sub(r"\\u\{([0-9A-Fa-f]+)\}", lambda m: chr(int(m.group(1), 16)), t)
    t = re.sub(r"\\u([0-9A-Fa-f]{4})", lambda m: chr(int(m.group(1), 16)), t)
    return re.sub(r"\\x([0-9A-Fa-f]{2})", lambda m: chr(int(m.group(1), 16)), t)


# ── 1. Le terminal ─────────────────────────────────────────────────────────

# Identifiants des tableaux et composants tirés du corpus. Un seul qui revient
# — dans la source OU dans la page servie — fait rougir.
IDENTIFIANTS_INTERDITS = (
    "NLP_SM", "NLP_RANKS", "NLP_CORPUS", "NLP_LANGS", "NLP_SIGS",
    "NLP_RECENT6M", "NLP_FG", "NlpDash", "MEMBERS", "CHAT", "META",
    "NLP_TICKERS",
)

# Textes affichés que le retrait doit avoir emportés.
TEXTES_INTERDITS = (
    "NLP CORPUS", "SMART MONEY", "SM~", "NLP%", "Alpha 12M", "Smart Sentiment",
    "Biais groupe", "Score SM", "Win Rate", "Timeliness", "CORPUS WHATSAPP",
    "Messages analysés", "messages analysés", "signaux NLP", "NLP Comportemental",
    "★★★★", "SM_HEUR_NON_CALIBRE", "MASI 1 · NLP", "NLP ✓",
)

# Tout compteur de messages : « 896 907 msgs », « 91 748 messages »…
COMPTEUR_MESSAGES = re.compile(r"\d{1,3}(?:[\s\u202f\u00a0]\d{3})+\s*(?:msgs|messages)\b",
                               re.IGNORECASE)
# Pseudonymes de membres du groupe (forme M####) : aucune table de membres ne
# doit subsister dans la page.
PSEUDONYME = re.compile(r"\bM\d{4,}\b")


def _fautes(texte: str) -> list[str]:
    texte = _decoder(texte)
    f = [i for i in IDENTIFIANTS_INTERDITS
         if re.search(r"\bconst\s+" + i + r"\s*=", texte) or re.search(r"\b" + i + r"\b", texte)]
    f += [t for t in TEXTES_INTERDITS if t in texte]
    f += [f"compteur : {m.group(0)}" for m in COMPTEUR_MESSAGES.finditer(texte)]
    if PSEUDONYME.search(texte):
        f.append("pseudonyme de membre (M####)")
    return f


@pytest.mark.parametrize("nom", ["terminal.src.html", "index.html"])
def test_aucune_trace_du_corpus_dans_le_terminal(nom):
    fautes = _fautes({"terminal.src.html": SRC, "index.html": COMPILE}[nom])
    assert not fautes, f"{nom} : le corpus NLP réapparaît — {fautes}"


def test_le_controle_voit_bien_un_retour():
    """Contrôle négatif : une garde jamais vue rouge ne prouve rien. Les
    valeurs injectées sont INVENTÉES — aucune n'est tirée de l'ancien tableau."""
    for faux in ('const NLP_SM=[{name:"M9999",tier:"Tier 1"}];',
                 "React.createElement(NlpDash, null)",
                 '"12 345 msgs \\xB7 6 ans"',
                 '{id:"nlp",label:"NLP CORPUS"}',
                 '["NLP%","SM~","ALPHA"]'):
        assert _fautes(faux), faux
    assert not _fautes('const MASI1_TICKERS=new Set(["CMT"]);')


def test_onglets_et_menu_sans_smart_money_ni_nlp():
    for id_ in ("smart", "nlp"):
        assert f'{{id:"{id_}"' not in SRC, f"onglet « {id_} » encore déclaré"
        assert f'tab==="{id_}"' not in SRC, f"onglet « {id_} » encore routé"
    # Un ancien lien `#onglet=nlp` ne doit pas ouvrir une page vide.
    assert "VUES_CONNUES.includes(m[1])" in SRC


def test_le_classement_n_a_plus_de_colonne_ni_de_tri_nlp():
    heads = re.search(r"const HEADS=\[(.*?)\];", SRC).group(1)
    sorts = re.search(r"const SORTS=\[(.*?)\];", SRC).group(1)
    for x in ('"NLP%"', '"SM~"', '"ALPHA"'):
        assert x not in heads, x
    for x in ('"nlp"', '"alpha"'):
        assert x not in sorts, x
    assert 'sort==="nlp"' not in SRC and 'sort==="alpha"' not in SRC
    # L'export CSV ne porte plus les colonnes du corpus.
    assert '"ALPHA","SM_HEUR' not in SRC and "r.alpha||" not in SRC and "r.win||" not in SRC


def test_le_terminal_ne_lit_plus_aucun_champ_du_corpus():
    """Ni au chargement de data.json (`t.nlp`), ni à l'affichage (`r.win`)."""
    lus = sorted({m.group(0) for m in re.finditer(
        r"\b[rt]\.(?:" + "|".join(CHAMPS_RETIRES) + r")\b", SRC)})
    assert not lus, f"champs du corpus encore lus par le terminal : {lus}"


def test_les_actualites_restent_sans_leur_sentiment():
    """Le flux d'actualités RESTE ; seul le sentiment calculé dessus part."""
    assert "<TickerNews sym={sym}/>" in SRC and "const NewsFeed=" in SRC
    assert "a.sentiment" not in SRC
    assert "Ton positif" not in SRC and "Ton négatif" not in SRC


# ── 2. Le moteur ───────────────────────────────────────────────────────────

def test_le_moteur_ne_publie_plus_les_champs_du_corpus():
    """L'enregistrement du titre (update_data.run) ne recopie plus les champs
    du pilier depuis `v53`, et `compute_v53` ne les calcule plus (lot 2)."""
    publies = re.findall(r'^\s*"(' + "|".join(CHAMPS_RETIRES) + r')":\s*v53\b',
                         MOTEUR, re.M)
    assert not publies, f"update_data.py publie encore : {publies}"
    assert '"poids":  v53["poids"],' in MOTEUR
    import update_data
    r = update_data.compute_v53("MNG", 6.0, 7.0, 0, 0.0, {"market_status": "CLOSED"})
    assert not set(CHAMPS_RETIRES) & set(r), sorted(set(CHAMPS_RETIRES) & set(r))
    assert set(r["poids"]) == {"f", "t"}



# ── 3. Le fichier publié ───────────────────────────────────────────────────

def test_le_fichier_publie_ne_porte_plus_le_corpus(titres):
    porteurs = {s: sorted(k for k in CHAMPS_RETIRES if k in t)
                for s, t in titres.items()}
    porteurs = {s: k for s, k in porteurs.items() if k}
    avec_n = sorted(s for s, t in titres.items() if "n" in (t.get("poids") or {}))
    # ⏳ À RETIRER APRÈS LE PREMIER RUN update_bvc SUIVANT LA FUSION
    # (transition du 28/10/2026). Le data.json du dépôt est écrit par le moteur
    # d'AVANT : les 80 titres portent encore tous les champs. TOUS = fichier
    # antérieur au code, on le dit ; une PARTIE seulement = vraie incohérence,
    # on échoue. Dans la CI (tests.yml) et dans update_bvc, le fichier est
    # généré par le code courant : cette échappatoire ne s'y déclenche pas.
    if titres and len(porteurs) == len(titres) and all(
            len(k) == len(CHAMPS_RETIRES) for k in porteurs.values()):
        pytest.skip(f"{TRANSITION} — data.json antérieur au retrait du pilier "
                    f"NLP (28/10/2026)")
    assert not porteurs, f"champs du corpus encore publiés : {dict(list(porteurs.items())[:5])}"
    assert not avec_n, f"`poids.n` encore publié sur {len(avec_n)} titre(s) : {avec_n[:5]}"
