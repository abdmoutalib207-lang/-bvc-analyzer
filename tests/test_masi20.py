#!/usr/bin/env python3
"""Le MASI 20, et les deux pièges qu'il a fait apparaître.

⚠️ PIÈGE 1 — UN CODE INCONNU N'ÉCHOUE PAS
Interrogé le 25/09/2026, le fournisseur répond à `MASI20` par une charge utile
**valide dont tous les champs sont des chaînes vides**. Pas d'erreur, pas de
`Valid=false` : un indice silencieusement creux.

    `MASI`   → Libelle « MASI »       ✅
    `MASI20` → ('', '', '')           ⚠️  la devinette plausible
    `MSI20`  → Libelle « MASI 20 »    ✅  le vrai code

Et le champ `ISIN` de la réponse vaut « MASI20 » alors que le paramètre qui
l'atteint est « MSI20 » : deux graphies dans la même charge utile.

L'identité a été confirmée par l'ARITHMÉTIQUE, pas par le code — le
`CoursVeille` de MSI20 vaut 1 294,1574, exactement la clôture du MASI 20 au
24/09 publiée par ailleurs. C'est la même méthode que pour `MRL`.

⚠️ PIÈGE 2 — DEUX SÉANCES AFFICHÉES COMME UNE SEULE
Dès le premier relevé, le fournisseur servait le MASI 20 du **25/09** alors que
les cours publiés portaient le **24/09**. Les mettre côte à côte sans le dire,
c'est le défaut du 14/08 (séance fantôme) et du 28/08 (source qui recule).
"""

from __future__ import annotations

import ast
import json
import sys
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))
sys.path.insert(0, str(RACINE / "pipeline"))

SOURCE = (RACINE / "update_data.py").read_text(encoding="utf-8")
ECRAN = (RACINE / "index.html").read_text(encoding="utf-8")


# ── ⚠️ Le code du fournisseur, jamais deviné ───────────────────────────────

def test_le_code_interroge_est_MSI20_et_non_MASI20():
    """⚠️ LE TEST QUI EMPÊCHE LA DEVINETTE DE REVENIR.

    « MASI20 » est le nom que tout le monde écrirait. Il renvoie des chaînes
    vides sans lever d'erreur : le défaut serait muet et permanent.

    Lu par l'AST sur l'appel réel, pas à la ligne — le fichier CITE « MASI20 »
    dans ses commentaires pour expliquer pourquoi ce n'est pas lui.
    """
    arbre = ast.parse(SOURCE)
    codes = set()
    for n in ast.walk(arbre):
        if (isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
                and n.func.id == "_ligne_indice_cdg" and n.args):
            a = n.args[0]
            if isinstance(a, ast.Constant):
                codes.add(a.value)
    assert "MSI20" in codes, (
        "le moteur n'interroge pas le MASI 20 sous le code du fournisseur")
    assert "MASI20" not in codes, (
        "« MASI20 » renvoie une charge utile VIDE sans erreur — le code du "
        "fournisseur est « MSI20 »")


def test_une_charge_utile_creuse_est_refusee_et_signalee():
    """⚠️ La signature d'un code inconnu est `Cours` VIDE, pas absent. Un
    test de présence de clé ne l'attraperait pas."""
    i = SOURCE.find("def _ligne_indice_cdg")
    bloc = SOURCE[i:i + 3000]
    assert 'not ligne.get("Cours")' in bloc, (
        "un code inconnu produirait un indice creux publié comme valide")
    assert "creuse" in bloc, (
        "le refus doit être journalisé — sinon l'indice disparaît en silence")


# ── ⚠️ Le YTD du MASI 20 suit la même règle que celui du MASI ──────────────

def test_le_ytd_du_masi20_est_recalcule_et_non_recopie():
    """Le champ `VariationAnneeP` décrit `CoursVeille`. La preuve vaut pour
    les deux indices :

        MASI 20 : 1485,6472 + (−191,4898) = 1294,1574 = CoursVeille
        MASI    : 18846,3502 + (−977,2931) = 17869,0571 = CoursVeille
    """
    from marche_history import extraire
    e = extraire({"Cours": 1292.0266, "CoursVeille": 1294.1574,
                  "VariationAnneeP": -12.89, "VariationAnneeV": -191.4898,
                  "CoursPremiereCotation": 1485.6472})
    # attendu à la main : 1292,0266 / 1485,6472 − 1 = −13,03 %
    assert e["ytd_pct"] == -13.03
    assert e["ytd_pct_source_veille"] == -12.89


# ── ⚠️ Deux séances ne s'affichent pas comme une seule ─────────────────────

def test_le_masi20_porte_sa_propre_date():
    """Sans sa date, impossible de savoir qu'il décrit une autre séance."""
    i = SOURCE.find("def fetch_masi20")
    bloc = SOURCE[i:i + 2500]
    assert '"asof"' in bloc, "le MASI 20 est publié sans sa séance"


def test_le_terminal_signale_un_masi20_d_une_autre_seance():
    """⚠️ Le cas s'est présenté au PREMIER relevé : fournisseur au 25/09,
    cours publiés au 24/09. On n'aligne pas les dates, on les DIT."""
    i = ECRAN.find("masi.masi20.asof")
    assert i > 0, "le terminal ne lit pas la date du MASI 20"
    bloc = ECRAN[max(0, i - 600):i + 600]
    assert "masi.masi20.asof!==masi.asof" in bloc, (
        "deux séances seraient affichées comme une seule")


def test_le_masi20_ne_remplace_pas_le_masi():
    """⚠️ Il se lit À CÔTÉ. L'indice de référence reste le MASI ; le MASI 20
    ne couvre que vingt valeurs sur quatre-vingts."""
    assert "masi.value" in ECRAN or "masi.chg" in ECRAN
    i = ECRAN.find("MASI&nbsp;20")
    assert i > 0, "le MASI 20 n'est pas étiqueté à l'écran"


def test_son_absence_ne_casse_rien():
    """⚠️ Complément de lecture, pas dépendance : le bulletin se publie sans
    lui. Le composant ne doit rien rendre plutôt que planter."""
    assert "masi.masi20&&masi.masi20.value!=null&&" in ECRAN


# ── Le flux publié ─────────────────────────────────────────────────────────

def test_le_flux_publie_le_masi20_avec_son_libelle(
):
    f = RACINE / "data.json"
    if not f.exists():
        pytest.skip("data.json absent de ce clone")
    m = json.loads(f.read_text(encoding="utf-8")).get("masi20")
    if m is None:
        pytest.skip("MASI 20 non collecté sur ce run — son absence est permise")
    assert m.get("libelle") == "MASI 20", (
        f"le fournisseur a renvoyé « {m.get('libelle')} » — l'identité du code "
        f"a-t-elle changé ?")
    assert m.get("value") and m["value"] > 0
    assert m.get("asof"), "un indice sans séance ne peut pas être arbitré"


def test_l_ecart_avec_le_masi_est_calculable():
    """⚠️ C'est la raison d'être du second indice : au 25/09, −13,0 % contre
    −5,2 % sur l'année. Sans les deux, l'écart ne se voit pas."""
    f = RACINE / "data.json"
    if not f.exists():
        pytest.skip("data.json absent de ce clone")
    d = json.loads(f.read_text(encoding="utf-8"))
    m20, masi = d.get("masi20"), d.get("masi") or {}
    if not m20 or m20.get("ytd_pct") is None or masi.get("ytd_pct") is None:
        pytest.skip("les deux YTD ne sont pas disponibles sur ce run")
    assert isinstance(m20["ytd_pct"] - masi["ytd_pct"], float)
