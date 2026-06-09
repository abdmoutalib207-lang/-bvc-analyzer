#!/usr/bin/env python3
"""
BVC TERMINAL — collect_history_bvcscrap.py
═══════════════════════════════════════════════════════════════════════════════
Collecte 90 jours d'historique OHLCV via BVCscrap (wrapper Médias24) pour
les 72/77 tickers du terminal BVC et calcule les indicateurs techniques.

Résultat : pipeline/historical_data.json
  → utilisé par update_data.py comme source de MA20/MA50/RSI quand
    l'API Médias24 directe est bloquée (GitHub Actions).

À exécuter depuis Colab ou une machine non bloquée, idéalement chaque semaine.

Usage :
    python pipeline/collect_history_bvcscrap.py
    python pipeline/collect_history_bvcscrap.py --days 120
    python pipeline/collect_history_bvcscrap.py --tickers IAM,ATW,BCP

Dépendances :
    pip install bvcscrap pandas numpy

4 tickers sans mapping BVCscrap : SGTM, CMGP, VCNE, BMC
═══════════════════════════════════════════════════════════════════════════════
"""

import sys, json, time, argparse, logging
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Auto-install
for pkg in ["bvcscrap", "pandas", "numpy"]:
    try:
        __import__(pkg if pkg != "bvcscrap" else "BVCscrap")
    except ImportError:
        import subprocess
        subprocess.run([sys.executable, "-m", "pip", "install", pkg, "-q"], check=True)

import pandas as pd
import numpy as np

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("BVCSCRAP_HIST")

# ─────────────────────────────────────────────────────────────────────────────
# MAPPING ticker → nom BVCscrap (Médias24)
# 4 sans mapping : SGTM, CMGP, VCNE, BMC
# ─────────────────────────────────────────────────────────────────────────────

MANUAL_MAP: dict[str, str] = {
    # Grandes capitalisations
    "IAM":  "Maroc Telecom",
    "ATW":  "Attijariwafa bank",
    "BCP":  "Banque Centrale Populaire",
    "BOA":  "Bank Of Africa",
    "CIH":  "CIH Bank",
    "CDM":  "Crédit du Maroc",
    "WAF":  "Wafa Assurance",
    "LHM":  "LafargeHolcim Maroc",
    "GAZ":  "Afriquia Gaz",
    "ATL":  "Auto Hall",
    "HPS":  "HPS",
    "LBV":  "Label Vie",
    "LES":  "Lesieur Cristal",
    "TQA":  "Taqa Morocco",
    "MRL":  "Marsa Maroc",
    "TMA":  "TotalEnergies Marketing Maroc",
    "CMT":  "Ciments du Maroc",
    "MNG":  "Managem",
    "SMI":  "SMI",
    # Moyennes capitalisations
    "AKD":  "Akdital",
    "ARD":  "Aradei Capital",
    "SAF":  "Saham Assurance",
    "OUL":  "Les Eaux Minérales d'Oulmès",
    "CIM":  "Cimat",
    "CTM":  "CTM",
    "ZLD":  "Zellidja",
    "SOT":  "Sothema",
    "MSA":  "Mutandis",
    "ADI":  "Alliances",
    "ADH":  "Addoha",
    "TGCC": "TGCC",
    "CFGB": "CFG Bank",
    "CASH": "CashPlus",
    "SRM":  "Stokvis",
    "SNA":  "Sonasid",
    "RDS":  "RDSA",
    "RIS":  "Résidences Dar Saada",
    "CSR":  "Ciments de l'Atlas",
    "ALU":  "Aluminium du Maroc",
    "MGL":  "Maghreb Steel",
    "DAR":  "Dar Saada",
    "IMI":  "Immorente",
    "DTT":  "Disty Technologies",
    # Petites capitalisations
    "DSW":  "Disway",
    "MOX":  "Maghreb Oxygène",
    "STR":  "Stroc Industrie",
    "TIM":  "Timar",
    "SNP":  "SNEP",
    "SLM":  "Salafin",
    "JET":  "Jet Contractors",
    "M2M":  "M2M",
    "INV":  "Involys",
    "S2M":  "S2M",
    "COL":  "Colorado",
    "AFM":  "AFMA",
    "AGM":  "Agma Lahlou Tazi",
    "FNB":  "Finance.com",
    "BAL":  "Balima",
    "NEJ":  "Nejma",
    "HAL":  "Hala",
    "CAR":  "Cartier Saada",
    "AFI":  "Afine",
    "MIC":  "Microdata",
    "MUT":  "Mutandis SCA",
    "ENK":  "Enkaje",
    "EQD":  "Equity",
    "DHO":  "Daho",
    "PPM":  "Papier Industrie",
    "REB":  "Rebab Company",
    "SBS":  "Super Céréales",
    "STK":  "Stokvis Nord Afrique",
    "UNI":  "Unimer",
    "IBM":  "IB Maroc",
    # Sans mapping BVCscrap (seront ignorés) :
    # SGTM, CMGP, VCNE, BMC
}

