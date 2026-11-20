"""La version téléphone du terminal — 29/09/2026.

⚠️ 20/11/2026 — classement allégé : les colonnes du classement se masquent
désormais par CLASSE (`c-titre`, `c-cours`…), plus par position. Les tests
qui liaient les positions nth-child à la liste des en-têtes sont remplacés
par ceux de `tests/test_classement_allege.py` (même garantie : le téléphone
cache exactement ce qu'il doit, et le contrôle voit l'ancien défaut).
"""

from __future__ import annotations

import re
from pathlib import Path

SRC = (Path(__file__).resolve().parent.parent / "terminal.src.html").read_text(encoding="utf-8")

def test_les_regles_mobiles_existent():
    css = SRC[SRC.index("VERSION TÉLÉPHONE"):SRC.index("</style>")]
    # 07/10/2026 : la rangée d'onglets disparaît sous 640 px (le MENU donne
    # toutes les vues) ; seul RETOUR reste, et seulement s'il sert.
    # 19/11/2026 : « .entete{position:static » retirée — seule la ligne du
    # MENU reste collée, sur téléphone aussi (tests/test_cadre_commun.py).
    for regle in (".bandeau-defilant{display:none", ".onglets .onglet{display:none",
                  ".onglets.sans-retour{display:none", ".carte-indices>.carte-ind{display:none",
                  ".indices-ligne{display:flex", ".classement{min-width:0",
                  ".bandeau-masi{flex-wrap:wrap"):
        assert regle in css, regle
    assert 'className={"onglets"+(peutRevenir?"":" sans-retour")}' in SRC
    # Les classes utilisées par le CSS sont bien posées dans le JSX.
    for classe in ("entete", "onglet", "carte-ind", "indices-ligne", "classement", "bandeau-masi",
                   # badge-version et entete-droite : retirés du cadre le 19/11/2026
                   # secteur-societe : retiré du classement le 20/11/2026 (le
                   # secteur passe au survol du nom, au filtre et sur la fiche)
                   "nom-societe"):
        assert re.search(rf'className="(?:[^"]* )?{classe}(?: [^"]*)?"', SRC), classe


def test_ouverture_et_volume_restent_lisibles_sur_telephone():
    """Demande du 30/09/2026 : les colonnes OUVERT et VOLUME sont masquées
    sur téléphone, leurs valeurs passaient sous la clôture et la variation.

    20/11/2026 (classement allégé) : la ligne du téléphone ne porte plus que
    titre, cours et variation, Score BVC et confiance. Le montant échangé et
    l'ouverture restent lisibles EN TOUCHANT LA LIGNE : la fiche donne le
    montant dans « En bref » (« … DH échangés ») et l'ouverture dans la
    légende du graphique (O, H, B, C de la dernière séance, affichée sans
    survol). Sur ordinateur, « Plus de colonnes » les rappelle au classement."""
    assert SRC.count('className="mobile-seul"') == 2      # variation et confiance
    avant_media = SRC[:SRC.index("@media(max-width:640px)")]
    assert ".mobile-seul{display:none}" in avant_media
    i = SRC.index("const EnTeteEssentiel=")
    assert "const dh=r.echange_dh;" in SRC[i:i + 400]
    assert '${lab("O")} ${val(d.open)}' in SRC and "legende(iDerAxe);" in SRC
    assert '{plus&&<td className="c-ouv"' in SRC and "{nombreInsecable(volumeCourt(r))}" in SRC


def test_le_volume_s_affiche_en_dirhams_et_jamais_une_quantite_sous_l_etiquette_dh():
    """30/09/2026 : « au lieu d'afficher le volume en DH il affiche la
    quantité échangée ». Le montant d'abord ; à défaut, des TITRES, dits tels."""
    i = SRC.index("const volumeCourt=")
    corps = SRC[i:i + 300]
    assert corps.index("r.echange_dh!=null") < corps.index("r.vol")
    assert "titres`" in corps


def test_la_variation_montre_sa_reference():
    """MNG le 29/09 : veille 1 580, ouverture 1 600, clôture 1 600, +1,27 %.
    Sans la veille à l'écran, la variation semblait fausse."""
    # ⚠️ Servie par la source : déduite du % arrondi, elle valait 1 579,93.
    assert "réf. {px(r.reference)}" in SRC and "reference:t.reference" in SRC


