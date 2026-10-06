#!/usr/bin/env python3
"""Backtest reproductible : UNE commande, un artefact daté, aucun réseau.

    python3 pipeline/backtest_reproductible.py            # notes de score_history.json
    python3 pipeline/backtest_reproductible.py --source git   # + archéologie de data.json

Sortie : `datasets/backtest/backtest_AAAA-MM-JJ.json` et `.md`, où la date est
celle de la DERNIÈRE SÉANCE des entrées (jamais l'horloge) : deux exécutions
sur les mêmes entrées donnent le même fichier, à l'octet près. Le fichier
JSON porte le sha256 de chaque entrée lue et le commit git.

⚠️ CE QUI EST MESURÉ : LES NOTES PUBLIÉES, PAS REJOUÉES
Le journal `score_history.json` (ou, avec --source git, le dernier commit de
chaque jour sur `data.json`) dit ce que le terminal AFFICHAIT. Rien n'est
recalculé : les fondamentaux sont figés à leur valeur actuelle, les rejouer
sur le passé donnerait au modèle la connaissance du futur.

⚠️ RÈGLES ÉCRITES AVANT LES RÉSULTATS (pré-enregistrées, jamais retouchées)
  - Rendement : TOTAL (cours + dividende à la date de détachement,
    `datasets/dividendes_bvc.json`), de la clôture du jour de publication à la
    clôture h séances plus tard, h = 5 et 20, séances du calendrier du MASI.
  - Alpha = rendement total du titre − variation du MASI sur les mêmes dates.
  - Frais : 2 % aller-retour, déduits du rendement de tout titre « acheté ».
  - Sont écartés, et COMPTÉS : confiance < 2 ou signal « Données
    insuffisantes » ; cours de la note d'une autre séance que celle de la
    publication (`prix_asof`) ; clôture absente à l'entrée ou à la sortie ;
    fenêtre contenant une rupture de série > ±50 % (opération non déclarée).
  - Corrélation de rang : Spearman note → alpha, JOUR PAR JOUR, puis moyenne
    des jours (IC). Écart décile haut − bas : par jour (décile = n // 10
    titres, classés par note puis symbole), puis moyenne.
  - « Bon sens » : ACHETER → alpha net de frais > 0 ; ÉVITER (et ÉVITER FORT)
    → alpha < 0 ; SURVEILLER et ATTENDRE n'annoncent pas de sens : seule la
    part d'alpha > 0 est publiée.
  - Deux grilles de confiance, JAMAIS dans un même chiffre : « v1 » avant le
    06/10/2026, « v2 » à partir du 06/10/2026 (date de la publication).
  - t : trois valeurs sur la série des moyennes JOURNALIÈRES — naïf,
    Newey-West (Bartlett, retard h−1) et sous-échantillon non chevauchant
    (une date sur h). RETENU : Newey-West. Aucune conclusion sous 20 jours
    distincts OU sous 10 dates non chevauchantes : le texte dit alors
    « insuffisant », quel que soit le t (Newey-West sur une vingtaine de jours
    sous-estime l'incertitude ; la deuxième condition empêche d'y croire seul).

⚠️ LIMITES, AVANT LES RÉSULTATS
  1. Un seul régime de marché, quelques semaines : `score_history.json`
     commence le 24/09/2026. --source git remonte au 10/08 (début de `_meta`).
  2. Observations CHEVAUCHANTES : à 20 séances, deux jours voisins partagent
     19 séances. D'où Newey-West et le sous-échantillon ; ni l'un ni l'autre ne
     rend fiable un t calculé sur peu de jours.
  3. Le MASI est un indice de COURS ; les titres sont en rendement TOTAL. Le
     biais favorise les titres, il n'est pas chiffré ici.
  4. Plusieurs versions du score (`score_version`) et deux pondérations
     (25/09, 29/09) traversent l'échantillon : non séparées, listées dans
     `entrees.versions_score`.
  5. Entrée à la clôture du jour de publication, comme `backtest.py` : un
     lecteur agit le lendemain à un cours inconnu. Léger optimisme.
  6. Aucune fourchette, aucun impact de marché ; la liquidité n'est que
     décrite (montant médian échangé des titres ACHETER).
  7. Dividendes : 2025-2026 pour tous, 2024 pour Immorente seulement.
  8. La date de bascule de la grille de confiance (06/10/2026) vient de la
     demande du chantier ; elle n'est écrite nulle part dans le dépôt.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))
sys.path.insert(0, str(RACINE / "pipeline"))

from calibrage_signaux import _dividendes, _masi  # noqa: E402  (réutilisé, pas dupliqué)

HORIZONS = (5, 20)
FRAIS_AR = 0.02
GRILLE_V2 = "2026-10-06"
CONFIANCE_MIN = 2
MIN_JOURS = 20
MIN_DATES_INDEP = 10
RUPTURE = 0.5
SORTIE = RACINE / "datasets" / "backtest"
PALIERS = ("ACHETER", "SURVEILLER", "ATTENDRE", "ÉVITER")
ENTREES = {"score_history": "pipeline/score_history.json",
           "masi": "pipeline/masi_history.json",
           "dividendes": "datasets/dividendes_bvc.json"}
CODE = ("pipeline/backtest_reproductible.py", "pipeline/calibrage_signaux.py")


# ───────────────────────────── entrées ─────────────────────────────

def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def _git(*args) -> str | None:
    try:
        r = subprocess.run(["git", *args], capture_output=True, text=True,
                           cwd=RACINE, check=True)
        return r.stdout
    except (OSError, subprocess.CalledProcessError):
        return None


def palier(sig) -> str | None:
    s = (sig or "").strip().upper()
    for p in PALIERS:
        if s.startswith(p):
            return p
    return None


def grille(date: str) -> str:
    return "v2" if date >= GRILLE_V2 else "v1"


def notes_score_history(chemin: Path) -> tuple[list[dict], dict]:
    """Les lignes du journal : [{date, t, v53, sig, conf, asof}]."""
    d = json.loads(chemin.read_text(encoding="utf-8"))
    cols = d["_colonnes"]
    ix = {c: i for i, c in enumerate(cols)}
    out, versions = [], {}
    for date in sorted(d["seances"]):
        s = d["seances"][date]
        versions[date] = s.get("score_version")
        for r in s["tickers"]:
            g = lambda c: r[ix[c]] if ix[c] < len(r) else None  # noqa: E731
            out.append({"date": date, "t": g("symbol"), "v53": g("v53"),
                        "sig": g("sig"), "conf": g("conf"), "asof": g("prix_asof")})
    return out, versions


def notes_git() -> tuple[list[dict], dict, dict]:
    """Dernier commit de chaque jour sur data.json (HEAD), lu hors réseau."""
    log = (_git("log", "HEAD", "--format=%H %ad", "--date=format:%Y-%m-%d",
                "--", "data.json") or "").splitlines()
    par_jour: dict[str, str] = {}
    for ligne in log:
        h, _, d = ligne.partition(" ")
        par_jour.setdefault(d.strip(), h)
    out, versions = [], {}
    for date in sorted(par_jour):
        try:
            flux = json.loads(_git("show", f"{par_jour[date]}:data.json") or "")
        except ValueError:
            continue
        versions[date] = flux.get("score_version")
        for x in flux.get("tickers") or []:
            v = x.get("v53")
            if x.get("symbol") and isinstance(v, (int, float)) and not isinstance(v, bool):
                m = x.get("_meta") or {}
                out.append({"date": date, "t": x["symbol"], "v53": float(v), "sig": x.get("sig"),
                            "conf": m.get("confidence"), "asof": m.get("prix_asof")})
    return out, versions, par_jour


def indice_total(t: str, dossier: Path) -> pd.DataFrame | None:
    """Clôture et indice de rendement total d'un titre, indexés par date."""
    f = dossier / f"{t}.json"
    if not f.exists():
        return None
    df = pd.DataFrame(json.loads(f.read_text(encoding="utf-8")))
    if df.empty or "c" not in df:
        return None
    df["date"] = pd.to_datetime(df["d"])
    df = df.sort_values("date").drop_duplicates("date").reset_index(drop=True)
    c = df["c"].astype(float)
    div = pd.Series(0.0, index=df.index)
    for e in _dividendes().get(t, []):
        k = df.index[df["date"] >= pd.Timestamp(e["detachement"])]
        if len(k):
            div[k[0]] += e["montant_ajuste_split"]
    df["tr"] = ((c + div) / c.shift(1)).fillna(1.0).cumprod()
    df["rup"] = (c / c.shift(1) - 1).abs() > RUPTURE
    v = df["v"].fillna(0).astype(float) if "v" in df else pd.Series(0.0, index=df.index)
    df["montant"] = (c * v).where(v > 0).rolling(60, min_periods=10).median()
    df["c"] = c
    return df.set_index("date")


