#!/usr/bin/env python3
"""Une valeur aberrante se refuse à l'entrée, pas à la porte de sortie.

LA PUBLICATION ANNULÉE DU 16/09/2026
────────────────────────────────────
16h22 Casablanca. La source a servi pour Minière Touissit une capitalisation de
**3 727 MDHS** là où elle valait **7 313** un run plus tôt — exactement la
moitié. CMT est suspendue depuis le 17/07 : son cours est figé à 4 350, son
volume est nul. Rien, dans le titre, n'avait bougé.

Les contrôles de publication l'ont vu, et ils ont eu raison de le voir : le
P/BOOK tombait de 8,12 à 4,14, et le nombre d'actions implicite de 1 681 233 à
856 782. Mais comme ces contrôles sont BLOQUANTS, **la séance entière n'a pas
été publiée**. Quatre-vingts titres retenus pour la capitalisation fautive d'un
seul, et le terminal figé sur le run précédent.

CE QUI ÉTAIT MAL PLACÉ
──────────────────────
Pas le contrôle : le MOMENT.

À la porte de sortie, on ne peut plus que tout annuler. À l'entrée, on peut
neutraliser UN titre et publier les soixante-dix-neuf autres. C'est la même
logique que la chaîne de repli des prix (R3), qui écarte une ligne périmée sans
renoncer à la séance.

L'ARBITRE ÉTAIT DÉJÀ ÉCRIT
──────────────────────────
Le CLAUDE.md le fixe depuis le 02/07 (LOI N°3, règle 2) : « valider via
prix × nb_titres ; la cap dans data.json doit être cohérente avec ce calcul ».
Les deux termes sont sourcés — le cours par la chaîne de repli, le nombre
d'actions par un rapport déposé à l'AMMC, avec sa page.

⚠️ LE SEUIL N'EST PAS ARBITRAIRE. Relevé le 16/09 sur les 21 titres dont le
nombre d'actions est sourcé, le pire écart légitime vaut 3,2 % (Mutandis). Dix
pour cent laisse trois fois cette marge, et écarte sans hésiter le facteur deux.

⚠️ ET ON NE TRANCHE PAS SANS ARBITRE. Sans nombre d'actions sourcé, la
capitalisation servie est gardée telle quelle. Refuser faute de pouvoir
vérifier supprimerait la capitalisation des cinquante-neuf titres dont le
rapport n'est pas encore relevé — on remplacerait un défaut rare par une perte
générale.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parent.parent

from conftest import chemin_data_json  # noqa: E402


@pytest.fixture(scope="module")
def moteur():
    """Le module du moteur, chargé une fois."""
    spec = importlib.util.spec_from_file_location("ud_cap", RACINE / "update_data.py")
    m = importlib.util.module_from_spec(spec)
    sys.modules["ud_cap"] = m
    spec.loader.exec_module(m)
    return m


def _faits(n_actions, exercice=2025):
    return {"CMT": {"exercice": exercice,
                    "faits": {"nombre_actions_au_rapport": {"valeur": n_actions,
                                                            "page": 57}}}}


# (nom, actions sourcées, prix, cap servie, cap attendue, provenance attendue)
SITUATIONS = [
    ("LE 16/09 : capitalisation servie de moitié",
     1_681_233, 4350.0, 3727, 7313, "calculee_apres_refus"),

    ("capitalisation servie cohérente : on la garde",
     1_681_233, 4350.0, 7313, 7313, "servie"),

    ("écart de 3 % : dans la marge des écarts réels",
     1_681_233, 4350.0, 7100, 7100, "servie"),

    ("capitalisation absente mais actions sourcées",
     1_681_233, 4350.0, None, 7313, "calculee_faute_de_source"),

    ("capitalisation doublée : refusée aussi",
     1_681_233, 4350.0, 14600, 7313, "calculee_apres_refus"),
]


@pytest.mark.parametrize("nom,actions,prix,servie,attendue,provenance",
                         SITUATIONS, ids=[s[0] for s in SITUATIONS])
def test_la_capitalisation_est_arbitree(moteur, nom, actions, prix, servie,
                                        attendue, provenance):
    moteur.FAITS_DATA = _faits(actions)
    cap, src = moteur._capitalisation("CMT", prix, servie)
    assert (cap, src) == (attendue, provenance), f"{nom} → {cap} ({src})"


def test_sans_actions_sourcees_on_ne_tranche_pas(moteur):
    """⚠️ La moitié de la cote n'a pas encore de rapport relevé.

    Refuser une capitalisation qu'on ne peut pas vérifier reviendrait à la
    supprimer pour cinquante-neuf titres : on remplacerait un défaut rare par
    une perte générale.
    """
    moteur.FAITS_DATA = {}
    assert moteur._capitalisation("XXX", 100.0, 1234) == (1234, "servie")
    assert moteur._capitalisation("XXX", 100.0, None) == (None, "absente")


def test_un_refus_ne_neutralise_que_le_titre_concerne(moteur):
    """LE CŒUR DU CORRECTIF.

    Le contrôle rend une valeur pour CE titre. Il ne lève pas, il n'interrompt
    rien : les autres titres suivent leur chemin. C'est toute la différence
    avec un contrôle de publication, qui ne sait qu'annuler la séance entière.
    """
    moteur.FAITS_DATA = _faits(1_681_233)
    cap, src = moteur._capitalisation("CMT", 4350.0, 3727)
    assert cap == 7313 and src == "calculee_apres_refus"
    # Et un titre inconnu du référentiel traverse sans encombre.
    assert moteur._capitalisation("AUTRE", 250.0, 900) == (900, "servie")


def test_le_seuil_laisse_passer_les_ecarts_reels(moteur):
    """3,2 % est le pire écart légitime mesuré ; le seuil est à 10 %.

    Un seuil trop serré ferait refuser des capitalisations justes, et le moteur
    publierait alors SA valeur à la place de celle du marché — l'inverse de ce
    qu'on cherche.
    """
    assert moteur.ECART_CAP_TOLERE >= 0.05, "seuil trop serré : des écarts réels seraient refusés"
    assert moteur.ECART_CAP_TOLERE <= 0.25, "seuil trop lâche : un facteur deux passerait"
    moteur.FAITS_DATA = _faits(1_000_000)
    for ecart in (0.0, 0.032, 0.09):
        servie = round(100 * 1_000_000 / 1e6 / (1 + ecart))
        _, src = moteur._capitalisation("CMT", 100.0, servie)
        assert src == "servie", f"un écart de {ecart:.1%} a été refusé"


# ── Ce que le fichier publié doit montrer ────────────────────────────────────

def test_la_provenance_de_la_capitalisation_est_publiee():
    """Un chiffre remplacé sans le dire est exactement ce qu'on reproche à la
    table figée. Chaque titre porte d'où vient sa capitalisation.

    ⚠️ Le contrôle porte sur le MOTEUR autant que sur le fichier. Un fichier
    publié hier garde son `cap_source` même si le code cesse de l'émettre —
    seule la lecture du moteur attrape la suppression tout de suite. C'est le
    piège des tests qui relisent des données : ils décrivent le dernier run,
    pas le code d'aujourd'hui.
    """
    moteur = (RACINE / "update_data.py").read_text(encoding="utf-8")
    assert '"cap_source":' in moteur, (
        "le moteur n'émet plus la provenance de la capitalisation")
    assert "cap_source=_cap_source" in moteur, (
        "la provenance est déclarée mais jamais transmise")

    d = json.loads(chemin_data_json().read_text(encoding="utf-8"))
    porteurs = [t for t in d["tickers"] if "cap_source" in (t.get("_meta") or {})]
    if not porteurs:
        # Le fichier a été produit avant ce contrôle. Ce n'est pas une
        # exemption qui s'installe : `tests.yml` et la garde bloquante
        # RÉGÉNÈRENT data.json avant de lancer la suite, donc là où cela
        # compte, la branche ci-dessous est toujours prise. Et l'assertion sur
        # le moteur, elle, vient de s'exécuter sans condition.
        pytest.skip("data.json antérieur au contrôle de capitalisation")
    sans = [t["symbol"] for t in d["tickers"]
            if "cap_source" not in (t.get("_meta") or {})]
    assert not sans, f"capitalisation sans provenance : {sans[:8]}"


def test_aucune_capitalisation_publiee_ne_contredit_les_actions_sourcees():
    """⚠️ LE CONTRÔLE QUI REMPLACE CELUI QUI BLOQUAIT.

    Il porte sur le fichier publié, et il ne peut plus échouer pour une valeur
    aberrante de la source : le moteur l'a déjà refusée en amont. S'il échoue
    malgré tout, c'est que le refus n'a pas eu lieu — et là, il a raison de
    bloquer.
    """
    sys.path.insert(0, str(RACINE))
    from bvc_config import SPLITS

    d = json.loads(chemin_data_json().read_text(encoding="utf-8"))
    ff = json.loads((RACINE / "pipeline" / "faits_financiers.json")
                    .read_text(encoding="utf-8"))
    ecarts, controles = [], 0
    for x in d["tickers"]:
        t, prix, cap = x["symbol"], x.get("price"), x.get("cap")
        e = ff.get(t)
        if not isinstance(e, dict) or not prix or not cap:
            continue
        f = e.get("faits") or {}
        na = (f.get("nombre_actions_existant") or f.get("nombre_actions_au_rapport")
              or f.get("nombre_actions_retenu_pour_le_bpa"))
        if not na:
            continue
        n = float(na["valeur"])
        cloture = f"{e.get('exercice', 2025)}-12-31"
        for sp in SPLITS.get(t, []):
            if sp["date"] > cloture:
                n *= sp["ratio"]
        controles += 1
        calc = prix * n / 1e6
        if abs(calc / cap - 1) > 0.12:          # un cheveu au-dessus du seuil moteur
            ecarts.append(f"{t} : publié {cap:.0f} MDHS, prix × actions = {calc:.0f}")
    assert controles >= 15, (
        f"seuls {controles} titres contrôlés — le référentiel a-t-il rétréci ?")
    assert not ecarts, ("le refus en amont n'a pas eu lieu :\n  " + "\n  ".join(ecarts))
