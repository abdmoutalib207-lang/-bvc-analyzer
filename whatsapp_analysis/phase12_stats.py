"""
Phase 12 — Tests Statistiques de Robustesse
Bootstrap, Monte Carlo, permutation tests, correction FDR, analyse du sur-apprentissage
"""
from __future__ import annotations

import logging
import warnings
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from scipy import stats
from scipy.stats import ks_2samp, kstest, mannwhitneyu

warnings.filterwarnings("ignore")
logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────
# CONSTANTES
# ─────────────────────────────────────────────────────────────

N_BOOTSTRAP = 1000
N_MONTE_CARLO = 1000
CONFIDENCE_LEVEL = 0.95
ALPHA = 1 - CONFIDENCE_LEVEL   # 0.05


# ─────────────────────────────────────────────────────────────
# BOOTSTRAP
# ─────────────────────────────────────────────────────────────

def bootstrap_confidence_interval(
    data: np.ndarray,
    statistic_fn: callable,
    n_iterations: int = N_BOOTSTRAP,
    ci_level: float = CONFIDENCE_LEVEL,
    seed: int = 42,
) -> Dict[str, float]:
    """
    Calcule l'intervalle de confiance par bootstrap pour une statistique donnée.
    """
    rng = np.random.RandomState(seed)
    if len(data) < 5:
        return {"ci_lower": np.nan, "ci_upper": np.nan, "mean": np.nan, "std": np.nan}

    bootstrapped = np.array([
        statistic_fn(rng.choice(data, size=len(data), replace=True))
        for _ in range(n_iterations)
    ])

    bootstrapped = bootstrapped[np.isfinite(bootstrapped)]
    if len(bootstrapped) == 0:
        return {"ci_lower": np.nan, "ci_upper": np.nan, "mean": np.nan, "std": np.nan}

    alpha_half = (1 - ci_level) / 2
    return {
        "ci_lower": float(np.percentile(bootstrapped, alpha_half * 100)),
        "ci_upper": float(np.percentile(bootstrapped, (1 - alpha_half) * 100)),
        "mean": float(np.mean(bootstrapped)),
        "std": float(np.std(bootstrapped)),
        "n_valid": len(bootstrapped),
    }


def bootstrap_auc(
    y_true: np.ndarray,
    y_pred_proba: np.ndarray,
    n_iterations: int = N_BOOTSTRAP,
    seed: int = 42,
) -> Dict[str, float]:
    """
    Bootstrap de l'AUC-ROC.
    """
    from sklearn.metrics import roc_auc_score

    rng = np.random.RandomState(seed)
    n = len(y_true)
    aucs = []

    for _ in range(n_iterations):
        idx = rng.choice(n, size=n, replace=True)
        y_t = y_true[idx]
        y_p = y_pred_proba[idx]

        if len(np.unique(y_t)) < 2:
            continue
        try:
            aucs.append(roc_auc_score(y_t, y_p))
        except Exception:
            pass

    aucs = np.array(aucs)
    if len(aucs) == 0:
        return {"ci_lower": 0.5, "ci_upper": 0.5, "mean": 0.5, "std": 0.0}

    return {
        "ci_lower": float(np.percentile(aucs, 2.5)),
        "ci_upper": float(np.percentile(aucs, 97.5)),
        "mean": float(np.mean(aucs)),
        "std": float(np.std(aucs)),
        "n_samples": len(aucs),
    }


