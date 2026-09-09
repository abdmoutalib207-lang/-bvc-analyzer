"""Les vues de pondération, et la règle qui les rend honnêtes.

CE QUI EXISTAIT AVANT LE 08/09/2026
───────────────────────────────────
Le terminal portait déjà trois interrupteurs FOND / NLP / TECH qui
recalculaient la note dans le navigateur. Mais **la colonne SIGNAL ne suivait
pas** : elle restait celle produite par le moteur avec 47/28/25.

Les deux colonnes, côte à côte, ne parlaient plus de la même formule, et rien
à l'écran ne le disait. Mesuré : **28 titres sur 80 auraient changé de palier**
si le signal avait suivi la note — BCP de SURVEILLER à ACHETER, TGCC
d'ACHETER à ATTENDRE. Et l'export CSV emportait la même contradiction dans un
fichier qui survit à l'écran.

LA RÈGLE RETENUE
────────────────
UNE pondération est officielle : elle porte le signal, va dans le bulletin, et
pourra un jour être backtestée. Les autres sont des vues d'exploration, et le
signal y disparaît.

**Une note s'explore ; un signal se recommande.** Si l'on peut faire glisser
les poids jusqu'à ce que le classement dise ce qu'on pensait, la note cesse
d'être un jugement et devient le miroir d'une opinion — c'est la définition du
biais de confirmation, et c'est ce que ces tests empêchent.

⚠️ Ces tests lisent le SOURCE du frontend, faute de pouvoir l'exécuter : le
projet n'a pas d'outillage JavaScript en intégration continue. Ils vérifient
donc que les garde-fous sont ÉCRITS. La compilation JSX, elle, se vérifie avec
la skill `run-tests`.
"""

import re
from pathlib import Path

FRONT = Path(__file__).resolve().parent.parent / "index.html"


def _src():
    return FRONT.read_text(encoding="utf-8")


def _bloc_ponderations():
    m = re.search(r"const PONDERATIONS=\[(.*?)\];", _src(), re.S)
    assert m, "le catalogue PONDERATIONS est introuvable"
    return m.group(1)


def _vues():
    """[(nom, f, n, t, officiel)] — lu depuis le source."""
    out = []
    for ligne in re.findall(r"\{nom:\"([^\"]+)\",f:(\d+),n:(\d+),t:(\d+)([^}]*)\}",
                            _bloc_ponderations()):
        nom, f, n, t, reste = ligne
        out.append((nom, int(f), int(n), int(t), "officiel:true" in reste))
    return out


def test_les_six_vues_demandees_existent():
    """OFFICIEL plus les cinq répartitions demandées le 08/09."""
    noms = {v[0] for v in _vues()}
    assert {"OFFICIEL", "70/30", "60/40", "50/50", "40/60", "30/70"} <= noms, (
        f"vues manquantes — présentes : {sorted(noms)}")


def test_une_seule_vue_est_officielle():
    """Deux pondérations officielles, ce serait deux vérités concurrentes."""
    officielles = [v[0] for v in _vues() if v[4]]
    assert officielles == ["OFFICIEL"], f"officielles : {officielles}"


def test_la_vue_officielle_est_la_formule_v53():
    """R8 : la formule publiée reste Fond 47 · NLP 28 · Tech 25."""
    off = [v for v in _vues() if v[4]][0]
    assert (off[1], off[2], off[3]) == (47, 28, 25), (
        f"la vue officielle est {off[1]}/{off[2]}/{off[3]}, pas 47/28/25")


def test_chaque_vue_totalise_cent():
    for nom, f, n, t, _ in _vues():
        assert f + n + t == 100, f"{nom} totalise {f+n+t}, pas 100"


def test_les_vues_de_simulation_ecartent_le_nlp():
    """Elles existent précisément pour répondre à « et sans le NLP ? ».

    Le score NLP mesuré le 08/09 va de 4,80 à 5,30 sur une échelle de 0 à 10,
    avec un écart-type de 0,081 — dix fois moins que le fondamental. Il occupe
    28 % de la note et n'explique pas 2 % des écarts entre titres.
    """
    for nom, f, n, t, officiel in _vues():
        if not officiel:
            assert n == 0, f"{nom} garde un poids NLP de {n}"


