#!/usr/bin/env python3
"""Ce qu'un import a le droit de remplacer, et ce qu'il doit laisser.

⚠️ UN IMPORT QUI ÉCRASE TOUT EST UNE RÉGRESSION DÉGUISÉE EN CORRECTION
──────────────────────────────────────────────────────────────────────
L'export de l'opérateur fait foi **sur la période qu'il couvre**, et sur elle
seule. Trois zones, trois traitements — et c'est là que tout se joue :

  - AVANT sa première séance : nos bougies restent. TGCC a trois ans de plus
    que l'export ; un import qui « remplace la série » lui en ferait perdre
    448. Ce que l'export ne dit pas ne l'autorise pas à effacer.
  - PENDANT : l'export remplace, date pour date.
  - APRÈS sa dernière séance : nos bougies restent. C'est la séance du jour,
    que l'opérateur n'a pas encore publiée — l'écraser reviendrait à effacer
    chaque jour le travail du moteur.

⚠️ ET DEUX ABSENCES QUI NE VEULENT PAS DIRE LA MÊME CHOSE
Une date à nous absente de l'export DANS la période est une séance fantôme :
le marché n'a pas ouvert. Une date absente HORS période n'est rien du tout.
Confondre les deux, c'est soit garder des séances fictives, soit amputer la
série de sa profondeur.

⚠️ Aucun attendu n'est calculé par le code testé.
"""

from __future__ import annotations

import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))
sys.path.insert(0, str(RACINE / "pipeline"))

from importer_export_bvc import bougie_depuis_export, fusionner  # noqa: E402


def _b(d, c, v=0, o=None, h=None, l=None):
    return {"d": d, "o": o if o is not None else c, "h": h if h is not None else c,
            "l": l if l is not None else c, "c": c, "v": v}


def _ligne(cours, ouverture=None, haut=None, bas=None, titres="-", mad="-"):
    return {"Ouverture": ouverture if ouverture is not None else cours,
            "Dernier Cours": cours,
            "Plus Haut": haut if haut is not None else cours,
            "Plus Bas": bas if bas is not None else cours,
            "Titres Échangés": titres, "Volume (MAD)": mad}


# ── La bougie lue dans l'export ────────────────────────────────────────────

def test_le_volume_vient_des_titres_echanges():
    """⚠️ Et jamais du montant en dirhams, qui est sur la ligne d'à côté."""
    b = bougie_depuis_export("2026-09-22",
                             _ligne("691.00", titres="33778",
                                    mad="23343966.70"))
    assert b["v"] == 33778


def test_une_seance_sans_echange_garde_un_volume_nul():
    """⚠️ Elle est CONSERVÉE : le marché était ouvert, le titre n'a pas traité.
    C'est une information, pas un trou. Et son volume vaut 0, jamais le
    cours — le défaut que cet import répare."""
    b = bougie_depuis_export("2023-09-25", _ligne("700.00"))
    assert b is not None
    assert b["v"] == 0
    assert b["c"] == 700.0


def test_une_seance_sans_cours_est_incotable():
    assert bougie_depuis_export("2023-09-25", _ligne("-")) is None
    assert bougie_depuis_export("2023-09-25", _ligne("0.00")) is None


def test_les_extremes_manquants_donnent_une_bougie_plate():
    b = bougie_depuis_export("2023-09-25", _ligne("700.00"))
    assert b["o"] == b["h"] == b["l"] == b["c"] == 700.0


def test_l_invariant_ohlc_est_impose():
    """Un plus-haut inférieur à la clôture n'existe pas. L'export est sain sur
    ce point ; la garde reste pour le titre n°28."""
    b = bougie_depuis_export("2026-09-22",
                             _ligne("700.00", ouverture="690.00",
                                    haut="695.00", bas="705.00"))
    assert b["h"] >= max(b["o"], b["c"])
    assert b["l"] <= min(b["o"], b["c"])


# ── Les trois zones ────────────────────────────────────────────────────────

