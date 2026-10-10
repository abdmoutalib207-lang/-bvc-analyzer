#!/usr/bin/env python3
"""Ancienne note fondamentale contre note PAR FAMILLE, sur l'historique publié.

    python3 pipeline/mesure_note_sectorielle.py

Sortie : `datasets/backtest/note_sectorielle_AAAA-MM-JJ.json` (date de la
dernière séance du journal, jamais l'horloge). Aucun réseau.

⚠️ CE QUE CETTE MESURE EST, ET CE QU'ELLE N'EST PAS — écrit AVANT les chiffres
  1. La NOUVELLE note n'a jamais été publiée : elle est REJOUÉE. Pour chaque
     séance du journal `score_history.json`, on la recalcule avec les cours de
     cette séance (PER et P/B relatifs, médianes de famille du jour) mais avec
     les fondamentaux d'AUJOURD'HUI (comptes S1 2026 déposés en septembre).
     C'est de la CONNAISSANCE DU FUTUR pour les séances antérieures à leur
     dépôt : la mesure ne prouve rien sur la capacité de prévoir. Elle compare
     seulement deux grilles, qui souffrent du même biais.
  2. L'ANCIENNE note est celle qui a été réellement publiée chaque jour
     (`score_fond`), fondamentaux de l'époque compris : les deux séries ne
     portent donc pas les mêmes données, ce qui avantage la nouvelle. À lire
     avec la fenêtre « depuis 29/09 », où les fondamentaux calculés existent.
  3. Douze séances (24/09 → 09/10) : UN régime, observations chevauchantes. Le
     backtest du projet exige 20 jours distincts et 10 dates non chevauchantes
     avant toute conclusion ; l'horizon de 20 séances n'est atteint par aucune
     date. Les nombres produits sont DESCRIPTIFS, sans valeur probante.
  4. Mêmes règles que `backtest_reproductible.py` (réutilisé, pas dupliqué) :
     rendement total, alpha contre le MASI, confiance ≥ 2, deux grilles de
     confiance jamais mélangées. Seuls les couples (séance, titre) ayant UNE
     note dans chaque grille sont comparés.

Ce que la Vision Produit demande n'est pas « la note prédit-elle ? » mais « les
fréquences affichées sont-elles justes et utiles ? » : cette mesure ne la
remplace pas, elle dit seulement si la nouvelle grille classe les titres
autrement que l'ancienne sur les séances disponibles.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))
sys.path.insert(0, str(RACINE / "pipeline"))

import backtest_reproductible as br  # noqa: E402
from bvc_config import SANS_COMPTES, TICKERS_ALL, est_suspendu  # noqa: E402
from pipeline.smart_money import fond_score_sectoriel as fs  # noqa: E402

DEPUIS = "2026-09-29"       # première séance où les fondamentaux calculés existent


def lignes_journal(racine: Path = RACINE) -> tuple[list[dict], str, str]:
    d = json.loads((racine / "pipeline" / "score_history.json").read_text(encoding="utf-8"))
    ix = {c: i for i, c in enumerate(d["_colonnes"])}
    out = []
    for date in sorted(d["seances"]):
        for r in d["seances"][date]["tickers"]:
            g = lambda c: r[ix[c]] if ix[c] < len(r) else None  # noqa: E731
            out.append({"date": date, "t": g("symbol"), "fond": g("score_fond"), "sig": g("sig"),
                        "conf": g("conf"), "asof": g("prix_asof"), "prix": g("prix")})
    dates = sorted(d["seances"])
    return out, dates[0], dates[-1]


def notes_rejouees(lignes: list[dict], racine: Path = RACINE) -> dict:
    """{(date, titre): note par famille}, cours du jour, fondamentaux d'aujourd'hui."""
    import update_data as u                      # `_pb_sourcé`, la même fonction que le moteur
    src = fs.charger_sources(racine)
    u.FAITS_DATA = src["faits"]
    par_date: dict[str, dict] = {}
    for l in lignes:
        par_date.setdefault(l["date"], {})[l["t"]] = l
    out = {}
    for date, jour in par_date.items():
        prix = {t: l["prix"] for t, l in jour.items() if l["prix"] and l["asof"] == date}
        pb = {t: u._pb_sourcé(t, p) for t, p in prix.items()}
        res = fs.noter_univers(TICKERS_ALL, prix, pb, src["fondamentaux"], src["bpa"], src["s1"],
                               src["faits"], sans_comptes=set(SANS_COMPTES),
                               suspendus={t for t in TICKERS_ALL if est_suspendu(t, date)})
        for t, r in res.items():
            out[(date, t)] = r["note"]
    return out


def construire(racine: Path = RACINE) -> dict:
    lignes, premiere, derniere = lignes_journal(racine)
    nouvelles = notes_rejouees(lignes, racine)
    communs = [l for l in lignes if l["fond"] is not None and nouvelles.get((l["date"], l["t"])) is not None]
    candles = racine / "pipeline" / "candles"
    masi = br._masi()
    res = {"_quoi": "Ancienne note fondamentale (publiée) contre note par famille (REJOUÉE) — mesure descriptive",
           "_methode": __doc__.strip(),
           "entrees": {"premiere_seance": premiere, "derniere_seance": derniere,
                       "lignes_du_journal": len(lignes), "couples_avec_les_deux_notes": len(communs),
                       "fenetre_fondamentaux_calcules_depuis": DEPUIS,
                       "sha256": {"score_history": br._sha(racine / "pipeline" / "score_history.json"),
                                  "fondamentaux": br._sha(racine / "fondamentaux.json"),
                                  "bpa": br._sha(racine / "bpa.json")},
                       "commit_git": (br._git("rev-parse", "HEAD") or "").strip() or None},
           "resultats": {}}
    for nom, depuis in (("toutes_les_seances", None), ("depuis_29_09", DEPUIS)):
        bloc = {}
        for grille_nom, cle in (("ancienne_publiee", "fond"), ("par_famille_rejouee", "nouvelle")):
            notes = [{"date": l["date"], "t": l["t"],
                      "v53": l["fond"] if cle == "fond" else nouvelles[(l["date"], l["t"])],
                      "sig": l["sig"], "conf": l["conf"], "asof": l["asof"]}
                     for l in communs if depuis is None or l["date"] >= depuis]
            df, ecarts = br.observations(notes, candles, masi)
            bloc[grille_nom] = {"observations_ecartees": ecarts, "notes_retenues": int(len(df)), "grilles": {}}
            for g in ("v1", "v2"):
                sous = df[df["grille"] == g]
                bloc[grille_nom]["grilles"][g] = {
                    "notes_retenues": int(len(sous)),
                    **{f"h{h}": {k: v for k, v in br.mesurer_grille(sous, h).items() if k != "par_palier"}
                       for h in br.HORIZONS}}
        res["resultats"][nom] = bloc
    return res


def main() -> int:
    res = construire()
    sortie = RACINE / "datasets" / "backtest"
    sortie.mkdir(parents=True, exist_ok=True)
    p = sortie / f"note_sectorielle_{res['entrees']['derniere_seance']}.json"
    p.write_text(json.dumps(res, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(p)
    for fen, bloc in res["resultats"].items():
        for nom, b in bloc.items():
            for g, x in b["grilles"].items():
                h5 = x["h5"]
                ic, dec = h5["correlation_rang_note_alpha"], h5["ecart_decile_haut_moins_bas_alpha"]
                print(f"{fen:20} {nom:20} {g} h5 : {h5['observations']:4} obs, {h5['jours']} jours, "
                      f"IC {ic['moyenne']}, écart déciles {dec['moyenne']} — {ic['lecture']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