def test_le_signal_disparait_hors_du_mode_officiel():
    """LE test qui compte. Sans lui, tout le reste est décoratif."""
    s = _src()
    m = re.search(r"<td style=\{\{padding:\"8px 8px\"\}\}>\{customMode(.{0,400})", s, re.S)
    assert m, ("la cellule SIGNAL ne teste pas `customMode` — une note "
               "recalculée s'afficherait à côté d'un signal calculé autrement")
    assert "—" in m.group(1), "le signal masqué doit afficher un tiret explicite"


def test_le_mode_officiel_rend_le_v53_du_moteur_tel_quel():
    """Le recalculer dans le navigateur donnerait un chiffre légèrement
    différent de celui du bulletin — bonus et malus compris — et personne ne
    saurait lequel croire."""
    m = re.search(r"function computeDisplayScore\(r, p\) \{(.*?)\n\}", _src(), re.S)
    assert m, "computeDisplayScore introuvable"
    assert re.search(r"if \(!p \|\| p\.officiel\) return r\.v53;", m.group(1))


def test_l_export_csv_emporte_la_ponderation():
    """Un CSV survit à l'écran qui l'a produit. Une note sans sa formule est
    ininterprétable, et le signal ne doit pas s'y glisser en simulation."""
    s = _src()
    assert '"PONDERATION"' in s, "la colonne PONDERATION manque dans l'export"
    assert 'customMode?"":(r.sig||"")' in s, (
        "l'export laisse passer le signal en mode simulation")
    assert "scoreModeLabel(scoreMode).replace" in s, (
        "le nom du fichier ne porte pas la pondération")


def test_un_bandeau_signale_la_simulation():
    assert "SIMULATION" in _src(), (
        "rien à l'écran ne distingue une vue d'exploration de la note publiée")


# ── la fiche détaillée ───────────────────────────────────────────────────
#
# ⚠️ CES TESTS N'EXISTAIENT PAS le 08/09, et c'est pourquoi le défaut est
# passé. J'avais fait suivre la pondération au CLASSEMENT en oubliant la
# FICHE. Résultat : le même titre affichait un score dans le tableau et un
# autre sur sa fiche, pour la même vue — et le grand chiffre de la fiche ne
# bougeait jamais. Signalé par Abd Moutalib : « le score ne bouge pas même
# après changement de pourcentage ».
#
# La leçon dépasse ce cas : un réglage qui traverse l'interface doit être
# vérifié À CHAQUE ENDROIT où il s'applique, pas au premier.

def test_la_fiche_detaillee_recoit_la_ponderation():
    assert "const Detail=({rows,sel,setSel,fav=[],toggleFav=()=>{},scoreMode})" in _src(), (
        "le composant Detail ne reçoit pas scoreMode : sa note ne peut pas suivre")
    assert "<Detail rows={rows}" in _src() and "scoreMode={scoreMode}/>" in _src(), (
        "scoreMode n'est pas passé à Detail à l'appel")


def test_la_fiche_affiche_la_note_de_la_vue_choisie():
    """Le grand chiffre de la fiche doit venir de computeDisplayScore, pas de
    `r.v53` — sinon il reste figé sur la formule officielle."""
    s = _src()
    assert "const scoreAffiche=computeDisplayScore(r,scoreMode);" in s
    assert "lineHeight:1}}>{fmt(scoreAffiche)}</div>" in s, (
        "la fiche affiche encore fmt(r.v53) : la note n'y bougera jamais")


def test_le_signal_disparait_aussi_sur_la_fiche():
    """Même règle qu'au classement. Un signal qui survit sur la fiche pendant
    qu'il disparaît du tableau serait pire que pas de règle du tout."""
    s = _src()
    assert 'label="SIMULATION — signal masqué"' in s, (
        "la fiche affiche encore le signal du moteur en mode simulation")


def test_la_fiche_annonce_la_vue_utilisee():
    assert "scoreModeLabel(scoreMode)}</span>" in _src(), (
        "rien sur la fiche ne dit quelle pondération produit le chiffre affiché")


