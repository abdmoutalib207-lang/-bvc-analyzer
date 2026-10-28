#!/usr/bin/env python3
"""Backtest du score descriptif (référentiel Nour) : UNE commande, un artefact daté.

    python3 pipeline/backtest_score_descriptif.py

Sortie : `datasets/backtests/score_descriptif_AAAA-MM-JJ.json`, où la date est
celle de la DERNIÈRE SÉANCE des chandelles (jamais l'horloge). Aucun réseau.
Deux exécutions sur les mêmes entrées donnent le même fichier, à l'octet près
(le rééchantillonnage est à graine fixe).

    --jusqu-au AAAA-MM-JJ   rejoue un artefact ancien : chandelles, MASI et notes
                            v53 tronqués à cette date (les chandelles avancent
                            chaque jour ; sans cela l'artefact d'hier ne se
                            reproduit plus)
    --sans-git              v53 : `score_history.json` seul. Par défaut s'y ajoute
                            l'historique git de data.json, qui dépend du CLONE
                            (tronqué au 05/09/2026 le 28/10). Seule la partie
                            `comparaison_v53` en dépend ; `resultats` jamais.

⚠️ CE QUI A ÉTÉ AJOUTÉ APRÈS LE PREMIER RELEVÉ, et doit se lire comme tel :
le détail du momentum par zone de RSI (`par_facteur.momentum_par_zone_de_rsi`)
— décidé en voyant que la zone « hors 30-70 » se comportait à l'inverse de ses
points — et le masquage des t sous les seuils d'effectif (le premier relevé
affichait des t de 8 à 15 sur 16 dates). Le détail RSI est EXPLORATOIRE : il
n'est pas corrigé de la multiplicité.

CE QUE CE BACKTEST MESURE — ET CE QU'IL NE PRÉTEND PAS
─────────────────────────────────────────────────────
Le produit ne prédit pas : il publie des FRÉQUENCES OBSERVÉES. La question n'est
donc pas « le score prédit-il ? » mais « les fréquences par tranche sont-elles
JUSTES (recalculables, assez de cas, période dite) et UTILES (les tranches se
distinguent-elles) ? ». Chaque ligne publie : effectif, nombre de dates et de
titres, fréquence de surperformance à 20 séances, médiane de l'écart, taux de
base de l'univers SUR LES MÊMES DATES, écart apparié à ce taux et son test.

RÈGLES — ÉCRITES AVANT D'AVOIR VU LES RÉSULTATS, JAMAIS RETOUCHÉES
  Score        `pipeline/score_descriptif.py`, rejoué CHAQUE séance avec les seules
               données connues à la date : clôtures jusqu'à t, MM20/MM50/RSI
               calculés comme `update_data.py` (vérifié égal à data.json sur 78
               titres), rapport de volume et liquidité sur les 20 séances
               précédentes. Aucune ré-estimation, aucun paramètre ajusté.
  Observation  un titre ÉCHANGÉ (volume > 0) à la séance t, calendrier des
               séances = dates où au moins 20 titres échangent. Un titre non
               échangé à t n'a pas de cours frais : pas d'observation (c'est le
               `stale` du moteur).
  Horizon      20 séances du calendrier. Entrée à la clôture de t, sortie à la
               clôture de t+20 (clôture reportée si le titre n'échange pas ce
               jour-là).
  Rendement    TOTAL : cours + dividende réinvesti à la date de détachement
               (`datasets/dividendes_bvc.json`, 2024-2026 pour tous les
               émetteurs ; il manque octobre-décembre 2023).
  Frais        2 % aller-retour, déduits du rendement du TITRE (pas de la
               référence). C'est conservateur pour le titre, et optimiste sur le
               coût réel des titres peu liquides (ni fourchette, ni impact).
  Référence    le MASI (indice de cours, `pipeline/masi_history.json`, 941
               séances du 02/01/2023 au 28/10/2026, source investing.com
               recoupée au calendrier de l'opérateur), et, en contrôle, la
               moyenne équipondérée des titres LIQUIDES de la date (montant
               médian ≥ 1 MDH, séance échangée, fenêtre propre).
  Surperformance  rendement total − 2 % − rendement de la référence > 0.
  Fenêtres écartées, et COMPTÉES : sortie sans bougie ; MASI absent ; fenêtre
               [t, t+20] traversant une RUPTURE — écart de clôture > 10 % entre
               deux séances échangées (R10) ou opération inscrite au registre
               (`SPLITS`, `SUSPENSIONS`, reprises), exactement la règle de
               `technical/serie_propre.py` ; indicateurs lus sur une série
               ROMPUE (suspension, reprise ou saut > 10 % dans les 50 séances
               qui précèdent t : MM50 et RSI mélangeraient deux régimes de
               prix, R11). Les splits déclarés ne déclenchent PAS ce dernier
               filtre : les chandelles stockées sont déjà ajustées.
  Tranches     < 40 · 40–59 · 60–74 · ≥ 75 (échelle 0-100) ; v53 : < 4 · 4–5,5 ·
               5,5–7 · ≥ 7 (paliers du terminal, `pipeline/backtest.py`).
  Taux de base fréquence de surperformance de TOUTES les observations calculables
               de la même date. Écart apparié = moyenne, sur les observations de
               la tranche, de (1[surperforme] − taux de base de leur date).
  Test         t de Newey-West (Bartlett, retard 19) sur les sommes JOURNALIÈRES
               de l'écart (estimateur de ratio : somme des écarts ÷ effectif) ;
               p bilatéral normal. Contrôles : bootstrap par blocs de 20 dates
               (graine fixe, 2 000 tirages) et échantillons NON chevauchants
               (une date sur 20, les 20 décalages). Retenu : Newey-West.
  Conclusion autorisée seulement si n ≥ 30, ≥ 20 dates distinctes ET ≥ 10 blocs
               de 20 séances touchés (règle de `backtest_reproductible.py`).
               Sinon la ligne dit « insuffisant », quel que soit le t.
  Rentabilité  mesure SANS (couverture 80, point-in-time par construction) et
               AVEC le ROE actuel. ⚠️ La seconde a un BIAIS D'ANTICIPATION : le
               ROE 2025 n'était pas connu en 2023 ni en 2024. Elle ne prouve
               rien sur ce qu'un lecteur aurait pu faire.

LIMITES, AVANT LES RÉSULTATS
  1. ~3 ans, un seul cycle de marché ; l'effectif des fenêtres INDÉPENDANTES de
     20 séances est d'environ 40, et les observations d'un même jour sont
     corrélées (même marché). Les p-valeurs sont indicatives, non corrigées de
     la multiplicité (4 tranches × variantes).
  2. SURVIE : l'univers est celui d'AUJOURD'HUI (80 titres cotés). Les valeurs
     radiées pendant la fenêtre en sont absentes (Timar, radiée le 10/06/2024
     après OPRO à 660 DH, n'a pas de chandelles) ; SAMIR est suspendue depuis
     2015 et ne cote pas dans la fenêtre. Le sens du biais n'est pas établi.
  3. Le MASI est un indice de COURS ; les titres sont en rendement TOTAL (biais
     favorable aux titres, non chiffré). Le MASI pondère par capitalisation : une
     moyenne de petits titres ne se compare pas honnêtement à lui — d'où la
     référence équipondérée en contrôle.
  4. Entrée à la clôture de la séance du signal : un lecteur agit le lendemain.
  5. Montants échangés ESTIMÉS (clôture × quantité), non le cours moyen pondéré.
  6. Les titres peu liquides (< 1 MDH/séance) y sont inclus mais illusoirement
     négociables aux prix de clôture : leurs lignes sont publiées à part.
  7. La note v53 n'existe dans le dépôt que depuis le 05/09/2026 (historique git
     tronqué) ou le 24/09/2026 (`score_history.json`) : le tableau comparatif
     repose sur moins de 20 dates d'entrée à 20 séances. Il décrit, il ne
     tranche pas.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from pathlib import Path
from statistics import median

import numpy as np
import pandas as pd

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))
sys.path.insert(0, str(RACINE / "pipeline"))

import bvc_config as cfg  # noqa: E402
from pipeline import score_descriptif as sd  # noqa: E402
from pipeline.technical.serie_propre import charger, ruptures  # noqa: E402

HORIZON = 20
FRAIS_AR = 0.02
MIN_TITRES_SEANCE = 20
LIQUIDE_DH = 1_000_000.0
FENETRE_RUPTURE = 50
SEANCES_APRES_REPRISE = 20          # miroir de update_data.SEANCES_APRES_REPRISE (testé)
NW_LAG = HORIZON - 1
BLOC = HORIZON
TIRAGES = 2000
GRAINE = 20261028
MIN_OBS, MIN_DATES, MIN_BLOCS = 30, 20, 10
TRANCHES = (("< 40", 0, 40), ("40 – 59", 40, 60), ("60 – 74", 60, 75), ("≥ 75", 75, 1e9))
TRANCHES_V53 = (("< 4", 0, 4), ("4 – 5,5", 4, 5.5), ("5,5 – 7", 5.5, 7), ("≥ 7", 7, 1e9))
SORTIE = RACINE / "datasets" / "backtests"
CANDLES = RACINE / "pipeline" / "candles"
COMMANDE = "python3 pipeline/backtest_score_descriptif.py"
CODE = ("pipeline/backtest_score_descriptif.py", "pipeline/score_descriptif.py",
        "pipeline/technical/serie_propre.py")
FACTEURS_SANS_ROE = ("tendance20", "tendance50", "momentum", "activité", "liquidité")


# ───────────────────────────── entrées ─────────────────────────────

def _sha_octets(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def _sha(p: Path) -> str:
    return _sha_octets(p.read_bytes())


def charger_bougies(fin: str | None = None) -> dict:
    """{ticker: [bougies triées]} pour les titres de `TICKERS_ALL` (alias TGC exclu).

    `fin` : tronque les chandelles à cette date (AAAA-MM-JJ) pour REJOUER un
    artefact ancien tel qu'il était — les chandelles du dépôt avancent chaque jour.
    """
    out = {}
    for t in cfg.TICKERS_ALL:
        f = CANDLES / f"{t}.json"
        if not f.exists():
            continue
        b = json.loads(f.read_text(encoding="utf-8"))
        b = sorted((x for x in b if x.get("c") and x["c"] > 0 and (fin is None or x["d"] <= fin)),
                   key=lambda x: x["d"])
        if len({x["d"] for x in b}) != len(b):
            raise ValueError(f"{t}: dates en double dans les chandelles")
        if b:
            out[t] = b
    return out


def calendrier(bougies: dict) -> list:
    """Séances réelles : dates où au moins 20 titres ont échangé."""
    n: dict = {}
    for b in bougies.values():
        for x in b:
            if (x.get("v") or 0) > 0:
                n[x["d"]] = n.get(x["d"], 0) + 1
    return sorted(d for d, k in n.items() if k >= MIN_TITRES_SEANCE)


def roe_actuels() -> dict:
    d = json.loads((RACINE / "data.json").read_text(encoding="utf-8"))
    out = {}
    for t in d["tickers"]:
        r = sd.roe_publie(t)
        if r is not None:
            out[t["symbol"]] = r
    return out


def masi_serie(fin: str | None = None) -> dict:
    m = json.loads((RACINE / "pipeline" / "masi_history.json").read_text(encoding="utf-8"))
    return {d: float(v) for d, v in m["seances"].items() if fin is None or d <= fin}


def dividendes() -> dict:
    f = RACINE / "datasets" / "dividendes_bvc.json"
    return json.loads(f.read_text(encoding="utf-8")).get("dividendes", {})


def _dates_suspension(t: str) -> list:
    """Dates de suspension / reprise inscrites au registre (hors splits)."""
    d = []
    for e in cfg.SUSPENSIONS.get(t, []):
        d += [e[k] for k in ("depuis", "reprise") if e.get(k)]
    return sorted(set(d))


# ───────────────────────────── panel ─────────────────────────────

def panel_titre(t: str, bars: list, roe, cal_pos: dict, cal: list, masi: dict, divs: list) -> list:
    """Une ligne par (titre, séance échangée du calendrier), sans regard vers l'avenir.

    Les colonnes de score ne lisent que les bougies jusqu'à la date ; les colonnes
    `r`, `rm` (rendements futurs) ne servent QU'À la mesure.
    """
    n = len(bars)
    dates = [b["d"] for b in bars]
    o = [float(b["o"]) for b in bars]
    h = [float(b["h"]) for b in bars]
    lo = [float(b["l"]) for b in bars]
    c = [float(b["c"]) for b in bars]
    v = [float(b["v"]) if sd._fini(b.get("v")) else 0.0 for b in bars]
    veq = sd.volumes_equivalents(t, bars)
    # RSI : séances échangées seulement, récursion incrémentale (aucun regard en avant)
    masque = sd.masque_echange(o, h, lo, c, v)
    rs = sd.serie_rsi([c[i] for i in range(n) if masque[i]])
    rsi, k = [None] * n, -1
    for i in range(n):
        if masque[i]:
            k += 1
        rsi[i] = rs[k] if k >= 0 else None
    # indice de rendement total
    div = [0.0] * n
    for e in divs:
        j = next((i for i in range(n) if dates[i] >= e["detachement"]), None)
        if j is not None:
            div[j] += e["montant_ajuste_split"]
    tr, acc = [1.0] * n, 1.0
    for i in range(1, n):
        acc *= (c[i] + div[i]) / c[i - 1]
        tr[i] = acc
    # ruptures (séances échangées) : fenêtre avant (indicateurs) et après (rendement)
    s = charger(CANDLES / f"{t}.json", dates[-1])
    rup_all = sorted({s["d"][b] for b in ruptures(s["d"], s["c"], sd_evenements(t))}) if s else []
    rup_ind = sorted({s["d"][b] for b in ruptures(s["d"], s["c"], _dates_suspension(t))}) if s else []
    idx_date = {d: i for i, d in enumerate(dates)}
    rup_ind_idx = [idx_date[r] for r in rup_ind if r in idx_date]
    reprises = sorted(e["reprise"] for e in cfg.SUSPENSIONS.get(t, []) if e.get("reprise"))
    lignes = []
    for i in range(n):
        d0 = dates[i]
        if v[i] <= 0 or d0 not in cal_pos:
            continue
        # reprise de cotation récente (miroir de `reprise_trop_recente`, sans regard en avant)
        passees = [r for r in reprises if r <= d0]
        depuis = None
        if passees:
            cnt = sum(1 for j in range(i + 1) if dates[j] >= passees[-1])
            depuis = cnt if cnt < SEANCES_APRES_REPRISE else None
        m = sd.mesures_series(c[max(0, i - HORIZON):i + 1], veq[max(0, i - HORIZON):i + 1],
                              depuis, n_total=i + 1)
        decision, motif = sd.etat_donnees(
            suspendu=bool(cfg.est_suspendu(t, d0)), stale=False, prix=c[i],
            cloture_coherente=True, n_seances=i + 1,
            liquidite_prete=m["liquidite_prete"], reprise_recente=depuis is not None)
        ma20 = round(float(np.mean(c[i - 19:i + 1])), 2) if i >= 19 else None
        ma50 = round(float(np.mean(c[i - 49:i + 1])), 2) if i >= 49 else None
        kw = dict(prix=c[i], ma20=ma20, ma50=ma50, rsi=rsi[i], ratio_volume=m["ratio_volume"],
                  montant_median=m["montant_median"], liquidite_prete=m["liquidite_prete"],
                  decision=decision, motif=motif)
        sans = sd.score_descriptif(roe=None, **kw)
        avec = sd.score_descriptif(roe=roe, **kw)
        p = cal_pos[d0]
        ligne = {"date": d0, "pos": p, "t": t, "decision": decision,
                 "etat_sans": sans["etat"], "etat_avec": avec["etat"],
                 "sans": sans["valeur"], "avec": avec["valeur"],
                 "montant": m["montant_median"], "prete": m["liquidite_prete"], "rsi": rsi[i],
                 "rupture_indic": any(0 <= i - r < FENETRE_RUPTURE for r in rup_ind_idx),
                 "r": None, "rm": None, "sortie_absente": False, "fenetre_rompue": False,
                 "horizon_non_atteint": False, "masi_absent": False}
        for nom, f in avec["facteurs"].items():
            ligne["pts_" + nom] = f["points"]
        if p + HORIZON >= len(cal):
            ligne["horizon_non_atteint"] = True
        else:
            d1 = cal[p + HORIZON]
            j = idx_date.get(d1)
            if j is None:
                ligne["sortie_absente"] = True
            else:
                ligne["r"] = tr[j] / tr[i] - 1
                if any(d0 < r <= d1 for r in rup_all):
                    ligne["fenetre_rompue"] = True
            if d0 in masi and d1 in masi:
                ligne["rm"] = masi[d1] / masi[d0] - 1
            else:
                ligne["masi_absent"] = True
        lignes.append(ligne)
    return lignes


def sd_evenements(t: str) -> list:
    """Dates d'opérations déclarées (splits + suspensions) : règle de serie_propre."""
    from pipeline.technical.serie_propre import evenements_titre
    return evenements_titre(t)


