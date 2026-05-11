# ============================================================
# BVC ULTIMATE ANALYZER v3.4 — MEDIAS24
# Source : API Medias24 — 80 titres + nouvelles IPO
# Timezone Casablanca | Preload unique | Sans Excel
#
# CORRECTIONS v3.4 :
#   ✅ SetupDetector robuste aux NaN (conditions indépendantes)
#   ✅ DecisionEngine : 1 flag CRITIQUE/bloquant suffit à bloquer
#   ✅ Red flags triés par sévérité dans la note (CRITIQUE en premier)
#   ✅ ValuationEngine utilise target_price/bear_case/bull_case du JSON
#   ✅ FundamentalScorer : forward_per, momentum, rerating, cycle_commodities
#   ✅ Medias24 get_live : haut/bas corrigés
#   ✅ EVA (ROIC - WACC) affiché dans la note
# ============================================================

import subprocess, sys

def auto_install(pkg):
    try: __import__(pkg)
    except ImportError:
        subprocess.check_call([sys.executable, "-m", "pip", "install", pkg, "-q"])

for pkg in ["openpyxl", "requests", "pandas", "numpy"]:
    auto_install(pkg)

import pandas as pd
import numpy as np
import requests
import logging
import warnings
import json
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from enum import Enum
from pathlib import Path

try:
    from zoneinfo import ZoneInfo
    TZ_CASABLANCA = ZoneInfo("Africa/Casablanca")
except ImportError:
    TZ_CASABLANCA = None

warnings.filterwarnings("ignore")
logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)-8s | %(message)s", datefmt="%H:%M:%S")
logger = logging.getLogger("BVC")

GITHUB_URL = "https://raw.githubusercontent.com/abdmoutalib207-lang/-bvc-analyzer/main/fondamentaux.json"

for folder in ["data/historique", "exports"]:
    Path(folder).mkdir(parents=True, exist_ok=True)

# ============================================================
# ISIN MAP — 80 TITRES + NOUVELLES IPO
# ============================================================

ISIN_MAP = {
    "ADH":  "MA0000011512",
    "AFM":  "MA0000012296",
    "AFI":  "MA0000012114",
    "GAZ":  "MA0000010951",
    "AGM":  "MA0000010944",
    "AKD":  "MA0000012585",
    "ADI":  "MA0000011819",
    "ALU":  "MA0000010936",
    "ARD":  "MA0000012460",
    "ATL":  "MA0000011710",
    "ATW":  "MA0000012445",
    "HAL":  "MA0000010969",
    "NEJ":  "MA0000011009",
    "BAL":  "MA0000011991",
    "BOA":  "MA0000012437",
    "BCP":  "MA0000011884",
    "BMC":  "MA0000010811",
    "CAR":  "MA0000011868",
    "CDM":  "MA0000010381",
    "CIH":  "MA0000011454",
    "CIM":  "MA0000010506",
    "CMT":  "MA0000011793",
    "COL":  "MA0000011934",
    "CSR":  "MA0000012247",
    "CTM":  "MA0000010340",
    "DAR":  "MA0000011421",
    "DHO":  "MA0000011850",
    "DTT":  "MA0000012536",
    "DSW":  "MA0000011637",
    "ENK":  "MA0000011942",
    "EQD":  "MA0000010357",
    "FNB":  "MA0000011587",
    "HPS":  "MA0000011611",
    "IBM":  "MA0000011132",
    "IMI":  "MA0000012387",
    "INV":  "MA0000011579",
    "JET":  "MA0000012080",
    "LBV":  "MA0000011801",
    "LHM":  "MA0000012320",
    "LES":  "MA0000012031",
    "M2M":  "MA0000011678",
    "MOX":  "MA0000010985",
    "MGL":  "MA0000011215",
    "MNG":  "MA0000011058",
    "MRL":  "MA0000010035",
    "IAM":  "MA0000011488",
    "MIC":  "MA0000012163",
    "MUT":  "MA0000012395",
    "OUL":  "MA0000010415",
    "PPM":  "MA0000011660",
    "REB":  "MA0000010993",
    "RDS":  "MA0000012239",
    "RIS":  "MA0000011462",
    "S2M":  "MA0000012106",
    "SLM":  "MA0000012007",
    "SAF":  "MA0000011744",
    "SMI":  "MA0000010068",
    "STK":  "MA0000011843",
    "SNP":  "MA0000011728",
    "MSA":  "MA0000012312",
    "SON":  "MA0000010019",
    "SOT":  "MA0000012502",
    "SRM":  "MA0000011595",
    "SBS":  "MA0000010365",
    "STR":  "MA0000012056",
    "TQA":  "MA0000012205",
    "TGC":  "MA0000012528",
    "TIM":  "MA0000011686",
    "TMA":  "MA0000012262",
    "UNI":  "MA0000012023",
    "WAF":  "MA0000010928",
    "ZLD":  "MA0000010571",
    # Nouvelles IPO
    "CFGB": "MA0000012627",
    "CMGP": "MA0000012718",
    "VCNE": "MA0000012759",
    "CASH": "MA0000012767",
    "SGTM": "MA0000012783",
}

TICKERS_DEFAUT = [
    "SMI", "MNG", "RIS", "RDS", "CSR", "SOT",
    "ADI", "MSA", "ADH", "TGC", "CMT", "SRM",
    "CFGB", "CMGP", "VCNE", "CASH", "SGTM"
]

