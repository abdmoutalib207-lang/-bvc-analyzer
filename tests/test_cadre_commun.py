"""Le cadre commun du terminal — en-tête et pied (19/11/2026).

Inventaire du bruit, PR 2 : ce que l'en-tête et le pied montrent sur TOUS
les écrans. Affichage seulement — ni moteur, ni données, ni Score BVC.

1. Retraits : horloge à la seconde, point pulsant, badge « v6.4 », doublons
   du nombre de titres, bouton de menu flottant du téléphone.
2. Reformulations : date des données, état de la séance, largeur du marché,
   carte MASI 20 ; le nombre de transactions quitte le cadre.
3. Bandeau défilant masqué sur téléphone.
4. Seule la première ligne de l'en-tête reste collée.
5. Lisibilité : plancher de 12 px sur téléphone, avertissement en 13 px et
   contrasté, gris #5a6478 retiré du texte.

Les mesures en navigateur (hauteurs, part de texte sous 12 px) sont dans le
compte rendu de la PR ; ces tests verrouillent le code qui les produit.
"""
from __future__ import annotations

import re
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
SRC = (RACINE / "terminal.src.html").read_text(encoding="utf-8")


def _entre(s: str, debut: str, fin: str) -> str:
    i = s.index(debut)
    return s[i:s.index(fin, i)]


def _sans_commentaires(s: str) -> str:
    s = re.sub(r"/\*.*?\*/", " ", s, flags=re.S)
    s = re.sub(r"\{/\*.*?\*/\}", " ", s, flags=re.S)
    return re.sub(r"(?<![:\"'])//[^\n]*", " ", s)


ENTETE = _sans_commentaires(_entre(SRC, "const Header=(", "\n};\n"))
APP = _sans_commentaires(_entre(SRC, "function App(", "\nclass ErrorBoundary"))


# ── 1. Retraits ─────────────────────────────────────────────────────────────

def test_plus_d_horloge_a_la_seconde_dans_l_en_tete():
    """L'heure de l'appareil, rafraîchie chaque seconde, se lisait comme un
    temps réel que le produit n'a pas. Seule la date des données reste."""
    assert "setClock" not in ENTETE and "{clock}" not in ENTETE
    assert "setInterval" not in ENTETE, "l'en-tête ne doit plus rien animer à intervalle"
    assert 'second:"2-digit"' not in ENTETE


def test_plus_de_point_pulsant():
    assert "pulse" not in ENTETE
    assert "transition:\"background .4s\"" not in ENTETE


def test_plus_de_badge_de_version():
    code = _sans_commentaires(SRC)
    assert "v6.4 — SCORE BVC" not in code
    assert 'className="badge-version"' not in code and ".badge-version" not in code


def test_plus_de_doublons_du_nombre_de_titres():
    code = _sans_commentaires(SRC)
    assert "données: {src}" not in code
    assert "BVC · {univers" not in code and 'className="entete-droite"' not in code
    assert "Clôture · ${nLive} titres" not in code and "setSrc(" not in code


def test_plus_de_bouton_de_menu_flottant():
    """Le MENU de la ligne collée suffit : le rond flottant le doublait et
    masquait le bas de l'écran du téléphone."""
    code = _sans_commentaires(SRC)
    assert "menu-flottant" not in code
    assert "setLoin" not in code


# ── 3. Bandeau défilant ─────────────────────────────────────────────────────

def _css_telephone() -> str:
    css = SRC[:SRC.index("</style>")]
    i = css.index("VERSION TÉLÉPHONE")
    return css[i:css.index("@keyframes ticker", i)]


def test_le_bandeau_defilant_est_masque_sur_telephone_seulement():
    tape = _entre(SRC, "const TickerTape=", "\n};\n")
    assert 'className="bandeau-defilant"' in tape
    assert ".bandeau-defilant{display:none!important}" in _css_telephone()
    # ailleurs, il reste : aucune autre règle ne le masque
    hors = SRC[:SRC.index("</style>")].replace(_css_telephone(), "")
    assert "bandeau-defilant" not in hors
    assert "{etatDonnees===\"ok\"&&<TickerTape rows={rows}/>}" in SRC


# ── 4. Seule la première ligne reste collée ─────────────────────────────────