# ───────────────────────────── statistiques ─────────────────────────────

def t_serie(x: list[float], h: int) -> dict:
    """Moyenne et trois t d'une série de moyennes journalières."""
    a = np.asarray(x, dtype=float)
    T = len(a)
    out = {"n_jours": T, "moyenne": None, "t_naif": None,
           "t_newey_west": None, "t_non_chevauchant": None, "n_non_chevauchant": 0}
    if T == 0:
        return out
    out["moyenne"] = float(a.mean())
    if T > 1 and a.std(ddof=1) > 0:
        out["t_naif"] = float(a.mean() / (a.std(ddof=1) / math.sqrt(T)))
    e = a - a.mean()
    g0 = float(e @ e) / T
    v = g0
    for lag in range(1, min(h - 1, T - 1) + 1):
        v += 2 * (1 - lag / h) * float(e[lag:] @ e[:-lag]) / T
    if T > 1 and v > 0:
        out["t_newey_west"] = float(a.mean() / math.sqrt(v / T))
    s = a[::h]
    out["n_non_chevauchant"] = len(s)
    if len(s) > 1 and s.std(ddof=1) > 0:
        out["t_non_chevauchant"] = float(s.mean() / (s.std(ddof=1) / math.sqrt(len(s))))
    return out


def _r(v, n=6):
    return None if v is None or (isinstance(v, float) and math.isnan(v)) else round(float(v), n)


