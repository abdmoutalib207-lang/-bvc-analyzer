#!/usr/bin/env python3
import sys, json, time, argparse, logging
from datetime import datetime, timedelta, timezone
from pathlib import Path

try:
    import pandas as pd
    import numpy as np
except ImportError as _e:
    sys.exit(f"Dépendance manquante : {_e}\nInstalle : pip install -r requirements_pipeline.txt")

sys.path.insert(0, str(Path(__file__).parent.parent))
from bvc_config import SPLITS

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("BVCSCRAP_HIST")


def adjust_splits_df(ticker: str, df: "pd.DataFrame") -> "pd.DataFrame":
    """Ajuste les cours pré-split d'une source BRUTE (XLSX / BVCscrap).

    Ces sources identifient les sociétés par NOM et renvoient des cours NON
    ajustés : sans ce correctif, l'historique antérieur à un split reste à
    l'ancienne échelle (fausse chute de -90%, MA/Bollinger/52w faussés).

    ⚠️ À n'appliquer QUE sur des données fraîchement téléchargées. Les candles
    déjà stockées sont ajustées ; les repasser ici provoquerait un double split.
    """
    splits = SPLITS.get(ticker)
    if not splits or df.empty or "date" not in df.columns:
        return df
    df = df.copy()
    # Les sources renvoient souvent des cours entiers (dtype int64). Diviser
    # produit des décimales (5119/10 = 511.9) : sans ce cast, pandas 3 lève
    # "TypeError: Invalid value '[511.9 ...]' for dtype 'int64'".
    price_cols = [c for c in ("open", "high", "low", "close") if c in df.columns]
    for col in price_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce").astype("float64")
    for sp in splits:
        eff = pd.Timestamp(sp["date"])
        mask = df["date"] < eff
        if mask.any():
            for col in price_cols:
                df.loc[mask, col] = (df.loc[mask, col] / sp["ratio"]).round(2)
            log.info(f"  split {ticker} {sp['date']} 1:{sp['ratio']} — "
                     f"{int(mask.sum())} bougies ajustées")
    return df

MANUAL_MAP: dict[str, str] = {
    # ── Grandes capitalisations ───────────────────────────────────────────────
    "IAM":  "Maroc Telecom",
    "ATW":  "Attijariwafa",
    "BCP":  "BCP",
    "BOA":  "BOA",
    "CIH":  "CIH",
    "CDM":  "CDM",
    "WAF":  "Wafa Assur",
    "LHM":  "LafargeHolcim",
    "GAZ":  "Afriquia Gaz",
    "ATL":  "AtlantaSanad",    # ATL = AtlantaSanad (assurance) — PAS Auto Hall (= HAL)
    "HPS":  "HPS",
    "LBV":  "LABEL VIE",
    "LES":  "Lesieur Cristal",
    "TQA":  "TAQA Morocco",
    "MRL":  "SODEP",           # SODEP = ancien nom BVCscrap pour Marsa Maroc (MRL)
    "TMA":  "Total Maroc",
    "CMT":  "CMT",
    "MNG":  "Managem",
    "SMI":  "SMI",
    # ── Moyennes capitalisations ──────────────────────────────────────────────
    "AKD":  "Akdital",
    "ARD":  "Aradei Capital",
    "SAF":  "Sanlam Maroc",
    "OUL":  "Oulmes",
    "CIM":  "Ciments du Maroc",
    "CTM":  "CTM",
    "ZLD":  "Zellidja",
    "SOT":  "SOTHEMA",
    "MSA":  "Marsa Maroc",     # MSA = Marsa Maroc — PAS Mutandis (= MUT)
    "ADI":  "Alliances",
    "ADH":  "Addoha",
    "TGCC": "TGCC",
    "CFGB": "CFG Bank",        # CFGB = CFG Bank — PAS BMCI (= BMC)
    "CASH": "Cash Plus",
    "SGTM": "SGTM",
    "CMGP": "CMGP Group",
    "VCNE": "Vivo Energy",
    "RIS":  "Risma",
    "CSR":  "Cosumar",
    "SNA":  "Sonasid",
    "SRM":  "SRM",
    "RDS":  "Dar Saada",       # RDS = Résidences Dar Saada — DAR est Dari Couspate
    "ALU":  "Aluminium Maroc",
    "MGL":  "Maghrebail",
    "DAR":  "Dari Couspate",   # DAR = Dari Couspate (agroalim.) — PAS Dar Saada (= RDS)
    "IMI":  "Immr Invest",
    "DTT":  "Disty Technolog",
    # ── Petites capitalisations ───────────────────────────────────────────────
    "DSW":  "DISWAY",
    "MOX":  "Maghreb Oxygene",
    "STR":  "STROC Indus",
    "TIM":  "Timar",
    "SNP":  "SNEP",
    "SLM":  "SALAFIN",
    "JET":  "Jet Contractors",
    "M2M":  "M2M Group",
    "INV":  "INVOLYS",
    "S2M":  "S2M",
    "COL":  "Colorado",
    "AFM":  "AFMA",
    "AGM":  "Agma",
    "FNB":  "Fenie Brossette",
    "BAL":  "BALIMA",
    "NEJ":  "Auto Nejma",
    "HAL":  "Auto Hall",       # HAL = Auto Hall — PAS ATL (= AtlantaSanad)
    "BMC":  "BMCI",            # BMC = BMCI — PAS CFGB (= CFG Bank)
    "CAR":  "Cartier Saada",
    "AFI":  "Afric Indus",
    "MIC":  "Microdata",
    "MUT":  "Mutandis",        # MUT = Mutandis SCA — PAS MSA (= Marsa Maroc)
    "ENK":  "Enkaje",
    "EQD":  "EQDOM",
    "DHO":  "Delta Holding",
    "PPM":  "Papelera Tetuan",
    "REB":  "Rebab Company",
    "SBS":  "Super Cereales",  # SBS = Super Céréales — PAS Société des Boissons
    "STK":  "Stokvis Nord Afr",
    "UNI":  "Unimer",
    "IBM":  "IBMaroc",
}

