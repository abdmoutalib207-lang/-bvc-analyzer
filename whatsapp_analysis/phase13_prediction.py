"""
Phase 13 — Moteur de Prédiction Composite
Score composite 0-100 par valeur BVC + probabilités ML + signaux finaux
"""
from __future__ import annotations

import json
import logging
import warnings
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")
logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────────────────────
FINANCIAL_DATA_PATH = Path(__file__).parent.parent / "financial_data.json"
DATA_JSON_PATH = Path(__file__).parent.parent / "data.json"

# Poids du score composite (totalisent 100%)
DEFAULT_WEIGHTS = {
    "fundamental": 0.25,    # PE, PB, dividende, capex, etc.
    "technical": 0.20,      # RSI, MACD, BB, momentum prix
    "nlp_sentiment": 0.20,  # Sentiment NLP du groupe WhatsApp
    "smart_money": 0.20,    # Score Smart Money membres
    "network_momentum": 0.10,  # Métriques réseau (centralité, activité)
    "behavioral_regime": 0.05,  # Fear & Greed
}

# Seuils de signal
SIGNAL_THRESHOLDS = {
    "FORT_ACHAT": 75,
    "ACHAT": 60,
    "NEUTRE_UPPER": 60,
    "NEUTRE_LOWER": 40,
    "VENTE": 25,
    "FORT_VENTE": 0,
}

PREDICTION_HORIZONS = [30, 90, 180, 365]  # jours


# ─────────────────────────────────────────────────────────────
# CHARGEMENT DES DONNÉES FONDAMENTALES
# ─────────────────────────────────────────────────────────────

def load_fundamental_data() -> Dict[str, Dict[str, Any]]:
    """
    Charge les données fondamentales depuis financial_data.json et data.json.
    Retourne: dict ticker -> {pe, pb, div_yield, rsi, alpha, win_rate, ...}
    """
    fundamental: Dict[str, Dict[str, Any]] = {}

    # financial_data.json
    if FINANCIAL_DATA_PATH.exists():
        try:
            with open(FINANCIAL_DATA_PATH, "r", encoding="utf-8") as f:
                fd = json.load(f)
            data = fd.get("data", {})
            for ticker, info in data.items():
                if not isinstance(info, dict):
                    continue
                market = info.get("market", {}) or {}
                tech = info.get("technical", {}) or {}
                fund = info.get("fundamentals", {}) or {}
                sm = info.get("smart_money", {}) or {}

                fundamental[ticker] = {
                    "price": float(market.get("price", 0) or 0),
                    "variation_pct": float(market.get("variation_pct", 0) or 0),
                    "volume": float(market.get("volume", 0) or 0),
                    "pe_ratio": float(fund.get("pe_ratio_ttm", 0) or 0),
                    "pb_ratio": float(fund.get("pb_ratio", 0) or 0),
                    "div_yield": float(fund.get("dividend_yield", 0) or 0),
                    "market_cap": float(fund.get("market_cap_mdh", 0) or 0),
                    "rsi": float(tech.get("rsi_14", 50) or 50),
                    "ma20": float(tech.get("ma20", 0) or 0),
                    "ma50": float(tech.get("ma50", 0) or 0),
                    "high_90d": float(tech.get("high_90d", 0) or 0),
                    "low_90d": float(tech.get("low_90d", 0) or 0),
                    "alpha_12m": float(sm.get("alpha_12m", 0) or 0),
                    "smart_sentiment": float(sm.get("smart_sentiment", 50) or 50),
                    "win_rate_6m": float(sm.get("win_rate_6m", 50) or 50),
                    "source": "financial_data.json",
                }
        except Exception as e:
            logger.warning(f"financial_data.json: {e}")

    # data.json (complémente)
    if DATA_JSON_PATH.exists():
        try:
            with open(DATA_JSON_PATH, "r", encoding="utf-8") as f:
                dj = json.load(f)
            tickers_list = dj.get("tickers", [])
            if isinstance(tickers_list, list):
                for item in tickers_list:
                    ticker = item.get("symbol", "")
                    if not ticker:
                        continue
                    if ticker in fundamental:
                        # Enrichit les données existantes
                        fundamental[ticker].update({
                            "bvc_score": float(item.get("bvc", 0) or 0),
                            "v53_score": float(item.get("v53", 0) or 0),
                            "nlp_data_json": float(item.get("nlp", 0) or 0),
                            "alpha_data_json": float(item.get("alpha", 0) or 0),
                            "win_data_json": float(item.get("win", 50) or 50),
                            "signal_raw": str(item.get("sig", "")),
                            "bear_price": float(item.get("bear", 0) or 0),
                            "base_price": float(item.get("base", 0) or 0),
                            "bull_price": float(item.get("bull", 0) or 0),
                            "upside_pct": float(item.get("upside", 0) or 0),
                        })
                    else:
                        fundamental[ticker] = {
                            "price": float(item.get("price", 0) or 0),
                            "pe_ratio": float(item.get("pe", 0) or 0),
                            "pb_ratio": float(item.get("pb", 0) or 0),
                            "div_yield": float(item.get("div", 0) or 0),
                            "rsi": float(item.get("rsi", 50) or 50),
                            "ma20": float(item.get("ma20", 0) or 0),
                            "ma50": float(item.get("ma50", 0) or 0),
                            "alpha_data_json": float(item.get("alpha", 0) or 0),
                            "win_data_json": float(item.get("win", 50) or 50),
                            "bvc_score": float(item.get("bvc", 0) or 0),
                            "upside_pct": float(item.get("upside", 0) or 0),
                            "source": "data.json",
                        }
        except Exception as e:
            logger.warning(f"data.json: {e}")

    logger.info(f"Données fondamentales: {len(fundamental)} tickers")
    return fundamental


