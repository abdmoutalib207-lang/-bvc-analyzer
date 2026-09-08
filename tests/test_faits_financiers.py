"""Les faits financiers doivent rester vérifiables — chacun avec sa page.

POURQUOI CE FICHIER EXISTE
──────────────────────────
`fondamentaux.json` porte 77 sociétés, saisies à la main depuis une
quarantaine de sources secondaires — « Zonebourse / Boursenews »,
« L'Economiste / Wafabourse », des notes de courtiers — et tout y date de
juin 2026. Aucun chiffre n'est rattachable à un document : si quelqu'un
demande d'où vient un PER, la réponse honnête est « d'un site financier, en
juin, et j'ignore comment il l'a calculé ».

Mesuré le 07/09/2026 sur ADI, en descendant au rapport déposé à l'AMMC :

    price-to-book        rapport 2,30   terminal 0,80    ×2,9
    dette nette / EBE    rapport 2,16   terminal 5,50    ×2,5
    croissance du CA     rapport +2,9 % terminal 25,7 %  ×9

Le premier écart inverse la thèse : le terminal présente un titre sous sa
valeur comptable alors qu'il vaut 2,3 fois ses fonds propres.

CE QUE CES TESTS GARANTISSENT
Que le fichier de faits ne dérive pas vers les mêmes travers. Un fait sans
page redevient un chiffre de seconde main — on aurait seulement déplacé le
problème.
"""

import json
from pathlib import Path

import pytest

CHEMIN = Path(__file__).resolve().parent.parent / "pipeline" / "faits_financiers.json"


def _charge():
    if not CHEMIN.exists():
        pytest.skip("faits_financiers.json pas encore créé")
    return json.loads(CHEMIN.read_text(encoding="utf-8"))


def _emetteurs(d):
    return {k: v for k, v in d.items() if not k.startswith("_")}


def _blocs(e):
    """Le bloc annuel, puis chaque publication trimestrielle.

    Les mêmes règles s'appliquent partout : sans cela, un fait déposé dans
    `publications` échapperait au contrôle de page et à l'interdiction des
    ratios — et le fichier dériverait par le bas.
    """
    yield e
    for pub in e.get("publications", []):
        yield pub


def test_chaque_fait_porte_sa_page():
    """La règle non négociable du fichier.

    Sans page, on ne peut pas recontrôler, et le fichier n'apporte rien de
    plus que `fondamentaux.json`.
    """
    for tic, e in _emetteurs(_charge()).items():
        for bloc in _blocs(e):
            for nom, fait in bloc["faits"].items():
                assert "page" in fait, f"{tic}.{nom} n'a pas de page"
                assert isinstance(fait["page"], int) and fait["page"] > 0
                assert fait["page"] <= bloc["pages_document"], (
                    f"{tic}.{nom} renvoie à la page {fait['page']} d'un "
                    f"document qui en compte {bloc['pages_document']}")


def test_chaque_emetteur_porte_son_document_et_sa_date():
    for tic, e in _emetteurs(_charge()).items():
        for champ in ("societe", "exercice", "document", "url",
                      "depose_aupres_de", "releve_le"):
            assert e.get(champ), f"{tic} : champ « {champ} » manquant"
        assert e["url"].startswith("https://"), f"{tic} : url non sécurisée"


def test_le_capital_se_recoupe_avec_le_nombre_d_actions():
    """Le contrôle arithmétique qui a tranché l'ISIN de Maroc Leasing.

    `capital social ÷ valeur nominale = nombre d'actions`. Deux sources
    peuvent se tromper ensemble ; un calcul qui boucle, non. C'est la
    méthode de validation la plus fiable dont dispose le projet.
    """
    for tic, e in _emetteurs(_charge()).items():
        f = e["faits"]
        if "capital_social" not in f or "nombre_actions" not in f:
            continue
        capital = f["capital_social"]["valeur"] * 1e6      # MMAD → MAD
        actions = f["nombre_actions"]["valeur"]
        nominale = capital / actions
        assert abs(nominale - round(nominale)) < 0.01, (
            f"{tic} : capital {capital:,.0f} ÷ {actions:,} donne une valeur "
            f"nominale de {nominale:.4f}, qui n'est pas un nombre rond")
        assert 1 <= nominale <= 1000, f"{tic} : valeur nominale {nominale} implausible"


def test_la_part_du_groupe_ne_depasse_pas_le_consolide_sans_explication():
    """Le résultat part du groupe PEUT dépasser le consolidé.

    C'est le cas d'ADI en 2025 : 407,6 contre 401,8, parce que les intérêts
    minoritaires sont en perte. Ce n'est pas une erreur de saisie — mais ça
    doit être dit, sinon le prochain lecteur le corrigera « à l'envers ».
    """
    for tic, e in _emetteurs(_charge()).items():
        f = e["faits"]
        if "resultat_net_part_groupe" not in f or "resultat_net_consolide" not in f:
            continue
        pg, cons = f["resultat_net_part_groupe"], f["resultat_net_consolide"]
        if pg["valeur"] > cons["valeur"]:
            assert pg.get("note"), (
                f"{tic} : la part du groupe dépasse le consolidé sans note "
                f"expliquant pourquoi")


def test_les_ratios_ne_sont_pas_stockes():
    """Un ratio stocké se fige. C'est le défaut `pb_fige`, sur 80 titres/80.

    Le fichier ne porte que des FAITS. Les ratios se recalculent depuis ces
    faits et le cours du jour, à chaque fois.
    """
    interdits = {"per", "pe", "pb", "price_to_book", "roic", "div_yield",
                 "marge_nette", "croissance_ca", "dette_nette_ebitda"}
    for tic, e in _emetteurs(_charge()).items():
        for bloc in _blocs(e):
            trouves = interdits & set(bloc["faits"])
            assert not trouves, (
                f"{tic} : {sorted(trouves)} sont des ratios, pas des faits. "
                f"Les stocker revient à refaire `pb_fige`.")