# ─────────────────────────────────────────────────────────────────────────────
# INDICATEURS TECHNIQUES (même logique que update_data.py)
# ─────────────────────────────────────────────────────────────────────────────

def calc_rsi(closes: pd.Series, period: int = 14) -> float:
    delta    = closes.diff()
    up       = delta.clip(lower=0)
    down     = -delta.clip(upper=0)
    ema_up   = up.ewm(com=period - 1, adjust=False).mean()
    ema_down = down.ewm(com=period - 1, adjust=False).mean()
    rs       = ema_up / ema_down.replace(0, np.nan)
    rsi      = 100 - (100 / (1 + rs))
    return round(float(rsi.iloc[-1]), 1) if not rsi.empty else 50.0


def calc_ma(closes: pd.Series, period: int) -> float:
    if len(closes) < period:
        return round(float(closes.mean()), 2)
    return round(float(closes.tail(period).mean()), 2)


def calc_macd(closes: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9):
    if len(closes) < slow + signal:
        return None, None, None
    ema_f = closes.ewm(span=fast, adjust=False).mean()
    ema_s = closes.ewm(span=slow, adjust=False).mean()
    macd  = ema_f - ema_s
    sig   = macd.ewm(span=signal, adjust=False).mean()
    hist  = macd - sig
    return (
        round(float(macd.iloc[-1]), 4),
        round(float(sig.iloc[-1]),  4),
        round(float(hist.iloc[-1]), 4),
    )


def calc_bollinger(closes: pd.Series, period: int = 20, n_std: float = 2.0):
    if len(closes) < period:
        return None, None, None
    tail   = closes.tail(period)
    mid    = tail.mean()
    std    = tail.std(ddof=1)
    return (
        round(float(mid + n_std * std), 2),
        round(float(mid), 2),
        round(float(mid - n_std * std), 2),
    )


def calc_stoch(closes: pd.Series, highs: pd.Series, lows: pd.Series,
               k_period: int = 14, d_period: int = 3):
    if len(closes) < k_period:
        return None, None
    k_vals = []
    for i in range(d_period):
        idx = len(closes) - 1 - i
        if idx < k_period - 1:
            break
        c  = float(closes.iloc[idx])
        hh = float(highs.iloc[idx - k_period + 1: idx + 1].max())
        ll = float(lows.iloc[idx  - k_period + 1: idx + 1].min())
        d  = hh - ll
        k_vals.append(100 * (c - ll) / d if d > 0 else 50.0)
    if not k_vals:
        return None, None
    return round(k_vals[0], 2), round(float(np.mean(k_vals)), 2)


def compute_indicators(df: pd.DataFrame) -> dict:
    """Calcule tous les indicateurs à partir d'un DataFrame OHLCV."""
    closes = df["close"]
    highs  = df["high"]
    lows   = df["low"]

    rsi            = calc_rsi(closes)
    ma20           = calc_ma(closes, 20)
    ma50           = calc_ma(closes, 50)
    h90            = round(float(highs.max()), 2)
    l90            = round(float(lows.min()), 2)
    macd, ms, mh   = calc_macd(closes)
    bbu, bbm, bbl  = calc_bollinger(closes)
    sk, sd         = calc_stoch(closes, highs, lows)

    return {
        "rsi":         rsi,
        "ma20":        ma20,
        "ma50":        ma50,
        "h90":         h90,
        "l90":         l90,
        "macd":        macd,
        "macd_signal": ms,
        "macd_hist":   mh,
        "bb_upper":    bbu,
        "bb_mid":      bbm,
        "bb_lower":    bbl,
        "stoch_k":     sk,
        "stoch_d":     sd,
        "last_close":  round(float(closes.iloc[-1]), 2),
        "last_date":   str(df["date"].iloc[-1])[:10] if "date" in df.columns else "",
        "n_candles":   len(df),
    }