# ─────────────────────────────────────────────────────────────
# SCORES PAR COMPOSANTE
# ─────────────────────────────────────────────────────────────

def compute_fundamental_score(ticker: str, data: Dict[str, Any]) -> float:
    """
    Score fondamental 0-100.
    Basé sur PE, PB, dividende, alpha historique, upside price.
    """
    sub_scores = []

    # Score PE (bas PE = meilleur, mais PE nul = pas de données)
    pe = data.get("pe_ratio", 0)
    if pe and pe > 0:
        # PE<10: excellent, PE 10-20: bon, PE>30: cher
        pe_score = max(0, min(100, 100 - (pe - 10) * 3))
        sub_scores.append(pe_score)

    # Score PB
    pb = data.get("pb_ratio", 0)
    if pb and pb > 0:
        pb_score = max(0, min(100, 100 - (pb - 1.0) * 15))
        sub_scores.append(pb_score)

    # Score dividende
    div = data.get("div_yield", 0)
    if div and div > 0:
        div_score = min(100, div * 10)  # 10% yield = 100pts
        sub_scores.append(div_score)

    # Score alpha 12m (surperformance historique)
    alpha = data.get("alpha_12m", data.get("alpha_data_json", 0))
    if alpha:
        alpha_score = min(100, max(0, 50 + alpha * 2))
        sub_scores.append(alpha_score)

    # Upside potentiel
    upside = data.get("upside_pct", 0)
    if upside:
        upside_score = min(100, max(0, 50 + upside * 3))
        sub_scores.append(upside_score)

    # BVC score natif
    bvc_score_raw = data.get("bvc_score", data.get("v53_score", 0))
    if bvc_score_raw and bvc_score_raw > 0:
        # Normalisé en 0-100 (BVC score est typiquement 0-10)
        sub_scores.append(min(100, bvc_score_raw * 10))

    if not sub_scores:
        return 50.0  # Score neutre par défaut

    return float(np.mean(sub_scores))


