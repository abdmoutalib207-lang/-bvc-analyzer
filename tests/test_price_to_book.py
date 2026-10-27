"""Le price-to-book, calculé depuis des faits sourcés ou pas affiché du tout.

CE QUE L'AUDIT EXTERNE A MONTRÉ (09/09/2026)
────────────────────────────────────────────
Le champ `pb` venait de `FOND_DATA`, une table codée en dur, et portait
`pb_fige: true` sur 80 titres sur 80. L'étiquette ne suffisait pas :

    Alliances (ADI)   fiche : 0,80      comptes 2025 : 2,32
    CMT               fiche : 2,00      comptes 2025 : 8,12

Sur Alliances, **le sens de l'information s'inversait** — la fiche suggérait
une société valorisée sous ses fonds propres quand elle se paie plus de deux
fois ceux-ci. « Une constante signalée comme figée reste une constante ;
l'étiquette ne corrige pas le chiffre. »

LE CHOIX RETENU
───────────────
Calculer là où les deux termes sont sourcés et datés — capitaux propres part
du groupe et nombre d'actions, chacun avec sa page — et n'afficher RIEN
ailleurs. Publier un nombre faux accompagné d'un avertissement est pire que ne
rien publier : le lecteur retient le nombre, pas l'avertissement.

⚠️ `pb` n'entre PAS dans le score v5.3 : vérifié avant la bascule. Nullifier
76 valeurs ne déplace aucune note, ce qui rend le changement sûr au regard
de R8.
"""

import json
import re
from pathlib import Path

import pytest

from conftest import chemin_data_json  # noqa: E402
import _echelle  # noqa: E402  (contrôles relatifs)

RACINE = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="module")
def faits():
    return json.loads((RACINE / "pipeline" / "faits_financiers.json")
                      .read_text(encoding="utf-8"))


def _moteur():
    return (RACINE / "update_data.py").read_text(encoding="utf-8")


def test_le_moteur_lit_enfin_les_faits_sources():
    """L'audit relevait que faits_financiers.json n'était « pas lu directement
    par update_data.py ». Un référentiel qu'aucun programme ne consulte n'est
    pas un référentiel, c'est une archive."""
    s = _moteur()
    assert "faits_financiers.json" in s, "le moteur ignore encore le référentiel"
    assert "FAITS_DATA" in s


def test_le_pb_ne_vient_plus_de_la_table_figee():
    s = _moteur()
    assert '"pb":     _pb_sourcé(ticker, price)' in s, (
        "le price-to-book publié vient encore de FOND_DATA")
    assert '"pb":     fd.get("pb")' not in s


def test_pb_fige_a_disparu_au_profit_d_une_provenance():
    """`pb_fige: true` disait « c'est une constante » sans dire laquelle ni
    d'où. `pb_source` dit si la valeur est calculée ou absente."""
    s = _moteur()
    assert '"pb_fige":      True' not in s
    assert '"pb_source":' in s


def test_le_calcul_est_celui_annonce():
    """PB = cours × nombre d'actions ÷ capitaux propres PART DU GROUPE.

    Les capitaux propres consolidés, minoritaires inclus, sous-estimeraient le
    ratio : le nombre d'actions est celui de la société mère."""
    # ⚠️ 22/10/2026 (lot B3-B4) : le calcul vit dans `_pb_detail`, les fonds
    # propres dans `_fonds_propres_pb` (les plus récents relevés sur pièce).
    m = re.search(r"def _pb_sourcé\(ticker: str, price: float\):(.*?)\n\ndef ",
                  _moteur(), re.S)
    assert m, "_pb_sourcé introuvable"
    assert "_pb_detail(ticker, price)" in m.group(1)
    fp = re.search(r"def _fonds_propres_pb.*?\n\ndef ", _moteur(), re.S).group(0)
    assert '.get("capitaux_propres_part_groupe")' in fp
    corps = re.search(r"def _pb_detail.*?\n\ndef ", _moteur(), re.S).group(0)
    assert 'round(price * n / (fp["valeur"] * 1e6), 2)' in corps, (
        "les faits sont en MMAD : sans conversion le ratio est un million de "
        "fois trop grand")


