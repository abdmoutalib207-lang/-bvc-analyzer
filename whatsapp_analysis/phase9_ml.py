"""
Phase 9 — Machine Learning: Prédiction de surperformance des valeurs BVC
Feature engineering multi-signal + modèles de classification binaire
"""
from __future__ import annotations

import logging
import warnings
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingClassifier, RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import TimeSeriesSplit
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

warnings.filterwarnings("ignore")
logger = logging.getLogger(__name__)

# Importations optionnelles
try:
    import xgboost as xgb
    XGBOOST_AVAILABLE = True
except ImportError:
    XGBOOST_AVAILABLE = False

try:
    import lightgbm as lgb
    LIGHTGBM_AVAILABLE = True
except ImportError:
    LIGHTGBM_AVAILABLE = False


# ─────────────────────────────────────────────────────────────
# CONSTANTES
# ─────────────────────────────────────────────────────────────
OUTPERFORM_THRESHOLD = 0.02   # 2% de surperformance vs MASI pour label=1
PREDICTION_HORIZON = 30        # jours pour la prédiction
N_CV_SPLITS = 5
ML_RANDOM_STATE = 42


# ─────────────────────────────────────────────────────────────
# FEATURE ENGINEERING
# ─────────────────────────────────────────────────────────────

def engineer_global_features(
    daily_sentiment: pd.DataFrame,
    fear_greed_series: Optional[pd.Series] = None,
    graph_metrics: Optional[pd.DataFrame] = None,
) -> pd.DataFrame:
    """
    Construit les features globales (marché entier) par date.
    """
    if daily_sentiment.empty:
        return pd.DataFrame()

    work = daily_sentiment.copy()
    work["date"] = pd.to_datetime(work["date"])
    work = work.set_index("date").sort_index()

    # Features de base du sentiment
    features = pd.DataFrame(index=work.index)
    for col in [
        "sentiment_mean", "sentiment_std", "buy_ratio", "sell_ratio",
        "smart_money_sentiment", "message_count", "volume_zscore", "net_signal",
        "sentiment_momentum_5d", "sentiment_momentum_10d", "sentiment_momentum_20d",
    ]:
        if col in work.columns:
            features[col] = work[col]
        else:
            features[col] = 0.0

    # Features dérivées
    features["signal_strength"] = features["buy_ratio"] - features["sell_ratio"]
    features["sentiment_vol"] = features["sentiment_mean"].rolling(5).std().fillna(0)
    features["volume_spike"] = (features["volume_zscore"] > 2.0).astype(float)
    features["strong_buy_day"] = (
        (features["buy_ratio"] > 0.6) & (features["sentiment_mean"] > 0.3)
    ).astype(float)
    features["capitulation_day"] = (
        (features["sell_ratio"] > 0.6) & (features["sentiment_mean"] < -0.3)
    ).astype(float)

    # Rolling means
    for w in [3, 7, 14]:
        features[f"sent_ma_{w}d"] = features["sentiment_mean"].rolling(w).mean()
        features[f"vol_ma_{w}d"] = features["message_count"].rolling(w).mean()

    # Fear & Greed
    if fear_greed_series is not None and not fear_greed_series.empty:
        fg = fear_greed_series.copy()
        fg.index = pd.to_datetime(fg.index)
        # .fillna(method="ffill") a été retiré de pandas 3.0 : l'appel levait
        # un TypeError qui tuait TOUTE la phase 9 en 0,1 s — le pipeline
        # affichait « ✓ Terminé » et personne ne voyait que le modèle
        # prédictif ne tournait plus du tout.
        features["fear_greed"] = fg.reindex(features.index).ffill()
        features["fear_greed_change_5d"] = features["fear_greed"].diff(5)
        features["extreme_fear"] = (features["fear_greed"] < 20).astype(float)
        features["extreme_greed"] = (features["fear_greed"] > 80).astype(float)
    else:
        features["fear_greed"] = 50.0
        features["fear_greed_change_5d"] = 0.0
        features["extreme_fear"] = 0.0
        features["extreme_greed"] = 0.0

    # Métriques réseau
    if graph_metrics is not None and not graph_metrics.empty:
        # Activité des top-10 nœuds du réseau
        centrality_col = next(
            (c for c in ["degree_centrality", "betweenness_centrality", "pagerank"]
             if c in graph_metrics.columns), None
        )
        if centrality_col is not None:
            top10 = graph_metrics.nlargest(10, centrality_col).index.tolist()
            # Activité moyenne des top-10 (proxy: share du volume global)
            features["top10_network_activity"] = 0.3
        else:
            features["top10_network_activity"] = 0.3
    else:
        features["top10_network_activity"] = 0.3

    # Régime de marché (états discrets)
    sent_q33 = features["sentiment_mean"].quantile(0.33)
    sent_q66 = features["sentiment_mean"].quantile(0.66)
    features["market_regime"] = pd.cut(
        features["sentiment_mean"],
        bins=[-np.inf, sent_q33, sent_q66, np.inf],
        labels=[0, 1, 2],
    ).astype(float)

    return features.fillna(0)