def compute_technical_score(ticker: str, data: Dict[str, Any]) -> float:
    """
    Score technique 0-100.
    Basé sur RSI, position MA, MACD, bandes de Bollinger.
    """
    sub_scores = []
    price = data.get("price", 0) or 0

    # RSI (autour de 50 = neutre, <30 = survendu/opportunité, >70 = surachetée)
    rsi = data.get("rsi", 50) or 50
    if 0 < rsi <= 100:
        if rsi < 30:
            rsi_score = 80.0  # Survendu = opportunité potentielle
        elif rsi < 40:
            rsi_score = 70.0
        elif rsi < 55:
            rsi_score = 55.0
        elif rsi < 70:
            rsi_score = 40.0
        else:
            rsi_score = 25.0  # Surachetée
        sub_scores.append(rsi_score)

    # Position vs MA20 et MA50
    ma20 = data.get("ma20", 0)
    ma50 = data.get("ma50", 0)
    if price > 0 and ma20 > 0:
        ma20_ratio = price / ma20
        if ma20_ratio > 1.05:
            sub_scores.append(65.0)  # Au-dessus MA20 = positif
        elif ma20_ratio > 0.95:
            sub_scores.append(55.0)
        else:
            sub_scores.append(35.0)  # En dessous MA20 = négatif

    if price > 0 and ma50 > 0:
        ma50_ratio = price / ma50
        if ma50_ratio > 1.03:
            sub_scores.append(65.0)
        elif ma50_ratio > 0.97:
            sub_scores.append(50.0)
        else:
            sub_scores.append(35.0)

    # Position 90j: distance du plus bas (force relative)
    high_90 = data.get("high_90d", 0)
    low_90 = data.get("low_90d", 0)
    if price > 0 and high_90 > 0 and low_90 > 0 and (high_90 - low_90) > 0:
        position_90 = (price - low_90) / (high_90 - low_90)
        # 0 = proche du plus bas (potentiel), 1 = proche du plus haut
        # Score: proche du bas = 70, milieu = 50, proche du haut = 40
        pos_score = max(30, min(70, 70 - position_90 * 30))
        sub_scores.append(pos_score)

    # Win rate historique
    win_rate = data.get("win_rate_6m", data.get("win_data_json", 50))
    if win_rate and 0 <= win_rate <= 100:
        sub_scores.append(float(win_rate))

    if not sub_scores:
        return 50.0

    return float(np.mean(sub_scores))


def compute_nlp_sentiment_score(
    ticker: str,
    ticker_daily: Optional[pd.DataFrame],
    global_daily: Optional[pd.DataFrame],
    recent_days: int = 30,
) -> float:
    """
    Score NLP sentiment 0-100 basé sur le sentiment des messages récents.
    """
    base_score = 50.0

    if ticker_daily is not None and not ticker_daily.empty:
        t_df = ticker_daily[ticker_daily["ticker"] == ticker]
        if not t_df.empty:
            t_df = t_df.copy()
            t_df["date"] = pd.to_datetime(t_df["date"])
            t_df = t_df.sort_values("date")

            # Sentiment récent (last N jours)
            cutoff = t_df["date"].max() - pd.Timedelta(days=recent_days)
            recent = t_df[t_df["date"] >= cutoff]

            if not recent.empty:
                sent_mean = float(recent["sentiment_mean"].mean())
                # Convertit de (-1,1) en (0,100)
                base_score = (sent_mean + 1) / 2 * 100

                # Bonus pour velocity positive
                velocity = recent["sentiment_velocity"].mean() if "sentiment_velocity" in recent.columns else 0
                if velocity and velocity > 0.1:
                    base_score = min(100, base_score + 10)
                elif velocity and velocity < -0.1:
                    base_score = max(0, base_score - 10)

    elif global_daily is not None and not global_daily.empty:
        # Fallback: sentiment global du marché
        sent = global_daily["sentiment_mean"].tail(recent_days).mean()
        base_score = (float(sent) + 1) / 2 * 100

    return float(np.clip(base_score, 0, 100))


def compute_smart_money_score(
    ticker: str,
    fundamental_data: Dict[str, Any],
    member_scores: Optional[pd.DataFrame],
    df: Optional[pd.DataFrame],
    recent_days: int = 30,
) -> float:
    """
    Score Smart Money 0-100.
    Basé sur smart_sentiment et win_rate des membres influents.
    """
    # Score depuis financial_data.json
    sm_sentiment = fundamental_data.get(ticker, {}).get("smart_sentiment", 50)
    if sm_sentiment and 0 <= sm_sentiment <= 100:
        base_score = float(sm_sentiment)
    else:
        base_score = 50.0

    # Affine avec les données membres si disponibles
    if member_scores is not None and not member_scores.empty and df is not None:
        sms_col = next(
            (c for c in ["sms_score", "smart_money_score", "score"] if c in member_scores.columns),
            None,
        )
        if sms_col and "author" in df.columns and "signal" in df.columns:
            # Top 10% membres par SMS
            threshold = member_scores[sms_col].quantile(0.9)
            top_members = member_scores[member_scores[sms_col] >= threshold]

            if not top_members.empty:
                top_authors = set(top_members.index.tolist())
                if hasattr(top_members, "author"):
                    top_authors = set(top_members["author"].tolist())

                # Signaux récents des top membres sur ce ticker
                df_work = df.copy()
                df_work["date"] = pd.to_datetime(df_work["timestamp"]).dt.normalize()
                cutoff = df_work["date"].max() - pd.Timedelta(days=recent_days)

                recent_top = df_work[
                    (df_work["date"] >= cutoff) &
                    (df_work["author"].isin(top_authors))
                ]

                if not recent_top.empty and "tickers_mentioned" in recent_top.columns:
                    ticker_msgs = recent_top[
                        recent_top["tickers_mentioned"].apply(
                            lambda x: ticker in (x if isinstance(x, list) else [])
                        )
                    ]
                    if not ticker_msgs.empty:
                        signal_map = {
                            "ACHAT_FORT": 100, "ACHETER": 75, "RENFORCEMENT": 65,
                            "DOUTE": 50, "VENTE": 25, "PANIQUE": 5,
                        }
                        signals = ticker_msgs["signal"].map(
                            lambda x: signal_map.get(str(x).upper(), 50) if pd.notna(x) else 50
                        )
                        sm_from_msgs = float(signals.mean())
                        # Moyenne pondérée avec le score de base
                        base_score = 0.5 * base_score + 0.5 * sm_from_msgs

    return float(np.clip(base_score, 0, 100))


