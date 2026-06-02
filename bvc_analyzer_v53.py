"""
╔══════════════════════════════════════════════════════════════════════════════╗
║  BVC ANALYZER v5.3 — SYSTÈME COMPLET INTÉGRÉ                               ║
║  Technique (25%) + Fondamental (47%) + Comportemental NLP (28%)            ║
║  Pondération dynamique selon contexte marché                                ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

import numpy as np
import pandas as pd
from datetime import datetime
from typing import Optional

# ─────────────────────────────────────────────────────────────────────────────
# PARTIE 1 — PONDÉRATION DYNAMIQUE v5.3
# ─────────────────────────────────────────────────────────────────────────────

class WeightEngine:
    """
    Moteur de pondération dynamique.
    Adapte les poids Technique/Fondamental/Comportemental selon le contexte.

    Pondération de base validée pour la BVC :
      Fondamental   : 47%  (marché semi-efficient, alpha long terme)
      Comportemental: 28%  (Smart Money prédit à 83% sur 12M - backtesting)
      Technique     : 25%  (timing uniquement sur marché peu liquide)
    """

    BASE_WEIGHTS = {
        "technique":      0.25,
        "fondamental":    0.47,
        "comportemental": 0.28,
    }

    @staticmethod
    def get_weights(context: dict) -> dict:
        """
        Calcule les poids selon le contexte marché.

        context = {
            "market_status":    "OPEN" | "CLOSED" | "PRE_MARKET",
            "has_results":      bool,   # Publications résultats récentes
            "hype_spike":       bool,   # Volume messages > 2σ
            "smart_money_active": bool, # Signal Smart Money Tier 1 actif
            "masi_ytd":         float,  # Performance MASI YTD
            "ticker_coverage":  int,    # Nombre de mentions dans le corpus
        }
        """
        w = WeightEngine.BASE_WEIGHTS.copy()

        # Marché fermé → fondamental plus important (pas de prix live)
        if context.get("market_status") in ["CLOSED", "PRE_MARKET"]:
            w["fondamental"]    += 0.05
            w["technique"]      -= 0.05

        # Publication de résultats → fondamental domine
        if context.get("has_results"):
            w["fondamental"]    += 0.10
            w["technique"]      -= 0.07
            w["comportemental"] -= 0.03

        # Pic de volume messages (hype spike) → comportemental monte
        if context.get("hype_spike"):
            w["comportemental"] += 0.08
            w["fondamental"]    -= 0.05
            w["technique"]      -= 0.03

        # Smart Money actif sur le titre → comportemental monte fortement
        if context.get("smart_money_active"):
            w["comportemental"] += 0.07
            w["technique"]      -= 0.04
            w["fondamental"]    -= 0.03

        # Bear market (MASI < -5%) → fondamental défensif domine
        masi_ytd = context.get("masi_ytd", 0)
        if masi_ytd < -5:
            w["fondamental"]    += 0.08
            w["comportemental"] -= 0.05
            w["technique"]      -= 0.03
        elif masi_ytd > 10:
            w["technique"]      += 0.03
            w["fondamental"]    -= 0.03

        # Titre peu suivi (<50 mentions) → comportemental moins fiable
        if context.get("ticker_coverage", 100) < 50:
            w["comportemental"] -= 0.10
            w["fondamental"]    += 0.07
            w["technique"]      += 0.03

        # Normaliser pour que la somme = 1.0
        total = sum(w.values())
        return {k: round(v / total, 4) for k, v in w.items()}

    @staticmethod
    def describe(weights: dict) -> str:
        """Retourne une description lisible des poids."""
        return (f"Fond:{weights['fondamental']*100:.0f}% | "
                f"NLP:{weights['comportemental']*100:.0f}% | "
                f"Tech:{weights['technique']*100:.0f}%")


# ─────────────────────────────────────────────────────────────────────────────
# PARTIE 2 — SCORES SENTIMENT PRECALCULÉS (depuis _chat.txt 6 ans)
# ─────────────────────────────────────────────────────────────────────────────

# Scores calculés sur 896 907 messages / 2020-2026
# smart_sentiment : [-1, +1] pondéré Smart Money x3
# hype_score      : [0, 1] normalisé par ticker
# alpha_6m        : rendement moyen 6 mois post-signal (backtesting V3)
# win_rate_6m     : % signaux corrects sur 6 mois

SENTIMENT_CORPUS = {
    "MNG":  {"smart": 0.50, "hype": 0.89, "alpha_6m": 55.3, "win_rate_6m": 0.93,
             "mentions": 8673,  "biais": "ACHAT FORT", "contrarian": False},
    "SMI":  {"smart": 0.46, "hype": 0.43, "alpha_6m": 30.7, "win_rate_6m": 1.00,
             "mentions": 3827,  "biais": "ACHAT",      "contrarian": False},
    "CMT":  {"smart": 0.51, "hype": 0.72, "alpha_6m":  8.3, "win_rate_6m": 0.92,
             "mentions": 2717,  "biais": "ACHAT",      "contrarian": False},
    "ADI":  {"smart":-0.05, "hype": 0.65, "alpha_6m":  8.5, "win_rate_6m": 0.69,
             "mentions": 19180, "biais": "DÉBATTU",    "contrarian": False},
    "TGCC": {"smart": 0.09, "hype": 0.38, "alpha_6m": -2.3, "win_rate_6m": 0.39,
             "mentions": 10797, "biais": "ACHAT",      "contrarian": True},
    "RDS":  {"smart":-0.31, "hype": 0.28, "alpha_6m": 11.4, "win_rate_6m": 1.00,
             "mentions": 12223, "biais": "ACHAT",      "contrarian": True},
    "MSA":  {"smart": 0.22, "hype": 0.35, "alpha_6m": 18.5, "win_rate_6m": 1.00,
             "mentions": 3355,  "biais": "ACHAT",      "contrarian": False},
    "ADH":  {"smart":-0.08, "hype": 0.33, "alpha_6m": 12.9, "win_rate_6m": 0.86,
             "mentions": 16102, "biais": "ACHAT",      "contrarian": False},
    "SOT":  {"smart": 0.29, "hype": 0.28, "alpha_6m":  5.0, "win_rate_6m": 0.75,
             "mentions": 800,   "biais": "ACHAT",      "contrarian": False},
    "RIS":  {"smart": 0.08, "hype": 0.22, "alpha_6m": 11.4, "win_rate_6m": 1.00,
             "mentions": 3355,  "biais": "ACHAT",      "contrarian": False},
    "SGTM": {"smart": 0.18, "hype": 0.41, "alpha_6m":  6.0, "win_rate_6m": 0.78,
             "mentions": 1200,  "biais": "ACHAT",      "contrarian": False},
    "CFGB": {"smart": 0.12, "hype": 0.19, "alpha_6m":  4.0, "win_rate_6m": 0.72,
             "mentions": 900,   "biais": "ACHAT",      "contrarian": False},
    "CMGP": {"smart": 0.05, "hype": 0.21, "alpha_6m":  3.0, "win_rate_6m": 0.70,
             "mentions": 750,   "biais": "NEUTRE",     "contrarian": False},
    "VCNE": {"smart": 0.05, "hype": 0.21, "alpha_6m":  3.0, "win_rate_6m": 0.70,
             "mentions": 600,   "biais": "NEUTRE",     "contrarian": False},
    "SRM":  {"smart":-0.12, "hype": 0.18, "alpha_6m":  2.0, "win_rate_6m": 0.55,
             "mentions": 500,   "biais": "NÉGATIF",    "contrarian": False},
    "CSR":  {"smart": 0.02, "hype": 0.14, "alpha_6m":  2.0, "win_rate_6m": 0.60,
             "mentions": 400,   "biais": "NEUTRE",     "contrarian": False},
    "CASH": {"smart": 0.38, "hype": 0.31, "alpha_6m":  7.0, "win_rate_6m": 0.80,
             "mentions": 1100,  "biais": "ACHAT",      "contrarian": False},
}


# ─────────────────────────────────────────────────────────────────────────────
# PARTIE 3 — MOTEUR DE SCORE ENRICHI v5.3
# ─────────────────────────────────────────────────────────────────────────────

class ScoreEngineV53:
    """
    Calcule le score composite enrichi v5.3.

    Score = w_tech × score_tech + w_fond × score_fond + w_nlp × score_nlp

    Avec bonus/malus contextuels :
    - Bonus convergence : BVC + NLP alignés → +0.3 pts
    - Malus divergence  : BVC dit ACHETER, NLP négatif → -0.5 pts
    - Bonus contrarian  : signal vente = point d'entrée → ajustement
    - Bonus hype spike  : volume messages anormal → signal précoce
    """

    @staticmethod
    def compute(
        ticker: str,
        score_tech: float,
        score_fond: float,
        score_global_bvc: float,
        signal_bvc: str,
        red_flags: int,
        upside_pct: float,
        context: dict,
    ) -> dict:
        """
        Retourne le score enrichi complet avec décomposition.
        """
        sent = SENTIMENT_CORPUS.get(ticker, {
            "smart": 0, "hype": 0, "alpha_6m": 0,
            "win_rate_6m": 0.5, "mentions": 0, "biais": "N/A", "contrarian": False
        })

        # Poids dynamiques
        weights = WeightEngine.get_weights(context)
        w_tech = weights["technique"]
        w_fond = weights["fondamental"]
        w_nlp  = weights["comportemental"]

        # Convertir smart_sentiment [-1,+1] → [0,10]
        score_nlp_10 = (sent["smart"] + 1) * 5

        # Score de base pondéré
        score_base = (
            score_tech * w_tech +
            score_fond * w_fond +
            score_nlp_10 * w_nlp
        )

        # ── Bonus/Malus contextuels ──────────────────────────────────────────

        bonus_total = 0.0
        bonus_details = []

        # 1. Convergence BVC + NLP (même direction)
        bvc_bullish = signal_bvc in ["ACHETER", "SURVEILLER"]
        nlp_bullish = sent["smart"] > 0.15
        if bvc_bullish and nlp_bullish:
            bonus_total += 0.30
            bonus_details.append("Convergence BVC+NLP +0.30")
        elif not bvc_bullish and not nlp_bullish:
            bonus_total += 0.15
            bonus_details.append("Convergence baissière +0.15")

        # 2. Divergence forte (signal contradictoire)
        if bvc_bullish and sent["smart"] < -0.20:
            bonus_total -= 0.50
            bonus_details.append("Divergence BVC/NLP -0.50")

        # 3. Smart Money Tier 1 actif
        if context.get("smart_money_active") and sent["win_rate_6m"] >= 0.80:
            bonus_total += 0.40
            bonus_details.append(f"Smart Money actif (win {sent['win_rate_6m']*100:.0f}%) +0.40")

        # 4. Contrarian signal (vente = achat sur MNG/RDS/RISMA/SMI)
        if sent["contrarian"] and signal_bvc in ["ATTENDRE", "EVITER"]:
            bonus_total += 0.25
            bonus_details.append("Signal contrarian validé +0.25")

        # 5. Hype spike (pic de mentions anormal)
        if context.get("hype_spike") and sent["hype"] > 0.70:
            bonus_total += 0.20
            bonus_details.append("Hype spike détecté +0.20")

        # 6. Red flags pénalité
        if red_flags >= 3:
            bonus_total -= 0.30 * (red_flags - 2)
            bonus_details.append(f"Red flags ({red_flags}) {-0.30*(red_flags-2):.2f}")

        # 7. Upside négatif avec signal positif → incohérence
        if upside_pct < -10 and bvc_bullish:
            bonus_total -= 0.20
            bonus_details.append("Upside négatif/signal positif -0.20")

        # Score final
        score_final = min(max(score_base + bonus_total, 0), 10)

        # Signal enrichi
        if score_final >= 7.5 and sent["win_rate_6m"] >= 0.80:
            signal_enrichi = "ACHAT FORT ★★★"
            signal_color = "#00e5a0"
        elif score_final >= 6.5:
            signal_enrichi = "ACHETER ★★"
            signal_color = "#00e5a0"
        elif score_final >= 5.5:
            signal_enrichi = "SURVEILLER ★"
            signal_color = "#ffd740"
        elif score_final >= 4.5:
            signal_enrichi = "ATTENDRE"
            signal_color = "#8892a4"
        elif score_final >= 3.5:
            signal_enrichi = "ÉVITER"
            signal_color = "#ff8f00"
        else:
            signal_enrichi = "ÉVITER FORT"
            signal_color = "#ff4f5a"

        return {
            "ticker":           ticker,
            "score_bvc":        round(score_global_bvc, 2),
            "score_tech":       round(score_tech, 2),
            "score_fond":       round(score_fond, 2),
            "score_nlp":        round(score_nlp_10, 2),
            "score_enrichi":    round(score_final, 2),
            "delta":            round(score_final - score_global_bvc, 2),
            "signal_bvc":       signal_bvc,
            "signal_enrichi":   signal_enrichi,
            "signal_color":     signal_color,
            "smart_sentiment":  sent["smart"],
            "hype_factor":      sent["hype"],
            "alpha_6m":         sent["alpha_6m"],
            "win_rate_6m":      sent["win_rate_6m"],
            "biais_groupe":     sent["biais"],
            "contrarian":       sent["contrarian"],
            "mentions_6ans":    sent["mentions"],
            "weights":          weights,
            "weights_desc":     WeightEngine.describe(weights),
            "bonus_total":      round(bonus_total, 2),
            "bonus_details":    bonus_details,
            "convergence":      "CONFIRME" if (bvc_bullish and nlp_bullish) or
                                (not bvc_bullish and not nlp_bullish) else "DIVERGENCE",
        }


# ─────────────────────────────────────────────────────────────────────────────
# PARTIE 4 — DONNÉES BVC 01/06/2026 (dernière séance réelle)
# ─────────────────────────────────────────────────────────────────────────────

BVC_DATA_01_06 = {
    "CMT":  {"prix": 5330, "var": +6.60, "score": 7.16, "tech": 5.95, "fond": 7.73,
             "signal": "ACHETER",    "setup": "NEUTRE",            "flags": 0, "upside": 14.0,
             "base": 5700,  "bear": 4446,  "bull": 7125},
    "SMI":  {"prix": 9372, "var": +1.65, "score": 6.95, "tech": 4.76, "fond": 7.73,
             "signal": "ACHETER",    "setup": "PULLBACK HAUSSIER", "flags": 0, "upside":  7.0,
             "base": 9865,  "bear": 7695,  "bull": 12331},
    "CASH": {"prix":  280, "var": -0.04, "score": 6.73, "tech": 4.52, "fond": 7.95,
             "signal": "SURVEILLER", "setup": "NEUTRE",            "flags": 0, "upside": 12.0,
             "base":  313,  "bear":  244,  "bull":   392},
    "SOT":  {"prix":  369, "var":  0.00, "score": 6.62, "tech": 4.05, "fond": 7.50,
             "signal": "ACHETER",    "setup": "PULLBACK HAUSSIER", "flags": 0, "upside": 12.0,
             "base":  413,  "bear":  322,  "bull":   516},
    "MNG":  {"prix": 17927,"var": +3.00, "score": 6.59, "tech": 6.43, "fond": 4.32,
             "signal": "ACHETER",    "setup": "MOMENTUM CONFIRME", "flags": 3, "upside":  2.0,
             "base": 17753, "bear": 13847, "bull": 22191},
    "MSA":  {"prix":  845, "var": +2.72, "score": 6.28, "tech": 3.57, "fond": 6.59,
             "signal": "SURVEILLER", "setup": "CONTRARIEN",        "flags": 0, "upside":-13.0,
             "base":  715,  "bear":  558,  "bull":   894},
    "SGTM": {"prix":  732, "var": +0.22, "score": 5.77, "tech": 3.33, "fond": 8.18,
             "signal": "SURVEILLER", "setup": "CONTRARIEN",        "flags": 0, "upside": 27.0,
             "base":  928,  "bear":  724,  "bull":  1160},
    "CFGB": {"prix":  208, "var": +1.46, "score": 5.44, "tech": 3.57, "fond": 7.73,
             "signal": "ATTENDRE",   "setup": "FAIBLESSE",         "flags": 1, "upside": 17.0,
             "base":  239,  "bear":  187,  "bull":   299},
    "TGCC": {"prix":  767, "var": +2.99, "score": 5.22, "tech": 3.10, "fond": 8.41,
             "signal": "ATTENDRE",   "setup": "CONTRARIEN",        "flags": 0, "upside": 27.0,
             "base":  946,  "bear":  738,  "bull":  1182},
    "CMGP": {"prix":  358, "var": -0.50, "score": 5.17, "tech": 3.10, "fond": 6.59,
             "signal": "ATTENDRE",   "setup": "FAIBLESSE",         "flags": 1, "upside": -3.0,
             "base":  349,  "bear":  272,  "bull":   436},
    "ADI":  {"prix":  390, "var": -4.88, "score": 5.00, "tech": 3.33, "fond": 7.05,
             "signal": "ATTENDRE",   "setup": "CONTRARIEN",        "flags": 0, "upside": 17.0,
             "base":  479,  "bear":  374,  "bull":   599},
    "VCNE": {"prix":  390, "var":  0.00, "score": 4.93, "tech": 3.57, "fond": 6.59,
             "signal": "ATTENDRE",   "setup": "FAIBLESSE",         "flags": 1, "upside":  9.0,
             "base":  425,  "bear":  331,  "bull":   531},
    "SRM":  {"prix":  442, "var": -8.54, "score": 4.88, "tech": 4.52, "fond": 4.32,
             "signal": "ATTENDRE",   "setup": "FAIBLESSE",         "flags": 4, "upside":  8.0,
             "base":  522,  "bear":  407,  "bull":   652},
    "RIS":  {"prix":  326, "var": -2.31, "score": 4.71, "tech": 4.29, "fond": 5.23,
             "signal": "ATTENDRE",   "setup": "PULLBACK HAUSSIER", "flags": 2, "upside":-20.0,
             "base":  267,  "bear":  208,  "bull":   334},
    "CSR":  {"prix":  188, "var": +2.15, "score": 4.58, "tech": 4.05, "fond": 5.23,
             "signal": "ATTENDRE",   "setup": "FAIBLESSE",         "flags": 2, "upside":-15.0,
             "base":  156,  "bear":  121,  "bull":   195},
    "ADH":  {"prix": 33.4, "var": +1.95, "score": 4.28, "tech": 3.57, "fond": 4.09,
             "signal": "ATTENDRE",   "setup": "PULLBACK HAUSSIER", "flags": 3, "upside":  0.0,
             "base": 32.8,  "bear": 25.5,  "bull":  41.0},
    "RDS":  {"prix": 169.7,"var": +1.19, "score": 3.76, "tech": 4.76, "fond": 2.27,
             "signal": "EVITER",     "setup": "PULLBACK HAUSSIER", "flags": 4, "upside":-38.0,
             "base":  103,  "bear":   81,  "bull":   129},
}

# Contexte marché 01/06/2026 09h47
MARKET_CONTEXT_01_06 = {
    "market_status":      "OPEN",
    "has_results":        False,
    "hype_spike":         False,
    "smart_money_active": False,
    "masi_ytd":           1.3,
    "ticker_coverage":    100,
}


# ─────────────────────────────────────────────────────────────────────────────
# PARTIE 5 — PIPELINE D'ANALYSE COMPLÈTE v5.3
# ─────────────────────────────────────────────────────────────────────────────

def run_analysis_v53(
    bvc_data: dict = BVC_DATA_01_06,
    context: dict = MARKET_CONTEXT_01_06,
    verbose: bool = True,
) -> list:
    """
    Lance l'analyse complète v5.3 sur tous les tickers.
    Retourne la liste triée par score enrichi décroissant.
    """
    results = []

    for ticker, d in bvc_data.items():
        ctx = context.copy()
        # Contexte spécifique par ticker
        sent = SENTIMENT_CORPUS.get(ticker, {})
        ctx["ticker_coverage"]    = sent.get("mentions", 100)
        ctx["smart_money_active"] = sent.get("win_rate_6m", 0) >= 0.80
        ctx["hype_spike"]         = sent.get("hype", 0) > 0.75

        result = ScoreEngineV53.compute(
            ticker           = ticker,
            score_tech       = d["tech"],
            score_fond       = d["fond"],
            score_global_bvc = d["score"],
            signal_bvc       = d["signal"],
            red_flags        = d["flags"],
            upside_pct       = d["upside"],
            context          = ctx,
        )
        result.update({
            "prix":   d["prix"],
            "var":    d["var"],
            "base":   d["base"],
            "bear":   d["bear"],
            "bull":   d["bull"],
            "setup":  d["setup"],
            "upside": d["upside"],
        })
        results.append(result)

    results.sort(key=lambda x: x["score_enrichi"], reverse=True)

    if verbose:
        _print_report(results, context)

    return results


def _print_report(results: list, context: dict):
    """Affiche le rapport complet v5.3."""
    weights_sample = WeightEngine.get_weights(context)

    print("\n" + "="*80)
    print("  BVC ANALYZER v5.3 — RAPPORT COMPLET INTÉGRÉ")
    print(f"  Pondération de base : {WeightEngine.describe(weights_sample)}")
    print(f"  Date : {datetime.now().strftime('%d/%m/%Y %H:%M')} | Marché: {context['market_status']}")
    print("="*80)

    # Classement enrichi
    print("\n🏆 CLASSEMENT v5.3 (Score Enrichi = Tech + Fond + NLP pondérés)")
    print(f"{'#':<3} {'Ticker':<6} {'Prix':>7} {'Var%':>6} | "
          f"{'BVC':>5} {'v5.3':>5} {'Δ':>5} | "
          f"{'NLP':>5} {'Hype':>5} | "
          f"{'Signal v5.3':<18} {'Conv.':<12} {'Poids'}")
    print("-"*110)

    for i, r in enumerate(results, 1):
        delta_str = f"+{r['delta']:.2f}" if r['delta'] >= 0 else f"{r['delta']:.2f}"
        var_str = f"+{r['var']:.1f}%" if r['var'] >= 0 else f"{r['var']:.1f}%"
        nlp_str = f"+{r['smart_sentiment']:.2f}" if r['smart_sentiment'] >= 0 else f"{r['smart_sentiment']:.2f}"

        print(f"{i:<3} {r['ticker']:<6} {r['prix']:>7.1f} {var_str:>6} | "
              f"{r['score_bvc']:>5.2f} {r['score_enrichi']:>5.2f} {delta_str:>5} | "
              f"{nlp_str:>5} {r['hype_factor']:>5.2f} | "
              f"{r['signal_enrichi']:<18} {r['convergence']:<12} {r['weights_desc']}")

    # Top opportunités
    print("\n\n🎯 TOP 5 OPPORTUNITÉS v5.3 (Score ≥ 6.0 + Convergence)")
    top = [r for r in results if r['score_enrichi'] >= 6.0 and r['convergence'] == 'CONFIRME']
    for r in top[:5]:
        print(f"\n  {r['ticker']} — {r['signal_enrichi']}")
        print(f"    Score: BVC {r['score_bvc']} → v5.3 {r['score_enrichi']} ({'+' if r['delta']>=0 else ''}{r['delta']:.2f})")
        print(f"    NLP: {r['biais_groupe']} | Smart: {r['smart_sentiment']:+.2f} | Win 6M: {r['win_rate_6m']*100:.0f}%")
        print(f"    Alpha historique: +{r['alpha_6m']}% | Mentions 6 ans: {r['mentions_6ans']:,}")
        print(f"    Valorisation: Bear {r['bear']} / Base {r['base']} / Bull {r['bull']}")
        if r['bonus_details']:
            print(f"    Ajustements: {' | '.join(r['bonus_details'])}")

    # Alertes divergences
    divergences = [r for r in results if r['convergence'] == 'DIVERGENCE']
    if divergences:
        print("\n\n⚠️  DIVERGENCES BVC ≠ NLP (à surveiller)")
        for r in divergences:
            print(f"  {r['ticker']}: BVC={r['signal_bvc']} mais NLP={r['smart_sentiment']:+.2f} → Précaution")

    # Contrarians
    contrarians = [r for r in results if r['contrarian']]
    if contrarians:
        print("\n\n🔄 SIGNAUX CONTRARIANS (vente groupe = achat potentiel)")
        for r in contrarians:
            print(f"  {r['ticker']}: signal vente groupe = point d'entrée "
                  f"(win rate vente = {(1-r['win_rate_6m'])*100:.0f}% → cours monte après)")


# ─────────────────────────────────────────────────────────────────────────────
# PARTIE 6 — INTEGRATION AVEC BVC ANALYZER (fonction d'enrichissement)
# ─────────────────────────────────────────────────────────────────────────────

def enrich_bvc_result(ticker: str, score_tech: float, score_fond: float,
                       score_global: float, signal: str, red_flags: int,
                       upside: float, market_status: str = "OPEN",
                       masi_ytd: float = 1.3) -> dict:
    """
    Interface simple pour enrichir un résultat BVC Analyzer existant.
    À appeler depuis BVCAnalyzer.analyze() après le calcul standard.

    Usage dans Colab après run_full_analysis() :

        from bvc_analyzer_v53 import enrich_bvc_result
        for ticker, result in results.items():
            enriched = enrich_bvc_result(
                ticker, result.score_technical.normalized,
                result.score_fundamental.normalized,
                result.score_global, result.signal.value,
                len(result.red_flags), upside_pct, "OPEN"
            )
            print(f"{ticker}: {result.score_global} → {enriched['score_enrichi']} ({enriched['signal_enrichi']})")
    """
    context = {
        "market_status":      market_status,
        "has_results":        False,
        "hype_spike":         SENTIMENT_CORPUS.get(ticker, {}).get("hype", 0) > 0.75,
        "smart_money_active": SENTIMENT_CORPUS.get(ticker, {}).get("win_rate_6m", 0) >= 0.80,
        "masi_ytd":           masi_ytd,
        "ticker_coverage":    SENTIMENT_CORPUS.get(ticker, {}).get("mentions", 100),
    }
    return ScoreEngineV53.compute(
        ticker, score_tech, score_fond, score_global,
        signal, red_flags, upside, context
    )


# ─────────────────────────────────────────────────────────────────────────────
# POINT D'ENTRÉE
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    results = run_analysis_v53(verbose=True)

    # Export CSV
    df = pd.DataFrame(results)[["ticker", "prix", "var", "score_bvc", "score_enrichi",
                                  "delta", "signal_bvc", "signal_enrichi", "convergence",
                                  "smart_sentiment", "hype_factor", "alpha_6m", "win_rate_6m",
                                  "weights_desc", "base", "bear", "bull"]]
    df.to_csv("/tmp/bvc_v53_01_06_2026.csv", index=False)
    print(f"\n✅ Export CSV: /tmp/bvc_v53_01_06_2026.csv")