def test_un_split_posterieur_a_la_cloture_est_applique(faits):
    """Le rapport arrête ses comptes au 31/12 : un split postérieur n'y figure
    pas. Managem (10:1 le 27/07/2026) et Sothema (5:1 le 05/05/2026) sont tous
    deux dans ce cas pour l'exercice 2025."""
    # ⚠️ LE CALCUL A DÉMÉNAGÉ, PAS LA RÈGLE. Le nombre d'actions ajusté des
    # splits est sorti de `_pb_sourcé` le 16/09 pour devenir
    # `_actions_sourcees()`, parce que le contrôle de la capitalisation en a
    # besoin lui aussi — et qu'une règle écrite deux fois finit par diverger.
    # Ce test suit la règle là où elle vit, et exige en outre que le
    # price-to-book la partage au lieu de la recopier.
    corps = re.search(r"def _actions_sourcees.*?\n\n# ", _moteur(), re.S).group(0)
    assert 'cloture = f"{e.get(\'exercice\', 2025)}-12-31"' in corps
    assert 'if sp["date"] > cloture:' in corps
    assert "n *= sp[\"ratio\"]" in corps
    # Et le registre fait foi, il n'est pas redéclaré ici.
    assert "SPLITS.get(ticker" in corps

    # 22/10/2026 (B3) : le P/B lit le nombre de la capitalisation
    # (`_actions_pb` : officiel, sinon `_actions_sourcees`).
    pb = re.search(r"def _actions_pb.*?\n\ndef ", _moteur(), re.S).group(0)
    assert "_actions_sourcees(ticker)" in pb, (
        "le price-to-book a recopié le calcul au lieu de le partager — deux "
        "copies d'une même règle finissent par ne plus dire la même chose")


def _emetteurs_avec_fonds_propres(faits):
    return sorted(t for t, e in faits.items()
                  if not t.startswith("_") and isinstance(e, dict)
                  and (e.get("faits") or {}).get("capitaux_propres_part_groupe"))


def test_les_deux_termes_sont_sources_avec_leur_page(faits):
    """Tout émetteur portant des fonds propres porte aussi ses deux pages.

    ⚠️ Ce test énumérait quatre tickers en dur — ADI, CMT, MNG, MSA, les seuls
    qui portaient le fait le 09/09. Il décrivait donc l'ÉTAT du référentiel et
    non sa RÈGLE : en y ajoutant un cinquième émetteur, il serait resté vert
    sans rien vérifier de neuf. Un test qui fige un instantané cesse de mordre
    dès que le travail avance — on s'y est repris trois fois dans ce projet
    (T2S, SOT.h52w, les comptes d'ARBITRAGES).

    La règle, elle, ne vieillit pas : un fait sans page est un chiffre de
    seconde main, et le P/BOOK qui en découlerait serait invérifiable.
    """
    avec = _emetteurs_avec_fonds_propres(faits)
    assert len(avec) >= 4, (
        f"seuls {len(avec)} émetteurs portent des fonds propres — régression ?")
    for ticker in avec:
        f = faits[ticker]["faits"]
        cp = f["capitaux_propres_part_groupe"]
        na = _nombre_d_actions_releve(f)
        assert isinstance(cp.get("page"), int), (
            f"{ticker} : capitaux propres sans page — le PB serait invérifiable")
        assert na and isinstance(na.get("page"), int), (
            f"{ticker} : fonds propres relevés mais pas le nombre d'actions — "
            "le P/BOOK reste incalculable, et l'à-peu-près n'est pas une option")