def bootstrap_sharpe(
    returns: pd.Series,
    n_iterations: int = N_BOOTSTRAP,
    rf_annual: float = 0.03,
    seed: int = 42,
) -> Dict[str, float]:
    """
    Bootstrap du Sharpe Ratio.
    """
    from whatsapp_analysis.phase11_backtest import TRADING_DAYS_YEAR

    rng = np.random.RandomState(seed)
    ret_arr = returns.dropna().values
    if len(ret_arr) < 10:
        return {"ci_lower": np.nan, "ci_upper": np.nan, "mean": np.nan, "std": np.nan}

    rf_daily = (1 + rf_annual) ** (1 / TRADING_DAYS_YEAR) - 1

    def sharpe_fn(r: np.ndarray) -> float:
        excess = r - rf_daily
        vol = np.std(r)
        if vol < 1e-9:
            return 0.0
        return float(np.mean(excess) * TRADING_DAYS_YEAR / (vol * np.sqrt(TRADING_DAYS_YEAR)))

    sharpes = [
        sharpe_fn(rng.choice(ret_arr, size=len(ret_arr), replace=True))
        for _ in range(n_iterations)
    ]
    sharpes = [s for s in sharpes if np.isfinite(s)]

    if not sharpes:
        return {"ci_lower": np.nan, "ci_upper": np.nan, "mean": np.nan, "std": np.nan}

    return {
        "ci_lower": float(np.percentile(sharpes, 2.5)),
        "ci_upper": float(np.percentile(sharpes, 97.5)),
        "mean": float(np.mean(sharpes)),
        "std": float(np.std(sharpes)),
        "observed": sharpe_fn(ret_arr),
    }


def bootstrap_correlation(
    x: np.ndarray,
    y: np.ndarray,
    n_iterations: int = N_BOOTSTRAP,
    seed: int = 42,
) -> Dict[str, float]:
    """
    Bootstrap de la corrélation de Pearson.
    """
    from scipy.stats import pearsonr

    rng = np.random.RandomState(seed)
    n = min(len(x), len(y))
    if n < 10:
        return {"ci_lower": np.nan, "ci_upper": np.nan, "mean": np.nan}

    corrs = []
    for _ in range(n_iterations):
        idx = rng.choice(n, size=n, replace=True)
        try:
            r, _ = pearsonr(x[idx], y[idx])
            if np.isfinite(r):
                corrs.append(r)
        except Exception:
            pass

    if not corrs:
        return {"ci_lower": np.nan, "ci_upper": np.nan, "mean": np.nan}

    return {
        "ci_lower": float(np.percentile(corrs, 2.5)),
        "ci_upper": float(np.percentile(corrs, 97.5)),
        "mean": float(np.mean(corrs)),
        "std": float(np.std(corrs)),
        "observed": float(np.corrcoef(x[:n], y[:n])[0, 1]),
    }


# ─────────────────────────────────────────────────────────────
# MONTE CARLO
# ─────────────────────────────────────────────────────────────

def monte_carlo_null_auc(
    y_true: np.ndarray,
    observed_auc: float,
    n_iterations: int = N_MONTE_CARLO,
    seed: int = 42,
) -> Dict[str, Any]:
    """
    Monte Carlo: mélange les labels et mesure combien de fois
    un signal aléatoire dépasse notre AUC observée.
    p-value = fraction des runs aléatoires qui dépassent observed_auc.
    """
    from sklearn.metrics import roc_auc_score

    rng = np.random.RandomState(seed)
    n = len(y_true)
    null_aucs = []

    for _ in range(n_iterations):
        y_shuffled = rng.permutation(y_true)
        y_random_pred = rng.random(n)

        if len(np.unique(y_shuffled)) < 2:
            null_aucs.append(0.5)
            continue
        try:
            null_aucs.append(roc_auc_score(y_shuffled, y_random_pred))
        except Exception:
            null_aucs.append(0.5)

    null_aucs = np.array(null_aucs)
    p_value = float(np.mean(null_aucs >= observed_auc))

    return {
        "observed_auc": float(observed_auc),
        "null_mean": float(np.mean(null_aucs)),
        "null_std": float(np.std(null_aucs)),
        "null_p95": float(np.percentile(null_aucs, 95)),
        "p_value": p_value,
        "significant": p_value < ALPHA,
        "n_iterations": n_iterations,
        "interpretation": (
            f"AUC={observed_auc:.4f} significativement supérieure au hasard (p={p_value:.4f})"
            if p_value < ALPHA
            else f"AUC={observed_auc:.4f} non distinguable du hasard (p={p_value:.4f})"
        ),
    }


