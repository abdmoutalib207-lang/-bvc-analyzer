"""
BVC Data Loader — Chargement des données historiques réelles BVC
Sources: data/historique/*.xlsx (2 ans réels) + simulation GBM calibrée (4 ans)
"""
from __future__ import annotations

import pickle
from pathlib import Path
from typing import Dict, Optional, Tuple

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).parent.parent
HIST_DIR  = REPO_ROOT / "data" / "historique"
CACHE_PKL = REPO_ROOT / "data" / "bvc_prices.pkl"

# Mapping ticker → fichier Excel (TGCC est dans TGC.xlsx)
TICKER_FILE_MAP: Dict[str, str] = {
    "ADH":  "ADH",  "ADI":  "ADI",  "CASH": "CASH",
    "CFGB": "CFGB", "CMGP": "CMGP", "CMT":  "CMT",
    "CSR":  "CSR",  "MNG":  "MNG",  "MSA":  "MSA",
    "RDS":  "RDS",  "RIS":  "RIS",  "SGTM": "SGTM",
    "SMI":  "SMI",  "SOT":  "SOT",  "SRM":  "SRM",
    "TGCC": "TGC",  "VCNE": "VCNE",
}

CORPUS_START = pd.Timestamp("2020-09-01")
CORPUS_END   = pd.Timestamp("2026-06-05")


# ─────────────────────────────────────────────
# CHARGEMENT DONNÉES RÉELLES
# ─────────────────────────────────────────────

def load_real_prices() -> Dict[str, pd.DataFrame]:
    """Charge les 17 fichiers Excel historiques depuis data/historique/."""
    prices: Dict[str, pd.DataFrame] = {}
    if not HIST_DIR.exists():
        return prices

    for ticker, fname in TICKER_FILE_MAP.items():
        fpath = HIST_DIR / f"{fname}.xlsx"
        if not fpath.exists():
            continue
        try:
            df = pd.read_excel(fpath, engine="openpyxl")
            df["date"] = pd.to_datetime(df["date"])
            df = df.sort_values("date").set_index("date")
            # Normaliser les colonnes
            df.columns = [c.lower() for c in df.columns]
            prices[ticker] = df[["close", "high", "low", "open", "volume"]]
        except Exception as e:
            print(f"  Erreur chargement {ticker}: {e}")

    return prices


# ─────────────────────────────────────────────
# EXTENSION PAR GBM CALIBRÉ
# ─────────────────────────────────────────────

def _gbm_extend_backward(
    df_real: pd.DataFrame,
    target_start: pd.Timestamp,
    seed: int = 42,
) -> pd.DataFrame:
    """
    Étend un historique réel vers le passé par simulation GBM calibrée.
    Calibrage: μ et σ estimés depuis les données réelles.
    """
    if df_real.empty or df_real.index.min() <= target_start:
        return df_real

    real_start = df_real.index.min()
    real_close = df_real["close"].dropna()

    # Calibration μ, σ journaliers
    log_returns = np.log(real_close / real_close.shift(1)).dropna()
    mu    = float(log_returns.mean())
    sigma = float(log_returns.std())
    if sigma < 1e-6:
        sigma = 0.01

    # Jours ouvrables à générer
    biz_days = pd.bdate_range(start=target_start, end=real_start - pd.Timedelta(days=1))
    if len(biz_days) == 0:
        return df_real

    # GBM backward (on part du premier prix réel)
    rng = np.random.default_rng(seed)
    n   = len(biz_days)
    S0  = float(real_close.iloc[0])

    dt = 1.0
    z  = rng.standard_normal(n)
    # Path simulé forward, puis inversé pour le backward fill
    log_steps = (mu - 0.5 * sigma**2) * dt + sigma * np.sqrt(dt) * z
    # On génère vers le passé (reversal)
    path = S0 * np.exp(-np.cumsum(log_steps[::-1]))[::-1]

    # Volume simulé (proportionnel au volume moyen réel)
    vol_mean = float(df_real["volume"].mean()) if "volume" in df_real.columns else 10000
    vol_sim  = rng.lognormal(mean=np.log(max(vol_mean, 1)), sigma=0.5, size=n).astype(int)

    df_sim = pd.DataFrame({
        "close":  path,
        "high":   path * (1 + rng.uniform(0, 0.02, n)),
        "low":    path * (1 - rng.uniform(0, 0.02, n)),
        "open":   path * (1 + rng.uniform(-0.01, 0.01, n)),
        "volume": vol_sim,
        "_simulated": True,
    }, index=biz_days)

    df_real_copy = df_real.copy()
    df_real_copy["_simulated"] = False

    combined = pd.concat([df_sim, df_real_copy]).sort_index()
    combined = combined[~combined.index.duplicated(keep="last")]
    return combined


def extend_to_corpus_period(
    prices: Dict[str, pd.DataFrame],
    start: pd.Timestamp = CORPUS_START,
) -> Dict[str, pd.DataFrame]:
    """Étend toutes les séries vers le début du corpus WhatsApp."""
    extended: Dict[str, pd.DataFrame] = {}
    for i, (ticker, df) in enumerate(prices.items()):
        extended[ticker] = _gbm_extend_backward(df, start, seed=42 + i)
    return extended


# ─────────────────────────────────────────────
# MASI SYNTHÉTIQUE (si pas de données réelles)
# ─────────────────────────────────────────────