# ============================================================
# CALENDRIER MARCHE
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
        if now.weekday() >= 5: return "WEEKEND"
        open_t  = now.replace(hour=9,  minute=30, second=0, microsecond=0)
        close_t = now.replace(hour=15, minute=30, second=0, microsecond=0)
        post_t  = now.replace(hour=15, minute=45, second=0, microsecond=0)
        if now < open_t:             return "PRE_MARKET"
        if open_t <= now <= close_t: return "OPEN"
        if close_t < now <= post_t:  return "POST_CLOSE"
        return "CLOSED"

    @staticmethod
    def message():
        s   = MarketCalendar.status()
        now = MarketCalendar.now()
        h   = now.strftime("%H:%M")
        return {
            "OPEN":       f"Marche OUVERT | Casablanca : {h}",
            "POST_CLOSE": f"Post-cloture | Casablanca : {h}",
            "PRE_MARKET": f"Avant ouverture | Casablanca : {h}",
            "WEEKEND":    f"Weekend | Casablanca : {h}",
            "CLOSED":     f"Marche ferme | Casablanca : {h}"
        }.get(s, f"Casablanca : {h}")

# ============================================================
# SAFE MATH
# ============================================================

class SafeMath:
    @staticmethod
    def to_float(value):
        if value is None: return np.nan
        if isinstance(value, (list, dict, tuple)): return np.nan
        try:
            if pd.isna(value): return np.nan
        except: pass
        if isinstance(value, str):
            value = value.replace("\xa0"," ").replace(" "," ").replace(" ","").replace(",",".").replace("%","").strip()
            if value in ["","-","N/A","nan","None"]: return np.nan
        try: return float(value)
        except: return np.nan

    @staticmethod
    def last(series):
        s = series.dropna()
        return s.iloc[-1] if not s.empty else np.nan

    @staticmethod
    def prev(series, n=2):
        s = series.dropna()
        return s.iloc[-n] if len(s) >= n else np.nan

    @staticmethod
    def pct_change(a, b):
        if b == 0 or pd.isna(a) or pd.isna(b): return np.nan
        return round((a/b-1)*100, 2)

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
    MOMENTUM_CONFIRME  = "MOMENTUM CONFIRME"
    BREAKOUT_POTENTIEL = "BREAKOUT POTENTIEL"
    PULLBACK_HAUSSIER  = "PULLBACK HAUSSIER"
    CONTRARIEN         = "CONTRARIEN"
    ACCUMULATION_LENTE = "ACCUMULATION LENTE"
    FAIBLESSE          = "FAIBLESSE"
    NEUTRE             = "NEUTRE"

class Severity(Enum):
    CRITIQUE = "CRITIQUE"
    ELEVEE   = "ELEVEE"
    MOYENNE  = "MOYENNE"
    FAIBLE   = "FAIBLE"

# Ordre de sévérité pour tri dans la note
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
        if self.max_score <= 0: return 0
        return round(min(10, self.score/self.max_score*10), 2)

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
    score_global: float; red_flags: List[RedFlag]
    valuation: Valuation; technical_data: Dict[str, Any]
    fundamental_data: Dict[str, Any]
    live_data: Dict[str, Any] = field(default_factory=dict)
    market_status: str = "UNKNOWN"
    institutional_note: str = ""

# ============================================================
# CONNECTEUR MEDIAS24
# ============================================================

class Medias24Connector:
    BASE_URL = "https://medias24.com/content/api"
    HEADERS  = {"User-Agent": "Mozilla/5.0"}

    def __init__(self, isin_map: dict):
        self.isin_map  = isin_map
        self.available = False
        self.checked   = False

    def _get(self, params: dict, timeout=10):
        try:
            r = requests.get(
                self.BASE_URL,
                params={**params, "format": "json"},
                headers=self.HEADERS,
                timeout=timeout
            )
            if r.status_code == 200 and len(r.text) > 50:
                return json.loads(r.text)
        except Exception as e:
            logger.debug(f"Medias24 erreur : {e}")
        return None

    def preload(self):
        if self.checked: return self.available
        self.checked = True
        test = self._get({"method": "getStockInfo", "ISIN": "MA0000010068"}, timeout=8)
        if test and test.get("result"):
            self.available = True
            logger.info("Medias24 : disponible")
        else:
            logger.warning("Medias24 : indisponible")
        return self.available

    def get_historique(self, ticker: str, days: int = 730) -> pd.DataFrame:
        isin = self.isin_map.get(ticker.upper())
        if not isin:
            logger.warning(f"{ticker} : ISIN introuvable")
            return pd.DataFrame()

        end   = datetime.now().strftime("%Y-%m-%d")
        start = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")

        data = self._get({"method": "getPriceHistory", "ISIN": isin, "from": start, "to": end})
        if not data or not data.get("result"):
            return pd.DataFrame()

        records = data["result"]
        df = pd.DataFrame({
            "date":   [r.get("date")                          for r in records],
            "close":  [SafeMath.to_float(r.get("value"))     for r in records],
            "high":   [SafeMath.to_float(r.get("max"))       for r in records],
            "low":    [SafeMath.to_float(r.get("min"))       for r in records],
            "volume": [SafeMath.to_float(r.get("volume", 0)) for r in records],
        })

        df["date"] = pd.to_datetime(df["date"], dayfirst=True, errors="coerce")
        df["open"] = df["close"].shift(1).fillna(df["close"])
        df = df.dropna(subset=["date","close","high","low"])
        df = df.sort_values("date").reset_index(drop=True)
        df = self._adjust_splits(df, ticker)

        logger.info(f"Medias24 {ticker} : {len(df)} lignes | {df['close'].iloc[-1]} DH")
        return df

    def _adjust_splits(self, df: pd.DataFrame, ticker: str) -> pd.DataFrame:
        df   = df.copy().sort_values("date").reset_index(drop=True)
        rets = df["close"].pct_change()
        splits = rets[rets < -0.4].index.tolist()
        if splits:
            for idx in splits:
                ratio = df.loc[idx, "close"] / df.loc[idx-1, "close"]
                logger.info(f"Split detecte {ticker} a {df.loc[idx,'date'].date()} — ratio {ratio:.4f}")
                for col in ["close","open","high","low"]:
                    df.loc[:idx-1, col] = df.loc[:idx-1, col] * ratio
        return df

    def get_live(self, ticker: str) -> dict:
        isin = self.isin_map.get(ticker.upper())
        if not isin or not self.available: return {}

        data = self._get({"method": "getStockInfo", "ISIN": isin})
        if not data or not data.get("result"): return {}

        r = data["result"]
        cours = SafeMath.to_float(r.get("cours"))
        return {
            "cours":      cours,
            "ouverture":  SafeMath.to_float(r.get("ouverture")),
            "variation":  SafeMath.to_float(r.get("variation")),
            "volume_mad": SafeMath.to_float(r.get("volume")),
            "quantite":   SafeMath.to_float(r.get("volumeTitre")),
            # ✅ haut/bas depuis les vrais champs API (fallback sur cours)
            "haut":       SafeMath.to_float(r.get("max") or r.get("haut") or cours),
            "bas":        SafeMath.to_float(r.get("min") or r.get("bas")  or cours),
            "source":     "Medias24",
            "timestamp":  MarketCalendar.now().strftime("%H:%M:%S")
        }

