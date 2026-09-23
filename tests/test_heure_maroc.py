#!/usr/bin/env python3
"""Le décalage horaire du Maroc est un fait déclaré, pas une constante.

⚠️ CE QUE L'ERREUR A COÛTÉ, LE 23/09/2026
─────────────────────────────────────────
Le Maroc a changé d'heure le DIMANCHE 20/09 À MINUIT et est passé à UTC+0.
La base de fuseaux du conteneur, figée en avril 2025, l'ignorait. Pendant
trois séances, tout le raisonnement horaire du projet était faux d'une heure :

  — le cron « 45 14 », présenté comme le run de 15h45 qui fixe le cours,
    tombait à 14h45 locales : QUARANTE-CINQ MINUTES AVANT la clôture ;
  — le contrôle d'horodatage plaçait la clôture une heure trop tôt et aurait
    accepté un fichier qui ne la contenait pas ;
  — `data.json` s'annonçait « 16h08+01:00 » pour un run de 15h08 locales.

⚠️ ET L'AVERTISSEMENT AVAIT ÉTÉ DONNÉ LA VEILLE. Deux tests passaient en local
et échouaient en intégration, avec exactement une heure d'écart. J'en ai conclu
que le runner GitHub avait une base périmée et j'ai FORCÉ UTC+1 en dur.
C'était l'inverse : le runner était à jour, et j'ai inscrit l'erreur dans le
code. C'est Abd Moutalib, depuis Casablanca, qui l'a vue — « il est 15h09 ».

La règle : un décalage horaire est décrété par un État. Il se constate sur
pièce et se déclare, comme un split ou une suspension (R11).
"""

from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
import yaml

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))
sys.path.insert(0, str(RACINE / "pipeline"))

from bvc_config import DECALAGES_MAROC, decalage_maroc  # noqa: E402


# ── Le registre ────────────────────────────────────────────────────────────

def test_le_changement_du_20_septembre_est_declare():
    """⚠️ LE FAIT CENTRAL, constaté sur place."""
    assert decalage_maroc("2026-09-19") == 1, "avant le changement : UTC+1"
    assert decalage_maroc("2026-09-20") == 0, "le jour du changement : UTC+0"
    assert decalage_maroc("2026-09-23") == 0


def test_le_ramadan_est_declare_lui_aussi():
    """Le Maroc revient à UTC+0 pendant le Ramadan. Sans cette entrée, le
    projet aurait la même panne chaque année."""
    assert decalage_maroc("2026-02-10") == 0
    assert decalage_maroc("2026-04-01") == 1


def test_les_entrees_sont_triees_et_plausibles():
    dates = [e["depuis"] for e in DECALAGES_MAROC]
    assert dates == sorted(dates), "registre non trié : la lecture serait fausse"
    for e in DECALAGES_MAROC:
        assert e["offset"] in (0, 1), f"{e}: le Maroc n'a que deux décalages"
        assert e.get("source"), f"{e}: un fait déclaré sans source n'est pas un fait"


def test_une_date_anterieure_au_registre_ne_leve_pas():
    assert decalage_maroc("1999-01-01") in (0, 1)


# ── Ce qui ne doit plus jamais être écrit en dur ───────────────────────────

@pytest.mark.parametrize("fichier", [
    "pipeline/verifier_seance.py", "update_data.py",
])
def test_aucun_decalage_ecrit_en_dur(fichier):
    """⚠️ `timezone(timedelta(hours=1))` et `ZoneInfo('Africa/Casablanca')`
    sont tous deux faux : le premier ignore les décrets, le second dépend
    d'une base dont on ne maîtrise pas la fraîcheur."""
    # ⚠️ On retire commentaires ET docstrings par l'AST : ma première version
    # filtrait les lignes commençant par `#` et rougissait sur la CITATION du
    # motif dans un docstring explicatif. Un test qui accuse une explication
    # n'accuse rien.
    import ast, io, tokenize
    src = (RACINE / fichier).read_text(encoding="utf-8")
    arbre = ast.parse(src)
    docstrings = set()
    for n in ast.walk(arbre):
        if isinstance(n, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            d = ast.get_docstring(n, clean=False)
            if d:
                docstrings.add(d)
    sans_com = []
    for tok in tokenize.generate_tokens(io.StringIO(src).readline):
        if tok.type == tokenize.COMMENT:
            continue
        if tok.type == tokenize.STRING:
            try:
                if ast.literal_eval(tok.string) in docstrings:
                    continue
            except Exception:
                pass
        sans_com.append(tok.string)
    code = " ".join(sans_com)
    assert "timezone(timedelta(hours=1))" not in code, (
        f"{fichier} fige le décalage — il doit venir de `decalage_maroc()`")
    assert "ZoneInfo('Africa/Casablanca')" not in code, (
        f"{fichier} interroge la base système — elle peut être périmée")


# ── Les crons ──────────────────────────────────────────────────────────────

def _crons():
    d = yaml.safe_load((RACINE / ".github/workflows/update_bvc.yml")
                       .read_text(encoding="utf-8"))
    return [c["cron"] for c in (d.get("on") or d.get(True))["schedule"]]


def test_le_run_de_cloture_tombe_apres_la_cloture():
    """⚠️ LE DÉFAUT LE PLUS GRAVE. Le run censé fixer le cours définitif
    tombait 45 minutes AVANT la clôture de 15h30, ce qui fige la séance en vol
    — exactement l'incident du 21/09."""
    aujourdhui = datetime.now(timezone.utc).date().isoformat()
    offset = decalage_maroc(aujourdhui)
    principaux = [c for c in _crons() if "," not in c.split()[0]]
    heures = sorted((int(c.split()[1]) + offset, int(c.split()[0])) for c in principaux)
    apres = [(h, m) for h, m in heures if (h, m) > (15, 30)]
    assert apres, (
        f"aucun cron ne tombe après la clôture de 15h30 locale "
        f"(décalage UTC+{offset}) : {heures}")


def test_la_redondance_couvre_les_deux_decalages_possibles():
    """⚠️ Un cron GitHub est en UTC fixe : il ne peut pas suivre un décret.
    La fenêtre de rattrapage doit donc englober la séance que le Maroc soit à
    UTC+0 ou à UTC+1, sans quoi elle dérive d'une heure à chaque changement."""
    redondance = [c for c in _crons() if "," in c.split()[0]]
    assert redondance, "aucun cron de rattrapage"
    champ = redondance[0].split()[1]
    a, b = champ.split("-")
    for offset in (0, 1):
        debut, fin = int(a) + offset, int(b) + offset
        assert debut <= 9, f"UTC+{offset} : le rattrapage démarre à {debut}h, après l'ouverture de 9h30"
        assert fin >= 16, f"UTC+{offset} : le rattrapage s'arrête à {fin}h, avant la clôture de 15h30"
