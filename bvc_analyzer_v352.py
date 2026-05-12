# ============================================================
# BVC ULTIMATE ANALYZER v3.5.2 PRO
# Medias24 + GitHub + Risk + Liquidity + Graphiques + Backtest + PDF + News
# Correctifs v3.5.2 :
#   - SOT ISIN historique restauré (MA0000012502)
#   - Split appliqué une seule fois (dans analyze uniquement)
#   - PDF rattaché au ticker via PDF_TICKER_MAP
#   - Double ajustement split supprimé
# Correctifs v3.5.2.1 :
#   ✅ ChartEngine : split_date converti en string pour add_vline (fix pandas 2.x)
#   ✅ NoteGenerator : red flags triés par sévérité (CRITIQUE → ELEVEE → MOYENNE → FAIBLE)
# ============================================================

import sys, subprocess, os, re, json, warnings, logging
from pathlib import Path
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Any, Optional

def auto_install(pkg, pip_name=None):
    try:
        __import__(pkg)
    except ImportError:
        subprocess.check_call([sys.executable, "-m", "pip", "install", pip_name or pkg, "-q"])

for pkg, pip_name in [
    ("requests",   "requests"),
    ("pandas",     "pandas"),
    ("numpy",      "numpy"),
    ("openpyxl",   "openpyxl"),
    ("bs4",        "beautifulsoup4"),
    ("pdfplumber", "pdfplumber"),
    ("plotly",     "plotly"),
]:
    auto_install(pkg, pip_name)

import requests
import pandas as pd
import numpy as np
import pdfplumber
from bs4 import BeautifulSoup
import plotly.graph_objects as go
from plotly.subplots import make_subplots

try:
    from zoneinfo import ZoneInfo
    TZ_CASABLANCA = ZoneInfo("Africa/Casablanca")
except Exception:
    TZ_CASABLANCA = None

warnings.filterwarnings("ignore")
VERSION = "v3.5.2 PRO"

GITHUB_URL     = "https://raw.githubusercontent.com/abdmoutalib207-lang/-bvc-analyzer/main/fondamentaux.json"
MEDIAS24_API   = "https://medias24.com/content/api"
BOURSENEWS_URL = "https://www.boursenews.ma"

BUY_FEE  = 0.01
SELL_FEE = 0.01
TAX_RATE = 0.15

for folder in ["data/historique", "exports", "charts", "logs"]:
    Path(folder).mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(message)s",
    datefmt="%H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("logs/bvc_v352.log", encoding="utf-8")
    ]
)
logger = logging.getLogger("BVC")

# ============================================================
# ISIN MAP — SOT = ancien ISIN historique MA0000012502
# ============================================================

ISIN_MAP = {
    "ADH":  "MA0000011512", "AFM":  "MA0000012296", "AFI":  "MA0000012114",
    "GAZ":  "MA0000010951", "AGM":  "MA0000010944", "AKD":  "MA0000012585",
    "ADI":  "MA0000011819", "ALU":  "MA0000010936", "ARD":  "MA0000012460",
    "ATL":  "MA0000011710", "ATW":  "MA0000012445", "HAL":  "MA0000010969",
    "NEJ":  "MA0000011009", "BAL":  "MA0000011991", "BOA":  "MA0000012437",
    "BCP":  "MA0000011884", "BMC":  "MA0000010811", "CAR":  "MA0000011868",
    "CDM":  "MA0000010381", "CIH":  "MA0000011454", "CIM":  "MA0000010506",
    "CMT":  "MA0000011793", "COL":  "MA0000011934", "CSR":  "MA0000012247",
    "CTM":  "MA0000010340", "DAR":  "MA0000011421", "DHO":  "MA0000011850",
    "DTT":  "MA0000012536", "DSW":  "MA0000011637", "ENK":  "MA0000011942",
    "EQD":  "MA0000010357", "FNB":  "MA0000011587", "HPS":  "MA0000011611",
    "IBM":  "MA0000011132", "IMI":  "MA0000012387", "INV":  "MA0000011579",
    "JET":  "MA0000012080", "LBV":  "MA0000011801", "LHM":  "MA0000012320",
    "LES":  "MA0000012031", "M2M":  "MA0000011678", "MOX":  "MA0000010985",
    "MGL":  "MA0000011215", "MNG":  "MA0000011058", "MRL":  "MA0000010035",
    "IAM":  "MA0000011488", "MIC":  "MA0000012163", "MUT":  "MA0000012395",
    "OUL":  "MA0000010415", "PPM":  "MA0000011660", "REB":  "MA0000010993",
    "RDS":  "MA0000012239", "RIS":  "MA0000011462", "S2M":  "MA0000012106",
    "SLM":  "MA0000012007", "SAF":  "MA0000011744", "SMI":  "MA0000010068",
    "STK":  "MA0000011843", "SNP":  "MA0000011728", "MSA":  "MA0000012312",
    "SON":  "MA0000010019",
    "SOT":  "MA0000012502",   # ← ISIN historique — NE PAS CHANGER
    "SRM":  "MA0000011595", "SBS":  "MA0000010365", "STR":  "MA0000012056",
    "TQA":  "MA0000012205", "TGC":  "MA0000012528", "TIM":  "MA0000011686",
    "TMA":  "MA0000012262", "UNI":  "MA0000012023", "WAF":  "MA0000010928",
    "ZLD":  "MA0000010571", "CFGB": "MA0000012627", "CMGP": "MA0000012718",
    "VCNE": "MA0000012759", "CASH": "MA0000012767", "SGTM": "MA0000012783",
}

TICKERS_DEFAUT = [
    "SMI", "MNG", "RIS", "RDS", "CSR", "SOT",
    "ADI", "MSA", "ADH", "TGC", "CMT", "SRM",
    "CFGB", "CMGP", "VCNE", "CASH", "SGTM"
]

# ============================================================
# CORPORATE ACTIONS OFFICIELLES
# ============================================================

OFFICIAL_SPLITS = {
    "SOT": {
        "date":            "2026-05-05",
        "ratio":           5,
        "old_isin":        "MA0000012502",
        "new_isin":        "MA0000012833",
        "label":           "Split officiel SOTHEMA 5:1",
        "source":          "Avis BVC AV-2026-033",
        "neutralize_days": 5
    }
}

# Rattachement PDF → tickers autorisés
# Clé = nom de fichier (basename), valeur = liste de tickers autorisés
PDF_TICKER_MAP: Dict[str, List[str]] = {
    # Exemple : "av-2026-033_fr.pdf": ["SOT"]
}

# ============================================================
# UTILITAIRES
# ============================================================

class MarketCalendar:
    @staticmethod
    def now():
        if TZ_CASABLANCA:
            return datetime.now(TZ_CASABLANCA)
        return datetime.utcnow() + timedelta(hours=1)

    @staticmethod
    def status():
        now = MarketCalendar.now()
        if now.weekday() >= 5:
            return "WEEKEND"
        open_t  = now.replace(hour=9,  minute=30, second=0, microsecond=0)
        close_t = now.replace(hour=15, minute=30, second=0, microsecond=0)
        post_t  = now.replace(hour=15, minute=45, second=0, microsecond=0)
        if now < open_t:             return "PRE_MARKET"
        if open_t <= now <= close_t: return "OPEN"
        if close_t < now <= post_t:  return "POST_CLOSE"
        return "CLOSED"

    @staticmethod
    def message():
        h = MarketCalendar.now().strftime("%H:%M")
        return {
            "OPEN":       f"Marché OUVERT | Casablanca : {h}",
            "POST_CLOSE": f"Post-clôture | Casablanca : {h}",
            "PRE_MARKET": f"Avant ouverture | Casablanca : {h}",
            "WEEKEND":    f"Weekend | Casablanca : {h}",
            "CLOSED":     f"Marché fermé | Casablanca : {h}",
        }.get(MarketCalendar.status(), f"Casablanca : {h}")