XLSX_DIR = Path(__file__).parent.parent / "data" / "historique"


def load_xlsx(ticker: str) -> pd.DataFrame:
    path = XLSX_DIR / f"{ticker}.xlsx"
    if not path.exists():
        return pd.DataFrame()
    try:
        df = pd.read_excel(path, engine="openpyxl")
        df.columns = [c.lower().strip() for c in df.columns]
        col_map = {}
        for col in df.columns:
            if col == "date":
                col_map[col] = "date"
            elif col in ("close", "clôture", "cloture", "dernier", "cours"):
                col_map[col] = "close"
            elif col in ("open", "ouvert"):
                col_map[col] = "open"
            elif col in ("high", "haut", "max"):
                col_map[col] = "high"
            elif col in ("low", "bas", "min"):
                col_map[col] = "low"
            elif "vol" in col:
                col_map[col] = "volume"
        df = df.rename(columns=col_map)
        if "date" not in df.columns or "close" not in df.columns:
            return pd.DataFrame()
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
        df = df.dropna(subset=["date", "close"])
        df["close"] = pd.to_numeric(df["close"], errors="coerce")
        for c in ["open", "high", "low"]:
            if c not in df.columns:
                df[c] = df["close"]
            else:
                df[c] = pd.to_numeric(df[c], errors="coerce").fillna(df["close"])
        if "volume" not in df.columns:
            df["volume"] = 0
        else:
            df["volume"] = pd.to_numeric(df["volume"], errors="coerce").fillna(0)
        df = df[df["close"] > 0].sort_values("date").reset_index(drop=True)
        return df[["date", "open", "high", "low", "close", "volume"]]
    except Exception as e:
        log.warning(f"Erreur lecture {path}: {e}")
        return pd.DataFrame()