def monte_carlo_null_sharpe(
    equity_curve: pd.Series,
    observed_sharpe: float,
    n_iterations: int = N_MONTE_CARLO,
    seed: int = 42,
) -> Dict[str, Any]:
    """
    Monte Carlo: génère des séries de rendements aléatoires avec la même distribution
    et mesure combien de fois un Sharpe aléatoire dépasse le Sharpe observé.
    """
    from whatsapp_analysis.phase11_backtest import TRADING_DAYS_YEAR

    returns = equity_curve.pct_change().dropna()
    if len(returns) < 10:
        return {"p_value": 1.0, "significant": False}

    ret_arr = returns.values
    rng = np.random.RandomState(seed)
    rf_daily = (1 + 0.03) ** (1 / TRADING_DAYS_YEAR) - 1

    null_sharpes = []
    for _ in range(n_iterations):
        shuffled = rng.permutation(ret_arr)
        vol = np.std(shuffled)
        if vol < 1e-9:
            null_sharpes.append(0.0)
            continue
        excess = shuffled - rf_daily
        sh = float(np.mean(excess) * TRADING_DAYS_YEAR / (vol * np.sqrt(TRADING_DAYS_YEAR)))
        if np.isfinite(sh):
            null_sharpes.append(sh)

    null_sharpes = np.array(null_sharpes)
    p_value = float(np.mean(null_sharpes >= observed_sharpe))

    return {
        "observed_sharpe": float(observed_sharpe),
        "null_mean": float(np.mean(null_sharpes)),
        "null_std": float(np.std(null_sharpes)),
        "null_p95": float(np.percentile(null_sharpes, 95)),
        "p_value": p_value,
        "significant": p_value < ALPHA,
        "n_iterations": n_iterations,
    }


# ─────────────────────────────────────────────────────────────
# PERMUTATION TESTS
# ─────────────────────────────────────────────────────────────

def permutation_test_correlation(
    sentiment: pd.Series,
    returns: pd.Series,
    observed_corr: float,
    n_permutations: int = N_MONTE_CARLO,
    seed: int = 42,
) -> Dict[str, Any]:
    """
    Test de permutation: mélange les dates du sentiment et recalcule les corrélations.
    Tests si la corrélation observée est due au hasard.
    """
    from scipy.stats import pearsonr

    rng = np.random.RandomState(seed)
    common_idx = sentiment.dropna().index.intersection(returns.dropna().index)

    if len(common_idx) < 20:
        return {"p_value": 1.0, "significant": False}

    s = sentiment.reindex(common_idx).values
    r = returns.reindex(common_idx).values

    permuted_corrs = []
    for _ in range(n_permutations):
        s_shuffled = rng.permutation(s)
        try:
            corr, _ = pearsonr(s_shuffled, r)
            if np.isfinite(corr):
                permuted_corrs.append(corr)
        except Exception:
            pass

    if not permuted_corrs:
        return {"p_value": 1.0, "significant": False}

    permuted_corrs = np.array(permuted_corrs)
    # Test bilatéral
    p_value = float(np.mean(np.abs(permuted_corrs) >= abs(observed_corr)))

    return {
        "observed_correlation": float(observed_corr),
        "permuted_mean": float(np.mean(permuted_corrs)),
        "permuted_std": float(np.std(permuted_corrs)),
        "p_value": p_value,
        "significant": p_value < ALPHA,
        "n_permutations": n_permutations,
    }


# ─────────────────────────────────────────────────────────────
# TESTS KS & MANN-WHITNEY
# ─────────────────────────────────────────────────────────────