# ============================================================
# HISTORIQUE LOCAL
# ============================================================

class HistoryStore:
    def __init__(self, base_path="data/historique"):
        self.base = Path(base_path)
        self.base.mkdir(parents=True, exist_ok=True)

    def path(self, ticker):
        return self.base / f"{ticker.upper()}.xlsx"

    def load(self, ticker):
        p = self.path(ticker)
        if not p.exists(): return pd.DataFrame()
        try:
            df = pd.read_excel(p)
            df["date"] = pd.to_datetime(df["date"], errors="coerce")
            return df.dropna(subset=["date"])
        except Exception:
            return pd.DataFrame()

    def save(self, ticker, df):
        df = df.copy()
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
        df = df.dropna(subset=["date"])
        df = df.sort_values("date").drop_duplicates(subset=["date"], keep="last").reset_index(drop=True)
        df.to_excel(self.path(ticker), index=False)
        return df

# ============================================================
# INDICATEURS TECHNIQUES
# ============================================================

class TechnicalIndicators:
    @staticmethod
    def calculate_all(df):
        df = df.copy()
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

        ll            = df["low"].rolling(14).min()
        hh            = df["high"].rolling(14).max()
        df["Stoch_K"] = (100*(df["close"]-ll)/(hh-ll).replace(0,np.nan)).fillna(50)
        df["Stoch_D"] = df["Stoch_K"].rolling(3).mean().fillna(50)

        vol_ma              = df["volume"].rolling(20).mean().replace(0, np.nan)
        df["Vol_MA20"]      = vol_ma
        df["Volume_Ratio"]  = df["volume"] / vol_ma
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
        return df

# ============================================================
# SCORING TECHNIQUE
# ============================================================

