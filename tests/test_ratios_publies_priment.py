"""Les ratios calculés sur comptes publiés priment sur la saisie — 01/10/2026.

Décision d'Abd Moutalib (R8) : « rectifier les anciens calculs faux grâce aux
publications ». Les attendus sont calculés À LA MAIN sur la grille de
`compute_fond_score`, pas en rappelant la fonction :

    note = qualité×0,40 + croissance×0,30 + valorisation×0,20 + bilan×0,10

Fiche de base : croissance nulle (g = 4,5), PER 15 (v = 7,0), WACC 10.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pipeline.smart_money import fond_score as F  # noqa: E402

BASE = {"wacc": 10, "croissance_bpa": 0, "croissance_ca": 0, "forward_per": 15,
        "secteur": "Industrie"}


def _fiche(**champs):
    return dict(BASE, **champs)


def test_sans_ratio_publie_la_saisie_est_lue():
    # ROIC saisi 30 → écart au WACC 20 → q 9,5 ; saisi 11 → écart 1 → q 5,0.
    # Tout le reste égal, seule la qualité bouge : (9,5 − 5,0) × 0,40 = 1,8.
    f = {"X": _fiche(roic=30, dette_nette_ebitda=0.5, cash_conversion=90)}
    f2 = {"X": _fiche(roic=11, dette_nette_ebitda=0.5, cash_conversion=90)}
    assert round(F.compute_fond_score("X", f) - F.compute_fond_score("X", f2), 2) == 1.8


def test_le_roic_publie_remplace_le_roic_saisi():
    # Saisi 30 (q 9,5), publié 11 (q 5,0) : la note doit être celle du 11.
    saisi = {"X": _fiche(roic=30, dette_nette_ebitda=0.5, cash_conversion=90)}
    publie = {"X": _fiche(roic=30, dette_nette_ebitda=0.5, cash_conversion=90,
                          ratios_publies={"roic": {"valeur": 11.0}})}
    assert round(F.compute_fond_score("X", saisi)
                 - F.compute_fond_score("X", publie), 2) == 1.8


def test_la_valeur_saisie_reste_lue_faute_de_ratio_numerique():
    # « sans objet » ou une entrée sans valeur n'est pas une mesure.
    a = {"X": _fiche(roic=30, ratios_publies={"roic": {"valeur": None}})}
    b = {"X": _fiche(roic=30, ratios_publies={"roic": "sans objet"})}
    c = {"X": _fiche(roic=30)}
    assert F.compute_fond_score("X", a) == F.compute_fond_score("X", c)
    assert F.compute_fond_score("X", b) == F.compute_fond_score("X", c)


def test_msa_garde_sa_saisie_jusqu_au_recoupement():
    assert "MSA" in F.RATIOS_EN_VERIFICATION
    f = {"MSA": _fiche(roic=11, ratios_publies={"roic": {"valeur": 47.6}})}
    g = {"MSA": _fiche(roic=11)}
    assert F.compute_fond_score("MSA", f) == F.compute_fond_score("MSA", g)


def test_la_saisie_n_est_pas_effacee():
    f = {"X": _fiche(roic=30, ratios_publies={"roic": {"valeur": 11.0}})}
    F.compute_fond_score("X", f)
    assert f["X"]["roic"] == 30


def test_le_fichier_publie_pour_un_cas_reel():
    # OUL au 01/10 : ROIC saisi en juin, ROIC calculé sur comptes 2025 présent.
    # On ne fige pas la note (elle suivra les publications), seulement le
    # sens : la note lit bien la valeur publiée.
    fond = F.reload()
    rp = (fond.get("OUL") or {}).get("ratios_publies") or {}
    if not isinstance(rp.get("roic"), dict):
        return
    saisi = dict(fond["OUL"])
    saisi.pop("ratios_publies")
    saisi["roic"] = rp["roic"]["valeur"]
    for k in ("dette_nette_ebitda", "cash_conversion"):
        if isinstance(rp.get(k), dict) and rp[k].get("valeur") is not None:
            saisi[k] = rp[k]["valeur"]
    assert F.compute_fond_score("OUL", fond) == F.compute_fond_score("OUL", {"OUL": saisi})