def compute_network_score(
    ticker: str,
    graph_metrics: Optional[pd.DataFrame],
    ticker_daily: Optional[pd.DataFrame],
) -> float:
    """
    Score réseau 0-100 basé sur l'activité réseau autour du ticker.
    """
    base_score = 50.0

    # Activité de mention du ticker (momentum réseau)
    if ticker_daily is not None and not ticker_daily.empty:
        t_df = ticker_daily[ticker_daily["ticker"] == ticker]
        if not t_df.empty:
            t_df = t_df.copy()
            t_df["date"] = pd.to_datetime(t_df["date"])
            recent = t_df.tail(14)
            older = t_df.tail(30).head(16)

            if not recent.empty and not older.empty:
                recent_mentions = recent["mention_count"].mean()
                older_mentions = older["mention_count"].mean()
                if older_mentions > 0:
                    trend = recent_mentions / older_mentions
                    # Trend > 1.5: forte croissance = 75pts; <0.5: déclin = 25pts
                    if trend > 2.0:
                        base_score = 80.0
                    elif trend > 1.5:
                        base_score = 70.0
                    elif trend > 1.0:
                        base_score = 55.0
                    elif trend > 0.5:
                        base_score = 45.0
                    else:
                        base_score = 30.0

    # Centralité du réseau (les nœuds les plus actifs parlent-ils du ticker?)
    if graph_metrics is not None and not graph_metrics.empty:
        # Proxy: score réseau lié à l'importance globale
        pagerank_col = next(
            (c for c in ["pagerank", "degree_centrality", "betweenness"] if c in graph_metrics.columns),
            None,
        )
        if pagerank_col:
            avg_centrality = float(graph_metrics[pagerank_col].mean())
            # Ajustement mineur
            base_score = base_score * 0.9 + avg_centrality * 10

    return float(np.clip(base_score, 0, 100))


def compute_behavioral_score(
    fear_greed_series: Optional[pd.Series],
    recent_days: int = 7,
) -> float:
    """
    Score comportemental 0-100 basé sur le Fear & Greed Index récent.
    Logique contrariante: F&G très bas (panique) = opportunité = score élevé.
    """
    if fear_greed_series is None or fear_greed_series.empty:
        return 50.0

    fg = fear_greed_series.dropna()
    if len(fg) == 0:
        return 50.0

    recent_fg = float(fg.tail(recent_days).mean())

    # Logique contrariante modérée (pas trop extrême)
    if recent_fg < 15:
        return 85.0   # Panique extrême = forte opportunité contrariante
    elif recent_fg < 25:
        return 75.0
    elif recent_fg < 40:
        return 60.0
    elif recent_fg < 60:
        return 50.0   # Zone neutre
    elif recent_fg < 75:
        return 40.0
    elif recent_fg < 85:
        return 30.0
    else:
        return 20.0   # Euphorie extrême = signal de vente contrarian


# ─────────────────────────────────────────────────────────────
# NORMALISATION
# ─────────────────────────────────────────────────────────────

def normalize_score(
    raw_score: float,
    min_val: float = 0.0,
    max_val: float = 100.0,
) -> float:
    """Normalise un score en 0-100."""
    if max_val <= min_val:
        return 50.0
    normalized = (raw_score - min_val) / (max_val - min_val) * 100
    return float(np.clip(normalized, 0, 100))


# ─────────────────────────────────────────────────────────────
# POIDS DYNAMIQUES
# ─────────────────────────────────────────────────────────────