def construire_panel(bougies: dict, cal: list, roes: dict, masi: dict, divs: dict) -> pd.DataFrame:
    cal_pos = {d: i for i, d in enumerate(cal)}
    lignes = []
    for t in sorted(bougies):
        lignes += panel_titre(t, bougies[t], roes.get(t), cal_pos, cal, masi, divs.get(t, []))
    P = pd.DataFrame(lignes)
    P["propre"] = (P["r"].notna() & ~P["fenetre_rompue"] & ~P["rupture_indic"]
                   & ~P["sortie_absente"] & P["rm"].notna())
    P["liquide"] = P["prete"] & (P["montant"] >= LIQUIDE_DH)
    # référence équipondérée : titres liquides de la date, fenêtre propre
    liq = P[P["propre"] & P["liquide"]].groupby("pos")["r"].mean()
    P["ref_ew"] = P["pos"].map(liq)
    P["ex"] = P["r"] - FRAIS_AR - P["rm"]                 # écart net de frais au MASI
    P["ex_ew"] = P["r"] - FRAIS_AR - P["ref_ew"]          # écart net de frais à l'équipondéré
    P["gagne"] = (P["ex"] > 0).astype(float)
    P["gagne_ew"] = (P["ex_ew"] > 0).astype(float)
    return P


