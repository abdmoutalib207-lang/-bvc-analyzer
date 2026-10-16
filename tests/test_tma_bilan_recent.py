"""TMA : le bilan le plus récent (30/06/2026) contredit celui que lit la note
(31/12/2025). Tant que la règle de choix de période n'est pas décidée, l'écart
est une RÉSERVE VISIBLE, chiffrée sur pièce — pas un changement silencieux."""
import json
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

from pipeline.smart_money import fond_score as fg  # noqa: E402


def test_la_reserve_de_tma_dit_le_bilan_recent_et_son_effet():
    txt = fg.RESERVES_RATIOS["TMA"]["bilan"]
    for attendu in ("+326,3", "30/06/2026", "p.4", "6,95", "SURVEILLER ★", "ACHETER ★★"):
        assert attendu in txt, attendu


def test_la_note_lit_encore_le_bilan_de_l_exercice():
    fond = json.loads((RACINE / "fondamentaux.json").read_text(encoding="utf-8"))
    fond = fond.get("societes", fond)
    dn = fond["TMA"]["ratios_publies"]["dette_nette"]
    assert dn["date"] == "2025-12-31" and dn["valeur"] == -288.6


def test_l_arithmetique_du_bilan_s1_se_refait():
    # Total_Maroc_S1_26.pdf p.4 (KMAD) : « Dettes financières non courantes 473.879 »,
    # « Dettes financières courantes 841.200 », « Trésorerie et équivalents de trésorerie 988.736 »
    assert round(473.879 + 841.200 - 988.736, 1) == 326.3
