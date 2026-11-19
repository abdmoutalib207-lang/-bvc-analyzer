#!/usr/bin/env python3
"""Mesure du Score BVC TEL QU'AFFICHÉ : une observation par titre et par SEMAINE close.

    python3 pipeline/backtest_score_bvc_hebdo.py [--jusqu-au AAAA-MM-JJ]
        [--roe-depuis datasets/backtests/score_bvc_hebdo_AAAA-MM-JJ.json]
        [--controle-affichage] [--sortie DOSSIER]

Sortie : `datasets/backtests/score_bvc_hebdo_AAAA-MM-JJ.json` (date de la dernière
séance des chandelles). Aucun réseau. R8 : ce script MESURE, il ne change ni
facteur, ni poids, ni seuil.

POURQUOI CE SCRIPT (audits externes du 19/11/2026, GPT M1 et Manus MJ-7)
  L'artefact `score_bvc_2026-11-03.json` porte sur le score QUOTIDIEN, une
  observation par titre ÉCHANGÉ ET PAR SÉANCE, et son titre publié (43 031
  observations) est la variante SANS rentabilité (`resultats.sans_rentabilite`,
  score renormalisé sur les facteurs disponibles, soit 85 points sur 100). Or le
  terminal affiche depuis le 17/11 le score de la SEMAINE CLOSE, ROE compris
  (`score_bvc.py::score_titre_bvc_semaine`).

CE QUE CE SCRIPT MESURE
  Observation   un titre ÉCHANGÉ à la dernière séance d'une semaine close (celle
                que `score_bvc.fin_de_semaine_close` désigne), score calculé sur
                la série arrêtée à cette clôture (les lignes du panel de
                `backtest_score_descriptif.py` ne lisent que les bougies jusqu'à
                la date). Entrée à cette clôture, sortie 20 séances du
                calendrier plus tard, mêmes règles que le quotidien : rendement
                total (dividendes réinvestis), frais 2 % aller-retour, alpha
                contre le MASI, fenêtres rompues écartées et comptées.
  Principal     le titre a échangé à la clôture de la semaine.
  Sensibilité   la dernière séance ÉCHANGÉE du titre dans la semaine (le terminal
                juge « chaque titre sur SA dernière clôture ») ; l'entrée est
                alors cette clôture-là.
  Variantes ROE `sans_rentabilite` (point-in-time, score renormalisé sur les
                facteurs connus) et `avec_roe_actuel` (ROE 2025 de `data.json`
                appliqué à TOUTES les dates). ⚠️ BIAIS D'ANTICIPATION de la
                seconde : le ROE de l'exercice 2025 n'était pas connu en 2023,
                2024 ni avant ses dépôts de 2026. Borne, non performance
                atteignable. Le terminal affiche, lui, le ROE connu AUJOURD'HUI :
                c'est la variante `avec_roe_actuel` qui lui ressemble, mais
                sa mesure rétrospective est la plus biaisée des deux.

SEUIL D'EFFECTIF — ÉCRIT AVANT D'AVOIR VU LES RÉSULTATS
  Une fréquence n'est PUBLIABLE pour une tranche que si : n ≥ 300 observations
  ET ≥ 30 blocs de 20 séances touchés (une centaine de semaines donnent au plus
  ~40 fenêtres indépendantes ; deux semaines consécutives se chevauchent sur 15
  séances de 20). Sous ce seuil la tranche est publiée avec la mention
  « effectif insuffisant ». Le seuil plus faible du code partagé (30 obs., 20
  dates, 10 blocs) ne gouverne que l'affichage des tests t (`conclusion_autorisee`).
  L'intervalle de Wilson est calculé sur n observations COMME SI elles étaient
  indépendantes : il est donc TROP ÉTROIT (titres d'une même date corrélés,
  fenêtres chevauchantes). L'intervalle à retenir est celui du bootstrap par
  blocs (`frequence_ic95_blocs`) ; Wilson est donné parce qu'il est demandé et
  recalculable.

LIMITES (héritées, voir `score_bvc_2026-11-03.json::limites`) : un seul cycle de
~3 ans ; biais du survivant (univers = titres cotés aujourd'hui) ; MASI indice de
cours contre rendement total des titres ; entrée à la clôture du signal ; aucun
test corrigé de la multiplicité (4 tranches × 2 variantes × 2 définitions).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import platform
import subprocess
import sys
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))
sys.path.insert(0, str(RACINE / "pipeline"))

import backtest_score_descriptif as bs  # noqa: E402
import backtest_score_bvc as bb  # noqa: E402
from pipeline import score_bvc as sb  # noqa: E402

COMMANDE = "python3 pipeline/backtest_score_bvc_hebdo.py"
SEUIL_N, SEUIL_BLOCS = 300, 30
CODE = ("pipeline/backtest_score_bvc_hebdo.py", "pipeline/backtest_score_bvc.py", "pipeline/score_bvc.py",
        "pipeline/backtest_score_descriptif.py", "pipeline/score_descriptif.py",
        "pipeline/technical/serie_propre.py", "bvc_config.py")
FICHIERS = ("pipeline/masi_history.json", "datasets/dividendes_bvc.json", "fondamentaux.json")


def _digest_json(obj) -> str:
    return bs._sha_octets(json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode())


def wilson(k: int, n: int, z: float = 1.96) -> list:
    if n <= 0:
        return [None, None]
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return [round(c - h, 4), round(c + h, 4)]


def fins_de_semaine(bougies: dict) -> list:
    """Les fins de semaine closes, par la fonction MÊME du produit."""
    seances = sb.seances_du_marche(list(bougies.values()))
    out, vus = [], set()
    d0 = date.fromisoformat(seances[0])
    d1 = date.fromisoformat(seances[-1])
    lundi = d0 - timedelta(days=d0.weekday())
    derniere_close = sb.fin_de_semaine_close(seances, seances[-1])   # la semaine en cours n'est pas close
    while lundi <= d1:
        samedi = (lundi + timedelta(days=5)).isoformat()
        f = sb.fin_de_semaine_close(seances, samedi)
        if f and f <= derniere_close and f not in vus and lundi.isoformat() <= f < (lundi + timedelta(days=7)).isoformat():
            vus.add(f)
            out.append(f)
        lundi += timedelta(days=7)
    return out


def tranches_enrichies(res: dict) -> None:
    """Ajoute à chaque tranche : Wilson, publiabilité (seuil du docstring)."""
    for nom, l in res["tranches"].items():
        n = l.get("n", 0)
        k = round((l.get("frequence_surperformance") or 0) * n)
        l["gagnants"] = int(k)
        l["frequence_wilson95_naif"] = wilson(int(k), n)
        ok = n >= SEUIL_N and (l.get("blocs_de_20_seances_touches") or 0) >= SEUIL_BLOCS
        l["effectif_suffisant"] = bool(ok)
        if not ok:
            l["mention"] = (f"effectif insuffisant (seuil : n ≥ {SEUIL_N} et ≥ {SEUIL_BLOCS} blocs ; "
                            f"ici n = {n}, {l.get('blocs_de_20_seances_touches')} blocs)")


def mesure(E: pd.DataFrame, col: str, cal: list, T: int, tir) -> dict:
    out = {"observations": int(len(E)), "dates_d_entree": int(E["pos"].nunique())}
    t = bs.table(E, col, bs.TRANCHES, T=T, tir=tir)
    tranches_enrichies(t)
    out.update(t)
    out["utilite"] = bs.ic_et_ecart_haut_bas(E, col, 60, 40, "gagne", "ex", T)
    out["par_semestre"] = bs.periodes(E, col, bs.TRANCHES, cal, T, tir)
    return out


def controle_affichage(P: pd.DataFrame, fins: list) -> dict:
    """Le panel rejoue-t-il le score que data.json publie pour la dernière semaine close ?

    Compare `bvc_avec` du panel (ROE de data.json) à `score_bvc.valeur` publié,
    sur les titres dont le cours de la semaine est celui de la clôture `fin`.
    DÉPEND de data.json (sha256 donné) : hors `resultats`."""
    djs = RACINE / "data.json"
    d = json.loads(djs.read_text(encoding="utf-8"))
    fin = max((t.get("score_bvc") or {}).get("semaine", {}).get("fin") or "" for t in d["tickers"])
    ligne = P[P["date"] == fin].set_index("t")
    comp, ecarts = 0, []
    for t in d["tickers"]:
        sbv = t.get("score_bvc") or {}
        if (sbv.get("semaine") or {}).get("cours_du") != fin or sbv.get("valeur") is None:
            continue
        if t["symbol"] not in ligne.index or pd.isna(ligne.loc[t["symbol"], "bvc_avec"]):
            continue
        comp += 1
        ecarts.append((t["symbol"], round(float(ligne.loc[t["symbol"], "bvc_avec"]) - float(sbv["valeur"]), 2)))
    diff = [(s, e) for s, e in ecarts if abs(e) > 0.01]
    return {"fin_de_semaine": fin, "data_json_sha256": bs._sha(djs), "titres_comparés": comp,
            "identiques_au_centieme": comp - len(diff), "ecarts": sorted(diff, key=lambda x: -abs(x[1]))[:15],
            "_lecture": "dépend de data.json du jour ; hors `resultats`"}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--sortie", default=str(bs.SORTIE))
    ap.add_argument("--jusqu-au", default=None, metavar="AAAA-MM-JJ")
    ap.add_argument("--roe-depuis", default=None, metavar="ARTEFACT",
                    help="rejoue avec la table de ROE embarquée dans un artefact (sinon : data.json du jour)")
    ap.add_argument("--controle-affichage", action="store_true")
    a = ap.parse_args(argv)

    bougies = bs.charger_bougies(a.jusqu_au)
    cal = bs.calendrier(bougies)
    T = len(cal)
    masi = bs.masi_serie(a.jusqu_au)
    if a.roe_depuis:
        roes = json.loads(Path(a.roe_depuis).read_text(encoding="utf-8"))["entrees"]["roe_2025_table"]
    else:
        roes = {k: v for k, v in bs.roe_actuels().items()}
    roes = {k: float(roes[k]) for k in sorted(roes)}
    P = bs.construire_panel(bougies, cal, roes, masi, bs.dividendes(), extra=bb.extra_bvc())
    tir = bs._tirages(T)
    fin = cal[-1]

    fins = fins_de_semaine(bougies)
    fins_cal = [f for f in fins if f in set(cal)]
    P["semaine"] = [(date.fromisoformat(d) - timedelta(days=date.fromisoformat(d).weekday())).isoformat()
                    for d in P["date"]]
    sur_fin = P[P["date"].isin(set(fins_cal))]
    # sensibilité : dernière séance échangée du titre dans la semaine close
    sem_close = {(date.fromisoformat(f) - timedelta(days=date.fromisoformat(f).weekday())).isoformat() for f in fins_cal}
    derniere = (P[P["semaine"].isin(sem_close)].sort_values("date").groupby(["t", "semaine"], as_index=False).tail(1))

    res = {}
    for defn, base_df in (("principal_echange_a_la_cloture_de_la_semaine", sur_fin),
                          ("sensibilite_derniere_seance_echangee_de_la_semaine", derniere)):
        bloc = {}
        for nom, col in (("sans_rentabilite", "bvc_sans"), ("avec_roe_actuel", "bvc_avec")):
            E = base_df[base_df["propre"] & base_df[col].notna()]
            bloc[nom] = mesure(E, col, cal, T, tir)
        bloc["avec_roe_actuel"]["_biais"] = ("BIAIS D'ANTICIPATION : ROE 2025 appliqué à toutes les dates. "
                                             "Borne, pas une performance atteignable.")
        res[defn] = bloc

    def cnt(df):
        return {"lignes_titre_x_semaine": int(len(df)),
                "horizon_non_atteint": int(df["horizon_non_atteint"].sum()),
                "sortie_absente": int(df["sortie_absente"].sum()),
                "fenetre_rompue": int(df["fenetre_rompue"].sum()),
                "indicateurs_sur_serie_rompue": int(df["rupture_indic"].sum()),
                "masi_absent": int(df["masi_absent"].sum()),
                "propres": int(df["propre"].sum()),
                "propres_et_score_sans_roe": int((df["propre"] & df["bvc_sans"].notna()).sum()),
                "propres_et_score_avec_roe": int((df["propre"] & df["bvc_avec"].notna()).sum())}

    seances_bg = sb.seances_du_marche(list(bougies.values()))
    code_sha = {c: bs._sha(RACINE / c) for c in CODE}
    ser_trunc = {t: _digest_json(bougies[t]) for t in sorted(bougies)}
    try:
        tete = subprocess.run(["git", "rev-parse", "HEAD"], cwd=RACINE, capture_output=True, text=True).stdout.strip()
    except OSError:
        tete = None
    entrees = {
        "tete_git": tete,
        "versions": {"python": platform.python_version(), "numpy": np.__version__, "pandas": pd.__version__},
        "calendrier": {"seances": T, "du": cal[0], "au": fin},
        "fins_de_semaine": {"semaines_closes": len(fins), "dans_le_calendrier": len(fins_cal),
                            "premiere": fins_cal[0], "derniere": fins_cal[-1],
                            "hors_calendrier": [f for f in fins if f not in set(cal)],
                            "seances_marche_quorum_20": len(seances_bg)},
        "chandelles": {"titres": len(bougies),
                       "seances_titre": int(sum(len(b) for b in bougies.values())),
                       "empreinte_series_tronquees_sha256": _digest_json(ser_trunc),
                       "par_titre_series_tronquees_sha256": ser_trunc,
                       "fichiers_complets_sha256": {t: bs._sha(bs.CANDLES / f"{t}.json") for t in sorted(bougies)}},
        "masi": {"seances": len(masi), "empreinte_serie_tronquee_sha256": _digest_json(masi),
                 "fichier_sha256": bs._sha(RACINE / "pipeline/masi_history.json")},
        "dividendes": {"fichier_sha256": bs._sha(RACINE / "datasets/dividendes_bvc.json")},
        "fondamentaux": {"fichier_sha256": bs._sha(RACINE / "fondamentaux.json"),
                         "_note": "ne sert PAS au score ; listé pour exhaustivité. Le ROE lu est celui de "
                                  "`data.json::ratios_publies.roe_2025`, embarqué ci-dessous."},
        "roe_2025_table": roes,
        "roe_2025_empreinte_sha256": _digest_json(roes),
        "code_sha256": code_sha,
    }
    art = {
        "_quoi": "Mesure du Score BVC tel qu'affiché : une observation par titre et par semaine close",
        "_commande": COMMANDE + f" --jusqu-au {fin}", "_rejeu": (
            f"{COMMANDE} --jusqu-au {fin} --roe-depuis datasets/backtests/score_bvc_hebdo_{fin}.json "
            f"--sortie <dossier> ; `entrees` et `resultats` doivent être identiques à l'octet près "
            f"(le contrôle d'affichage, hors résultats, dépend de data.json)."),
        "version_score": sb.VERSION, "poids": dict(sb.POIDS_BVC), "date_artefact": fin,
        "horizon_seances": bs.HORIZON, "frais_aller_retour": bs.FRAIS_AR, "reference_principale": "MASI",
        "tranches": [t[0] for t in bs.TRANCHES],
        "seuil_effectif_publiable": {"n_min": SEUIL_N, "blocs_de_20_seances_min": SEUIL_BLOCS,
                                     "ecrit": "avant les résultats ; voir docstring du script"},
        "definition": __doc__.split("CE QUE CE SCRIPT MESURE")[1].split("SEUIL D'EFFECTIF")[0].strip(),
        "limites": __doc__.split("LIMITES (héritées")[1].strip(),
        "entrees": entrees,
        "exclusions": {"semaines_principal": cnt(sur_fin), "sensibilite": cnt(derniere)},
        "resultats": res,
    }
    if a.controle_affichage:
        art["controle_fidelite_affichage"] = controle_affichage(P, fins_cal)
    out = Path(a.sortie)
    out.mkdir(parents=True, exist_ok=True)
    f = out / f"score_bvc_hebdo_{fin}.json"
    f.write_text(json.dumps(art, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"✅ {f}  ({f.stat().st_size // 1024} Ko)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
