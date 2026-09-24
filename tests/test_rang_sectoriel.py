#!/usr/bin/env python3
"""Situer un ratio dans son secteur — et se taire quand on ne peut pas.

⚠️ LE PIÈGE DE CE MODULE EST LE SENS DE LECTURE
───────────────────────────────────────────────
Pour le PER et le price-to-book, **bas vaut mieux que haut** : un PER faible
dit « pas cher ». Un classement naïf, du plus grand au plus petit, mettrait
donc le titre le plus CHER au rang 1 — et le lecteur, qui lit un rang comme un
palmarès, conclurait l'inverse de la vérité.

Pour le dividende c'est l'opposé, et c'est pourquoi les deux sens sont testés
côte à côte : un module qui se tromperait sur l'un seulement rendrait des
chiffres justes et un classement retourné.

⚠️ LE SECOND PIÈGE EST DE CONCLURE SUR RIEN
La cote de Casablanca compte des secteurs à un titre — Télécom en a un. Un
« rang 1 sur 1 » n'informe de rien, et une médiane sur deux valeurs est un
tirage au sort. Rendre `None` se lit « pas assez de pairs » ; rendre « dans la
moyenne » serait une affirmation, et elle serait fausse.
"""

from __future__ import annotations

import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))
sys.path.insert(0, str(RACINE / "pipeline"))

from rang_sectoriel import MIN_PAIRS, rangs, resume  # noqa: E402


def _t(sym, secteur, pe=None, pb=None, div=None):
    return {"symbol": sym, "sector": secteur, "pe": pe, "pb": pb, "div": div}


def _banques(pes):
    return [_t(f"B{i}", "Banque", pe=v) for i, v in enumerate(pes)]


# ── ⚠️ Le sens de lecture ──────────────────────────────────────────────────

def test_pour_le_per_le_rang_1_est_le_MOINS_cher():
    """⚠️ LA GARDE CENTRALE. Un rang se lit comme un palmarès : le 1 doit
    désigner le titre le plus attrayant. Classer du plus grand au plus petit
    mettrait le plus CHER en tête et retournerait la conclusion."""
    r = rangs(_banques([30, 20, 10, 40]))
    assert r["B2"]["pe"]["rang"] == 1, "le PER de 10 est le moins cher"
    assert r["B3"]["pe"]["rang"] == 4, "le PER de 40 est le plus cher"


def test_pour_le_dividende_le_rang_1_est_le_PLUS_genereux():
    """Le sens inverse, et c'est pourquoi les deux sont testés ensemble."""
    t = [_t(f"D{i}", "Banque", div=v) for i, v in enumerate([1.0, 5.0, 3.0, 2.0])]
    r = rangs(t)
    assert r["D1"]["div"]["rang"] == 1, "5 % est le meilleur rendement"
    assert r["D0"]["div"]["rang"] == 4


def test_le_price_to_book_suit_la_meme_regle_que_le_per():
    t = [_t(f"P{i}", "Banque", pb=v) for i, v in enumerate([3.0, 0.8, 1.5, 2.0])]
    assert rangs(t)["P1"]["pb"]["rang"] == 1


# ── ⚠️ Ne pas conclure sur rien ────────────────────────────────────────────

def test_un_secteur_trop_petit_ne_produit_aucun_rang():
    """Un « rang 1 sur 1 » n'informe de rien. Le silence est la seule réponse
    honnête — et il se lit « pas assez de pairs », pas « dans la moyenne »."""
    assert rangs([_t("SEUL", "Télécom", pe=14.8)]) == {}


def test_le_seuil_est_bien_celui_annonce():
    assert rangs(_banques([10] * (MIN_PAIRS - 1))) == {}
    assert rangs(_banques([10, 20, 30, 40][:MIN_PAIRS])) != {}


def test_un_titre_sans_le_ratio_ne_compte_pas_comme_pair():
    """⚠️ Quatre titres dans un secteur dont un seul porte un PER, ce n'est pas
    quatre comparables. Compter les lignes plutôt que les valeurs produirait un
    rang sur un échantillon d'un."""
    t = _banques([10, 20, 30, 40])
    for x in t[1:]:
        x["pe"] = None
    assert "pe" not in rangs(t).get("B0", {})


# ── Les valeurs qui ne se comparent pas ────────────────────────────────────

def test_un_per_negatif_est_ecarte():
    """⚠️ Un PER négatif n'est PAS un PER bas : c'est une société en perte. Le
    classer parmi les moins chers le hisserait en tête d'un palmarès
    « bon marché » — exactement l'inverse de ce qu'il signifie."""
    t = _banques([10, 20, 30, 40, 50])
    t[0]["pe"] = -8.0
    r = rangs(t)
    assert "B0" not in r or "pe" not in r["B0"]
    assert r["B1"]["pe"]["rang"] == 1, "le PER de 20 devient le moins cher"


