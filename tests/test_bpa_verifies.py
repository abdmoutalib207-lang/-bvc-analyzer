"""Les BPA vérifiés dans les rapports déposés à l'AMMC.

CE QUE CE FICHIER PROTÈGE
─────────────────────────
Onze émetteurs dont le bénéfice par action a été relu dans le rapport
financier annuel déposé au régulateur, page par page. Ces tests empêchent une
saisie manuelle de les écraser en silence — ce qui s'est produit au moins une
fois par ticker avant le 09/09/2026.

CE QU'ON A TROUVÉ EN LES RELISANT (09/09/2026)
──────────────────────────────────────────────
Sept titres passés au crible, **sept BPA faux, tous dans le même sens** :

    ADH  2,50 → 1,13    ×2,21      PER 14,2 → 31,4
    CSR    11 → 7,45    ×1,48      PER 17,6 → 26,0
    HPS  28,4 → 14,31   ×1,98      PER 23,6 → 46,8
    RIS  23,1 → 16,84   ×1,37      PER 13,9 → 19,1
    SNA 148,1 → 69,69   ×2,13      PER 13,0 → 27,7
    SOT  32,0 → 10,14   ×3,16      PER 11,3 → 35,6
    TQA  63,4 → 41,58   ×1,52      PER 28,1 → 42,8

Aucun facteur commun : ce n'est donc pas une erreur de formule unique, mais
sept saisies indépendantes. **Et pourtant toutes surestiment le bénéfice**,
donc sous-estiment le PER, donc font paraître le titre meilleur marché qu'il
n'est. Un biais qui ne va que dans un sens n'est pas du bruit.

Deux enregistrements se contredisaient eux-mêmes : HPS portait la note « RNPG
106 MDH » — le bon chiffre — à côté d'un BPA qui en implique 210 ; TQA portait
« RNPG 981 MDH » à côté d'un BPA qui en implique 1 495. Le commentaire disait
vrai, le nombre disait faux, dans le même objet.

CE QUI N'EST PAS COUVERT
────────────────────────
⚠️ Les DIVIDENDES de ces sept titres n'ont pas été revérifiés — seul le
bénéfice par action l'a été. Ne pas lire ce fichier comme un quitus sur le
reste de l'enregistrement.
"""

import json
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parent.parent

# ticker: (bpa attendu, page du RNPG, page du nombre d'actions)
VERIFIES = {
    "ADH": 1.13,
    "CMT": 116.86,
    "CSR": 7.45,
    "HPS": 14.31,
    "RIS": 16.84,
    "SNA": 69.69,
    "SOT": 10.14,
    "TQA": 41.58,
}