class SafeMath:
    @staticmethod
    def to_float(x):
        if x is None or isinstance(x, (list, dict, tuple)):
            return np.nan
        try:
            if pd.isna(x):
                return np.nan
        except Exception:
            pass
        if isinstance(x, str):
            x = x.replace("\xa0"," ").replace(" ","").replace(",",".").replace("%","").replace("DH","").replace("MAD","").strip()
            if x in ["","-","N/A","nan","None","null"]:
                return np.nan
        try:
            return float(x)
        except Exception:
            return np.nan

    @staticmethod
    def last(s):
        s = pd.Series(s).dropna()
        return s.iloc[-1] if len(s) else np.nan

    @staticmethod
    def prev(s, n=2):
        s = pd.Series(s).dropna()
        return s.iloc[-n] if len(s) >= n else np.nan

    @staticmethod
    def pct(a, b):
        a, b = SafeMath.to_float(a), SafeMath.to_float(b)
        if pd.isna(a) or pd.isna(b) or b == 0:
            return np.nan
        return round((a/b - 1)*100, 2)

# ============================================================
# STRUCTURES
# ============================================================

class Signal(Enum):
    ACHETER    = "ACHETER"
    ACCUMULER  = "ACCUMULER"
    SURVEILLER = "SURVEILLER"
    ATTENDRE   = "ATTENDRE"
    EVITER     = "EVITER"

class Setup(Enum):
    MOMENTUM     = "MOMENTUM CONFIRMÉ"
    BREAKOUT     = "BREAKOUT POTENTIEL"
    PULLBACK     = "PULLBACK HAUSSIER"
    CONTRARIEN   = "CONTRARIEN"
    ACCUMULATION = "ACCUMULATION LENTE"
    FAIBLESSE    = "FAIBLESSE"
    NEUTRE       = "NEUTRE"

class Severity(Enum):
    CRITIQUE = "CRITIQUE"
    ELEVEE   = "ELEVEE"
    MOYENNE  = "MOYENNE"
    FAIBLE   = "FAIBLE"

# Ordre de sévérité pour tri dans la note — doit être défini après Severity
_SEV_ORDER = {Severity.CRITIQUE: 0, Severity.ELEVEE: 1, Severity.MOYENNE: 2, Severity.FAIBLE: 3}

@dataclass
class RedFlag:
    severity: Severity
    category: str
    message: str
    is_blocking: bool = False

@dataclass
class ScoreResult:
    score: float
    max_score: float
    reasons: List[str]
    raw_details: Dict[str, Any] = field(default_factory=dict)

    @property
    def normalized(self):
        return round(min(10, self.score/self.max_score*10), 2) if self.max_score else 0

@dataclass
class Valuation:
    base: Optional[float]; bull: Optional[float]; bear: Optional[float]
    upside_base: Optional[float]; upside_bull: Optional[float]
    downside: Optional[float]; premium_pct: Optional[float]
    methodology: str; confidence: str

@dataclass
class AnalysisResult:
    ticker: str; price: float; date: datetime
    setup: Setup; signal: Signal; action: str
    score_technical: ScoreResult; score_fundamental: ScoreResult
    score_liquidity: ScoreResult; score_risk: ScoreResult
    score_global: float; red_flags: List[RedFlag]
    valuation: Valuation
    technical_data: Dict[str, Any]; fundamental_data: Dict[str, Any]
    live_data: Dict[str, Any]; market_status: str
    corporate_actions: List[str]; backtest: Dict[str, Any]
    news: List[Dict[str, str]]; pdf_summary: str
    chart_file: str; export_detail_file: str
    note: str = ""

# ============================================================
# CORPORATE ACTION ENGINE — appliqué UNE SEULE FOIS dans analyze()
# ============================================================

class CorporateActionEngine:
    @staticmethod
    def apply_official_splits(df: pd.DataFrame, ticker: str):
        """
        Applique les splits officiels sur la série historique.
        Appelé UNE SEULE FOIS dans BVCAnalyzer.analyze().
        NE PAS appeler dans get_history().
        """
        df = df.copy()
        actions = []

        if ticker not in OFFICIAL_SPLITS:
            df["corporate_action"]   = ""
            df["post_split_window"]  = False
            return df, actions

        info        = OFFICIAL_SPLITS[ticker]
        split_date  = pd.to_datetime(info["date"])
        ratio       = float(info["ratio"])
        neutralize  = int(info.get("neutralize_days", 5))

        df["date"]  = pd.to_datetime(df["date"], errors="coerce")
        before      = df["date"] < split_date

        for col in ["open","high","low","close"]:
            if col in df.columns:
                df.loc[before, col] = df.loc[before, col] / ratio

        if "volume" in df.columns:
            df.loc[before, "volume"] = df.loc[before, "volume"] * ratio

        df["corporate_action"] = ""
        df.loc[df["date"] >= split_date, "corporate_action"] = f"SPLIT {int(ratio)}:1"

        end_neutral = split_date + pd.Timedelta(days=neutralize + 3)
        df["post_split_window"] = (df["date"] >= split_date) & (df["date"] <= end_neutral)

        actions.append(
            f"SPLIT officiel {ticker} | {int(ratio)}:1 | effet {split_date.date()} | "
            f"ancien ISIN {info.get('old_isin','N/A')} → nouvel ISIN {info.get('new_isin','N/A')} | "
            f"historique ajusté"
        )
        logger.info(actions[-1])
        return df, actions

# ============================================================
# CONNECTEUR MEDIAS24 — get_history() sans split
# ============================================================

class Medias24Connector:
    def __init__(self, isin_map):
        self.isin_map  = isin_map
        self.available = False
        self.checked   = False

    def _get(self, params, timeout=12):
        try:
            r = requests.get(
                MEDIAS24_API,
                params={**params, "format": "json"},
                headers={"User-Agent": "Mozilla/5.0"},
                timeout=timeout
            )
            if r.status_code == 200 and len(r.text) > 20:
                return r.json()
        except Exception as e:
            logger.debug(f"Medias24 : {e}")
        return None

    def preload(self):
        if self.checked:
            return self.available
        self.checked = True
        test = self._get({"method": "getStockInfo", "ISIN": "MA0000010068"})
        self.available = bool(test and test.get("result"))
        logger.info("Medias24 disponible" if self.available else "Medias24 indisponible")
        return self.available

    def get_history(self, ticker: str, days: int = 730) -> pd.DataFrame:
        """
        Récupère l'historique brut depuis Medias24.
        PAS de split ici — le split est appliqué dans analyze().
        """
        isin = self.isin_map.get(ticker.upper())
        if not isin:
            logger.warning(f"{ticker} : ISIN introuvable")
            return pd.DataFrame()

        end   = MarketCalendar.now().strftime("%Y-%m-%d")
        start = (MarketCalendar.now() - timedelta(days=days)).strftime("%Y-%m-%d")

        data = self._get({"method": "getPriceHistory", "ISIN": isin, "from": start, "to": end})
        if not data or not data.get("result"):
            return pd.DataFrame()

        records = data["result"]
        df = pd.DataFrame({
            "date":   [r.get("date")                          for r in records],
            "close":  [SafeMath.to_float(r.get("value"))      for r in records],
            "high":   [SafeMath.to_float(r.get("max"))        for r in records],
            "low":    [SafeMath.to_float(r.get("min"))        for r in records],
            "volume": [SafeMath.to_float(r.get("volume", 0))  for r in records],
        })

        df["date"]  = pd.to_datetime(df["date"], dayfirst=True, errors="coerce")
        df["open"]  = df["close"].shift(1).fillna(df["close"])
        df = df.dropna(subset=["date","close","high","low"])
        df = df.sort_values("date").reset_index(drop=True)

        df["corporate_action"]  = ""
        df["post_split_window"] = False
        df["value_traded"]      = df["close"] * df["volume"]

        logger.info(f"Medias24 {ticker} : {len(df)} lignes | dernier {df['close'].iloc[-1]} DH")
        return df

    def get_live(self, ticker: str) -> dict:
        isin = self.isin_map.get(ticker.upper())
        if not isin or not self.available:
            return {}

        data = self._get({"method": "getStockInfo", "ISIN": isin})
        if not data or not data.get("result"):
            return {}

        r     = data["result"]
        cours = SafeMath.to_float(r.get("cours"))
        ouv   = SafeMath.to_float(r.get("ouverture"))

        return {
            "cours":      cours,
            "ouverture":  ouv if not pd.isna(ouv) and ouv > 0 else cours,
            "variation":  SafeMath.to_float(r.get("variation")),
            "volume_mad": SafeMath.to_float(r.get("volume")),
            "quantite":   SafeMath.to_float(r.get("volumeTitre")),
            "haut":       np.nan,
            "bas":        np.nan,
            "source":     "Medias24",
            "timestamp":  MarketCalendar.now().strftime("%H:%M:%S"),
            "warning":    "Haut/Bas live non fournis par Medias24"
        }