def test_seule_la_premiere_ligne_est_collee():
    """Deux blocs frères : .entete (collé : marque, MENU, ?, date) puis
    .entete-suite (défile : état, indices, Actualiser, onglets). Un élément
    collé ne sort pas de son parent — imbriqués, la ligne partirait avec le
    reste."""
    i = ENTETE.index('className="entete-suite"')
    colle, suite = ENTETE[ENTETE.index('className="entete"'):i], ENTETE[i:]
    assert 'className="entete"' in colle and 'position:"sticky",top:0' in colle
    for x in ("<Marque/>", "<Menu ", 'setTab("guide")', 'className="entete-date"'):
        assert x in colle, x
    for x in ("<CarteIndices", "{actualiser}", "{badge}", 'className={"onglets"'):
        assert x not in colle, f"{x} ne doit pas rester collé"
        assert x in suite, x
    assert "position:\"sticky\"" not in suite
    assert "return(<>" in ENTETE, "les deux blocs doivent être frères"


def test_plus_aucune_regle_ne_decolle_la_ligne_du_menu():
    css = SRC[:SRC.index("</style>")]
    assert ".entete{position:static" not in css
    # la hauteur collée est mesurée et sert au défilement vers une ancre
    assert "html{scroll-padding-top:var(--h-entete,0px)}" in css
    assert '"--h-entete"' in ENTETE and SRC.count('"--h-entete"') == 1


# ── 2. Reformulations ───────────────────────────────────────────────────────

CARTE = _sans_commentaires(_entre(SRC, "const CarteIndices=(", "\n};\n"))


def _executer(appels: str):
    import json
    import shutil
    import subprocess
    import pytest
    if not shutil.which("node"):
        pytest.skip("node absent")
    horloge = _entre(SRC, "const DECALAGES_MAROC=", "async function fetchChart")
    fonctions = _entre(SRC, "function horodatage(iso)", "\n// ── MASI INDEX")
    code = horloge + fonctions + "\nconsole.log(JSON.stringify(" + appels + "));"
    out = subprocess.run(["node", "-e", code], capture_output=True, text=True, check=True).stdout
    return json.loads(out)


def test_date_des_donnees_lisible():
    """« données : 19/11/2026 16:56:21 » → « Données du 19/11 à 16h56 »,
    à l'heure de Casablanca (registre des décalages, pas le navigateur)."""
    r = _executer('[libelleDonnees(horodatage("2026-11-19T16:56:21Z")),'
                  'libelleDonnees(horodatage("2026-07-10T15:05:00Z")),'
                  'libelleDonnees(horodatage("")),horodatage("2026-11-19T16:56:21Z").complet]')
    assert r == ["Données du 19/11 à 16h56", "Données du 10/07 à 16h05", "Données : —",
                 "19/11/2026 16:56:21"]
    assert "libelleDonnees(h)" in ENTETE and "h.complet" in ENTETE   # l'horodatage complet au survol
    assert "{ts||\"—\"}" not in ENTETE


def test_etat_de_la_seance_sans_temps_reel():
    """Pendant la séance : « différé », jamais « temps réel ».
    Après : « Clôture du JJ/MM », JJ/MM étant la séance DES DONNÉES. Entre la
    clôture et la publication du passage de clôture : ni l'un ni l'autre.
    ⚠️ 20/11/2026 (lot 1.2) : le badge est écrit par `libelleCours`, qui lit
    aussi la date du cours et l'heure du relevé (tests/test_cours_de_seance.py)."""
    def lc(asof, releve, maintenant):
        return f'libelleCours({{prix_asof:"{asof}"}},"{releve}",new Date("{maintenant}"))'
    r = _executer("[" + ",".join([
        lc("2026-11-19", "2026-11-19T11:02:00Z", "2026-11-19T11:30:00Z"),
        lc("2026-11-19", "2026-11-19T16:56:21Z", "2026-11-19T17:00:00Z"),
        lc("2026-11-19", "2026-11-19T12:46:00Z", "2026-11-19T15:50:00Z"),
        lc("2026-11-20", "2026-11-21T09:00:00Z", "2026-11-21T09:05:00Z"),
        lc("2026-11-19", "2026-11-20T08:10:00Z", "2026-11-20T08:15:00Z"),
    ]) + "]")
    textes = [x["texte"] for x in r]
    assert textes == ["Cours de séance · 11h02 · différé", "Clôture du 19/11",
                      "Cours de séance du 19/11 · 12h46 · clôture non publiée", "Clôture du 20/11",
                      "Clôture du 19/11"]
    assert "libelleCours({prix_asof:seance||masi.asof},ts,new Date())" in ENTETE
    assert "BVC {mktStatus.label}" not in ENTETE and "etatSeance(" not in ENTETE
    for bloc in (ENTETE, CARTE, _entre(SRC, "function horodatage(iso)", "\n// ── MASI INDEX")):
        assert "temps réel" not in _sans_commentaires(bloc).lower()


