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


# ── Ratios de bilan 2025 (dette nette, EBITDA, ROIC, conversion) ─────────
#
#   dette nette        = dettes financières − trésorerie et équivalents
#   EBITDA             = EBE / EBITDA PUBLIÉ par la société s'il l'est,
#                        sinon résultat d'exploitation + dotations aux
#                        AMORTISSEMENTS d'exploitation (jamais un total mêlé
#                        de provisions : faute de ligne, pas d'EBITDA)
#   dette nette/EBITDA = seulement si EBITDA > 0
#   ROIC               = REX × (1 − t) ÷ (capitaux propres totaux + dette nette)
#                        t = impôt ÷ résultat avant impôt ; si ce dernier est
#                        ≤ 0 il n'y a pas d'impôt sur une perte : t = 0, et le
#                        libellé le dit
#   conversion         = flux de trésorerie d'exploitation ÷ résultat net
#                        consolidé, seulement si ce résultat est > 0
#
# ⚠️ Ces ratios ne sont écrits QUE dans `ratios_publies`. Les champs
# `roic`, `dette_nette_ebitda` et `cash_conversion` de premier niveau — ceux
# que lit la note (fond_score.py) — ne sont PAS touchés : les substituer
# changerait des notes, ce qui demande mesure ET accord (R8). La mesure est
# dans datasets/mesure_ratios_2026-09-30.json.
#
# Banques, assurances et sociétés de financement : sans objet. Leur dette est
# leur matière première ; un « dette nette / EBITDA » n'y a pas de sens.

SECTEURS_FINANCIERS = ("Banque", "Assurance", "Finance")
SANS_OBJET_FINANCIER = "sans objet : établissement financier"
DATE_EXERCICE = "2025-12-31"


def est_financier(fiche: dict | None) -> bool:
    return any(str((fiche or {}).get("secteur") or "").startswith(s) for s in SECTEURS_FINANCIERS)


def _v(f: dict, k: str):
    x = f.get(k)
    return None if not isinstance(x, dict) else x.get("valeur")


def _src(entree: dict, f: dict, k: str) -> str:
    return f"{entree.get('document')} — {entree.get('url')}, p. {f[k].get('page')}"