# ============================================================
# HISTORIQUE LOCAL
# ============================================================

class HistoryStore:
    def __init__(self):
        self.base = Path("data/historique")
        self.base.mkdir(parents=True, exist_ok=True)

    def path(self, ticker):
        return self.base / f"{ticker.upper()}.xlsx"

    def save(self, ticker, df):
        df = df.copy()
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
        df = df.dropna(subset=["date","close"])
        df = df.sort_values("date").drop_duplicates(subset=["date"], keep="last").reset_index(drop=True)
        df.to_excel(self.path(ticker), index=False)
        return df

# ============================================================
# INDICATEURS TECHNIQUES
# ============================================================

class TechnicalIndicators:
    @staticmethod
    def calculate_all(df):
        df = df.copy().sort_values("date").reset_index(drop=True)

        for p in [20, 50, 100, 200]:
            df[f"MA{p}"] = df["close"].rolling(p).mean()

        delta    = df["close"].diff()
        gain     = delta.clip(lower=0)
        loss     = -delta.clip(upper=0)
        avg_gain = gain.ewm(alpha=1/14, adjust=False).mean()
        avg_loss = loss.ewm(alpha=1/14, adjust=False).mean()
        rs       = avg_gain / avg_loss.replace(0, np.nan)
        df["RSI"] = (100 - 100/(1+rs)).fillna(50)

        ema12             = df["close"].ewm(span=12, adjust=False).mean()
        ema26             = df["close"].ewm(span=26, adjust=False).mean()
        df["MACD"]        = ema12 - ema26
        df["MACD_SIGNAL"] = df["MACD"].ewm(span=9, adjust=False).mean()
        df["MACD_HIST"]   = df["MACD"] - df["MACD_SIGNAL"]

        ma20           = df["close"].rolling(20).mean()
        std            = df["close"].rolling(20).std()
        df["BB_upper"] = ma20 + 2*std
        df["BB_lower"] = ma20 - 2*std
        df["BB_width"] = (df["BB_upper"] - df["BB_lower"]) / ma20.replace(0, np.nan)

        df["tenkan"] = (df["high"].rolling(9).max()  + df["low"].rolling(9).min())  / 2
        df["kijun"]  = (df["high"].rolling(26).max() + df["low"].rolling(26).min()) / 2
        df["kumo_a"] = (df["tenkan"] + df["kijun"]) / 2
        df["kumo_b"] = (df["high"].rolling(52).max() + df["low"].rolling(52).min()) / 2

        ll              = df["low"].rolling(14).min()
        hh              = df["high"].rolling(14).max()
        df["Stoch_K"]   = (100*(df["close"]-ll)/(hh-ll).replace(0,np.nan)).fillna(50)
        df["Stoch_D"]   = df["Stoch_K"].rolling(3).mean().fillna(50)

        df["Vol_MA20"]      = df["volume"].rolling(20).mean()
        df["Volume_Ratio"]  = df["volume"] / df["Vol_MA20"].replace(0, np.nan)
        df["value_traded"]  = df["close"] * df["volume"]
        df["Avg_Value_20"]  = df["value_traded"].rolling(20).mean()
        df["Return_1D"]     = df["close"].pct_change() * 100
        df["Return_5D"]     = df["close"].pct_change(5)  * 100
        df["Return_20D"]    = df["close"].pct_change(20) * 100
        df["Volatility_20"] = df["Return_1D"].rolling(20).std()

        tr = pd.concat([
            df["high"] - df["low"],
            abs(df["high"] - df["close"].shift(1)),
            abs(df["low"]  - df["close"].shift(1))
        ], axis=1).max(axis=1)
        df["ATR"]     = tr.rolling(14).mean()
        df["High_20"] = df["high"].rolling(20).max()
        df["Low_20"]  = df["low"].rolling(20).min()
        df["cummax"]  = df["close"].cummax()
        df["drawdown"] = df["close"] / df["cummax"] - 1

        return df

# ============================================================
# SCORERS
# ============================================================

class TechnicalScorer:
    def score(self, df):
        m = SafeMath()
        score, maxs, reasons = 0, 0, []

        p      = m.last(df["close"])
        ma20   = m.last(df["MA20"]);   ma50  = m.last(df["MA50"]);   ma200 = m.last(df["MA200"])
        rsi    = m.last(df["RSI"])
        macd   = m.last(df["MACD"]);   sig   = m.last(df["MACD_SIGNAL"])
        hist   = m.last(df["MACD_HIST"]); histp = m.prev(df["MACD_HIST"])
        vr     = m.last(df["Volume_Ratio"])
        sk, sd = m.last(df["Stoch_K"]), m.last(df["Stoch_D"])
        ka, kb = m.last(df["kumo_a"]),  m.last(df["kumo_b"])
        tenkan = m.last(df["tenkan"]); kijun  = m.last(df["kijun"])
        ret5   = m.last(df["Return_5D"]); vol20 = m.last(df["Volatility_20"])
        post   = bool(m.last(df.get("post_split_window", pd.Series([False]))))

        maxs += 3
        if not any(pd.isna(x) for x in [p, ma20, ma50]):
            if p > ma20 > ma50:   score += 3; reasons.append("✅ Tendance haussière court/moyen terme")
            elif p < ma20 < ma50: reasons.append("❌ Tendance baissière court/moyen terme")
            else:                 score += 1; reasons.append("⚠️ Moyennes mobiles mixtes")

        maxs += 2
        if not pd.isna(ma200) and not pd.isna(p):
            if p > ma200: score += 2; reasons.append("✅ Prix au-dessus MA200")
            else:         reasons.append("❌ Prix sous MA200")

        maxs += 3
        if not any(pd.isna(x) for x in [macd, sig, hist, histp]):
            if macd > sig and hist > histp > 0:   score += 3; reasons.append("✅ MACD haussier accélérant")
            elif macd > sig:                      score += 2; reasons.append("✅ MACD haussier")
            elif macd < sig and hist < histp:     reasons.append("❌ MACD baissier dégradé")
            else:                                 score += 1; reasons.append("⚠️ MACD neutre")

        maxs += 2
        if not pd.isna(rsi):
            if 40 <= rsi <= 60:  score += 2; reasons.append(f"✅ RSI équilibré : {rsi:.1f}")
            elif 60 < rsi <= 70: score += 1; reasons.append(f"⚠️ RSI positif à surveiller : {rsi:.1f}")
            elif rsi > 70:       reasons.append(f"❌ RSI en surchauffe : {rsi:.1f}")
            else:                score += 0.75; reasons.append(f"⚠️ RSI faible : {rsi:.1f}")

        maxs += 3
        if not pd.isna(ka) and not pd.isna(kb):
            nh, nb = max(ka,kb), min(ka,kb)
            if p > nh and not pd.isna(tenkan) and not pd.isna(kijun) and tenkan > kijun:
                score += 3; reasons.append("✅ Ichimoku positif")
            elif p > nh:  score += 2; reasons.append("⚠️ Prix au-dessus du nuage")
            elif p > nb:  score += 1; reasons.append("⚠️ Prix dans le nuage")
            else:         reasons.append("❌ Prix sous le nuage")

        maxs += 2
        if not any(pd.isna(x) for x in [sk, sd]):
            if sk < 20 and sk > sd:  score += 2;   reasons.append("✅ Stochastique sortie de survente")
            elif sk > 80:            score += 0.5; reasons.append("⚠️ Stochastique surachat")
            else:                    score += 1;   reasons.append("⚠️ Stochastique neutre")

        maxs += 2
        if not pd.isna(vr):
            if vr >= 2:    score += 2;   reasons.append("✅ Volume fort confirmé")
            elif vr >= 1.2: score += 1;  reasons.append("⚠️ Volume supérieur moyenne")
            elif vr < 0.15: reasons.append("❌ Volume très faible")
            elif vr < 0.5:  score += 0.5; reasons.append("⚠️ Volume faible")
            else:           score += 1;   reasons.append("⚠️ Volume modéré")

        maxs += 1
        if not pd.isna(ret5):
            if post:
                score += 0.5; reasons.append(f"⚠️ Momentum neutralisé post-split : {ret5:.1f}%")
            else:
                score += 1 if abs(ret5) <= 5 else 0.5
                reasons.append(f"{'✅' if abs(ret5)<=5 else '⚠️'} Momentum 5j : {ret5:.1f}%")

        maxs += 1
        if not pd.isna(vol20):
            if post:
                score += 0.5; reasons.append(f"⚠️ Volatilité neutralisée post-split : {vol20:.1f}%")
            elif vol20 < 1.5:
                score += 1;   reasons.append(f"✅ Volatilité faible : {vol20:.1f}%")
            elif vol20 <= 5:
                score += 0.5; reasons.append(f"⚠️ Volatilité modérée : {vol20:.1f}%")
            else:
                reasons.append(f"❌ Volatilité élevée : {vol20:.1f}%")

        return ScoreResult(score, maxs, reasons, {
            "prix": p, "ma20": ma20, "ma50": ma50, "ma200": ma200,
            "rsi": rsi, "macd": macd, "volume_ratio": vr,
            "avg_value_20": m.last(df["Avg_Value_20"]),
            "return_5d": ret5, "volatility_20": vol20
        })


