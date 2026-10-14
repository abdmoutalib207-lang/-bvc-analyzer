"""Les fichiers DÉRIVÉS doivent refléter leurs pièces.

⚠️ 14/10/2026 : neuf ROE 2025 (IAM, JET, LHM, PPM, REB, SBS, SNA, SRM, SMI)
étaient calculables depuis les fonds propres relevés sur pièce (#238), mais
`fondamentaux.json` n'avait pas été régénéré : `resultats_semestriels.py` et
`ratios_financiers.py` se lancent à la main, et rien ne disait qu'on les avait
oubliés. Même famille que le BPA de SMI (#247) : un chiffre juste dans la
pièce, faux ou absent dans ce qui est publié.

Ces tests rejouent les deux calculs EN MÉMOIRE sur les pièces du dépôt et
comparent au fichier publié. Une pièce modifiée sans régénération échoue ici.
Remède : `python pipeline/resultats_semestriels.py` (qui enchaîne les ratios).
"""
import copy
import json
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

from pipeline import ratios_financiers as rf  # noqa: E402
from pipeline import resultats_semestriels as rs  # noqa: E402


def _lire(p):
    return json.loads((RACINE / p).read_text(encoding="utf-8"))


def test_bpa_et_douze_mois_synchronises():
    jeu, bpa, fond = _lire("datasets/resultats_s1_2026.json"), _lire("bpa.json"), _lire("fondamentaux.json")
    b2, f2 = copy.deepcopy(bpa), copy.deepcopy(fond)
    rs.appliquer(jeu, b2, f2)
    ecarts = [s for s in set(bpa) | set(b2) if bpa.get(s) != b2.get(s)]
    assert not ecarts, f"bpa.json dérive des pièces pour : {sorted(ecarts)} — relancer resultats_semestriels.py"


def test_ratios_publies_synchronises():
    fond = _lire("fondamentaux.json")
    f2 = copy.deepcopy(fond)
    rf.recalculer(_lire("datasets/resultats_s1_2026.json")["titres"],
                  _lire("pipeline/faits_financiers.json"), f2, rf.charger_verifies())
    ecarts = sorted(s for s in f2 if isinstance(f2[s], dict)
                    and (fond.get(s) or {}).get("ratios_publies") != f2[s].get("ratios_publies"))
    assert not ecarts, f"ratios publiés en retard sur les pièces pour : {ecarts} — relancer resultats_semestriels.py"