def test_largeur_du_marche_en_toutes_lettres():
    r = _executer("[largeurMots(15,45,6),largeurMots(1,2,1),largeurMots(3,4,0)]")
    assert r == [["15 en hausse", "45 en baisse", "6 inchangées"],
                 ["1 en hausse", "2 en baisse", "1 inchangée"],
                 ["3 en hausse", "4 en baisse", "0 inchangée"]]
    assert "largeurMots(masi.hausses,masi.baisses,masi.inchanges??0)" in CARTE
    for code in ("{masi.hausses}▲", "{masi.hausses} ▲", "{masi.baisses}▼", "{masi.baisses} ▼",
                 "{masi.inchanges??0}=", "{masi.inchanges??0} ="):
        assert code not in CARTE, code


def test_le_nombre_de_transactions_quitte_le_cadre():
    """Hors du texte de l'en-tête ; il reste au survol du montant et en clair
    dans le tableau de bord du briefing."""
    assert "transactions</span>" not in CARTE and "transactions comptées" not in CARTE
    assert "toLocaleString(\"fr-FR\")} transactions`" in CARTE      # le title du montant
    assert '<Kpi l="Transactions"' in SRC


def test_la_carte_masi_20_dit_ce_qu_elle_est():
    assert "Indice MASI&nbsp;20 (20 grandes valeurs)" in CARTE
    assert ">MASI&nbsp;20</span>" not in CARTE.replace("letterSpacing:1}}>MASI&nbsp;20</span>", "")


# ── 5. Lisibilité ───────────────────────────────────────────────────────────

