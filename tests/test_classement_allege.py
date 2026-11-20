"""Le classement allégé — 20/11/2026 (feuille de route, phase 1).

Demande d'Abd Moutalib : « faire le nettoyage du bruit sur l'interface, la
lecture doit être simple facile ». Le classement comptait onze colonnes (#,
TICKER, OUVERT, CLÔT., VAR%, VOLUME, PE, DIV%, SCORE BVC, RSI, COULEUR) ;
mesuré au navigateur sur data.json du 20/11 :

                     avant                       après (vue par défaut)
  390 px   5 colonnes, ligne de 72 px      3 colonnes, ligne de 61 px
  768 px   11 colonnes, tableau 1 004 px   7 colonnes, tableau 740 px
           pour 740 (264 px à faire        (aucun défilement)
           défiler), ligne de 77 px        ligne de 54 px
  1440 px  11 colonnes, ligne de 77 px     7 colonnes, ligne de 54 px

Ce qui part et pourquoi, et où l'information reste :
- le rang « # » : l'ordre des lignes le donne déjà ;
- COULEUR : fondue dans la colonne du Score BVC (même tranche, mêmes états
  « Données insuffisantes », « SUSPENDU », « REPRISE DE COTATION ») ;
- la barre sous le score : elle redisait le chiffre ;
- OUVERT (avec la référence de la variation), le MONTANT ÉCHANGÉ et le RSI :
  derrière « Plus de colonnes », et sur la fiche (en-tête « En bref » pour le
  montant, légende du graphique pour l'ouverture, composition du score pour
  le RSI). Le RSI s'affiche de lui-même quand on trie ou filtre sur lui.

⚠️ Les colonnes se désignent par CLASSE (`c-titre`, `c-cours`…) : le
téléphone les cachait par position (nth-child), et retirer une colonne
décalait en silence ce qu'il masquait — d'où les tests de positions de
`test_mobile.py`, devenus sans objet.

Chaque contrôle est une fonction qui rend la liste des défauts ; le contrôle
négatif la passe sur des extraits de l'ANCIEN code et vérifie qu'elle les voit.
"""

from __future__ import annotations

import re
from pathlib import Path

SRC = (Path(__file__).resolve().parent.parent / "terminal.src.html").read_text(encoding="utf-8")

DEFAUT = ["TITRE", "COURS", "VAR%", "SCORE BVC", "CONFIANCE", "PER", "DIVIDENDE"]
PLUS = ["OUVERT", "ÉCHANGÉ", "RSI"]
GARDEES_TELEPHONE = {"c-titre", "c-cours", "c-score"}

# Extraits de l'ancien code (origin/main au 20/11/2026, avant ce lot).
ANCIEN_HEADS = 'const HEADS=["#","TICKER","OUVERT","CLÔT.","VAR%","VOLUME","PE","DIV%","SCORE BVC","RSI","COULEUR"];'
ANCIEN_CSS = """      .classement{min-width:0!important}
      .classement th:nth-child(1),.classement td:nth-child(1),
      .classement th:nth-child(3),.classement td:nth-child(3),
      .classement th:nth-child(n+6):nth-child(-n+8),.classement td:nth-child(n+6):nth-child(-n+8),
      .classement th:nth-child(10),.classement td:nth-child(10){display:none}
"""
ANCIEN_RSI = 'const rsiColor=rsiVal>70?"#ff4f5a":rsiVal<30?"#00e5a0":"#ffd740";'


def _liste(src: str, nom: str) -> list[str] | None:
    m = re.search(rf"const {nom}=\[(.*?)\];", src)
    return None if not m else [x.strip().strip('"') for x in m.group(1).split(",")]


def _ranking(src: str = SRC) -> str:
    i = src.index("const Ranking=")
    return src[i:src.index("// ── CLASSEMENT PAR PER", i)]


def _css_telephone(src: str = SRC) -> str:
    i = src.index("@media(max-width:640px)")
    return src[i:src.index("@keyframes ticker", i)]


# ── Les contrôles ────────────────────────────────────────────────────────────