def test_nos_seances_anterieures_a_l_export_sont_conservees():
    """⚠️ TGCC a 1 180 bougies pour 734 dans l'export. Un import qui
    « remplace la série » lui en ferait perdre 448."""
    f = fusionner([_b("2020-01-02", 500.0), _b("2026-09-22", 700.0)],
                  [_b("2026-09-22", 710.0, 5)])
    assert [b["d"] for b in f["serie"]] == ["2020-01-02", "2026-09-22"]
    assert f["serie"][0]["c"] == 500.0, "la séance de 2020 doit être intacte"
    assert f["conservees_avant"] == 1


def test_la_seance_du_jour_est_conservee():
    """⚠️ L'export s'arrête la veille. Écraser ce qui suit effacerait chaque
    jour ce que le moteur vient d'écrire."""
    f = fusionner([_b("2026-09-22", 700.0), _b("2026-09-23", 705.0, 900)],
                  [_b("2026-09-22", 710.0, 5)])
    dernier = f["serie"][-1]
    assert dernier["d"] == "2026-09-23" and dernier["c"] == 705.0
    assert f["conservees_apres"] == 1


def test_l_export_remplace_dans_sa_periode():
    f = fusionner([_b("2026-09-21", 690.0, 12), _b("2026-09-22", 700.0, 99)],
                  [_b("2026-09-21", 690.0, 12), _b("2026-09-22", 710.0, 5)])
    par = {b["d"]: b for b in f["serie"]}
    assert par["2026-09-22"]["c"] == 710.0 and par["2026-09-22"]["v"] == 5
    assert f["remplacees"] == ["2026-09-22"]
    assert "2026-09-21" not in f["remplacees"], "identique : pas un remplacement"


def test_une_seance_de_l_export_que_nous_n_avions_pas_est_ajoutee():
    f = fusionner([_b("2026-09-22", 700.0)],
                  [_b("2026-06-22", 650.0, 3), _b("2026-09-22", 700.0)])
    assert f["ajoutees"] == ["2026-06-22"]
    assert len(f["serie"]) == 2


# ── Les deux absences, qui ne disent pas la même chose ─────────────────────

def test_une_date_a_nous_dans_la_periode_est_une_seance_fantome():
    """⚠️ Le 30/07/2026 — Fête du Trône — sur les 27 titres. L'export liste
    toutes les séances réelles, y compris celles sans échange, et omet
    exactement les jours sans ouverture."""
    f = fusionner([_b("2026-07-29", 700.0), _b("2026-07-30", 700.0, 700),
                   _b("2026-07-31", 702.0)],
                  [_b("2026-07-29", 700.0), _b("2026-07-31", 702.0)])
    assert f["fantomes"] == ["2026-07-30"]
    assert "2026-07-30" not in {b["d"] for b in f["serie"]}


def test_une_date_a_nous_hors_periode_n_est_pas_un_fantome():
    """⚠️ La distinction qui protège la profondeur des séries. Sans elle,
    TGCC perdrait ses 448 séances d'avant 2023 en les traitant comme des
    jours de fermeture."""
    f = fusionner([_b("2020-01-02", 500.0), _b("2026-09-22", 700.0)],
                  [_b("2026-09-22", 700.0)])
    assert f["fantomes"] == []
    assert "2020-01-02" in {b["d"] for b in f["serie"]}


def test_un_export_vide_ne_touche_a_rien():
    """⚠️ Un import raté ne doit jamais valoir suppression. La série reste
    exactement ce qu'elle était."""
    anciennes = [_b("2026-09-22", 700.0), _b("2026-09-23", 705.0)]
    f = fusionner(anciennes, [])
    assert f["serie"] == anciennes
    assert f["fantomes"] == [] and f["remplacees"] == []


# ── La série rendue ────────────────────────────────────────────────────────

def test_la_serie_sort_triee_et_sans_doublon():
    f = fusionner([_b("2026-09-23", 705.0), _b("2020-01-02", 500.0)],
                  [_b("2026-09-22", 700.0), _b("2026-06-22", 650.0)])
    dates = [b["d"] for b in f["serie"]]
    assert dates == sorted(dates)
    assert len(dates) == len(set(dates))
