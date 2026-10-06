#!/usr/bin/env python3
"""Fréquences publiées des signaux techniques : UNE source de vérité.

Le produit ne prédit pas ; il affiche des fréquences OBSERVÉES. Pour qu'elles
soient justes, chacune doit être recalculable (effectif, période, définition)
et dire avec quelle incertitude elle est connue (intervalle de Wilson).

Ce module :
  - rejoue le calibrage du 03/10/2026 (pipeline/calibrage_regime.py, mêmes
    définitions, aucune retouche) sur les chandelles TRONQUÉES à la fin de la
    période de calibrage, pour que le recalcul ne bouge pas à chaque séance ;
  - en tire les quatre fréquences affichées par le terminal ;
  - écrit datasets/frequences_publiees.json (jamais à la main).

Les signaux n'entrent PAS dans la note (R8) : aucune note ne dépend de ce fichier.

Usage : python3 pipeline/frequences.py [--sortie FICHIER.json]
"""
from __future__ import annotations

import argparse
import json
import math
import subprocess
import sys
from multiprocessing import Pool
from pathlib import Path

import pandas as pd

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))
sys.path.insert(0, str(RACINE / "pipeline"))

import calibrage_figures as cf  # noqa: E402
import calibrage_regime as cr  # noqa: E402
import calibrage_signaux as cs  # noqa: E402

FIN_CALIBRAGE = "2026-10-02"   # dernière séance des données du calibrage du 03/10
DEBUT_MESURE = "2025-01-01"    # période 2025-01 → 2026-10 de l'étape 2
HORIZON = 60                   # séances
SOURCE = "datasets/calibrage_technique/etape2_regime_2026-10-03.json"
SORTIE = RACINE / "datasets" / "frequences_publiees.json"

# clé affichée par le terminal → (signal, régime allumé ?, libellé, condition)
DEFS = {
    "cassure": ("cassure90", True, "Cassure du plus haut 90 jours avec volume", "en tendance"),
    "surachat": ("rsi_sortie_surachat", True, "Sortie de surachat du RSI (la force continue)", "en tendance"),
    "pullback_on": ("pullback", True, "Pullback (repli en tendance haussière)", "en tendance"),
    "pullback_off": ("pullback", False, "Pullback (repli en tendance haussière)", "hors tendance"),
}
DEFINITIONS = {
    "cassure90": "clôture au-dessus du plus haut des 90 séances précédentes ET volume > 1,5 × médiane des 50 séances précédentes",
    "rsi_sortie_surachat": "le RSI 14 repasse sous 70 après avoir été au-dessus la séance précédente",
    "pullback": "cours > MA200, MA50 > MA200 et cours au moins 3 % sous la MA20",
}
REGLE_TENDANCE = "MASI > sa moyenne 200 séances ET plus de 50 % des titres liquides au-dessus de leur MA200"


# ───────────────────────── statistiques ─────────────────────────

def wilson(k: int, n: int, z: float = 1.959964) -> tuple[float, float]:
    """Intervalle de Wilson à 95 % d'une proportion k/n."""
    if n <= 0:
        return (float("nan"), float("nan"))
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    m = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (max(0.0, c - m), min(1.0, c + m))


def diff_proportions(k1: int, n1: int, k2: int, n2: int) -> dict:
    """Test z de différence de deux proportions (variance combinée), bilatéral.
    Hypothèse d'indépendance des observations : ici elles se chevauchent, le p
    est donc OPTIMISTE — dit dans le fichier publié."""
    if min(n1, n2) <= 0:
        return {"ecart_points": None, "z": None, "p": None}
    p1, p2 = k1 / n1, k2 / n2
    pc = (k1 + k2) / (n1 + n2)
    se = math.sqrt(pc * (1 - pc) * (1 / n1 + 1 / n2))
    if se == 0:
        return {"ecart_points": round(100 * (p1 - p2), 1), "z": None, "p": None}
    z = (p1 - p2) / se
    return {"ecart_points": round(100 * (p1 - p2), 1), "z": round(z, 2),
            "p": float(f"{math.erfc(abs(z) / math.sqrt(2)):.3g}")}


def resume(alpha: pd.Series, rendement: pd.Series, frais: float = cs.FRAIS_AR) -> dict:
    """Effectif, alpha moyen/médian, gagnants (alpha > 0) et IC de Wilson."""
    a = alpha.dropna()
    n = int(len(a))
    if n == 0:
        return {"n": 0}
    k = int((a > 0).sum())
    lo, hi = wilson(k, n)
    return {"n": n, "gagnants_k": k,
            "pct_gagnants": round(100 * k / n, 1),
            "ic95_gagnants": [round(100 * lo, 1), round(100 * hi, 1)],
            "alpha_moyen_pct": round(100 * float(a.mean()), 2),
            "alpha_median_pct": round(100 * float(a.median()), 2),
            "rendement_net_frais_moyen_pct": round(100 * float(rendement.loc[a.index].mean() - frais), 2)}


# ───────────────────────── collecte ─────────────────────────