def fetch_bvcscrap_extension(name: str, from_date: pd.Timestamp) -> pd.DataFrame:
    try:
        import BVCscrap as bvc
        start = (from_date + timedelta(days=1)).strftime("%Y-%m-%d")
        end = datetime.now().strftime("%Y-%m-%d")
        if start >= end:
            return pd.DataFrame()
        df = bvc.loadata(name, start=start, end=end)
        if df is None or df.empty:
            return pd.DataFrame()
        df = df.reset_index()
        col_map = {}
        for col in df.columns:
            cl = col.lower()
            if any(k in cl for k in ["close", "clôture", "cloture", "dernier", "cours", "value"]):
                col_map[col] = "close"
            elif any(k in cl for k in ["open", "ouvert"]):
                col_map[col] = "open"
            elif any(k in cl for k in ["high", "haut", "max"]):
                col_map[col] = "high"
            elif any(k in cl for k in ["low", "bas", "min"]):
                col_map[col] = "low"
            elif any(k in cl for k in ["vol", "volume"]):
                col_map[col] = "volume"
            elif any(k in cl for k in ["date", "index"]):
                col_map[col] = "date"
        df = df.rename(columns=col_map)
        if "date" not in df.columns:
            df["date"] = pd.date_range(end=datetime.now(), periods=len(df), freq="B")
        else:
            df["date"] = pd.to_datetime(df["date"], dayfirst=True, errors="coerce")
        if "close" not in df.columns:
            return pd.DataFrame()
        for c in ["open", "high", "low"]:
            if c not in df.columns:
                df[c] = df["close"]
        if "volume" not in df.columns:
            df["volume"] = 0
        df = df[["date", "open", "high", "low", "close", "volume"]].copy()
        df = df.dropna(subset=["date", "close"])
        df["close"]  = pd.to_numeric(df["close"],  errors="coerce")
        df["high"]   = pd.to_numeric(df["high"],   errors="coerce").fillna(df["close"])
        df["low"]    = pd.to_numeric(df["low"],    errors="coerce").fillna(df["close"])
        df["open"]   = pd.to_numeric(df["open"],   errors="coerce").fillna(df["close"])
        df["volume"] = pd.to_numeric(df["volume"], errors="coerce").fillna(0)
        df = df[df["close"] > 0].sort_values("date").reset_index(drop=True)
        return df
    except Exception as e:
        log.debug(f"loadata({name}): {e}")
        return pd.DataFrame()


def combine(xlsx_df: pd.DataFrame, ext_df: pd.DataFrame) -> pd.DataFrame:
    if ext_df.empty:
        return xlsx_df
    if xlsx_df.empty:
        return ext_df
    combined = pd.concat([xlsx_df, ext_df], ignore_index=True)
    combined = combined.drop_duplicates(subset=["date"]).sort_values("date").reset_index(drop=True)
    return combined


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
    tail = closes.tail(period)
    mid  = tail.mean()
    std  = tail.std(ddof=1)
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
    closes = df["close"]
    highs  = df["high"]
    lows   = df["low"]

    now = pd.Timestamp.now()
    w52_start = now - pd.Timedelta(weeks=52)
    w90_start = now - pd.Timedelta(days=90)

    df_52w = df[df["date"] >= w52_start]
    df_90  = df[df["date"] >= w90_start]

    h52w = round(float(df_52w["high"].max()), 2) if not df_52w.empty else round(float(highs.max()), 2)
    l52w = round(float(df_52w["low"].min()),  2) if not df_52w.empty else round(float(lows.min()),  2)
    h90  = round(float(df_90["high"].max()),  2) if not df_90.empty  else round(float(highs.max()), 2)
    l90  = round(float(df_90["low"].min()),   2) if not df_90.empty  else round(float(lows.min()),  2)

    rsi           = calc_rsi(closes)
    ma20          = calc_ma(closes, 20)
    ma50          = calc_ma(closes, 50)
    ma200         = calc_ma(closes, 200)
    macd, ms, mh  = calc_macd(closes)
    bbu, bbm, bbl = calc_bollinger(closes)
    sk, sd        = calc_stoch(closes, highs, lows)

    candles_250 = df.tail(250).copy()
    candles = [
        {
            "d": str(row["date"])[:10],
            "o": round(float(row["open"]),  2),
            "h": round(float(row["high"]),  2),
            "l": round(float(row["low"]),   2),
            "c": round(float(row["close"]), 2),
            "v": int(row["volume"]),
        }
        for _, row in candles_250.iterrows()
    ]

    return {
        "rsi":         rsi,
        "ma20":        ma20,
        "ma50":        ma50,
        "ma200":       ma200,
        "h90":         h90,
        "l90":         l90,
        "h52w":        h52w,
        "l52w":        l52w,
        "macd":        macd,
        "macd_signal": ms,
        "macd_hist":   mh,
        "bb_upper":    bbu,
        "bb_mid":      bbm,
        "bb_lower":    bbl,
        "stoch_k":     sk,
        "stoch_d":     sd,
        "last_close":  round(float(closes.iloc[-1]), 2),
        "last_date":   str(df["date"].iloc[-1])[:10],
        "n_candles":   len(df),
        "candles":     candles,
    }