def _bloc_t(x: list[float], h: int) -> dict:
    s = t_serie(x, h)
    ok = s["n_jours"] >= MIN_JOURS and s["n_non_chevauchant"] >= MIN_DATES_INDEP
    return {"n_jours": s["n_jours"], "moyenne": _r(s["moyenne"]),
            "t_naif": _r(s["t_naif"], 3), "t_newey_west": _r(s["t_newey_west"], 3),
            "t_non_chevauchant": _r(s["t_non_chevauchant"], 3),
            "n_dates_non_chevauchantes": s["n_non_chevauchant"],
            "t_retenu": "newey_west",
            "conclusion_autorisee": ok,
            "lecture": (_r(s["t_newey_west"], 2) if ok else
                        f"insuffisant : {s['n_jours']} jours (min {MIN_JOURS}), "
                        f"{s['n_non_chevauchant']} dates non chevauchantes (min {MIN_DATES_INDEP})")}


# ───────────────────────────── observations ─────────────────────────────

def observations(notes: list[dict], dossier: Path, masi: pd.Series) -> tuple[pd.DataFrame, dict]:
    cal = list(masi.index)
    pos = {d: i for i, d in enumerate(cal)}
    cache: dict[str, pd.DataFrame | None] = {}
    ecarts = {"confiance_insuffisante": 0, "signal_sans_palier": 0, "cours_d_une_autre_seance": 0,
              "titre_sans_chandelles": 0, "cloture_absente": 0, "fenetre_sans_masi": 0,
              "rupture_de_serie": 0, "horizon_non_atteint": {f"h{h}": 0 for h in HORIZONS}}
    lignes = []
    for n in notes:
        p = palier(n["sig"])
        if n["conf"] is None or n["conf"] < CONFIANCE_MIN or (n["sig"] or "").startswith("Données"):
            ecarts["confiance_insuffisante"] += 1
            continue
        if p is None:
            ecarts["signal_sans_palier"] += 1
            continue
        if n["asof"] != n["date"]:
            ecarts["cours_d_une_autre_seance"] += 1
            continue
        if n["t"] not in cache:
            cache[n["t"]] = indice_total(n["t"], dossier)
        df = cache[n["t"]]
        d0 = pd.Timestamp(n["date"])
        if df is None:
            ecarts["titre_sans_chandelles"] += 1
            continue
        if d0 not in df.index or d0 not in pos:
            ecarts["cloture_absente"] += 1
            continue
        base = {"date": n["date"], "t": n["t"], "v53": n["v53"], "palier": p,
                "grille": grille(n["date"]), "montant": df.at[d0, "montant"]}
        for h in HORIZONS:
            j = pos[d0] + h
            if j >= len(cal):
                ecarts["horizon_non_atteint"][f"h{h}"] += 1
                continue
            d1 = cal[j]
            if d1 not in df.index:
                ecarts["cloture_absente"] += 1
                continue
            if df.loc[d0:d1, "rup"].iloc[1:].any():
                ecarts["rupture_de_serie"] += 1
                continue
            r = df.at[d1, "tr"] / df.at[d0, "tr"] - 1
            rm = masi.iloc[j] / masi.iloc[pos[d0]] - 1
            base[f"r{h}"], base[f"a{h}"] = float(r), float(r - rm)
        lignes.append(base)
    cols = ["date", "t", "v53", "palier", "grille", "montant"] + [f"{k}{h}" for h in HORIZONS for k in "ra"]
    return pd.DataFrame(lignes, columns=cols), ecarts


