"""Les fonds propres relevés au rapport — l'unité, la colonne, et la page.

CE QUE NOURE A SIGNALÉ LE 16/09/2026
───────────────────────────────────
« Il y'a plein de P/BOOK qui manque. » Mesuré sur le `data.json` servi à
00h42 : **4 titres sur 80** en portaient un — ADI, CMT, MNG, MSA.

Ce n'était pas un défaut de calcul. `_pb_sourcé()` exige le fait
`capitaux_propres_part_groupe`, et sur les onze émetteurs archivés quatre
seulement le portaient — exactement ces quatre-là. Les sept autres avaient été
relevés pour le BPA : résultat net et nombre d'actions. La ligne des fonds
propres n'avait jamais été lue. Un relevé à compléter, pas un bug à corriger.

LES DEUX PIÈGES DE CE RELEVÉ, ET POURQUOI ILS SONT TESTÉS
─────────────────────────────────────────────────────────
**1. L'unité.** Les rapports publient indifféremment en dirhams, en milliers ou
en millions, et rien dans la ligne elle-même ne le dit. Addoha écrit
9 481 694 524, Cosumar écrit 5 633,8 : le premier est en MAD, le second en
millions, et les deux désignent des fonds propres du même ordre. Se tromper
d'unité déplace le P/BOOK d'un facteur mille **sans rien casser** — le nombre
reste un nombre, la fiche reste lisible, et personne ne le voit.

**2. L'ordre des colonnes.** Il n'est pas constant, y compris à l'intérieur
d'un même rapport. Deux émetteurs sur dix-sept mettent l'exercice clos en
SECOND — Mutandis (« en KMAD Actif 31/12/2024 31/12/2025 ») et Risma (« EN
KMAD 31/12/2024 31/12/2025 »). Prendre le premier nombre y aurait publié les
comptes 2024 en les présentant comme ceux de 2025.

D'où les deux champs que ces tests exigent : `valeur_au_rapport`, le nombre TEL
QU'IL EST IMPRIMÉ, et `unite_au_rapport`. Ensemble ils rendent la conversion
REFAISABLE sans rouvrir le PDF. Sans eux, `valeur` est un chiffre converti que
personne ne peut recontrôler — et l'on aurait seulement déplacé le problème
qu'on reprochait à `fondamentaux.json`.

⚠️ CES TESTS NE VÉRIFIENT PAS QUE LE CHIFFRE EST LE BON. Aucun test ne peut
lire un PDF à notre place. Ils vérifient que tout ce qu'il faut pour le
recontrôler EST LÀ, et que ce qui est publié découle bien de ce qui est relevé.
La lecture, elle, se refait à la page indiquée.
"""

import json
import re
from pathlib import Path

import pytest

from conftest import chemin_data_json  # noqa: E402

RACINE = Path(__file__).resolve().parent.parent

# Ce par quoi multiplier le nombre imprimé pour obtenir des MMAD, la convention
# du fichier. Cette table est l'ATTENDU du test : elle est écrite ici, à la
# main, et non lue depuis le code qu'elle contrôle.
VERS_MMAD = {"MAD": 1e-6, "KMAD": 1e-3, "MMAD": 1.0}