def _nombre_d_actions_releve(f):
    """Le nombre d'actions d'un émetteur : lu au dépôt, ou DÉCLARÉ de l'opérateur.

    ⚠️ 10/10/2026, accord d'Abd Moutalib (CAR, PPM). Quand le dépôt AMMC
    n'imprime ni nombre de titres ni nominal, le nombre du référentiel de
    l'opérateur (capitalisation ÷ cours) est accepté — à une condition
    ÉTROITE : la clé `nombre_actions_referentiel` doit porter, dans l'entrée
    elle-même, `origine: "operateur"` ET le motif « non publié au dépôt ».
    Jamais par défaut : une entrée qui ne le déclare pas, et qui n'a pas de
    nombre lu au dépôt, reste en échec.
    """
    lu = (f.get("nombre_actions_existant")
          or f.get("nombre_actions_au_rapport")
          or f.get("nombre_actions_retenu_pour_le_bpa"))
    if lu:
        return lu
    ref = f.get("nombre_actions_referentiel")
    if (isinstance(ref, dict) and ref.get("origine") == "operateur"
            and ref.get("motif") == "non publié au dépôt"
            and isinstance(ref.get("valeur"), (int, float)) and ref["valeur"] > 0):
        return ref
    return None


def test_un_nombre_d_actions_de_l_operateur_n_est_accepte_que_declare():
    """Contrôle négatif : sans nombre lu NI déclaration explicite, l'entrée échoue."""
    base = {"valeur": 1000, "page": 3}
    assert _nombre_d_actions_releve({"nombre_actions_referentiel": dict(base)}) is None
    assert _nombre_d_actions_releve({"nombre_actions_referentiel": dict(
        base, origine="operateur")}) is None          # motif manquant
    assert _nombre_d_actions_releve({"nombre_actions_referentiel": dict(
        base, motif="non publié au dépôt")}) is None  # origine manquante
    assert _nombre_d_actions_releve({}) is None
    assert _nombre_d_actions_releve({"nombre_actions_referentiel": dict(
        base, origine="operateur", motif="non publié au dépôt")}) is not None
    # un nombre lu au dépôt reste prioritaire et suffit
    assert _nombre_d_actions_releve({"nombre_actions_au_rapport": base}) is base


def test_les_nombres_d_actions_de_l_operateur_declares_sont_les_seuls(faits):
    """Tout `nombre_actions_referentiel` qui tient lieu de dénominateur du P/B
    est déclaré ; ceux d'un titre sans fonds propres (STR) restent hors champ."""
    for t in _emetteurs_avec_fonds_propres(faits):
        f = faits[t]["faits"]
        if "nombre_actions_referentiel" in f and not (
                f.get("nombre_actions_au_rapport") or f.get("nombre_actions_existant")
                or f.get("nombre_actions_retenu_pour_le_bpa")):
            assert _nombre_d_actions_releve(f), (
                f"{t} : nombre de l'opérateur non déclaré (origine + motif)")


def test_tout_pb_publie_remonte_a_un_fait_source(faits):
    """Aucun P/BOOK à l'écran qui ne se retrouve dans un rapport déposé.

    C'est l'inverse du test précédent, et c'est celui qui compte pour le
    lecteur : le premier dit que nos faits sont vérifiables, celui-ci dit
    qu'aucun chiffre publié ne vient d'ailleurs. Réintroduire une constante
    dans FOND_DATA le ferait tomber.
    """
    d = json.loads(chemin_data_json().read_text(encoding="utf-8"))
    avec = set(_emetteurs_avec_fonds_propres(faits))
    orphelins = sorted(t["symbol"] for t in d["tickers"]
                       if t.get("pb") is not None and t["symbol"] not in avec)
    assert not orphelins, f"P/BOOK publié sans fait sourcé : {orphelins}"