def defauts_colonnes(src: str) -> list[str]:
    d = []
    heads = _liste(src, "HEADS") or []
    if heads != DEFAUT:
        d.append(f"colonnes par défaut : {heads}")
    if len(heads) > 7:
        d.append(f"{len(heads)} colonnes par défaut, plus de 7")
    if _liste(src, "HEADS_PLUS") != PLUS:
        d.append("« Plus de colonnes » absent ou incomplet")
    for retire in ("#", "COULEUR"):
        if retire in heads:
            d.append(f"colonne « {retire} » encore présente")
    return d


def defauts_telephone(css: str) -> list[str]:
    d = []
    if re.search(r"\.classement (?:th|td):nth-child", css):
        d.append("colonnes du classement cachées par position (nth-child)")
    m = re.search(r"((?:\.classement \.c-[a-z]+,?\s*)+)\{display:none\}", css)
    cachees = set(re.findall(r"\.(c-[a-z]+)", m.group(1))) if m else set()
    toutes = {"c-titre", "c-cours", "c-var", "c-ouv", "c-echange", "c-score", "c-conf", "c-per", "c-div", "c-rsi"}
    if cachees != toutes - GARDEES_TELEPHONE:
        d.append(f"le téléphone cache {sorted(cachees)}")
    return d


def defauts_rsi(src: str) -> list[str]:
    return ["RSI peint en vert/rouge"] if re.search(r"rsiColor\s*=.*#(?:00e5a0|ff4f5a)", src) else []


# ── Sur le code actuel ───────────────────────────────────────────────────────

def test_sept_colonnes_par_defaut_et_trois_derriere_plus_de_colonnes():
    assert defauts_colonnes(SRC) == []


def test_le_telephone_cache_par_classe_et_garde_titre_cours_et_score():
    assert defauts_telephone(_css_telephone()) == []
    # « Plus de colonnes » n'existe pas sur téléphone : la fiche les donne.
    assert ".plus-colonnes{display:none!important}" in _css_telephone()


def test_le_rsi_n_est_plus_peint_en_vert_ou_rouge():
    assert defauts_rsi(SRC) == []
    i = _ranking().index('className="c-rsi"')
    cellule = _ranking()[i:i + 400]
    assert "#00e5a0" not in cellule and "#ff4f5a" not in cellule


# ── Contrôle négatif : les mêmes contrôles voient l'ancien code ─────────────

def test_controle_negatif_sur_l_ancien_code():
    assert any("COULEUR" in x for x in defauts_colonnes(ANCIEN_HEADS))
    assert any("plus de 7" in x for x in defauts_colonnes(ANCIEN_HEADS))
    assert any("nth-child" in x for x in defauts_telephone(ANCIEN_CSS))
    assert defauts_rsi(ANCIEN_RSI) == ["RSI peint en vert/rouge"]


# ── Chaque colonne a sa classe, et l'en-tête suit les cellules ──────────────

def test_chaque_colonne_a_une_classe_et_une_seule_cellule():
    r = _ranking()
    m = re.search(r"const CLASSE_COLONNE=\{(.*?)\};", r, re.S)
    assert m, "table CLASSE_COLONNE introuvable"
    classes = dict(re.findall(r'"([^"]+)":"(c-[a-z]+)"', m.group(1)))
    assert set(classes) == set(DEFAUT + PLUS)
    for nom, cls in classes.items():
        assert r.count(f'<td className="{cls}"') == 1, f"{nom} : cellule {cls} absente ou en double"
    # L'en-tête et les cellules suivent le même ordre : titre, cours, variation,
    # [ouverture, montant], score, confiance, PER, dividende, [RSI].
    ordre = re.findall(r'<td className="(c-[a-z]+)"', r)
    assert ordre == ["c-titre", "c-cours", "c-var", "c-ouv", "c-echange", "c-score",
                     "c-conf", "c-per", "c-div", "c-rsi"]
    assert ('const colonnes=[...HEADS.slice(0,3),...(plus?HEADS_PLUS.slice(0,2):[]),'
            '...HEADS.slice(3),...(voirRSI?["RSI"]:[])]') in r