def _quotidien(df: pd.DataFrame, h: int, f) -> list[float]:
    """f(sous-DataFrame d'un jour) → nombre ; None ignoré. Jours triés."""
    out = []
    for _, g in df.dropna(subset=[f"a{h}"]).sort_values("date").groupby("date", sort=True):
        v = f(g)
        if v is not None and not (isinstance(v, float) and math.isnan(v)):
            out.append(float(v))
    return out


def _ic(g: pd.DataFrame, h: int):
    if len(g) < 10 or g["v53"].nunique() < 2:
        return None
    return g["v53"].rank().corr(g[f"a{h}"].rank())


def _decile(g: pd.DataFrame, h: int):
    if len(g) < 20:
        return None
    k = len(g) // 10
    s = g.sort_values(["v53", "t"])
    return s[f"a{h}"].iloc[-k:].mean() - s[f"a{h}"].iloc[:k].mean()


def mesurer_grille(df: pd.DataFrame, h: int) -> dict:
    d = df.dropna(subset=[f"a{h}"])
    res = {"observations": int(len(d)), "jours": int(d["date"].nunique()),
           "titres": int(d["t"].nunique())}
    ic = _quotidien(d, h, lambda g: _ic(g, h))
    dec = _quotidien(d, h, lambda g: _decile(g, h))
    res["correlation_rang_note_alpha"] = _bloc_t(ic, h)
    res["ecart_decile_haut_moins_bas_alpha"] = _bloc_t(dec, h)
    par = {}
    for p in PALIERS:
        s = d[d["palier"] == p]
        e = {"observations": int(len(s)), "jours": int(s["date"].nunique()),
             "titres": int(s["t"].nunique())}
        if len(s):
            e["alpha_moyen_brut"] = _r(s[f"a{h}"].mean())
            e["alpha_moyen_net_frais"] = _r(s[f"a{h}"].mean() - FRAIS_AR)
            e["rendement_total_net_frais_moyen"] = _r(s[f"r{h}"].mean() - FRAIS_AR)
            if p == "ACHETER":
                e["bon_sens"] = _r((s[f"a{h}"] - FRAIS_AR > 0).mean(), 4)
                e["montant_median_echange_dh"] = _r(s["montant"].median(), 0)
            elif p == "ÉVITER":
                e["bon_sens"] = _r((s[f"a{h}"] < 0).mean(), 4)
            else:
                e["bon_sens"] = None
                e["part_alpha_positif"] = _r((s[f"a{h}"] > 0).mean(), 4)
            e["alpha_journalier"] = _bloc_t(_quotidien(s, h, lambda g: g[f"a{h}"].mean()), h)
        par[p] = e
    res["par_palier"] = par
    return res