def save_candle_file(ticker: str, df: pd.DataFrame, candles_dir: Path) -> None:
    candles_dir.mkdir(parents=True, exist_ok=True)
    candles = [
        {
            "d": str(row["date"])[:10],
            "o": round(float(row["open"]),  2),
            "h": round(float(row["high"]),  2),
            "l": round(float(row["low"]),   2),
            "c": round(float(row["close"]), 2),
            "v": int(row["volume"]),
        }
        for _, row in df.iterrows()
    ]
    out = candles_dir / f"{ticker}.json"
    out.write_text(json.dumps(candles, ensure_ascii=False), encoding="utf-8")


def run(tickers_filter: list[str] | None = None) -> dict:
    try:
        import BVCscrap  # noqa: F401
        bvcscrap_ok = True
    except ImportError:
        log.warning("BVCscrap non disponible — extension BVCscrap désactivée")
        bvcscrap_ok = False

    xlsx_tickers = {f.stem for f in XLSX_DIR.glob("*.xlsx")} if XLSX_DIR.exists() else set()
    all_tickers = sorted(xlsx_tickers | set(MANUAL_MAP.keys()))

    if tickers_filter:
        all_tickers = [t for t in all_tickers if t in tickers_filter]

    log.info(f"{len(all_tickers)} tickers à traiter")

    candles_dir = Path(__file__).parent / "candles"
    results: dict = {}

    for i, ticker in enumerate(all_tickers, 1):
        log.info(f"[{i}/{len(all_tickers)}] {ticker}")

        # Sources BRUTES → ajustement split immédiat, avant toute fusion avec
        # les candles stockées (qui sont, elles, déjà ajustées).
        xlsx_df = adjust_splits_df(ticker, load_xlsx(ticker))

        if bvcscrap_ok and ticker in MANUAL_MAP:
            name = MANUAL_MAP[ticker]
            if not xlsx_df.empty:
                last_date = xlsx_df["date"].iloc[-1]
            else:
                last_date = pd.Timestamp(datetime.now() - timedelta(days=31))
            ext_df = adjust_splits_df(ticker, fetch_bvcscrap_extension(name, last_date))
            df = combine(xlsx_df, ext_df)
            if not ext_df.empty:
                log.info(f"  +{len(ext_df)} bougies BVCscrap ajoutées")
        else:
            df = xlsx_df

        # Merge / base depuis le candle file existant.
        # Si df est vide (pas de XLSX, BVCscrap indisponible), on utilise le candle
        # file comme base — permet de débloquer les tickers sans XLSX.
        existing_path = candles_dir / f"{ticker}.json"
        if existing_path.exists():
            try:
                existing = json.loads(existing_path.read_text(encoding="utf-8"))
                if existing:
                    ex_df = pd.DataFrame(existing)
                    ex_df = ex_df.rename(columns={"d": "date", "o": "open", "h": "high",
                                                   "l": "low", "c": "close", "v": "volume"})
                    ex_df["date"] = pd.to_datetime(ex_df["date"], errors="coerce")
                    if "volume" not in ex_df.columns:
                        ex_df["volume"] = 0
                    for col in ["open", "high", "low", "close"]:
                        if col not in ex_df.columns:
                            ex_df[col] = ex_df.get("close", 0)
                    ex_df = ex_df[["date", "open", "high", "low", "close", "volume"]].copy()
                    ex_df["close"] = pd.to_numeric(ex_df["close"], errors="coerce")
                    if df.empty:
                        df = ex_df
                        log.info(f"  candle file utilisé comme base ({len(ex_df)} bougies)")
                    else:
                        newer = ex_df[ex_df["date"] > df["date"].iloc[-1]].copy()
                        if not newer.empty:
                            df = combine(df, newer)
                            log.info(f"  +{len(newer)} bougies préservées depuis candle file")
            except Exception:
                pass

        if df.empty or len(df) < 14:
            log.warning(f"  {ticker}: historique insuffisant ({len(df)} bougies) — ignoré")
            continue

        try:
            ind = compute_indicators(df)
            results[ticker] = ind
            log.info(
                f"  {len(df)} bougies → RSI={ind['rsi']} "
                f"MA20={ind['ma20']} MA50={ind['ma50']} "
                f"H52w={ind['h52w']} L52w={ind['l52w']}"
            )
            save_candle_file(ticker, df, candles_dir)
        except Exception as e:
            log.warning(f"  {ticker}: calcul indicateurs échoué: {e}")

        time.sleep(0.2)

    return results


# Champs qui décrivent la série elle-même, pas un indicateur.
_CHAMPS_SERIE = {"candles", "last_close", "last_date", "n_candles"}