def compute_dynamic_weights(
    fundamental_score: float,
    smart_money_score: float,
    nlp_score: float,
    technical_score: float,
    base_weights: Dict[str, float] = DEFAULT_WEIGHTS,
) -> Dict[str, float]:
    """
    Ajuste les poids dynamiquement quand le modèle ML diverge du Smart Money.
    - Si Smart Money très fort (>75) et NLP faible (<40): augmente poids SM
    - Si NLP et Smart Money concordent: poids équilibrés
    """
    weights = dict(base_weights)

    # Divergence Smart Money vs NLP
    sm_nlp_divergence = abs(smart_money_score - nlp_score)

    if sm_nlp_divergence > 30:
        # Fort désaccord: donne plus de poids au Smart Money (historiquement plus précis)
        if smart_money_score > nlp_score:
            weights["smart_money"] = min(0.35, weights["smart_money"] * 1.5)
            weights["nlp_sentiment"] = max(0.10, weights["nlp_sentiment"] * 0.7)
        else:
            # NLP plus haussier que SM: prudence, augmente légèrement NLP
            weights["nlp_sentiment"] = min(0.30, weights["nlp_sentiment"] * 1.3)

    # Si fondamentaux très bons, augmente leur poids
    if fundamental_score > 80:
        weights["fundamental"] = min(0.35, weights["fundamental"] * 1.2)

    # Normalise pour que la somme reste 1.0
    total = sum(weights.values())
    weights = {k: v / total for k, v in weights.items()}

    return weights


# ─────────────────────────────────────────────────────────────
# PROBABILITÉS ML
# ─────────────────────────────────────────────────────────────