def test_plus_de_colonnes_se_rappelle_et_le_rsi_suit_son_tri():
    r = _ranking()
    assert 'className="plus-colonnes"' in r and "aria-pressed={plus}" in r
    assert 'lsLire("bvc_classement_plus")' in r and 'lsEcrire("bvc_classement_plus"' in r
    assert '{plus&&<td className="c-ouv"' in r and '{plus&&<td className="c-echange"' in r
    assert '{voirRSI&&<td className="c-rsi"' in r
    assert "const voirRSI=plus||sort===\"rsi\"||rsiZone!=null;" in r
    # La référence de la variation accompagne l'ouverture.
    assert "{plus&&r.reference!=null&&" in r and "réf. {px(r.reference)}" in r


# ── Ce que la ligne du téléphone porte ─────────────────────────────────────

def _cellule(cls: str) -> str:
    r = _ranking()
    i = r.index(f'<td className="{cls}"')
    return r[i:r.index("</td>", i)]


def test_sur_telephone_la_variation_et_la_confiance_passent_dessous():
    assert '<div className="mobile-seul" style={{fontSize:12}}>{variation}</div>' in _cellule("c-cours")
    assert '<div className="mobile-seul" style={{marginTop:2}}><Confiance r={r}/></div>' in _cellule("c-score")
    assert "<Confiance r={r}/>" in _cellule("c-conf")


# ── La règle CLAUDE.md : confiance ≤ 1 ─────────────────────────────────────

def test_donnees_insuffisantes_reste_dans_la_colonne_du_score_et_le_score_grisé():
    c = _cellule("c-score")
    assert "color:couleurChiffre(r)" in c          # gris à confiance ≤ 1
    assert 'meta(r).conf<=1\n                        ? <Chip wrap label="Données insuffisantes"' in c
    # Un titre suspendu passe AVANT la confiance (le titre ne cote plus).
    assert (c.index("meta(r).susp\n") < c.index("meta(r).reprise_recente\n")
            < c.index('meta(r).conf<=1\n                        ? <Chip'))
    assert "<PastilleBVC r={r}/>" in c
    i = SRC.index("const couleurChiffre=")
    assert 'meta(r).conf<=1||valeurBVC(r)==null?"#8892a4"' in SRC[i:i + 120]


# ── Rien de ce qui protège la lecture n'est parti ──────────────────────────

def test_les_reserves_et_les_mentions_restent():
    r = _ranking()
    for m in ("score descriptif, pas une prévision", "couv. ${s.couverture_pct} %", '"⚠ rupture"',
              ">~hist</span>", "OPA {px(meta(r).offre_publique.prix)} DH", "<Perime r={r}/>",
              "NON_COTE", "r.chg_alert", 'label="SUSPENDU"', 'label="REPRISE DE COTATION"',
              "perTxt(r.pe,r.bpa_12m??r.bpa)", "divClassement(r.div)"):
        assert m in r, m
    # Aucun mot d'action dans la vue.
    for mot in ("ACHETER", "VENDRE", "ÉVITER", "SURVEILLER", "prudence"):
        assert mot not in r, mot


def test_la_semaine_du_score_est_dite():
    r = _ranking()
    assert "sem. au {jjmm(semaineCommune)}" in r            # en-tête
    assert "semR!==semaineCommune" in r and "sem. au {jjmm(semR)}" in r   # ligne en écart


def test_les_tris_existants_restent():
    r = _ranking()
    assert _liste(r, "SORTS") is not None
    for t in ('sort==="az"', 'sort==="bvc"', 'sort==="var"', 'sort==="var_asc"', 'sort==="rsi"'):
        assert t in r, t
    assert 'const TRI_COLONNE={"TITRE":"az","VAR%":"var","SCORE BVC":"bvc","RSI":"rsi"};' in r
    assert "const triCroissant=s=>s===\"var_asc\"||s===\"az\"||s===\"rsi\";" in SRC