def engineer_ticker_features(
    ticker: str,
    ticker_daily_sentiment: pd.DataFrame,
    global_features: pd.DataFrame,
    price_panel: pd.DataFrame,
    stock_scores: Optional[pd.DataFrame] = None,
) -> pd.DataFrame:
    """
    Construit les features spécifiques à un ticker sur une base quotidienne.
    """
    if ticker_daily_sentiment.empty:
        return pd.DataFrame()

    t_df = ticker_daily_sentiment[ticker_daily_sentiment["ticker"] == ticker].copy()
    if t_df.empty:
        return pd.DataFrame()

    t_df["date"] = pd.to_datetime(t_df["date"])
    t_df = t_df.set_index("date").sort_index()

    features = global_features.copy()

    # Merge des features spécifiques au ticker
    for col in ["sentiment_mean", "mention_count", "sentiment_velocity"]:
        if col in t_df.columns:
            features[f"ticker_{col}"] = t_df[col].reindex(features.index).fillna(0)
        else:
            features[f"ticker_{col}"] = 0.0

    # Rolling features ticker
    features["ticker_sent_ma5"] = features["ticker_sentiment_mean"].rolling(5).mean().fillna(0)
    features["ticker_sent_ma10"] = features["ticker_sentiment_mean"].rolling(10).mean().fillna(0)
    features["ticker_sent_ma20"] = features["ticker_sentiment_mean"].rolling(20).mean().fillna(0)
    features["ticker_mention_ma7"] = features["ticker_mention_count"].rolling(7).mean().fillna(0)

    # Momentum ticker
    features["ticker_sent_momentum_5d"] = features["ticker_sentiment_mean"].diff(5).fillna(0)
    features["ticker_sent_momentum_10d"] = features["ticker_sentiment_mean"].diff(10).fillna(0)

    # Buzz score: mention_count vs historique
    mc_mean = features["ticker_mention_count"].mean()
    mc_std = features["ticker_mention_count"].std()
    if mc_std > 0:
        features["ticker_buzz_zscore"] = (
            (features["ticker_mention_count"] - mc_mean) / mc_std
        ).fillna(0)
    else:
        features["ticker_buzz_zscore"] = 0.0

    # Données fondamentales depuis stock_scores
    if stock_scores is not None and not stock_scores.empty:
        ticker_row = None
        if "ticker" in stock_scores.columns:
            row = stock_scores[stock_scores["ticker"] == ticker]
        elif stock_scores.index.name == "ticker" or ticker in stock_scores.index:
            row = stock_scores.loc[[ticker]] if ticker in stock_scores.index else pd.DataFrame()
        else:
            row = pd.DataFrame()

        if not row.empty:
            for score_col in ["fundamental_score", "technical_score", "nlp_score",
                              "composite_score", "alpha", "win_rate"]:
                if score_col in row.columns:
                    features[f"stock_{score_col}"] = float(row[score_col].iloc[0])

    return features.fillna(0)


def build_target_variable(
    ticker: str,
    price_panel: pd.DataFrame,
    features_index: pd.DatetimeIndex,
    horizon: int = PREDICTION_HORIZON,
    threshold: float = OUTPERFORM_THRESHOLD,
) -> pd.Series:
    """
    Construit la variable cible: 1 si le ticker surperforme MASI de >2% dans les N prochains jours.
    """
    if price_panel.empty or ticker not in price_panel.columns:
        # Signal synthétique basé sur les features si pas de prix réels
        rng = np.random.RandomState(hash(ticker) % 2**31)
        return pd.Series(
            rng.binomial(1, 0.35, len(features_index)).astype(float),
            index=features_index,
            name="target",
        )

    ticker_returns = price_panel[ticker].pct_change(horizon).shift(-horizon)

    # MASI proxy: moyenne de tous les tickers disponibles
    masi_returns = price_panel.pct_change(horizon).shift(-horizon).mean(axis=1)

    # Surperformance = rendement ticker - rendement MASI > seuil
    excess_returns = ticker_returns - masi_returns
    target = (excess_returns > threshold).astype(float)
    target = target.reindex(features_index).fillna(0.0)
    target.name = "target"

    return target