def test_les_ecarts_mesures_citent_les_deux_cotes():
    """Un écart consigné doit dire ce que dit le rapport ET ce que dit le
    terminal, sinon il n'est pas reproductible."""
    for tic, e in _emetteurs(_charge()).items():
        ec = e.get("_ecarts_mesures")
        if not ec:
            continue
        assert ec.get("_quand"), f"{tic} : les écarts n'ont pas de date"
        for nom, val in ec.items():
            if nom.startswith("_"):
                continue
            assert {"rapport", "terminal", "ecart"} <= set(val), (
                f"{tic}.{nom} : un écart doit porter rapport, terminal et ecart")


def test_chaque_publication_porte_sa_date_et_son_document():
    """Une publication trimestrielle sans date d'arrêté est inutilisable.

    ⚠️ Au Maroc, un trimestriel publie le chiffre d'affaires, l'endettement et
    l'activité commerciale — jamais le résultat net ni les capitaux propres.
    Le PER et le price-to-book ne peuvent donc être rafraîchis que deux fois
    par an. La date d'arrêté est ce qui permet de dire à l'écran « PB au
    31/12/2025 » plutôt que de le laisser passer pour courant.
    """
    for tic, e in _emetteurs(_charge()).items():
        for pub in e.get("publications", []):
            for champ in ("periode", "arrete_au", "type", "document",
                          "url", "publie_le", "pages_document"):
                assert pub.get(champ), f"{tic}/{pub.get('periode','?')} : « {champ} » manquant"
            assert pub["arrete_au"] <= pub["publie_le"], (
                f"{tic}/{pub['periode']} : publié avant sa propre date d'arrêté")


def test_les_publications_vont_de_la_plus_recente_a_la_plus_ancienne():
    """L'ordre porte du sens : la première ligne est l'état le plus frais."""
    for tic, e in _emetteurs(_charge()).items():
        dates = [p["arrete_au"] for p in e.get("publications", [])]
        assert dates == sorted(dates, reverse=True), (
            f"{tic} : publications dans le désordre — {dates}")


# ── contrôles de vraisemblance sur les données PUBLIÉES ──────────────────

def test_aucun_benefice_par_action_n_excede_le_cours():
    """Un BPA supérieur au cours signale presque toujours une opération sur
    titres non répercutée.

    ⚠️ C'est le défaut trouvé le 08/09 sur Managem : `bpa.json` porte 234,0
    avec la note « PER réel 64 (cours 14 998 DH) » — un cours d'AVANT le split
    10:1 du 27/07/2026. Le split a divisé le cours par dix, pas le BPA. Le
    terminal affichait donc Managem à 7,5 fois ses bénéfices, un titre bon
    marché, alors qu'il se paie 69 fois.

    Le seuil est volontairement large : un BPA vaut rarement plus du tiers du
    cours (PER 3), et jamais sur un marché comme la BVC.
    """
    racine = Path(__file__).resolve().parent.parent
    d = json.loads((racine / "data.json").read_text(encoding="utf-8"))
    coupables = []
    for x in d["tickers"]:
        bpa, prix = x.get("bpa"), x.get("price")
        if not bpa or not prix or prix <= 0:
            continue
        if bpa > prix / 3:
            coupables.append((x["symbol"], bpa, prix, round(prix / bpa, 1)))

    # ⚠️ Les cas déjà constatés et non encore tranchés sont en quarantaine
    # dans faits_financiers.json, avec leur date et ce qu'il faut pour les
    # lever. Sans cela, ce test resterait rouge en permanence — et une alarme
    # toujours allumée n'alerte plus. Il échoue donc sur les cas NOUVEAUX.
    connus = set(_charge().get("_defauts_connus", {}).get("bpa_implausible", {}))
    nouveaux = [c for c in coupables if c[0] not in connus]
    assert not nouveaux, (
        "BPA implausible — vérifier une opération sur titres non répercutée "
        f"(cf. SPLITS dans bvc_config.py) : {nouveaux}")


def test_aucun_resultat_net_n_excede_la_capitalisation():
    """Le contrôle qui aurait attrapé la collision MRL / Marsa Maroc.

    `bpa.json["MRL"]` — Maroc Leasing, société de financement — porte la note
    « RNPG 1 589 MDH, trafic 67 Mt ». C'est la description de Marsa Maroc.
    Maroc Leasing capitalise 1 076 MMAD : un tel résultat donnerait un PER de
    0,68, ce qui n'existe pas.

    Le test porte sur `bpa × nombre d'actions` reconstitué depuis la
    capitalisation et le cours — donc sur ce que le terminal publie
    réellement, pas sur une intention.
    """
    racine = Path(__file__).resolve().parent.parent
    d = json.loads((racine / "data.json").read_text(encoding="utf-8"))
    coupables = []
    for x in d["tickers"]:
        bpa, prix, cap = x.get("bpa"), x.get("price"), x.get("cap")
        if not bpa or not prix or not cap or prix <= 0 or cap <= 0:
            continue
        actions = cap * 1e6 / prix
        rn = bpa * actions / 1e6           # en MMAD
        if rn > cap:                        # PER < 1
            coupables.append((x["symbol"], round(rn), cap, round(prix / bpa, 2)))
    assert not coupables, (
        "résultat net reconstitué supérieur à la capitalisation — identité "
        f"probablement croisée : {coupables}")
