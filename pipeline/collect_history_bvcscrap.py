#!/usr/bin/env python3
import sys, json, math, time, argparse, logging
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


# ── GARDE-FOU D'IDENTITÉ ────────────────────────────────────────────────────
# ⚠️ Ajouté après qu'un titre eut porté cinq semaines durant les cours d'une
# AUTRE société sans qu'aucun contrôle ne s'en aperçoive. Les cours reçus
# étaient valides : invariant OHLC respecté, variation dans les limites, série
# continue. Ils appartenaient simplement à quelqu'un d'autre.
#
# Le garde-fou refuse l'ÉCRITURE quand l'identité n'est pas établie. Il
# n'empêche pas d'interroger la source ni d'examiner ce qu'elle renvoie.
try:
    from identites import autoriser_ecriture
except ImportError:                                   # exécution hors paquet
    import sys as _sys
    from pathlib import Path as _Path
    _sys.path.insert(0, str(_Path(__file__).resolve().parent))
    from identites import autoriser_ecriture


try:
    from identites import source_utilisable
except ImportError:
    import sys as _sys3
    from pathlib import Path as _Path3
    _sys3.path.insert(0, str(_Path3(__file__).resolve().parent))
    from identites import source_utilisable

try:
    from contamination import indicateurs_permis, usage_permis
except ImportError:                                   # exécution hors paquet
    import sys as _sys2
    from pathlib import Path as _Path2
    _sys2.path.insert(0, str(_Path2(__file__).resolve().parent))
    from contamination import indicateurs_permis, usage_permis


SOURCES_DIR = Path(__file__).resolve().parent.parent / "sources"


def load_export(ticker: str) -> tuple:
    """L'export de l'opérateur : les cours ET leur identité, dans la même ligne.

    ⚠️ C'EST LE POINT QUE LA REVUE A RELEVÉ, ET IL EST STRUCTUREL.
    Lire l'identité dans un fichier et les cours dans un autre ne prouve rien :
    c'est la configuration même de juin, où `MANUAL_MAP` nommait « Mutandis »
    et une autre source livrait les cours. Ici, les deux viennent des mêmes
    lignes — si la ligne ment sur l'instrument, elle ment à côté de son prix.

    Rend `(DataFrame, nom d'instrument)`. Rend `(vide, None)` s'il n'y a pas
    d'export, ou si son identité n'est pas constante sur toutes les lignes de
    cours : dans ce cas rien n'est importé, plutôt qu'importé sans garantie.
    """
    dossier = SOURCES_DIR / ticker
    fichiers = sorted(dossier.glob("*.csv")) if dossier.exists() else []
    if not fichiers:
        return pd.DataFrame(), None
    try:
        from identite_source import identite_de_l_export
        from importer_export import importer
    except ImportError:
        return pd.DataFrame(), None

    chemin = fichiers[-1]
    lu = identite_de_l_export(chemin)
    if not lu["identite_portee"]:
        log.warning(f"  {ticker}: export écarté — {lu['motif']}")
        return pd.DataFrame(), None

    brut = importer(chemin, ticker)
    lignes = []
    for o in brut["observations"]:
        # ⚠️ Une observation sans clôture n'est pas une bougie à zéro : elle
        # n'est pas une bougie. On ne comble rien.
        if o.get("cloture") is None:
            continue
        c = o["cloture"]
        lignes.append({
            "date": o["date"],
            "open":  o["ouverture"] if o.get("ouverture") is not None else c,
            "high":  o["plus_haut"] if o.get("plus_haut") is not None else c,
            "low":   o["plus_bas"]  if o.get("plus_bas")  is not None else c,
            "close": c,
            # ⚠️ « Titres Échangés », jamais « Volume (MAD) ». Les deux
            # colonnes existent et ne disent pas la même chose.
            "volume": int(o["titres_echanges"] or 0),
        })
    if not lignes:
        return pd.DataFrame(), None
    df = pd.DataFrame(lignes)
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.dropna(subset=["date"]).sort_values("date").reset_index(drop=True)
    log.info(f"  {ticker}: {len(df)} bougies depuis l'export « {chemin.name} » "
             f"— identité portée : « {lu['instrument']} »")
    return df, lu["instrument"]


def ecriture_autorisee(ticker: str, identite_recue: str | None = None) -> dict:
    """À appeler AVANT d'écrire l'historique d'un titre.

    `identite_recue` est le nom ou le code que la source a réellement renvoyé.
    Sans lui, l'écriture est refusée : une table cohérente avec elle-même peut
    être fausse, et c'est précisément ce qui s'est produit.
    """
    return autoriser_ecriture(ticker, identite_recue)


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