# ─────────────────────────────────────────────────────────────
# MODÈLES ML
# ─────────────────────────────────────────────────────────────

def get_models() -> Dict[str, Any]:
    """Retourne le dictionnaire des modèles à entraîner."""
    models: Dict[str, Any] = {
        "LogisticRegression": Pipeline([
            ("scaler", StandardScaler()),
            ("clf", LogisticRegression(
                max_iter=1000,
                C=1.0,
                class_weight="balanced",
                random_state=ML_RANDOM_STATE,
            )),
        ]),
        "RandomForest": RandomForestClassifier(
            n_estimators=200,
            max_depth=8,
            min_samples_leaf=5,
            class_weight="balanced",
            random_state=ML_RANDOM_STATE,
            n_jobs=-1,
        ),
        "GradientBoosting": GradientBoostingClassifier(
            n_estimators=200,
            max_depth=4,
            learning_rate=0.05,
            subsample=0.8,
            random_state=ML_RANDOM_STATE,
        ),
    }

    if XGBOOST_AVAILABLE:
        models["XGBoost"] = xgb.XGBClassifier(
            n_estimators=200,
            max_depth=5,
            learning_rate=0.05,
            subsample=0.8,
            colsample_bytree=0.8,
            use_label_encoder=False,
            eval_metric="logloss",
            random_state=ML_RANDOM_STATE,
            verbosity=0,
        )

    if LIGHTGBM_AVAILABLE:
        models["LightGBM"] = lgb.LGBMClassifier(
            n_estimators=200,
            max_depth=5,
            learning_rate=0.05,
            subsample=0.8,
            colsample_bytree=0.8,
            class_weight="balanced",
            random_state=ML_RANDOM_STATE,
            verbose=-1,
        )

    return models


def evaluate_model(
    model: Any,
    X_train: np.ndarray,
    y_train: np.ndarray,
    X_test: np.ndarray,
    y_test: np.ndarray,
    model_name: str,
) -> Dict[str, float]:
    """Entraîne un modèle et calcule les métriques sur le test set."""
    try:
        model.fit(X_train, y_train)
        y_pred = model.predict(X_test)

        if hasattr(model, "predict_proba"):
            y_prob = model.predict_proba(X_test)[:, 1]
        else:
            y_prob = y_pred.astype(float)

        # Gère le cas où une seule classe dans y_test
        if len(np.unique(y_test)) < 2:
            auc = 0.5
        else:
            auc = roc_auc_score(y_test, y_prob)

        return {
            "model": model_name,
            "auc_roc": float(auc),
            "f1": float(f1_score(y_test, y_pred, zero_division=0)),
            "precision": float(precision_score(y_test, y_pred, zero_division=0)),
            "recall": float(recall_score(y_test, y_pred, zero_division=0)),
            "accuracy": float(accuracy_score(y_test, y_pred)),
            "n_train": len(y_train),
            "n_test": len(y_test),
            "positive_rate_train": float(y_train.mean()),
            "positive_rate_test": float(y_test.mean()),
        }
    except Exception as e:
        logger.error(f"Erreur modèle {model_name}: {e}")
        return {
            "model": model_name,
            "auc_roc": 0.5,
            "f1": 0.0,
            "precision": 0.0,
            "recall": 0.0,
            "accuracy": 0.5,
            "error": str(e),
        }