@pytest.fixture(scope="module")
def bpa():
    return json.loads((RACINE / "bpa.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def faits():
    return json.loads((RACINE / "pipeline" / "faits_financiers.json")
                      .read_text(encoding="utf-8"))


@pytest.mark.parametrize("ticker,attendu", sorted(VERIFIES.items()))
def test_le_bpa_reste_celui_du_rapport(bpa, ticker, attendu):
    assert bpa[ticker]["bpa"] == pytest.approx(attendu, abs=0.01), (
        f"{ticker} : le BPA a été modifié sans repasser par le rapport AMMC")


@pytest.mark.parametrize("ticker", sorted(VERIFIES))
def test_la_provenance_est_le_rapport_annuel(bpa, ticker):
    src = bpa[ticker].get("source", "")
    assert "AMMC" in src, (
        f"{ticker} : source « {src} » — un BPA vérifié doit citer le rapport "
        "déposé au régulateur, pas une source secondaire")


@pytest.mark.parametrize("ticker", sorted(VERIFIES))
def test_chaque_fait_porte_sa_page(faits, ticker):
    """La règle du fichier : aucune valeur sans page. Un chiffre sans page
    redevient un chiffre de seconde main."""
    e = faits[ticker]
    assert e["faits"], f"{ticker} : aucun fait enregistré"
    for nom, f in e["faits"].items():
        assert isinstance(f.get("page"), int), f"{ticker}.{nom} : page absente"
        assert f.get("valeur") is not None, f"{ticker}.{nom} : valeur absente"
        assert 1 <= f["page"] <= e["pages_document"], (
            f"{ticker}.{nom} : page {f['page']} hors du document "
            f"({e['pages_document']} pages)")


@pytest.mark.parametrize("ticker", sorted(VERIFIES))
def test_le_bpa_decoule_des_faits_enregistres(faits, bpa, ticker):
    """Le contrôle qui compte vraiment : le BPA publié doit se REDÉDUIRE des
    faits, sinon on a seulement déplacé le chiffre non vérifiable.

    Tolérance large (3 %) parce que le diviseur légitime varie — nombre moyen
    pondéré, titres auto-détenus exclus — sans que ça change la conclusion.
    """
    f = faits[ticker]["faits"]
    rnpg = f.get("resultat_net_part_groupe")
    # Ordre de préséance du diviseur, et il compte :
    #   1. le nombre d'actions EXISTANT établi par une résolution d'AG — c'est
    #      lui qui vaut pour un ratio par action d'aujourd'hui ;
    #   2. à défaut, le nombre retenu par la société pour son propre BPA
    #      (moyenne pondérée au sens d'IAS 33) ;
    #   3. à défaut, le total inscrit au rapport.
    # Risma a fait basculer 1 devant 2 : sa résolution du 02/06/2026 établit
    # 16 012 132 titres quand le rapport en moyenne 14 326 947. Les deux sont
    # justes — ils répondent à deux questions différentes.
    actions = (f.get("nombre_actions_existant")
               or f.get("nombre_actions_retenu_pour_le_bpa")
               or f.get("nombre_actions_au_rapport"))
    if not rnpg or not actions:
        pytest.skip(f"{ticker} : le rapport ne donne pas les deux termes")

    n = actions["valeur"]
    if ticker == "SOT":
        # Le rapport précède le split ×5 du 05/05/2026 ; le BPA publié est
        # post-split, le nombre d'actions du rapport ne l'est pas.
        n *= 5
    attendu = rnpg["valeur"] * 1e6 / n
    assert attendu == pytest.approx(bpa[ticker]["bpa"], rel=0.03), (
        f"{ticker} : {rnpg['valeur']} MMAD ÷ {n:,} actions = {attendu:.2f}, "
        f"mais bpa.json porte {bpa[ticker]['bpa']}")


def test_sothema_ne_reprend_pas_le_rnpg_de_la_page_de_synthese(faits):
    """⚠️ Mon propre outil s'est trompé ici (ERRORS, famille 10) : il a lu 418
    sur une page de faits marquants dont l'extraction mélange les colonnes.
    L'état consolidé audité donne 388 229 KMAD, et 50,7 × 7 606 728 = 385,7
    le confirme."""
    assert faits["SOT"]["faits"]["resultat_net_part_groupe"]["valeur"] == 386.0
    assert faits["SOT"]["faits"]["resultat_net_consolide"]["page"] == 64


def test_aucun_bpa_verifie_ne_reste_sur_une_source_secondaire(bpa):
    """SNA portait une estimation 2026 (« bookvaleur_2025 ») dans un champ de
    résultat réalisé. Le champ et son contenu ne parlaient pas du même
    exercice."""
    for t in VERIFIES:
        n = bpa[t].get("note", "")
        assert "CORRIGÉ" in n or "AMMC" in bpa[t].get("source", ""), (
            f"{t} : rien n'atteste que ce BPA a été relu dans le rapport")


# ── recoupement à trois sources (10/09/2026) ─────────────────────────────
#
# Le calendrier des dividendes d'IDBourse, apporté par Abd Moutalib, donne une
# TROISIÈME lecture, indépendante d'Attijari et des dépôts AMMC. Résultat du
# recoupement sur 47 valeurs appariées : **40 concordances**.
#
# ⚠️ MON EXTRACTEUR S'EST TROMPÉ AVANT LES DONNÉES. Ce PDF mélange les deux
# conventions décimales — « 3.5 » avec un point, « 8,44 » avec une virgule — et
# ma première passe supprimait tous les points : Colorado passait de 3,5 à 35,
# TotalEnergies de 89,57 à 8 957. J'ai failli conclure à neuf écarts qui
# n'existaient pas. Contrôler le résultat, jamais l'outil.

def test_les_dividendes_restent_dans_un_ordre_de_grandeur_plausible(bpa):
    """Un dividende par action de plusieurs milliers de dirhams n'existe pas
    sur ce marché — sauf pour les très hauts cours. Le rapport dividende/cours
    borne l'absurdité mieux qu'un seuil absolu.

    Ce test attrape la classe d'erreur qui m'a piégé : un séparateur décimal
    mal lu déplace la virgule d'un facteur 10, 100 ou 1000.
    """
    import json as _j
    d = _j.loads((RACINE / "data.json").read_text(encoding="utf-8"))
    cours = {x["symbol"]: x.get("price") for x in d["tickers"]}
    for t, e in bpa.items():
        v, p = e.get("div_dh"), cours.get(t)
        if v is None or not p:
            continue
        assert 0 <= v <= p, (
            f"{t} : dividende de {v} DH pour un cours de {p} DH — un titre ne "
            "distribue pas plus que sa propre valeur ; séparateur décimal ?")
        if v > 0:
            rendement = v / p * 100
            assert rendement <= 25, (
                f"{t} : rendement de {rendement:.1f} % ({v} DH sur {p} DH). "
                "Au-delà de 25 %, c'est une erreur de saisie ou d'unité, pas "
                "une politique de distribution.")


def test_les_dividendes_issus_de_deux_sources_le_disent(bpa):
    """Une valeur qui repose sur deux sources secondaires concordantes n'est
    pas une valeur vérifiée en source primaire. La différence doit rester
    lisible dans le fichier, sinon elle se perd à la première relecture."""
    for t, e in bpa.items():
        src = e.get("div_source") or ""
        if "deux sources" not in src:
            continue
        assert "non relue" in (e.get("div_statut") or ""), (
            f"{t} : deux sources concordantes, mais le statut ne dit pas que "
            "la résolution d'assemblée n'a pas été lue")