def _luminance(h: str) -> float:
    c = [int(h[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    c = [x / 12.92 if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4 for x in c]
    return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]


def _contraste(texte: str, fond: str) -> float:
    a, b = sorted((_luminance(texte), _luminance(fond)), reverse=True)
    return (a + 0.05) / (b + 0.05)


def test_plancher_de_12_px_sur_telephone():
    """Toute taille posée en ligne sous 12 px (8 à 11,5) remonte à 12 sous
    640 px, et les règles par classe aussi."""
    css = _css_telephone()
    for t in ("8", "8.5", "9", "9.5", "10", "10.5", "11", "11.5"):
        assert f'[style*="font-size: {t}px"]' in css, t
    assert '[style*="font-size: 11.5px"]{font-size:12px!important}' in css
    tailles = {float(x) for x in re.findall(r"fontSize:(\d+(?:\.\d+)?)[,}]", SRC)}
    assert not {t for t in tailles if t < 12} - {8, 8.5, 9, 9.5, 10, 10.5, 11, 11.5}, \
        "nouvelle taille < 12 px non couverte par le plancher"
    # aucune règle du bloc téléphone ne repose une taille sous 12 px
    petites = re.findall(r"font-size:(\d+(?:\.\d+)?)px", css)
    assert all(float(x) >= 12 for x in petites), petites   # règles (sans espace) ; les sélecteurs [style*="font-size: 8px"] ont une espace
    for classe in (".tdb-titre", ".tdb-src", ".ef-t thead th", ".ef-c small", ".tdb-puce"):
        assert classe in css, classe


def test_l_avertissement_est_lisible_et_son_texte_inchange():
    pied = _entre(SRC, "const MentionLegale=()=>(", "\n);\n")
    assert 'fontSize:13,lineHeight:1.7,color:"#8892a4"' in pied
    assert "#6b7689" not in pied
    fond = "#%02x%02x%02x" % tuple(round(v + 0.02 * (255 - v)) for v in (8, 13, 26))  # #080d1a + 2 % de blanc
    assert _contraste("#8892a4", fond) >= 4.5
    assert _contraste("#6b7689", fond) < 4.5          # contrôle : l'ancienne teinte échouait
    # le texte, mot pour mot (taille et couleur seulement)
    texte = re.sub(r"<[^>]+>|\{[^}]*\}", " ", pied)
    texte = " ".join(texte.replace("&nbsp;", " ").split())
    for phrase in (
        "AVERTISSEMENT",
        "BVC Analyzer est un outil d'analyse quantitative à vocation informative . Les scores, "
        "signaux et indicateurs présentés ne constituent ni un conseil en investissement, ni une "
        "recommandation personnalisée, ni une offre ou sollicitation d'achat ou de vente "
        "d'instruments financiers.",
        "L'éditeur n'est pas agréé par l'AMMC en qualité de conseiller en investissement "
        "financier. Les données proviennent de sources publiques tierces, sont différées et "
        "peuvent comporter des erreurs ou des omissions ; leur exactitude n'est pas garantie. "
        "L'indicateur de confiance ●●●○○ affiché sous chaque score indique le niveau de "
        "vérification réellement atteint pour cette valeur.",
        "Les performances passées ne préjugent pas des performances futures. Toute décision "
        "d'investissement relève de votre seule responsabilité et devrait être précédée de "
        "l'avis d'un professionnel habilité.",
    ):
        assert phrase in texte, phrase[:60]


def test_le_gris_5a6478_ne_porte_plus_de_texte():
    """#5a6478 sur le fond : 3,26:1 — sous le seuil de 4,5. Il reste
    seulement en fond de barre (part des inchangées)."""
    assert _contraste("#5a6478", "#080d1a") < 4.5 <= _contraste("#8892a4", "#080d1a")
    code = _sans_commentaires(SRC)
    for motif in (r'color:\s*"?#5a6478', r'\?"#5a6478"', r'(?<!background):"#5a6478"', r'fill="#5a6478"'):
        assert not re.search(motif, code), motif
    assert all('background:"#5a6478"' in l for l in code.splitlines() if "#5a6478" in l)


def test_les_textes_svg_et_les_exposants_suivent_le_plancher():
    """Mesuré à 390 px : il restait 84 signes sous 12 px dans la fiche IAM —
    les textes SVG du graphique des états financiers (attribut font-size) et
    les exposants ⚠ ∑ ° (« smaller » = 10 px). ⚠ est une réserve."""
    css = _css_telephone()
    attributs = {x for x in re.findall(r'fontSize="(\d+(?:\.\d+)?)"', SRC) if float(x) < 12}
    assert attributs, "contrôle : le relevé des attributs ne trouve plus rien"
    for x in attributs:
        assert f'svg text[font-size="{x}"]' in css, x
    assert "sup{font-size:12px}" in css


def test_les_tableaux_tiennent_a_12_px_sans_couper_un_nombre():
    """À 12 px le classement mesurait 409 px et le classement PER 413 pour
    362 disponibles. Les mentions secondaires passent à la ligne ; un montant,
    lui, ne se coupe jamais au milieu (« 5 172 » / « 012 DH » se lit comme
    deux nombres)."""
    import json
    import shutil
    import subprocess
    import pytest
    css = _css_telephone()
    assert ".classement .marqueur-offre{white-space:normal!important}" in css
    assert ".classement-per td,.classement-per td *,.classement-per th{white-space:normal!important}" in css
    assert "{nombreInsecable(volumeCourt(r))}" in SRC
    if not shutil.which("node"):
        pytest.skip("node absent")
    f = _entre(SRC, "const nombreInsecable=", "\n\n")
    jsx = '<><span style={{whiteSpace:"nowrap"}}>{t.slice(0,k)}</span>{t.slice(k)}</>'
    assert jsx in f
    code = (f.replace(jsx, "[{nowrap:t.slice(0,k)},t.slice(k)]")
            + "\nconsole.log(JSON.stringify([nombreInsecable('5 172 012 DH'),"
              "nombreInsecable('—'),nombreInsecable('12 titres')]));")
    out = json.loads(subprocess.run(["node", "-e", code], capture_output=True, text=True, check=True).stdout)
    assert out == [[{"nowrap": "5 172 012"}, " DH"], "—", [{"nowrap": "12"}, " titres"]]