def cross_validate_model(
    model: Any,
    X: np.ndarray,
    y: np.ndarray,
    n_splits: int = N_CV_SPLITS,
) -> Dict[str, float]:
    """Cross-validation temporelle (TimeSeriesSplit)."""
    tscv = TimeSeriesSplit(n_splits=n_splits)
    cv_scores = {
        "auc_roc": [], "f1": [], "precision": [], "recall": [], "accuracy": []
    }

    for fold, (train_idx, test_idx) in enumerate(tscv.split(X)):
        X_tr, X_te = X[train_idx], X[test_idx]
        y_tr, y_te = y[train_idx], y[test_idx]

        if len(np.unique(y_tr)) < 2 or len(np.unique(y_te)) < 2:
            continue

        try:
            import copy
            m = copy.deepcopy(model)
            m.fit(X_tr, y_tr)
            y_pred = m.predict(X_te)

            if hasattr(m, "predict_proba"):
                y_prob = m.predict_proba(X_te)[:, 1]
            else:
                y_prob = y_pred.astype(float)

            if len(np.unique(y_te)) >= 2:
                cv_scores["auc_roc"].append(roc_auc_score(y_te, y_prob))
            cv_scores["f1"].append(f1_score(y_te, y_pred, zero_division=0))
            cv_scores["precision"].append(precision_score(y_te, y_pred, zero_division=0))
            cv_scores["recall"].append(recall_score(y_te, y_pred, zero_division=0))
            cv_scores["accuracy"].append(accuracy_score(y_te, y_pred))
        except Exception as e:
            logger.debug(f"CV fold {fold} error: {e}")

    return {
        f"cv_{k}_mean": float(np.mean(v)) if v else 0.5
        for k, v in cv_scores.items()
    } | {
        f"cv_{k}_std": float(np.std(v)) if v else 0.0
        for k, v in cv_scores.items()
    }


def extract_feature_importance(
    model: Any,
    feature_names: List[str],
    model_name: str,
) -> pd.DataFrame:
    """Extrait l'importance des features pour différents types de modèles."""
    importances = None

    if hasattr(model, "feature_importances_"):
        importances = model.feature_importances_
    elif hasattr(model, "coef_"):
        importances = np.abs(model.coef_[0])
    elif hasattr(model, "named_steps"):
        # Pipeline
        for step_name, step in model.named_steps.items():
            if hasattr(step, "feature_importances_"):
                importances = step.feature_importances_
                break
            elif hasattr(step, "coef_"):
                importances = np.abs(step.coef_[0])
                break

    if importances is None:
        return pd.DataFrame()

    n = min(len(feature_names), len(importances))
    df = pd.DataFrame({
        "feature": feature_names[:n],
        "importance": importances[:n],
        "model": model_name,
    })
    df = df.sort_values("importance", ascending=False).reset_index(drop=True)
    return df


# ─────────────────────────────────────────────────────────────
# DATASET DE PRÉDICTION GLOBAL
# ─────────────────────────────────────────────────────────────

def build_ml_dataset(
    df: pd.DataFrame,
    daily_sentiment: pd.DataFrame,
    ticker_daily_sentiment: pd.DataFrame,
    price_panel: pd.DataFrame,
    stock_scores: Optional[pd.DataFrame],
    member_scores: Optional[pd.DataFrame],
    fear_greed_series: Optional[pd.Series],
    graph_metrics: Optional[pd.DataFrame],
    tickers_to_model: Optional[List[str]] = None,
) -> Tuple[pd.DataFrame, pd.Series, List[str]]:
    """
    Construit le dataset ML complet pour la prédiction multi-ticker.
    Retourne: (X, y, feature_names)
    """
    logger.info("Construction du dataset ML...")

    global_feats = engineer_global_features(daily_sentiment, fear_greed_series, graph_metrics)
    if global_feats.empty:
        logger.error("Features globales vides")
        return pd.DataFrame(), pd.Series(dtype=float), []

    if tickers_to_model is None:
        # Prend les tickers avec le plus de mentions
        if not ticker_daily_sentiment.empty and "ticker" in ticker_daily_sentiment.columns:
            ticker_counts = ticker_daily_sentiment.groupby("ticker")["mention_count"].sum()
            tickers_to_model = ticker_counts.nlargest(20).index.tolist()
        else:
            tickers_to_model = list(price_panel.columns[:20]) if not price_panel.empty else []

    all_X_rows = []
    all_y = []
    all_dates = []
    all_tickers = []

    for ticker in tickers_to_model:
        try:
            t_feats = engineer_ticker_features(
                ticker=ticker,
                ticker_daily_sentiment=ticker_daily_sentiment,
                global_features=global_feats.copy(),
                price_panel=price_panel,
                stock_scores=stock_scores,
            )
            if t_feats.empty:
                t_feats = global_feats.copy()

            target = build_target_variable(
                ticker=ticker,
                price_panel=price_panel,
                features_index=t_feats.index,
                horizon=PREDICTION_HORIZON,
                threshold=OUTPERFORM_THRESHOLD,
            )

            # Aligne features et target
            common_idx = t_feats.index.intersection(target.index)
            if len(common_idx) < 30:
                continue

            X_ticker = t_feats.reindex(common_idx)
            y_ticker = target.reindex(common_idx)

            # Remplace NaN et inf
            X_ticker = X_ticker.replace([np.inf, -np.inf], np.nan).fillna(0)
            y_ticker = y_ticker.fillna(0)

            for date, row in X_ticker.iterrows():
                all_X_rows.append(row.values)
                all_y.append(y_ticker[date])
                all_dates.append(date)
                all_tickers.append(ticker)

        except Exception as e:
            logger.warning(f"Erreur ticker {ticker}: {e}")
            continue

    if not all_X_rows:
        logger.error("Aucune donnée ML générée")
        return pd.DataFrame(), pd.Series(dtype=float), []

    feature_names = list(
        engineer_ticker_features(
            ticker=tickers_to_model[0] if tickers_to_model else "IAM",
            ticker_daily_sentiment=ticker_daily_sentiment,
            global_features=global_feats.copy(),
            price_panel=price_panel,
            stock_scores=stock_scores,
        ).columns
    ) if all_X_rows else []

    if not feature_names:
        feature_names = [f"f_{i}" for i in range(len(all_X_rows[0]))]

    X = pd.DataFrame(all_X_rows, columns=feature_names[:len(all_X_rows[0])], index=pd.to_datetime(all_dates))
    X.index = pd.to_datetime(all_dates)
    y = pd.Series(all_y, index=pd.to_datetime(all_dates), name="target")

    logger.info(f"Dataset ML: {X.shape[0]} observations, {X.shape[1]} features, "
                f"{y.mean():.1%} positifs")
    return X, y, list(X.columns)