class FundamentalScorer:
    MAP = {
        "per":                ["per","PER"],
        "croissance_ca":      ["croissance_ca","croissance","growth"],
        "dette_nette_ebitda": ["dette_nette_ebitda","dette"],
        "div_yield":          ["div_yield","dividende"],
        "roic":               ["roic","ROIC"],
        "wacc":               ["wacc","WACC"],
        "cash_conversion":    ["cash_conversion","cash"],
        "marge_nette":        ["marge_nette","marge"],
        "catalyseur":         ["catalyseur","catalyst"],
        "nom":                ["nom","name"],
    }

    @classmethod
    def normalize(cls, d):
        out = {}
        for k, alts in cls.MAP.items():
            for a in alts:
                if isinstance(d, dict) and a in d and d[a] is not None:
                    out[k] = d[a]; break
        return out

    def __init__(self, f):
        self.f = self.normalize(f or {})

    def score(self):
        if not self.f:
            return ScoreResult(0, 10, ["❌ Pas de données fondamentales"])

        m = SafeMath(); score, maxs, r = 0, 0, []

        per   = m.to_float(self.f.get("per"))
        g     = m.to_float(self.f.get("croissance_ca"))
        d     = m.to_float(self.f.get("dette_nette_ebitda"))
        roic  = m.to_float(self.f.get("roic"))
        wacc  = m.to_float(self.f.get("wacc"))
        cash  = m.to_float(self.f.get("cash_conversion"))
        marge = m.to_float(self.f.get("marge_nette"))
        div   = m.to_float(self.f.get("div_yield"))

        maxs += 2
        if not pd.isna(per):
            if per < 8:    score += 2;    r.append("✅ PER très attractif")
            elif per < 12: score += 1.75; r.append("✅ PER attractif")
            elif per < 18: score += 1.25; r.append("⚠️ PER raisonnable")
            elif per < 25: score += 0.5;  r.append("⚠️ PER exigeant")
            else:                         r.append("❌ PER élevé")

        maxs += 2
        if not pd.isna(g):
            if g > 20:   score += 2;   r.append("✅ Croissance forte")
            elif g > 15: score += 1.5; r.append("✅ Croissance solide")
            elif g > 8:  score += 1;   r.append("⚠️ Croissance correcte")
            elif g > 0:  score += 0.5; r.append("⚠️ Croissance faible")
            else:                      r.append("❌ Croissance négative")

        maxs += 2
        if not pd.isna(d):
            if d <= 1:   score += 2;    r.append("✅ Dette très faible")
            elif d <= 2: score += 1.75; r.append("✅ Dette faible")
            elif d <= 3: score += 1;    r.append("⚠️ Dette modérée")
            elif d <= 4: score += 0.25; r.append("⚠️ Dette élevée")
            else:                       r.append("❌ Dette très élevée")

        maxs += 2
        if not pd.isna(roic) and not pd.isna(wacc):
            sp = roic - wacc
            if sp >= 5:   score += 2;   r.append("✅ Forte création de valeur")
            elif sp >= 2: score += 1.5; r.append("✅ Création de valeur")
            elif sp >= 0: score += 0.5; r.append("⚠️ Création de valeur faible")
            else:                       r.append("❌ ROIC inférieur au WACC")

        maxs += 1
        if not pd.isna(cash):
            if cash >= 80:   score += 1;    r.append("✅ Cash conversion excellente")
            elif cash >= 65: score += 0.75; r.append("✅ Cash conversion correcte")
            elif cash >= 50: score += 0.5;  r.append("⚠️ Cash conversion moyenne")
            else:                           r.append("❌ Cash conversion faible")

        maxs += 1
        if not pd.isna(marge):
            if marge >= 18:   score += 1;    r.append("✅ Marge nette élevée")
            elif marge >= 12: score += 0.75; r.append("✅ Marge nette solide")
            elif marge >= 7:  score += 0.5;  r.append("⚠️ Marge nette correcte")
            else:                            r.append("❌ Marge faible")

        maxs += 1
        if not pd.isna(div):
            if div > 4:     score += 1;    r.append("✅ Dividende élevé")
            elif div > 2.5: score += 0.75; r.append("✅ Dividende correct")
            elif div > 1:   score += 0.25; r.append("⚠️ Dividende modeste")

        return ScoreResult(score, maxs, r, self.f)


class LiquidityScorer:
    def score(self, df):
        m = SafeMath()
        avg        = m.last(df["Avg_Value_20"])
        vr         = m.last(df["Volume_Ratio"])
        last_value = m.last(df["value_traded"])
        score, maxs, r = 0, 5, []

        if pd.isna(avg):
            return ScoreResult(0, maxs, ["⚠️ Liquidité non disponible"])

        if avg >= 5_000_000:
            score += 3; r.append(f"✅ Liquidité forte : moy 20j ≈ {avg:,.0f} DH")
        elif avg >= 1_000_000:
            score += 2; r.append(f"✅ Liquidité correcte : moy 20j ≈ {avg:,.0f} DH")
        elif avg >= 300_000:
            score += 1; r.append(f"⚠️ Liquidité faible : moy 20j ≈ {avg:,.0f} DH")
        else:
            r.append(f"❌ Liquidité très faible : moy 20j ≈ {avg:,.0f} DH")

        if not pd.isna(vr):
            if vr >= 1:     score += 1;   r.append("✅ Volume récent ≥ moyenne")
            elif vr >= 0.5: score += 0.5; r.append("⚠️ Volume récent faible mais acceptable")
            else:                         r.append("❌ Volume récent faible")

        if not pd.isna(last_value):
            if last_value >= avg * 0.7:   score += 1; r.append("✅ Dernière séance active")
            else:                         r.append("⚠️ Dernière séance peu active")

        return ScoreResult(score, maxs, r, {"avg_value_20": avg, "volume_ratio": vr, "last_value": last_value})


