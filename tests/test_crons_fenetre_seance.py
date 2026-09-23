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

import yaml

RACINE = Path(__file__).resolve().parent.parent
WF = RACINE / ".github" / "workflows" / "update_bvc.yml"

# Casablanca = UTC+1. Séance : 9h30–15h30, donc 08:30–14:30 UTC.
# La fenêtre autorisée va de l'ouverture au filet du soir : 08:00–18:00 UTC.
PREMIERE_HEURE_UTC = 8
DERNIERE_HEURE_UTC = 17


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
        hors = sorted(x for x in h
                      if not PREMIERE_HEURE_UTC <= x <= DERNIERE_HEURE_UTC)
        if hors:
            fautifs.append((cron, [f"{(x+1) % 24:02d}h Casa" for x in hors]))
    assert not fautifs, f"cron(s) hors fenêtre de séance : {fautifs}"


def test_les_crons_ne_courent_que_les_jours_ouvres():
    for cron in _crons():
        assert cron.split()[4] == "1-5", f"{cron} : la BVC ne cote pas le week-end"


def test_la_redondance_couvre_toute_la_fenetre():
    """Le remède au retard de GitHub n'est pas d'avancer les heures — ça
    décalerait le problème — mais de multiplier les occasions dans la fenêtre
    utile. Encore faut-il qu'elles la couvrent."""
    couvertes: set[int] = set()
    for cron in _crons():
        couvertes |= _heures(cron.split()[1])
    attendues = set(range(PREMIERE_HEURE_UTC, DERNIERE_HEURE_UTC + 1))
    assert attendues <= couvertes, (
        f"heures de séance sans aucun cron : "
        f"{sorted((x+1) % 24 for x in attendues - couvertes)} Casa")


def test_les_quatre_passages_qui_portent_la_promesse_subsistent():
    """Ouverture, mi-séance, clôture, filet. Le run de 15h45 est celui qui
    fixe le cours définitif."""
    crons = _crons()
    for attendu in ("40 8 * * 1-5", "0 11 * * 1-5",
                    "45 14 * * 1-5", "0 17 * * 1-5"):
        assert attendu in crons, f"passage manquant : {attendu}"


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
    principaux = {"40 8 * * 1-5", "0 11 * * 1-5", "45 14 * * 1-5", "0 17 * * 1-5"}
    for cron in _crons():
        if cron in principaux:
            continue
        minute = cron.split()[0]
        assert minute.startswith(("25", "55")), (
            f"{cron} : minute non reconnue par le gate, ce run publierait "
            f"sans passer par la porte de rattrapage")
