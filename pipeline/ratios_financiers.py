#!/usr/bin/env python3
"""Les ratios de rentabilité, CALCULÉS depuis les comptes publiés — 30/09/2026.

⚠️ POURQUOI CE MODULE
─────────────────────
Le ROE et la marge nette affichés sur la fiche venaient de l'export DATA+
d'IDBourse, figé au 01/07 et rafraîchi à la main ; `fondamentaux.json`
portait des ROIC, marges et dettes saisis en mai-juin, d'une quarantaine de
sources. Demande d'Abd Moutalib : « on ne peut pas le calculer à partir des
résultats de leur date au lieu qu'il reste figé ? » — si, pour ce que les
comptes contiennent.

Chaque ratio est calculé à partir de deux termes SOURCÉS (dépôt AMMC, page ou
citation) et porte sa date, sa formule et ses sources. Un terme manquant : le
ratio n'est pas publié. Rien n'est supposé.

    ROE 2025        = résultat net part du groupe 2025
                      ÷ capitaux propres part du groupe au 31/12/2025
    ROE 12 mois     = résultat net part du groupe sur 12 mois (au 30/06/2026)
                      ÷ capitaux propres part du groupe au 30/06/2026
    Marge nette S1  = résultat net part du groupe S1 2026 ÷ chiffre d'affaires
                      S1 2026 — pour une banque, le dénominateur est le PNB,
                      et le libellé le dit.

⚠️ Les capitaux propres sont ceux de la PART DU GROUPE, cohérents avec un
résultat part du groupe. yuna.ma retient parfois l'ensemble consolidé
(CMGP : 7,4 % chez yuna, 8,8 % ici) — convention différente, pas erreur.

⚠️ AUCUNE NOTE NE CHANGE : `fond_score` ne lit ni le ROE ni la marge nette.
Le ROIC et la dette nette, qui entrent dans la note, viendront ensuite — avec
mesure et accord (R8).

    python pipeline/ratios_financiers.py      # écrit ratios_publies dans fondamentaux.json
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

S1 = RACINE / "datasets" / "resultats_s1_2026.json"
FAITS = RACINE / "pipeline" / "faits_financiers.json"
FOND = RACINE / "fondamentaux.json"
DATE_MAJ = "2026-09-30"


def _pct(num, den):
    if num is None or not den or den <= 0:
        return None                      # des capitaux propres ≤ 0 : ratio sans objet
    return round(num / den * 100, 1)


def calculer(t: dict, faits: dict | None) -> dict:
    """Les ratios d'un titre, chacun avec sa formule et ses sources. Pure."""
    out = {}
    f = (faits or {}).get("faits") or {}
    cp_fin = t.get("capitaux_propres_pg_31_12_2025")
    src_cp_fin = t.get("source_capitaux_propres")
    if cp_fin is None and (f.get("capitaux_propres_part_groupe") or {}).get("valeur"):
        cp_fin = f["capitaux_propres_part_groupe"]["valeur"]
        src_cp_fin = (f"{faits.get('document')} — {faits.get('url')}, p. "
                      f"{f['capitaux_propres_part_groupe'].get('page')}")
    rn25 = t.get("rnpg_exercice_2025")
    roe25 = _pct(rn25, cp_fin)
    if roe25 is not None:
        out["roe_2025"] = {
            "valeur": roe25, "date": "2025-12-31",
            "formule": f"{rn25} ÷ {cp_fin} (MMAD)",
            "sources": {"resultat": t.get("source_exercice_2025"),
                        "capitaux_propres": src_cp_fin}}
    cp_s1 = t.get("capitaux_propres_pg_30_06_2026")
    rn12 = None
    if all(t.get(k) is not None for k in ("rnpg_exercice_2025", "rnpg_s1_2026", "rnpg_s1_2025")):
        rn12 = round(t["rnpg_exercice_2025"] + t["rnpg_s1_2026"] - t["rnpg_s1_2025"], 3)
    roe12 = _pct(rn12, cp_s1)
    if roe12 is not None:
        out["roe_12m"] = {
            "valeur": roe12, "date": "2026-06-30",
            "formule": f"({t['rnpg_exercice_2025']} + {t['rnpg_s1_2026']} − {t['rnpg_s1_2025']}) ÷ {cp_s1} (MMAD)",
            "sources": {"resultat": t.get("url"), "capitaux_propres": t.get("source_capitaux_propres")}}
    ca = t.get("ca_s1_2026")
    if t.get("rnpg_s1_2026") is not None and ca and ca > 0:
        out["marge_nette_s1_2026"] = {
            "valeur": round(t["rnpg_s1_2026"] / ca * 100, 1), "date": "2026-06-30",
            "denominateur": t.get("ca_libelle") or "chiffre d'affaires",
            "formule": f"{t['rnpg_s1_2026']} ÷ {ca} (MMAD)",
            "sources": {"comptes": t.get("url")}}
    return out


def main() -> int:
    s1 = json.loads(S1.read_text(encoding="utf-8"))["titres"]
    faits = json.loads(FAITS.read_text(encoding="utf-8"))
    fond = json.loads(FOND.read_text(encoding="utf-8"))
    n = 0
    for sym, t in s1.items():
        r = calculer(t, faits.get(sym))
        if not r:
            continue
        fond.setdefault(sym, {})["ratios_publies"] = {**r, "calcule_le": DATE_MAJ}
        n += 1
        print(sym, {k: v["valeur"] for k, v in r.items()})
    FOND.write_text(json.dumps(fond, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"{n} titres avec au moins un ratio calculé")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
