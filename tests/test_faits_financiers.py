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


def test_chaque_fait_porte_sa_page():
    """La règle non négociable du fichier.

    Sans page, on ne peut pas recontrôler, et le fichier n'apporte rien de
    plus que `fondamentaux.json`.
    """
    for tic, e in _emetteurs(_charge()).items():
        for nom, fait in e["faits"].items():
            assert "page" in fait, f"{tic}.{nom} n'a pas de page"
            assert isinstance(fait["page"], int) and fait["page"] > 0
            assert fait["page"] <= e["pages_document"], (
                f"{tic}.{nom} renvoie à la page {fait['page']} d'un document "
                f"qui en compte {e['pages_document']}")


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
        trouves = interdits & set(e["faits"])
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