class RedFlagDetector:
    def __init__(self, fundamentals):
        self.f = FundamentalScorer.normalize(fundamentals or {})

    def detect(self, df):
        m = SafeMath(); flags = []
        post = bool(m.last(df.get("post_split_window", pd.Series([False]))))

        d    = m.to_float(self.f.get("dette_nette_ebitda"))
        cash = m.to_float(self.f.get("cash_conversion"))
        roic = m.to_float(self.f.get("roic"))
        wacc = m.to_float(self.f.get("wacc"))

        p, ma20, ma50 = m.last(df["close"]), m.last(df["MA20"]), m.last(df["MA50"])
        rsi     = m.last(df["RSI"])
        vr      = m.last(df["Volume_Ratio"])
        vol20   = m.last(df["Volatility_20"])
        ret20   = m.last(df["Return_20D"])
        avg_val = m.last(df["Avg_Value_20"])

        if not pd.isna(d):
            if d > 5:   flags.append(RedFlag(Severity.CRITIQUE, "Structure",  "Dette/EBITDA critique",    True))
            elif d > 4: flags.append(RedFlag(Severity.ELEVEE,   "Structure",  "Dette élevée"))
            elif d > 3: flags.append(RedFlag(Severity.MOYENNE,  "Structure",  "Endettement élevé"))

        if not pd.isna(cash):
            if cash < 30:   flags.append(RedFlag(Severity.CRITIQUE, "Cash-flow", "Cash conversion critique", True))
            elif cash < 50: flags.append(RedFlag(Severity.MOYENNE,  "Cash-flow", "Cash conversion faible"))

        if not pd.isna(roic) and not pd.isna(wacc) and roic < wacc:
            flags.append(RedFlag(Severity.ELEVEE, "Rentabilité", "ROIC inférieur au WACC"))

        if not post:
            if not any(pd.isna(x) for x in [p, ma20, ma50]) and p < ma20 < ma50:
                flags.append(RedFlag(Severity.ELEVEE, "Technique", "Tendance baissière court/moyen terme"))

            if not pd.isna(ret20):
                if ret20 < -25:   flags.append(RedFlag(Severity.CRITIQUE, "Momentum", "Correction forte sur 20j",     True))
                elif ret20 < -15: flags.append(RedFlag(Severity.ELEVEE,  "Momentum", "Correction sur 20j"))

            if not pd.isna(vol20) and vol20 > 6:
                flags.append(RedFlag(Severity.MOYENNE, "Risque", "Volatilité récente élevée"))

        if not pd.isna(rsi):
            if rsi > 82:   flags.append(RedFlag(Severity.CRITIQUE, "Technique", "RSI extrême",    True))
            elif rsi > 75: flags.append(RedFlag(Severity.ELEVEE,   "Technique", "RSI surchauffe"))

        if not pd.isna(vr) and not post:
            if vr < 0.15:  flags.append(RedFlag(Severity.CRITIQUE, "Liquidité", "Volume relatif très faible", True))
            elif vr < 0.3: flags.append(RedFlag(Severity.MOYENNE,  "Liquidité", "Volume relatif faible"))

        if not pd.isna(avg_val) and avg_val < 300_000:
            flags.append(RedFlag(Severity.ELEVEE, "Liquidité", "Valeur échangée moyenne très faible"))

        return flags


class RiskScorer:
    def score(self, df, flags):
        blocking = [f for f in flags if f.is_blocking]
        high     = [f for f in flags if f.severity == Severity.ELEVEE]
        score, maxs, r = 0, 5, []

        if blocking:
            return ScoreResult(0, maxs, ["❌ Risque bloquant détecté"])

        if high:  score += 1.5; r.append("⚠️ Red flags élevés présents")
        else:     score += 2;   r.append("✅ Aucun red flag critique/élevé")

        dd  = SafeMath.to_float(df["drawdown"].min())
        vol = SafeMath.last(df["Volatility_20"])

        if not pd.isna(dd):
            if dd > -0.15:   score += 1.5; r.append(f"✅ Drawdown contenu : {dd*100:.1f}%")
            elif dd > -0.35: score += 0.75; r.append(f"⚠️ Drawdown significatif : {dd*100:.1f}%")
            else:            r.append(f"❌ Drawdown lourd : {dd*100:.1f}%")

        if not pd.isna(vol):
            if vol <= 2:   score += 1.5; r.append("✅ Volatilité récente maîtrisée")
            elif vol <= 5: score += 0.75; r.append("⚠️ Volatilité récente moyenne")
            else:          r.append("❌ Volatilité récente élevée")

        return ScoreResult(score, maxs, r)

# ============================================================
# SETUP / DECISION / VALORISATION
# ============================================================

class SetupDetector:
    def detect(self, df):
        m = SafeMath()
        p, ma20, ma50 = m.last(df["close"]), m.last(df["MA20"]), m.last(df["MA50"])
        rsi, vr       = m.last(df["RSI"]),   m.last(df["Volume_Ratio"])
        macd, sig     = m.last(df["MACD"]),  m.last(df["MACD_SIGNAL"])
        high20, low20 = m.last(df["High_20"]), m.last(df["Low_20"])
        stoch         = m.last(df["Stoch_K"])

        has_trend = not any(pd.isna(x) for x in [p, ma20, ma50])
        has_rsi   = not pd.isna(rsi)
        has_macd  = not any(pd.isna(x) for x in [macd, sig])
        has_vr    = not pd.isna(vr)

        if has_trend and has_rsi and p < ma20 < ma50 and rsi < 48:
            return Setup.FAIBLESSE
        if has_trend and has_rsi and has_macd and p > ma20 > ma50 and rsi > 52 and macd > sig:
            if not has_vr or vr >= 1.2:
                return Setup.MOMENTUM
        if has_trend and has_macd and not pd.isna(high20) and p >= high20*0.98 and macd > sig:
            if not has_vr or vr >= 1.3:
                return Setup.BREAKOUT
        if has_trend and has_rsi and p > ma50 and ma20 > ma50 and 40 <= rsi <= 58 and p <= ma20*1.02:
            return Setup.PULLBACK
        if has_rsi and not pd.isna(low20) and p <= low20*1.06:
            if rsi < 38 or (not pd.isna(stoch) and stoch < 25):
                return Setup.CONTRARIEN
        if has_trend and has_rsi and has_macd and p > ma50 and 45 <= rsi <= 60 and macd > sig:
            if not has_vr or vr < 0.8:
                return Setup.ACCUMULATION
        return Setup.NEUTRE


class DecisionEngine:
    def decide(self, tech, fond, liq, risk, setup, flags):
        score = round(
            tech.normalized * 0.45 +
            fond.normalized * 0.25 +
            liq.normalized  * 0.15 +
            risk.normalized * 0.15,
            2
        )

        if any(f.is_blocking for f in flags):
            return Signal.EVITER, "EVITER — risque bloquant détecté", score

        if setup == Setup.FAIBLESSE:
            if fond.normalized >= 6.5 and liq.normalized >= 5:
                return Signal.ATTENDRE, "ATTENDRE — fondamental correct mais timing faible", score
            return Signal.EVITER, "EVITER — faiblesse technique", score

        if liq.normalized < 3:
            return Signal.ATTENDRE, "ATTENDRE — liquidité insuffisante", score

        if setup == Setup.CONTRARIEN:
            if fond.normalized >= 5 and risk.normalized >= 5 and score >= 5:
                return Signal.SURVEILLER, "SURVEILLER REBOND — contrarien non confirmé", score
            return Signal.ATTENDRE, "ATTENDRE — rebond non confirmé", score

        if score >= 7.5 and setup in [Setup.MOMENTUM, Setup.BREAKOUT] and risk.normalized >= 6:
            return Signal.ACHETER,    f"ACHETER — {setup.value}",              score
        if score >= 6.8 and setup == Setup.PULLBACK and risk.normalized >= 6:
            return Signal.ACHETER,    "ACHETER — pullback haussier confirmé",  score
        if score >= 6.2 and setup == Setup.ACCUMULATION:
            return Signal.ACCUMULER,  "ACCUMULER — accumulation progressive",  score
        if score >= 5.6:
            return Signal.SURVEILLER, f"SURVEILLER — {setup.value}",           score
        if score >= 4:
            return Signal.ATTENDRE,   f"ATTENDRE — {setup.value}",             score
        return Signal.EVITER, f"EVITER — {setup.value}", score