# ⚠️ COPIE CONFORME DE `update_data.py::calc_rsi`.
# C'est CE calc_rsi-ci qui produit les RSI de `historical_data.json`, et
# c'est ce cache que le moteur publié sert pour 73 titres sur 74. Corriger
# la fonction de `update_data.py` seule n'aurait donc changé presque aucune
# valeur affichée. Les deux exemplaires doivent rester identiques :
# `tests/test_rsi_wilder_publie.py` les confronte sur une batterie de séries
# et refuse toute divergence.
def calc_rsi(closes: pd.Series, period: int = 14):
    """RSI de Wilder — amorçage par moyenne arithmétique, limites définies.

    ⚠️ DEUX DÉFAUTS REPRODUITS PAR LA REVUE DU 12/09, CORRIGÉS ICI.

    1. **Une hausse continue rendait `nan` au lieu de 100.**
       `ema_down.replace(0, np.nan)` transformait l'absence de baisse — qui est
       la DÉFINITION du RSI à 100 — en valeur indéfinie. Un `nan` traverse
       ensuite `calc_score_tech` sans déclencher aucune branche : le titre
       recevait le score neutre, en silence.

    2. **L'amorçage n'était pas celui de Wilder.**
       `ewm(com=period-1, adjust=False)` démarre le lissage sur la PREMIÈRE
       variation, ce qui laisse la série s'en souvenir longtemps. Wilder amorce
       par la MOYENNE ARITHMÉTIQUE des `period` premières variations, puis
       lisse. Sur les quinze clôtures alternées
       [100, 101, 100, … 101, 100], l'ancienne forme rendait 66,5 ; la
       définition en rend 50 — autant de hausses que de baisses, de même
       amplitude.

    AMORÇAGE ET LONGUEUR MINIMALE, DÉCLARÉS
    ───────────────────────────────────────
      · `period` variations sont nécessaires pour l'amorçage, donc
        **`period + 1` clôtures** au minimum — QUINZE pour un RSI(14).
      · en deçà, la fonction rend `None`. ⚠️ Pas 50 : un RSI absent n'est pas
        un RSI neutre, et le faire passer pour neutre revient à inventer une
        mesure.

    LIMITES, QUI DÉCOULENT DE LA DÉFINITION
    ───────────────────────────────────────
      · aucune baisse et au moins une hausse → RS infini → **100**
      · aucune hausse et au moins une baisse → RS nul    → **0**
      · ni hausse ni baisse (série plate)    → indéterminé → **50**, et c'est
        le seul cas où 50 est produit par le calcul lui-même.
    """
    # ⚠️ AUCUN FILTRAGE SILENCIEUX, ET LA DATE DU RÉSULTAT EST TENUE.
    # Ma première version écartait les valeurs absentes avant de calculer.
    # Conséquence : une série terminée par une absence rendait un RSI daté de
    # la séance PRÉCÉDENTE, présenté comme celui de la dernière — et une série
    # croissante terminée par `None` pouvait ainsi rendre 100. Le trou était
    # refermé sans que personne le sache.
    #
    # Le lissage de Wilder est RÉCURSIF : un trou au milieu propage sa
    # correction jusqu'au bout. Une série percée ne donne donc pas « un RSI
    # approximatif », elle donne un RSI d'une autre série.
    #
    # POLITIQUE DES VALEURS ABSENTES : la fonction REFUSE. Elle ne comble pas,
    # ne saute pas, ne rapproche pas. Le résultat porte toujours sur la
    # DERNIÈRE clôture de la série reçue, jamais sur une antérieure.
    brut = closes.tolist()
    if any(x is None or pd.isna(x) for x in brut):
        return None
    try:
        vals = [float(x) for x in brut]
    except (TypeError, ValueError):
        return None
    # ⚠️ FINITUDE. `+inf` traverse `pd.isna` sans être signalé et contamine
    # toute la récurrence : une moyenne infinie rend le RSI indéfini, ou 100
    # par accident. Un infini n'est pas un cours.
    if not all(math.isfinite(v) for v in vals):
        return None
    if len(vals) < period + 1:
        return None

    variations = [vals[i] - vals[i - 1] for i in range(1, len(vals))]
    gains = [max(d, 0.0) for d in variations]
    pertes = [max(-d, 0.0) for d in variations]

    # Amorçage de Wilder : moyenne arithmétique des `period` premières.
    mg = sum(gains[:period]) / period
    mp = sum(pertes[:period]) / period
    # Puis lissage : moyenne = (précédente × (period − 1) + courante) / period.
    for i in range(period, len(variations)):
        mg = (mg * (period - 1) + gains[i]) / period
        mp = (mp * (period - 1) + pertes[i]) / period

    if mp == 0:
        return 100.0 if mg > 0 else 50.0
    if mg == 0:
        return 0.0
    return round(100.0 - 100.0 / (1.0 + mg / mp), 1)

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