def _purger_fantome(results: dict) -> None:
    """Retire la séance fantôme des chandelles ET des indicateurs, sur place.

    `seance.purger_seance_fantome()` nettoie les fichiers de chandelles ; les
    indicateurs, eux, viennent d'être calculés en mémoire sur la série avec le
    doublon. Les laisser tels quels décalerait les moyennes mobiles — MA20 d'ADH
    à 34,80 au lieu de 34,67, écart faible mais qui se propage au scoring.

    `n_candles` est décrémenté d'une séance et non recompté : il compte la série
    source complète, pas la liste stockée qui est tronquée à 250 points.
    """
    try:
        from seance import purger_seance_fantome
    except ImportError:
        from pipeline.seance import purger_seance_fantome

    date_fantome, n = purger_seance_fantome()
    if not date_fantome:
        return
    log.warning(f"Séance fantôme {date_fantome} : {n} fichiers de chandelles purgés")

    recales = 0
    for ticker, v in results.items():
        candles = v.get("candles")
        if not isinstance(candles, list) or not candles:
            continue
        gardees = [c for c in candles if c.get("d") != date_fantome]
        if len(gardees) == len(candles):
            continue
        df = pd.DataFrame([
            {"date": pd.Timestamp(c["d"]), "open": c["o"], "high": c["h"],
             "low": c["l"], "close": c["c"], "volume": c.get("v", 0)}
            for c in gardees
        ])
        try:
            indicateurs = compute_indicators(df)
        except Exception as e:
            log.warning(f"  {ticker}: recalcul indicateurs échoué après purge: {e}")
            continue
        # Ne recopier que les indicateurs. `compute_indicators` renvoie aussi
        # candles / last_close / last_date / n_candles, qui décrivent la série
        # tronquée à 250 points qu'il vient de construire — les laisser passer
        # ferait retomber n_candles de 784 à 249.
        for cle, val in indicateurs.items():
            if cle in v and cle not in _CHAMPS_SERIE:
                v[cle] = val
        v["candles"]    = gardees
        v["last_close"] = gardees[-1]["c"]
        v["last_date"]  = gardees[-1]["d"]
        v["n_candles"]  = max(0, v.get("n_candles", len(gardees)) - 1)
        recales += 1
    if recales:
        log.warning(f"Indicateurs recalculés sans le {date_fantome} : {recales} tickers")


def save(results: dict, out_path: Path) -> None:
    output = {
        "_updated": datetime.now(timezone.utc).isoformat(),
        "_source":  "xlsx 3ans + BVCscrap extension",
        "_tickers": len(results),
        **results,
    }
    out_path.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    log.info(f"Sauvegardé : {out_path} ({len(results)} tickers)")


def main() -> None:
    parser = argparse.ArgumentParser(description="Collecte historique BVCscrap")
    parser.add_argument("--tickers", type=str, default="",
                        help="Liste CSV de tickers (défaut: tous)")
    parser.add_argument("--dry-run", action="store_true",
                        help="N'écrit pas le fichier de sortie")
    args = parser.parse_args()

    tickers_filter = [t.strip().upper() for t in args.tickers.split(",") if t.strip()] or None

    results = run(tickers_filter=tickers_filter)

    if not results:
        log.error("Aucun résultat")
        sys.exit(1)

    # Séance fantôme : la source date parfois ses cours d'un jour où la Bourse
    # n'a pas ouvert. Le 14/08 (férié), la clôture du 13 est revenue estampillée
    # du 14 et s'est écrite ici comme partout ailleurs. Le contrôle ne peut se
    # faire qu'après coup, à l'échelle du marché : titre par titre, une clôture
    # inchangée d'une séance à l'autre est parfaitement banale.
    _purger_fantome(results)

    log.info(f"Résultats : {len(results)} tickers traités")
    missing = [t for t in MANUAL_MAP if t not in results]
    if missing:
        log.info(f"Manquants MANUAL_MAP : {missing}")

    if not args.dry_run:
        try:
            out = Path(__file__).parent / "historical_data.json"
        except NameError:
            out = Path("pipeline/historical_data.json")
        save(results, out)
        print(f"\nFichier : {out}")
    else:
        log.info("[dry-run] Aucune écriture")
        for t, v in sorted(results.items()):
            print(f"  {t:6s}: RSI={v['rsi']:5.1f} MA20={v['ma20']:8.2f} MA50={v['ma50']:8.2f} "
                  f"n={v['n_candles']}")


if __name__ == "__main__":
    main()