class TechnicalScorer:
    def score(self, df):
        m     = SafeMath()
        score = 0; maxs = 0; reasons = []

        p      = m.last(df["close"]);  ma20  = m.last(df["MA20"])
        ma50   = m.last(df["MA50"]);   ma200 = m.last(df["MA200"])
        rsi    = m.last(df["RSI"])
        macd   = m.last(df["MACD"]);   sig   = m.last(df["MACD_SIGNAL"])
        hist   = m.last(df["MACD_HIST"]); histp = m.prev(df["MACD_HIST"])
        vr     = m.last(df["Volume_Ratio"])
        sk     = m.last(df["Stoch_K"]); sd   = m.last(df["Stoch_D"])
        bbu    = m.last(df["BB_upper"]); bbl  = m.last(df["BB_lower"])
        bbw    = m.last(df["BB_width"])
        tenkan = m.last(df["tenkan"]); kijun  = m.last(df["kijun"])
        ka     = m.last(df["kumo_a"]); kb     = m.last(df["kumo_b"])
        ret5   = m.last(df["Return_5D"]); vol20 = m.last(df["Volatility_20"])

        nuage_h = max(ka,kb) if not pd.isna(ka) and not pd.isna(kb) else np.nan
        nuage_b = min(ka,kb) if not pd.isna(ka) and not pd.isna(kb) else np.nan

        maxs += 3
        if not any(pd.isna(x) for x in [p, ma20, ma50]):
            if p > ma20 > ma50:   score += 3; reasons.append("✅ Tendance haussiere forte")
            elif p < ma20 < ma50: reasons.append("❌ Tendance baissiere confirmee")
            else:                 score += 1; reasons.append("⚠️ Moyennes mobiles mixtes")

        maxs += 2
        if not pd.isna(ma200) and not pd.isna(p):
            if p > ma200: score += 2 if p > ma200*1.05 else 1; reasons.append("✅ Prix au-dessus MA200")
            else: reasons.append("❌ Prix sous MA200")

        maxs += 3
        if not any(pd.isna(x) for x in [macd, sig, hist, histp]):
            if macd > sig and hist > histp > 0: score += 3; reasons.append("✅ MACD haussier accelerant")
            elif macd > sig:                    score += 2; reasons.append("✅ MACD haussier")
            elif macd < sig and hist < histp:   reasons.append("❌ MACD baissier degrade")
            else:                               score += 0.5; reasons.append("⚠️ MACD en stabilisation")

        maxs += 2
        if not pd.isna(rsi):
            if 40 <= rsi <= 60:  score += 2; reasons.append(f"✅ RSI equilibre : {rsi:.1f}")
            elif 60 < rsi <= 70: score += 1; reasons.append(f"⚠️ RSI positif a surveiller : {rsi:.1f}")
            elif rsi > 70:       reasons.append(f"❌ RSI surchauffe : {rsi:.1f}")
            else:                score += 1; reasons.append(f"⚠️ RSI bas : {rsi:.1f}")

        maxs += 3
        if not pd.isna(nuage_h) and not pd.isna(p):
            if p > nuage_h and not pd.isna(tenkan) and not pd.isna(kijun) and tenkan > kijun:
                score += 3; reasons.append("✅ Ichimoku positif")
            elif p > nuage_h:                    score += 2; reasons.append("⚠️ Prix au-dessus du nuage")
            elif not pd.isna(nuage_b) and p > nuage_b: score += 1; reasons.append("⚠️ Prix dans le nuage")
            else:                                reasons.append("❌ Prix sous le nuage")

        maxs += 2
        if not any(pd.isna(x) for x in [sk, sd]):
            if sk < 20 and sk > sd:  score += 2; reasons.append("✅ Stochastique sortie de survente")
            elif sk > 80:            score += 0.5; reasons.append("⚠️ Stochastique surachat")
            else:                    score += 1; reasons.append("⚠️ Stochastique neutre")

        maxs += 2
        if not any(pd.isna(x) for x in [p, bbu, bbl]):
            if p < bbl and not pd.isna(rsi) and rsi < 40:
                score += 2; reasons.append("✅ Rebond Bollinger possible")
            elif p > bbu and not pd.isna(rsi) and rsi > 65:
                reasons.append("❌ Exces Bollinger")
            elif not pd.isna(bbw) and bbw < 0.05:
                score += 1.5; reasons.append("⚠️ Squeeze Bollinger")
            else:
                score += 1; reasons.append("⚠️ Bollinger neutre")

        maxs += 2
        if not pd.isna(vr):
            if vr >= 2 and not pd.isna(p) and not pd.isna(ma20) and p > ma20:
                score += 2; reasons.append("✅ Volume fort confirme")
            elif vr >= 1.2: score += 1;   reasons.append("⚠️ Volume superieur moyenne")
            elif vr < 0.15: reasons.append("❌ Volume tres faible")
            elif vr < 0.5:  score += 0.5; reasons.append("⚠️ Volume faible")
            else:           score += 1;   reasons.append("⚠️ Volume modere")

        maxs += 1
        if not pd.isna(ret5):
            score += 1 if abs(ret5) <= 5 else 0.5
            reasons.append(f"{'✅' if abs(ret5)<=5 else '⚠️'} Momentum 5j : {ret5:.1f}%")

        maxs += 1
        if not pd.isna(vol20):
            if vol20 < 1.5:   score += 1;   reasons.append(f"✅ Volatilite faible : {vol20:.1f}%")
            elif vol20 <= 5:  score += 0.5; reasons.append(f"⚠️ Volatilite moderee : {vol20:.1f}%")
            else:             reasons.append(f"❌ Volatilite elevee : {vol20:.1f}%")

        return ScoreResult(score, maxs, reasons, {
            "prix": p, "ma20": ma20, "ma50": ma50, "ma200": ma200,
            "rsi": rsi, "macd": macd, "vol_ratio": vr, "stoch_k": sk
        })

# ============================================================
# FONDAMENTAL — v3.4 corrigé
# ============================================================