def run(tickers_filter: list[str] | None = None,
        identites_recues: dict | None = None,
        rendre_refus: bool = False,
        candles_dir: Path | None = None):
    """Collecte l'historique. ⚠️ N'écrit que les identités ÉTABLIES.

    `identites_recues` : le nom ou le code que la SOURCE a réellement renvoyé,
    ticker par ticker. Sans lui, l'écriture est refusée — une table cohérente
    avec elle-même peut être fausse, et elle l'était.
    """
    identites_recues = identites_recues or {}
    refus: dict = {}
    return _run(tickers_filter, identites_recues, refus, rendre_refus, candles_dir)


def _run(tickers_filter, identites_recues, refus, rendre_refus, candles_dir=None):
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

    # ⚠️ Paramétrable : un test qui écrirait dans pipeline/candles/ abîmerait
    # le dépôt qu'il est censé protéger.
    candles_dir = candles_dir or (Path(__file__).parent / "candles")
    results: dict = {}

    for i, ticker in enumerate(all_tickers, 1):
        log.info(f"[{i}/{len(all_tickers)}] {ticker}")

        # ── CHAQUE CONTRIBUTION PROUVE SON IDENTITÉ, OU N'ENTRE PAS ────────
        #
        # ⚠️ DÉFAUT RELEVÉ PAR LA REVUE. Le garde-fou consultait un dictionnaire
        # d'identités fourni de l'extérieur : il démontrait que la décision
        # était appliquée, pas que l'identité contrôlée venait de la MÊME
        # réponse que les cours. Et une identité donnée « pour le titre »
        # blanchirait toutes les contributions fusionnées sous elle.
        #
        # Les deux sources de ce programme sont aujourd'hui INCAPABLES de
        # prouver ce qu'elles renvoient — l'XLSX est nommé d'après notre propre
        # ticker, et la bibliothèque est interrogée par nom sans rien rendre
        # qui identifie l'instrument. Elles sont donc explicitement désactivées.
        # L'export de l'opérateur, quand il existe, est la SEULE source qui
        # porte son identité. On ne fusionne alors RIEN d'autre sous elle :
        # une identité prouvée pour un fichier ne blanchit pas les lignes d'un
        # autre. Mieux vaut un historique plus court que nommé par hypothèse.
        export_df, identite_export = load_export(ticker)
        if identite_export:
            identites_recues = {**identites_recues, ticker: identite_export}

        etats_sources = {n: source_utilisable(n)
                         for n in ("xlsx_local", "bvcscrap_extension")}
        inutilisables = [e for e in etats_sources.values() if not e["utilisable"]]
        if inutilisables and not identites_recues.get(ticker):
            motifs = " · ".join(f"{e['source']} : {e['motif']}"
                                for e in inutilisables)
            log.warning(f"  {ticker}: SOURCES DÉSACTIVÉES — {motifs}")
            refus[ticker] = {"autorise": False, "ticker": ticker,
                             "motif": "aucune source ne peut prouver son "
                                      "identité pour ce titre",
                             "sources": etats_sources}
            continue

        # Sources BRUTES → ajustement split immédiat, avant toute fusion avec
        # les candles stockées (qui sont, elles, déjà ajustées).
        if identite_export:
            df = adjust_splits_df(ticker, export_df)
            xlsx_df = df
        else:
            xlsx_df = adjust_splits_df(ticker, load_xlsx(ticker))

        if identite_export:
            pass                      # aucune fusion : voir ci-dessus
        elif bvcscrap_ok and ticker in MANUAL_MAP:
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
        if existing_path.exists() and not identite_export:
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

        # ── GARDE-FOU D'IDENTITÉ — AVANT tout calcul et toute écriture ─────
        #
        # ⚠️ DÉFAUT CORRIGÉ, RELEVÉ PAR LA REVUE. Le garde-fou existait mais
        # n'était appelé de nulle part : `run()` allait jusqu'à l'écriture sans
        # jamais le consulter. Éprouvé en externe — zéro appel, trois fichiers
        # créés, indicateurs renvoyés pour les trois. Une promesse non branchée
        # ne protège rien, et les tests qui interrogeaient la fonction sans
        # lancer le parcours ne pouvaient pas s'en apercevoir.
        #
        # Le contrôle est ici, au seul endroit qui compte : entre la donnée
        # assemblée et son entrée dans les séries et les résultats.
        verdict = ecriture_autorisee(ticker, identites_recues.get(ticker))
        if not verdict["autorise"]:
            log.warning(f"  {ticker}: ÉCRITURE REFUSÉE — {verdict['motif']}")
            refus[ticker] = verdict
            # ⚠️ Ni indicateur, ni fichier. Ce qui existait déjà reste INTACT :
            # un import refusé ne doit pas détruire des données antérieures
            # valides.
            continue

        # ── Contamination : INDICATEUR PAR INDICATEUR ─────────────────────
        #
        # ⚠️ DÉFAUT RELEVÉ PAR LA REVUE. On passait TOUTES les dates de la série
        # au contrôle, si bien qu'une observation suspecte de juin refusait une
        # moyenne sur vingt clôtures de juillet — qui ne la touche jamais. Le
        # refus était prudent pour ce qui consomme l'ancienne observation, trop
        # large pour tout le reste.
        #
        # Chaque indicateur déclare la profondeur qu'il lit, amorçage compris.
        # Ceux qui atteignent une date contaminée sont retirés ; les autres
        # restent. ⚠️ On ne supprime JAMAIS les anciennes lignes pour
        # « nettoyer » : cela changerait les valeurs sans le dire.
        dates_utilisees = [str(d)[:10] for d in df["date"].tolist()]
        tri = indicateurs_permis(ticker, dates_utilisees)

        try:
            ind = compute_indicators(df)
            if tri["refuses"]:
                log.warning(
                    f"  {ticker}: {len(tri['refuses'])} indicateur(s) retiré(s) "
                    f"— fenêtre contaminée : {', '.join(sorted(tri['refuses']))}")
                for nom in tri["refuses"]:
                    ind.pop(nom, None)
                ind["_indicateurs_retires"] = tri["refuses"]
                ind["_pourquoi"] = (
                    "ces indicateurs lisent une fenêtre où le titre pourrait "
                    "porter les cours d'une autre société. Les valeurs y sont "
                    "bien formées : c'est leur APPARTENANCE qui est en cause.")
                refus.setdefault(ticker, {
                    "autorise": True, "ticker": ticker, "partiel": True,
                    "motif": "indicateurs partiellement retirés",
                    "indicateurs_retires": sorted(tri["refuses"])})
            results[ticker] = ind
            # ⚠️ Le journal ne peut pas citer un indicateur retiré : il lit
            # donc ce qui reste, et dit combien manquent.
            log.info(
                f"  {len(df)} bougies → RSI={ind.get('rsi', '—')} "
                f"MA20={ind.get('ma20', '—')} MA50={ind.get('ma50', '—')} "
                f"H52w={ind.get('h52w', '—')} L52w={ind.get('l52w', '—')}"
                + (f" · {len(tri['refuses'])} retiré(s)" if tri["refuses"] else "")
            )
            save_candle_file(ticker, df, candles_dir)
        except Exception as e:
            log.warning(f"  {ticker}: calcul indicateurs échoué: {e}")

        time.sleep(0.2)

    if refus:
        log.warning(f"{len(refus)} titre(s) refusé(s) à l'écriture : "
                    f"{', '.join(sorted(refus))}")
    if rendre_refus:
        return results, refus
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
        from seance import purger_seance_fantome, purger_suspensions
    except ImportError:
        from pipeline.seance import purger_seance_fantome

    date_fantome, n = purger_seance_fantome()
    # ⚠️ Ce programme réécrit historical_data.json DEPUIS LA SOURCE : il
    # ignore le registre des suspensions et ramenait les séances fantômes
    # que le nettoyage précédent avait retirées. Le balayage les reprend.
    _ns, _fs = purger_suspensions()
    if _ns:
        print(f"  Suspensions : {_ns} bougie(s) retirée(s) de {_fs} fichier(s)")
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


