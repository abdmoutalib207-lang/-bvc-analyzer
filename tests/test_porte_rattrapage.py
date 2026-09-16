#!/usr/bin/env python3
"""Le filet de sécurité voit-il le trou qu'il est censé rattraper ?

LE JOUR OÙ IL NE L'A PAS VU
───────────────────────────
Mercredi 16/09/2026, 11h08 Casablanca — une heure trente-huit APRÈS
l'ouverture. Le terminal servait encore la clôture du 15 :

    data.json  updated : 2026-09-16T03:15:41+0100
               prix_asof : 78 titres au 2026-09-15

Deux choses avaient manqué, et la seconde est la grave.

1. Le cron de 09h40 n'est pas parti. C'est le mal connu, documenté depuis le
   28/08 : GitHub décale ses tâches de deux à huit heures, quand il ne les
   oublie pas.

2. LE FILET N'A PAS VU LE TROU. Le cron horaire existe précisément pour ça, et
   sa porte répondait « à jour — rien à rattraper ». Elle jugeait sur la DATE
   DU FICHIER et non sur la SÉANCE QU'IL PORTE : un run de 3h du matin — un
   rattrapage tardif de la VEILLE — lui suffisait à croire la journée couverte.
   Sa première règle exigeait de surcroît qu'il soit 10h30 passées.

   Entre 9h30 et 16h30, un fichier fabriqué avant l'ouverture était donc réputé
   à jour. Sans intervention manuelle, le terminal aurait montré la veille
   pendant toute la séance.

CE QUE CES TESTS PROTÈGENT
──────────────────────────
La première situation de la table ci-dessous EST celle du 16/09, chiffres
compris. Elle doit rendre « lancer ». C'est le test qui aurait épargné la
journée.

⚠️ ET LE FREIN, qui compte autant. Un jour férié, la séance du jour n'existera
jamais : sans frein, la règle déclencherait un run par heure, donc un commit
par heure, et le quota de reconstruction de GitHub Pages — la ressource rare du
projet — y passerait. Une tentative par fenêtre suffit : si un run a déjà eu
lieu sans ramener les cours du jour, recommencer n'y changera rien.

Supprimer le frein pour « être sûr de ne rien rater » casserait la publication
même qu'on cherche à protéger. Deux tests l'interdisent.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE / "pipeline"))

from porte_rattrapage import decider, seance_portee  # noqa: E402

yaml = pytest.importorskip("yaml")


def fichier(updated: str, asof: str, retardataires: dict | None = None) -> dict:
    """Un data.json réduit à ce que la porte regarde.

    `retardataires` permet de glisser des titres qui n'ont pas coté — la
    situation normale, jamais l'exception.
    """
    # ⚠️ LES RETARDATAIRES VIENNENT EN TÊTE, et ce n'est pas un détail de
    # fabrication. `data.json` est rangé par le classement, donc dans un ordre
    # arbitraire au regard des dates. En les mettant à la fin, une lecture « au
    # premier titre venu » rendrait par accident la bonne réponse et le
    # contrôle de la majorité ne prouverait rien — vérifié par mutation.
    tickers = [{"symbol": sym, "_meta": {"prix_asof": date}}
               for sym, date in (retardataires or {}).items()]
    tickers += [{"symbol": f"T{i:02d}", "_meta": {"prix_asof": asof}}
                for i in range(60)]
    return {"updated": updated, "tickers": tickers}


AUJ = "2026-09-16"
HIER = "2026-09-15"


# (nom, maintenant, fichier, attendu)
SITUATIONS = [
    ("LE 16/09 : 11h08, fichier de 3h du matin portant la veille",
     1108, fichier(f"{AUJ}T03:15:41+0100", HIER), True),

    ("la séance du jour est déjà là",
     1108, fichier(f"{AUJ}T09:47:00+0100", AUJ), False),

    ("férié : déjà tenté à 10h10 sans cours du jour",
     1125, fichier(f"{AUJ}T10:10:00+0100", HIER), False),

    ("trop tôt : 9h25, les titres peu liquides n'ont rien imprimé",
     925, fichier(f"{AUJ}T03:15:00+0100", HIER), False),

    ("avant l'ouverture : 8h00, le fichier porte la veille et c'est normal",
     800, fichier(f"{AUJ}T03:15:00+0100", HIER), False),

    ("la clôture a sauté : 17h25, fichier du jour écrit à midi",
     1725, fichier(f"{AUJ}T12:00:00+0100", AUJ), True),

    ("la clôture est prise : 17h25, fichier du jour écrit à 15h50",
     1725, fichier(f"{AUJ}T15:50:00+0100", AUJ), False),

    ("journée entière manquée : 16h25, rien du jour, jamais tenté le soir",
     1625, fichier(f"{AUJ}T03:15:00+0100", HIER), True),

    ("le frein du soir : 17h25, déjà tenté à 16h10 sans cours du jour",
     1725, fichier(f"{AUJ}T16:10:00+0100", HIER), False),

    ("le frein du MATIN ne vaut pas pour le soir",
     1625, fichier(f"{AUJ}T10:10:00+0100", HIER), True),

    ("des retardataires ne changent rien : la majorité porte le jour",
     1108, fichier(f"{AUJ}T09:47:00+0100", AUJ,
                   {"CMT": "2026-07-16", "LHM": "2026-08-05"}), False),

    ("fichier absent",
     1108, None, True),

    ("fichier sans aucune date de séance",
     1108, {"updated": f"{AUJ}T09:47:00+0100", "tickers": [{"symbol": "X"}]}, True),

    ("mi-séance, tout est en ordre",
     1500, fichier(f"{AUJ}T12:03:00+0100", AUJ), False),

    ("horodatage illisible et séance du jour absente : on lance",
     1108, fichier("n'importe quoi", HIER), True),
]


@pytest.mark.parametrize("nom,maintenant,data,attendu",
                         SITUATIONS, ids=[s[0] for s in SITUATIONS])
def test_la_porte_decide_comme_attendu(nom, maintenant, data, attendu):
    run, pourquoi = decider(maintenant, AUJ, data)
    assert run is attendu, f"{nom} → {run} ({pourquoi})"
    assert pourquoi, "une décision sans motif ne se relit pas dans un journal"


def test_la_situation_du_16_septembre_declenche_bien():
    """⚠️ LE TEST QUI COMPTE. Chiffres réels, relevés ce jour-là.

    Il est isolé de la table pour qu'on le voie tomber pour ce qu'il est : le
    terminal montrant la veille en pleine séance.
    """
    reel = fichier(f"{AUJ}T03:15:41+0100", HIER,
                   {"CMT": "2026-07-16", "LHM": "2026-08-05"})
    run, pourquoi = decider(1108, AUJ, reel)
    assert run is True, (
        "la porte laisserait de nouveau le terminal sur la veille pendant "
        f"toute la séance — motif rendu : {pourquoi}")
    assert HIER in pourquoi, "le motif ne dit pas quelle séance le fichier porte"


def test_le_frein_existe_et_borne_les_relances():
    """Au plus deux rattrapages par jour, même quand la séance n'existe pas.

    ⚠️ Sans frein, un jour férié produirait un run — donc un commit, donc une
    reconstruction de Pages — à chaque heure de la journée. Le quota de
    publication est la ressource rare du projet : le filet le consommerait.
    """
    declenches = []
    ecrit = f"{AUJ}T03:15:00+0100"
    porte = HIER
    for heure in range(9, 24):                    # le cron passe à HHh25
        maintenant = heure * 100 + 25
        run, _ = decider(maintenant, AUJ, fichier(ecrit, porte))
        if run:
            declenches.append(maintenant)
            # Le run a lieu : il réécrit le fichier, sans ramener de cours.
            ecrit = f"{AUJ}T{heure:02d}:28:00+0100"
    assert len(declenches) <= 2, (
        f"{len(declenches)} relances sur une journée sans cotation : {declenches}")
    assert declenches, "aucune relance : le filet ne sert plus à rien"


def test_une_journee_normale_ne_declenche_rien():
    """Les quatre crons prévus suffisent : le rattrapage doit rester muet.

    C'est l'autre moitié du contrat. Un filet qui se déclenche tous les jours
    n'est pas un filet, c'est un cinquième cron — et chacun coûte un commit.
    """
    journee = [
        (950, f"{AUJ}T09:45:00+0100"),
        (1125, f"{AUJ}T09:45:00+0100"),
        (1225, f"{AUJ}T12:04:00+0100"),
        (1425, f"{AUJ}T12:04:00+0100"),
        (1625, f"{AUJ}T15:48:00+0100"),
        (1825, f"{AUJ}T18:02:00+0100"),
        (2125, f"{AUJ}T18:02:00+0100"),
    ]
    for maintenant, ecrit in journee:
        run, pourquoi = decider(maintenant, AUJ, fichier(ecrit, AUJ))
        assert run is False, f"relance inutile à {maintenant:04d} : {pourquoi}"


def test_la_seance_portee_se_lit_a_la_majorite():
    """Pas au premier titre venu : quelques valeurs ne cotent pas chaque jour.

    Relevé le 16/09 sur le fichier réel : 57 titres au 16, 15 au 15, 2 au 14.
    """
    d = fichier(f"{AUJ}T11:26:00+0100", AUJ,
                {"A": HIER, "B": HIER, "C": "2026-09-14"})
    assert d["tickers"][0]["_meta"]["prix_asof"] != AUJ, (
        "le jeu d'essai ne met pas de retardataire en tête : il ne pourrait "
        "pas distinguer une lecture à la majorité d'une lecture au premier venu")
    assert seance_portee(d) == AUJ
    assert seance_portee({"tickers": []}) is None


# ── Le workflow appelle-t-il bien cette porte ? ──────────────────────────────

@pytest.fixture(scope="module")
def workflow():
    f = RACINE / ".github" / "workflows" / "update_bvc.yml"
    if not f.exists():
        pytest.skip("update_bvc.yml absent")
    return yaml.safe_load(f.read_text(encoding="utf-8")), f.read_text(encoding="utf-8")


def test_le_cron_de_rattrapage_delegue_sa_decision(workflow):
    """La décision n'est plus quarante lignes de shell que personne n'éprouve."""
    _, brut = workflow
    assert "pipeline/porte_rattrapage.py" in brut, (
        "le workflow ne consulte pas la porte testée ici")


def test_le_depot_est_present_avant_la_porte(workflow):
    """⚠️ La porte lit `data.json` et importe un module : elle ne peut pas
    s'exécuter sur un runner vide.

    C'est la classe de défauts des 18 runs rouges du 15/09 — des étapes qui se
    prononçaient sur un dépôt absent. Le checkout passe devant, sans condition.
    """
    conf, _ = workflow
    etapes = conf["jobs"]["update-bvc-data"]["steps"]
    noms = [(e.get("name") or e.get("uses") or "") for e in etapes]
    i_checkout = next(i for i, n in enumerate(noms) if "Checkout" in n)
    i_porte = next(i for i, n in enumerate(noms) if "session BVC" in n)
    assert i_checkout < i_porte, f"la porte précède le checkout : {noms[:3]}"
    assert not etapes[i_checkout].get("if"), (
        "le checkout est conditionné — il doit être inconditionnel, sans quoi "
        "la porte retrouve un dépôt absent")
