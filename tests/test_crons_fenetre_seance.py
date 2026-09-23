#!/usr/bin/env python3
"""Le moteur tourne pendant la séance, et seulement pendant la séance.

⚠️ CONSTAT DU 23/09/2026, VÉRIFIÉ
─────────────────────────────────
Entre 19h et 01h46 Casablanca, SEPT runs se sont déclenchés — la Bourse était
fermée. Puis plus rien de 07h09 à 12h32, alors que la séance était ouverte
depuis trois heures.

Deux causes cumulées :
  1. le cron de rattrapage était `25 * * * 1-5`, soit TOUTES LES HEURES, NUIT
     COMPRISE. La porte écartait ces runs, mais ils partaient quand même ;
  2. deux crons de « redondance du soir » à 20h et 22h Casablanca, posés
     contre les retards de GitHub — mais là où rien ne peut être collecté.

La redondance n'était pas absente : elle était AU MAUVAIS ENDROIT.
"""

from __future__ import annotations

from pathlib import Path

import sys

import yaml

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))
from bvc_config import decalage_maroc  # noqa: E402
WF = RACINE / ".github" / "workflows" / "update_bvc.yml"

# ⚠️ EN HEURES LOCALES, PAS EN UTC.
#
# La première version de ce fichier fixait « 8h–17h UTC » en dur, en supposant
# Casablanca à UTC+1. Le Maroc est passé à UTC+0 le 20/09/2026 et ces bornes
# sont devenues fausses — les tests ont rougi alors que les crons venaient
# d'être CORRIGÉS. Un test calé sur un décalage périmé accuse le correctif.
#
# La règle vraie porte sur l'heure LOCALE : le moteur travaille entre
# l'ouverture (9h30) et le filet du soir (18h), jamais la nuit.
PREMIERE_HEURE_LOCALE = 8
DERNIERE_HEURE_LOCALE = 19


def _offset():
    from datetime import datetime, timezone
    return decalage_maroc(datetime.now(timezone.utc).date().isoformat())


def _crons():
    d = yaml.safe_load(WF.read_text(encoding="utf-8"))
    return [c["cron"] for c in (d.get("on") or d.get(True))["schedule"]]


def _heures(champ: str) -> set[int]:
    """Les heures UTC qu'un champ cron désigne."""
    if champ == "*":
        return set(range(24))
    heures: set[int] = set()
    for part in champ.split(","):
        if "-" in part:
            a, b = part.split("-")
            heures |= set(range(int(a), int(b) + 1))
        else:
            heures.add(int(part))
    return heures


def test_aucun_cron_ne_tourne_la_nuit():
    """⚠️ LE DÉFAUT CENTRAL. Hors séance il n'y a rien à collecter : un run
    nocturne ne peut que republier ce qu'on a déjà."""
    fautifs = []
    for cron in _crons():
        h = _heures(cron.split()[1])
        o = _offset()
        hors = sorted(x for x in h
                      if not PREMIERE_HEURE_LOCALE <= (x + o) % 24 <= DERNIERE_HEURE_LOCALE)
        if hors:
            fautifs.append((cron, [f"{(x+o) % 24:02d}h locales" for x in hors]))
    assert not fautifs, f"cron(s) hors fenêtre de séance : {fautifs}"


def test_les_crons_ne_courent_que_les_jours_ouvres():
    for cron in _crons():
        assert cron.split()[4] == "1-5", f"{cron} : la BVC ne cote pas le week-end"


def test_la_redondance_couvre_toute_la_fenetre():
    """Le remède au retard de GitHub n'est pas d'avancer les heures — ça
    décalerait le problème — mais de multiplier les occasions dans la fenêtre
    utile. Encore faut-il qu'elles la couvrent."""
    o = _offset()
    couvertes = {(x + o) % 24 for cron in _crons() for x in _heures(cron.split()[1])}
    # La séance court de 9h30 à 15h30 locales ; le filet va jusqu'à 18h.
    attendues = set(range(9, 19))
    assert attendues <= couvertes, (
        f"heures de séance sans aucun cron : "
        f"{sorted(attendues - couvertes)} locales")


def test_les_quatre_passages_qui_portent_la_promesse_subsistent():
    """Ouverture, mi-séance, clôture, filet. Le run de 15h45 est celui qui
    fixe le cours définitif."""
    o = _offset()
    principaux = [c for c in _crons() if "," not in c.split()[0]]
    locales = sorted(((int(c.split()[1]) + o) % 24, int(c.split()[0]))
                     for c in principaux)
    assert len(locales) >= 4, f"moins de quatre passages : {locales}"
    # ouverture (après 9h30), mi-séance, APRÈS la clôture de 15h30, filet du soir
    assert any((9, 30) < hm <= (10, 30) for hm in locales), f"ouverture absente : {locales}"
    assert any((11, 0) <= hm <= (13, 0) for hm in locales), f"mi-séance absente : {locales}"
    assert any((15, 30) < hm <= (16, 30) for hm in locales), (
        f"AUCUN passage après la clôture de 15h30 — c'est celui qui fixe le "
        f"cours définitif : {locales}")
    assert any(hm >= (17, 30) for hm in locales), f"filet du soir absent : {locales}"


def test_le_gate_reconnait_le_cron_de_rattrapage_par_sa_forme():
    """⚠️ Le gate testait une CHAÎNE EXACTE, `25 * * * 1-5`. En changeant le
    cron pour qu'il cesse de tourner la nuit, cette égalité aurait
    silencieusement cessé de le reconnaître — et les runs de rattrapage
    auraient contourné la porte pour publier toutes les demi-heures, soit
    exactement ce que la porte existe pour empêcher."""
    source = WF.read_text(encoding="utf-8")
    assert '"$CRON" = "25 * * * 1-5"' not in source, (
        "le gate compare encore une chaîne exacte de cron")
    assert "RATTRAPAGE=1" in source and "porte_rattrapage.py" in source


def test_chaque_cron_de_rattrapage_passe_par_la_porte():
    """Tout cron de redondance doit commencer par une minute que le gate
    reconnaît. Sinon il publierait sans filtre."""
    # ⚠️ Un cron principal se reconnaît à sa FORME — une minute unique — pas à
    # une liste de chaînes littérales. La première version en épinglait quatre
    # ; le recalage horaire du 23/09 les a toutes changées, et le test a rougi
    # sur des crons parfaitement corrects.
    for cron in _crons():
        if "," not in cron.split()[0]:
            continue
        minute = cron.split()[0]
        assert minute.startswith(("25", "55")), (
            f"{cron} : minute non reconnue par le gate, ce run publierait "
            f"sans passer par la porte de rattrapage")