def save(results: dict, out_path: Path, refus: dict | None = None) -> None:
    """Écrit le cache commun SANS effacer ce qui n'a pas été réimporté.

    ⚠️ DÉFAUT RELEVÉ PAR LA REVUE. Cette fonction remplaçait le fichier entier
    par les seuls résultats du run. Un titre refusé à l'import DISPARAISSAIT
    donc du cache — le fichier individuel de chandelles était bien préservé,
    mais l'entrée commune s'évaporait. Contre-épreuve de la revue : cache
    contenant MSA et CDM, import de MSA accepté, import de CDM refusé,
    sauvegarde → CDM disparu.

    ⚠️ DEUX DÉCISIONS DISTINCTES, ET IL NE FAUT PAS LES CONFONDRE :
      · CONSERVER une donnée ancienne — un refus d'import ne doit rien effacer ;
      · AUTORISER SA RÉUTILISATION — une donnée reconnue contaminée reste
        lisible, mais porte la marque qui l'écarte des calculs concernés.
    Effacer reviendrait à perdre la trace ; réutiliser en silence reviendrait à
    propager le défaut. On garde, et on marque.
    """
    refus = refus or {}
    ancien: dict = {}
    if out_path.exists():
        try:
            ancien = json.loads(out_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            log.warning(f"cache illisible ({e}) — il ne sera pas fusionné, "
                        f"et RIEN n'est écrasé tant qu'on ne sait pas lire")
            raise

    conserves = {k: v for k, v in ancien.items()
                 if not k.startswith("_") and k not in results}

    # ⚠️ Marquer, jamais supprimer. L'entrée reste, sa réutilisation non.
    for t in list(conserves):
        if t in refus:
            conserves[t] = dict(conserves[t]) if isinstance(conserves[t], dict) \
                else {"_valeur": conserves[t]}
            conserves[t]["_reimport_refuse"] = {
                "le": datetime.now(timezone.utc).isoformat(),
                "motif": refus[t].get("motif"),
                "_lecture": "donnée ANCIENNE conservée. Le réimport a été "
                            "refusé ; cette entrée n'a pas été rafraîchie et "
                            "ne doit pas être lue comme récente.",
            }

    output = {
        "_updated": datetime.now(timezone.utc).isoformat(),
        "_source":  "xlsx 3ans + BVCscrap extension",
        "_tickers": len(results) + len(conserves),
        "_importes_ce_run": sorted(results),
        "_conserves_sans_reimport": sorted(conserves),
        "_refuses_ce_run": sorted(refus),
        "_politique": "un refus d'import ne supprime AUCUNE donnée ancienne. "
                      "Conserver un fichier et autoriser sa réutilisation sont "
                      "deux décisions distinctes.",
        **conserves,
        **results,
    }
    out_path.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    log.info(f"Sauvegardé : {out_path} — {len(results)} importé(s), "
             f"{len(conserves)} conservé(s) sans réimport")


def main() -> None:
    parser = argparse.ArgumentParser(description="Collecte historique BVCscrap")
    parser.add_argument("--tickers", type=str, default="",
                        help="Liste CSV de tickers (défaut: tous)")
    parser.add_argument("--dry-run", action="store_true",
                        help="N'écrit pas le fichier de sortie")
    args = parser.parse_args()

    tickers_filter = [t.strip().upper() for t in args.tickers.split(",") if t.strip()] or None

    # ⚠️ L'IDENTITÉ VIENT DES DONNÉES IMPORTÉES, PAS DE NOTRE TABLE.
    # `MANUAL_MAP` nomme les sociétés depuis NOTRE dépôt : s'en servir pour
    # vérifier l'identité reviendrait à confronter la table à elle-même —
    # c'est exactement ce qui a laissé passer « MSA = Mutandis » en juin.
    # Seuls les exports de l'opérateur portent une colonne d'identité SUR LA
    # LIGNE DU COURS. Les titres qui n'en ont pas restent sans identité, et
    # le collecteur refusera de les écrire. Un refus large est assumé : nous
    # ne savons pas nommer ce que nous importons.
    try:
        from identite_source import pour_le_collecteur
        identites = pour_le_collecteur()
    except ImportError:
        identites = {}
    if identites:
        log.info(f"Identité portée par la source pour {len(identites)} titre(s) : "
                 f"{', '.join(sorted(identites))}")
    else:
        log.warning("Aucune source ne porte d'identité — le run refusera "
                    "chaque titre. Voir identites.SOURCES.")

    results = run(tickers_filter=tickers_filter, identites_recues=identites)

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