class FundamentalScorer:
    def __init__(self, f):
        self.raw  = f or {}
        self.math = SafeMath()
        self.f    = self._normalize(self.raw)

    def _normalize(self, d):
        mapping = {
            "per":                  ["per","PER"],
            "forward_per":          ["forward_per"],          # ✅ ajouté
            "croissance_ca":        ["croissance_ca","croissance","growth"],
            "dette_nette_ebitda":   ["dette_nette_ebitda","dette"],
            "div_yield":            ["div_yield","dividende"],
            "roic":                 ["roic","ROIC"],
            "wacc":                 ["wacc","WACC"],
            "cash_conversion":      ["cash_conversion"],
            "marge_nette":          ["marge_nette","marge"],
            "momentum_fondamental": ["momentum_fondamental","momentum"],  # ✅ ajouté
            "rerating":             ["rerating"],                          # ✅ ajouté
            "cycle_commodities":    ["cycle_commodities","cycle"],         # ✅ ajouté
            "secteur":              ["secteur"],
            "catalyseur":           ["catalyseur"]
        }
        out = {}
        for k, alts in mapping.items():
            for a in alts:
                if a in d and d[a] is not None:
                    out[k] = d[a]; break
        return out

    def score(self):
        if not self.f:
            return ScoreResult(0, 12, ["❌ Pas de donnees fondamentales"])

        m = self.math; score = 0; maxs = 0; r = []

        per         = m.to_float(self.f.get("per"))
        forward_per = m.to_float(self.f.get("forward_per"))   # ✅
        g           = m.to_float(self.f.get("croissance_ca"))
        d           = m.to_float(self.f.get("dette_nette_ebitda"))
        div         = m.to_float(self.f.get("div_yield"))
        roic        = m.to_float(self.f.get("roic"))
        wacc        = m.to_float(self.f.get("wacc"))
        cash        = m.to_float(self.f.get("cash_conversion"))
        marge       = m.to_float(self.f.get("marge_nette"))
        momentum    = str(self.f.get("momentum_fondamental", "")).lower()  # ✅
        rerating    = bool(self.f.get("rerating", False))                  # ✅
        cycle       = str(self.f.get("cycle_commodities", "")).lower()    # ✅

        # PER courant (max 2)
        maxs += 2
        if not pd.isna(per):
            if per < 8:    score += 2;    r.append("✅ PER tres attractif")
            elif per < 12: score += 1.75; r.append("✅ PER attractif")
            elif per < 18: score += 1.25; r.append("⚠️ PER raisonnable")
            elif per < 25: score += 0.5;  r.append("⚠️ PER exigeant")
            else:                         r.append("❌ PER eleve")

        # Forward PER ✅ (max 1)
        maxs += 1
        if not pd.isna(forward_per) and not pd.isna(per):
            contraction = per - forward_per
            if forward_per < 10 and contraction >= 2:
                score += 1;    r.append(f"✅ Forward PER tres attractif : {forward_per}x")
            elif forward_per < 14 and contraction >= 1:
                score += 0.75; r.append(f"✅ Forward PER attractif : {forward_per}x")
            elif forward_per < per:
                score += 0.5;  r.append(f"⚠️ Forward PER en amelioration : {forward_per}x")

        # Croissance CA (max 2)
        maxs += 2
        if not pd.isna(g):
            if g > 20:   score += 2;   r.append("✅ Croissance forte")
            elif g > 15: score += 1.5; r.append("✅ Croissance solide")
            elif g > 8:  score += 1;   r.append("⚠️ Croissance correcte")
            elif g > 0:  score += 0.5; r.append("⚠️ Croissance faible")
            else:                      r.append("❌ Croissance negative")

        # Dette/EBITDA (max 2)
        maxs += 2
        if not pd.isna(d):
            if d <= 1:   score += 2;    r.append("✅ Dette tres faible")
            elif d <= 2: score += 1.75; r.append("✅ Dette faible")
            elif d <= 3: score += 1;    r.append("⚠️ Dette moderee")
            elif d <= 4: score += 0.25; r.append("⚠️ Dette elevee")
            else:                       r.append("❌ Dette tres elevee")

        # ROIC/WACC (max 2)
        maxs += 2
        if not pd.isna(roic) and not pd.isna(wacc):
            s = roic - wacc
            if s >= 5:   score += 2;   r.append("✅ Forte creation de valeur")
            elif s >= 2: score += 1.5; r.append("✅ Creation de valeur")
            elif s >= 0: score += 0.5; r.append("⚠️ Creation de valeur faible")
            else:                      r.append("❌ ROIC inferieur au WACC")

        # Cash conversion (max 1)
        maxs += 1
        if not pd.isna(cash):
            if cash >= 80:   score += 1;    r.append("✅ Cash conversion excellente")
            elif cash >= 65: score += 0.75; r.append("✅ Cash conversion correcte")
            elif cash >= 50: score += 0.5;  r.append("⚠️ Cash conversion moyenne")
            else:                           r.append("❌ Cash conversion faible")

        # Marge nette (max 1)
        maxs += 1
        if not pd.isna(marge):
            if marge >= 18:   score += 1;    r.append("✅ Marge nette elevee")
            elif marge >= 12: score += 0.75; r.append("✅ Marge solide")
            elif marge >= 7:  score += 0.5;  r.append("⚠️ Marge correcte")
            else:                            r.append("❌ Marge faible")

        # Dividende (max 1)
        maxs += 1
        if not pd.isna(div):
            if div > 4:     score += 1;    r.append("✅ Dividende eleve")
            elif div > 2.5: score += 0.75; r.append("✅ Dividende correct")
            elif div > 1:   score += 0.25; r.append("⚠️ Dividende modeste")

        # Momentum / Re-rating / Cycle ✅ (max 1)
        maxs += 1
        bonus = 0.0
        if momentum in ["très positif", "tres positif"]:
            bonus += 0.5; r.append("✅ Momentum fondamental tres positif")
        elif momentum == "positif":
            bonus += 0.3; r.append("✅ Momentum fondamental positif")
        elif "négatif" in momentum or "negatif" in momentum:
            r.append("❌ Momentum fondamental negatif")
        if rerating:
            bonus += 0.3; r.append("✅ Re-rating potentiel identifie")
        if cycle == "bullish":
            bonus += 0.2; r.append("✅ Cycle commodites favorable")
        elif cycle in ["bearish", "baissier"]:
            r.append("❌ Cycle commodites defavorable")
        score += min(bonus, 1.0)

        return ScoreResult(score, maxs, r)

# ============================================================
# RED FLAGS
# ============================================================