def test_la_carte_des_indices_reserve_sa_place_au_chargement():
    """07/10/2026 : sans carte tant que `masi` était vide, l'en-tête grandissait
    à son arrivée (CLS 0,82 mesuré à 1440 px). Le gabarit garde la place."""
    # 19/11/2026 : les deux reçoivent l'état de la séance et ↻ (ligne du téléphone).
    assert ("masi?<CarteIndices masi={masi} avant={badge} apres={actualiser}/>"
            ":<CarteIndices masi={GABARIT_MASI} gabarit avant={badge} apres={actualiser}/>") in SRC
    assert "[data-gabarit] .carte-ind *" in SRC


def test_la_colonne_couleur_tient_dans_l_ecran_du_telephone():
    """07/10/2026 : à 390 px la colonne COULEUR finissait à 409 px. Le
    remplissage posé sur TOUT son contenu (rond compris) la portait à 92 px.

    20/11/2026 : COULEUR est fondue dans la colonne du Score BVC ; la même
    garde vaut pour ses états, dans une colonne de largeur FIXE (mesuré à
    390 px : « Données insuffisantes » sur deux lignes, tableau à 362 px)."""
    css = SRC[SRC.index("VERSION TÉLÉPHONE"):SRC.index("</style>")]
    assert ".classement .c-score .etat-score *{font-size:12px!important;letter-spacing:0!important;white-space:normal!important}" in css
    assert ".classement{min-width:0!important;table-layout:fixed}" in css
    assert ".classement .c-score{width:118px;max-width:118px}" in css
    assert "padding:3px 5px!important" not in css
    assert ".classement .ligne-ticker{flex-wrap:wrap" in css and 'className="ligne-ticker"' in SRC


def test_les_boutons_du_graphique_ont_une_zone_tactile_de_44_px():
    """07/10/2026 : sous pointer:coarse, ⟳ n'offrait que 30 px de large et les
    zones de deux rangées se chevauchaient (15 paires mesurées à 390 px)."""
    i = SRC.index("@media (pointer:coarse)")
    bloc = SRC[i:SRC.index("\n    }", i)]
    assert ".btn-graphe{min-width:38px;}" in bloc
    assert ".btn-graphe::after{inset:-6px -3px!important;}" in bloc
    assert ".barre-graphe{row-gap:12px!important;}" in bloc
    assert SRC.count('className="btn-graphe"') >= 5 and SRC.count('className="barre-graphe"') == 2


def test_l_etoile_des_favoris_se_voit_et_se_touche():
    """07/10/2026 : ☆ en #2a3550 sur le fond — contraste 1,59, 10×14 px."""
    assert SRC.count('className="etoile"') == 2
    assert '"#ffd740":"#2a3550"' not in SRC
    assert ".etoile{display:inline-flex;align-items:center;justify-content:center;min-width:32px;min-height:32px" in SRC


def test_les_teintes_sombres_ne_servent_plus_qu_au_decor():
    """07/10/2026 : #4a5570 et #2a3550 (contraste ~1,6 à 2,5) portaient des
    textes à lire — légende des signaux, « SCORE », RETOUR. Ils restent pour
    le décor : ○ de la confiance, ◆ du bandeau, ▲▼, états vides, bordures."""
    textes = re.findall(r'color:[^,}]*"#(?:4a5570|2a3550)"[^>]*>([^<]*)<', SRC)
    assert sorted(t.strip() for t in textes) == sorted(
        ['{"○".repeat(5-conf)}', '{ouvert?"▲":"▼"}', "◆", "★", "FIL VIDE"]), textes


def test_la_fiche_sur_telephone_commence_par_la_fiche():
    """07/10/2026 : 80 boutons de titres avant la fiche, et la fiche ouverte
    hors de l'écran (y = −192 à 390 px)."""
    assert SRC.count('className="selecteur-titres"') == 2
    assert ".selecteur-titres{display:none!important}" in SRC[SRC.index("VERSION TÉLÉPHONE"):SRC.index("</style>")]
    assert 'refFiche.current.scrollIntoView({block:"start"})' in SRC


def test_plancher_de_police_sur_telephone():
    """07/10/2026 : 413 textes sous 10 px dans le classement à 390 px, le plus
    petit à 8. Toute taille en ligne de 8 à 9,5 px passe à 10 sous 640 px.
    19/11/2026 : le plancher passe à 12 px, de 8 à 11,5 px — détail dans
    tests/test_cadre_commun.py::test_plancher_de_12_px_sur_telephone."""
    css = SRC[SRC.index("VERSION TÉLÉPHONE"):SRC.index("</style>")]
    assert ('[style*="font-size: 8px"],[style*="font-size: 8.5px"],[style*="font-size: 9px"],'
            '[style*="font-size: 9.5px"],') in css
    assert '[style*="font-size: 11.5px"]{font-size:12px!important}' in css
    tailles = {float(x) for x in re.findall(r"fontSize:(\d+(?:\.\d+)?)[,}]", SRC)}
    assert not {t for t in tailles if t < 12} - {8, 8.5, 9, 9.5, 10, 10.5, 11, 11.5}, \
        "nouvelle taille < 12 px non couverte"