# ── la barre de répartition ──────────────────────────────────────────────
#
# ⚠️ TROISIÈME fois que le même défaut se reproduit à un endroit nouveau.
# Signalé par Abd Moutalib le 09/09 : « le curseur ne bouge pas quand je change
# les pourcentages ».
#
# Les quatre endroits qui DESSINENT la répartition lisaient `r.poids` — les
# poids retenus par le moteur pour ce titre. Choisir 60/40 changeait donc la
# note sans changer la barre : l'écran montrait une note calculée avec une
# répartition, à côté d'une répartition qui n'était pas celle-là.
#
# La note du 08/09 disait déjà « un réglage qui traverse l'interface doit être
# vérifié À CHAQUE ENDROIT où il s'applique ». Je l'avais écrite, puis vérifié
# la note et oublié la barre. Ces tests couvrent maintenant les quatre.

def test_l_helper_de_poids_existe():
    m = re.search(r"function poidsAffiches\(r, p\) \{(.*?)\n\}", _src(), re.S)
    assert m, "poidsAffiches introuvable"
    assert "if (!p || p.officiel) return r.poids" in m.group(1), (
        "en mode officiel la barre doit rendre les poids DU MOTEUR : le "
        "WeightEngine les module par titre (ATW est à 52/28/20, pas 47/28/25), "
        "et les remplacer par 47/28/25 afficherait un chiffre que le moteur "
        "n'a pas utilisé")


def test_plus_aucun_affichage_ne_lit_r_poids_directement():
    """Le contrôle qui compte : `r.poids` ne doit plus apparaître que DANS
    l'helper. Partout ailleurs, il fige la barre."""
    s = _src()
    # Le corps de l'helper est le seul endroit légitime : c'est lui qui rend
    # `r.poids` en mode officiel. On le retire du texte avant de chercher.
    helper = re.search(r"function poidsAffiches\(r, p\) \{.*?\n\}", s, re.S)
    assert helper, "poidsAffiches introuvable"
    s = s.replace(helper.group(0), "")
    dehors = [l for l in s.splitlines()
              if "r.poids" in l and not l.strip().startswith("//")]
    assert not dehors, (
        "ces lignes lisent encore r.poids et ne suivront pas la pondération :\n"
        + "\n".join("  " + l.strip()[:110] for l in dehors))


def test_les_quatre_affichages_utilisent_les_poids_de_la_vue():
    s = _src()
    assert "poidsAffiches(r,scoreMode)" in s, "le classement n'appelle pas l'helper"
    assert "const pdsAff=poidsAffiches(r,scoreMode);" in s, "la fiche n'appelle pas l'helper"
    for attendu, ou in ((("<WBar f={pw.f} n={pw.n} t={pw.t}/>"), "barre du classement"),
                        (("F{pw.f}·N{pw.n}·T{pw.t}"), "libellé du classement"),
                        (("<WBar f={pdsAff.f} n={pdsAff.n} t={pdsAff.t}/>"), "barre de la fiche"),
                        (("fond×{pdsAff.f}%"), "formule de la fiche")):
        assert attendu in s, f"{ou} : ne suit pas la pondération choisie"


def test_la_formule_simulee_n_annonce_pas_de_bonus():
    """computeDisplayScore est une moyenne pondérée PURE — ni bonus ni malus.
    Écrire « + bonus/malus » en simulation rendrait la formule affichée
    incapable de redonner le chiffre affiché juste à côté d'elle."""
    assert 'simu?" =":" + bonus/malus ="' in _src(), (
        "la fiche annonce un bonus que la note simulée n'applique pas")


def test_la_formule_conclut_sur_la_note_affichee():
    """Elle se terminait sur `r.v53` en dur : la ligne « fond×60% + tech×40% »
    aboutissait donc à la note OFFICIELLE."""
    s = _src()
    assert "fond×{pdsAff.f}%" in s
    i = s.index("fond×{pdsAff.f}%")
    fin = s[i:i+900]
    assert "{fmt(scoreAffiche)}" in fin, (
        "la formule de la fiche ne conclut pas sur la note qu'elle décrit")
    assert "(r.v53||0).toFixed(2)" not in fin, (
        "la formule conclut encore sur le v5.3 du moteur")