class RedFlagDetector:
    def __init__(self, f):
        self.f = FundamentalScorer(f).f
        self.m = SafeMath()

    def detect(self, df):
        flags = []
        d     = self.m.to_float(self.f.get("dette_nette_ebitda"))
        cash  = self.m.to_float(self.f.get("cash_conversion"))
        roic  = self.m.to_float(self.f.get("roic"))
        wacc  = self.m.to_float(self.f.get("wacc"))
        marge = self.m.to_float(self.f.get("marge_nette"))
        p     = self.m.last(df["close"]); ma20  = self.m.last(df["MA20"])
        ma50  = self.m.last(df["MA50"]);  rsi   = self.m.last(df["RSI"])
        vr    = self.m.last(df["Volume_Ratio"]); ret20 = self.m.last(df["Return_20D"])

        if not pd.isna(d):
            if d > 5:   flags.append(RedFlag(Severity.CRITIQUE,"Structure","Dette/EBITDA critique",True))
            elif d > 4: flags.append(RedFlag(Severity.ELEVEE,"Structure","Dette elevee"))
            elif d > 3: flags.append(RedFlag(Severity.MOYENNE,"Structure","Endettement eleve"))

        if not pd.isna(cash):
            if cash < 30:   flags.append(RedFlag(Severity.CRITIQUE,"Cash-flow","Cash conversion critique",True))
            elif cash < 50: flags.append(RedFlag(Severity.MOYENNE,"Cash-flow","Cash conversion faible"))

        if not pd.isna(roic) and not pd.isna(wacc) and roic < wacc:
            flags.append(RedFlag(Severity.ELEVEE,"Rentabilite","ROIC inferieur au WACC"))

        if not pd.isna(marge) and marge < 5:
            flags.append(RedFlag(Severity.MOYENNE,"Rentabilite","Marge nette faible"))

        if not any(pd.isna(x) for x in [p, ma20, ma50]) and p < ma20 < ma50:
            flags.append(RedFlag(Severity.ELEVEE,"Technique","Tendance baissiere court/moyen terme"))

        if not pd.isna(rsi):
            if rsi > 80:   flags.append(RedFlag(Severity.CRITIQUE,"Technique","RSI surchauffe extreme",True))
            elif rsi > 75: flags.append(RedFlag(Severity.ELEVEE,"Technique","RSI surchauffe"))

        if not pd.isna(vr):
            if vr < 0.15:  flags.append(RedFlag(Severity.CRITIQUE,"Liquidite","Volume tres faible",True))
            elif vr < 0.3: flags.append(RedFlag(Severity.MOYENNE,"Liquidite","Volume faible"))

        if not pd.isna(ret20):
            if ret20 < -25:   flags.append(RedFlag(Severity.CRITIQUE,"Momentum","Correction forte sur 20j",True))
            elif ret20 < -15: flags.append(RedFlag(Severity.ELEVEE,"Momentum","Correction sur 20j"))

        return flags

# ============================================================
# SETUP DETECTOR — ✅ ROBUSTE AUX NaN
# ============================================================

class SetupDetector:
    def detect(self, df):
        m      = SafeMath()
        p      = m.last(df["close"]);  ma20   = m.last(df["MA20"])
        ma50   = m.last(df["MA50"]);   rsi    = m.last(df["RSI"])
        vr     = m.last(df["Volume_Ratio"])
        high20 = m.last(df["High_20"]); low20 = m.last(df["Low_20"])
        macd   = m.last(df["MACD"]);   sig    = m.last(df["MACD_SIGNAL"])

        # ✅ Conditions indépendantes — plus de return NEUTRE global si 1 valeur manque
        has_trend = not any(pd.isna(x) for x in [p, ma20, ma50])
        has_rsi   = not pd.isna(rsi)
        has_macd  = not any(pd.isna(x) for x in [macd, sig])
        has_vr    = not pd.isna(vr)

        if has_trend and has_rsi and p < ma20 < ma50 and rsi < 48:
            return Setup.FAIBLESSE

        if has_trend and has_rsi and has_macd and p > ma20 > ma50 and rsi > 52 and macd > sig:
            if not has_vr or vr >= 1.2:
                return Setup.MOMENTUM_CONFIRME

        if has_trend and has_macd and not pd.isna(high20) and p >= high20*0.98 and macd > sig:
            if not has_vr or vr >= 1.3:
                return Setup.BREAKOUT_POTENTIEL

        if has_trend and has_rsi and p > ma50 and ma20 > ma50 and 40 <= rsi <= 58 and p <= ma20*1.02:
            return Setup.PULLBACK_HAUSSIER

        if has_rsi and not pd.isna(low20) and p <= low20*1.06:
            stk = m.last(df["Stoch_K"])
            if rsi < 38 or (not pd.isna(stk) and stk < 25):
                return Setup.CONTRARIEN

        if has_trend and has_rsi and has_macd and p > ma50 and 45 <= rsi <= 60 and macd > sig:
            if not has_vr or vr < 0.8:
                return Setup.ACCUMULATION_LENTE

        return Setup.NEUTRE

# ============================================================
# DECISION ENGINE — ✅ 1 FLAG CRITIQUE/BLOQUANT SUFFIT
# ============================================================

class DecisionEngine:
    def decide(self, st, sf, setup, flags):
        score    = round(st.normalized*0.65 + sf.normalized*0.35, 2)

        # ✅ 1 seul flag CRITIQUE ou is_blocking = EVITER immédiat
        critical = [f for f in flags if f.severity == Severity.CRITIQUE]
        blocking = [f for f in flags if f.is_blocking]
        if critical or blocking:
            msg = critical[0].message if critical else blocking[0].message
            return Signal.EVITER, f"EVITER — {msg}", score

        if score >= 7 and setup in [Setup.MOMENTUM_CONFIRME, Setup.BREAKOUT_POTENTIEL]:
            return Signal.ACHETER,    f"ACHETER — {setup.value}",              score
        if score >= 6.5 and setup == Setup.PULLBACK_HAUSSIER:
            return Signal.ACHETER,    "ACHETER — pullback haussier",           score
        if score >= 6 and setup == Setup.ACCUMULATION_LENTE:
            return Signal.ACCUMULER,  "ACCUMULER — accumulation progressive",  score
        if score >= 5.5:
            return Signal.SURVEILLER, f"SURVEILLER — {setup.value}",          score
        if score >= 4:
            return Signal.ATTENDRE,   f"ATTENDRE — {setup.value}",            score
        return Signal.EVITER, f"EVITER — {setup.value}", score