class ValuationEngine:
    def __init__(self, f):
        self.f = FundamentalScorer.normalize(f or {})

    def calculate(self, price):
        m    = SafeMath()
        per  = m.to_float(self.f.get("per"))
        g    = m.to_float(self.f.get("croissance_ca"))
        roic = m.to_float(self.f.get("roic"))
        wacc = m.to_float(self.f.get("wacc"))
        d    = m.to_float(self.f.get("dette_nette_ebitda"))
        cash = m.to_float(self.f.get("cash_conversion"))

        if pd.isna(per) or pd.isna(g):
            return Valuation(None,None,None,None,None,None,None,"Insuffisant","Faible")

        prem = 0
        if g > 20:   prem += 0.15
        elif g > 15: prem += 0.10
        elif g > 8:  prem += 0.05
        elif g < 0:  prem -= 0.10

        if not pd.isna(roic) and not pd.isna(wacc):
            sp = roic - wacc
            if sp >= 5:   prem += 0.12
            elif sp >= 2: prem += 0.07
            elif sp < 0:  prem -= 0.10

        if per < 8:    prem += 0.12
        elif per < 12: prem += 0.08
        elif per > 28: prem -= 0.15
        elif per > 22: prem -= 0.08

        if not pd.isna(cash):
            if cash >= 80:  prem += 0.05
            elif cash < 40: prem -= 0.08

        if not pd.isna(d):
            if d > 4:   prem -= 0.10
            elif d > 3: prem -= 0.05
            elif d < 1: prem += 0.05

        prem = max(min(prem, 0.35), -0.30)
        base = round(price*(1+prem), 2)
        bull = round(base*1.20, 2)
        bear = round(base*0.80, 2)

        return Valuation(base, bull, bear,
            m.pct(base,price), m.pct(bull,price), m.pct(bear,price),
            round(prem*100,1), "Score fondamental relatif", "Moyenne à faible")

# ============================================================
# BACKTEST
# ============================================================

class Backtester:
    @staticmethod
    def run(df):
        d = df.copy().dropna(subset=["MA20","MA50","RSI","MACD","MACD_SIGNAL"])
        if len(d) < 80:
            return {"status": "Historique insuffisant"}

        d["entry_signal"] = (
            (d["close"] > d["MA20"]) & (d["MA20"] > d["MA50"]) &
            (d["RSI"].between(40,70)) & (d["MACD"] > d["MACD_SIGNAL"])
        )
        d["exit_signal"] = (
            (d["close"] < d["MA20"]) | (d["RSI"] > 75) | (d["MACD"] < d["MACD_SIGNAL"])
        )

        trades = []; in_pos = False
        entry_raw = entry_net = entry_date = None

        for _, row in d.iterrows():
            if bool(row.get("post_split_window", False)):
                continue
            close, date = row["close"], row["date"]
            if not in_pos and row["entry_signal"]:
                in_pos = True; entry_raw = close
                entry_net = close*(1+BUY_FEE); entry_date = date
                continue
            if in_pos and row["exit_signal"]:
                exit_net   = close*(1-SELL_FEE)
                gross      = exit_net - entry_net
                net        = gross*(1-TAX_RATE) if gross > 0 else gross
                ret        = net / entry_net
                trades.append({"entry_date": entry_date, "exit_date": date,
                                "entry_raw": round(entry_raw,2), "exit_raw": round(close,2),
                                "return_net_%": round(ret*100,2)})
                in_pos = False

        buyhold = round(float((d["close"].iloc[-1]/d["close"].iloc[0]-1)*100), 2)
        if not trades:
            return {"status": "Aucun trade généré", "strategy_return_%": 0,
                    "buyhold_return_%": buyhold, "trades": 0,
                    "win_rate_%": None, "last_trades": []}

        capital = 1.0
        for t in trades:
            capital *= 1 + t["return_net_%"]/100

        return {
            "status":             "OK",
            "strategy_return_%":  round(float((capital-1)*100), 2),
            "buyhold_return_%":   buyhold,
            "trades":             len(trades),
            "win_rate_%":         round(sum(t["return_net_%"]>0 for t in trades)/len(trades)*100, 1),
            "last_trades":        trades[-5:]
        }

# ============================================================
# GRAPHIQUE — ✅ split_date converti en string (fix pandas 2.x Timestamp arithmetic)
# ============================================================

class ChartEngine:
    @staticmethod
    def create(ticker, df):
        try:
            fig = make_subplots(
                rows=4, cols=1, shared_xaxes=True,
                vertical_spacing=0.03,
                row_heights=[0.50, 0.16, 0.17, 0.17],
                subplot_titles=("Prix ajusté", "RSI", "MACD", "Volume")
            )

            fig.add_trace(go.Candlestick(
                x=df["date"], open=df["open"], high=df["high"],
                low=df["low"], close=df["close"], name="Prix"), row=1, col=1)

            for ma, color in [("MA20","orange"),("MA50","blue"),("MA200","red")]:
                if ma in df.columns:
                    fig.add_trace(go.Scatter(x=df["date"], y=df[ma], name=ma,
                        line=dict(color=color, width=1)), row=1, col=1)

            fig.add_trace(go.Scatter(x=df["date"], y=df["RSI"], name="RSI",
                line=dict(color="purple")), row=2, col=1)
            fig.add_hline(y=70, line_dash="dash", line_color="red",   row=2, col=1)
            fig.add_hline(y=30, line_dash="dash", line_color="green", row=2, col=1)

            fig.add_trace(go.Scatter(x=df["date"], y=df["MACD"],        name="MACD"),   row=3, col=1)
            fig.add_trace(go.Scatter(x=df["date"], y=df["MACD_SIGNAL"], name="Signal"), row=3, col=1)
            fig.add_trace(go.Bar(   x=df["date"], y=df["MACD_HIST"],    name="Hist"),   row=3, col=1)
            fig.add_trace(go.Bar(   x=df["date"], y=df["volume"],       name="Volume"), row=4, col=1)

            if ticker in OFFICIAL_SPLITS:
                # ✅ Convertir en string ISO pour éviter l'erreur pandas 2.x
                # "Addition/subtraction of integers and integer-arrays with Timestamp is not supported"
                split_date_str = pd.to_datetime(OFFICIAL_SPLITS[ticker]["date"]).strftime("%Y-%m-%d")
                fig.add_vline(
                    x=split_date_str,
                    line_dash="dash", line_color="red",
                    annotation_text="Split officiel",
                    annotation_position="top right"
                )

            fig.update_layout(
                title=f"{ticker} — BVC Ultimate Analyzer {VERSION}",
                height=950,
                xaxis_rangeslider_visible=False
            )
            path = f"charts/{ticker}_chart_{MarketCalendar.now().strftime('%Y%m%d_%H%M')}.html"
            fig.write_html(path)
            return path
        except Exception as e:
            logger.warning(f"Graphique {ticker} : {e}")
            return ""

# ============================================================
# NEWS
# ============================================================