def test_un_price_to_book_nul_est_ecarte():
    t = _banques([10, 20, 30, 40])
    for x, v in zip(t, [0.0, 1.0, 2.0, 3.0]):
        x["pb"] = v
    r = rangs(t)
    assert "pb" not in r.get("B0", {})


def test_une_valeur_non_numerique_ne_fait_pas_tomber_le_calcul():
    """⚠️ Le premier jet de ce test attendait 3 titres classés là où le module
    n'en rendait aucun — et le module avait raison : six titres moins deux
    valeurs illisibles font quatre comparables, soit tout juste le seuil.
    C'était le test qui était faux, pas le code."""
    t = _banques([10, 20, 30, 40, 50, 60])
    t[0]["pe"] = "n/d"
    t[1]["pe"] = True          # un booléen n'est pas un nombre ici
    r = rangs(t)
    assert len(r) == 4
    assert r["B2"]["pe"]["rang"] == 1, "le PER de 30 devient le moins cher"


# ── Ce que le relevé publie ────────────────────────────────────────────────

def test_la_mediane_et_l_ecart_sont_justes():
    """Attendus calculés à la main : médiane de (10, 20, 30, 40) = 25 ;
    écart de 10 à 25 = −60 %."""
    r = rangs(_banques([10, 20, 30, 40]))
    assert r["B0"]["pe"]["mediane_secteur"] == 25.0
    assert r["B0"]["pe"]["ecart_pct"] == -60.0
    assert r["B0"]["pe"]["pairs"] == 4
    assert r["B0"]["pe"]["secteur"] == "Banque"


def test_les_secteurs_ne_se_melangent_pas():
    """⚠️ Le point entier du module. Un promoteur ne se compare pas à une
    banque ; les deux groupes doivent produire deux médianes distinctes."""
    t = _banques([10, 12, 14, 16]) + [
        _t(f"I{i}", "Immobilier", pe=v) for i, v in enumerate([40, 42, 44, 46])]
    r = rangs(t)
    assert r["B0"]["pe"]["mediane_secteur"] == 13.0
    assert r["I0"]["pe"]["mediane_secteur"] == 43.0
    assert r["I0"]["pe"]["rang"] == 1, "le rang se calcule DANS le secteur"


def test_le_resume_dit_ce_qui_n_a_pas_pu_etre_situe():
    """⚠️ Ce chiffre compte autant que l'autre : il dit sur combien de titres
    la lecture sectorielle est muette, et pourquoi."""
    t = _banques([10, 20, 30, 40]) + [_t("SEUL", "Télécom", pe=14.8)]
    r = resume(rangs(t), t)
    assert r["titres_classes"] == 4
    assert r["titres_total"] == 5
    assert r["secteurs_trop_petits"] == {"Télécom": 1}


# ── ⚠️ R8 : le score ne bouge pas ──────────────────────────────────────────

def test_le_module_ne_touche_a_aucun_score():
    """Le rang est une lecture posée À CÔTÉ du chiffre, jamais dedans. L'y
    faire entrer déplacerait la note de tous les titres — ce que R8 interdit
    sans backtesting et accord explicite."""
    import ast
    source = (RACINE / "pipeline" / "rang_sectoriel.py").read_text(encoding="utf-8")
    arbre = ast.parse(source)
    interdits = {"v53", "bvc", "score_fond", "score_tech", "score_nlp", "poids"}
    for n in ast.walk(arbre):
        if isinstance(n, ast.Constant) and isinstance(n.value, str):
            assert n.value not in interdits, (
                f"le module manipule « {n.value} » — il ne doit lire que des "
                f"ratios, jamais toucher au score")


def test_le_titre_n_est_pas_modifie():
    import copy
    t = _banques([10, 20, 30, 40])
    avant = copy.deepcopy(t)
    rangs(t)
    assert t == avant


# ── Le flux publié ─────────────────────────────────────────────────────────

def test_le_flux_publie_situe_une_part_utile_des_titres():
    """Sur la cote réelle, une quarantaine de titres appartiennent à un secteur
    assez fourni. En dessous, ce serait que la table des secteurs a été cassée,
    pas que le marché a changé."""
    import json
    import pytest
    chemin = RACINE / "data.json"
    if not chemin.exists():
        pytest.skip("data.json absent de ce clone")
    t = json.loads(chemin.read_text(encoding="utf-8")).get("tickers") or []
    if not t:
        pytest.skip("data.json vide")
    r = rangs(t)
    assert len(r) >= 30, (
        f"seulement {len(r)} titres situés dans leur secteur sur {len(t)} — "
        f"la table COMPANY_SECTORS est-elle intacte ?")
