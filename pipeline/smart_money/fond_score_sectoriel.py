#!/usr/bin/env python3
"""Note fondamentale PAR SECTEUR — calculée en FANTÔME, jamais publiée — 30/09/2026.

⚠️ CE MODULE NE CHANGE AUCUNE NOTE. Aucun calcul publié ne le lit. Il produit
une MESURE (`datasets/note_sectorielle_2026-09-30.json`) pour qu'Abd Moutalib
décide, titre par titre, s'il remplace `fond_score.py` (règle R8).

⚠️ POURQUOI UNE AUTRE GRILLE
`fond_score.py` applique la même grille aux 80 sociétés :
  · qualité = ROIC − WACC, sans objet pour une banque ou un assureur ;
  · dette / EBITDA, sans objet pour un établissement financier ;
  · PER prévisionnel face à un repère FIXE de 15 ;
  · et, faute de donnée, des valeurs SUPPOSÉES : PER prévisionnel 15 (37 titres
    au 30/09), dette 1,0× l'EBITDA (40), ROIC = WACC (38) — d'où tant de notes
    fondamentales identiques à 5,45.
Relevé d'Abd Moutalib, appuyé sur yuna.ma : « les secteurs ne se calculent pas
toujours pareil ».

⚠️ PRINCIPES DE CETTE GRILLE
1. Seules des données CALCULÉES sur comptes publiés, datées : ROIC, ROE,
   dette nette / EBITDA, conversion (ratios_publies), croissances et BPA sur
   12 mois (dépôts S1 2026). Les champs saisis à la main ne sont pas lus.
2. Un critère sans donnée S'ABSTIENT ; les poids se répartissent entre les
   critères présents. Moins de la moitié du poids disponible : pas de note
   (« données insuffisantes »), jamais une note par défaut.
3. Rentabilité : ROIC pour les sociétés non financières (ROE à défaut),
   ROE pour banques, crédit et assurances.
4. Valorisation RELATIVE : PER 12 mois rapporté à la médiane de son secteur
   (au moins 3 titres, sinon médiane du marché). Une perte : 1,5.
5. Bilan : sociétés non financières seulement.
6. Aucun modificateur d'opinion (momentum, rerating, cycle) : non mesurés.

⚠️ LES SEUILS sont ceux de la grille actuelle quand un équivalent existe
(croissance, dette / EBITDA, conversion) ; pour le ROE, le ROIC et le PER
relatif, ce sont des paliers nouveaux, déclarés ici et non calibrés. Ils
n'ont PAS été backtestés : l'historique de fondamentaux calculés commence le
29/09/2026. Ce module sert à décider, pas à prouver.
"""

from __future__ import annotations

import json
import statistics
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(RACINE))

POIDS = {"rentabilite": 0.40, "croissance": 0.30, "valorisation": 0.20, "bilan": 0.10}
FONCIERES = {"ARD", "IMI"}          # foncières cotées (revenus locatifs)


def famille(sym: str, secteur: str) -> str:
    s = secteur or ""
    if s.startswith("Banque"):
        return "banque"
    if s.startswith("Assurance"):
        return "assurance"
    if s.startswith("Finance"):
        return "credit"
    if sym in FONCIERES:
        return "fonciere"
    return "autre"


def note_roic(r):
    for s, n in ((25, 9.5), (18, 8.5), (12, 7.0), (8, 6.0), (5, 5.0), (0, 3.5)):
        if r >= s:
            return n
    return 2.0


def note_roe(r):
    for s, n in ((25, 9.5), (18, 8.5), (13, 7.0), (9, 6.0), (6, 5.0), (0, 3.5)):
        if r >= s:
            return n
    return 2.0


def note_croissance(g):
    # Paliers repris de fond_score.py.
    for s, n in ((100, 10.0), (50, 9.0), (25, 7.5), (10, 6.5), (5, 5.5), (0, 4.5), (-10, 3.0)):
        if g >= s:
            return n
    return 1.5


def note_per_relatif(ratio):
    if ratio <= 0.6:
        return 9.5
    if ratio <= 0.8:
        return 8.5
    if ratio <= 1.0:
        return 7.0
    if ratio <= 1.25:
        return 5.5
    if ratio <= 1.6:
        return 4.0
    return 2.5


def note_bilan(dne, cc):
    # Paliers repris de fond_score.py.
    if dne < 0:
        bs = 9.0
    elif dne < 0.5:
        bs = 8.5
    elif dne < 1.5:
        bs = 7.0
    elif dne < 2.5:
        bs = 5.5
    elif dne < 3.5:
        bs = 4.0
    elif dne < 5.0:
        bs = 2.5
    else:
        bs = 1.5
    if cc is not None:
        if cc >= 85:
            bs = min(10.0, bs + 0.5)
        elif cc < 40:
            bs = max(0.0, bs - 0.5)
    return bs


def _val(ratios: dict, cle: str):
    x = (ratios or {}).get(cle)
    return x.get("valeur") if isinstance(x, dict) else None