# ============================================================
# VALORISATION — ✅ TARGETS JSON EN PRIORITÉ
# ============================================================

class ValuationEngine:
    def __init__(self, f):
        self.raw = f or {}                   # ✅ raw pour accéder aux targets JSON
        self.f   = FundamentalScorer(f).f
        self.m   = SafeMath()

    def calculate(self, price):
        m = self.m

        # ✅ PRIORITÉ 1 : objectifs analyst depuis fondamentaux.json
        target = m.to_float(self.raw.get("target_price"))
        bear_t = m.to_float(self.raw.get("bear_case"))
        bull_t = m.to_float(self.raw.get("bull_case"))

        if not any(pd.isna(x) for x in [target, bear_t, bull_t]):
            return Valuation(
                base=round(target, 2), bull=round(bull_t, 2), bear=round(bear_t, 2),
                upside_base=m.pct_change(target, price),
                upside_bull=m.pct_change(bull_t, price),
                downside=m.pct_change(bear_t, price),
                premium_pct=None,
                methodology="Objectifs analyst JSON",
                confidence="Haute"
            )

        # PRIORITÉ 2 : multi-facteurs (fallback)
        per  = m.to_float(self.f.get("per"))
        g    = m.to_float(self.f.get("croissance_ca"))
        roic = m.to_float(self.f.get("roic"))
        wacc = m.to_float(self.f.get("wacc"))
        d    = m.to_float(self.f.get("dette_nette_ebitda"))
        cash = m.to_float(self.f.get("cash_conversion"))

        if pd.isna(per) or pd.isna(g):
            return Valuation(None,None,None,None,None,None,None,"Insuffisant","Faible")

        prem = 0.0
        if g > 20: prem += .15
        elif g > 15: prem += .10
        elif g > 8: prem += .05
        elif g < 0: prem -= .10

        if not pd.isna(roic) and not pd.isna(wacc):
            sp = roic - wacc
            if sp >= 5: prem += .12
            elif sp >= 2: prem += .07
            elif sp < 0: prem -= .10

        if per < 8: prem += .12
        elif per < 12: prem += .08
        elif per > 28: prem -= .15
        elif per > 22: prem -= .08

        if not pd.isna(cash):
            if cash >= 80: prem += .05
            elif cash < 40: prem -= .08

        if not pd.isna(d):
            if d > 4: prem -= .10
            elif d > 3: prem -= .05
            elif d < 1: prem += .05

        base = round(price*(1+prem),2)
        bull = round(base*1.25,2)
        bear = round(base*.78,2)
        return Valuation(base,bull,bear,
            m.pct_change(base,price), m.pct_change(bull,price),
            m.pct_change(bear,price), round(prem*100,1),
            "Multi-facteurs","Moyenne" if abs(prem)<0.2 else "Haute")

# ============================================================
# NOTE — ✅ TRIÉE PAR SÉVÉRITÉ + EVA
# ============================================================

class NoteGenerator:
    def generate(self, r):
        f    = FundamentalScorer(r.fundamental_data).f
        live = r.live_data or {}
        tech = "\n".join([f"  * {x}" for x in r.score_technical.reasons])
        fond = "\n".join([f"  * {x}" for x in r.score_fundamental.reasons])

        # ✅ Flags triés par sévérité : CRITIQUE → ELEVEE → MOYENNE → FAIBLE
        flags = "\n".join([
            f"  {x.severity.value} | {x.category} : {x.message}" + (" [BLOQUANT]" if x.is_blocking else "")
            for x in sorted(r.red_flags, key=lambda x: _SEV_ORDER[x.severity])
        ]) if r.red_flags else "  OK Aucun red flag majeur"

        # ✅ EVA calculé et affiché
        roic_v = SafeMath.to_float(r.fundamental_data.get("roic"))
        wacc_v = SafeMath.to_float(r.fundamental_data.get("wacc"))
        if not pd.isna(roic_v) and not pd.isna(wacc_v):
            spread = roic_v - wacc_v
            eva_txt = f"+{spread:.1f} pts ✅ creation de valeur" if spread >= 0 else f"{spread:.1f} pts ❌ destruction de valeur"
        else:
            eva_txt = "N/A"

        val_src = r.valuation.methodology if r.valuation.base else "N/A"

        return f"""
================================================================================
NOTE INSTITUTIONNELLE — {r.ticker}
BVC ULTIMATE ANALYZER v3.4 MEDIAS24 | {r.date.strftime('%d/%m/%Y %H:%M')}
================================================================================
MARCHE  : {r.market_status} | {MarketCalendar.message()}

SYNTHESE
  Prix        : {r.price:.2f} DH
  Signal      : {r.action}
  Setup       : {r.setup.value}
  Technique   : {r.score_technical.normalized}/10
  Fondamental : {r.score_fundamental.normalized}/10
  Global      : {r.score_global}/10
  Source      : {live.get('source','Medias24')}
  Cours live  : {live.get('cours','N/A')} DH
  Variation   : {live.get('variation','N/A')} %
  Volume      : {live.get('volume_mad','N/A')}

ANALYSE TECHNIQUE
{tech}

ANALYSE FONDAMENTALE
  PER : {f.get('per','N/A')}x | Forward PER : {f.get('forward_per','N/A')}x | Croissance : {f.get('croissance_ca','N/A')}%
  Dette : {f.get('dette_nette_ebitda','N/A')}x | ROIC/WACC : {f.get('roic','N/A')}/{f.get('wacc','N/A')}
  Cash : {f.get('cash_conversion','N/A')}% | Marge : {f.get('marge_nette','N/A')}%
  EVA (ROIC - WACC) : {eva_txt}
{fond}

RED FLAGS
{flags}

VALORISATION ({val_src})
  Bear : {r.valuation.bear} DH | Base : {r.valuation.base} DH ({r.valuation.upside_base}%) | Bull : {r.valuation.bull} DH

RECOMMANDATION : {r.action}
Catalyseur : {f.get('catalyseur','N/A')}
================================================================================
"""

