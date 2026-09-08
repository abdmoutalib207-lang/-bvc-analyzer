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