def composantes(sym, fiche, bpa, prix, famille_, mediane_per):
    """Les critères présents, chacun avec sa donnée et sa note. Pure."""
    r = (fiche or {}).get("ratios_publies") or {}
    out = {}
    fin = famille_ in ("banque", "credit", "assurance")
    roe = _val(r, "roe_12m") if _val(r, "roe_12m") is not None else _val(r, "roe_2025")
    roic = None if fin else _val(r, "roic")
    if roic is not None:
        out["rentabilite"] = {"mesure": f"ROIC {roic} %", "note": note_roic(roic)}
    elif roe is not None:
        out["rentabilite"] = {"mesure": f"ROE {roe} %", "note": note_roe(roe)}
    # Croissance : seulement si elle vient des dépôts S1 2026.
    if (fiche or {}).get("source_s1_2026"):
        cb, cc = fiche.get("croissance_bpa"), fiche.get("croissance_ca")
        if cb is not None or cc is not None:
            g = (cb if cb is not None else cc) * (0.6 if cc is not None and cb is not None else 1.0) \
                + (cc * 0.4 if cc is not None and cb is not None else 0.0)
            out["croissance"] = {"mesure": f"BPA {cb} % · CA {cc} %", "note": note_croissance(g)}
    b12 = (bpa or {}).get("bpa_12m")
    if b12 is not None and prix:
        if b12 <= 0:
            out["valorisation"] = {"mesure": "perte sur 12 mois", "note": 1.5}
        elif mediane_per:
            per = prix / b12
            out["valorisation"] = {"mesure": f"PER 12 m {per:.1f} / médiane {mediane_per:.1f}",
                                   "note": note_per_relatif(per / mediane_per)}
    if not fin:
        dne = _val(r, "dette_nette_ebitda")
        if dne is not None:
            out["bilan"] = {"mesure": f"dette nette / EBITDA {dne}", "note": note_bilan(dne, _val(r, "cash_conversion"))}
    return out


def note(comp: dict):
    """Moyenne pondérée des critères PRÉSENTS ; None sous la moitié du poids."""
    w = sum(POIDS[k] for k in comp)
    if w < 0.5:
        return None
    return round(sum(POIDS[k] * v["note"] for k, v in comp.items()) / w, 2)


def medianes_per(titres, bpa, prix, secteurs):
    par_sect, tous = {}, []
    for s in titres:
        b = (bpa.get(s) or {}).get("bpa_12m")
        p = prix.get(s)
        if b and b > 0 and p:
            per = p / b
            par_sect.setdefault(secteurs.get(s, ""), []).append(per)
            tous.append(per)
    marche = statistics.median(tous) if tous else None
    return {k: (statistics.median(v) if len(v) >= 3 else marche) for k, v in par_sect.items()}, marche


def main() -> int:
    from bvc_config import COMPANY_SECTORS
    fond = json.loads((RACINE / "fondamentaux.json").read_text(encoding="utf-8"))
    bpa = json.loads((RACINE / "bpa.json").read_text(encoding="utf-8"))
    data = json.loads((RACINE / "data.json").read_text(encoding="utf-8"))
    T = {t["symbol"]: t for t in data["tickers"]}
    prix = {s: t.get("price") for s, t in T.items()}
    med, marche = medianes_per(T, bpa, prix, COMPANY_SECTORS)
    pal = lambda v: ("ACHETER" if v >= 6.5 else "SURVEILLER" if v >= 5.5 else
                     "ATTENDRE" if v >= 4.5 else "ÉVITER" if v >= 3.5 else "ÉVITER FORT")
    out = {}
    for s, t in T.items():
        fam = famille(s, COMPANY_SECTORS.get(s, ""))
        comp = composantes(s, fond.get(s), bpa.get(s), prix.get(s), fam,
                           med.get(COMPANY_SECTORS.get(s, ""), marche))
        n = note(comp)
        # La note PUBLIÉE, pas un recalcul : c'est elle qu'on compare.
        ancienne = t.get("score_fond")
        pf = (t.get("poids") or {}).get("f", 0) / 100
        v0 = t.get("v53")
        # v53 est linéaire en score_fond (compute_v53, aucun bonus depuis le
        # 30/09) : la simulation est exacte, au plafond [0, 10] près.
        v1 = (round(min(max(v0 + (n - ancienne) * pf, 0), 10), 2)
              if None not in (n, v0, ancienne) else None)
        out[s] = {"famille": fam, "secteur": COMPANY_SECTORS.get(s, ""),
                  "note_actuelle": ancienne, "note_sectorielle": n,
                  "composantes": comp, "v53_actuelle": v0, "v53_simulee": v1,
                  "palier_actuel": pal(v0) if v0 is not None else None,
                  "palier_simule": pal(v1) if v1 is not None else "données insuffisantes"}
    (RACINE / "datasets" / "note_sectorielle_2026-09-30.json").write_text(json.dumps(
        {"_quoi": "MESURE, non appliquée : note fondamentale par secteur (fond_score_sectoriel.py) "
                  "comparée à la note actuelle. v53 simulée = v53 + (nouvelle − ancienne) × poids fondamental.",
         "_mediane_per_marche": round(marche, 1) if marche else None,
         "titres": out}, ensure_ascii=False, indent=1), encoding="utf-8")
    ch = [s for s, x in out.items() if x["palier_simule"] != x["palier_actuel"]]
    print(f"{len(out)} titres ; paliers qui changeraient : {len(ch)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