# ─────────────────────────────────────────────────────────────────────────────
# DÉCOUVERTE BVCscrap
# ─────────────────────────────────────────────────────────────────────────────

def discover_bvcscrap_names(bvc) -> set[str]:
    """Retourne l'ensemble des noms disponibles dans BVCscrap."""
    try:
        df = bvc.notation()
        if df is None or df.empty:
            return set()
        # La colonne contenant les noms s'appelle 'Société' ou similaire
        name_col = None
        for col in df.columns:
            if any(k in col.lower() for k in ["société", "societe", "company", "nom", "name", "valeur"]):
                name_col = col
                break
        if name_col is None and len(df.columns) > 0:
            name_col = df.columns[0]
        if name_col:
            return set(df[name_col].dropna().str.strip().tolist())
        return set()
    except Exception as e:
        log.warning(f"notation() échoué: {e}")
        return set()


def fuzzy_match(name: str, available: set[str]) -> str | None:
    """Cherche le meilleur match insensible à la casse et aux accents."""
    import unicodedata

    def normalize(s: str) -> str:
        return unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()

    norm_name = normalize(name)
    # Exact match après normalisation
    for a in available:
        if normalize(a) == norm_name:
            return a
    # Contient
    for a in available:
        if norm_name in normalize(a) or normalize(a) in norm_name:
            return a
    # Premier mot
    first = norm_name.split()[0] if norm_name.split() else ""
    for a in available:
        if normalize(a).startswith(first):
            return a
    return None

# ─────────────────────────────────────────────────────────────────────────────
# COLLECTE PRINCIPALE
# ─────────────────────────────────────────────────────────────────────────────

def fetch_ticker_history(bvc, name: str, days: int = 95) -> pd.DataFrame:
    """Récupère l'historique OHLCV BVCscrap et retourne un DataFrame standardisé."""
    try:
        end   = datetime.now()
        start = end - timedelta(days=days + 30)
        df    = bvc.historique(
            name,
            start.strftime("%Y-%m-%d"),
            end.strftime("%Y-%m-%d"),
        )
        if df is None or df.empty:
            return pd.DataFrame()

        # Normalisation colonnes BVCscrap → nos noms
        col_map = {}
        for col in df.columns:
            cl = col.lower()
            if any(k in cl for k in ["close", "clôture", "cloture", "dernier", "cours"]):
                col_map[col] = "close"
            elif any(k in cl for k in ["open", "ouvert"]):
                col_map[col] = "open"
            elif any(k in cl for k in ["high", "haut", "max"]):
                col_map[col] = "high"
            elif any(k in cl for k in ["low", "bas", "min"]):
                col_map[col] = "low"
            elif any(k in cl for k in ["vol", "volume"]):
                col_map[col] = "vol"
            elif any(k in cl for k in ["date"]):
                col_map[col] = "date"
        df = df.rename(columns=col_map)

        # Colonne date
        if "date" not in df.columns:
            df["date"] = pd.to_datetime(df.index)
        else:
            df["date"] = pd.to_datetime(df["date"], dayfirst=True, errors="coerce")

        # Colonne close obligatoire
        if "close" not in df.columns:
            return pd.DataFrame()

        for c in ["open", "high", "low", "vol"]:
            if c not in df.columns:
                df[c] = df["close"]

        df = df[["date", "open", "high", "low", "close", "vol"]].copy()
        df = df.dropna(subset=["date", "close"])
        df["close"] = pd.to_numeric(df["close"], errors="coerce")
        df["high"]  = pd.to_numeric(df["high"],  errors="coerce").fillna(df["close"])
        df["low"]   = pd.to_numeric(df["low"],   errors="coerce").fillna(df["close"])
        df["open"]  = pd.to_numeric(df["open"],  errors="coerce").fillna(df["close"])
        df = df[df["close"] > 0].sort_values("date").reset_index(drop=True)
        return df.tail(days)

    except Exception as e:
        log.debug(f"fetch_ticker_history({name}): {e}")
        return pd.DataFrame()


