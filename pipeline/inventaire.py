#!/usr/bin/env python3
"""Inventaire reproductible de ce que le dépôt possède réellement.

POURQUOI CE PROGRAMME REMPLACE UN DOCUMENT ÉCRIT À LA MAIN
──────────────────────────────────────────────────────────
La première version de l'inventaire du lot 1 était recopiée à la main dans un
markdown. La revue externe a recalculé quatre volumes médians et trouvé quatre
écarts :

    ADH  annoncé 124 625   recalculé 121 846
    ADI  annoncé  22 380   recalculé  21 984
    CSR  annoncé  27 504   recalculé  25 440,5
    MNG  annoncé  34 625   recalculé  34 574

**La cause est une formule, pas une faute de frappe.** J'avais écrit
`sorted(v)[len(v)//2]`, qui rend l'élément supérieur du milieu — pas la
médiane. Sur une fenêtre de 60 observations, nombre pair, la médiane est la
MOYENNE des deux valeurs centrales. Le `,5` de Cosumar le signalait.

D'où ce programme : l'inventaire se calcule, il ne se recopie pas. Et chaque
grandeur porte sa définition, pour qu'un désaccord se règle sur la formule
plutôt que sur les chiffres.

CE QU'IL DÉCLARE POUR CHAQUE SÉRIE
──────────────────────────────────
Fichier source et son empreinte, première et dernière date, nombre de lignes
RÉELLEMENT présentes, fenêtre et formule exacte des statistiques de volume,
répartition inconnu / nul / positif, unité du volume avec son niveau de
certitude, et les trous du calendrier attendu.

⚠️ `n_candles` de `historical_data.json` compte la SÉRIE SOURCE, pas la liste
stockée — tronquée à 250 points. Ce programme ne compte que ce qu'il lit.

USAGE
    python pipeline/inventaire.py [--json FICHIER] [--markdown FICHIER]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import statistics
import sys
from datetime import date, timedelta
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
CANDLES = RACINE / "pipeline" / "candles"

sys.path.insert(0, str(RACINE))
from bvc_config import (COMPANY_SECTORS, ISIN_MAP, SPLITS,  # noqa: E402
                        SUSPENSIONS, TICKERS_ACTIFS, TICKERS_ALL,
                        est_ferie_fixe)

# Fenêtre des statistiques d'activité. Nommée ici pour qu'un désaccord porte
# sur la définition et non sur le résultat.
FENETRE_ACTIVITE = 60

# ⚠️ NIVEAU DE CERTITUDE DE L'UNITÉ DU VOLUME.
#
# CDG distingue dans son bulletin `QteEchangee` (nombre de titres) de `Volumes`
# (montant en dirhams), et `update_data.py` lit le premier. Mais les chandelles
# ne conservent PAS le programme qui les a écrites : pour une bougie ancienne,
# l'unité est déduite de la convention du moteur, pas lue dans la donnée.
#
# C'est la réserve DAT-10, ouverte. Elle est déclarée ici plutôt que supposée.
UNITE_VOLUME = "nombre de titres"
CERTITUDE_UNITE = ("présumée — convention du moteur (QteEchangee), non "
                   "enregistrée dans la chandelle elle-même")


def empreinte(chemin: Path) -> str:
    h = hashlib.sha256()
    with open(chemin, "rb") as f:
        for bloc in iter(lambda: f.read(65536), b""):
            h.update(bloc)
    return h.hexdigest()


def mediane(valeurs: list) -> float | None:
    """Médiane au sens strict : moyenne des deux centrales si le nombre est pair.

    ⚠️ `sorted(v)[len(v)//2]` n'est PAS la médiane sur un effectif pair. C'est
    l'erreur qui a produit quatre chiffres faux dans le premier inventaire.
    """
    return statistics.median(valeurs) if valeurs else None


def jours_ouvres(debut: str, fin: str) -> list:
    """Calendrier ATTENDU, hors week-ends et fériés à date fixe.

    ⚠️ Approximation assumée : les fériés marocains suivent en partie le
    calendrier lunaire et le projet ne maintient pas leur liste. Un « trou »
    signalé ici peut donc être un férié mobile, et non une séance manquante.
    La grandeur est publiée avec cette réserve, pas comme un décompte d'erreurs.
    """
    d0 = date.fromisoformat(debut)
    d1 = date.fromisoformat(fin)
    out, d = [], d0
    while d <= d1:
        iso = d.isoformat()
        if d.weekday() < 5 and not est_ferie_fixe(iso):
            out.append(iso)
        d += timedelta(days=1)
    return out


def inventorier_serie(ticker: str) -> dict:
    f = CANDLES / f"{ticker}.json"
    if not f.exists():
        return {"ticker": ticker, "fichier": None, "etat": "aucune série"}

    serie = json.loads(f.read_text(encoding="utf-8"))
    dates = [str(b.get("d") or "")[:10] for b in serie]
    vols = [b.get("v") for b in serie]

    fen = serie[-FENETRE_ACTIVITE:]
    v_fen = [(b.get("v") or 0) for b in fen]

    attendus = jours_ouvres(dates[0], dates[-1]) if dates else []
    presents = set(dates)
    trous = [d for d in attendus if d not in presents]

    return {
        "ticker": ticker,
        "isin": ISIN_MAP.get(ticker),
        "secteur": COMPANY_SECTORS.get(ticker),
        "masi1": ticker in TICKERS_ACTIFS,
        "fichier": str(f.relative_to(RACINE)),
        "empreinte_sha256": empreinte(f),
        "lignes_presentes": len(serie),
        "premiere_date": dates[0] if dates else None,
        "derniere_date": dates[-1] if dates else None,
        "dates_en_double": len(dates) - len(set(dates)),
        "dates_desordonnees": dates != sorted(dates),
        "volume": {
            "unite": UNITE_VOLUME,
            "certitude_unite": CERTITUDE_UNITE,
            "inconnus": sum(1 for v in vols if v is None),
            "nuls": sum(1 for v in vols if v == 0),
            "positifs": sum(1 for v in vols if isinstance(v, (int, float)) and v > 0),
            "part_seances_sans_volume": round(
                sum(1 for v in vols if not v) / len(vols), 4) if vols else None,
            "fenetre": FENETRE_ACTIVITE,
            "formule": "statistics.median sur les N dernières lignes présentes, "
                       "valeurs absentes comptées comme 0",
            "mediane_fenetre": mediane(v_fen),
            "lignes_dans_la_fenetre": len(fen),
        },
        "calendrier": {
            "jours_ouvres_attendus": len(attendus),
            "trous": len(trous),
            "reserve": "les fériés mobiles ne sont pas au calendrier : un trou "
                       "peut être un jour férié, pas une séance manquante",
        },
        "operations_sur_titres": SPLITS.get(ticker, []),
        "suspension": SUSPENSIONS.get(ticker, []),
    }


def inventorier() -> dict:
    series = [inventorier_serie(t) for t in sorted(TICKERS_ALL)]
    avec = [s for s in series if s.get("lignes_presentes")]
    prof = sorted(s["lignes_presentes"] for s in avec)
    faits = json.loads((RACINE / "pipeline" / "faits_financiers.json")
                       .read_text(encoding="utf-8"))
    bpa = json.loads((RACINE / "bpa.json").read_text(encoding="utf-8"))
    verifies = sorted(k for k in faits if not k.startswith("_"))

    return {
        "_quoi": "Inventaire calculé, jamais recopié. Toute grandeur porte sa "
                 "définition ; un désaccord se règle sur la formule.",
        "univers": len(TICKERS_ALL),
        "masi1": len(TICKERS_ACTIFS),
        "series_presentes": len(avec),
        "series_absentes": sorted(s["ticker"] for s in series
                                  if not s.get("lignes_presentes")),
        "profondeur": {
            "min": prof[0] if prof else None,
            "mediane": mediane(prof),
            "max": prof[-1] if prof else None,
            "au_moins_250": sum(1 for n in prof if n >= 250),
            "au_moins_500": sum(1 for n in prof if n >= 500),
        },
        "fondamentaux_source_primaire": verifies,
        "dividendes_sur_resolution_ag": sorted(
            t for t, e in bpa.items()
            if "ésolution" in (e.get("div_source") or "")),
        "series": series,
    }


def en_markdown(inv: dict) -> str:
    L = []
    w = L.append
    w("# Inventaire des données — calculé\n")
    w("Produit par `pipeline/inventaire.py`. **Aucun chiffre n'est recopié.**")
    w("Chaque grandeur porte sa définition ; un désaccord se règle sur la")
    w("formule, pas sur le résultat.\n")
    w("⚠️ Le premier inventaire, écrit à la main, portait quatre volumes")
    w("médians faux : `sorted(v)[len(v)//2]` rend l'élément supérieur du")
    w("milieu, pas la médiane. Sur un effectif pair, la médiane est la MOYENNE")
    w("des deux valeurs centrales.\n")
    p = inv["profondeur"]
    w("## Vue d'ensemble\n")
    w(f"- univers : **{inv['univers']} titres**, dont {inv['masi1']} au MASI 1")
    w(f"- séries présentes : **{inv['series_presentes']}**")
    if inv["series_absentes"]:
        w(f"- sans série : {', '.join(inv['series_absentes'])}")
    w(f"- profondeur : min **{p['min']}**, médiane **{p['mediane']}**, "
      f"max **{p['max']}** lignes")
    w(f"- au moins 250 lignes : **{p['au_moins_250']}** · "
      f"au moins 500 : **{p['au_moins_500']}**")
    w(f"- fondamentaux relus en source primaire : "
      f"**{len(inv['fondamentaux_source_primaire'])}** "
      f"({' '.join(inv['fondamentaux_source_primaire'])})")
    w(f"- dividendes sur résolution d'assemblée : "
      f"**{len(inv['dividendes_sur_resolution_ag'])}**\n")
    w(f"## Volume — unité et certitude\n")
    w(f"- unité retenue : **{UNITE_VOLUME}**")
    w(f"- certitude : *{CERTITUDE_UNITE}*")
    w(f"- fenêtre d'activité : **{FENETRE_ACTIVITE}** dernières lignes présentes")
    w(f"- formule : `statistics.median`, valeurs absentes comptées comme 0\n")
    w("## Séries\n")
    w("| Titre | Secteur | Lignes | Première | Dernière | Médiane vol. | "
      "Sans vol. | Trous |")
    w("|---|---|---:|---|---|---:|---:|---:|")
    for s in inv["series"]:
        if not s.get("lignes_presentes"):
            continue
        v = s["volume"]
        w(f"| {s['ticker']} | {s['secteur'] or '—'} | {s['lignes_presentes']} | "
          f"{s['premiere_date']} | {s['derniere_date']} | "
          f"{v['mediane_fenetre']:,.1f} | "
          f"{v['part_seances_sans_volume']:.0%} | {s['calendrier']['trous']} |"
          .replace(",", " "))
    return "\n".join(L) + "\n"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--json", type=Path)
    ap.add_argument("--markdown", type=Path)
    a = ap.parse_args()
    inv = inventorier()
    if a.json:
        a.json.write_text(json.dumps(inv, ensure_ascii=False, indent=2),
                          encoding="utf-8")
        print(f"→ {a.json}")
    if a.markdown:
        a.markdown.write_text(en_markdown(inv), encoding="utf-8")
        print(f"→ {a.markdown}")
    if not a.json and not a.markdown:
        print(en_markdown(inv))


if __name__ == "__main__":
    main()