def ks_test_smart_money_returns(
    equity_smart: pd.Series,
    equity_random: pd.Series,
) -> Dict[str, Any]:
    """
    Test KS: les rendements des signaux Smart Money sont-ils différents du hasard?
    """
    if equity_smart.empty or equity_random.empty:
        return {"p_value": 1.0, "significant": False}

    ret_smart = equity_smart.pct_change().dropna().values
    ret_random = equity_random.pct_change().dropna().values

    if len(ret_smart) < 5 or len(ret_random) < 5:
        return {"p_value": 1.0, "significant": False}

    ks_stat, p_value = ks_2samp(ret_smart, ret_random)
    mw_stat, mw_p = mannwhitneyu(ret_smart, ret_random, alternative="greater")

    return {
        "ks_statistic": float(ks_stat),
        "ks_p_value": float(p_value),
        "mann_whitney_statistic": float(mw_stat),
        "mann_whitney_p_value": float(mw_p),
        "significant_ks": p_value < ALPHA,
        "significant_mw": mw_p < ALPHA,
        "smart_mean_return": float(np.mean(ret_smart)),
        "random_mean_return": float(np.mean(ret_random)),
        "interpretation": (
            "Les rendements Smart Money sont statistiquement différents du hasard"
            if p_value < ALPHA
            else "Pas de différence statistiquement significative vs hasard"
        ),
    }


# ─────────────────────────────────────────────────────────────
# CORRECTION POUR TESTS MULTIPLES (Benjamini-Hochberg)
# ─────────────────────────────────────────────────────────────

def benjamini_hochberg_correction(
    p_values: List[float],
    alpha: float = ALPHA,
) -> Tuple[List[bool], List[float]]:
    """
    Correction de Benjamini-Hochberg pour contrôler le FDR (False Discovery Rate).
    Retourne: (reject_array, adjusted_p_values)
    """
    n = len(p_values)
    if n == 0:
        return [], []

    p_arr = np.array(p_values, dtype=float)
    sorted_idx = np.argsort(p_arr)
    sorted_p = p_arr[sorted_idx]

    # BH threshold: p_i <= (i/n) * alpha
    bh_threshold = (np.arange(1, n + 1) / n) * alpha
    reject_sorted = sorted_p <= bh_threshold

    # Propagation: si reject[k]=True, tous les précédents aussi
    if np.any(reject_sorted):
        last_reject = np.where(reject_sorted)[0][-1]
        reject_sorted[:last_reject + 1] = True

    # Adjusted p-values (BH)
    adjusted_sorted = np.minimum(1.0, sorted_p * n / np.arange(1, n + 1))
    # Monotonicity
    for i in range(n - 2, -1, -1):
        adjusted_sorted[i] = min(adjusted_sorted[i], adjusted_sorted[i + 1])

    # Remet dans l'ordre original
    reject = np.empty(n, dtype=bool)
    adjusted_p = np.empty(n)
    reject[sorted_idx] = reject_sorted
    adjusted_p[sorted_idx] = adjusted_sorted

    return reject.tolist(), adjusted_p.tolist()


def apply_multiple_testing_correction(
    test_results: Dict[str, Dict[str, Any]],
    p_value_key: str = "p_value",
) -> Dict[str, Dict[str, Any]]:
    """
    Applique la correction BH à tous les tests d'un dictionnaire.
    """
    keys = [k for k, v in test_results.items() if isinstance(v, dict) and p_value_key in v]
    p_values = [test_results[k][p_value_key] for k in keys]

    if not p_values:
        return test_results

    reject, adjusted = benjamini_hochberg_correction(p_values)

    for i, k in enumerate(keys):
        test_results[k]["bh_reject"] = reject[i]
        test_results[k]["bh_adjusted_p"] = adjusted[i]

    return test_results


# ─────────────────────────────────────────────────────────────
# ANALYSE DU SUR-APPRENTISSAGE
# ─────────────────────────────────────────────────────────────