# ============================================================
# ANALYSEUR PRINCIPAL
# ============================================================

class BVCAnalyzer:
    def __init__(self):
        self.connector          = Medias24Connector(ISIN_MAP)
        self.history            = HistoryStore()
        self.fundamentals_cache = {}
        self.last_fetch         = None

    def fetch_fundamentals(self):
        if self.last_fetch and datetime.now() - self.last_fetch < timedelta(hours=6):
            return
        try:
            r = requests.get(GITHUB_URL, timeout=20)
            r.raise_for_status()
            self.fundamentals_cache = r.json()
            self.last_fetch = datetime.now()
            logger.info(f"Fondamentaux GitHub : {len(self.fundamentals_cache)} tickers")
        except Exception as e:
            logger.warning(f"GitHub indisponible : {e}")

    def analyze(self, ticker: str) -> Optional[AnalysisResult]:
        self.fetch_fundamentals()

        df = self.connector.get_historique(ticker, days=730)
        if df.empty:
            logger.warning(f"{ticker} : pas de donnees Medias24")
            return None

        df = self.history.save(ticker, df)

        if len(df) < 50:
            logger.warning(f"{ticker} : historique insuffisant ({len(df)} lignes)")
            return None

        live = self.connector.get_live(ticker) if self.connector.available else {}
        df   = TechnicalIndicators.calculate_all(df)

        price        = SafeMath.last(df["close"])
        fundamentals = self.fundamentals_cache.get(ticker.upper(), {})

        score_tech             = TechnicalScorer().score(df)
        score_fond             = FundamentalScorer(fundamentals).score()
        flags                  = RedFlagDetector(fundamentals).detect(df)
        setup                  = SetupDetector().detect(df)
        signal, action, score_global = DecisionEngine().decide(score_tech, score_fond, setup, flags)
        valuation              = ValuationEngine(fundamentals).calculate(price)

        result = AnalysisResult(
            ticker=ticker, price=price,
            date=MarketCalendar.now().replace(tzinfo=None),
            setup=setup, signal=signal, action=action,
            score_technical=score_tech, score_fundamental=score_fond,
            score_global=score_global, red_flags=flags,
            valuation=valuation, technical_data=score_tech.raw_details,
            fundamental_data=fundamentals, live_data=live,
            market_status=MarketCalendar.status()
        )
        result.institutional_note = NoteGenerator().generate(result)
        return result

# ============================================================
# MAIN
# ============================================================

def main():
    now = MarketCalendar.now()
    print("="*80)
    print("BVC ULTIMATE ANALYZER v3.4 — MEDIAS24 (corrections appliquées)")
    print("80 titres | Nouvelles IPO incluses | Sans Excel")
    print("="*80)
    print(f"Heure Casablanca : {now.strftime('%H:%M:%S')}")
    print(f"Statut marche    : {MarketCalendar.status()}")
    print(f"Message          : {MarketCalendar.message()}")

    analyzer = BVCAnalyzer()

    print("\nTest Medias24...", end=" ")
    ok = analyzer.connector.preload()
    print("✅ DISPONIBLE" if ok else "❌ INDISPONIBLE")

    print(f"\nAnalyse de {len(TICKERS_DEFAUT)} titres...\n")

    results = {}
    for ticker in TICKERS_DEFAUT:
        try:
            r = analyzer.analyze(ticker)
            if r:
                results[ticker] = r
                print(f"  ✅ {ticker:6} | {r.price:>10.2f} DH | {r.action:<40} | Score {r.score_global}")
                print(r.institutional_note)
            else:
                print(f"  ❌ {ticker:6} | Données indisponibles")
        except Exception as e:
            print(f"  ❌ {ticker:6} | Erreur : {e}")

    if results:
        rows = []
        for r in sorted(results.values(), key=lambda x: x.score_global, reverse=True):
            rows.append({
                "Ticker":       r.ticker,
                "Prix":         r.price,
                "Signal":       r.signal.value,
                "Action":       r.action,
                "Score Global": r.score_global,
                "Technique":    r.score_technical.normalized,
                "Fondamental":  r.score_fundamental.normalized,
                "Setup":        r.setup.value,
                "Red Flags":    len(r.red_flags),
                "Valorisation": r.valuation.methodology,
                "Base":         r.valuation.base,
                "Upside %":     r.valuation.upside_base,
                "Marche":       r.market_status,
                "Heure":        MarketCalendar.now().strftime("%H:%M"),
                "Source":       r.live_data.get("source","Medias24") if r.live_data else "Medias24",
                "Cours Live":   r.live_data.get("cours","N/A")       if r.live_data else "N/A",
                "Variation":    r.live_data.get("variation","N/A")   if r.live_data else "N/A",
            })

        df_out = pd.DataFrame(rows)
        print("\n" + "="*80)
        print("CLASSEMENT GLOBAL")
        print("="*80)
        print(df_out.to_string(index=False))

        export = f"exports/bvc_v34_medias24_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"
        df_out.to_excel(export, index=False)
        print(f"\nExport : {export}")

        try:
            from google.colab import files
            files.download(export)
        except:
            pass

    print("\nANALYSE TERMINEE")
    print("Historiques : data/historique/")
    print("Exports     : exports/")

if __name__ == "__main__":
    main()