@pytest.fixture(scope="module")
def faits():
    return json.loads((RACINE / "pipeline" / "faits_financiers.json")
                      .read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def publie():
    return json.loads(chemin_data_json().read_text(encoding="utf-8"))


def _avec_fonds_propres(faits):
    return {t: e["faits"]["capitaux_propres_part_groupe"]
            for t, e in faits.items()
            if not t.startswith("_") and isinstance(e, dict)
            and (e.get("faits") or {}).get("capitaux_propres_part_groupe")}


def test_la_conversion_se_refait_sans_rouvrir_le_pdf(faits):
    """`valeur` = `valeur_au_rapport` × le facteur de l'unité déclarée.

    C'est le test qui attrape une erreur d'unité — la seule des deux qui soit
    vérifiable par le calcul. Changer `unite_au_rapport` sans changer `valeur`,
    ou l'inverse, le fait tomber.
    """
    cp = _avec_fonds_propres(faits)
    assert cp, "aucun émetteur ne porte de fonds propres"
    for t, f in sorted(cp.items()):
        assert "valeur_au_rapport" in f, (
            f"{t} : le nombre imprimé au rapport n'est pas conservé — la "
            "conversion en MMAD est alors invérifiable")
        u = f.get("unite_au_rapport")
        assert u in VERS_MMAD, f"{t} : unité {u!r} inconnue"
        attendu = f["valeur_au_rapport"] * VERS_MMAD[u]
        assert abs(f["valeur"] - attendu) <= max(1e-6, abs(attendu) * 1e-9), (
            f"{t} : {f['valeur']} MMAD publié, mais {f['valeur_au_rapport']} "
            f"{u} font {attendu} MMAD")


def test_la_colonne_retenue_est_declaree(faits):
    """Chaque fait dit à QUEL RANG, dans la ligne citée, se trouve le montant.

    Dans un bilan, ce rang désigne l'exercice : deux rapports le mettent en
    second. Ce champ n'est pas une précaution de style — c'est la trace de la
    seule chose qui distingue les comptes 2025 de ceux de 2024 quand les deux
    sont sur la même ligne.

    ⚠️ La borne est à dix, pas à quatre. Un TABLEAU DE VARIATION DES CAPITAUX
    PROPRES ne range pas ses colonnes par exercice mais par composante —
    capital, primes, réserves, écarts, part du groupe, minoritaires, total — et
    la ligne de clôture en porte huit chez CFG Bank, la part du groupe venant
    en sixième position. Le rang garde le même rôle : il dit lequel des
    montants de la ligne a été retenu, et c'est ce que vérifie le contrôle
    suivant.
    """
    cp = _avec_fonds_propres(faits)
    for t, f in sorted(cp.items()):
        col = f.get("colonne_exercice_clos")
        assert isinstance(col, int) and 1 <= col <= 10, (
            f"{t} : rang {col!r} — sans lui, rien ne dit lequel des montants "
            "de la ligne a été retenu")


_NOMBRE_CITE = re.compile(
    r"\d{1,3}(?:[  .]\d{3})+(?:,\d+)?"     # 9.481.694.524 · 5 444 531
    r"|\d+,\d+"                                  # 5 633,8
    r"|\b\d{4,}\b")                              # 12568130


def _degrouper_citation(jeton):
    """Sépare deux colonnes recollées : « 700 159 645 289 » → deux montants.

    ⚠️ LE RECOLLAGE EST INHÉRENT AU TEXTE DES PDF. Dans un tableau, deux
    montants voisins ne sont séparés que par une espace — la même que celle qui
    sépare les milliers à l'intérieur d'un montant. Rien, dans la chaîne, ne dit
    où l'un finit et où l'autre commence.

    Ce qui tranche est la SYMÉTRIE : deux colonnes voisines d'un même tableau
    portent des montants du même ordre, donc le même nombre de groupes de trois
    chiffres. Un recollage a donc un nombre PAIR de groupes, et se coupe au
    milieu. Vérifié sur les six cas du référentiel — CFG Bank, CTM, Oulmès,
    Immorente, SNEP, Minière Touissit : tous se coupent en deux parts égales.

    Un nombre IMPAIR de groupes ne se découpe pas ainsi : on rend None plutôt
    que de choisir. Une lecture ambiguë se dit, elle ne se devine pas.
    """
    if len(re.sub(r"\D", "", jeton)) <= 11:
        return [jeton]
    groupes = re.split(r"[\s\u00a0.]", jeton)
    if len(groupes) < 2 or len(groupes) % 2:
        return None
    m = len(groupes) // 2
    return [" ".join(groupes[:m]), " ".join(groupes[m:])]


def _nombres_cites(note):
    """Les montants de la ligne citée, après l'étiquette, recollages défaits.

    Rend None quand la citation ne s'analyse pas — aucun montant, ou un
    recollage à nombre impair de groupes. La borne des onze chiffres est
    physique : les fonds propres d'Attijariwafa, la plus grosse de la cote,
    avoisinent 6 × 10¹⁰ dirhams. Douze chiffres ne sont plus un montant.
    """
    cite = re.search(r"«([^»]*)»", note or "")
    if not cite:
        return None
    m = re.search(r"capitaux\s+propres[^\d]{0,60}", cite.group(1), re.I)
    jetons = []
    for x in _NOMBRE_CITE.findall(cite.group(1)[m.end():] if m else cite.group(1)):
        part = _degrouper_citation(x)
        if part is None:
            return None
        jetons += part
    if not jetons:
        return None
    valeurs = []
    for x in jetons:
        brut = re.sub(r"[\s\u00a0]", "", x)
        v = (float(brut.replace(".", "").replace(",", ".")) if "," in brut
             else float(brut.replace(".", "")))
        # ⚠️ UN MONTANT ENTRE PARENTHÈSES EST NÉGATIF. Convention comptable
        # constante, et pas un détail de présentation : les fonds propres part
        # du groupe de Stokvis valent « ( 97.214) », c'est-à-dire moins 97
        # millions de dirhams — ses réserves consolidées, -299 928 KMAD,
        # excèdent son capital. Lus positifs, ils produiraient un price-to-book
        # là où la réponse juste est qu'il n'y en a pas : une société dont le
        # livre est négatif ne se compare pas à son livre.
        #
        # La parenthèse se cherche dans la CITATION ENTIÈRE, pas dans ce qui
        # suit l'étiquette : le motif d'étiquette, glouton jusqu'au premier
        # chiffre, avale la parenthèse ouvrante de « part du groupe ( 97.214) ».
        if re.search(r"\(\s*" + re.escape(x) + r"\s*\)", cite.group(1)):
            v = -v
        valeurs.append(v)
    return valeurs


def test_la_valeur_retenue_est_bien_celle_de_la_colonne_declaree(faits):
    """Le nombre publié est celui qui occupe, dans la ligne citée, le rang
    déclaré.

    C'est le seul contrôle qui attrape une INVERSION DE COLONNE sans rouvrir le
    PDF. Déclarer « colonne 2 » puis retenir le premier nombre — ou l'inverse —
    publie les comptes de l'exercice précédent sous la date du dernier. Les
    deux chiffres étant du même ordre, rien d'autre ne le signale : ni les
    bornes, ni le recoupement avec la capitalisation, qui ne regardent que la
    grandeur.

    ⚠️ IL NE S'APPLIQUE PAS PARTOUT, et c'est assumé — mais l'exception s'est
    réduite à UN cas sur trente : Marsa Maroc, dont la part du groupe n'a pas de
    colonne propre et se déduit du total moins les minoritaires. Les citations
    où le PDF recollait deux colonnes s'analysent désormais, la symétrie des
    groupes de trois chiffres suffisant à les séparer. Le plancher ci-dessous
    empêche l'exception de s'étendre en silence jusqu'à ce que le test ne
    contrôle plus rien.
    """
    applique = 0
    for t, f in sorted(_avec_fonds_propres(faits).items()):
        nombres = _nombres_cites(f.get("note"))
        col = f["colonne_exercice_clos"]
        if nombres is None or len(nombres) < col:
            continue
        applique += 1
        assert nombres[col - 1] == pytest.approx(f["valeur_au_rapport"], rel=1e-9), (
            f"{t} : la colonne {col} de la ligne citée porte {nombres[col - 1]}, "
            f"mais le fait retient {f['valeur_au_rapport']}")
    assert applique >= 25, (
        f"le contrôle ne s'est appliqué qu'à {applique} émetteurs : les "
        "citations sont devenues trop irrégulières pour qu'il morde encore")


def test_les_colonnes_inversees_sont_signalees_dans_la_note(faits):
    """Un ordre de colonnes inhabituel s'explique, il ne se subit pas.

    ⚠️ Ce test ne fige PAS la liste des émetteurs concernés — elle changera au
    prochain relevé. Il exprime la règle : tout fait pris ailleurs qu'en
    première colonne porte, dans sa note, de quoi comprendre pourquoi.
    """
    cp = _avec_fonds_propres(faits)
    inverses = {t: f for t, f in cp.items() if f["colonne_exercice_clos"] != 1}
    for t, f in sorted(inverses.items()):
        note = f.get("note") or ""
        assert "⚠" in note and re.search(r"colonne|gauche|second", note, re.I), (
            f"{t} : l'exercice clos est pris en colonne "
            f"{f['colonne_exercice_clos']} sans que la note dise pourquoi")


def test_chaque_fait_cite_la_ligne_du_rapport(faits):
    """La note reproduit la ligne lue, entre guillemets.

    « AUCUNE valeur n'entre ici sans sa page » est la règle du fichier. Une
    page seule ne suffit pourtant pas : elle dit où chercher, pas ce qui a été
    lu. La citation permet de retrouver la ligne parmi les quinze qui parlent
    de capitaux propres sur la même page — chez Addoha, trois se suivent et ne
    diffèrent que par leur qualificatif.
    """
    cp = _avec_fonds_propres(faits)
    for t, f in sorted(cp.items()):
        note = f.get("note") or ""
        assert "«" in note and "»" in note, (
            f"{t} : la note ne cite pas la ligne du rapport")
        assert re.search(r"capitaux\s+propres", note, re.I), (
            f"{t} : la citation ne porte pas sur une ligne de capitaux propres")


def test_aucun_fait_ne_confond_la_part_du_groupe_avec_l_ensemble(faits):
    """Les fonds propres retenus sont ceux de la PART DU GROUPE.

    Les consolidés, minoritaires inclus, sont plus grands — les prendre
    SOUS-ESTIMERAIT le P/BOOK, c'est-à-dire ferait paraître le titre moins cher
    qu'il n'est. C'est le sens d'erreur le plus coûteux pour un lecteur, et
    c'est celui qu'on avait déjà corrigé sur le BPA d'Addoha.
    """
    interdits = re.compile(r"d[e']\s*ensemble|des minoritaires", re.I)
    cp = _avec_fonds_propres(faits)
    for t, f in sorted(cp.items()):
        cite = re.search(r"«([^»]*)»", f.get("note") or "")
        assert cite, f"{t} : pas de citation à contrôler"
        assert not interdits.search(cite.group(1)), (
            f"{t} : la ligne citée est celle de l'ensemble consolidé ou des "
            f"minoritaires — {cite.group(1)[:70]!r}")


def test_le_pb_publie_se_recoupe_avec_la_capitalisation(publie, faits):
    """Contrôle par une grandeur que le calcul n'utilise PAS.

    Le moteur calcule `cours × actions_du_rapport ÷ fonds_propres`. La
    capitalisation vient d'IDBourse et n'entre nulle part dans ce calcul :
    `capitalisation ÷ fonds_propres` est donc un second chemin vers le même
    ratio, qui passe par le nombre d'actions RÉEL du marché au lieu de celui
    du rapport.

    Les deux ne peuvent diverger que si le nombre d'actions a bougé depuis la
    clôture des comptes. Au-delà de 10 %, ce n'est plus une opération sur
    titres : c'est une erreur de relevé.

    ⚠️ Ce contrôle ne dit RIEN de l'unité des fonds propres — les deux chemins
    la partagent. C'est le test de conversion qui s'en charge.
    """
    cp = _avec_fonds_propres(faits)
    ecarts = []
    for x in publie["tickers"]:
        t, pb, cap = x["symbol"], x.get("pb"), x.get("cap")
        if pb is None or not cap or t not in cp:
            continue
        temoin = cap / cp[t]["valeur"]          # capitalisation et fonds propres, en MMAD
        if abs(temoin / pb - 1) > 0.10:
            ecarts.append(f"{t} : moteur {pb:.2f}, capitalisation ÷ fonds "
                          f"propres {temoin:.2f}")
    assert not ecarts, "P/BOOK non recoupé par la capitalisation :\n  " + \
        "\n  ".join(ecarts)


def test_le_nombre_d_actions_du_rapport_colle_au_marche(publie, faits):
    """Le dénominateur se recoupe avec une source qui n'est pas le rapport.

    Le rapport dit combien d'actions existaient au 31 décembre ; la
    capitalisation divisée par le cours dit combien il en existe aujourd'hui.
    Les deux ne peuvent diverger que par une opération sur titres — et le
    registre `SPLITS` porte celles qu'on connaît. Au-delà de 10 % une fois le
    split appliqué, ce n'est plus une opération : c'est une nominale mal
    devinée, et le P/BOOK est faux du même facteur.

    C'est le recoupement qui avait tranché l'ISIN de Maroc Leasing : deux
    sources peuvent se tromper ensemble, un calcul qui boucle non.

    ⚠️ Ce contrôle ne dit rien de l'unité des fonds propres — il ne les touche
    pas. C'est `test_la_conversion_se_refait_sans_rouvrir_le_pdf` qui s'en
    charge. Chacun son défaut ; un contrôle qui prétend tout voir ne voit rien.
    """
    import bvc_config

    cours = {x["symbol"]: (x.get("price"), x.get("cap"))
             for x in publie["tickers"]}
    ecarts = []
    for t, f in sorted(_avec_fonds_propres(faits).items()):
        faits_t = faits[t]["faits"]
        na = next((faits_t[k] for k in ("nombre_actions_existant",
                                        "nombre_actions_au_rapport",
                                        "nombre_actions_retenu_pour_le_bpa")
                   if k in faits_t), None)
        prix, cap = cours.get(t, (None, None))
        if not na or not prix or not cap:
            continue
        n = float(na["valeur"])
        cloture = f"{faits[t].get('exercice', 2025)}-12-31"
        for sp in bvc_config.SPLITS.get(t, []):
            if sp["date"] > cloture:
                n *= sp["ratio"]
        marche = cap * 1e6 / prix
        if abs(n / marche - 1) > 0.10:
            ecarts.append(f"{t} : {n:,.0f} au rapport contre {marche:,.0f} "
                          f"selon le marché".replace(",", " "))
    assert not ecarts, ("nombre d'actions non recoupé par le marché :\n  "
                        + "\n  ".join(ecarts))


def test_les_fonds_propres_ont_un_ordre_de_grandeur_defendable(publie, faits):
    """La capitalisation rapportée aux fonds propres reste dans une plage
    tenable.

    ⚠️ C'EST LE FILET CONTRE L'ERREUR D'UNITÉ QUI SE DÉCLARE ELLE-MÊME. Le test
    de conversion vérifie que `valeur` découle de `valeur_au_rapport` et de
    l'unité annoncée — mais si les DEUX sont faux ensemble, il passe. C'est
    exactement ce qui arrive quand deux colonnes recollées sont prises pour un
    montant : chez CTM, « 243 479 362 360 » lu comme un seul nombre donnerait
    243 479 MMAD de fonds propres pour une société qui en capitalise 1 065. Le
    ratio tomberait à 0,004, mille fois trop bas, sans qu'aucun autre contrôle
    ne bronche.

    La capitalisation vient d'IDBourse et n'entre dans aucun de ces faits :
    c'est une mesure extérieure. La plage est large à dessein — de 0,2 à 50 —
    parce qu'elle n'est pas là pour juger une valorisation, seulement pour
    attraper un facteur mille. Les trente valeurs relevées le 16/09 s'étagent
    de 1,04 à 17,8.

    Les fonds propres négatifs sont hors sujet : il n'y a pas de rapport à
    former, et le moteur s'en abstient déjà.
    """
    cap = {x["symbol"]: x.get("cap") for x in publie["tickers"]}
    aberrants = []
    for t, f in sorted(_avec_fonds_propres(faits).items()):
        fp, c = f["valeur"], cap.get(t)
        if not c or fp <= 0:
            continue
        r = c / fp
        if not (0.2 <= r <= 50):
            aberrants.append(f"{t} : capitalisation {c} MMAD ÷ fonds propres "
                             f"{fp} MMAD = {r:.4f}")
    assert not aberrants, ("ordre de grandeur indéfendable — erreur d'unité ou "
                           "colonnes recollées :\n  " + "\n  ".join(aberrants))


def test_le_releve_progresse_et_ne_recule_pas(faits):
    """Un plancher, pas un instantané.

    ⚠️ Écrire « 21 émetteurs » ferait un test qui tombe au prochain relevé —
    c'est-à-dire un test qui punit le travail qu'il est censé protéger. On s'y
    est repris trois fois dans ce projet avant de comprendre (T2S, SOT.h52w,
    les comptes d'ARBITRAGES), et une garde `len(exceptions) < 10` est un jour
    passée au rouge sur le treizième titre CORRIGÉ. Le plancher, lui, ne dit
    qu'une chose, et c'est la seule qui compte : on ne revient pas en arrière.

    ⚠️ Ce test compte dans le RÉFÉRENTIEL, pas dans `data.json`. Les deux ne
    disent pas la même chose : le fichier publié date du dernier run du moteur,
    et un relevé fait après lui n'y figure pas encore. Compter là aurait produit
    un rouge qui signifie « le moteur n'a pas encore tourné » — un rouge qu'on
    apprend à ignorer, donc un test mort.
    """
    cp = _avec_fonds_propres(faits)
    calculables = [t for t in cp
                   if any(k in faits[t]["faits"] for k in
                          ("nombre_actions_existant", "nombre_actions_au_rapport",
                           "nombre_actions_retenu_pour_le_bpa"))]
    assert len(calculables) >= 30, (
        f"{len(calculables)} émetteurs seulement ont de quoi calculer un "
        "P/BOOK — le relevé du 16/09 en avait porté 30 sur 80, dont 29 qui donnent un ratio (Stokvis a des fonds propres négatifs). Une baisse "
        "signale un fait perdu, pas un progrès.")

    # ⚠️ CE PLANCHER SE REMONTE À CHAQUE LOT, sinon il cesse de mordre : à 21
    # alors que le référentiel en portait 29, retirer un fait passait inaperçu.
    # Un cliquet qu'on oublie de remonter n'est plus un cliquet.