# ───────────────────────────── assemblage ─────────────────────────────

def construire(source: str = "score_history", racine: Path | None = None) -> dict:
    racine = racine or RACINE
    fichiers = {k: racine / v for k, v in ENTREES.items()}
    candles = racine / "pipeline" / "candles"
    empreintes = {k: _sha(p) for k, p in fichiers.items()}
    empreintes["candles"] = {p.name: _sha(p) for p in sorted(candles.glob("*.json"))}
    empreintes["code"] = {c: _sha(racine / c) for c in CODE}
    versions, commits_jours = {}, None
    if source == "git":
        notes, versions, commits_jours = notes_git()
    else:
        notes, versions = notes_score_history(fichiers["score_history"])
    seances = sorted({n["date"] for n in notes})
    masi = _masi()
    df, ecarts = observations(notes, candles, masi)
    entrees = {"source_des_notes": source,
               "commit_git": (_git("rev-parse", "HEAD") or "").strip() or None,
               "sha256": empreintes,
               "premiere_seance": seances[0] if seances else None,
               "derniere_seance": seances[-1] if seances else None,
               "seances_publiees": len(seances), "notes_lues": len(notes),
               "versions_score": versions}
    if commits_jours is not None:
        entrees["commits_par_jour"] = dict(sorted(commits_jours.items()))
    res = {"_quoi": "Backtest reproductible des notes PUBLIÉES — mesure, pas promesse",
           "_methode": __doc__.strip(),
           "limites_ecrites_avant_les_resultats": [
               "Un seul régime de marché, quelques semaines d'historique de notes.",
               "Observations chevauchantes : t naïf surestimé, Newey-West retenu.",
               "MASI en cours seuls contre titres en rendement total : biais favorable aux titres, non chiffré.",
               "Plusieurs versions du score et deux pondérations dans l'échantillon, non séparées.",
               "Entrée à la clôture du jour de publication ; aucune fourchette ni impact de marché.",
               "Grille de confiance : v1 avant le 06/10/2026, v2 ensuite, jamais mélangées.",
               f"Aucune conclusion sous {MIN_JOURS} jours distincts ni sous {MIN_DATES_INDEP} dates non chevauchantes."],
           "parametres": {"horizons_seances": list(HORIZONS), "frais_aller_retour": FRAIS_AR,
                          "confiance_min": CONFIANCE_MIN, "debut_grille_v2": GRILLE_V2,
                          "min_jours_pour_conclure": MIN_JOURS,
                          "min_dates_non_chevauchantes": MIN_DATES_INDEP, "rupture_serie": RUPTURE},
           "entrees": entrees,
           "observations_ecartees": ecarts,
           "resultats": {}}
    for g in ("v1", "v2"):
        sous = df[df["grille"] == g]
        res["resultats"][f"grille_{g}"] = {
            "notes_retenues": int(len(sous)),
            "jours_de_publication": int(sous["date"].nunique()),
            **{f"h{h}": mesurer_grille(sous, h) for h in HORIZONS}}
    res["verdict"] = verdict(res["resultats"])
    return res