class NewsConnector:
    def fetch(self, ticker, company=""):
        try:
            r    = requests.get(BOURSENEWS_URL, headers={"User-Agent": "Mozilla/5.0"}, timeout=15)
            soup = BeautifulSoup(r.text, "html.parser")
            keys = [ticker.lower()] + [x.lower() for x in company.split() if len(x) > 3]
            generic = ["bourse","casablanca","marché","resultat","résultat","dividende","capital"]
            out, seen = [], set()
            for a in soup.find_all("a", href=True):
                title = a.get_text(" ", strip=True)
                if len(title) < 20:
                    continue
                low      = title.lower()
                relevant = any(k in low for k in keys)
                if relevant or any(k in low for k in generic):
                    if low not in seen:
                        out.append({"source": "BourseNews", "title": title, "relevant": relevant})
                        seen.add(low)
            out.sort(key=lambda x: x["relevant"], reverse=True)
            return out[:8]
        except Exception:
            return []

# ============================================================
# PDF — rattaché au ticker via PDF_TICKER_MAP
# ============================================================

class PDFReader:
    KEYWORDS = ["résultat","resultat","chiffre d'affaires","marge","dette",
                "cash","dividende","rnpg","ebitda"]

    def read(self, pdf_files, ticker):
        if not pdf_files:
            return "N/A"

        summaries = []
        for file in pdf_files:
            basename = os.path.basename(file)

            allowed = PDF_TICKER_MAP.get(basename, [])
            if allowed and ticker.upper() not in [t.upper() for t in allowed]:
                continue

            try:
                txt = ""
                with pdfplumber.open(file) as pdf:
                    for page in pdf.pages[:12]:
                        txt += "\n" + (page.extract_text() or "")

                if ticker.lower() not in txt.lower():
                    continue

                lines = []
                for line in txt.splitlines():
                    low = line.lower()
                    if ticker.lower() in low or any(k in low for k in self.KEYWORDS):
                        clean = re.sub(r"\s+", " ", line).strip()
                        if len(clean) > 20:
                            lines.append(clean)

                summaries.append(
                    f"{basename} : " + " | ".join(lines[:12])
                    if lines
                    else f"{basename} : PDF lu, aucun élément pertinent détecté."
                )
            except Exception as e:
                summaries.append(f"{basename} : erreur lecture — {e}")

        return "\n".join(summaries) if summaries else "N/A"

# ============================================================
# EXPORT
# ============================================================

class ExportEngine:
    @staticmethod
    def details(ticker, df, result):
        path = f"exports/{ticker}_details_{MarketCalendar.now().strftime('%Y%m%d_%H%M')}.xlsx"
        try:
            with pd.ExcelWriter(path, engine="openpyxl") as writer:
                df.to_excel(writer, index=False, sheet_name="serie_ajustee")
                pd.DataFrame([{
                    "ticker":           result.ticker,
                    "prix":             result.price,
                    "action":           result.action,
                    "score_global":     result.score_global,
                    "corporate_actions":" | ".join(result.corporate_actions),
                    "backtest_%":       result.backtest.get("strategy_return_%", np.nan)
                }]).to_excel(writer, index=False, sheet_name="resume")
        except Exception as e:
            logger.warning(f"Export détail {ticker} : {e}")
        return path

# ============================================================
# NOTE — ✅ Red flags triés par sévérité (CRITIQUE → ELEVEE → MOYENNE → FAIBLE)
# ============================================================

class NoteGenerator:
    @staticmethod
    def v(x):
        try:   return "N/A" if x is None or pd.isna(x) else x
        except: return x

    @staticmethod
    def fmt_backtest(bt):
        if not bt or bt.get("status") != "OK":
            return str(bt.get("status","N/A")) if bt else "N/A"
        return (
            f"Stratégie {bt.get('strategy_return_%','N/A')}% | "
            f"Buy&Hold {bt.get('buyhold_return_%','N/A')}% | "
            f"{bt.get('trades',0)} trades | "
            f"Win rate {bt.get('win_rate_%','N/A')}%"
        )

    @staticmethod
    def generate(r):
        f    = FundamentalScorer.normalize(r.fundamental_data or {})
        live = r.live_data or {}
        V    = NoteGenerator.v

        tech  = "\n".join([f"  • {x}" for x in r.score_technical.reasons])
        fond  = "\n".join([f"  • {x}" for x in r.score_fundamental.reasons])
        liq   = "\n".join([f"  • {x}" for x in r.score_liquidity.reasons])
        risk  = "\n".join([f"  • {x}" for x in r.score_risk.reasons])

        # ✅ Red flags triés par sévérité : CRITIQUE → ELEVEE → MOYENNE → FAIBLE
        flags = "\n".join([
            f"  {x.severity.value} | {x.category} : {x.message}" + (" [BLOQUANT]" if x.is_blocking else "")
            for x in sorted(r.red_flags, key=lambda x: _SEV_ORDER[x.severity])
        ]) if r.red_flags else "  ✅ Aucun red flag majeur"

        corp  = "\n".join([f"  • {x}" for x in r.corporate_actions]) if r.corporate_actions else "  N/A"
        news  = "\n".join([f"  • [{n['source']}] {n['title']}" for n in r.news]) if r.news else "  N/A"

        return f"""
================================================================================
NOTE INSTITUTIONNELLE — {r.ticker}
BVC ULTIMATE ANALYZER {VERSION} | {r.date.strftime('%d/%m/%Y %H:%M')}
================================================================================
MARCHÉ  : {r.market_status} | {MarketCalendar.message()}

SYNTHÈSE
  Prix        : {r.price:.2f} DH
  Signal      : {r.action}
  Setup       : {r.setup.value}
  Technique   : {r.score_technical.normalized}/10
  Fondamental : {r.score_fundamental.normalized}/10
  Liquidité   : {r.score_liquidity.normalized}/10
  Risque      : {r.score_risk.normalized}/10
  Global      : {r.score_global}/10

LIVE
  Source      : {live.get('source','N/A')} | Cours : {live.get('cours','N/A')} DH
  Ouverture   : {live.get('ouverture','N/A')} DH | Variation : {live.get('variation','N/A')} %
  Volume MAD  : {live.get('volume_mad','N/A')} | Warning : {live.get('warning','N/A')}

CORPORATE ACTIONS
{corp}

ANALYSE TECHNIQUE
{tech}

ANALYSE FONDAMENTALE
  PER : {f.get('per','N/A')}x | Croissance : {f.get('croissance_ca','N/A')}% | Dette : {f.get('dette_nette_ebitda','N/A')}x
  ROIC/WACC : {f.get('roic','N/A')}/{f.get('wacc','N/A')} | Cash : {f.get('cash_conversion','N/A')}% | Marge : {f.get('marge_nette','N/A')}%
{fond}

LIQUIDITÉ
{liq}

RISQUE
{risk}

RED FLAGS
{flags}

VALORISATION
  Méthode : {r.valuation.methodology} | Confiance : {r.valuation.confidence}
  Bear : {V(r.valuation.bear)} DH | Base : {V(r.valuation.base)} DH (+{V(r.valuation.upside_base)}%) | Bull : {V(r.valuation.bull)} DH

BACKTEST : {NoteGenerator.fmt_backtest(r.backtest)}

NEWS
{news}

PDF : {r.pdf_summary[:1500] if r.pdf_summary else 'N/A'}

GRAPHIQUE : {r.chart_file}

RECOMMANDATION : {r.action}
Note automatique. Ne constitue pas un conseil en investissement.
================================================================================
"""

# ============================================================
# ANALYSEUR PRINCIPAL
# ============================================================