def calculer_bilan(entree: dict | None) -> tuple[dict, dict]:
    """(ratios, non_calcules) d'un émetteur non financier. Pure.

    Lit uniquement `faits_financiers.json`. Un terme absent, ou déclaré
    douteux dans `_controles_ratios_2025.non_calcules`, et le ratio n'est pas
    publié : sa raison l'est à la place."""
    entree = entree or {}
    f = entree.get("faits") or {}
    ctrl = entree.get("_controles_ratios_2025") or {}
    refus = dict(ctrl.get("non_calcules") or {})
    if not ctrl:
        return {}, {}
    out, non = {}, {}
    mm = "MMAD"

    def base(val, formule, sources, **extra):
        return {"valeur": val, "date": DATE_EXERCICE, "formule": formule,
                "sources": sources, "base": ctrl.get("base"), **extra}

    # dette nette
    dn = None
    if "dette_nette" in refus:
        non["dette_nette"] = refus["dette_nette"]
    elif _v(f, "dettes_financieres") is not None and _v(f, "tresorerie_actif") is not None:
        dn = round(_v(f, "dettes_financieres") - _v(f, "tresorerie_actif"), 3)
        out["dette_nette"] = base(round(dn, 1), f"{_v(f, 'dettes_financieres')} − {_v(f, 'tresorerie_actif')} ({mm})", {
            "dettes_financieres": _src(entree, f, "dettes_financieres"),
            "tresorerie": _src(entree, f, "tresorerie_actif")}, unite=mm)
    else:
        non["dette_nette"] = "dettes financières ou trésorerie non relevées"

    # EBITDA
    rex_k = "resultat_exploitation_etats" if _v(f, "resultat_exploitation_etats") is not None else "resultat_exploitation"
    rex = _v(f, rex_k)
    eb = None
    if "ebitda" in refus:
        non["ebitda"] = refus["ebitda"]
    elif _v(f, "excedent_brut_exploitation") is not None:
        eb = _v(f, "excedent_brut_exploitation")
        out["ebitda"] = base(round(eb, 1), f"EBE/EBITDA publié par la société : {eb} ({mm})",
                             {"ebitda": _src(entree, f, "excedent_brut_exploitation")}, unite=mm, origine="publié")
    elif rex is not None and _v(f, "dotations_amortissements_exploitation") is not None:
        d = _v(f, "dotations_amortissements_exploitation")
        eb = round(rex + d, 3)
        out["ebitda"] = base(round(eb, 1), f"{rex} + {d} ({mm}) — résultat d'exploitation + dotations aux amortissements",
                             {"resultat_exploitation": _src(entree, f, rex_k),
                              "amortissements": _src(entree, f, "dotations_amortissements_exploitation")},
                             unite=mm, origine="calculé")
    else:
        non["ebitda"] = "ni EBE publié, ni dotations aux amortissements isolées"

    # dette nette / EBITDA
    if dn is not None and eb is not None:
        if eb > 0:
            out["dette_nette_ebitda"] = base(round(dn / eb, 2), f"{round(dn, 3)} ÷ {eb}", {
                "dette_nette": "ratios_publies.dette_nette", "ebitda": "ratios_publies.ebitda"})
        else:
            non["dette_nette_ebitda"] = f"EBITDA négatif ou nul ({eb}) : ratio sans signification"
    else:
        non["dette_nette_ebitda"] = "dette nette ou EBITDA non calculé"

    # ROIC
    rai, imp, cp = _v(f, "resultat_avant_impot"), _v(f, "impot_resultat"), _v(f, "capitaux_propres_consolides")
    if "roic" in refus:
        non["roic"] = refus["roic"]
    elif None in (rex, rai, imp, cp) or dn is None:
        non["roic"] = "un terme manque (résultat d'exploitation, résultat avant impôt, impôt, capitaux propres consolidés ou dette nette)"
    else:
        if rai > 0:
            t = imp / rai
            lib_t = f"t = {imp} ÷ {rai} = {round(t * 100, 1)} %"
        else:
            t = 0.0
            lib_t = f"t = 0 (résultat avant impôt {rai} ≤ 0 : pas d'impôt sur une perte)"
        ce = cp + dn
        if not 0 <= t < 1:
            non["roic"] = f"taux effectif hors de [0, 100 %[ ({round(t * 100, 1)} %)"
        elif ce <= 0:
            non["roic"] = f"capitaux employés ≤ 0 ({round(ce, 1)})"
        else:
            out["roic"] = base(round(rex * (1 - t) / ce * 100, 1),
                               f"{rex} × (1 − t) ÷ ({cp} + {round(dn, 3)}) ; {lib_t}", {
                                   "resultat_exploitation": _src(entree, f, rex_k),
                                   "impot": _src(entree, f, "impot_resultat"),
                                   "resultat_avant_impot": _src(entree, f, "resultat_avant_impot"),
                                   "capitaux_propres": _src(entree, f, "capitaux_propres_consolides"),
                                   "dette_nette": "ratios_publies.dette_nette"},
                               unite="%", taux_impot_effectif=round(t * 100, 1))

    # conversion en trésorerie
    cfo, rn = _v(f, "flux_tresorerie_exploitation"), _v(f, "resultat_net_consolide")
    if "cash_conversion" in refus:
        non["cash_conversion"] = refus["cash_conversion"]
    elif cfo is None or rn is None:
        non["cash_conversion"] = "flux de trésorerie d'exploitation ou résultat net consolidé non relevé"
    elif rn <= 0:
        non["cash_conversion"] = f"résultat net ≤ 0 ({rn}) : ratio sans signification"
    else:
        out["cash_conversion"] = base(round(cfo / rn * 100, 1), f"{cfo} ÷ {rn} ({mm})", {
            "flux": _src(entree, f, "flux_tresorerie_exploitation"),
            "resultat_net": _src(entree, f, "resultat_net_consolide")}, unite="%")
    return out, non


def main() -> int:
    s1 = json.loads(S1.read_text(encoding="utf-8"))["titres"]
    faits = json.loads(FAITS.read_text(encoding="utf-8"))
    fond = json.loads(FOND.read_text(encoding="utf-8"))
    n = nb = nf = 0
    tickers = list(s1) + [s for s in faits if not s.startswith("_") and s not in s1]
    tickers += [s for s, v in fond.items() if isinstance(v, dict) and est_financier(v) and s not in tickers]
    for sym in tickers:
        r = calculer(s1.get(sym) or {}, faits.get(sym))
        fiche = fond.get(sym) if isinstance(fond.get(sym), dict) else None
        if fiche is not None and est_financier(fiche):
            r["ratios_bilan_2025"] = {"sans_objet": SANS_OBJET_FINANCIER, "secteur": fiche.get("secteur"),
                                      "ratios": ["dette_nette", "ebitda", "dette_nette_ebitda", "roic", "cash_conversion"]}
            nf += 1
        else:
            rb, non = calculer_bilan(faits.get(sym))
            r.update(rb)
            if non:
                r["non_calcules_2025"] = non
            nb += bool(rb)
        if not r:
            continue
        fond.setdefault(sym, {})["ratios_publies"] = {**r, "calcule_le": DATE_MAJ}
        n += 1
        print(sym, {k: v.get("valeur", v.get("sans_objet")) for k, v in r.items()
                    if isinstance(v, dict) and k != "non_calcules_2025"})
    print(f"{nb} émetteurs avec au moins un ratio de bilan, {nf} financiers sans objet")
    FOND.write_text(json.dumps(fond, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"{n} titres avec au moins un ratio calculé")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