def run(tickers_filter: list[str] | None = None, days: int = 95) -> dict:
    try:
        from BVCscrap import BVCscrap
    except ImportError:
        try:
            from bvcscrap import BVCscrap
        except ImportError:
            log.error("BVCscrap non disponible — pip install bvcscrap")
            return {}

    bvc = BVCscrap()
    log.info("BVCscrap initialisé")

    # Découverte des noms disponibles
    available = discover_bvcscrap_names(bvc)
    if available:
        log.info(f"{len(available)} noms disponibles dans BVCscrap")
    else:
        log.warning("notation() vide — on essaie quand même avec MANUAL_MAP")

    # Résolution du mapping : MANUAL_MAP → vérification dans available
    resolved: dict[str, str] = {}
    unresolved: list[str] = []

    target = tickers_filter or list(MANUAL_MAP.keys())
    for ticker in target:
        if ticker not in MANUAL_MAP:
            unresolved.append(ticker)
            continue
        name = MANUAL_MAP[ticker]
        if available:
            # Vérifier que le nom est dans BVCscrap (ou fuzzy-matcher)
            if name in available:
                resolved[ticker] = name
            else:
                matched = fuzzy_match(name, available)
                if matched:
                    log.info(f"  {ticker}: '{name}' → '{matched}' (fuzzy)")
                    resolved[ticker] = matched
                else:
                    log.warning(f"  {ticker}: '{name}' introuvable dans BVCscrap")
                    unresolved.append(ticker)
        else:
            # Pas de liste dispo → on essaie directement
            resolved[ticker] = name

    log.info(f"{len(resolved)} tickers à collecter, {len(unresolved)} sans mapping")

    # Collecte historique
    results: dict = {}
    for i, (ticker, bvc_name) in enumerate(resolved.items(), 1):
        log.info(f"[{i}/{len(resolved)}] {ticker} ({bvc_name})")
        df = fetch_ticker_history(bvc, bvc_name, days=days)
        if df.empty or len(df) < 14:
            log.warning(f"  {ticker}: historique insuffisant ({len(df)} bougies) — ignoré")
            continue
        try:
            ind = compute_indicators(df)
            results[ticker] = ind
            log.info(
                f"  ✓ {len(df)} bougies → RSI={ind['rsi']} "
                f"MA20={ind['ma20']} MA50={ind['ma50']}"
            )
        except Exception as e:
            log.warning(f"  {ticker}: calcul indicateurs échoué: {e}")
        time.sleep(0.4)

    return results


# ─────────────────────────────────────────────────────────────────────────────
# SAUVEGARDE
# ─────────────────────────────────────────────────────────────────────────────

def save(results: dict, out_path: Path) -> None:
    existing: dict = {}
    if out_path.exists():
        try:
            existing = json.loads(out_path.read_text(encoding="utf-8"))
        except Exception:
            pass

    # Fusionner : nouvelles données écrasent l'existant ticker par ticker
    merged = {k: v for k, v in existing.items() if not k.startswith("_")}
    merged.update(results)

    output = {
        "_updated": datetime.now(timezone.utc).isoformat(),
        "_source":  "BVCscrap v0.2.1 (Médias24)",
        "_tickers": len(merged),
        **merged,
    }
    out_path.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    log.info(f"Sauvegardé : {out_path} ({len(merged)} tickers)")


# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="Collecte historique BVCscrap")
    parser.add_argument("--days",    type=int, default=95,
                        help="Fenêtre historique en jours (défaut: 95)")
    parser.add_argument("--tickers", type=str, default="",
                        help="Liste CSV de tickers à collecter (défaut: tous)")
    parser.add_argument("--dry-run", action="store_true",
                        help="N'écrit pas le fichier de sortie")
    args = parser.parse_args()

    tickers_filter = [t.strip().upper() for t in args.tickers.split(",") if t.strip()] or None

    results = run(tickers_filter=tickers_filter, days=args.days)

    if not results:
        log.error("Aucun résultat — vérifier la connexion et BVCscrap")
        sys.exit(1)

    log.info(f"\n{'='*60}")
    log.info(f"Résultats : {len(results)}/{len(MANUAL_MAP)} tickers collectés")
    missing = [t for t in MANUAL_MAP if t not in results]
    if missing:
        log.info(f"Manquants : {missing}")

    if not args.dry_run:
        try:
            out = Path(__file__).parent / "historical_data.json"
        except NameError:
            out = Path("pipeline/historical_data.json")
        save(results, out)
        print(f"\nFichier : {out}")
        print("Prochaine étape : committer et pousser historical_data.json sur le repo.")
    else:
        log.info("[dry-run] Aucune écriture")
        for t, v in sorted(results.items()):
            print(f"  {t:6s}: RSI={v['rsi']:5.1f} MA20={v['ma20']:8.2f} MA50={v['ma50']:8.2f} "
                  f"n={v['n_candles']}")


if __name__ == "__main__":
    main()
