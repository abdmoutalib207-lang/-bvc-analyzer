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

# ⚠️ La transition du lot 1 est retirée le 29/10/2026 : le run update_bvc de
# 22h29 le 28/10, premier après la fusion de #312, a publié un data.json sans
# aucun champ du lot 1 (mesuré : 0/80). Reste celle du lot 2, pour `warn` et
# `warnMsg`, que le moteur cesse de publier avec ce lot.
TRANSITION_LOT2 = "⏳ À RETIRER APRÈS LE PREMIER RUN update_bvc SUIVANT LA FUSION DU LOT 2"

# Les champs qui ne sont plus publiés dans data.json. `warn` / `warnMsg`
# (alerte « alpha historique négatif », lue dans le corpus, toujours fausse
# depuis le 29/09) s'y ajoutent au lot 2.
CHAMPS_RETIRES = ("nlp", "nlp_corpus", "nlp_news", "score_nlp",
                  "alpha", "win", "biais", "conv", "warn", "warnMsg")
CHAMPS_RETIRES_LOT2 = ("warn", "warnMsg")


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



# ── 2 bis. Le moteur ne contient plus le pilier (lot 2) ────────────────────

# Ce qui ne doit plus exister dans le moteur, ni comme nom, ni comme fichier.
NOMS_RETIRES_DU_MOTEUR = ("SENTIMENT", "_load_nlp_csv_overlay", "_apport_actualites",
                          "_NEWS_SENT", "alpha_mesure", "win_mesure",
                          "_replier_comportemental")
FICHIERS_RETIRES = ("sync_sentiment.py", "pipeline/news_sentiment.py",
                    "pipeline/smart_money/alpha.py")
# Les modules qui lisaient le corpus ou en dérivaient. `whatsapp_analysis`
# lui-même part au lot 3 ; ce qui reste ne doit plus en importer.
IMPORTS_INTERDITS = ("whatsapp_analysis", "news_sentiment", "sync_sentiment",
                     "pipeline.smart_money.alpha", "smart_money.alpha")


def _noms_definis(arbre) -> set:
    import ast
    noms = set()
    for n in arbre.body:
        if isinstance(n, (ast.FunctionDef, ast.ClassDef)):
            noms.add(n.name)
        elif isinstance(n, ast.Assign):
            noms |= {t.id for t in n.targets if isinstance(t, ast.Name)}
        elif isinstance(n, ast.AnnAssign) and isinstance(n.target, ast.Name):
            noms.add(n.target.id)
    return noms


def _imports(arbre) -> list[str]:
    import ast
    vus = []
    for n in ast.walk(arbre):
        if isinstance(n, ast.Import):
            vus += [a.name for a in n.names]
        elif isinstance(n, ast.ImportFrom):
            vus.append(n.module or "")
            vus += [f"{n.module}.{a.name}" for a in n.names]
    return vus


def _fautes_moteur(source: str) -> list[str]:
    import ast
    arbre = ast.parse(source)
    f = sorted(_noms_definis(arbre) & set(NOMS_RETIRES_DU_MOTEUR))
    f += sorted({i for i in _imports(arbre)
                 if any(i == x or i.startswith(x + ".") or i.endswith("." + x)
                        for x in IMPORTS_INTERDITS)})
    return f


def test_le_moteur_ne_contient_plus_le_pilier():
    fautes = _fautes_moteur(MOTEUR)
    assert not fautes, f"update_data.py porte encore le pilier NLP : {fautes}"


def test_les_fichiers_du_pilier_sont_retires():
    revenus = [f for f in FICHIERS_RETIRES if (RACINE / f).exists()]
    assert not revenus, f"fichiers du pilier NLP revenus : {revenus}"


def test_aucun_module_du_projet_n_importe_le_corpus():
    """Hors `whatsapp_analysis/` (lot 3), `archive/` et les tests qui
    exercent encore `whatsapp_analysis` jusqu'au lot 3, aucun fichier Python
    n'importe le corpus, le sentiment ou les constantes smart money."""
    exclus = ("whatsapp_analysis", "archive", "tests", "node_modules", ".claude")
    fautes = {}
    for f in RACINE.rglob("*.py"):
        rel = f.relative_to(RACINE)
        if rel.parts[0] in exclus:
            continue
        try:
            imp = _fautes_moteur(f.read_text(encoding="utf-8"))
        except (SyntaxError, UnicodeDecodeError):
            continue
        imp = [i for i in imp if i not in NOMS_RETIRES_DU_MOTEUR]
        if imp:
            fautes[str(rel)] = imp
    assert not fautes, f"modules qui importent encore le corpus : {fautes}"


def test_les_poids_n_ont_que_deux_piliers():
    import update_data
    for ctx in ({}, {"market_status": "CLOSED"}, {"market_status": "OPEN", "masi_ytd": -6.0},
                {"market_status": "CLOSED", "tech_non_fiable": True}):
        w = update_data.get_weights(ctx)
        assert set(w) == {"fondamental", "technique"}, ctx
        assert abs(sum(w.values()) - 1) < 1e-9, ctx


def test_le_controle_du_moteur_voit_bien_un_retour():
    """Contrôle négatif : chaque forme de retour est vue."""
    for faux in ("SENTIMENT = {}\n",
                 "def alpha_mesure(t, s):\n    return None\n",
                 "from whatsapp_analysis.config import BVC_TICKERS\n",
                 "import news_sentiment\n",
                 "from pipeline.smart_money.alpha import SENTIMENT_CORPUS\n",
                 "from pipeline.smart_money import alpha\n"):
        assert _fautes_moteur(faux), faux
    assert not _fautes_moteur("from pipeline.smart_money.fond_score import WACC_REF\n")