# ───────────────────────────── statistiques ─────────────────────────────

def _p_normal(t) -> float | None:
    return None if t is None or not math.isfinite(t) else math.erfc(abs(t) / math.sqrt(2))


def hac_ratio(S: np.ndarray, n: np.ndarray, lag: int = NW_LAG) -> dict:
    """Δ = ΣS / Σn et son t de Newey-West (Bartlett), par linéarisation du ratio."""
    N = float(n.sum())
    if N <= 0:
        return {"delta": None, "t": None, "p": None}
    delta = float(S.sum() / N)
    u = S - delta * n
    v = float(u @ u)
    for l_ in range(1, min(lag, len(u) - 1) + 1):
        v += 2 * (1 - l_ / (lag + 1)) * float(u[l_:] @ u[:-l_])
    var = v / N ** 2
    # variance nulle ou à la précision de la machine (écart nul par construction) : pas de t
    t = delta / math.sqrt(var) if var > 1e-18 else None
    return {"delta": delta, "t": t, "p": _p_normal(t)}


def _tirages(T: int) -> np.ndarray:
    """Indices de rééchantillonnage par blocs circulaires de 20 dates (graine fixe)."""
    rng = np.random.default_rng(GRAINE)
    nb = math.ceil(T / BLOC)
    starts = rng.integers(0, T, size=(TIRAGES, nb))
    idx = (starts[:, :, None] + np.arange(BLOC)[None, None, :]) % T
    return idx.reshape(TIRAGES, nb * BLOC)[:, :T]