def test_recherche_et_noms_de_societes():
    """07/10/2026 : « Rechercher ticker ou nom… » coupé à 390 px ; 34 noms sur
    80 tronqués sur une ligne. ⚠️ tools/qa_navigateur.js cible le champ par
    son aria-label : le changer impose de changer le contrôle."""
    assert 'placeholder="Ticker ou société" aria-label="Rechercher un titre"' in SRC
    qa = (Path(__file__).resolve().parent.parent / "tools" / "qa_navigateur.js").read_text(encoding="utf-8")
    assert 'input[aria-label="Rechercher un titre"]' in qa
    i = SRC.index('className="nom-societe"')
    assert "WebkitLineClamp:2" in SRC[i:i + 300] and 'whiteSpace:"nowrap"' not in SRC[i:i + 300]


def test_l_ouverture_dure_800_ms_et_une_fois_par_appareil():
    """07/10/2026 : 1 863 ms mesurés sans son, rejouée à chaque onglet."""
    i = SRC.index("const Intro=")
    corps = SRC[i:SRC.index("const Tuile=")]
    assert 'localStorage.getItem("bvc_intro")' in corps and "sessionStorage" not in corps
    assert 'try{localStorage.setItem("bvc_intro","1");}catch(e){}' in corps
    assert re.findall(r"setTimeout\(\(\)=>setVu\(true\),(\d+)\)", corps) == ["800", "800", "500"]
    assert "animation:intro-sortie 200ms ease-in 600ms both;" in SRC


def test_chaque_cotation_des_marches_mondiaux_renvoie_a_sa_source():
    """07/10/2026 — « sur matière première je veux pouvoir cliquer sur la
    source pour vérifier ». Le lien est construit depuis le ticker de la
    source (« COMEX:GC1! » → /symbols/COMEX-GC1!/), sous chaque ligne de
    l'onglet Marchés mondiaux et de la carte Matières premières du briefing.
    Vérifié au navigateur : 12 liens dans l'onglet, 5 dans le briefing.
    """
    src = (Path(__file__).resolve().parent.parent / "terminal.src.html").read_text(encoding="utf-8")
    assert "https://www.tradingview.com/symbols/${t.replace(\":\",\"-\")}/" in src
    assert src.count("<SourceCotation l=") >= 2, "un des deux affichages a perdu son lien source"
def test_la_ligne_du_telephone_porte_le_volume_et_ne_defile_plus():
    """07/10/2026 — « je vois pas Masi journalier ni le volume global ».

    Sous 640 px, les trois cartes laissent place à `indices-ligne`. Elle
    DÉFILAIT : à 390 px la variation du MASI 20, les hausses/baisses et le
    bouton 📈 sortaient de l'écran, et le volume de la séance n'y figurait
    pas. Mesuré au navigateur après correctif : tout visible à 360 et 390 px.
    """
    src = (Path(__file__).resolve().parent.parent / "terminal.src.html").read_text(encoding="utf-8")
    css = src[src.index(".indices-ligne{"):].split("}", 1)[0]
    assert "flex-wrap:wrap" in css, "la ligne des indices doit passer à la ligne, pas défiler"
    debut = src.index('<div className="indices-ligne">')
    ligne = src[debut:src.index('<div className="carte-ind"', debut)]
    assert "{volume}" in ligne, "le volume de la séance a disparu de la ligne du téléphone"
    assert "setGraphe" in ligne, "le bouton du graphique du MASI a disparu de la ligne du téléphone"


def test_le_terminal_s_ouvre_toujours_sur_l_accueil():
    """07/10/2026 — « à chaque fois que je lance le lien, il s'ouvre sur CMT ».
    Le dernier onglet était mémorisé : quitté sur une fiche, le terminal
    rouvrait la fiche (titre par défaut CMT). Vérifié au navigateur avec
    bvc_tab=detail en mémoire : ouverture sur ACCUEIL ; #onglet=ranking →
    CLASSEMENT."""
    src = (Path(__file__).resolve().parent.parent / "terminal.src.html").read_text(encoding="utf-8")
    debut = src.index("const [tab,setTab]=useState(")
    init = src[debut:src.index(";", src.index("return \"accueil\"", debut)) + 1]
    assert "bvc_tab" not in init and "localStorage" not in init, "l'onglet d'ouverture relit la mémoire"
    assert 'return "accueil"' in init
