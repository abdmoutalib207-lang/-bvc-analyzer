"""Une seule horloge : le registre `DECALAGES_MAROC`.

L'audit indépendant du 26/09 l'a relevé : la porte de rattrapage lisait
`ZoneInfo("Africa/Casablanca")`, la garde du workflow `TZ=Africa/Casablanca
date`, et le reste du moteur le registre. Depuis le 20/09 les deux premières
répondaient UTC+1 et le registre UTC+0 : la porte comparait un `updated` écrit
à l'heure du registre avec une montre en avance d'une heure.

Les attendus ci-dessous sont écrits À LA MAIN, heure par heure — pas recalculés
avec la fonction testée.
"""

from __future__ import annotations

import ast
import sys
from datetime import datetime, timezone
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

from bvc_config import heure_maroc  # noqa: E402


def test_avant_le_changement_du_20_09_le_maroc_est_a_utc_plus_1():
    h = heure_maroc(datetime(2026, 9, 19, 14, 30, tzinfo=timezone.utc))
    assert (h.hour, h.minute) == (15, 30)
    assert h.utcoffset().total_seconds() == 3600


def test_depuis_le_20_09_le_maroc_est_a_utc():
    h = heure_maroc(datetime(2026, 9, 29, 14, 30, tzinfo=timezone.utc))
    assert (h.hour, h.minute) == (14, 30)
    assert h.utcoffset().total_seconds() == 0


def test_la_date_suit_l_heure_locale():
    """23h30 UTC le 19/09 est déjà le 20/09 à Casablanca (UTC+1 ce jour-là)."""
    h = heure_maroc(datetime(2026, 9, 19, 23, 30, tzinfo=timezone.utc))
    assert h.date().isoformat() == "2026-09-20"


def _noms(fichier: Path) -> set[str]:
    arbre = ast.parse(fichier.read_text(encoding="utf-8"))
    return {n.id for n in ast.walk(arbre) if isinstance(n, ast.Name)} | {
        a.name for n in ast.walk(arbre) if isinstance(n, ast.ImportFrom) for a in n.names}


def test_la_porte_et_la_seance_source_lisent_le_registre():
    """Par l'arbre syntaxique : les docstrings citent ZoneInfo."""
    for rel in ("pipeline/porte_rattrapage.py", "pipeline/seance_source.py"):
        noms = _noms(RACINE / rel)
        assert "ZoneInfo" not in noms, f"{rel} lit encore la base de fuseaux du système"
        assert "heure_maroc" in noms, f"{rel} ne lit pas l'horloge du registre"


def test_la_garde_du_workflow_lit_le_registre():
    """Seules les lignes de commande comptent — pas les commentaires."""
    lignes = [l.strip() for l in (RACINE / ".github/workflows/update_bvc.yml")
              .read_text(encoding="utf-8").splitlines() if not l.strip().startswith("#")]
    for var in ("NOW=", "DAY=", "HEURE="):
        cmd = [l for l in lignes if l.startswith(var)]
        assert cmd, f"{var} introuvable dans update_bvc.yml"
        for l in cmd:
            assert "TZ=" not in l and "heure_maroc" in l, l