def _nonchevauchant(S, n) -> dict:
    ts, ds = [], []
    for k in range(HORIZON):
        sel = np.arange(len(S)) % HORIZON == k
        N = n[sel].sum()
        if N <= 0:
            continue
        d = S[sel].sum() / N
        u = S[sel] - d * n[sel]
        var = float(u @ u) / N ** 2
        if var > 0:
            ts.append(d / math.sqrt(var))
            ds.append(d)
    if not ts:
        return {"t_median": None, "delta_median": None, "decalages_significatifs": 0, "decalages": 0}
    return {"t_median": round(float(np.median(ts)), 3), "delta_median": round(float(np.median(ds)), 4),
            "decalages_significatifs": int(sum(abs(x) > 1.96 for x in ts)), "decalages": len(ts)}


def _r(x, d=4):
    return None if x is None or (isinstance(x, float) and not math.isfinite(x)) else round(float(x), d)


def ligne_groupe(sous: pd.DataFrame, base_pos: np.ndarray, T: int, tir: np.ndarray,
                 col_gagne: str, col_ex: str) -> dict:
    """Les chiffres d'UN groupe d'observations (une tranche)."""
    n_obs = len(sous)
    out = {"n": int(n_obs), "dates": int(sous["pos"].nunique()), "titres": int(sous["t"].nunique())}
    if n_obs == 0:
        return {**out, "lecture": "aucune observation"}
    pos = sous["pos"].to_numpy()
    w = sous[col_gagne].to_numpy()
    b = base_pos[pos]
    S = np.bincount(pos, weights=w - b, minlength=T)
    W = np.bincount(pos, weights=w, minlength=T)
    n = np.bincount(pos, minlength=T).astype(float)
    freq = float(w.mean())
    base_memes_dates = float(b.mean())
    hac = hac_ratio(S, n)
    Sb, nb_, Wb = S[tir], n[tir], W[tir]
    ok = nb_.sum(1) > 0
    dstar = Sb.sum(1)[ok] / nb_.sum(1)[ok]
    fstar = Wb.sum(1)[ok] / nb_.sum(1)[ok]
    d0 = hac["delta"]
    p_boot = float((1 + (np.abs(dstar - d0) >= abs(d0)).sum()) / (len(dstar) + 1)) if len(dstar) else None
    blocs = int(len(set((np.unique(pos) // HORIZON).tolist())))
    autorise = n_obs >= MIN_OBS and out["dates"] >= MIN_DATES and blocs >= MIN_BLOCS
    sig = bool(autorise and hac["p"] is not None and hac["p"] < 0.05
               and p_boot is not None and p_boot < 0.05)
    if not autorise:
        # Sous les seuils, un t calculé n'a aucun sens (16 dates ≈ une fraction de
        # bloc indépendant : Newey-West y sort des t de 8 ou 15). On ne le publie pas.
        hac = {"delta": hac["delta"], "t": None, "p": None}
        p_boot = None
    out.update({
        "blocs_de_20_seances_touches": blocs,
        "frequence_surperformance": _r(freq),
        "frequence_ic95_blocs": [None, None] if not autorise else
                                [_r(np.percentile(fstar, 2.5)), _r(np.percentile(fstar, 97.5))],
        "mediane_ecart_net_frais_pct": _r(float(np.median(sous[col_ex])) * 100, 2),
        "moyenne_ecart_net_frais_pct": _r(float(sous[col_ex].mean()) * 100, 2),
        "taux_de_base_memes_dates": _r(base_memes_dates),
        "ecart_apparie_pts": _r(d0 * 100, 2),
        "ecart_apparie_ic95_blocs_pts": [None, None] if not autorise else
                                        [_r(np.percentile(dstar, 2.5) * 100, 2),
                                         _r(np.percentile(dstar, 97.5) * 100, 2)],
        "t_newey_west": _r(hac["t"], 2), "p_newey_west": _r(hac["p"], 4),
        "p_bootstrap_blocs": _r(p_boot, 4),
        "non_chevauchant": _nonchevauchant(S, n) if autorise else None,
        "conclusion_autorisee": bool(autorise),
        "ecart_significatif_5pct": sig,
        "lecture": ("insuffisant : " + f"n={n_obs} (min {MIN_OBS}), {out['dates']} dates (min {MIN_DATES}), "
                    f"{blocs} blocs de 20 séances (min {MIN_BLOCS})") if not autorise else
                   ("écart significatif à 5 % (Newey-West ET bootstrap)" if sig else
                    "écart non distinguable du hasard à 5 %"),
    })
    return out


def table(df: pd.DataFrame, col: str, tranches, col_gagne="gagne", col_ex="ex", T=None, tir=None) -> dict:
    """Tableau par tranche. La base = TOUTES les observations de `df` à chaque date."""
    d = df[df[col].notna()]
    base = d.groupby("pos")[col_gagne].mean()
    base_pos = np.full(T, np.nan)
    base_pos[base.index.to_numpy()] = base.to_numpy()
    out = {"observations_total": int(len(d)), "dates": int(d["pos"].nunique()),
           "taux_de_base_global": _r(float(d[col_gagne].mean())) if len(d) else None,
           "mediane_ecart_net_frais_global_pct": _r(float(d[col_ex].median()) * 100, 2) if len(d) else None,
           "tranches": {}}
    for nom, lo, hi in tranches:
        sous = d[(d[col] >= lo) & (d[col] < hi)]
        out["tranches"][nom] = ligne_groupe(sous, base_pos, T, tir, col_gagne, col_ex)
    return out


def ic_et_ecart_haut_bas(df: pd.DataFrame, col: str, haut: float, bas: float, col_gagne: str,
                         col_ex: str, T: int) -> dict:
    """Utilité : corrélation de rang JOUR PAR JOUR score → écart, et écart haut − bas."""
    d = df[df[col].notna() & df[col_ex].notna()]
    S_ic = np.zeros(T)
    n_ic = np.zeros(T)
    S_hb = np.zeros(T)
    n_hb = np.zeros(T)
    for pos, g in d.groupby("pos"):
        if len(g) >= 10 and g[col].nunique() > 1:
            c = g[col].rank().corr(g[col_ex].rank())
            if c is not None and math.isfinite(c):
                S_ic[pos], n_ic[pos] = c, 1
        h_, b_ = g[g[col] >= haut], g[g[col] < bas]
        if len(h_) >= 3 and len(b_) >= 3:
            S_hb[pos], n_hb[pos] = h_[col_gagne].mean() - b_[col_gagne].mean(), 1
    def garde(h, n_):
        jours = int(n_.sum())
        blocs = len(set((np.nonzero(n_)[0] // HORIZON).tolist()))
        ok = jours >= MIN_DATES and blocs >= MIN_BLOCS
        return (h if ok else {**h, "t": None, "p": None}), jours, ok

    a, j_ic, ok_ic = garde(hac_ratio(S_ic, n_ic), n_ic)
    b, j_hb, ok_hb = garde(hac_ratio(S_hb, n_hb), n_hb)
    return {"correlation_rang_score_ecart": {
                "moyenne": _r(a["delta"], 4), "t_newey_west": _r(a["t"], 2), "p": _r(a["p"], 4),
                "jours": j_ic, "conclusion_autorisee": ok_ic},
            "ecart_frequence_haut_moins_bas": {
                "definition": f"fréquence(score ≥ {haut:g}) − fréquence(score < {bas:g}), jours où chaque groupe a ≥ 3 observations",
                "moyenne_pts": _r(b["delta"] * 100, 2) if b["delta"] is not None else None,
                "t_newey_west": _r(b["t"], 2), "p": _r(b["p"], 4), "jours": j_hb,
                "conclusion_autorisee": ok_hb}}


def periodes(df: pd.DataFrame, col: str, tranches, cal: list, T: int, tir) -> dict:
    """Les périodes de mauvaise performance : mêmes tranches, découpées par semestre d'entrée."""
    lab = pd.Series([cal[p][:4] + ("-S1" if cal[p][5:7] <= "06" else "-S2") for p in df["pos"]],
                    index=df.index)
    out = {}
    for per in sorted(lab.unique()):
        sous = df[(lab == per) & df[col].notna()]
        if sous.empty:
            continue
        out[per] ={"du": cal[int(sous["pos"].min())], "au": cal[int(sous["pos"].max())],
                    "observations": int(len(sous)),
                    "taux_de_base": _r(float(sous["gagne"].mean())),
                    "mediane_ecart_net_frais_pct": _r(float(sous["ex"].median()) * 100, 2),
                    "tranches": {}}
        base = sous.groupby("pos")["gagne"].mean()
        bp = np.full(T, np.nan)
        bp[base.index.to_numpy()] = base.to_numpy()
        for nom, lo, hi in tranches:
            g = sous[(sous[col] >= lo) & (sous[col] < hi)]
            if len(g):
                out[per]["tranches"][nom] = {
                    "n": int(len(g)), "dates": int(g["pos"].nunique()),
                    "frequence_surperformance": _r(float(g["gagne"].mean())),
                    "taux_de_base_memes_dates": _r(float(bp[g["pos"].to_numpy()].mean())),
                    "ecart_apparie_pts": _r(float((g["gagne"].to_numpy() - bp[g["pos"].to_numpy()]).mean()) * 100, 2),
                    "mediane_ecart_net_frais_pct": _r(float(g["ex"].median()) * 100, 2)}
    return out


def par_facteur(df: pd.DataFrame, T: int, tir) -> dict:
    """Pour chaque facteur : fréquence selon les points obtenus (plein / partiel / zéro)."""
    out = {}
    d = df[df["sans"].notna()]
    base = d.groupby("pos")["gagne"].mean()
    bp = np.full(T, np.nan)
    bp[base.index.to_numpy()] = base.to_numpy()
    for f in FACTEURS_SANS_ROE + ("rentabilité",):
        col = "pts_" + f
        poids = sd.POIDS[f]
        out[f] = {"biais_anticipation": f == "rentabilité"}
        for nom, cond in (("plein", d[col] >= poids), ("partiel", (d[col] > 0) & (d[col] < poids)),
                          ("zero", d[col] <= 0)):
            sous = d[cond.fillna(False)]
            out[f][nom] = ligne_groupe(sous, bp, T, tir, "gagne", "ex")
            # allège : on garde l'essentiel
            out[f][nom] = {k: out[f][nom].get(k) for k in
                           ("n", "dates", "frequence_surperformance", "taux_de_base_memes_dates",
                            "ecart_apparie_pts", "t_newey_west", "p_newey_west", "conclusion_autorisee",
                            "lecture")}
    # Détail du momentum : la formule de Nour donne 0 point hors [30 ; 70]. Que
    # observe-t-on dans chaque zone de RSI (valeur du jour, point-in-time) ?
    zones = (("RSI < 30", d["rsi"] < 30), ("30 ≤ RSI < 45", (d["rsi"] >= 30) & (d["rsi"] < 45)),
             ("45 ≤ RSI ≤ 70", (d["rsi"] >= 45) & (d["rsi"] <= 70)), ("RSI > 70", d["rsi"] > 70))
    det = {"_lecture": "points de Nour par zone : 0 · 7,5 · 15 · 0. Le RSI est celui de data.json "
                       "(séances échangées, arrondi à 1 décimale)."}
    for nom, cond in zones:
        for suffixe, masque in (("", cond), (" · titres liquides", cond & d["liquide"]),
                                (" · titres peu liquides", cond & ~d["liquide"])):
            l_ = ligne_groupe(d[masque.fillna(False)], bp, T, tir, "gagne", "ex")
            det[nom + suffixe] = {k: l_.get(k) for k in (
                "n", "dates", "titres", "frequence_surperformance", "taux_de_base_memes_dates",
                "ecart_apparie_pts", "mediane_ecart_net_frais_pct", "t_newey_west", "p_newey_west",
                "p_bootstrap_blocs", "conclusion_autorisee", "lecture")}
    out["momentum_par_zone_de_rsi"] = det
    return out


# ───────────────────────────── comparaison v53 ─────────────────────────────

def notes_v53(avec_git: bool = True, fin: str | None = None) -> tuple:
    """(lignes, sources) : v53 PUBLIÉE, `score_history.json` + (option) historique git.

    ⚠️ `score_history.json` est versionné : sa part est reproductible partout.
    L'historique git de `data.json`, lui, dépend du CLONE (tronqué au 05/09/2026
    dans l'arbre de travail du 28/10) : `--sans-git` l'écarte pour un résultat
    identique sur tout clone. L'empreinte de la série v53 retenue est écrite.
    """
    import backtest_reproductible as br
    sh, _ = br.notes_score_history(RACINE / "pipeline" / "score_history.json")
    git, par_jour = [], {}
    if avec_git:
        git, _, par_jour = br.notes_git()
    vu = {(n["date"], n["t"]): n for n in git}
    for n in sh:
        vu.setdefault((n["date"], n["t"]), n)
    lignes = sorted((n for n in vu.values()
                     if n["v53"] is not None and n["conf"] is not None and n["conf"] >= 2
                     and not (n["sig"] or "").startswith("Données") and n["asof"] == n["date"]
                     and (fin is None or n["date"] <= fin)),
                    key=lambda n: (n["date"], n["t"]))
    empreinte = _sha_octets(json.dumps([[n["date"], n["t"], n["v53"], n["conf"]] for n in lignes]).encode())
    return lignes, {"score_history.json": {"lignes": len(sh)},
                    "historique_git_data_json": ({"du": min(par_jour), "au": max(par_jour), "jours": len(par_jour)}
                                                 if par_jour else "non utilisé"),
                    "lignes_v53_retenues": len(lignes), "sha256_serie_v53_retenue": empreinte,
                    "filtres": "confiance ≥ 2, signal ≠ « Données insuffisantes », cours de la séance du jour"}


def quartiles_labels(serie: pd.Series) -> tuple:
    q = [float(serie.quantile(x)) for x in (0.25, 0.5, 0.75)]
    return q, (("Q1 (bas)", -1e9, q[0] + 1e-9), ("Q2", q[0] + 1e-9, q[1] + 1e-9),
               ("Q3", q[1] + 1e-9, q[2] + 1e-9), ("Q4 (haut)", q[2] + 1e-9, 1e9))


def comparaison_v53(P: pd.DataFrame, cal: list, T: int, tir, avec_git: bool = True,
                    fin: str | None = None) -> dict:
    lignes, src = notes_v53(avec_git, fin)
    if not lignes:
        return {"source_v53": src, "lecture": "aucune note v53 publiée à ces dates"}
    V = pd.DataFrame(lignes)[["date", "t", "v53"]]
    cal_pos = {d: i for i, d in enumerate(cal)}
    V["pos"] = V["date"].map(cal_pos)
    base = P[P["propre"]].merge(V[["date", "t", "v53"]], on=["date", "t"], how="inner")
    out = {"source_v53": src,
           "_lecture": ("v53 = note PUBLIÉE (confiance ≥ 2, cours de la séance du jour), pas rejouée. "
                        "Même rendement, même référence, mêmes frais, mêmes écarts de fenêtre que le "
                        "score descriptif. Ensemble COMMUN = (titre, date) où les deux notes existent.")}
    if base.empty:
        return {**out, "lecture": "aucune observation commune"}
    commun = base[base["sans"].notna()]
    out["fenetre_entrees"] = {"du": cal[int(commun["pos"].min())], "au": cal[int(commun["pos"].max())],
                              "dates": int(commun["pos"].nunique()), "observations": int(len(commun)),
                              "titres": int(commun["t"].nunique())}
    out["v53_toutes_observations"] = {
        "observations": int(len(base)), "dates": int(base["pos"].nunique()),
        "du": cal[int(base["pos"].min())], "au": cal[int(base["pos"].max())],
        "tranches_terminal": table(base, "v53", TRANCHES_V53, T=T, tir=tir)}
    out["ensemble_commun"] = {
        "score_descriptif_sans_roe": table(commun, "sans", TRANCHES, T=T, tir=tir),
        "v53": table(commun, "v53", TRANCHES_V53, T=T, tir=tir)}
    qs, ql = quartiles_labels(commun["sans"])
    qv, qlv = quartiles_labels(commun["v53"])
    out["ensemble_commun_quartiles"] = {
        "_lecture": "tranches d'effectifs ~égaux (bornes = quartiles de l'ensemble commun) : comparaison à échelle égale",
        "score_descriptif_sans_roe": {"bornes_q25_q50_q75": [round(x, 2) for x in qs],
                                      **table(commun, "sans", ql, T=T, tir=tir)},
        "v53": {"bornes_q25_q50_q75": [round(x, 2) for x in qv], **table(commun, "v53", qlv, T=T, tir=tir)}}
    out["utilite_ensemble_commun"] = {
        "score_descriptif_sans_roe": ic_et_ecart_haut_bas(commun, "sans", 60, 40, "gagne", "ex", T),
        "v53": ic_et_ecart_haut_bas(commun, "v53", 5.5, 4, "gagne", "ex", T)}
    return out


# ───────────────────────────── contrôle moteur ─────────────────────────────

def controle_moteur(P: pd.DataFrame, bougies: dict, cal: list) -> dict:
    """Le panel rejoue-t-il, à la dernière séance, ce que publie le moteur (data.json) ?"""
    d = json.loads((RACINE / "data.json").read_text(encoding="utf-8"))
    last = cal[-1]
    if str(d.get("date_analyse"))[:10] != last:
        return {"statut": "non vérifié", "motif": f"data.json daté {d.get('date_analyse')}, dernière séance {last}"}
    L = P[P["date"] == last].set_index("t")
    comparés = ecarts = 0
    detail = []
    for rec in d["tickers"]:
        s = rec["symbol"]
        if s not in L.index or not (rec.get("_meta") or {}).get("prix_asof") == last:
            continue
        moteur = sd.score_titre(rec, bougies.get(s, []))
        panel = L.at[s, "avec"]
        panel = None if pd.isna(panel) else float(panel)
        comparés += 1
        if moteur["valeur"] != panel:
            ecarts += 1
            detail.append({"t": s, "moteur": moteur["valeur"], "panel": panel, "motif": moteur["motif"]})
    return {"statut": "vérifié", "seance": last, "titres_comparés": comparés, "ecarts": ecarts,
            "detail": detail[:20]}


# ───────────────────────────── orchestration ─────────────────────────────

def exclusions(P: pd.DataFrame) -> dict:
    cal_obs = P
    calc = cal_obs["sans"].notna()
    return {
        "observations_titre_echange": int(len(P)),
        "etat_score_sans_roe": {k: int(v) for k, v in P["etat_sans"].value_counts().items()},
        "decision_donnees": {k: int(v) for k, v in P["decision"].value_counts().items()},
        "score_calculable_sans_roe": int(calc.sum()),
        "ecartees_horizon_non_atteint": int(P["horizon_non_atteint"].sum()),
        "ecartees_sortie_absente": int(P["sortie_absente"].sum()),
        "ecartees_fenetre_rompue": int(P["fenetre_rompue"].sum()),
        "ecartees_indicateurs_sur_serie_rompue": int(P["rupture_indic"].sum()),
        "ecartees_masi_absent": int(P["masi_absent"].sum()),
        "utilisables_toutes_notes": int(P["propre"].sum()),
        "utilisables_et_calculables_sans_roe": int((P["propre"] & calc).sum()),
        "utilisables_et_calculables_avec_roe": int((P["propre"] & P["avec"].notna()).sum()),
    }


def distribution_derniere_seance(P: pd.DataFrame, cal: list) -> dict:
    last = P[P["date"] == cal[-1]]
    out = {"date": cal[-1], "titres_echanges": int(len(last)),
           "etat_avec_roe": {k: int(v) for k, v in last["etat_avec"].value_counts().items()}}
    for var in ("avec", "sans"):
        v = last[var].dropna()
        out[f"score_{var}_roe"] = {
            "n": int(len(v)),
            "min": _r(float(v.min()), 2) if len(v) else None,
            "q25": _r(float(v.quantile(.25)), 2) if len(v) else None,
            "mediane": _r(float(v.median()), 2) if len(v) else None,
            "q75": _r(float(v.quantile(.75)), 2) if len(v) else None,
            "max": _r(float(v.max()), 2) if len(v) else None,
            "par_tranche": {nom: int(((v >= lo) & (v < hi)).sum()) for nom, lo, hi in TRANCHES}}
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--sortie", default=str(SORTIE), help="dossier de sortie")
    ap.add_argument("--jusqu-au", default=None, metavar="AAAA-MM-JJ",
                    help="tronque chandelles, MASI et notes v53 à cette date : rejoue un "
                         "artefact ancien (les chandelles du dépôt avancent chaque jour)")
    ap.add_argument("--sans-git", action="store_true",
                    help="v53 : score_history.json seul (identique sur tout clone) ; "
                         "défaut : + historique git de data.json s'il est disponible")
    a = ap.parse_args(argv)

    bougies = charger_bougies(a.jusqu_au)
    cal = calendrier(bougies)
    T = len(cal)
    masi = masi_serie(a.jusqu_au)
    manque = [d for d in cal if d not in masi]
    roes = roe_actuels()
    divs = dividendes()
    P = construire_panel(bougies, cal, roes, masi, divs)
    tir = _tirages(T)

    # ─ tableaux principaux (référence : MASI)
    sans = P[P["propre"] & P["sans"].notna()]
    avec = P[P["propre"] & P["avec"].notna()]
    res = {}
    for nom, df, col in (("sans_rentabilite", sans, "sans"), ("avec_roe_actuel", avec, "avec")):
        bloc = {"couverture_pct": 80 if col == "sans" else "100 (80 si ROE absent)",
                **table(df, col, TRANCHES, T=T, tir=tir),
                "utilite": ic_et_ecart_haut_bas(df, col, 60, 40, "gagne", "ex", T),
                "par_semestre": periodes(df, col, TRANCHES, cal, T, tir),
                "titres_liquides_seuls": table(df[df["liquide"]], col, TRANCHES, T=T, tir=tir),
                "titres_peu_liquides_seuls": table(df[~df["liquide"]], col, TRANCHES, T=T, tir=tir)}
        if col == "avec":
            bloc["_biais"] = ("BIAIS D'ANTICIPATION : le ROE 2025 (publié en 2026) est appliqué à toutes "
                              "les dates, 2023 comprise. À lire comme une borne de ce que vaudrait le "
                              "facteur s'il avait été connu, jamais comme une performance atteignable.")
        res[nom] = bloc
    res["sans_rentabilite"]["par_facteur"] = par_facteur(sans, T, tir)
    # ─ contrôle : référence équipondérée de l'univers liquide
    ew = P[P["propre"] & P["sans"].notna() & P["ref_ew"].notna()]
    res["controle_reference_equiponderee"] = {
        "_lecture": "même mesure SANS rentabilité, mais l'écart est pris contre la moyenne équipondérée "
                    "des titres liquides de la date (au lieu du MASI)",
        **table(ew, "sans", TRANCHES, "gagne_ew", "ex_ew", T=T, tir=tir),
        "utilite": ic_et_ecart_haut_bas(ew, "sans", 60, 40, "gagne_ew", "ex_ew", T)}

    deb, fin = cal[0], cal[-1]
    entrees = {
        "chandelles": {"titres": len(bougies), "bougies": int(sum(len(b) for b in bougies.values())),
                       "du": min(b[0]["d"] for b in bougies.values()), "au": fin,
                       "tronque_a": a.jusqu_au,
                       # empreinte du contenu UTILISÉ (tronqué), pas du fichier : il avance chaque jour
                       "sha256_bougies_utilisees": _sha_octets(json.dumps(
                           [[t, [[x["d"], x["o"], x["h"], x["l"], x["c"], x.get("v")] for x in bougies[t]]]
                            for t in sorted(bougies)]).encode())},
        "calendrier": {"seances": T, "du": deb, "au": fin,
                       "regle": f"dates où au moins {MIN_TITRES_SEANCE} titres ont échangé",
                       "seances_sans_masi": len(manque)},
        "masi": {"seances": len(masi), "du": min(masi), "au": max(masi),
                 "sha256_serie_utilisee": _sha_octets(json.dumps(sorted(masi.items())).encode())},
        "dividendes": {"sha256": _sha(RACINE / "datasets" / "dividendes_bvc.json")},
        "roe_actuels": {"titres_avec_roe": len(roes),
                        "sha256_vecteur": _sha_octets(json.dumps(roes, sort_keys=True).encode()),
                        "source": "data.json › ratios_publies.roe_2025.valeur (comptes déposés AMMC)"},
        "code_sha256": {c: _sha(RACINE / c) for c in CODE},
        "univers": ("titres de `bvc_config.TICKERS_ALL` (80, cotés à la date de rédaction) ; chandelles vides : "
                    + ", ".join(sorted(set(cfg.TICKERS_ALL) - set(bougies)))),
    }
    artefact = {
        "_quoi": "Backtest du score descriptif (référentiel BVC Nour) — mode fantôme, n'entre ni dans v53 ni dans le signal",
        "_commande": COMMANDE,
        "version_score": sd.VERSION, "reference_formule": sd.REFERENCE,
        "date_artefact": fin, "horizon_seances": HORIZON, "frais_aller_retour": FRAIS_AR,
        "reference_principale": "MASI (indice de cours), séances du calendrier des chandelles",
        "tranches": [t[0] for t in TRANCHES],
        "regles_et_limites": __doc__.split("LIMITES, AVANT LES RÉSULTATS")[0].split("RÈGLES — ÉCRITES")[1].strip(),
        "limites": __doc__.split("LIMITES, AVANT LES RÉSULTATS")[1].strip(),
        "entrees": entrees,
        "exclusions": exclusions(P),
        "controle_panel_contre_moteur": controle_moteur(P, bougies, cal),
        "distribution_derniere_seance": distribution_derniere_seance(P, cal),
        "resultats": res,
        "comparaison_v53": comparaison_v53(P, cal, T, tir, avec_git=not a.sans_git, fin=a.jusqu_au),
    }
    out = Path(a.sortie)
    out.mkdir(parents=True, exist_ok=True)
    f = out / f"score_descriptif_{fin}.json"
    f.write_text(json.dumps(artefact, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"✅ {f.relative_to(RACINE) if f.is_relative_to(RACINE) else f}  ({f.stat().st_size // 1024} Ko)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