def build_masi_proxy(prices: Dict[str, pd.DataFrame]) -> pd.Series:
    """
    Construit un proxy MASI à partir de la moyenne pondérée des prix normalisés.
    Si un seul ticker dispo, utilise celui-ci normalisé.
    """
    if not prices:
        return pd.Series(dtype=float)

    all_close = pd.DataFrame({
        t: df["close"] for t, df in prices.items()
        if "close" in df.columns
    })

    # Normaliser chaque série à 100 au départ
    normalized = all_close.divide(all_close.iloc[0], axis=1) * 100
    masi_proxy = normalized.mean(axis=1).rename("MASI")
    return masi_proxy


# ─────────────────────────────────────────────
# DAILY RETURNS
# ─────────────────────────────────────────────

def compute_returns(prices: Dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Calcule les rendements journaliers pour chaque ticker."""
    close_df = pd.DataFrame({
        t: df["close"] for t, df in prices.items()
        if "close" in df.columns
    })
    return close_df.pct_change().fillna(0)


# ─────────────────────────────────────────────
# POINT D'ENTRÉE PRINCIPAL
# ─────────────────────────────────────────────

def load_bvc_prices(
    extend: bool = True,
    use_cache: bool = True,
    force_reload: bool = False,
) -> Tuple[Dict[str, pd.DataFrame], pd.Series]:
    """
    Charge les données de prix BVC complètes.

    Returns
    -------
    prices : dict {ticker: DataFrame avec colonnes close/high/low/open/volume/_simulated}
    masi_proxy : Series (proxy MASI normalisé à 100)
    """
    # Cache
    if use_cache and CACHE_PKL.exists() and not force_reload:
        try:
            with open(CACHE_PKL, "rb") as f:
                return pickle.load(f)
        except Exception:
            pass

    # 1. Charger données réelles
    prices = load_real_prices()
    n_real = len(prices)
    print(f"  → {n_real} tickers avec données réelles (2024-2026)")

    if not prices:
        print("  ⚠ Aucune donnée réelle — simulation complète")
        # Générer données synthétiques pour les tickers principaux
        main_tickers = ["MNG", "ADH", "SMI", "HPS", "IAM", "ATW", "BCP", "CMT"]
        prices = _simulate_full_history(main_tickers)

    # 2. Étendre vers le début du corpus
    if extend:
        print(f"  → Extension GBM vers {CORPUS_START.date()} (calibrée sur données réelles)")
        prices = extend_to_corpus_period(prices)

    # 3. MASI proxy
    masi = build_masi_proxy(prices)

    result = (prices, masi)

    # Cache
    CACHE_PKL.parent.mkdir(parents=True, exist_ok=True)
    with open(CACHE_PKL, "wb") as f:
        pickle.dump(result, f)

    return result


def _simulate_full_history(
    tickers: list,
    start: pd.Timestamp = CORPUS_START,
    end: pd.Timestamp = CORPUS_END,
) -> Dict[str, pd.DataFrame]:
    """Simulation GBM complète pour tickers sans données réelles."""
    rng = np.random.default_rng(99)
    biz_days = pd.bdate_range(start=start, end=end)
    n = len(biz_days)

    # Paramètres BVC typiques: rendement ~8% annuel, vol ~20%
    mu_annual    = 0.08
    sigma_annual = 0.20
    mu    = mu_annual / 252
    sigma = sigma_annual / np.sqrt(252)

    prices = {}
    for i, ticker in enumerate(tickers):
        S0 = rng.uniform(100, 2000)
        z  = rng.standard_normal(n)
        log_path = np.cumsum((mu - 0.5*sigma**2) + sigma * z)
        path = S0 * np.exp(log_path)
        vol  = rng.lognormal(mean=np.log(10000), sigma=0.8, size=n).astype(int)
        prices[ticker] = pd.DataFrame({
            "close": path,
            "high":  path * (1 + rng.uniform(0, 0.02, n)),
            "low":   path * (1 - rng.uniform(0, 0.02, n)),
            "open":  path * (1 + rng.uniform(-0.01, 0.01, n)),
            "volume": vol,
            "_simulated": True,
        }, index=biz_days)

    return prices


# ─────────────────────────────────────────────
# RAPPORT DISPONIBILITÉ
# ─────────────────────────────────────────────

def print_data_coverage(prices: Dict[str, pd.DataFrame]) -> None:
    print(f"\n{'═'*55}")
    print(f"  COUVERTURE DONNÉES HISTORIQUES BVC")
    print(f"{'═'*55}")
    for ticker, df in sorted(prices.items()):
        real_rows  = int((~df.get("_simulated", pd.Series(False))).sum())
        sim_rows   = len(df) - real_rows
        start      = df.index.min().strftime("%Y-%m-%d")
        end        = df.index.max().strftime("%Y-%m-%d")
        pct_real   = real_rows / len(df) * 100 if len(df) > 0 else 0
        print(f"  {ticker:<6} {start} → {end}  "
              f"réel={real_rows:>4}j  sim={sim_rows:>4}j  ({pct_real:.0f}% réel)")
    print(f"{'═'*55}\n")


if __name__ == "__main__":
    print("Chargement des données BVC...")
    prices, masi = load_bvc_prices(force_reload=True)
    print_data_coverage(prices)

    returns = compute_returns(prices)
    print(f"Rendements calculés: {returns.shape}")
    print(returns.tail(3))

    print(f"\nProxy MASI: {len(masi)} observations")
    print(f"Période: {masi.index.min()} → {masi.index.max()}")
    print(masi.tail(3))
