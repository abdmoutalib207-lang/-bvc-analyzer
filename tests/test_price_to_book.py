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
    m = re.search(r"def _pb_sourcé\(ticker: str, price: float\):(.*?)\n\ndef ",
                  _moteur(), re.S)
    assert m, "_pb_sourcé introuvable"
    corps = m.group(1)
    assert 'faits.get("capitaux_propres_part_groupe")' in corps
    assert "return round(price * n / fp, 2)" in corps
    assert 'float(cp["valeur"]) * 1e6' in corps, (
        "les faits sont en MMAD : sans conversion le ratio est un million de "
        "fois trop grand")


def test_un_split_posterieur_a_la_cloture_est_applique(faits):
    """Le rapport arrête ses comptes au 31/12 : un split postérieur n'y figure
    pas. Managem (10:1 le 27/07/2026) et Sothema (5:1 le 05/05/2026) sont tous
    deux dans ce cas pour l'exercice 2025."""
    corps = re.search(r"def _pb_sourcé.*?\n\ndef ", _moteur(), re.S).group(0)
    assert 'cloture = f"{e.get(\'exercice\', 2025)}-12-31"' in corps
    assert 'if sp["date"] > cloture:' in corps
    assert "n *= sp[\"ratio\"]" in corps
    # Et le registre fait foi, il n'est pas redéclaré ici.
    assert "SPLITS.get(ticker" in corps


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
        na = (f.get("nombre_actions_existant")
              or f.get("nombre_actions_au_rapport")
              or f.get("nombre_actions_retenu_pour_le_bpa"))
        assert isinstance(cp.get("page"), int), (
            f"{ticker} : capitaux propres sans page — le PB serait invérifiable")
        assert na and isinstance(na.get("page"), int), (
            f"{ticker} : fonds propres relevés mais pas le nombre d'actions — "
            "le P/BOOK reste incalculable, et l'à-peu-près n'est pas une option")


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
    """Un price-to-book négatif n'a pas de sens ici, et au-delà de 50 il
    signale une erreur d'unité plutôt qu'une valorisation."""
    d = json.loads(chemin_data_json().read_text(encoding="utf-8"))
    for t in d["tickers"]:
        pb = t.get("pb")
        if pb is None:
            continue
        assert 0 < pb < 50, (
            f"{t['symbol']} : price-to-book de {pb} — hors de toute plage "
            "défendable, vérifier l'unité des capitaux propres (MMAD ?)")


def test_le_frontend_supporte_un_pb_absent():
    """Nullifier 76 valeurs ne doit pas produire « null » à l'écran."""
    s = (RACINE / "index.html").read_text(encoding="utf-8")
    assert 'r.pb?.toFixed(2)||"—"' in s, (
        "la fiche n'a pas de repli pour un price-to-book absent")
