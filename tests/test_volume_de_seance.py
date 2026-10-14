"""Le volume publié est celui de la séance de référence.

⚠️ 14/10/2026 : en séance, WAF (cours du 13/10, marqué périmé) publiait
103 titres — le volume du 13/10 — dans la colonne du jour, alors qu'il
n'avait rien échangé le 14/10. 13 titres dans ce cas au run de 14h56.
"""
import json
import sys
from collections import Counter
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

from update_data import volume_de_seance  # noqa: E402


def test_cours_de_la_veille_volume_nul():
    assert volume_de_seance(103, "2026-10-13", "2026-10-14") == 0


def test_cours_de_la_seance_volume_conserve():
    assert volume_de_seance(5716, "2026-10-14", "2026-10-14") == 5716


def test_sans_date_rien_n_est_invente():
    assert volume_de_seance(42, None, "2026-10-14") == 42
    assert volume_de_seance(42, "2026-10-14", "") == 42


def test_donnees_publiees_aucun_volume_d_une_autre_seance():
    d = json.loads((RACINE / "data.json").read_text(encoding="utf-8"))
    t = d.get("tickers") or []
    dates = [(x.get("_meta") or {}).get("prix_asof") for x in t]
    dates = [x for x in dates if x]
    if not dates:
        return
    reference = max(dates)
    fautifs = [x["symbol"] for x in t
               if (x.get("_meta") or {}).get("prix_asof")
               and x["_meta"]["prix_asof"] < reference and (x.get("vol") or 0) > 0]
    assert not fautifs, f"volume d'une autre séance publié pour : {fautifs}"