def collecter(fin: str | None) -> dict:
    """Occurrences des trois signaux, avec leur régime, sur des chandelles
    tronquées à `fin` (None = tout). Renvoie {signal: DataFrame}, plus la
    clé "_resolus" : ensemble des (titre, date) dont l'alpha à 60 séances est
    connu à `fin`."""
    cs.FIN = cf.FIN = fin
    try:
        p = cr.panel()
        reg = cr.regimes(p)
        p = p.join(reg, on="date")
        titres = [f.stem for f in sorted((RACINE / "pipeline" / "candles").glob("*.json"))]
        with Pool() as pool:
            fig = pd.DataFrame([o for lot in pool.map(cf._evenements, titres) for o in lot])
        fig["date"] = pd.to_datetime(fig["date"])
        fig = fig.join(reg, on="date")
        seuil = float(p["montant_median"].quantile(1 / 3))
        fig = fig[fig["montant"] >= seuil]
        liq = p[(p["liquidite"] != "basse") & (p["date"] >= DEBUT_MESURE)]
        fig = fig[fig["date"] >= DEBUT_MESURE]
    finally:
        cs.FIN = cf.FIN = None
    # ⚠️ La dé-duplication (une occurrence par titre et par fenêtre de 28 jours)
    # se fait DANS chaque régime, comme calibrage_regime.main() — l'inverse
    # donnerait 193 / 38 au lieu de 200 / 58 pour le pullback.
    def par_regime(x: str) -> pd.DataFrame:
        return pd.concat([cr._dedup(liq[liq["tendance"] == etat], x) for etat in (True, False)])

    out = {"pullback": par_regime("pullback"), "cassure90": par_regime("cassure90"),
           "rsi_sortie_surachat": fig[fig["signal"] == "rsi_sortie_surachat"]}
    # Sélection des colonnes utiles, mêmes noms partout.
    for k, e in out.items():
        out[k] = e[["t", "date", "tendance", f"a{HORIZON}", f"r{HORIZON}"]].copy()
    out["_resolus"] = set(zip(p.loc[p[f"a{HORIZON}"].notna(), "t"],
                              p.loc[p[f"a{HORIZON}"].notna(), "date"]))
    return out


def calculer(fin: str = FIN_CALIBRAGE) -> dict:
    """{clé: résumé} pour les quatre fréquences, mesurées à `fin`, et les
    comparaisons « en tendance / hors tendance » de chaque signal."""
    occ = collecter(fin)
    freq, grp = {}, {}
    for cle, (sig, etat, _lib, _cond) in DEFS.items():
        e = occ[sig]
        e = e[e["tendance"] == etat]
        freq[cle] = resume(e[f"a{HORIZON}"], e[f"r{HORIZON}"])
    for sig in DEFINITIONS:
        e = occ[sig].dropna(subset=[f"a{HORIZON}"])
        for etat in (True, False):
            s = e[e["tendance"] == etat][f"a{HORIZON}"]
            grp[(sig, etat)] = (int((s > 0).sum()), int(len(s)))
    return {"frequences": freq, "groupes": grp}


def utilite(groupes: dict) -> list[dict]:
    """Une fréquence qui ne distingue rien doit être signalée : pour chaque
    signal, % gagnants en tendance contre hors tendance et p du test."""
    res = []
    for sig in DEFINITIONS:
        k1, n1 = groupes[(sig, True)]
        k0, n0 = groupes[(sig, False)]
        t = diff_proportions(k1, n1, k0, n0)
        p = t["p"]
        if min(n1, n0) < 30:
            verdict = "effectif trop faible pour conclure (un groupe < 30 cas)"
        elif p is not None and p < 0.05:
            verdict = "distingue les deux situations (p < 0,05, indépendance supposée)"
        else:
            verdict = "NE DISTINGUE PAS les deux situations (p >= 0,05)"
        res.append({"signal": sig,
                    "en_tendance": {"n": n1, "gagnants_k": k1, "pct_gagnants": round(100 * k1 / n1, 1) if n1 else None},
                    "hors_tendance": {"n": n0, "gagnants_k": k0, "pct_gagnants": round(100 * k0 / n0, 1) if n0 else None},
                    **t, "verdict": verdict})
    return res


def _commit(chemin: str) -> str | None:
    try:
        r = subprocess.run(["git", "log", "-1", "--format=%h", "--", chemin], cwd=RACINE,
                           capture_output=True, text=True, timeout=20)
        return r.stdout.strip() or None
    except (OSError, subprocess.SubprocessError):
        return None


def construire() -> dict:
    c = calculer(FIN_CALIBRAGE)
    freqs = {}
    for cle, (sig, etat, lib, cond) in DEFS.items():
        freqs[cle] = {"libelle": lib, "condition": cond, "signal": sig,
                      "definition_signal": DEFINITIONS[sig], "regle_tendance": REGLE_TENDANCE,
                      "horizon_seances": HORIZON,
                      "periode_mesure": {"debut": DEBUT_MESURE, "fin_donnees": FIN_CALIBRAGE},
                      "univers": "titres liquides (deux tiers supérieurs du montant médian échangé)",
                      "mesure": "alpha = rendement total du titre moins rendement du MASI, à 60 séances",
                      "frais_inclus": False,
                      **c["frequences"][cle],
                      "source": {"fichier": SOURCE, "commit": _commit(SOURCE)}}
    return {"_quoi": "Fréquences observées des signaux techniques — source unique du terminal",
            "_avertissement": ("Fréquences passées, pas des promesses. Observations chevauchantes "
                               "(un même mouvement compte plusieurs fois) : les intervalles et les p "
                               "sont optimistes. Un seul régime de marché sur la période. "
                               "Alpha brut de frais ; rendement_net_frais_moyen_pct retranche 2 % d'aller-retour."),
            "_ne_pas_editer": "Produit par pipeline/frequences.py ; tests/test_frequences.py le recalcule.",
            "_r8": "Ces signaux n'entrent pas dans la note (mode ombre) : aucune note ne dépend de ce fichier.",
            "fin_calibrage": FIN_CALIBRAGE,
            "frequences": freqs,
            "utilite": utilite(c["groupes"])}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sortie", default=str(SORTIE))
    arg = ap.parse_args()
    res = construire()
    Path(arg.sortie).write_text(json.dumps(res, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    for k, f in res["frequences"].items():
        print(k, f["n"], f["pct_gagnants"], f["ic95_gagnants"], f["alpha_moyen_pct"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