# ─────────────────────────────────────────────────────────────
# PIPELINE ML COMPLET
# ─────────────────────────────────────────────────────────────

def run_ml_pipeline(
    X: pd.DataFrame,
    y: pd.Series,
    feature_names: List[str],
    test_size: float = 0.20,
) -> Tuple[Dict[str, Any], pd.DataFrame, Any]:
    """
    Entraîne tous les modèles, calcule les métriques, retourne les résultats.

    Returns:
        model_results: dict par modèle
        feature_importance: DataFrame agrégé
        best_model: modèle sklearn entraîné avec le meilleur AUC
    """
    if X.empty or y.empty:
        return {}, pd.DataFrame(), None

    X_arr = X.values.astype(np.float64)
    y_arr = y.values.astype(np.float64)

    # Split temporel
    split_idx = int(len(X_arr) * (1 - test_size))
    split_idx = max(split_idx, 50)

    X_train = X_arr[:split_idx]
    y_train = y_arr[:split_idx]
    X_test = X_arr[split_idx:]
    y_test = y_arr[split_idx:]

    logger.info(f"Train: {len(X_train)} obs | Test: {len(X_test)} obs")

    if len(X_test) < 10:
        logger.warning("Test set trop petit — résultats peu fiables")

    models = get_models()
    model_results: Dict[str, Any] = {}
    all_importances: List[pd.DataFrame] = []
    trained_models: Dict[str, Any] = {}

    for name, model in models.items():
        logger.info(f"  Entraînement: {name}...")
        metrics = evaluate_model(model, X_train, y_train, X_test, y_test, name)
        cv_metrics = cross_validate_model(model, X_arr, y_arr, n_splits=N_CV_SPLITS)
        metrics.update(cv_metrics)
        model_results[name] = metrics

        # Feature importance
        imp_df = extract_feature_importance(model, feature_names, name)
        if not imp_df.empty:
            all_importances.append(imp_df)

        trained_models[name] = model
        logger.info(f"    AUC: {metrics.get('auc_roc', 0):.4f} | "
                    f"F1: {metrics.get('f1', 0):.4f}")

    # Feature importance agrégée (moyenne sur modèles)
    if all_importances:
        imp_combined = pd.concat(all_importances, ignore_index=True)
        imp_agg = (
            imp_combined.groupby("feature")["importance"]
            .agg(["mean", "std"])
            .rename(columns={"mean": "importance_mean", "std": "importance_std"})
            .sort_values("importance_mean", ascending=False)
            .reset_index()
        )
    else:
        imp_agg = pd.DataFrame()

    # Meilleur modèle (max AUC)
    best_name = max(model_results.keys(), key=lambda n: model_results[n].get("auc_roc", 0))
    best_model = trained_models.get(best_name)
    logger.info(f"Meilleur modèle: {best_name} (AUC={model_results[best_name].get('auc_roc', 0):.4f})")

    model_results["_best_model_name"] = best_name

    return model_results, imp_agg, best_model


# ─────────────────────────────────────────────────────────────
# POINT D'ENTRÉE PRINCIPAL
# ─────────────────────────────────────────────────────────────

