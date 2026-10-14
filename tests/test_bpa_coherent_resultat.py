"""Le BPA de l'exercice 2025 doit se déduire du résultat RELEVÉ SUR PIÈCE.

⚠️ 14/10/2026 : SMI portait un BPA de 310 (source « resultats_officiels »,
sans pièce) alors que son rapport annuel donne 397,11 MDH pour 1 645 090
actions, soit 241,39. L'erreur passait dans le résultat sur douze mois
(645 au lieu de 532 MDH), donc dans le PER publié (14,7 au lieu d'environ
17,8). Même défaut, plus petit, sur INV (0,26 contre 0,30). Contrôle croisé
sur 72 titres : aucun autre écart au-delà de 2 %.

Le contrôle porte sur les DONNÉES : un BPA saisi qui s'écarte du résultat
relevé de plus de 2 % est une erreur, quelle que soit sa source.
"""
import json
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
TOLERANCE_PCT = 2.0


def _releves():
    r = json.loads((RACINE / "datasets" / "resultats_s1_2026.json").read_text(encoding="utf-8"))
    out = {}

    def parcourir(o):
        if isinstance(o, dict):
            for k, v in o.items():
                if isinstance(v, dict) and "rnpg_exercice_2025" in v:
                    out[k] = v
                else:
                    parcourir(v)
    parcourir(r)
    return out


def test_le_bpa_2025_se_deduit_du_resultat_releve():
    bpa = json.loads((RACINE / "bpa.json").read_text(encoding="utf-8"))
    ecarts = []
    for t, v in _releves().items():
        b = (bpa.get(t) or {}).get("bpa")
        if b is None or not v.get("actions") or not v.get("rnpg_exercice_2025"):
            continue
        calcule = v["rnpg_exercice_2025"] * 1e6 / v["actions"]
        if abs(b / calcule - 1) * 100 > TOLERANCE_PCT:
            ecarts.append(f"{t} : bpa.json {b} contre {calcule:.2f} (résultat ÷ actions)")
    assert not ecarts, "BPA incohérents avec le résultat relevé : " + " ; ".join(ecarts)


def test_smi_sur_piece():
    v = _releves()["SMI"]
    assert v["rnpg_exercice_2025"] == 397.1086
    assert "SMI_RFA_2025.pdf, p.44" in v["source_exercice_2025"]