def verdict(resultats: dict) -> list[str]:
    out = []
    for g, blocs in resultats.items():
        for h in HORIZONS:
            b = blocs[f"h{h}"]
            ic = b["correlation_rang_note_alpha"]
            if not ic["conclusion_autorisee"]:
                out.append(f"{g} h{h} : insuffisant ({ic['n_jours']} jours, "
                           f"{ic['n_dates_non_chevauchantes']} dates non chevauchantes, "
                           f"{b['observations']} observations) — on ne conclut pas"
                           + (f" ; IC moyen observé {ic['moyenne']}, sans valeur probante." if ic["moyenne"] is not None else "."))
            else:
                t = ic["t_newey_west"]
                sens = ("aucun pouvoir prédictif distinguable du hasard" if t is None or abs(t) < 2
                        else ("note prédictive" if ic["moyenne"] > 0 else "note ANTI-prédictive"))
                out.append(f"{g} h{h} : IC moyen {ic['moyenne']} sur {ic['n_jours']} jours, "
                           f"t Newey-West {t} — {sens}.")
    return out


def ecrire(res: dict, sortie: Path = SORTIE) -> tuple[Path, Path]:
    sortie.mkdir(parents=True, exist_ok=True)
    suffixe = "" if res["entrees"]["source_des_notes"] == "score_history" else "_git"
    base = f"backtest_{res['entrees']['derniere_seance']}{suffixe}"
    pj, pm = sortie / f"{base}.json", sortie / f"{base}.md"
    pj.write_text(json.dumps(res, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    pm.write_text(markdown(res), encoding="utf-8")
    return pj, pm


def markdown(res: dict) -> str:
    e = res["entrees"]
    L = [f"# Backtest des notes publiées — séances {e['premiere_seance']} → {e['derniere_seance']}", "",
         "Mesure, pas promesse. Fichier JSON jumeau : empreintes sha256 de toutes les entrées.", "",
         "## Limites (écrites avant les résultats)", ""]
    L += [f"- {x}" for x in res["limites_ecrites_avant_les_resultats"]]
    L += ["", f"Source : `{e['source_des_notes']}` · {e['seances_publiees']} séances · "
          f"{e['notes_lues']} notes · commit `{(e['commit_git'] or '?')[:10]}` · "
          f"frais {res['parametres']['frais_aller_retour']:.0%} aller-retour", ""]
    for g, blocs in res["resultats"].items():
        for h in HORIZONS:
            b = blocs[f"h{h}"]
            L += [f"## {g} — {h} séances", "",
                  f"{b['observations']} observations, {b['jours']} jours, {b['titres']} titres.", ""]
            if not b["observations"]:
                L += ["Aucune observation : horizon non atteint ou grille trop récente.", ""]
                continue
            for k, nom in (("correlation_rang_note_alpha", "Corrélation de rang note → alpha"),
                           ("ecart_decile_haut_moins_bas_alpha", "Écart décile haut − bas")):
                c = b[k]
                L.append(f"- {nom} : moyenne {c['moyenne']} sur {c['n_jours']} jours ; "
                         f"t naïf {c['t_naif']}, Newey-West {c['t_newey_west']} (retenu), "
                         f"non chevauchant {c['t_non_chevauchant']} ({c['n_dates_non_chevauchantes']} dates) "
                         f"→ {c['lecture']}")
            L += ["", "| palier | obs. | jours | titres | alpha brut | alpha net frais | bon sens |",
                  "|---|---|---|---|---|---|---|"]
            for p, s in b["par_palier"].items():
                L.append(f"| {p} | {s['observations']} | {s['jours']} | {s['titres']} | "
                         f"{s.get('alpha_moyen_brut', '—')} | {s.get('alpha_moyen_net_frais', '—')} | "
                         f"{s.get('bon_sens') if s.get('bon_sens') is not None else '—'} |")
            L.append("")
    L += ["## Verdict", ""] + [f"- {x}" for x in res["verdict"]] + [""]
    return "\n".join(L)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", choices=("score_history", "git"), default="score_history")
    ap.add_argument("--sortie", default=str(SORTIE))
    a = ap.parse_args()
    res = construire(a.source)
    pj, pm = ecrire(res, Path(a.sortie))
    print(pj)
    print(pm)
    print("\n".join(res["verdict"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
