"""Glossaire et « Comment lire » en une page — 20/11/2026 (feuille de route,
lot 1.6).

Demande d'Abd Moutalib : « la lecture doit être simple, facile ». Critère de
fin : chaque terme technique de la fiche et du classement a son explication
d'une phrase, accessible depuis le terme lui-même — au survol ET au toucher
(un `title` ne s'ouvre pas au doigt) —, et « Comment lire » rassemble toutes
les définitions.

Mesuré au navigateur (data.json du 20/11, 1 440 px, occurrences de 32
familles de termes) sur le classement et cinq fiches (IAM, ADH, SNP, BAL,
IBM) : avant, AUCUN terme du classement ne s'ouvrait au doigt (241
occurrences en `title` seul, 13 sans rien) et 6 à 9 termes par fiche sur 21
à 26 ; après, tous.

Une seule source : l'objet `GLOSSAIRE` de terminal.src.html, lu par
l'infobulle (`Terme`, `InfobulleRacine`) et par la section « Glossaire » de
« Comment lire ». Ce fichier vérifie :
1. chaque terme de la liste du lot a une entrée ;
2. chaque définition est UNE phrase, de 200 caractères au plus ;
3. aucun mot d'action ;
4. « Comment lire » rend toutes les entrées (chaque groupe est connu) ;
5. les termes de la fiche et du classement renvoient à la source unique, et
   les anciennes définitions en `title` ont disparu (pas de texte dupliqué) ;
6. l'accessibilité du déclencheur (bouton, aria-describedby, fermeture au
   toucher ailleurs et par Échap, cible ≥ 24 px) ;
7. les faits énoncés sont ceux du code qui les calcule (R12).

Chaque contrôle est une fonction qui rend la liste des défauts ; le contrôle
négatif la passe sur l'ANCIEN code (extraits figés d'origin/main au 20/11)
et sur des variantes fautives, et vérifie qu'elle les voit.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parent.parent
SRC = (RACINE / "terminal.src.html").read_text(encoding="utf-8")
COMPILE = (RACINE / "index.html").read_text(encoding="utf-8")


def _entre(src: str, debut: str, fin: str) -> str:
    i = src.index(debut)
    return src[i:src.index(fin, i)]


def _glossaire(src: str) -> dict[str, dict[str, str]]:
    """Les entrées de `GLOSSAIRE`, une par ligne : id:{g:"…",terme:"…",def:"…"}."""
    if "const GLOSSAIRE={" not in src:
        return {}
    bloc = _entre(src, "const GLOSSAIRE={", "\n};\n")
    lignes = [l for l in bloc.splitlines()[1:] if l.strip()]
    out = {}
    for l in lignes:
        m = re.fullmatch(r'\s+(\w+):\{g:"(\w+)",terme:"([^"]*)",def:"([^"]*)"\},?', l)
        assert m, f"entrée illisible : {l[:80]}"
        out[m.group(1)] = {"g": m.group(2), "terme": m.group(3), "def": m.group(4)}
    return out


def _groupes(src: str) -> list[str]:
    if "const GROUPES_GLOSSAIRE=" not in src:
        return []
    return re.findall(r'\["(\w+)","[^"]+"\]', _entre(src, "const GROUPES_GLOSSAIRE=", ";\n"))


# ── 1. La liste du lot ──────────────────────────────────────────────────────
# Terme demandé → entrée du glossaire, et un mot que la phrase doit contenir
# (pour qu'une entrée vide ou hors sujet ne passe pas).
EXIGES = {
    "PER": ("per", "bénéfice par action"),
    "P/B": ("pb", "fonds propres"),
    "ROE": ("roe", "fonds propres"),
    "rendement du dividende": ("rendement", "dividende"),
    "capitalisation": ("capitalisation", "nombre de ses actions"),
    "liquidité / montant échangé": ("liquidite", "dirhams"),
    "Score BVC": ("score_bvc", "pas une prévision"),
    "tranche du score": ("tranche", "ne dit pas quoi faire"),
    "confiance": ("confiance", "un point par garantie"),
    "n.s.": ("ns", "Non significatif"),
    "—": ("tiret", "rien n'est estimé"),
    "RSI": ("rsi", "14 séances"),
    "MA20/50/200": ("mm", "200 dernières clôtures"),
    "MACD": ("macd", "12 et 26"),
    "Bollinger": ("bollinger", "deux écarts-types"),
    "OBV": ("obv", "cumul des volumes"),
    "couv.": ("couv", "dénominateur"),
    "rupture": ("rupture", "reprise de cotation"),
    "~hist": ("hist", "15 séances"),
    "OPA": ("opa", "visa AMMC"),
    "n.c.": ("nc", "n'a pas échangé"),
    "⚡": ("eclair", "8 %"),
    "semaine close": ("semaine_close", "dernière semaine terminée"),
    "date d'arrêté des comptes": ("date_arrete", "comptes"),
}


def controle_liste(src: str) -> list[str]:
    g = _glossaire(src)
    defauts = []
    for terme, (cle, mot) in EXIGES.items():
        if cle not in g:
            defauts.append(f"« {terme} » : aucune entrée `{cle}`")
        elif mot not in g[cle]["def"]:
            defauts.append(f"« {terme} » : la phrase ne dit pas « {mot} »")
    return defauts


def test_chaque_terme_du_lot_a_sa_definition():
    assert controle_liste(SRC) == []


def test_confiance_dit_ce_que_garantit_chaque_point():
    """CLAUDE.md, « Score de confiance » : cinq garanties, un point chacune."""
    d = _glossaire(SRC)["confiance"]["def"]
    for garantie in ("cours de la dernière séance", "fondamentaux réels", "15 séances échangées",
                     "comptes déposés à l'AMMC", "100 000 DH"):
        assert garantie in d, garantie
    assert "0 à 5" in d


# ── 2. Une phrase, 200 caractères au plus ───────────────────────────────────
LONGUEUR_MAX = 200


def controle_phrases(src: str) -> list[str]:
    defauts = []
    for cle, x in _glossaire(src).items():
        d = x["def"]
        if len(d) > LONGUEUR_MAX:
            defauts.append(f"{cle} : {len(d)} caractères")
        if not d.endswith("."):
            defauts.append(f"{cle} : ne finit pas par un point")
        # Une seule phrase : ni « ! » ni « ? », et aucun point suivi d'une
        # nouvelle phrase (« . » + majuscule) avant la fin.
        if re.search(r"[!?]", d) or re.search(r"\.\s+[A-ZÀ-Ý«]", d[:-1]):
            defauts.append(f"{cle} : plus d'une phrase")
        if not x["terme"].strip():
            defauts.append(f"{cle} : terme vide")
    return defauts


def test_une_phrase_par_terme():
    assert controle_phrases(SRC) == []


# ── 3. Aucun mot d'action ───────────────────────────────────────────────────
# Le produit décrit, il ne recommande pas (Vision produit ; retrait de la v5.3
# le 06/11/2026). « suracheté / survendu » sont du vocabulaire interprétatif.
MOTS_ACTION = [r"\bachet\w*", r"\bachat\w*", r"\bvend\w*", r"\bvente\b", r"\bévit\w*", r"\bsurveill\w*",
               r"\bprudence\b", r"\bpotentiel\w*", r"\bobjectif\w*", r"\bsignal\b", r"\brecommand\w*",
               r"\bconseil\w*", r"\bopportunit\w*", r"\bsurachet\w*", r"\bsurvend\w*", r"\bà saisir\b",
               r"\bbon moment\b", r"\bcible\w*"]


def controle_mots_action(src: str) -> list[str]:
    defauts = []
    for cle, x in _glossaire(src).items():
        for m in MOTS_ACTION:
            if re.search(m, f"{x['terme']} {x['def']}", re.I):
                defauts.append(f"{cle} : « {m} »")
    return defauts


def test_aucun_mot_d_action():
    assert controle_mots_action(SRC) == []


def test_le_rsi_decrit_ce_qu_il_mesure():
    d = _glossaire(SRC)["rsi"]["def"]
    assert "compare l'ampleur des hausses et des baisses" in d
    assert "70" in d and "30" in d


# ── 4. « Comment lire » rend toutes les entrées ─────────────────────────────

def controle_comment_lire(src: str) -> list[str]:
    defauts = []
    if "const Guide=(" not in src:
        return ["composant Guide absent"]
    guide = _entre(src, "const Guide=(", "\n};\n")
    if "GROUPES_GLOSSAIRE.map(" not in guide or "Object.entries(GLOSSAIRE).filter(([,x])=>x.g===g)" not in guide:
        defauts.append("« Comment lire » ne parcourt pas GLOSSAIRE par groupe")
    groupes = set(_groupes(src))
    g = _glossaire(src)
    if not g:
        defauts.append("GLOSSAIRE absent")
    for cle, x in g.items():
        if x["g"] not in groupes:
            defauts.append(f"{cle} : groupe « {x['g']} » inconnu — l'entrée ne serait pas listée")
    if 'id={`glossaire-${id}`}' not in guide:
        defauts.append("entrées sans ancre glossaire-<id>")
    return defauts


def test_comment_lire_liste_toutes_les_entrees():
    assert controle_comment_lire(SRC) == []


def test_les_reserves_du_guide_restent():
    """L'entrée « non vérifié · ⚠ jj/mm » est fondue dans le glossaire : sa
    réserve (source non recoupée ; cours d'un autre jour) y est, sans
    « prudence »."""
    g = _glossaire(SRC)
    assert "recoupée" in g["non_verifie"]["def"]
    assert "non de la dernière séance" in g["date_ancienne"]["def"]
    guide = _entre(SRC, "const Guide=(", "\n};\n")
    for phrase in ("ne prédit pas", "conseil en investissement", "Score descriptif, pas une prévision",
                   "ne distingue pas les gagnants"):
        assert phrase in guide, phrase


# ── 5. Les termes de l'écran renvoient à la source unique ───────────────────

def _composant(src: str, nom: str) -> str:
    i = src.index(f"const {nom}=")
    j = src.find("\nconst ", i + 1)
    return src[i:j if j > 0 else len(src)]


TABLES = ("TERME_COLONNE", "TERME_FACTEUR_BVC", "TERME_RISQUE", "TERME_DATE")


def _ids_ouverts(corps: str, src: str) -> set[str]:
    """Les termes qu'un bout de code ouvre : `<Terme id="x"`, les chaînes
    d'un `<Terme id={…}>` calculé (« roe » ou « marge_nette »), et les
    tables de correspondance que ce code consulte."""
    ids = set(re.findall(r'<Terme id="(\w+)"', corps))
    for expr in re.findall(r"<Terme id=\{(.*?)\}(?=[ >])", corps):
        ids |= set(re.findall(r'(?<=[?:])"(\w+)"', expr))   # résultats du ternaire, pas ses conditions
    for table in TABLES:
        if f"{table}[" in corps and f"const {table}=" in src:
            ids |= set(re.findall(r':"(\w+)"', _entre(src, f"const {table}=", "};")))
    return ids


# Dans chaque vue, les termes qui doivent s'ouvrir depuis l'écran, et les
# composants qu'elle rend (la fiche délègue la composition du score, les
# trois chiffres, le risque, l'en-tête et la jauge du RSI).
VUES = {
    "Ranking": (["Ranking", "Confiance", "PastilleBVC", "Perime"],
                {"per", "rendement", "score_bvc", "confiance", "liquidite", "rsi", "semaine_close", "couv",
                 "rupture", "hist", "opa", "eclair", "tranche", "donnees_insuffisantes", "suspendu", "reprise",
                 "date_ancienne"}),
    "Detail": (["Detail", "ScoreBVC", "TroisChiffres", "RisqueMesure", "RSIGauge", "EnTeteEssentiel",
                "Confiance", "PastilleBVC", "Perime", "DateChiffre", "DatePER"],
               {"per", "pb", "roe", "marge_nette", "rendement", "capitalisation", "liquidite", "score_bvc",
                "tranche", "confiance", "semaine_close", "date_arrete", "couv", "mm", "rsi", "macd",
                "bollinger", "stoch", "obv", "adx", "extremes", "eclair", "non_verifie", "date_ancienne",
                "donnees_insuffisantes", "suspendu", "reprise", "volatilite", "beta", "perte_max", "var95"}),
}


def controle_renvois(src: str) -> list[str]:
    defauts = []
    g = _glossaire(src)
    tous = _ids_ouverts(src, src)
    for table in TABLES:
        if f"const {table}=" in src:
            tous |= set(re.findall(r':"(\w+)"', _entre(src, f"const {table}=", "};")))
    for cle in sorted(tous):
        if cle not in g:
            defauts.append(f"terme `{cle}` employé à l'écran, absent du glossaire")
    for vue, (composants, attendus) in VUES.items():
        if f"const {vue}=" not in src:
            defauts.append(f"vue {vue} absente")
            continue
        corps = "".join(_composant(src, c) for c in composants if f"const {c}=" in src)
        for cle in sorted(attendus - _ids_ouverts(corps, src)):
            defauts.append(f"{vue} : « {cle} » ne s'ouvre pas depuis le terme")
    # « — », « n.s. », « n.c. » passent par le glossaire.
    if "const lex=" not in src or '<Terme id="tiret"' not in src or '<Terme id="ns"' not in src:
        defauts.append("« — » et « n.s. » ne sont pas des termes (lex)")
    if 'const NON_COTE=<Terme id="nc"' not in src:
        defauts.append("« n.c. » n'est pas un terme")
    return defauts


def test_les_termes_de_la_fiche_et_du_classement_renvoient_au_glossaire():
    assert controle_renvois(SRC) == []


# Les anciennes définitions écrites en `title` (souris seulement) ou en
# légende, chacune dans des mots à elle : elles sont fondues dans GLOSSAIRE.
ANCIENNES_DEFINITIONS = [
    'title="Variation ≥ ±8% — approche limite BVC"',
    'title="Historique insuffisant : moins de 15 séances cotées',
    'title="On-Balance Volume',
    'title="Pas de cotation à la dernière séance',
    '"PER":"Cours ÷ bénéfice par action',
    '"DIVIDENDE":"Rendement du dividende',
    '"CONFIANCE":"Fiabilité des données, de 0 à 5"',
    "CONFIANCE ●●●○○ = fiabilité des données",
    "= moins de 15 séances cotées : RSI et moyennes absents",
    "La couleur situe le score ; elle ne dit pas quoi faire.`}",
    "source non recoupée, prudence",
]


def controle_doublons(src: str) -> list[str]:
    defauts = [f"ancienne définition encore écrite : {a[:50]}" for a in ANCIENNES_DEFINITIONS if a in src]
    for cle, x in _glossaire(src).items():
        if src.count(x["def"]) != 1:
            defauts.append(f"{cle} : la phrase est écrite {src.count(x['def'])} fois")
    return defauts


def test_pas_de_definition_dupliquee():
    assert controle_doublons(SRC) == []


# ── 6. Accessibilité du déclencheur ─────────────────────────────────────────

def controle_accessibilite(src: str) -> list[str]:
    if "const Terme=(" not in src:
        return ["composant Terme absent"]
    defauts = []
    t = _composant(src, "Terme")
    for attendu, quoi in (('<button type="button"', "bouton focusable"),
                          ("aria-describedby={`def-${id}`}", "aria-describedby"),
                          ('onFocus=', "ouverture au clavier"),
                          ('e.pointerType==="mouse"', "survol réservé à la souris"),
                          ("e.stopPropagation()", "le toucher n'ouvre pas la ligne")):
        if attendu not in t:
            defauts.append(f"Terme : {quoi}")
    r = _composant(src, "InfobulleRacine") if "const InfobulleRacine=" in src else ""
    for attendu, quoi in (('role="tooltip"', "role tooltip"),
                          ('id={`def-${id}`}', "définitions cachées référencées"),
                          ('addEventListener("pointerdown",dehors,true)', "fermeture au toucher ailleurs"),
                          ('x.key==="Escape"', "fermeture par Échap"),
                          ("Math.min(300,vw-16)", "largeur bornée à l'écran"),
                          ("Math.max(8,Math.min(", "position bornée aux bords"),
                          ("ReactDOM.createPortal(", "portail (ni rognée ni piégée)")):
        if attendu not in r:
            defauts.append(f"InfobulleRacine : {quoi}")
    if "<InfobulleRacine/>" not in src:
        defauts.append("InfobulleRacine non montée")
    if ".terme::after{" not in src or "width:max(100%,24px);height:max(100%,24px)" not in src:
        defauts.append("cible tactile < 24 px")
    return defauts


def test_accessibilite_du_terme():
    assert controle_accessibilite(SRC) == []


def test_le_bandeau_defilant_reste_inerte():
    """160 boutons qui défilent ne se touchent pas : le bandeau garde du
    texte, avec la même phrase (lue dans GLOSSAIRE) au survol."""
    tape = _composant(SRC, "TickerTape")
    assert "NON_COTE_BANDEAU" in tape and "<Terme" not in tape
    assert "title={GLOSSAIRE.eclair.def}" in tape


def test_le_compile_porte_le_glossaire():
    assert "GLOSSAIRE" in COMPILE and "InfobulleRacine" in COMPILE


# ── 7. Les faits énoncés sont ceux du code (R12) ────────────────────────────

def test_les_faits_sont_ceux_du_moteur():
    g = {k: v["def"] for k, v in _glossaire(SRC).items()}
    moteur = (RACINE / "update_data.py").read_text(encoding="utf-8")
    sd = (RACINE / "pipeline/score_descriptif.py").read_text(encoding="utf-8")
    risque = (RACINE / "pipeline/risque.py").read_text(encoding="utf-8")
    # ⚡ : |variation| ≥ 8 %
    assert '"chg_alert": chg is not None and abs(round(chg, 2)) >= 8.0' in moteur
    assert "au moins 8 %" in g["eclair"]
    # couverture minimale
    assert re.search(r"^COUVERTURE_MIN = 70$", sd, re.M) and "sous 70 %" in g["couv"]
    # confiance : 15 séances échangées, 100 000 DH
    meta = _entre(moteur, "def _meta_ticker(", "\ndef ")
    assert "n_echangees >= 15" in meta and ">= 100_000" in meta
    # indicateurs
    assert "def calc_rsi(closes: pd.Series, period: int = 14)" in moteur
    assert "def calc_macd(closes: pd.Series, fast=12, slow=26, signal=9)" in moteur
    assert "def calc_bollinger(closes: pd.Series, period=20, n_std=2.0)" in moteur
    assert "k_period=14, d_period=3" in moteur and "14 dernières séances" in g["stoch"]
    assert '"ma200": calc_ma(closes, 200)' in moteur
    assert "if len(closes) < period:\n        return None" in moteur      # « — » sous la période
    assert "days=90" in moteur and "weeks=52" in moteur
    # risque : 250 séances, VaR historique à 95 %
    assert "ANNUALISATION = 250" in risque and "250 séances" in g["volatilite"]
    assert "NIVEAU_VAR = 0.95" in risque and "5 %" in g["var95"]
    # tranches : celles de TRANCHES_BVC
    assert [int(x) for x in re.findall(r'\{id:"t\d+",min:(\d+)', SRC)] == [75, 60, 40]
    assert "sous 40, 40 à 59, 60 à 74, 75 et plus" in g["tranche"]


# ── Contrôle négatif ────────────────────────────────────────────────────────
# Extraits figés d'origin/main (20/11/2026, 22658ec52), avant ce lot.
ANCIEN_CLASSEMENT = '''const Ranking=({rows})=>{
  const TITRES_COLONNE={"PER":"Cours ÷ bénéfice par action — « n.s. » : non significatif","DIVIDENDE":"Rendement du dividende : dividende par action ÷ cours","CONFIANCE":"Fiabilité des données, de 0 à 5"};
  return <td className="c-per" title={perNS(r.pe,r.bpa_12m??r.bpa)||undefined}>{perTxt(r.pe,r.bpa_12m??r.bpa)}</td>;
};
const NON_COTE=<span title="Pas de cotation à la dernière séance — aucune variation observée" style={{color:"#8892a4"}}>n.c.</span>;
const Guide=({setTab})=>{
  return <L titre="« non vérifié » · ⚠ jj/mm"><T c="#ff8f00">non vérifié</T> : source non recoupée, prudence.</L>
};
'''


@pytest.mark.parametrize("controle", [controle_liste, controle_comment_lire, controle_renvois,
                                      controle_doublons, controle_accessibilite])
def test_controle_negatif_l_ancien_code_est_refuse(controle):
    assert controle(ANCIEN_CLASSEMENT), controle.__name__


def _remplacer_def(src: str, cle: str, nouvelle: str) -> str:
    d = _glossaire(src)[cle]["def"]
    return src.replace(f'def:"{d}"', f'def:"{nouvelle}"', 1)


def test_controle_negatif_variantes_fautives():
    # un mot d'action
    assert controle_mots_action(_remplacer_def(SRC, "rsi", "Au-dessus de 70, le titre est suracheté : mieux vaut vendre."))
    # deux phrases, et trop longue
    assert controle_phrases(_remplacer_def(SRC, "per", "Cours divisé par le BPA. Il se compare au secteur."))
    assert controle_phrases(_remplacer_def(SRC, "per", "x" * 201 + "."))
    # une entrée retirée
    d = _glossaire(SRC)["obv"]["def"]
    sans_obv = SRC.replace(f'  obv:{{g:"technique",terme:"OBV",def:"{d}"}},\n', "")
    assert sans_obv != SRC and controle_liste(sans_obv) and controle_renvois(sans_obv)
    # un groupe inconnu : l'entrée ne serait pas listée dans « Comment lire »
    assert controle_comment_lire(SRC.replace('opa:{g:"signes"', 'opa:{g:"divers"', 1))
    # un terme de l'écran qui pointe hors du glossaire
    assert controle_renvois(SRC.replace('<Terme id="macd">', '<Terme id="macd_inconnu">', 1))
    # une phrase recopiée ailleurs
    assert controle_doublons(SRC + _glossaire(SRC)["per"]["def"])
    # l'infobulle qui ne se ferme plus au toucher ailleurs
    assert controle_accessibilite(SRC.replace('addEventListener("pointerdown",dehors,true)', "", 1))
