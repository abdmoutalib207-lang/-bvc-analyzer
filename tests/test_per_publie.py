"""La valorisation lit le PER sur douze mois publié — 01/10/2026.

Décision d'Abd Moutalib (R8), après mesure de trois options. Audit externe
de la fiche ADI : `forward_per` saisi 12,5 quand les comptes donnent 19,4.
Attendus calculés À LA MAIN sur la grille de `compute_fond_score` :
valorisation 7,0 pour un PER ≤ 17, 5,5 pour ≤ 25 ; poids 0,20.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pipeline.smart_money import fond_score as F  # noqa: E402

FICHE = {"X": {"roic": 15, "wacc": 10, "croissance_bpa": 0, "croissance_ca": 0,
               "forward_per": 12.5, "dette_nette_ebitda": 1.0, "cash_conversion": 90,
               "secteur": "Immobilier"}}


def test_le_per_publie_remplace_le_forward_saisi():
    # 12,5 → v 7,0 ; 19,4 → v 5,5 : (7,0 − 5,5) × 0,20 = 0,30
    sans = F.compute_fond_score("X", FICHE)
    avec = F.compute_fond_score("X", FICHE, per_publie=19.4)
    assert round(sans - avec, 2) == 0.3


def test_sans_per_publie_la_saisie_reste_lue():
    # Société en perte : `_per` rend None — rien ne change.
    assert F.compute_fond_score("X", FICHE, per_publie=None) == F.compute_fond_score("X", FICHE)
    assert F.compute_fond_score("X", FICHE, per_publie=0) == F.compute_fond_score("X", FICHE)
    assert F.compute_fond_score("X", FICHE, per_publie=-3.0) == F.compute_fond_score("X", FICHE)


def test_un_per_publie_aberrant_est_lu_tel_quel():
    # RDS : PER 12 mois ≈ 250 sur un bénéfice minuscule — c'est un fait, il
    # tombe dans la dernière case (1,5), comme le forward de 1 634 saisi.
    assert F.compute_fond_score("X", FICHE, per_publie=250) == F.compute_fond_score(
        "X", {"X": dict(FICHE["X"], forward_per=1634.59)})


def test_le_moteur_passe_le_per_douze_mois():
    src = (Path(__file__).resolve().parent.parent / "update_data.py").read_text(encoding="utf-8")
    assert 'score_fond = _cfs(ticker, per_publie=_per_12m)' in src
    assert '_per_12m = _per(price, (BPA_DATA.get(ticker) or {}).get("bpa_12m"))' in src


def test_une_perte_n_affiche_pas_le_per_de_la_table():
    """LES : BPA 12 mois −1,85, et `data.json` affichait le PER figé 16,5."""
    src = (Path(__file__).resolve().parent.parent / "update_data.py").read_text(encoding="utf-8")
    assert '.get("bpa")) or fd.get("pe")' not in src
    assert 'if (BPA_DATA.get(ticker) or {}).get("bpa_12m") is not None else' in src
