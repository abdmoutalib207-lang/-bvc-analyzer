"""La version téléphone du terminal — 29/09/2026.

Les règles CSS masquent les colonnes du classement PAR POSITION (nth-child).
Si les colonnes sont réordonnées, le téléphone cacherait le score à la place
du volume, sans qu'aucune erreur ne se voie. Ce test lie les positions
supposées par le CSS à la liste réelle des en-têtes.
"""

from __future__ import annotations

import re
from pathlib import Path

SRC = (Path(__file__).resolve().parent.parent / "terminal.src.html").read_text(encoding="utf-8")

# Positions (1-indexées) que la règle mobile laisse visibles.
# ⚠️ Décalées le 29/09/2026 : les colonnes « BVC » et « Δ » (note figée du
# 03/06) ont quitté le classement — voir test_score_canonique.py.
# « SIGNAL » devient « COULEUR » le 07/10/2026 : plus de mot d'action, la
# pastille de couleur de la note (test_couleurs_sans_recommandation.py).
GARDEES = {2: "TICKER", 4: "CLÔT.", 5: "VAR%", 9: "scoreColLabel", 14: "COULEUR"}


def _entetes() -> list[str]:
    m = re.search(r"const HEADS=\[(.*?)\];", SRC)
    assert m, "liste HEADS introuvable"
    return [x.strip().strip('"') for x in m.group(1).split(",")]


def test_les_colonnes_gardees_sur_telephone_sont_les_bonnes():
    h = _entetes()
    for pos, nom in GARDEES.items():
        assert h[pos - 1] == nom, f"colonne {pos} : {h[pos - 1]!r} au lieu de {nom!r}"


def test_les_regles_mobiles_existent():
    css = SRC[SRC.index("VERSION TÉLÉPHONE"):SRC.index("</style>")]
    # 07/10/2026 : la rangée d'onglets disparaît sous 640 px (le MENU donne
    # toutes les vues) ; seul RETOUR reste, et seulement s'il sert.
    for regle in (".entete{position:static", ".onglets .onglet{display:none",
                  ".onglets.sans-retour{display:none", ".carte-indices>.carte-ind{display:none",
                  ".indices-ligne{display:flex", ".classement{min-width:0",
                  ".bandeau-masi{flex-wrap:wrap"):
        assert regle in css, regle
    assert 'className={"onglets"+(peutRevenir?"":" sans-retour")}' in SRC
    # Les classes utilisées par le CSS sont bien posées dans le JSX.
    for classe in ("entete", "onglet", "carte-ind", "indices-ligne", "classement", "bandeau-masi",
                   "badge-version", "choix-score", "entete-droite",
                   "nom-societe", "secteur-societe"):
        assert re.search(rf'className="(?:[^"]* )?{classe}(?: [^"]*)?"', SRC), classe


def test_le_telephone_masque_exactement_les_autres_colonnes():
    """Retirer une colonne décale toutes les suivantes : sans ce test, le
    téléphone montrerait le NLP à la place du signal sans que rien ne casse."""
    css = SRC[SRC.index("Le classement garde"):]
    bloc = css[:css.index("{display:none}")]
    masquees = set()
    for a, b in re.findall(r"td:nth-child\(n\+(\d+)\):nth-child\(-n\+(\d+)\)", bloc):
        masquees |= set(range(int(a), int(b) + 1))
    masquees |= {int(k) for k in re.findall(r"td:nth-child\((\d+)\)", bloc)}
    toutes = set(range(1, len(_entetes()) + 1))
    assert masquees == toutes - set(GARDEES), sorted(masquees ^ (toutes - set(GARDEES)))


def test_ouverture_et_volume_restent_lisibles_sur_telephone():
    """Demande du 30/09/2026 : les colonnes OUVERT et VOLUME sont masquées
    sur téléphone, leurs valeurs passent sous la clôture et la variation."""
    assert SRC.count('className="mobile-seul"') == 2
    assert "ouv. {r.open?px(r.open)" in SRC and "{volumeCourt(r)}" in SRC
    avant_media = SRC[:SRC.index("@media(max-width:640px)")]
    assert ".mobile-seul{display:none}" in avant_media


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
    assert "masi?<CarteIndices masi={masi}/>:<CarteIndices masi={GABARIT_MASI} gabarit/>" in SRC
    assert "[data-gabarit] .carte-ind *" in SRC


def test_la_colonne_couleur_tient_dans_l_ecran_du_telephone():
    """07/10/2026 : à 390 px la colonne COULEUR finissait à 409 px. Le
    remplissage posé sur TOUT son contenu (rond compris) la portait à 92 px."""
    css = SRC[SRC.index("VERSION TÉLÉPHONE"):SRC.index("</style>")]
    assert "td:nth-child(14) *{font-size:10px!important;letter-spacing:0!important;white-space:normal!important}" in css
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
    petit à 8. Toute taille en ligne de 8 à 9,5 px passe à 10 sous 640 px."""
    css = SRC[SRC.index("VERSION TÉLÉPHONE"):SRC.index("</style>")]
    assert ('[style*="font-size: 8px"],[style*="font-size: 8.5px"],[style*="font-size: 9px"],'
            '[style*="font-size: 9.5px"]{font-size:10px!important}') in css
    tailles = {float(x) for x in re.findall(r"fontSize:(\d+(?:\.\d+)?)[,}]", SRC)}
    assert not {t for t in tailles if t < 10} - {8, 8.5, 9, 9.5}, "nouvelle taille < 10 px non couverte"
