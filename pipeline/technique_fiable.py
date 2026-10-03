"""Le pilier technique est-il lisible sur ce titre ? Règle unique, partagée par
le moteur (`update_data.py`) et par la mesure qui l'a justifiée
(`pipeline/mesure_neutralisation_tech.py`, publiée avec le calibrage
technique : `pipeline/mesure_score_tech.py`, résultats dans
`datasets/calibrage_technique/`).

⚠️ POURQUOI — étape 0 du calibrage technique, 03/10/2026
Rejoué au jour le jour sur trois ans, le pilier technique actuel annonce
l'INVERSE de la suite sur les titres peu liquides et au fixing : corrélation
de rang avec l'alpha à 5 séances −0,18 / −0,20 sur le tiers le moins liquide,
−0,19 / −0,30 au fixing (2023-24 / 2025-26). Avec peu d'échanges, la clôture
saute d'un côté à l'autre du carnet et revient : le pilier lit ce bruit comme
une tendance. Sur ces titres, sa part revient au fondamental (accord d'Abd
Moutalib, R8), jusqu'au nouveau pilier technique.

⚠️ RÈGLE FIXÉE AVANT LA MESURE, établie À LA DATE depuis les chandelles :
  · peu liquide : montant médian échangé sur les 20 dernières séances
    ÉCHANGÉES < 125 947 DH (seuil du tiers le moins liquide, étape 0) ;
  · au fixing : la majorité de ces 20 séances sont plates (O = H = B = C).
Un titre sans aucune séance échangée est traité comme peu liquide.
"""
from __future__ import annotations

SEUIL_DH = 125_947
FENETRE = 20


def technique_non_fiable(bougies) -> dict | None:
    """Motif si le pilier technique doit être neutralisé, sinon None.

    `bougies` : DataFrame ou liste de dicts {d, o, h, l, c, v}, dans l'ordre
    chronologique, arrêtée à la date de calcul.
    """
    if bougies is None:
        return {"motif": "aucune chandelle", "seances_echangees": 0}
    lignes = bougies.to_dict("records") if hasattr(bougies, "to_dict") else list(bougies)
    ech = [b for b in lignes if (b.get("v") or 0) > 0][-FENETRE:]
    if not ech:
        return {"motif": "aucune séance échangée", "seances_echangees": 0}
    plates = sum(1 for b in ech if b.get("o") == b.get("h") == b.get("l") == b.get("c"))
    montants = sorted(float(b["c"]) * float(b["v"]) for b in ech)
    m = len(montants)
    median = montants[m // 2] if m % 2 else (montants[m // 2 - 1] + montants[m // 2]) / 2
    motifs = []
    if median < SEUIL_DH:
        motifs.append("peu liquide")
    if plates * 2 > len(ech):
        motifs.append("coté au fixing")
    if not motifs:
        return None
    return {"motif": " et ".join(motifs), "montant_median_dh": round(median),
            "seances_plates": plates, "seances_echangees": len(ech)}