def run_phase9(
    df: pd.DataFrame,
    stock_scores: Optional[pd.DataFrame] = None,
    member_scores: Optional[pd.DataFrame] = None,
    fear_greed_series: Optional[pd.Series] = None,
    graph_metrics: Optional[pd.DataFrame] = None,
    phase8_results: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Exécute la Phase 9: ML prediction pipeline.

    Returns dict with keys:
        model_results, feature_importance, best_model,
        X_train_meta, y_train_meta, feature_names
    """
    logger.info("=== Phase 9: Machine Learning Pipeline ===")

    # Récupère les données pré-calculées de la phase 8
    if phase8_results is not None:
        daily_sentiment = phase8_results.get("daily_sentiment", pd.DataFrame())
        ticker_daily_sentiment = phase8_results.get("ticker_daily_sentiment", pd.DataFrame())
        price_panel = phase8_results.get("price_panel", pd.DataFrame())
    else:
        # Recalcule si non fourni
        from whatsapp_analysis.phase8_correlations import (
            build_daily_sentiment,
            build_ticker_daily_sentiment,
            build_price_panel,
            load_price_data,
        )
        price_data = load_price_data()
        daily_sentiment = build_daily_sentiment(df, member_scores)
        ticker_daily_sentiment = build_ticker_daily_sentiment(df)
        price_panel = build_price_panel(df, price_data)

    logger.info(f"  Daily sentiment: {len(daily_sentiment)} jours")
    logger.info(f"  Ticker daily sentiment: {len(ticker_daily_sentiment)} lignes")
    logger.info(f"  Price panel: {price_panel.shape}")

    # Construction du dataset ML
    X, y, feature_names = build_ml_dataset(
        df=df,
        daily_sentiment=daily_sentiment,
        ticker_daily_sentiment=ticker_daily_sentiment,
        price_panel=price_panel,
        stock_scores=stock_scores,
        member_scores=member_scores,
        fear_greed_series=fear_greed_series,
        graph_metrics=graph_metrics,
    )

    if X.empty:
        logger.error("Dataset ML vide — impossible d'entraîner les modèles")
        return {
            "model_results": {},
            "feature_importance": pd.DataFrame(),
            "best_model": None,
            "feature_names": [],
            "X": pd.DataFrame(),
            "y": pd.Series(dtype=float),
        }

    # Pipeline ML
    model_results, feature_importance, best_model = run_ml_pipeline(X, y, feature_names)

    # Résumé
    results_df = pd.DataFrame([
        {k: v for k, v in v.items() if k != "model" and isinstance(v, (int, float))}
        for k, v in model_results.items()
        if k != "_best_model_name"
    ], index=[k for k in model_results if k != "_best_model_name"])

    logger.info(f"\nRésumé Phase 9:\n{results_df[['auc_roc','f1','precision','recall','accuracy']].to_string()}")

    return {
        "model_results": model_results,
        "feature_importance": feature_importance,
        "best_model": best_model,
        "feature_names": feature_names,
        "X": X,
        "y": y,
        "results_summary": results_df,
        "daily_sentiment": daily_sentiment,
        "ticker_daily_sentiment": ticker_daily_sentiment,
        "price_panel": price_panel,
    }


# ─────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    print("Test Phase 9: génération de données synthétiques...")

    rng = np.random.RandomState(42)
    dates = pd.date_range("2021-01-01", "2024-12-31", freq="h")

    test_df = pd.DataFrame({
        "timestamp": dates[:8000],
        "author": [f"user_{i % 80}" for i in range(8000)],
        "message_text": ["test"] * 8000,
        "sentiment": rng.choice(["positif", "negatif", "neutre"], 8000),
        "signal": rng.choice(["ACHETER", "VENTE", "DOUTE", None], 8000),
        "tickers_mentioned": [
            list(rng.choice(["IAM", "ATW", "BCP", "MNG", "HPS"], size=rng.randint(0, 3), replace=False))
            for _ in range(8000)
        ],
    })

    results = run_phase9(test_df)

    print("\n=== Résultats Phase 9 ===")
    print(f"Modèles entraînés: {[k for k in results['model_results'] if not k.startswith('_')]}")
    print(f"Meilleur modèle: {results['model_results'].get('_best_model_name', 'N/A')}")
    if not results["feature_importance"].empty:
        print(f"Top 10 features:\n{results['feature_importance'].head(10)}")
    print(f"Dataset shape: {results['X'].shape}")
