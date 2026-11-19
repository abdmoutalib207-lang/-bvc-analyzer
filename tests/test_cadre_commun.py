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
    """Pendant la séance : « cours différés », jamais « temps réel ».
    Après : « Clôture du JJ/MM », JJ/MM étant la séance DES DONNÉES. Entre la
    clôture et la publication du passage de clôture : ni l'un ni l'autre."""
    h = 'horodatage("{}")'
    r = _executer("[" + ",".join([
        f'etatSeance({{isOpen:true}},"2026-11-19",{h.format("2026-11-19T11:02:00Z")})',
        f'etatSeance({{isOpen:false}},"2026-11-19",{h.format("2026-11-19T16:56:21Z")})',
        f'etatSeance({{isOpen:false}},"2026-11-19",{h.format("2026-11-19T12:46:00Z")})',
        f'etatSeance({{isOpen:false}},"2026-11-20",{h.format("2026-11-21T09:00:00Z")})',
        f'etatSeance({{isOpen:false}},"2026-11-19",{h.format("2026-11-20T08:10:00Z")})',
        f'etatSeance({{isOpen:false}},null,{h.format("2026-11-19T16:56:21Z")})',
    ]) + "]")
    textes = [x and x["texte"] for x in r]
    assert textes == ["Séance en cours · cours différés", "Clôture du 19/11",
                      "Séance du 19/11 · clôture pas encore publiée", "Clôture du 20/11",
                      "Clôture du 19/11", None]
    assert "etatSeance(mktStatus,masi&&masi.asof,h)" in ENTETE
    assert "BVC {mktStatus.label}" not in ENTETE
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