def compute_ml_probabilities(
    ticker: str,
    best_model: Optional[Any],
    feature_names: Optional[List[str]],
    ticker_daily: Optional[pd.DataFrame],
    global_daily: Optional[pd.DataFrame],
    fear_greed_series: Optional[pd.Series],
    fundamental_data: Dict[str, Any],
    bootstrap_ci: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Calcule les probabilités de surperformance pour différents horizons.
    Utilise le meilleur modèle ML ou des estimations heuristiques si non disponible.
    """
    if best_model is None or feature_names is None:
        # Estimation heuristique basée sur le score composite
        return {"method": "heuristic", "horizons": {}}

    # Construit le vecteur de features pour ce ticker
    try:
        # Extrait les features récentes
        feature_vector = np.zeros(len(feature_names))

        # Remplit les features disponibles
        feature_mapping = {
            "sentiment_mean": 0.0,
            "buy_ratio": 0.5,
            "sell_ratio": 0.3,
            "volume_zscore": 0.0,
            "fear_greed": 50.0,
        }

        if global_daily is not None and not global_daily.empty:
            last_row = global_daily.tail(1)
            for col in ["sentiment_mean", "buy_ratio", "sell_ratio", "volume_zscore"]:
                if col in last_row.columns:
                    feature_mapping[col] = float(last_row[col].iloc[0])

        if fear_greed_series is not None and not fear_greed_series.empty:
            feature_mapping["fear_greed"] = float(fear_greed_series.dropna().iloc[-1])

        # Ticker-specific
        if ticker_daily is not None and not ticker_daily.empty:
            t_df = ticker_daily[ticker_daily["ticker"] == ticker].tail(5)
            if not t_df.empty:
                feature_mapping["ticker_sentiment_mean"] = float(t_df["sentiment_mean"].mean())
                feature_mapping["ticker_mention_count"] = float(t_df["mention_count"].mean())

        for i, fname in enumerate(feature_names):
            if fname in feature_mapping:
                feature_vector[i] = feature_mapping[fname]

        feature_vector = feature_vector.reshape(1, -1)

        # Prédiction
        if hasattr(best_model, "predict_proba"):
            prob_base = float(best_model.predict_proba(feature_vector)[0, 1])
        else:
            prob_base = float(best_model.predict(feature_vector)[0])

        # Ajustement par horizon (plus l'horizon est long, plus l'incertitude est grande)
        horizon_probs = {}
        uncertainty_factor = {30: 0.0, 90: 0.05, 180: 0.10, 365: 0.15}

        for horizon in PREDICTION_HORIZONS:
            p = prob_base
            unc = uncertainty_factor.get(horizon, 0.15)
            # L'incertitude tire vers 0.5
            p_adjusted = p + unc * (0.5 - p)

            # CI à partir du bootstrap si disponible
            if bootstrap_ci and "mean" in bootstrap_ci:
                auc_mean = bootstrap_ci.get("mean", 0.5)
                auc_ci_lower = bootstrap_ci.get("ci_lower", 0.4)
                auc_ci_upper = bootstrap_ci.get("ci_upper", 0.6)

                # Ajustement selon la qualité du modèle
                model_quality = (auc_mean - 0.5) / 0.5  # 0=hasard, 1=parfait
                p_adjusted = 0.5 + (p_adjusted - 0.5) * max(0, model_quality)

                # CI du modèle propagé sur la prédiction
                ci_width = (auc_ci_upper - auc_ci_lower) / 2 * 0.5
                horizon_probs[f"{horizon}d"] = {
                    "probability": float(np.clip(p_adjusted, 0.05, 0.95)),
                    "ci_lower": float(np.clip(p_adjusted - ci_width, 0.0, 1.0)),
                    "ci_upper": float(np.clip(p_adjusted + ci_width, 0.0, 1.0)),
                }
            else:
                base_ci = 0.1 + unc
                horizon_probs[f"{horizon}d"] = {
                    "probability": float(np.clip(p_adjusted, 0.05, 0.95)),
                    "ci_lower": float(np.clip(p_adjusted - base_ci, 0.0, 1.0)),
                    "ci_upper": float(np.clip(p_adjusted + base_ci, 0.0, 1.0)),
                }

        return {
            "method": "ml_model",
            "base_probability": float(prob_base),
            "horizons": horizon_probs,
        }

    except Exception as e:
        logger.debug(f"ML prob error for {ticker}: {e}")
        return {"method": "heuristic", "horizons": {}}


# ─────────────────────────────────────────────────────────────
# GÉNÉRATION DU SIGNAL FINAL
# ─────────────────────────────────────────────────────────────

def score_to_signal(composite_score: float) -> str:
    """Convertit un score composite 0-100 en signal de trading."""
    if composite_score >= SIGNAL_THRESHOLDS["FORT_ACHAT"]:
        return "FORT_ACHAT"
    elif composite_score >= SIGNAL_THRESHOLDS["ACHAT"]:
        return "ACHAT"
    elif composite_score >= SIGNAL_THRESHOLDS["NEUTRE_LOWER"]:
        return "NEUTRE"
    elif composite_score >= SIGNAL_THRESHOLDS["VENTE"]:
        return "VENTE"
    else:
        return "FORT_VENTE"


def score_to_signal_fr(signal: str) -> str:
    """Retourne la description française du signal."""
    labels = {
        "FORT_ACHAT": "Fort Achat ★★★★★",
        "ACHAT": "Achat ★★★★",
        "NEUTRE": "Neutre ★★★",
        "VENTE": "Vente ★★",
        "FORT_VENTE": "Fort Vente ★",
    }
    return labels.get(signal, "Neutre ★★★")


# ─────────────────────────────────────────────────────────────
# POINT D'ENTRÉE PRINCIPAL
# ─────────────────────────────────────────────────────────────

def run_phase13(
    df: pd.DataFrame,
    stock_scores: Optional[pd.DataFrame] = None,
    member_scores: Optional[pd.DataFrame] = None,
    fear_greed_series: Optional[pd.Series] = None,
    graph_metrics: Optional[pd.DataFrame] = None,
    phase8_results: Optional[Dict[str, Any]] = None,
    phase9_results: Optional[Dict[str, Any]] = None,
    phase12_results: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Exécute la Phase 13: Prédictions composites pour chaque valeur BVC.

    Returns dict with keys:
        predictions, final_rankings, ticker_details
    """
    logger.info("=== Phase 13: Moteur de Prédiction Composite ===")

    from whatsapp_analysis.config import BVC_TICKERS

    # Données de base
    fundamental_data = load_fundamental_data()

    # Données des phases précédentes
    daily_sentiment = pd.DataFrame()
    ticker_daily_sentiment = pd.DataFrame()
    if phase8_results is not None:
        daily_sentiment = phase8_results.get("daily_sentiment", pd.DataFrame())
        ticker_daily_sentiment = phase8_results.get("ticker_daily_sentiment", pd.DataFrame())

    best_model = None
    feature_names = None
    if phase9_results is not None:
        best_model = phase9_results.get("best_model")
        feature_names = phase9_results.get("feature_names")

    bootstrap_ci = None
    if phase12_results is not None:
        sr = phase12_results.get("stats_report", {})
        auc_bootstrap = sr.get("bootstrap_auc", {})
        bootstrap_ci = auc_bootstrap.get("best_model")

    # Détermine la liste des tickers à analyser
    tickers_to_analyze = set(fundamental_data.keys())
    if not ticker_daily_sentiment.empty and "ticker" in ticker_daily_sentiment.columns:
        tickers_to_analyze |= set(ticker_daily_sentiment["ticker"].unique())
    tickers_to_analyze &= set(BVC_TICKERS.keys())
    if not tickers_to_analyze:
        tickers_to_analyze = set(fundamental_data.keys())

    logger.info(f"Analyse de {len(tickers_to_analyze)} tickers...")

    # Score comportemental (global, identique pour tous les tickers)
    behavioral_score = compute_behavioral_score(fear_greed_series)
    logger.info(f"  Score comportemental global: {behavioral_score:.1f}")

    records = []

    for ticker in sorted(tickers_to_analyze):
        fd = fundamental_data.get(ticker, {})

        # ── Composantes ──
        fund_score = compute_fundamental_score(ticker, fd)
        tech_score = compute_technical_score(ticker, fd)
        nlp_score = compute_nlp_sentiment_score(
            ticker, ticker_daily_sentiment, daily_sentiment
        )
        sm_score = compute_smart_money_score(
            ticker, fundamental_data, member_scores, df
        )
        net_score = compute_network_score(ticker, graph_metrics, ticker_daily_sentiment)

        # ── Poids dynamiques ──
        weights = compute_dynamic_weights(
            fundamental_score=fund_score,
            smart_money_score=sm_score,
            nlp_score=nlp_score,
            technical_score=tech_score,
        )

        # ── Score composite ──
        composite = (
            weights["fundamental"] * fund_score
            + weights["technical"] * tech_score
            + weights["nlp_sentiment"] * nlp_score
            + weights["smart_money"] * sm_score
            + weights["network_momentum"] * net_score
            + weights["behavioral_regime"] * behavioral_score
        )
        composite = float(np.clip(composite, 0, 100))

        # ── Signal ──
        signal = score_to_signal(composite)

        # ── Probabilités ML ──
        ml_probs = compute_ml_probabilities(
            ticker=ticker,
            best_model=best_model,
            feature_names=feature_names,
            ticker_daily=ticker_daily_sentiment,
            global_daily=daily_sentiment,
            fear_greed_series=fear_greed_series,
            fundamental_data=fundamental_data,
            bootstrap_ci=bootstrap_ci,
        )

        # Probabilités par horizon (valeur résumée)
        p30 = ml_probs.get("horizons", {}).get("30d", {}).get("probability", composite / 100 * 0.7)
        p90 = ml_probs.get("horizons", {}).get("90d", {}).get("probability", p30 * 0.9)
        p180 = ml_probs.get("horizons", {}).get("180d", {}).get("probability", p90 * 0.9)
        p365 = ml_probs.get("horizons", {}).get("365d", {}).get("probability", p180 * 0.9)

        # Données fondamentales pour la table
        price = fd.get("price", 0)
        pe = fd.get("pe_ratio", 0)
        div_yield = fd.get("div_yield", 0)
        alpha = fd.get("alpha_12m", fd.get("alpha_data_json", 0))
        win_rate = fd.get("win_rate_6m", fd.get("win_data_json", 50))
        upside = fd.get("upside_pct", 0)

        record = {
            "ticker": ticker,
            "name": BVC_TICKERS.get(ticker, ticker),
            "price": float(price) if price else 0.0,
            "pe_ratio": float(pe) if pe else 0.0,
            "div_yield": float(div_yield) if div_yield else 0.0,
            "alpha_12m": float(alpha) if alpha else 0.0,
            "win_rate": float(win_rate) if win_rate else 50.0,
            "upside_pct": float(upside) if upside else 0.0,
            # Scores composantes
            "fundamental_score": round(fund_score, 1),
            "technical_score": round(tech_score, 1),
            "nlp_sentiment_score": round(nlp_score, 1),
            "smart_money_score": round(sm_score, 1),
            "network_score": round(net_score, 1),
            "behavioral_score": round(behavioral_score, 1),
            # Poids appliqués
            "weight_fundamental": round(weights["fundamental"], 3),
            "weight_technical": round(weights["technical"], 3),
            "weight_nlp": round(weights["nlp_sentiment"], 3),
            "weight_smart_money": round(weights["smart_money"], 3),
            # Score composite et signal
            "composite_score": round(composite, 1),
            "signal": signal,
            "signal_label": score_to_signal_fr(signal),
            # Probabilités ML
            "p_outperform_1m": round(float(p30), 3),
            "p_outperform_3m": round(float(p90), 3),
            "p_outperform_6m": round(float(p180), 3),
            "p_outperform_12m": round(float(p365), 3),
            "p_1m_ci_lower": ml_probs.get("horizons", {}).get("30d", {}).get("ci_lower", max(0, p30 - 0.1)),
            "p_1m_ci_upper": ml_probs.get("horizons", {}).get("30d", {}).get("ci_upper", min(1, p30 + 0.1)),
            "ml_method": ml_probs.get("method", "heuristic"),
        }
        records.append(record)

    if not records:
        logger.warning("Aucun ticker analysé")
        return {"predictions": pd.DataFrame(), "final_rankings": pd.DataFrame()}

    predictions = pd.DataFrame(records)
    predictions = predictions.sort_values("composite_score", ascending=False).reset_index(drop=True)
    predictions["rank"] = predictions.index + 1

    # ── Classement final ──
    final_rankings = predictions[[
        "rank", "ticker", "name", "composite_score", "signal", "signal_label",
        "fundamental_score", "technical_score", "nlp_sentiment_score",
        "smart_money_score", "network_score",
        "p_outperform_1m", "p_outperform_3m", "p_outperform_6m", "p_outperform_12m",
        "price", "pe_ratio", "div_yield", "upside_pct", "alpha_12m",
    ]].copy()

    # Statistiques résumées
    signal_counts = predictions["signal"].value_counts().to_dict()
    top5 = predictions.head(5)[["ticker", "name", "composite_score", "signal"]].to_dict("records")
    bottom5 = predictions.tail(5)[["ticker", "name", "composite_score", "signal"]].to_dict("records")

    fort_achat = predictions[predictions["signal"] == "FORT_ACHAT"]
    achat = predictions[predictions["signal"] == "ACHAT"]

    summary = {
        "n_tickers_analyzed": len(predictions),
        "signal_distribution": signal_counts,
        "top_5_picks": top5,
        "bottom_5_avoid": bottom5,
        "avg_composite_score": float(predictions["composite_score"].mean()),
        "n_fort_achat": len(fort_achat),
        "n_achat": len(achat),
        "n_neutre": len(predictions[predictions["signal"] == "NEUTRE"]),
        "n_vente": len(predictions[predictions["signal"] == "VENTE"]),
        "n_fort_vente": len(predictions[predictions["signal"] == "FORT_VENTE"]),
        "avg_p_outperform_1m": float(predictions["p_outperform_1m"].mean()),
        "behavioral_regime_score": behavioral_score,
        "weights_used": DEFAULT_WEIGHTS,
    }

    logger.info(f"\nPhase 13 terminée:")
    logger.info(f"  {len(predictions)} tickers analysés")
    logger.info(f"  Signaux: {signal_counts}")
    logger.info(f"  Top pick: {top5[0]['ticker']} (score={top5[0]['composite_score']:.1f})")

    return {
        "predictions": predictions,
        "final_rankings": final_rankings,
        "top5": top5,
        "signal_counts": signal_counts,
        "summary": summary,
    }


# ─────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    print("Test Phase 13: prédictions composites BVC...")

    rng = np.random.RandomState(42)
    dates = pd.date_range("2022-01-01", "2024-12-31", freq="h")[:3000]

    test_df = pd.DataFrame({
        "timestamp": dates,
        "author": [f"user_{i % 50}" for i in range(3000)],
        "message_text": ["test"] * 3000,
        "sentiment": rng.choice(["positif", "negatif", "neutre"], 3000),
        "signal": rng.choice(["ACHETER", "ACHAT_FORT", "VENTE", "DOUTE", None], 3000),
        "tickers_mentioned": [
            list(rng.choice(["IAM", "ATW", "BCP", "AKD", "HPS"], size=rng.randint(0, 3), replace=False))
            for _ in range(3000)
        ],
    })

    results = run_phase13(test_df)

    if not results["predictions"].empty:
        print("\n=== Top 10 Valeurs BVC ===")
        top10 = results["final_rankings"].head(10)
        print(top10[["ticker", "name", "composite_score", "signal_label",
                      "p_outperform_1m", "p_outperform_3m"]].to_string(index=False))

        print(f"\nDistribution des signaux: {results['signal_counts']}")
        print(f"Score composite moyen: {results['summary']['avg_composite_score']:.1f}")
    else:
        print("Aucun résultat (données insuffisantes)")
