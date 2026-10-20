#!/usr/bin/env python3
"""Compare le relevé officiel des émetteurs (datasets/bourse_emetteurs.json) à
notre référentiel. LECTURE SEULE : n'écrit rien, ne modifie ni bvc_config, ni
ISIN_MAP, ni aucune donnée (R2 : tout changement d'ISIN exige l'accord d'Abd).

Appariement, dans cet ordre, une ligne de la Bourse ne servant qu'une fois :
  1. ISIN, quand les deux côtés en portent un ;
  2. code officiel BVC : IDB_TICKER_MAP traduit NOTRE ticker en code officiel
     (notre SNA = Sonasid = SID à la Bourse ; le SNA de la Bourse est Stokvis,
     notre STK) ;
  3. nom normalisé (COMPANY_NAMES contre intitulé ou émetteur).

Écarts rendus : nombre de titres (> 0,5 %) contre fondamentaux.json
(`nb_actions`) et pipeline/faits_financiers.json ; ISIN différent ; titre
présent d'un seul côté ; statut (suspension / radiation / absence de comptes
chez nous, contre le statut affiché par la Bourse).

Usage : python3 tools/comparer_emetteurs.py [--releve CHEMIN] [--json]
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
RELEVE = RACINE / "datasets" / "bourse_emetteurs.json"
SEUIL_TITRES = 0.005  # 0,5 %

# Clés de faits_financiers.json portant un nombre d'actions, par préférence :
# le nombre ACTUEL d'abord (la Bourse publie l'état présent), celui du rapport
# ensuite — ce dernier est daté de la clôture et ignore les opérations postérieures.
CLES_FAITS_ACTIONS = (
    "nombre_actions_existant",
    "nombre_actions_referentiel",
    "nombre_actions",
    "nombre_actions_au_rapport",
    "nombre_actions_31_12_2025",
)
MOTS_VIDES = {"SA", "S", "A", "SCA", "LA", "LE", "LES", "DU", "DE", "DES", "D", "L", "ET", "AU", "COM"}


def normaliser(nom: str | None) -> str:
    if not nom:
        return ""
    s = unicodedata.normalize("NFKD", nom).encode("ascii", "ignore").decode().upper()
    s = re.sub(r"[^A-Z0-9]+", " ", s)
    return " ".join(m for m in s.split() if m not in MOTS_VIDES)


def _nb_faits(fiche: dict) -> tuple[int | None, str | None]:
    faits = (fiche or {}).get("faits") or {}
    for cle in CLES_FAITS_ACTIONS:
        v = (faits.get(cle) or {}).get("valeur") if isinstance(faits.get(cle), dict) else None
        if isinstance(v, (int, float)) and v > 0:
            return int(v), cle
    return None, None


def charger_referentiel(racine: Path = RACINE) -> dict:
    """Construit le référentiel depuis les fichiers du dépôt (lecture seule)."""
    sys.path.insert(0, str(racine))
    import bvc_config as c  # noqa: E402

    fond = json.loads((racine / "fondamentaux.json").read_text(encoding="utf-8"))
    chemin_faits = racine / "pipeline" / "faits_financiers.json"
    faits = json.loads(chemin_faits.read_text(encoding="utf-8")) if chemin_faits.exists() else {}

    statuts: dict[str, list[str]] = {}
    for t, evts in getattr(c, "SUSPENSIONS", {}).items():
        for e in evts:
            if not e.get("reprise"):
                statuts.setdefault(t, []).append(f"suspendu depuis {e.get('depuis')}")
    for t, e in getattr(c, "VALEURS_RADIEES", {}).items():
        statuts.setdefault(t, []).append(f"radié le {e.get('date')}")
    for t, e in getattr(c, "SANS_COMPTES", {}).items():
        statuts.setdefault(t, []).append(f"sans comptes depuis {e.get('dernier_depot')}")

    tickers = sorted(set(c.TICKERS_ALL) | set(c.COMPANY_NAMES))
    nb_faits, cle_faits = {}, {}
    for t in tickers:
        if isinstance(faits.get(t), dict):
            v, k = _nb_faits(faits[t])
            if v:
                nb_faits[t], cle_faits[t] = v, k
    return {
        "tickers": tickers,
        "noms": dict(c.COMPANY_NAMES),
        "isin": dict(c.ISIN_MAP),
        "code_officiel": dict(c.IDB_TICKER_MAP),
        "secteurs": dict(c.COMPANY_SECTORS),
        "nb_fondamentaux": {t: int(v["nb_actions"]) for t, v in fond.items()
                            if isinstance(v, dict) and isinstance(v.get("nb_actions"), (int, float))},
        "nb_faits": nb_faits,
        "cle_faits": cle_faits,
        "statuts": statuts,
        "splits": dict(getattr(c, "SPLITS", {})),
    }


def _ecart_rel(nous: int, bourse: int) -> float:
    return abs(nous - bourse) / bourse if bourse else float("inf")


def comparer(releve: dict, ref: dict) -> dict:
    """Rend {'appariements': [...], 'ecarts': [...], 'non_apparies_bourse': [...]}."""
    actions = [r for r in releve.get("enregistrements", []) if r.get("type_instrument") == "Actions"]
    pris: set[int] = set()

    def chercher(t: str) -> tuple[int | None, str | None]:
        isin = ref["isin"].get(t)
        if isin:
            for i, r in enumerate(actions):
                if i not in pris and r.get("isin") and r["isin"] == isin:
                    return i, "isin"
        code = ref["code_officiel"].get(t, t)
        cands = [i for i, r in enumerate(actions) if i not in pris and r.get("code") == code]
        if len(cands) == 1:
            return cands[0], "code"
        nom = normaliser(ref["noms"].get(t))
        if nom:
            cands = [i for i, r in enumerate(actions) if i not in pris
                     and nom in (normaliser(r.get("instrument")), normaliser(r.get("emetteur")))]
            if len(cands) == 1:
                return cands[0], "nom"
        return None, None

    appariements, ecarts = [], []
    # ISIN d'abord pour tous, puis code, puis nom : un titre apparié par une preuve
    # forte ne doit pas se faire prendre sa ligne par un appariement faible.
    restants = list(ref["tickers"])
    for passe in ("isin", "code", "nom"):
        suivants = []
        for t in restants:
            i, methode = chercher(t)
            if i is not None and methode == passe:
                pris.add(i)
                appariements.append((t, i, methode))
            else:
                suivants.append(t)
        restants = suivants

    sortie_app = []
    for t, i, methode in sorted(appariements):
        r = actions[i]
        nb_b = r.get("nombre_titres")
        ligne = {
            "ticker": t, "methode": methode, "code_bourse": r.get("code"),
            "nom_nous": ref["noms"].get(t), "emetteur_bourse": r.get("emetteur"),
            "secteur_nous": ref["secteurs"].get(t), "secteur_bourse": r.get("secteur"),
            "nombre_titres_bourse": nb_b, "statut_bourse": r.get("statut"),
            "statut_nous": "; ".join(ref["statuts"].get(t, [])) or None,
        }
        sortie_app.append(ligne)
        for source, table in (("fondamentaux.json", ref["nb_fondamentaux"]),
                              ("faits_financiers.json", ref["nb_faits"])):
            nous = table.get(t)
            if nous is not None and nb_b is not None and _ecart_rel(nous, nb_b) > SEUIL_TITRES:
                cle = ref.get("cle_faits", {}).get(t) if source == "faits_financiers.json" else "nb_actions"
                e = {"ticker": t, "grandeur": f"nombre de titres ({source} › {cle})",
                     "nous": nous, "bourse": nb_b,
                     "ecart_pct": round(100 * (nous - nb_b) / nb_b, 2)}
                splits = ref.get("splits", {}).get(t) or []
                if splits:
                    e["note"] = "; ".join(f"split ×{x['ratio']} du {x['date']} déclaré (SPLITS)" for x in splits)
                ecarts.append(e)
        isin_n, isin_b = ref["isin"].get(t), r.get("isin")
        if isin_n and isin_b and isin_n != isin_b:
            ecarts.append({"ticker": t, "grandeur": "ISIN", "nous": isin_n, "bourse": isin_b})
        if bool(ligne["statut_nous"]) != bool(ligne["statut_bourse"]) or (
                ligne["statut_nous"] and ligne["statut_bourse"]):
            ecarts.append({"ticker": t, "grandeur": "statut",
                           "nous": ligne["statut_nous"] or "aucun",
                           "bourse": ligne["statut_bourse"] or "aucun statut affiché"})

    for t in restants:
        ecarts.append({"ticker": t, "grandeur": "présent chez nous seulement",
                       "nous": ref["noms"].get(t),
                       "bourse": "absent de la liste",
                       "statut_nous": "; ".join(ref["statuts"].get(t, [])) or None})
    non_apparies = [actions[i] for i in range(len(actions)) if i not in pris]
    for r in non_apparies:
        ecarts.append({"ticker": None, "grandeur": "présent à la Bourse seulement",
                       "nous": "absent du référentiel",
                       "bourse": f"{r.get('code')} — {r.get('emetteur')} ({r.get('nombre_titres')} titres)"})
    return {"appariements": sortie_app, "ecarts": ecarts, "non_apparies_bourse": non_apparies,
            "n_actions_bourse": len(actions), "n_tickers_nous": len(ref["tickers"])}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--releve", default=str(RELEVE))
    ap.add_argument("--json", action="store_true", help="sortie JSON complète sur stdout")
    a = ap.parse_args()
    releve = json.loads(Path(a.releve).read_text(encoding="utf-8"))
    res = comparer(releve, charger_referentiel())
    if a.json:
        print(json.dumps(res, ensure_ascii=False, indent=1))
        return 0
    from collections import Counter
    m = Counter(x["methode"] for x in res["appariements"])
    print(f"Relevé du {releve.get('releve_le')} — {releve.get('url_source')}")
    print(f"{len(res['appariements'])}/{res['n_tickers_nous']} titres appariés "
          f"({dict(m)}) ; {res['n_actions_bourse']} actions à la Bourse.\n")
    print("| titre | grandeur | chez nous | à la Bourse |")
    print("|---|---|---|---|")
    for e in res["ecarts"]:
        extra = f" (écart {e['ecart_pct']:+.2f} %)" if "ecart_pct" in e else ""
        st = f" [{e['statut_nous']}]" if e.get("statut_nous") else ""
        extra += f" — {e['note']}" if e.get("note") else ""
        print(f"| {e['ticker'] or '—'} | {e['grandeur']} | {e['nous']}{st} | {e['bourse']}{extra} |")
    return 0


if __name__ == "__main__":
    sys.exit(main())
