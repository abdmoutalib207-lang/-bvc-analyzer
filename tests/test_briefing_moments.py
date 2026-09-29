"""Les briefings de mi-journée et de clôture — ajoutés le 29/09/2026.

Demandés par Abd Moutalib. `briefing.json` est réécrit à chaque passage : il
ne garde la trace d'aucun moment. Chaque moment a donc son fichier, écrit
seulement quand le passage tombe dans sa fenêtre.

Les attendus sont écrits À LA MAIN, passage par passage — pas recalculés avec
la fonction testée.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

from pipeline.briefing import dater, ecrire_moment, moment  # noqa: E402

AUJ = "2026-09-30"
VEILLE = "2026-09-29"

# (séance portée, heure du passage, moment attendu)
PASSAGES = [
    (AUJ, 945, None),            # ouverture : ni mi-journée ni clôture
    (AUJ, 1145, None),
    (AUJ, 1245, "mi_journee"),   # premier passage de mi-journée
    (AUJ, 1345, "mi_journee"),   # le remplace
    (AUJ, 1445, None),           # ⚠️ ne touche PLUS la mi-journée
    (AUJ, 1545, "cloture"),      # le run qui fixe le cours
    (AUJ, 1845, "cloture"),      # le filet la corrige
    (VEILLE, 900, "cloture"),    # avant l'ouverture : la veille est close
    (VEILLE, 1245, "cloture"),   # jour férié : la dernière séance est close
]


@pytest.mark.parametrize("seance,hhmm,attendu", PASSAGES)
def test_chaque_passage_ecrit_le_bon_moment(seance, hhmm, attendu):
    assert moment(seance, AUJ, hhmm) == attendu


def test_sans_seance_aucun_moment():
    assert moment("", AUJ, 1545) is None


def _b(seance):
    return {"seance": seance, "constats": ["x"], "non_mesurable": ["causes"]}


def test_une_lecture_en_seance_dit_qu_elle_est_partielle():
    b = dater(_b(AUJ), AUJ, 1345)
    assert b["moment"] == "mi_journee"
    assert b["ecrit_a"] == "2026-09-30 13:45"
    assert "13h45" in b["non_mesurable"][0] and "partiels" in b["non_mesurable"][0]


def test_une_lecture_de_cloture_ne_se_dit_pas_partielle():
    b = dater(_b(AUJ), AUJ, 1845)
    assert b["moment"] == "cloture"
    assert not any("partiels" in x for x in b["non_mesurable"])


def test_chaque_moment_a_son_fichier(tmp_path):
    ecrire_moment(dater(_b(AUJ), AUJ, 1345), tmp_path)
    ecrire_moment(dater(_b(AUJ), AUJ, 1545), tmp_path)
    assert json.loads((tmp_path / "briefing_mijournee.json").read_text())["moment"] == "mi_journee"
    assert json.loads((tmp_path / "briefing_cloture.json").read_text())["moment"] == "cloture"


def test_un_passage_hors_fenetre_n_ecrase_aucun_moment(tmp_path):
    """⚠️ Le cas qui justifie la borne de 14h : le passage de 14h45 ne doit
    pas remplacer la lecture de mi-journée."""
    ecrire_moment(dater(_b(AUJ), AUJ, 1345), tmp_path)
    assert ecrire_moment(dater(_b(AUJ), AUJ, 1445), tmp_path) is None
    assert "13:45" in json.loads(
        (tmp_path / "briefing_mijournee.json").read_text())["ecrit_a"]


def test_le_terminal_lit_les_deux_fichiers():
    ecran = (RACINE / "terminal.src.html").read_text(encoding="utf-8")
    for f in ("briefing_mijournee.json", "briefing_cloture.json"):
        assert f'fetch("{f}' in ecran, f"le terminal ne lit pas {f}"


def test_les_actualites_sont_collectees_avant_le_moteur():
    """⚠️ Le briefing lit news.json : collectées APRÈS le moteur, les
    actualités ne serviraient qu'au passage suivant."""
    lignes = [l.strip() for l in (RACINE / ".github/workflows/update_bvc.yml")
              .read_text(encoding="utf-8").splitlines()
              if not l.strip().startswith("#")]
    collecte = next(i for i, l in enumerate(lignes) if "pipeline/fetch_news.py" in l)
    moteur = next(i for i, l in enumerate(lignes) if l == "run: python update_data.py")
    assert collecte < moteur