def overfitting_assessment(
    model_results: Dict[str, Any],
    n_features: int,
    n_observations: int,
    in_sample_auc: float,
    out_sample_auc: float,
) -> Dict[str, Any]:
    """
    Évalue le risque de sur-apprentissage.
    """
    # Ratio paramètres/observations
    param_ratio = n_features / max(n_observations, 1)

    # IS vs OOS performance
    oos_ratio = out_sample_auc / max(in_sample_auc, 0.5)

    # Dégradation (% de perte de performance IS->OOS)
    degradation = (in_sample_auc - out_sample_auc) / max(in_sample_auc - 0.5, 0.01)

    # Évaluation
    risk_level = "FAIBLE"
    warnings_list = []

    if param_ratio > 0.1:
        risk_level = "MODÉRÉ"
        warnings_list.append(f"Ratio features/observations élevé: {param_ratio:.2f}")

    if degradation > 0.3:
        risk_level = "ÉLEVÉ"
        warnings_list.append(
            f"Forte dégradation IS→OOS: {degradation:.1%} | IS AUC={in_sample_auc:.3f} → OOS AUC={out_sample_auc:.3f}"
        )

    if out_sample_auc < 0.52:
        risk_level = "ÉLEVÉ"
        warnings_list.append(f"Performance OOS proche du hasard: AUC={out_sample_auc:.3f}")

    if param_ratio > 0.5:
        risk_level = "CRITIQUE"
        warnings_list.append("Nombre de features >> observations: sur-apprentissage probable")

    return {
        "risk_level": risk_level,
        "param_ratio": float(param_ratio),
        "is_auc": float(in_sample_auc),
        "oos_auc": float(out_sample_auc),
        "oos_ratio": float(oos_ratio),
        "degradation_pct": float(degradation),
        "n_features": n_features,
        "n_observations": n_observations,
        "warnings": warnings_list,
    }


def walk_forward_stability(
    X: pd.DataFrame,
    y: pd.Series,
    model: Any,
    n_splits: int = 5,
) -> Dict[str, Any]:
    """
    Teste la stabilité walk-forward: les performances sont-elles cohérentes
    sur différentes fenêtres temporelles?
    """
    from sklearn.model_selection import TimeSeriesSplit
    from sklearn.metrics import roc_auc_score
    import copy

    if X.empty or y.empty or model is None:
        return {"stable": False, "error": "Données manquantes"}

    tscv = TimeSeriesSplit(n_splits=n_splits)
    fold_aucs = []

    for fold_idx, (train_idx, test_idx) in enumerate(tscv.split(X)):
        X_tr = X.iloc[train_idx].values
        y_tr = y.iloc[train_idx].values
        X_te = X.iloc[test_idx].values
        y_te = y.iloc[test_idx].values

        if len(np.unique(y_tr)) < 2 or len(np.unique(y_te)) < 2:
            continue

        try:
            m = copy.deepcopy(model)
            m.fit(X_tr, y_tr)
            if hasattr(m, "predict_proba"):
                prob = m.predict_proba(X_te)[:, 1]
            else:
                prob = m.predict(X_te).astype(float)

            if len(np.unique(y_te)) >= 2:
                auc = roc_auc_score(y_te, prob)
                fold_aucs.append(float(auc))
        except Exception as e:
            logger.debug(f"Walk-forward fold {fold_idx}: {e}")

    if not fold_aucs:
        return {"stable": False, "fold_aucs": [], "cv_of_auc": np.nan}

    fold_arr = np.array(fold_aucs)
    cv_of_auc = float(np.std(fold_arr) / max(np.mean(fold_arr), 0.01))  # Coefficient de variation

    is_stable = (cv_of_auc < 0.20) and (np.min(fold_arr) > 0.50)

    return {
        "stable": is_stable,
        "fold_aucs": fold_aucs,
        "mean_auc": float(np.mean(fold_arr)),
        "std_auc": float(np.std(fold_arr)),
        "cv_of_auc": cv_of_auc,
        "min_fold_auc": float(np.min(fold_arr)),
        "max_fold_auc": float(np.max(fold_arr)),
        "n_folds": len(fold_aucs),
        "interpretation": (
            f"Modèle stable (CV={cv_of_auc:.2f})" if is_stable
            else f"Instabilité détectée (CV={cv_of_auc:.2f})"
        ),
    }


# ─────────────────────────────────────────────────────────────
# POINT D'ENTRÉE PRINCIPAL
# ─────────────────────────────────────────────────────────────