def test_le_pb_publie_reste_dans_une_plage_defendable():
    """Un price-to-book négatif n'a pas de sens ici. Un titre à un facteur 20
    de la médiane de la place est un titre À VÉRIFIER, rejeté seulement si un
    second indice concorde (facteur proche d'une puissance de 1 000 : erreur
    d'unité) ; sinon avertissement — des fonds propres minces donnent
    légitimement un P/B de 30. Le recoupement avec capitalisation ÷ fonds
    propres est dans `test_le_pb_publie_se_recoupe_avec_la_capitalisation`.

    ⚠️ 11/10/2026 : l'ancien `0 < pb < 50` était un seuil absolu — un vrai P/B
    de 55 sur une société à fonds propres minces aurait bloqué la publication.
    La bande est désormais RELATIVE à la place (voir `ratios_hors_echelle`) :
    elle ne dépend pas du niveau du marché, seulement de l'isolement d'un
    titre. Preuves négative (×1 000) et positive (marché −30 %) dans
    `tests/test_controles_echelle.py`.
    """
    d = json.loads(chemin_data_json().read_text(encoding="utf-8"))
    fautifs = _echelle.ratios_hors_echelle({t["symbol"]: t.get("pb") for t in d["tickers"]})
    assert not fautifs, (
        f"price-to-book hors de toute plage défendable : {fautifs} — "
        "vérifier l'unité des capitaux propres (MMAD ?)")


def _pb_publies():
    d = json.loads(chemin_data_json().read_text(encoding="utf-8"))
    return {t["symbol"]: t.get("pb") for t in d["tickers"]}


def test_controle_negatif_une_erreur_d_unite_est_toujours_attrapee():
    """Le défaut que la plage protégeait : un P/B 1 000 fois trop haut (MMAD
    lus comme des dirhams) ou trop bas, ou négatif, sur UN titre."""
    pb = {t: v for t, v in _pb_publies().items() if v is not None}
    t = next(iter(pb))
    for faux in (pb[t] * 1000, pb[t] / 1000, -1.0, 0.0):
        copie = dict(pb)
        copie[t] = faux
        assert any(x.startswith(t) for x in _echelle.ratios_hors_echelle(copie)), faux


def test_controle_positif_un_pb_de_30_sur_fonds_propres_faibles_passe():
    """Médiane 1, un titre à 30 (hors bande ×20, facteur 30 : pas une erreur
    d'unité) : avertissement, pas d'échec. Un P/B normal ×1 000 échoue, et le
    même 30 contredit par un témoin indépendant aussi."""
    place = {f"T{i}": 1.0 + 0.05 * i for i in range(10)}
    place["FAIBLE"] = 30.0
    with pytest.warns(UserWarning, match="à vérifier"):
        assert _echelle.ratios_hors_echelle(place) == []
    rejets, a_verifier = _echelle.classer_ratios(place)
    assert rejets == [] and len(a_verifier) == 1
    assert _echelle.ratios_hors_echelle({**place, "FAIBLE": 1.2 * 1000})
    assert _echelle.ratios_hors_echelle({**place, "FAIBLE": 1.2 / 1000})
    assert _echelle.ratios_hors_echelle(place, temoins={"FAIBLE": 3.0})
    assert _echelle.ratios_hors_echelle(place, temoins={"FAIBLE": 30.5}) == []


def test_controle_positif_une_chute_reelle_de_30_pour_cent_passe():
    """−30 % sur un titre, −30 % ou −60 % sur toute la place, +100 % sur la
    place : la bande suit le marché, rien ne rougit. L'ancien `pb < 50` aurait
    rougi dès qu'un titre dépassait 50, et `pb > 0` n'a jamais gêné."""
    pb = {t: v for t, v in _pb_publies().items() if v is not None}
    assert _echelle.ratios_hors_echelle(pb) == [], "base déjà hors bande"
    for coef in (0.7, 0.4, 2.0):
        assert _echelle.ratios_hors_echelle({t: v * coef for t, v in pb.items()}) == [], coef
    t = next(iter(pb))
    seul = dict(pb)
    seul[t] *= 0.7
    assert _echelle.ratios_hors_echelle(seul) == []


def test_le_frontend_supporte_un_pb_absent():
    """Nullifier 76 valeurs ne doit pas produire « null » à l'écran."""
    s = (RACINE / "terminal.src.html").read_text(encoding="utf-8")
    assert 'r.pb?.toFixed(2)||"—"' in s, (
        "la fiche n'a pas de repli pour un price-to-book absent")