# ── 3. Le fichier publié ───────────────────────────────────────────────────

def test_le_fichier_publie_ne_porte_plus_le_corpus(titres):
    porteurs = {s: sorted(k for k in CHAMPS_RETIRES if k in t)
                for s, t in titres.items()}
    porteurs = {s: k for s, k in porteurs.items() if k}
    avec_n = sorted(s for s, t in titres.items() if "n" in (t.get("poids") or {}))
    # ⏳ À RETIRER APRÈS LE PREMIER RUN update_bvc SUIVANT LA FUSION DU LOT 2
    # (transition du 29/10/2026). Le data.json du dépôt est écrit par le moteur
    # d'AVANT le lot 2 : les 80 titres portent encore `warn` et `warnMsg`, et
    # rien d'autre du pilier. TOUS, et exactement ces deux-là = fichier
    # antérieur au code, on le dit ; une PARTIE seulement, ou un champ du
    # lot 1 = vraie incohérence, on échoue. Dans la CI (tests.yml) et dans
    # update_bvc, le fichier est généré par le code courant : cette
    # échappatoire ne s'y déclenche pas.
    if titres and len(porteurs) == len(titres) and all(
            tuple(k) == tuple(sorted(CHAMPS_RETIRES_LOT2)) for k in porteurs.values()):
        assert not avec_n, f"`poids.n` encore publié sur {len(avec_n)} titre(s) : {avec_n[:5]}"
        pytest.skip(f"{TRANSITION_LOT2} — data.json antérieur au retrait de "
                    f"warn / warnMsg (29/10/2026)")
    assert not porteurs, f"champs du corpus encore publiés : {dict(list(porteurs.items())[:5])}"
    assert not avec_n, f"`poids.n` encore publié sur {len(avec_n)} titre(s) : {avec_n[:5]}"


# ── 4. Les actualités : le flux reste, le sentiment part (lot 2) ───────────

TRANSITION_NEWS = "⏳ À RETIRER APRÈS LE PREMIER RUN fetch_news SUIVANT LA FUSION DU LOT 2"


def _articles_types():
    """Un article tel que chaque producteur le fabrique, sans réseau."""
    from datetime import datetime, timezone
    from pipeline import enrich_news, official_news
    brut = {"title": "TGCC : hausse du résultat net", "summary": "", "url": "https://x.ma/a",
            "source": "BourseNews", "category": "bvc", "scope": "MAROC",
            "tickers": ["TGCC"], "sentiment": "POSITIF", "sentiment_lexical": "NEUTRE"}
    return {
        "enrich_news": enrich_news.enrich_article(brut),
        "official_news.annotate_provenance": official_news.annotate_provenance(
            brut, datetime(2026, 10, 29, tzinfo=timezone.utc).isoformat()),
    }


def test_aucun_producteur_n_emet_de_sentiment():
    porteurs = {nom: sorted(k for k in a if k.startswith("sentiment"))
                for nom, a in _articles_types().items()}
    porteurs = {k: v for k, v in porteurs.items() if v}
    assert not porteurs, f"le sentiment réapparaît dans les actualités : {porteurs}"
    src = (RACINE / "pipeline" / "fetch_news.py").read_text(encoding="utf-8")
    assert '"sentiment":' not in src and "def _sentiment" not in src
    assert "POSITIVE_KW" not in src and "NEGATIVE_KW" not in src


def test_radar_et_relais_n_affichent_plus_de_ton():
    for f in ("radar.html", "pipeline/radar_digest.py", "pipeline/radar_telegram.py",
              "pipeline/bvc_agent.py", ".github/workflows/fetch_news.yml"):
        texte = (RACINE / f).read_text(encoding="utf-8")
        for motif in ("a.sentiment", 'get("sentiment")', "get('sentiment')",
                      "TON POSITIF", "TON NÉGATIF"):
            assert motif not in texte, f"{f} lit encore le sentiment : {motif}"


def test_le_flux_d_actualites_publie_ne_porte_plus_le_sentiment():
    import json
    chemin = RACINE / "news.json"
    if not chemin.exists():
        pytest.skip("news.json absent de ce clone")
    articles = json.loads(chemin.read_text(encoding="utf-8")).get("articles") or []
    if not articles:
        pytest.skip("news.json vide")
    porteurs = [i for i, a in enumerate(articles)
                if isinstance(a, dict) and ("sentiment" in a or "sentiment_lexical" in a)]
    # ⏳ À RETIRER APRÈS LE PREMIER RUN fetch_news SUIVANT LA FUSION DU LOT 2
    # (transition du 29/10/2026). Le news.json du dépôt est écrit par le
    # collecteur d'AVANT : tous ses articles portent encore le champ. TOUS =
    # fichier antérieur au code, on le dit ; une PARTIE seulement = un
    # producteur qui n'a pas suivi, on échoue.
    if len(porteurs) == len(articles):
        pytest.skip(f"{TRANSITION_NEWS} — news.json antérieur au retrait du "
                    f"sentiment (29/10/2026)")
    assert not porteurs, (f"{len(porteurs)} article(s) de news.json portent encore "
                          f"un sentiment : {porteurs[:5]}")