def run_phase12(
    df: pd.DataFrame,
    stock_scores: Optional[pd.DataFrame] = None,
    member_scores: Optional[pd.DataFrame] = None,
    fear_greed_series: Optional[pd.Series] = None,
    graph_metrics: Optional[pd.DataFrame] = None,
    phase8_results: Optional[Dict[str, Any]] = None,
    phase9_results: Optional[Dict[str, Any]] = None,
    phase11_results: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Exécute la Phase 12: Tests statistiques de robustesse.

    Returns dict with keys:
        stats_report (dict complet avec p-values, CI, warnings)
    """
    logger.info("=== Phase 12: Tests Statistiques de Robustesse ===")

    stats_report: Dict[str, Any] = {
        "bootstrap_auc": {},
        "bootstrap_sharpe": {},
        "bootstrap_correlation": {},
        "monte_carlo_auc": {},
        "monte_carlo_sharpe": {},
        "permutation_correlation": {},
        "ks_tests": {},
        "multiple_testing": {},
        "overfitting": {},
        "walk_forward": {},
        "warnings": [],
    }

    # ── 1. Bootstrap AUC (depuis phase 9) ──────────────────
    if phase9_results is not None:
        X = phase9_results.get("X", pd.DataFrame())
        y = phase9_results.get("y", pd.Series(dtype=float))
        best_model = phase9_results.get("best_model")
        model_results = phase9_results.get("model_results", {})

        if not X.empty and not y.empty and best_model is not None:
            logger.info("Bootstrap AUC sur le meilleur modèle...")
            n = len(X)
            split = int(n * 0.8)

            X_train = X.iloc[:split].values
            y_train = y.iloc[:split].values
            X_test = X.iloc[split:].values
            y_test = y.iloc[split:].values

            if len(X_train) > 10 and len(X_test) > 5:
                try:
                    import copy
                    m = copy.deepcopy(best_model)
                    m.fit(X_train, y_train)
                    if hasattr(m, "predict_proba"):
                        y_prob = m.predict_proba(X_test)[:, 1]
                    else:
                        y_prob = m.predict(X_test).astype(float)

                    auc_ci = bootstrap_auc(y_test, y_prob)
                    stats_report["bootstrap_auc"]["best_model"] = auc_ci
                    logger.info(f"  AUC: {auc_ci.get('mean', 0):.4f} "
                                f"[{auc_ci.get('ci_lower', 0):.4f}, {auc_ci.get('ci_upper', 0):.4f}]")

                    # Monte Carlo null
                    best_name = model_results.get("_best_model_name", "")
                    obs_auc = model_results.get(best_name, {}).get("auc_roc", 0.5)
                    mc_result = monte_carlo_null_auc(y_test, obs_auc)
                    stats_report["monte_carlo_auc"]["best_model"] = mc_result
                    logger.info(f"  Monte Carlo AUC p-value: {mc_result.get('p_value', 1.0):.4f}")

                    # Walk-forward stability
                    wf = walk_forward_stability(X, y, best_model)
                    stats_report["walk_forward"]["best_model"] = wf
                    logger.info(f"  Walk-forward: {wf.get('interpretation', 'N/A')}")

                    # Overfitting assessment
                    # IS AUC: cross-val mean; OOS AUC: test set
                    is_auc = model_results.get(best_name, {}).get("cv_auc_roc_mean", 0.5)
                    ov = overfitting_assessment(
                        model_results=model_results,
                        n_features=X.shape[1],
                        n_observations=len(X),
                        in_sample_auc=is_auc,
                        out_sample_auc=obs_auc,
                    )
                    stats_report["overfitting"] = ov
                    if ov["risk_level"] in ("ÉLEVÉ", "CRITIQUE"):
                        stats_report["warnings"].extend(ov["warnings"])
                    logger.info(f"  Risque sur-apprentissage: {ov['risk_level']}")

                except Exception as e:
                    logger.error(f"Erreur bootstrap ML: {e}")

    # ── 2. Bootstrap Sharpe (depuis phase 11) ──────────────
    if phase11_results is not None:
        equity_curves = phase11_results.get("equity_curves", {})
        strategy_metrics = phase11_results.get("strategy_metrics", {})

        for strat_name, eq in equity_curves.items():
            if eq is None or (hasattr(eq, 'empty') and eq.empty):
                continue

            logger.info(f"Bootstrap Sharpe: {strat_name}...")
            returns = eq.pct_change().dropna()

            if len(returns) < 20:
                continue

            sh_ci = bootstrap_sharpe(returns)
            stats_report["bootstrap_sharpe"][strat_name] = sh_ci

            # Monte Carlo Sharpe
            obs_sharpe = strategy_metrics.get(strat_name, {}).get("sharpe", 0.0)
            if obs_sharpe and np.isfinite(obs_sharpe):
                mc_sh = monte_carlo_null_sharpe(eq, obs_sharpe)
                stats_report["monte_carlo_sharpe"][strat_name] = mc_sh

        logger.info(f"  {len(stats_report['bootstrap_sharpe'])} stratégies testées")

    # ── 3. Bootstrap Corrélation Lead-Lag (depuis phase 8) ──
    if phase8_results is not None:
        ll_results = phase8_results.get("lead_lag_results", {})
        daily_sentiment = phase8_results.get("daily_sentiment", pd.DataFrame())
        price_panel = phase8_results.get("price_panel", pd.DataFrame())

        if not daily_sentiment.empty and not price_panel.empty:
            logger.info("Bootstrap corrélation lead-lag globale...")
            sent = daily_sentiment.set_index("date")["sentiment_mean"].dropna()
            sent.index = pd.to_datetime(sent.index)
            market_ret = price_panel.pct_change().mean(axis=1).dropna()
            market_ret.index = pd.to_datetime(market_ret.index)

            common = sent.index.intersection(market_ret.index)
            if len(common) >= 20:
                x = sent.reindex(common).values
                y_arr = market_ret.reindex(common).values
                mask = np.isfinite(x) & np.isfinite(y_arr)
                if mask.sum() >= 20:
                    corr_ci = bootstrap_correlation(x[mask], y_arr[mask])
                    stats_report["bootstrap_correlation"]["global"] = corr_ci

                    # Permutation test
                    obs_corr = float(np.corrcoef(x[mask], y_arr[mask])[0, 1])
                    perm = permutation_test_correlation(
                        pd.Series(x[mask]), pd.Series(y_arr[mask]), obs_corr
                    )
                    stats_report["permutation_correlation"]["global"] = perm
                    logger.info(f"  Corrélation: {obs_corr:.4f} | "
                                f"Permutation p-value: {perm.get('p_value', 1.0):.4f}")

    # ── 4. KS Test Smart Money vs Random ──────────────────
    if phase11_results is not None:
        equity_curves = phase11_results.get("equity_curves", {})
        smart_eq = equity_curves.get("Smart_Money_Only") or equity_curves.get("Smart_Sentiment")
        bh_eq = equity_curves.get("BuyAndHold_MASI")

        if smart_eq is not None and bh_eq is not None:
            logger.info("Test KS: Smart Money vs Buy&Hold...")
            ks_res = ks_test_smart_money_returns(smart_eq, bh_eq)
            stats_report["ks_tests"]["smart_money_vs_benchmark"] = ks_res
            logger.info(f"  KS p-value: {ks_res.get('ks_p_value', 1.0):.4f}")

    # ── 5. Correction pour Tests Multiples ─────────────────
    logger.info("Application de la correction Benjamini-Hochberg...")

    # Collecte tous les p-values des tests
    all_p_tests: Dict[str, Dict[str, Any]] = {}

    for strat, res in stats_report["monte_carlo_sharpe"].items():
        if isinstance(res, dict) and "p_value" in res:
            all_p_tests[f"sharpe_{strat}"] = res

    for ticker, res in stats_report["permutation_correlation"].items():
        if isinstance(res, dict) and "p_value" in res:
            all_p_tests[f"corr_{ticker}"] = res

    for test, res in stats_report["monte_carlo_auc"].items():
        if isinstance(res, dict) and "p_value" in res:
            all_p_tests[f"auc_{test}"] = res

    all_p_tests = apply_multiple_testing_correction(all_p_tests)
    stats_report["multiple_testing"] = {
        "n_tests": len(all_p_tests),
        "n_significant_raw": sum(
            1 for r in all_p_tests.values()
            if isinstance(r, dict) and r.get("p_value", 1.0) < ALPHA
        ),
        "n_significant_bh": sum(
            1 for r in all_p_tests.values()
            if isinstance(r, dict) and r.get("bh_reject", False)
        ),
        "individual_tests": all_p_tests,
    }

    # ── 6. Résumé global ───────────────────────────────────
    n_sig = stats_report["multiple_testing"]["n_significant_bh"]
    n_total = stats_report["multiple_testing"]["n_tests"]
    risk = stats_report.get("overfitting", {}).get("risk_level", "INCONNU")

    logger.info(f"\nPhase 12 terminée:")
    logger.info(f"  Tests significatifs (après BH): {n_sig}/{n_total}")
    logger.info(f"  Risque sur-apprentissage: {risk}")
    logger.info(f"  Warnings: {len(stats_report['warnings'])}")

    if stats_report["warnings"]:
        for w in stats_report["warnings"]:
            logger.warning(f"  ⚠ {w}")

    stats_report["summary"] = {
        "n_tests_total": n_total,
        "n_significant_after_correction": n_sig,
        "overfitting_risk": risk,
        "n_warnings": len(stats_report["warnings"]),
        "bootstrap_models_tested": list(stats_report["bootstrap_auc"].keys()),
        "bootstrap_strategies_tested": list(stats_report["bootstrap_sharpe"].keys()),
    }

    return {"stats_report": stats_report}


# ─────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    print("Test Phase 12: tests statistiques de robustesse...")

    rng = np.random.RandomState(42)
    n = 500

    # Données synthétiques
    y_true = rng.binomial(1, 0.4, n)
    y_prob = 0.6 * y_true + 0.4 * rng.random(n)
    from sklearn.metrics import roc_auc_score
    obs_auc = roc_auc_score(y_true, y_prob)
    print(f"AUC observée: {obs_auc:.4f}")

    # Bootstrap AUC
    ci = bootstrap_auc(y_true, y_prob, n_iterations=500)
    print(f"Bootstrap AUC 95% CI: [{ci['ci_lower']:.4f}, {ci['ci_upper']:.4f}]")

    # Monte Carlo null
    mc = monte_carlo_null_auc(y_true, obs_auc, n_iterations=500)
    print(f"Monte Carlo p-value: {mc['p_value']:.4f}")
    print(f"Significatif: {mc['significant']}")

    # Bootstrap Sharpe
    returns = pd.Series(rng.normal(0.0005, 0.01, 252))
    sh_ci = bootstrap_sharpe(returns, n_iterations=500)
    print(f"\nBootstrap Sharpe 95% CI: [{sh_ci['ci_lower']:.3f}, {sh_ci['ci_upper']:.3f}]")

    # Correction BH
    p_values = [0.001, 0.01, 0.03, 0.04, 0.06, 0.1, 0.2, 0.5]
    reject, adj_p = benjamini_hochberg_correction(p_values)
    print(f"\nBH correction (alpha=0.05):")
    for p, r, ap in zip(p_values, reject, adj_p):
        print(f"  p={p:.3f} -> reject={r} | adj_p={ap:.4f}")

    # Overfitting assessment
    ov = overfitting_assessment(
        model_results={},
        n_features=50,
        n_observations=300,
        in_sample_auc=0.72,
        out_sample_auc=0.61,
    )
    print(f"\nOverfitting risk: {ov['risk_level']}")
    for w in ov["warnings"]:
        print(f"  {w}")