class BVCAnalyzer:
    def __init__(self):
        self.connector   = Medias24Connector(ISIN_MAP)
        self.history     = HistoryStore()
        self.news        = NewsConnector()
        self.pdf         = PDFReader()
        self.fundamentals = {}

    def load_fundamentals(self):
        try:
            r = requests.get(GITHUB_URL, headers={"User-Agent": "Mozilla/5.0"}, timeout=20)
            r.raise_for_status()
            self.fundamentals = r.json()
            logger.info(f"Fondamentaux GitHub : {len(self.fundamentals)} tickers")
        except Exception as e:
            logger.warning(f"Fondamentaux GitHub : {e}")
            self.fundamentals = {}

    def analyze(self, ticker: str, pdf_files: list) -> Optional[AnalysisResult]:
        # 1. Historique brut (sans split)
        df = self.connector.get_history(ticker)
        if df.empty or len(df) < 50:
            logger.warning(f"{ticker} : données insuffisantes")
            return None

        # 2. Appliquer le split UNE SEULE FOIS ici
        df, corporate_actions = CorporateActionEngine.apply_official_splits(df, ticker)

        # 3. Sauvegarde locale
        df = self.history.save(ticker, df)

        # 4. Indicateurs sur série ajustée
        df = TechnicalIndicators.calculate_all(df)

        # 5. Injection cours live
        live = self.connector.get_live(ticker)
        if live and not pd.isna(SafeMath.to_float(live.get("cours"))):
            price_live = SafeMath.to_float(live["cours"])
            ouv_live   = SafeMath.to_float(live.get("ouverture"))
            idx        = df.index[-1]
            df.loc[idx, "close"] = price_live
            if not pd.isna(ouv_live) and ouv_live > 0:
                df.loc[idx, "open"]  = ouv_live
            df.loc[idx, "high"]  = max(df.loc[idx,"high"], price_live)
            df.loc[idx, "low"]   = min(df.loc[idx,"low"],  price_live)
            if not pd.isna(SafeMath.to_float(live.get("volume_mad"))):
                df.loc[idx, "value_traded"] = SafeMath.to_float(live["volume_mad"])
            df = TechnicalIndicators.calculate_all(df)

        price = SafeMath.last(df["close"])
        f     = self.fundamentals.get(ticker.upper(), {})

        tech    = TechnicalScorer().score(df)
        fond    = FundamentalScorer(f).score()
        liq     = LiquidityScorer().score(df)
        flags   = RedFlagDetector(f).detect(df)
        risk    = RiskScorer().score(df, flags)
        setup   = SetupDetector().detect(df)
        signal, action, global_score = DecisionEngine().decide(tech, fond, liq, risk, setup, flags)
        valuation = ValuationEngine(f).calculate(price)
        backtest  = Backtester.run(df)
        chart     = ChartEngine.create(ticker, df)
        news      = self.news.fetch(ticker, f.get("nom",""))
        pdf_sum   = self.pdf.read(pdf_files, ticker)

        result = AnalysisResult(
            ticker=ticker, price=price,
            date=MarketCalendar.now().replace(tzinfo=None),
            setup=setup, signal=signal, action=action,
            score_technical=tech, score_fundamental=fond,
            score_liquidity=liq, score_risk=risk,
            score_global=global_score, red_flags=flags,
            valuation=valuation, technical_data=tech.raw_details,
            fundamental_data=f, live_data=live,
            market_status=MarketCalendar.status(),
            corporate_actions=corporate_actions,
            backtest=backtest, news=news,
            pdf_summary=pdf_sum, chart_file=chart,
            export_detail_file=""
        )

        result.export_detail_file = ExportEngine.details(ticker, df, result)
        result.note = NoteGenerator.generate(result)
        return result

# ============================================================
# MAIN
# ============================================================

def main():
    now = MarketCalendar.now()
    print("=" * 80)
    print(f"BVC ULTIMATE ANALYZER {VERSION}")
    print("Medias24 + GitHub + Risk + Liquidity + Graphiques + Backtest + PDF + News")
    print(f"Correctifs v3.5.2 : SOT ISIN restauré | Split unique | PDF par ticker")
    print("=" * 80)
    print(f"Heure Casablanca : {now.strftime('%H:%M:%S')}")
    print(f"Statut marché    : {MarketCalendar.status()}")
    print(f"Message          : {MarketCalendar.message()}")

    try:
        from google.colab import files as colab_files
        COLAB = True
    except Exception:
        COLAB = False

    pdf_files = []
    if COLAB:
        print("\nPDF optionnels — appuie Annuler si aucun PDF à uploader")
        try:
            uploaded  = colab_files.upload()
            pdf_files = [f for f in uploaded.keys() if f.lower().endswith(".pdf")]
            if pdf_files:
                print(f"\nPDF uploadés : {pdf_files}")
                print("💡 Si ces PDF concernent un titre spécifique (ex: SOT),")
                print("   ajoute-le dans PDF_TICKER_MAP en haut du code.")
        except Exception:
            pdf_files = []
    else:
        pdf_files = [f for f in os.listdir(".") if f.lower().endswith(".pdf")]

    print(f"\nPDF détectés : {len(pdf_files)}")

    analyzer = BVCAnalyzer()
    analyzer.load_fundamentals()

    print("\nTest Medias24...", end=" ")
    if not analyzer.connector.preload():
        print("❌ Medias24 indisponible — arrêt.")
        return
    print("✅ DISPONIBLE")

    print(f"\nAnalyse de {len(TICKERS_DEFAUT)} titres...\n")

    results = []
    for ticker in TICKERS_DEFAUT:
        try:
            r = analyzer.analyze(ticker, pdf_files)
            if r:
                results.append(r)
                print(f"  ✅ {ticker:<6} | {r.price:>10.2f} DH | {r.action:<45} | Score {r.score_global}")
                print(r.note)
            else:
                print(f"  ❌ {ticker:<6} | Données insuffisantes")
        except Exception as e:
            print(f"  ❌ {ticker:<6} | Erreur : {e}")
            import traceback; traceback.print_exc()

    if results:
        rows = []
        for r in sorted(results, key=lambda x: x.score_global, reverse=True):
            rows.append({
                "Ticker":           r.ticker,
                "Prix":             r.price,
                "Signal":           r.signal.value,
                "Action":           r.action,
                "Score Global":     r.score_global,
                "Technique":        r.score_technical.normalized,
                "Fondamental":      r.score_fundamental.normalized,
                "Liquidité":        r.score_liquidity.normalized,
                "Risque":           r.score_risk.normalized,
                "Setup":            r.setup.value,
                "Red Flags":        len(r.red_flags),
                "Corporate Actions":" | ".join(r.corporate_actions),
                "Base":             r.valuation.base,
                "Upside Base %":    r.valuation.upside_base,
                "Marché":           r.market_status,
                "Cours Live":       r.live_data.get("cours",    np.nan) if r.live_data else np.nan,
                "Variation %":      r.live_data.get("variation",np.nan) if r.live_data else np.nan,
                "Avg Value 20j":    r.technical_data.get("avg_value_20", np.nan),
                "RSI":              r.technical_data.get("rsi",          np.nan),
                "Backtest %":       r.backtest.get("strategy_return_%",  np.nan),
                "BuyHold %":        r.backtest.get("buyhold_return_%",   np.nan),
                "Win Rate %":       r.backtest.get("win_rate_%",         np.nan),
                "Graphique":        r.chart_file,
            })

        df_out = pd.DataFrame(rows)
        print("\n" + "=" * 80)
        print("CLASSEMENT GLOBAL")
        print("=" * 80)
        print(df_out.to_string(index=False))

        export = f"exports/bvc_v352_pro_{MarketCalendar.now().strftime('%Y%m%d_%H%M')}.xlsx"
        df_out.to_excel(export, index=False)
        print(f"\nExport résumé : {export}")

        if COLAB:
            try:
                colab_files.download(export)
            except Exception:
                pass

    print("\nANALYSE TERMINÉE")
    print("Historiques : data/historique/")
    print("Graphiques  : charts/")
    print("Exports     : exports/")
    print("Logs        : logs/")

if __name__ == "__main__":
    main()
