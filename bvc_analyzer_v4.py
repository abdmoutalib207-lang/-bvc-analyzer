# ============================================================
# BVC ULTIMATE ANALYZER v4.0 PRO — INSTITUTIONNEL
# ============================================================
# Auteur    : abdmoutalib207-lang
# Marché    : BVC Casablanca | AMMC | IFRS/CGNC
# WACC ref  : Rf Bons Trésor 10Y ~3% | ERP ~7% → ~10%
# Méthodo   : https://github.com/LKABAL-BVC/claude-skill-annual-report-analyzer
#
# CORRECTIONS v3.3 → v4.0 :
#   ✅ Valorisation utilise targets analyst JSON (target_price/bear/bull)
#   ✅ forward_per intégré dans scoring fondamental
#   ✅ SetupDetector robuste aux NaN (conditions indépendantes)
#   ✅ 1 seul flag CRITIQUE suffit à bloquer la décision
#   ✅ Pondération Tech/Fond dynamique selon liquidité BVC
#   ✅ EVA (Economic Value Added = ROIC – WACC) explicite
#   ✅ Décote liquidité BVC dans valorisation
#   ✅ Note institutionnelle 8 sections
#   ✅ Excel reader avec détection automatique des colonnes
#   ✅ BVC Live connector robuste (SSL + cache + filtrage)
#   ✅ momentum_fondamental, rerating, cycle_commodities utilisés
#   ✅ bpa_2026, dps_2026 affichés dans la note
# ============================================================

import openpyxl
import pandas as pd
import numpy as np
import requests
import logging
import warnings
import urllib3
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Any
from enum import Enum

warnings.filterwarnings("ignore")
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger("BVC")

__version__ = "4.0.0"

# ============================================================
# CONFIGURATION
# ============================================================

GITHUB_URL = "https://raw.githubusercontent.com/abdmoutalib207-lang/-bvc-analyzer/main/fondamentaux.json"
BVC_ACTIONS_URL = "https://www.casablanca-bourse.com/fr/live-market/marche-actions-groupement"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8",
    "Connection": "keep-alive",
}

# Pondérations Tech/Fond selon tier de liquidité
LIQUIDITY_TIERS = {
    "very_low":  {"max_vol": 0.30, "tech": 0.35, "fond": 0.65, "discount": 0.20},
    "low":       {"max_vol": 0.60, "tech": 0.45, "fond": 0.55, "discount": 0.12},
    "normal":    {"max_vol": 1.20, "tech": 0.60, "fond": 0.40, "discount": 0.05},
    "high":      {"max_vol": 2.00, "tech": 0.70, "fond": 0.30, "discount": 0.00},
    "very_high": {"max_vol": float("inf"), "tech": 0.75, "fond": 0.25, "discount": 0.00},
}

# ============================================================
# ENUMS
# ============================================================

class Signal(Enum):
    ACHAT_FORT = "ACHAT FORT"
    ACHETER    = "ACHETER"
    ACCUMULER  = "ACCUMULER"
    SURVEILLER = "SURVEILLER"
    ATTENDRE   = "ATTENDRE"
    EVITER     = "EVITER"

class Setup(Enum):
    MOMENTUM_CONFIRME  = "MOMENTUM CONFIRMÉ"
    BREAKOUT_POTENTIEL = "BREAKOUT POTENTIEL"
    PULLBACK_HAUSSIER  = "PULLBACK HAUSSIER"
    CONTRARIEN         = "CONTRARIEN"
    ACCUMULATION_LENTE = "ACCUMULATION LENTE"
    FAIBLESSE          = "FAIBLESSE"
    NEUTRE             = "NEUTRE"

class Severity(Enum):
    CRITIQUE = "🔴 CRITIQUE"
    ELEVEE   = "🟠 ÉLEVÉE"
    MOYENNE  = "🟡 MOYENNE"
    FAIBLE   = "🔵 FAIBLE"

class ValuationSource(Enum):
    ANALYST_TARGETS = "Objectifs analyst JSON"
    PREMIUM_BASED   = "Multi-facteurs"

# ============================================================
# DATACLASSES
# ============================================================

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
    def normalized(self) -> float:
        if self.max_score <= 0:
            return 0.0
        return round(min(10.0, (self.score / self.max_score) * 10), 2)

@dataclass
class EVAResult:
    roic: float
    wacc: float
    spread: float
    verdict: str
    description: str

@dataclass
class LiquidityProfile:
    vol_ratio: float
    tier: str
    discount_pct: float
    tech_weight: float
    fond_weight: float
    description: str

@dataclass
class Valuation:
    base: Optional[float]
    bull: Optional[float]
    bear: Optional[float]
    upside_base: Optional[float]
    upside_bull: Optional[float]
    downside: Optional[float]
    premium_pct: Optional[float]
    methodology: str
    source: ValuationSource
    liquidity_discount_pct: float
    confidence: str

@dataclass
class AnalysisResult:
    ticker: str
    price: float
    date: datetime
    setup: Setup
    signal: Signal
    action: str
    score_technical: ScoreResult
    score_fundamental: ScoreResult
    score_global: float
    red_flags: List[RedFlag]
    valuation: Valuation
    eva: Optional[EVAResult]
    liquidity: LiquidityProfile
    technical_data: Dict[str, Any]
    fundamental_data: Dict[str, Any]
    live_data: Dict[str, Any] = field(default_factory=dict)
    institutional_note: str = ""
    source_files: List[str] = field(default_factory=list)

# ============================================================
# SAFE MATH
# ============================================================

class SafeMath:
    @staticmethod
    def to_float(value: Any) -> float:
        if value is None:
            return np.nan
        if isinstance(value, (list, dict, tuple)):
            return np.nan
        try:
            if pd.isna(value):
                return np.nan
        except Exception:
            pass
        if isinstance(value, str):
            value = (
                value.replace("\xa0", " ")
                     .replace(" ", " ")
                     .replace(" ", "")
                     .replace(",", ".")
                     .replace("%", "")
                     .strip()
            )
            if value in ["", "-", "N/A", "nan", "—", "/"]:
                return np.nan
        try:
            return float(value)
        except Exception:
            return np.nan

    @staticmethod
    def last(series: pd.Series) -> float:
        s = series.dropna()
        return float(s.iloc[-1]) if not s.empty else np.nan

    @staticmethod
    def prev(series: pd.Series, n: int = 2) -> float:
        s = series.dropna()
        return float(s.iloc[-n]) if len(s) >= n else np.nan

    @staticmethod
    def pct_change(a: float, b: float) -> float:
        if pd.isna(a) or pd.isna(b) or b == 0:
            return np.nan
        return round((a / b - 1) * 100, 2)

    @staticmethod
    def fmt(value: Any, decimals: int = 2) -> str:
        v = SafeMath.to_float(value)
        return f"{v:.{decimals}f}" if not pd.isna(v) else "N/A"

    @staticmethod
    def fmt_pct(value: Any) -> str:
        v = SafeMath.to_float(value)
        if pd.isna(v):
            return "N/A"
        sign = "+" if v > 0 else ""
        return f"{sign}{v:.1f}%"

# ============================================================
# PROFIL LIQUIDITÉ BVC
# ============================================================

class LiquidityAnalyzer:
    @staticmethod
    def analyze(vol_ratio: float) -> LiquidityProfile:
        if pd.isna(vol_ratio):
            return LiquidityProfile(
                vol_ratio=np.nan, tier="normal",
                discount_pct=0.05, tech_weight=0.55, fond_weight=0.45,
                description="Volume inconnu — pondération par défaut"
            )
        for tier, cfg in LIQUIDITY_TIERS.items():
            if vol_ratio < cfg["max_vol"]:
                descriptions = {
                    "very_low":  "Liquidité très faible — signaux techniques peu fiables",
                    "low":       "Liquidité faible — prudence sur les signaux techniques",
                    "normal":    "Liquidité normale BVC",
                    "high":      "Bonne liquidité — signaux techniques fiables",
                    "very_high": "Très forte liquidité — signaux institutionnels",
                }
                return LiquidityProfile(
                    vol_ratio=round(vol_ratio, 2),
                    tier=tier,
                    discount_pct=cfg["discount"],
                    tech_weight=cfg["tech"],
                    fond_weight=cfg["fond"],
                    description=descriptions[tier],
                )
        cfg = LIQUIDITY_TIERS["very_high"]
        return LiquidityProfile(
            vol_ratio=round(vol_ratio, 2), tier="very_high",
            discount_pct=cfg["discount"], tech_weight=cfg["tech"],
            fond_weight=cfg["fond"], description="Très forte liquidité"
        )

# ============================================================
# EVA — ECONOMIC VALUE ADDED
# ============================================================

class EVACalculator:
    @staticmethod
    def calculate(roic: float, wacc: float) -> Optional[EVAResult]:
        if pd.isna(roic) or pd.isna(wacc):
            return None
        spread = round(roic - wacc, 2)
        if spread >= 6:
            verdict = "✅ Création de valeur exceptionnelle"
            desc = f"ROIC dépasse WACC de {spread} pts — avantage concurrentiel fort"
        elif spread >= 3:
            verdict = "✅ Création de valeur solide"
            desc = f"ROIC > WACC de {spread} pts — l'entreprise crée de la valeur économique"
        elif spread >= 0:
            verdict = "⚠️ Création de valeur marginale"
            desc = f"ROIC légèrement au-dessus du WACC (+{spread} pts) — vigilance sur durabilité"
        elif spread >= -3:
            verdict = "🟠 Destruction de valeur modérée"
            desc = f"EVA négatif : ROIC {abs(spread)} pts sous le WACC — dilution des actionnaires"
        else:
            verdict = "🔴 Destruction de valeur sévère"
            desc = f"ROIC {abs(spread)} pts sous le WACC — signal fondamental très négatif"
        return EVAResult(roic=roic, wacc=wacc, spread=spread, verdict=verdict, description=desc)

# ============================================================
# CONNECTEUR BVC LIVE — ROBUSTE
# ============================================================

class BVCLiveConnector:
    _EXPECTED_COLS = [
        "ticker", "nom", "statut", "cours", "veille", "reference",
        "quantite", "volume", "variation", "haut", "bas",
        "meilleure_demande", "meilleure_offre", "qte_demande",
        "qte_offre", "capitalisation", "transactions",
    ]

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(HEADERS)
        self._cache: Optional[pd.DataFrame] = None
        self._cache_time: Optional[datetime] = None
        self._ttl = timedelta(minutes=5)
        self.available = False

    def _get(self, url: str, timeout: int = 20) -> Optional[requests.Response]:
        for verify in (True, False):
            try:
                r = self.session.get(url, timeout=timeout, verify=verify)
                r.raise_for_status()
                return r
            except requests.exceptions.SSLError:
                if verify:
                    continue
                logger.debug("BVC: SSL non vérifiable même sans verify")
                return None
            except Exception as e:
                logger.debug(f"BVC fetch (verify={verify}): {e}")
                return None
        return None

    def _parse_table(self, html: str) -> pd.DataFrame:
        try:
            tables = pd.read_html(html)
        except Exception:
            return pd.DataFrame()
        candidates = [t for t in tables if t.shape[1] >= 8]
        if not candidates:
            return pd.DataFrame()
        df = max(candidates, key=len).copy()
        n = min(len(self._EXPECTED_COLS), df.shape[1])
        df = df.iloc[:, :n]
        df.columns = self._EXPECTED_COLS[:n]
        if "ticker" in df.columns:
            df["ticker"] = df["ticker"].astype(str).str.strip().str.upper()
        skip = {"ticker", "nom", "statut"}
        for col in df.columns:
            if col not in skip:
                df[col] = df[col].apply(SafeMath.to_float)
        df = df[df["ticker"].str.match(r"^[A-Z]{2,6}$", na=False)]
        return df.reset_index(drop=True)

    def fetch_table(self) -> pd.DataFrame:
        if (self._cache is not None
                and self._cache_time is not None
                and datetime.now() - self._cache_time < self._ttl):
            return self._cache
        r = self._get(BVC_ACTIONS_URL)
        if r is None:
            logger.warning("⚠️ BVC Live : site inaccessible")
            self.available = False
            return pd.DataFrame()
        df = self._parse_table(r.text)
        if df.empty:
            logger.warning("⚠️ BVC Live : aucune donnée parsée")
            self.available = False
            return pd.DataFrame()
        self._cache = df
        self._cache_time = datetime.now()
        self.available = True
        logger.info(f"✅ BVC Live : {len(df)} titres ({self._cache_time.strftime('%H:%M')})")
        return df

    def get_ticker(self, ticker: str) -> Dict[str, Any]:
        df = self.fetch_table()
        if df.empty:
            return {}
        row = df[df["ticker"] == ticker.upper()]
        return row.iloc[0].to_dict() if not row.empty else {}

# ============================================================
# INDICATEURS TECHNIQUES
# ============================================================

class TechnicalIndicators:
    @staticmethod
    def rsi_wilder(close: pd.Series, period: int = 14) -> pd.Series:
        delta = close.diff()
        gain = delta.clip(lower=0)
        loss = -delta.clip(upper=0)
        avg_gain = gain.ewm(alpha=1 / period, adjust=False).mean()
        avg_loss = loss.ewm(alpha=1 / period, adjust=False).mean()
        rs = avg_gain / avg_loss.replace(0, np.nan)
        return (100 - (100 / (1 + rs))).fillna(50)

    @staticmethod
    def macd(close: pd.Series) -> Tuple[pd.Series, pd.Series, pd.Series]:
        ema12 = close.ewm(span=12, adjust=False).mean()
        ema26 = close.ewm(span=26, adjust=False).mean()
        line = ema12 - ema26
        signal = line.ewm(span=9, adjust=False).mean()
        hist = line - signal
        return line, signal, hist

    @staticmethod
    def bollinger(close: pd.Series) -> Tuple[pd.Series, pd.Series, pd.Series]:
        ma = close.rolling(20).mean()
        std = close.rolling(20).std()
        upper = ma + 2 * std
        lower = ma - 2 * std
        width = (upper - lower) / ma.replace(0, np.nan)
        return upper, lower, width

    @staticmethod
    def ichimoku(df: pd.DataFrame) -> Tuple:
        tenkan = (df["high"].rolling(9).max() + df["low"].rolling(9).min()) / 2
        kijun  = (df["high"].rolling(26).max() + df["low"].rolling(26).min()) / 2
        kumo_a = (tenkan + kijun) / 2
        kumo_b = (df["high"].rolling(52).max() + df["low"].rolling(52).min()) / 2
        return tenkan, kijun, kumo_a, kumo_b

    @staticmethod
    def stochastic(high: pd.Series, low: pd.Series, close: pd.Series) -> Tuple[pd.Series, pd.Series]:
        ll = low.rolling(14).min()
        hh = high.rolling(14).max()
        k = (100 * (close - ll) / (hh - ll).replace(0, np.nan)).fillna(50)
        d = k.rolling(3).mean().fillna(50)
        return k, d

    @staticmethod
    def atr(df: pd.DataFrame) -> pd.Series:
        h, l, c = df["high"], df["low"], df["close"]
        tr = pd.concat([
            h - l,
            (h - c.shift(1)).abs(),
            (l - c.shift(1)).abs(),
        ], axis=1).max(axis=1)
        return tr.rolling(14).mean()

    @staticmethod
    def calculate_all(df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        for p in [20, 50, 100, 200]:
            df[f"MA{p}"] = df["close"].rolling(p).mean()
        df["MACD"], df["MACD_SIGNAL"], df["MACD_HIST"] = TechnicalIndicators.macd(df["close"])
        df["RSI"] = TechnicalIndicators.rsi_wilder(df["close"])
        df["BB_upper"], df["BB_lower"], df["BB_width"] = TechnicalIndicators.bollinger(df["close"])
        df["tenkan"], df["kijun"], df["kumo_a"], df["kumo_b"] = TechnicalIndicators.ichimoku(df)
        df["Stoch_K"], df["Stoch_D"] = TechnicalIndicators.stochastic(
            df["high"], df["low"], df["close"]
        )
        vol_ma = df["volume"].rolling(20).mean().replace(0, np.nan)
        df["Vol_MA20"] = vol_ma
        df["Volume_Ratio"] = df["volume"] / vol_ma
        df["Return_1D"]  = df["close"].pct_change() * 100
        df["Return_5D"]  = df["close"].pct_change(5) * 100
        df["Return_20D"] = df["close"].pct_change(20) * 100
        df["Volatility_20"] = df["Return_1D"].rolling(20).std()
        df["ATR"]   = TechnicalIndicators.atr(df)
        df["High_20"] = df["high"].rolling(20).max()
        df["Low_20"]  = df["low"].rolling(20).min()
        df["High_50"] = df["high"].rolling(50).max()
        df["Low_50"]  = df["low"].rolling(50).min()
        return df

# ============================================================
# SCORING TECHNIQUE
# ============================================================

class TechnicalScorer:
    def score(self, df: pd.DataFrame) -> ScoreResult:
        s = 0.0
        ms = 0.0
        reasons: List[str] = []
        details: Dict[str, Any] = {}

        G = SafeMath.last
        P = SafeMath.prev

        prix   = G(df["close"])
        ma20   = G(df["MA20"])
        ma50   = G(df["MA50"])
        ma200  = G(df["MA200"])
        rsi    = G(df["RSI"])
        macd   = G(df["MACD"])
        msig   = G(df["MACD_SIGNAL"])
        mhist  = G(df["MACD_HIST"])
        mhist2 = P(df["MACD_HIST"])
        vol_r  = G(df["Volume_Ratio"])
        stk    = G(df["Stoch_K"])
        std    = G(df["Stoch_D"])
        bb_u   = G(df["BB_upper"])
        bb_l   = G(df["BB_lower"])
        bb_w   = G(df["BB_width"])
        ten    = G(df["tenkan"])
        kij    = G(df["kijun"])
        ka     = G(df["kumo_a"])
        kb     = G(df["kumo_b"])
        ret5   = G(df["Return_5D"])
        vol20  = G(df["Volatility_20"])

        nuage_haut = max(ka, kb) if not (pd.isna(ka) or pd.isna(kb)) else np.nan
        nuage_bas  = min(ka, kb) if not (pd.isna(ka) or pd.isna(kb)) else np.nan

        details.update({
            "prix": prix, "ma20": ma20, "ma50": ma50, "ma200": ma200,
            "rsi": rsi, "macd": macd, "macd_signal": msig,
            "vol_ratio": vol_r, "stoch_k": stk,
            "nuage_haut": nuage_haut, "nuage_bas": nuage_bas,
        })

        ms += 3
        if not any(pd.isna(x) for x in [prix, ma20, ma50]):
            if prix > ma20 > ma50:
                s += 3; reasons.append("✅ Prix > MA20 > MA50 — tendance haussière forte")
            elif prix > ma20:
                s += 1.5; reasons.append("⚠️ Prix > MA20 mais MA50 résistante")
            elif prix < ma20 < ma50:
                reasons.append("❌ Prix < MA20 < MA50 — tendance baissière confirmée")
            else:
                s += 0.75; reasons.append("⚠️ Moyennes mobiles mixtes")

        ms += 2
        if not pd.isna(ma200) and not pd.isna(prix):
            if prix > ma200 * 1.05:
                s += 2; reasons.append("✅ Prix solidement au-dessus MA200")
            elif prix > ma200:
                s += 1; reasons.append("⚠️ Prix légèrement au-dessus MA200")
            else:
                reasons.append("❌ Prix sous MA200 — long terme négatif")

        ms += 3
        if not any(pd.isna(x) for x in [macd, msig, mhist, mhist2]):
            if macd > msig and mhist > mhist2 and mhist2 > 0:
                s += 3; reasons.append("✅ MACD haussier accélérant")
            elif macd > msig and mhist > mhist2:
                s += 2; reasons.append("✅ MACD haussier en progression")
            elif macd > msig:
                s += 1; reasons.append("⚠️ MACD haussier, momentum ralentit")
            elif macd < msig and mhist < mhist2 < 0:
                reasons.append("❌ MACD baissier accélérant")
            else:
                s += 0.5; reasons.append("⚠️ MACD en transition")

        ms += 2
        if not pd.isna(rsi):
            if 42 <= rsi <= 58:
                s += 2; reasons.append(f"✅ RSI sain : {rsi:.1f}")
            elif 58 < rsi <= 70:
                s += 1; reasons.append(f"⚠️ RSI positif mais tendu : {rsi:.1f}")
            elif rsi > 70:
                reasons.append(f"❌ RSI surchauffe : {rsi:.1f}")
            elif 35 <= rsi < 42:
                s += 0.75; reasons.append(f"⚠️ RSI bas : {rsi:.1f}")
            else:
                s += 1.25; reasons.append(f"⚠️ RSI survente forte : {rsi:.1f} — rebond possible")

        ms += 3
        if not pd.isna(nuage_haut) and not pd.isna(nuage_bas):
            if prix > nuage_haut and not pd.isna(ten) and not pd.isna(kij) and ten > kij:
                s += 3; reasons.append("✅ Ichimoku entièrement positif — momentum fort")
            elif prix > nuage_haut:
                s += 2; reasons.append("⚠️ Prix au-dessus nuage — Tenkan/Kijun non confirmé")
            elif prix > nuage_bas:
                s += 1; reasons.append("⚠️ Prix dans le nuage — zone d'incertitude")
            else:
                reasons.append("❌ Prix sous le nuage Ichimoku")

        ms += 2
        if not any(pd.isna(x) for x in [stk, std]):
            if stk < 20 and stk > std:
                s += 2; reasons.append(f"✅ Stochastique sortie de survente : {stk:.0f}")
            elif stk < 20:
                s += 1; reasons.append(f"⚠️ Stochastique en survente : {stk:.0f}")
            elif stk > 80 and stk < std:
                reasons.append(f"❌ Stochastique retournement depuis surachat : {stk:.0f}")
            elif stk > 80:
                s += 0.5; reasons.append(f"⚠️ Stochastique surachat : {stk:.0f}")
            else:
                s += 1; reasons.append(f"⚠️ Stochastique neutre : {stk:.0f}")

        ms += 2
        if not any(pd.isna(x) for x in [prix, bb_u, bb_l]):
            if prix < bb_l and not pd.isna(rsi) and rsi < 40:
                s += 2; reasons.append("✅ Sous Bollinger basse + RSI bas — rebond technique")
            elif prix > bb_u and not pd.isna(rsi) and rsi > 65:
                reasons.append("❌ Sur Bollinger haute + RSI élevé — excès haussier")
            elif not pd.isna(bb_w) and bb_w < 0.05:
                s += 1.5; reasons.append("⚠️ Squeeze Bollinger — breakout imminent")
            else:
                s += 1; reasons.append("⚠️ Bollinger normal")

        ms += 2
        if not pd.isna(vol_r):
            if vol_r >= 2.0 and not pd.isna(ma20) and prix > ma20:
                s += 2; reasons.append(f"✅ Volume très fort en hausse : {vol_r:.1f}x")
            elif vol_r >= 1.3 and not pd.isna(ma20) and prix > ma20:
                s += 1.5; reasons.append(f"✅ Volume fort : {vol_r:.1f}x")
            elif vol_r >= 0.8:
                s += 1; reasons.append(f"⚠️ Volume dans la moyenne : {vol_r:.1f}x")
            elif vol_r < 0.30:
                reasons.append(f"❌ Volume très faible : {vol_r:.1f}x — signaux peu fiables")
            elif vol_r < 0.60:
                s += 0.25; reasons.append(f"⚠️ Volume faible : {vol_r:.1f}x")
            else:
                s += 0.75; reasons.append(f"⚠️ Volume modéré : {vol_r:.1f}x")

        ms += 1
        if not pd.isna(ret5):
            if ret5 > 5:
                s += 1; reasons.append(f"✅ Momentum 5j fort : +{ret5:.1f}%")
            elif ret5 > 2:
                s += 0.5; reasons.append(f"✅ Momentum 5j positif : +{ret5:.1f}%")
            elif ret5 < -5:
                reasons.append(f"❌ Momentum 5j négatif : {ret5:.1f}%")
            else:
                s += 0.25; reasons.append(f"⚠️ Momentum 5j stable : {ret5:.1f}%")

        ms += 1
        if not pd.isna(vol20):
            if vol20 < 1.5:
                s += 1; reasons.append(f"✅ Volatilité faible : {vol20:.1f}%")
            elif vol20 <= 4:
                s += 0.5; reasons.append(f"⚠️ Volatilité modérée : {vol20:.1f}%")
            else:
                reasons.append(f"❌ Volatilité élevée : {vol20:.1f}%")

        close_s = df["close"].dropna()
        macd_s  = df["MACD"].dropna()
        if len(close_s) >= 10 and len(macd_s) >= 10:
            if float(close_s.iloc[-1]) > float(close_s.iloc[-10]) and \
               float(macd_s.iloc[-1])  < float(macd_s.iloc[-10]):
                s = max(0, s - 0.5)
                reasons.append("⚠️ Divergence baissière MACD/Prix (10j)")

        return ScoreResult(max(0.0, s), ms, reasons, details)

# ============================================================
# SCORING FONDAMENTAL — v4.0 COMPLET
# ============================================================

class FundamentalScorer:
    def __init__(self, fundamentals: Dict[str, Any]):
        self.f = fundamentals or {}

    def score(self) -> ScoreResult:
        if not self.f:
            return ScoreResult(0, 14, ["❌ Aucune donnée fondamentale pour ce ticker (GitHub)"])

        s = 0.0
        ms = 0.0
        reasons: List[str] = []
        m = SafeMath()

        per         = m.to_float(self.f.get("per"))
        forward_per = m.to_float(self.f.get("forward_per"))
        croissance  = m.to_float(self.f.get("croissance_ca"))
        dette       = m.to_float(self.f.get("dette_nette_ebitda"))
        div         = m.to_float(self.f.get("div_yield"))
        roic        = m.to_float(self.f.get("roic"))
        wacc        = m.to_float(self.f.get("wacc"))
        cash        = m.to_float(self.f.get("cash_conversion"))
        marge       = m.to_float(self.f.get("marge_nette"))
        momentum    = str(self.f.get("momentum_fondamental", "")).lower()
        rerating    = bool(self.f.get("rerating", False))
        cycle       = str(self.f.get("cycle_commodities", "")).lower()

        ms += 2
        if not pd.isna(per):
            if per < 8:
                s += 2;    reasons.append(f"✅ PER très attractif : {per}x")
            elif per < 12:
                s += 1.75; reasons.append(f"✅ PER attractif : {per}x")
            elif per < 18:
                s += 1.25; reasons.append(f"⚠️ PER raisonnable : {per}x")
            elif per < 25:
                s += 0.5;  reasons.append(f"⚠️ PER exigeant : {per}x")
            else:
                reasons.append(f"❌ PER élevé : {per}x")

        ms += 1
        if not pd.isna(forward_per):
            if not pd.isna(per):
                contraction = per - forward_per
                if forward_per < 10 and contraction >= 2:
                    s += 1;    reasons.append(f"✅ Forward PER très attractif : {forward_per}x (contraction {contraction:.1f} pts)")
                elif forward_per < 14 and contraction >= 1:
                    s += 0.75; reasons.append(f"✅ Forward PER attractif : {forward_per}x")
                elif forward_per < per:
                    s += 0.5;  reasons.append(f"⚠️ Forward PER en amélioration : {forward_per}x vs {per}x")
                else:
                    reasons.append(f"⚠️ Forward PER stable/dégradé : {forward_per}x")
            else:
                s += 0.5; reasons.append(f"⚠️ Forward PER : {forward_per}x (PER courant manquant)")

        ms += 2
        if not pd.isna(croissance):
            if croissance > 20:
                s += 2;    reasons.append(f"✅ Croissance CA forte : +{croissance}%")
            elif croissance > 15:
                s += 1.5;  reasons.append(f"✅ Croissance CA solide : +{croissance}%")
            elif croissance > 8:
                s += 1;    reasons.append(f"⚠️ Croissance correcte : +{croissance}%")
            elif croissance > 0:
                s += 0.5;  reasons.append(f"⚠️ Croissance modérée : +{croissance}%")
            else:
                reasons.append(f"❌ Croissance nulle ou négative : {croissance}%")

        ms += 2
        if not pd.isna(dette):
            if dette <= 1:
                s += 2;    reasons.append(f"✅ Endettement très faible : {dette}x")
            elif dette <= 2:
                s += 1.75; reasons.append(f"✅ Endettement faible : {dette}x")
            elif dette <= 3:
                s += 1;    reasons.append(f"⚠️ Endettement modéré : {dette}x")
            elif dette <= 4:
                s += 0.25; reasons.append(f"⚠️ Endettement élevé : {dette}x")
            else:
                reasons.append(f"❌ Endettement très élevé : {dette}x")

        ms += 2
        if not pd.isna(roic) and not pd.isna(wacc):
            spread = roic - wacc
            if spread >= 6:
                s += 2;    reasons.append(f"✅ EVA très positif : ROIC–WACC = +{spread:.1f} pts")
            elif spread >= 3:
                s += 1.5;  reasons.append(f"✅ Création de valeur : ROIC–WACC = +{spread:.1f} pts")
            elif spread >= 0:
                s += 0.75; reasons.append(f"⚠️ EVA marginalement positif : +{spread:.1f} pts")
            elif spread >= -3:
                reasons.append(f"🟠 EVA négatif : ROIC–WACC = {spread:.1f} pts")
            else:
                s -= 0.5;  reasons.append(f"❌ Destruction valeur sévère : ROIC–WACC = {spread:.1f} pts")

        ms += 1
        if not pd.isna(cash):
            if cash >= 80:
                s += 1;    reasons.append(f"✅ Cash conversion excellente : {cash}%")
            elif cash >= 65:
                s += 0.75; reasons.append(f"✅ Bonne cash conversion : {cash}%")
            elif cash >= 50:
                s += 0.5;  reasons.append(f"⚠️ Cash conversion moyenne : {cash}%")
            else:
                reasons.append(f"❌ Cash conversion faible : {cash}% — RN–FCF suspect")

        ms += 1
        if not pd.isna(marge):
            if marge >= 18:
                s += 1;    reasons.append(f"✅ Marge nette élevée : {marge}%")
            elif marge >= 12:
                s += 0.75; reasons.append(f"✅ Marge nette solide : {marge}%")
            elif marge >= 7:
                s += 0.5;  reasons.append(f"⚠️ Marge correcte : {marge}%")
            else:
                reasons.append(f"❌ Marge nette faible : {marge}%")

        ms += 1
        if not pd.isna(div):
            if div > 5:
                s += 1;    reasons.append(f"✅ Rendement dividende élevé : {div}%")
            elif div > 3:
                s += 0.75; reasons.append(f"✅ Dividende attractif : {div}%")
            elif div > 1:
                s += 0.25; reasons.append(f"⚠️ Dividende modeste : {div}%")

        ms += 1
        if momentum:
            if momentum in ["très positif", "tres positif"]:
                s += 1;    reasons.append(f"✅ Momentum fondamental : {momentum}")
            elif momentum == "positif":
                s += 0.6;  reasons.append(f"✅ Momentum fondamental : {momentum}")
            elif momentum == "stable":
                s += 0.25; reasons.append(f"⚠️ Momentum fondamental : {momentum}")
            elif "négatif" in momentum or "negatif" in momentum:
                reasons.append(f"❌ Momentum fondamental : {momentum}")

        ms += 1
        bonus = 0.0
        if rerating:
            bonus += 0.5; reasons.append("✅ Potentiel de re-rating identifié")
        if cycle == "bullish":
            bonus += 0.5; reasons.append(f"✅ Cycle commodités favorable : {cycle}")
        elif cycle in ["bearish", "baissier"]:
            reasons.append(f"❌ Cycle commodités défavorable : {cycle}")
        s += min(bonus, 1.0)

        return ScoreResult(max(0.0, s), ms, reasons)

# ============================================================
# RED FLAGS — v4.0
# ============================================================

class RedFlagDetector:
    def __init__(self, fundamentals: Dict[str, Any]):
        self.f = fundamentals or {}

    def detect(self, df: pd.DataFrame) -> List[RedFlag]:
        flags: List[RedFlag] = []
        m = SafeMath()

        dette = m.to_float(self.f.get("dette_nette_ebitda"))
        cash  = m.to_float(self.f.get("cash_conversion"))
        roic  = m.to_float(self.f.get("roic"))
        wacc  = m.to_float(self.f.get("wacc"))
        marge = m.to_float(self.f.get("marge_nette"))
        per   = m.to_float(self.f.get("per"))

        prix  = m.last(df["close"])
        ma20  = m.last(df["MA20"])
        ma50  = m.last(df["MA50"])
        rsi   = m.last(df["RSI"])
        vol_r = m.last(df["Volume_Ratio"])
        vol20 = m.last(df["Volatility_20"])
        ret20 = m.last(df["Return_20D"])

        if not pd.isna(dette):
            if dette > 5:
                flags.append(RedFlag(Severity.CRITIQUE, "Structure",
                    f"Dette/EBITDA critique : {dette}x (seuil alerte 5x)", True))
            elif dette > 4:
                flags.append(RedFlag(Severity.ELEVEE, "Structure",
                    f"Endettement élevé : {dette}x"))
            elif dette > 3:
                flags.append(RedFlag(Severity.MOYENNE, "Structure",
                    f"Endettement modéré : {dette}x"))

        if not pd.isna(cash):
            if cash < 30:
                flags.append(RedFlag(Severity.CRITIQUE, "Cash-flow",
                    f"Cash conversion critique : {cash}% — divergence RN/FCF majeure", True))
            elif cash < 50:
                flags.append(RedFlag(Severity.ELEVEE, "Cash-flow",
                    f"Cash conversion faible : {cash}% — surveiller BFR"))
            elif cash < 65:
                flags.append(RedFlag(Severity.MOYENNE, "Cash-flow",
                    f"Cash conversion modérée : {cash}%"))

        if not pd.isna(roic) and not pd.isna(wacc) and roic < wacc:
            spread = abs(roic - wacc)
            if spread > 5:
                flags.append(RedFlag(Severity.CRITIQUE, "Rentabilité",
                    f"ROIC {roic}% << WACC {wacc}% — destruction valeur sévère (EVA -{spread:.1f}pts)", True))
            else:
                flags.append(RedFlag(Severity.ELEVEE, "Rentabilité",
                    f"ROIC {roic}% < WACC {wacc}% — EVA négatif (–{spread:.1f} pts)"))

        if not pd.isna(marge) and marge < 5:
            flags.append(RedFlag(Severity.MOYENNE, "Rentabilité",
                f"Marge nette faible : {marge}%"))

        if not pd.isna(per) and per > 30:
            flags.append(RedFlag(Severity.MOYENNE, "Valorisation",
                f"PER élevé : {per}x — exige une forte croissance"))

        if not any(pd.isna(x) for x in [prix, ma20, ma50]):
            if prix < ma20 < ma50:
                flags.append(RedFlag(Severity.ELEVEE, "Technique",
                    "Tendance baissière court/moyen terme — prix sous MA20 et MA50"))

        if not pd.isna(rsi):
            if rsi > 82:
                flags.append(RedFlag(Severity.CRITIQUE, "Technique",
                    f"RSI surchauffe extrême : {rsi:.1f}", True))
            elif rsi > 75:
                flags.append(RedFlag(Severity.ELEVEE, "Technique",
                    f"RSI en surchauffe : {rsi:.1f}"))

        if not pd.isna(vol_r):
            if vol_r < 0.15:
                flags.append(RedFlag(Severity.CRITIQUE, "Liquidité BVC",
                    f"Volume quasi-nul : {vol_r:.2f}x — titre illiquide", True))
            elif vol_r < 0.30:
                flags.append(RedFlag(Severity.ELEVEE, "Liquidité BVC",
                    f"Volume très faible : {vol_r:.2f}x"))
            elif vol_r < 0.50:
                flags.append(RedFlag(Severity.MOYENNE, "Liquidité BVC",
                    f"Volume faible : {vol_r:.2f}x"))

        if not pd.isna(vol20) and vol20 > 6:
            flags.append(RedFlag(Severity.ELEVEE, "Volatilité",
                f"Volatilité 20j élevée : {vol20:.1f}%"))

        if not pd.isna(ret20):
            if ret20 < -25:
                flags.append(RedFlag(Severity.CRITIQUE, "Momentum",
                    f"Correction sévère 20j : {ret20:.1f}%", True))
            elif ret20 < -15:
                flags.append(RedFlag(Severity.ELEVEE, "Momentum",
                    f"Correction importante 20j : {ret20:.1f}%"))

        return flags

# ============================================================
# SETUP DETECTOR — ROBUSTE AUX NaN
# ============================================================

class SetupDetector:
    def detect(self, df: pd.DataFrame) -> Setup:
        G = SafeMath.last

        prix  = G(df["close"])
        ma20  = G(df["MA20"])
        ma50  = G(df["MA50"])
        rsi   = G(df["RSI"])
        vol_r = G(df["Volume_Ratio"])
        macd  = G(df["MACD"])
        msig  = G(df["MACD_SIGNAL"])
        h20   = G(df["High_20"])
        l20   = G(df["Low_20"])

        has_trend  = not any(pd.isna(x) for x in [prix, ma20, ma50])
        has_rsi    = not pd.isna(rsi)
        has_macd   = not any(pd.isna(x) for x in [macd, msig])
        has_volume = not pd.isna(vol_r)

        if has_trend and has_rsi and has_macd:
            if prix > ma20 > ma50 and rsi > 52 and macd > msig:
                if not has_volume or vol_r >= 1.2:
                    return Setup.MOMENTUM_CONFIRME

        if has_trend and not pd.isna(h20):
            if prix >= h20 * 0.98:
                vol_ok = not has_volume or vol_r >= 1.3
                macd_ok = not has_macd or macd > msig
                if vol_ok and macd_ok:
                    return Setup.BREAKOUT_POTENTIEL

        if has_trend and has_rsi:
            if prix > ma50 and ma20 > ma50 and 38 <= rsi <= 58:
                if prix <= ma20 * 1.03:
                    return Setup.PULLBACK_HAUSSIER

        if has_rsi and not pd.isna(l20):
            if rsi < 35 and prix <= l20 * 1.08:
                return Setup.CONTRARIEN

        if has_trend and has_rsi and has_macd:
            if prix > ma50 and 42 <= rsi <= 62 and macd > msig:
                if not has_volume or vol_r < 0.90:
                    return Setup.ACCUMULATION_LENTE

        if has_trend and has_rsi:
            if prix < ma20 < ma50 and rsi < 50:
                return Setup.FAIBLESSE

        return Setup.NEUTRE

# ============================================================
# VALORISATION v4.0 — TARGETS JSON + DÉCOTE LIQUIDITÉ
# ============================================================

class ValuationEngine:
    def __init__(self, fundamentals: Dict[str, Any]):
        self.f = fundamentals or {}

    def calculate(self, price: float, liquidity: LiquidityProfile) -> Valuation:
        m = SafeMath()
        disc = liquidity.discount_pct

        target = m.to_float(self.f.get("target_price"))
        bear_t = m.to_float(self.f.get("bear_case"))
        bull_t = m.to_float(self.f.get("bull_case"))

        if not any(pd.isna(x) for x in [target, bear_t, bull_t]):
            base = round(target * (1 - disc), 2)
            bear = round(bear_t * (1 - disc), 2)
            bull = round(bull_t, 2)
            return Valuation(
                base=base, bull=bull, bear=bear,
                upside_base=m.pct_change(base, price),
                upside_bull=m.pct_change(bull, price),
                downside=m.pct_change(bear, price),
                premium_pct=round(-disc * 100, 1),
                methodology=f"Objectifs analyst JSON + décote liquidité BVC {disc*100:.0f}%",
                source=ValuationSource.ANALYST_TARGETS,
                liquidity_discount_pct=round(disc * 100, 1),
                confidence="Haute" if disc < 0.10 else "Moyenne",
            )

        per     = m.to_float(self.f.get("per"))
        fwd_per = m.to_float(self.f.get("forward_per"))
        croiss  = m.to_float(self.f.get("croissance_ca"))
        roic    = m.to_float(self.f.get("roic"))
        wacc    = m.to_float(self.f.get("wacc"))
        dette   = m.to_float(self.f.get("dette_nette_ebitda"))
        cash    = m.to_float(self.f.get("cash_conversion"))

        if pd.isna(per) or pd.isna(croiss):
            return Valuation(
                base=None, bull=None, bear=None,
                upside_base=None, upside_bull=None, downside=None,
                premium_pct=None, methodology="Données insuffisantes",
                source=ValuationSource.PREMIUM_BASED,
                liquidity_discount_pct=0, confidence="Faible",
            )

        premium = 0.0
        if croiss > 20:    premium += 0.15
        elif croiss > 15:  premium += 0.10
        elif croiss > 8:   premium += 0.05
        elif croiss < 0:   premium -= 0.10

        if not any(pd.isna(x) for x in [roic, wacc]):
            sp = roic - wacc
            if sp >= 6:    premium += 0.12
            elif sp >= 3:  premium += 0.08
            elif sp >= 0:  premium += 0.03
            else:          premium -= 0.10

        ref_per = fwd_per if not pd.isna(fwd_per) else per
        if ref_per < 8:     premium += 0.12
        elif ref_per < 12:  premium += 0.08
        elif ref_per < 16:  premium += 0.03
        elif ref_per > 28:  premium -= 0.15
        elif ref_per > 22:  premium -= 0.08

        if not pd.isna(cash):
            if cash >= 80:  premium += 0.05
            elif cash < 40: premium -= 0.08

        if not pd.isna(dette):
            if dette > 4:   premium -= 0.12
            elif dette > 3: premium -= 0.06
            elif dette < 1: premium += 0.05

        premium -= disc
        base = round(price * (1 + premium), 2)
        bull = round(base * 1.25, 2)
        bear = round(base * 0.78, 2)

        return Valuation(
            base=base, bull=bull, bear=bear,
            upside_base=m.pct_change(base, price),
            upside_bull=m.pct_change(bull, price),
            downside=m.pct_change(bear, price),
            premium_pct=round(premium * 100, 1),
            methodology=f"Multi-facteurs (forward PER, ROIC/WACC) + décote BVC {disc*100:.0f}%",
            source=ValuationSource.PREMIUM_BASED,
            liquidity_discount_pct=round(disc * 100, 1),
            confidence="Moyenne",
        )

# ============================================================
# DECISION ENGINE v4.0
# ============================================================

class DecisionEngine:
    def decide(
        self,
        score_tech: ScoreResult,
        score_fond: ScoreResult,
        setup: Setup,
        red_flags: List[RedFlag],
        liquidity: LiquidityProfile,
    ) -> Tuple[Signal, str, float]:

        tw = liquidity.tech_weight
        fw = liquidity.fond_weight
        score_global = round(score_tech.normalized * tw + score_fond.normalized * fw, 2)

        critical = [f for f in red_flags if f.severity == Severity.CRITIQUE]
        if critical:
            return Signal.EVITER, f"ÉVITER — {critical[0].message}", score_global

        blocking = [f for f in red_flags if f.is_blocking]
        if blocking:
            return Signal.EVITER, f"ÉVITER — {blocking[0].message}", score_global

        severe_count = sum(1 for f in red_flags
                           if f.severity in [Severity.CRITIQUE, Severity.ELEVEE])

        if score_global >= 8.0 and setup in [Setup.MOMENTUM_CONFIRME, Setup.BREAKOUT_POTENTIEL] \
                and severe_count == 0:
            return Signal.ACHAT_FORT, f"ACHAT FORT — {setup.value}", score_global

        if score_global >= 7.0 and setup in [Setup.MOMENTUM_CONFIRME, Setup.BREAKOUT_POTENTIEL]:
            return Signal.ACHETER, f"ACHETER — {setup.value}", score_global

        if score_global >= 6.5 and setup == Setup.PULLBACK_HAUSSIER:
            return Signal.ACHETER, "ACHETER — Pullback haussier confirmé", score_global

        if score_global >= 6.0 and setup == Setup.ACCUMULATION_LENTE:
            return Signal.ACCUMULER, "ACCUMULER — Position progressive", score_global

        if score_global >= 5.5:
            return Signal.SURVEILLER, f"SURVEILLER — {setup.value}", score_global

        if score_global >= 4.0:
            return Signal.ATTENDRE, f"ATTENDRE — {setup.value}", score_global

        if setup == Setup.FAIBLESSE or score_fond.normalized < 4.0:
            return Signal.EVITER, f"ÉVITER — {setup.value}", score_global

        return Signal.ATTENDRE, "ATTENDRE — Signal insuffisant", score_global

# ============================================================
# LECTEUR EXCEL BVC — DÉTECTION AUTOMATIQUE DES COLONNES
# ============================================================

class BVCFileReader:
    _KEYWORDS = {
        "close":  ["cloture", "clôture", "close", "cours", "dernier", "last"],
        "high":   ["haut", "plus haut", "high", "max"],
        "low":    ["bas", "plus bas", "low", "min"],
        "volume": ["volume", "vol", "qte", "quantité", "quantite"],
    }
    _DEFAULT = {"close": 4, "high": 5, "low": 6, "volume": 7}

    @staticmethod
    def _detect_columns(ws) -> Dict[str, int]:
        for row in list(ws.rows)[:6]:
            found: Dict[str, int] = {}
            for col_idx, cell in enumerate(row):
                if cell.value is None:
                    continue
                val = str(cell.value).lower().strip()
                for field, kws in BVCFileReader._KEYWORDS.items():
                    if field not in found and any(kw in val for kw in kws):
                        found[field] = col_idx
            if "close" in found and "high" in found:
                logger.info(f"Colonnes auto-détectées : {found}")
                return found
        logger.info("Colonnes BVC standard (fallback)")
        return BVCFileReader._DEFAULT

    @staticmethod
    def read(filename: str) -> Tuple[str, pd.DataFrame]:
        wb = openpyxl.load_workbook(filename, data_only=True)
        ws = wb.active

        ticker = "UNKNOWN"
        for cell_ref in ["C2", "B2", "A2", "C1", "B1"]:
            val = ws[cell_ref].value
            if val:
                candidate = str(val).strip().upper()
                if 2 <= len(candidate) <= 6 and candidate.isalpha():
                    ticker = candidate
                    break

        col_map = BVCFileReader._detect_columns(ws)
        rows = []
        for row in list(ws.rows)[1:]:
            try:
                entry: Dict[str, float] = {}
                for field, idx in col_map.items():
                    entry[field] = SafeMath.to_float(row[idx].value) if idx < len(row) else np.nan
                rows.append(entry)
            except Exception:
                continue

        if not rows:
            raise ValueError(f"Aucune donnée dans {filename}")

        df = pd.DataFrame(rows)
        if "volume" not in df.columns:
            df["volume"] = 0.0
        df["volume"] = df["volume"].fillna(0.0)
        df = df.dropna(subset=["close", "high", "low"])
        df = df[df["close"] > 0]
        df = df.iloc[::-1].reset_index(drop=True)

        if len(df) < 30:
            raise ValueError(
                f"Historique insuffisant pour {ticker} : {len(df)} séances (minimum 30)"
            )
        logger.info(f"✅ {filename} → {ticker} | {len(df)} séances")
        return ticker, df

# ============================================================
# GÉNÉRATEUR DE NOTE INSTITUTIONNELLE — 8 SECTIONS
# ============================================================

class NoteGenerator:
    def generate(self, result: AnalysisResult) -> str:
        f    = result.fundamental_data
        live = result.live_data
        v    = result.valuation
        eva  = result.eva
        liq  = result.liquidity
        td   = result.technical_data
        m    = SafeMath()

        emoji_map = {
            "ACHAT FORT": "🟢🟢", "ACHETER": "🟢", "ACCUMULER": "🟢",
            "SURVEILLER": "🟡", "ATTENDRE": "🟡", "EVITER": "🔴",
        }
        sig_emoji = emoji_map.get(result.signal.value, "⚪")

        def fmt_flags(flags: List[RedFlag]) -> str:
            if not flags:
                return "    ✅ Aucun red flag majeur"
            out = []
            for fl in sorted(flags, key=lambda x: x.severity.value):
                blk = " [BLOQUANT]" if fl.is_blocking else ""
                out.append(f"    {fl.severity.value} | {fl.category} : {fl.message}{blk}")
            return "\n".join(out)

        if v.base is not None:
            val_text = (
                f"    Source       : {v.source.value}\n"
                f"    Méthode      : {v.methodology}\n"
                f"    Décote liq.  : -{v.liquidity_discount_pct}% (BVC)\n"
                f"    Bear         : {m.fmt(v.bear)} DH  ({m.fmt_pct(v.downside)})\n"
                f"    Base (cible) : {m.fmt(v.base)} DH  ({m.fmt_pct(v.upside_base)})\n"
                f"    Bull         : {m.fmt(v.bull)} DH  ({m.fmt_pct(v.upside_bull)})\n"
                f"    Confiance    : {v.confidence}"
            )
        else:
            val_text = "    Données insuffisantes pour valorisation"

        if eva:
            eva_text = (
                f"    ROIC {eva.roic}% | WACC {eva.wacc}% | Spread {m.fmt(eva.spread, 1)} pts\n"
                f"    {eva.verdict}\n"
                f"    {eva.description}"
            )
        else:
            eva_text = "    ROIC ou WACC manquant — EVA non calculable"

        if live and not pd.isna(live.get("cours", np.nan)):
            live_text = (
                f"{m.fmt(live.get('cours'))} DH  "
                f"(var. {m.fmt_pct(live.get('variation'))}  "
                f"vol. {m.fmt(live.get('volume'), 0)})"
            )
        else:
            live_text = "Non disponible (BVC hors séance ou site inaccessible)"

        tech_txt = "\n".join([f"    • {r}" for r in result.score_technical.reasons])
        fond_txt = "\n".join([f"    • {r}" for r in result.score_fundamental.reasons])

        return f"""
{"="*80}
  NOTE INSTITUTIONNELLE — {result.ticker}
  BVC ULTIMATE ANALYZER v{__version__} | {result.date.strftime('%d/%m/%Y %H:%M')}
{"="*80}

  {sig_emoji}  SIGNAL    : {result.action}
  Setup     : {result.setup.value}
  Secteur   : {f.get('secteur', 'N/A')}
  Prix anal. : {result.price:.2f} DH
  BVC Live  : {live_text}

  Score Technique   : {result.score_technical.normalized}/10
  Score Fondamental : {result.score_fundamental.normalized}/10
  Score Global      : {result.score_global}/10
  Pondération       : Tech {liq.tech_weight*100:.0f}% / Fond {liq.fond_weight*100:.0f}%
  Liquidité BVC     : {liq.tier.replace('_',' ').title()} — {liq.description}

{"─"*80}
  1. COMPTE DE RÉSULTAT & QUALITÉ DES BÉNÉFICES
{"─"*80}
  Croissance CA    : {f.get('croissance_ca', 'N/A')}%
  Croissance BPA   : {f.get('croissance_bpa', 'N/A')}%
  Marge nette      : {f.get('marge_nette', 'N/A')}%
  BPA 2026E        : {f.get('bpa_2026', 'N/A')} DH
  DPS 2026E        : {f.get('dps_2026', 'N/A')} DH
  Momentum fond.   : {f.get('momentum_fondamental', 'N/A')}
  Re-rating        : {'✅ Oui' if f.get('rerating') else 'Non'}
  Cycle commodités : {f.get('cycle_commodities', 'N/A')}

{"─"*80}
  2. CASH-FLOW & CONVERSION (Pont RN → FCF)
{"─"*80}
  Cash conversion  : {f.get('cash_conversion', 'N/A')}%
  Lecture          : Cash conv. < 50% → risque BFR gonflé ou revenus reconnus tôt.
                     Données granulaires RN→FCF nécessitent le RFA PDF complet.

{"─"*80}
  3. STRUCTURE FINANCIÈRE
{"─"*80}
  Dette nette/EBITDA : {f.get('dette_nette_ebitda', 'N/A')}x
  Rendement div.     : {f.get('div_yield', 'N/A')}%
  WACC BVC ref.      : ~10% (Rf 3% Bons Trésor + ERP 7%)

{"─"*80}
  4. RENTABILITÉ & CRÉATION DE VALEUR (EVA)
{"─"*80}
{eva_text}

{"─"*80}
  5. CONTEXTE MARCHÉ & CATALYSEURS
{"─"*80}
  Secteur    : {f.get('secteur', 'N/A')}
  Catalyseur : {f.get('catalyseur', 'N/A')}
  Risque     : {f.get('risque', 'N/A')}
  News       : {f.get('news', 'N/A')}
  Source     : {f.get('source', 'N/A')} | MAJ : {f.get('date_maj', 'N/A')}

{"─"*80}
  6. RED FLAGS — MINDSET AUDIT
{"─"*80}
{fmt_flags(result.red_flags)}

{"─"*80}
  7. VALORISATION
{"─"*80}
{val_text}

{"─"*80}
  8. ANALYSE TECHNIQUE DÉTAILLÉE
{"─"*80}
  PER courant  : {f.get('per', 'N/A')}x   Forward PER : {f.get('forward_per', 'N/A')}x
  Prix / MA20  : {m.fmt(td.get('ma20'))} DH
  Prix / MA50  : {m.fmt(td.get('ma50'))} DH
  Prix / MA200 : {m.fmt(td.get('ma200'))} DH
  RSI          : {m.fmt(td.get('rsi'), 1)}
  MACD / Signal: {m.fmt(td.get('macd'))} / {m.fmt(td.get('macd_signal'))}
  Nuage Ichi.  : {m.fmt(td.get('nuage_bas'))} — {m.fmt(td.get('nuage_haut'))} DH
  Volume Ratio : {m.fmt(td.get('vol_ratio'), 2)}x
  Stochastique : {m.fmt(td.get('stoch_k'), 1)}

  Points techniques :
{tech_txt}

  Points fondamentaux :
{fond_txt}

{"─"*80}
  SYNTHÈSE EXÉCUTIVE
{"─"*80}
  Recommandation   : {result.action}
  Objectif 12M     : Base {m.fmt(v.base)} DH | Bull {m.fmt(v.bull)} DH | Bear {m.fmt(v.bear)} DH
  Thèse haussière  : {f.get('catalyseur', 'N/A')}
  Thèse baissière  : {f.get('risque', 'N/A')}

  ⚠️ Note automatique. Ne constitue pas un conseil en investissement
     ni une recommandation personnalisée (AMMC / réglementation BVC).
{"="*80}
"""

# ============================================================
# ANALYSEUR PRINCIPAL v4.0
# ============================================================

class BVCAnalyzer:
    def __init__(self, github_url: str = GITHUB_URL, use_live_bvc: bool = True):
        self.github_url = github_url
        self.use_live_bvc = use_live_bvc
        self._fundamentals: Dict[str, Any] = {}
        self._fund_loaded: Optional[datetime] = None
        self._fund_ttl = timedelta(hours=6)
        self.live = BVCLiveConnector()

    def _load_fundamentals(self) -> None:
        if self._fund_loaded and datetime.now() - self._fund_loaded < self._fund_ttl:
            return
        try:
            r = requests.get(self.github_url, timeout=20, headers=HEADERS)
            r.raise_for_status()
            self._fundamentals = r.json()
            self._fund_loaded = datetime.now()
            logger.info(f"✅ Fondamentaux GitHub : {list(self._fundamentals.keys())}")
        except Exception as e:
            logger.warning(f"⚠️ GitHub fondamentaux : {e}")

    def get_fundamentals(self, ticker: str) -> Dict[str, Any]:
        self._load_fundamentals()
        data = self._fundamentals.get(ticker.upper(), {})
        if not data:
            logger.warning(f"⚠️ Aucun fondamental pour {ticker} — scoring fondamental à 0")
        return data

    def analyze(self, filename: str) -> AnalysisResult:
        ticker, df = BVCFileReader.read(filename)

        live_data: Dict[str, Any] = {}
        if self.use_live_bvc:
            live_data = self.live.get_ticker(ticker)
            if live_data and not pd.isna(live_data.get("cours", np.nan)):
                lp = float(live_data["cours"])
                idx = df.index[-1]
                df.at[idx, "close"] = lp
                df.at[idx, "high"]  = max(float(df.at[idx, "high"]), lp)
                df.at[idx, "low"]   = min(float(df.at[idx, "low"]),  lp)
                if not pd.isna(live_data.get("quantite", np.nan)):
                    df.at[idx, "volume"] = float(live_data["quantite"])
                logger.info(f"✅ Prix live injecté {ticker} : {lp:.2f} DH")

        df = TechnicalIndicators.calculate_all(df)

        price     = SafeMath.last(df["close"])
        vol_ratio = SafeMath.last(df["Volume_Ratio"])

        liquidity = LiquidityAnalyzer.analyze(vol_ratio)

        fundamentals = self.get_fundamentals(ticker)

        score_tech = TechnicalScorer().score(df)
        score_fond = FundamentalScorer(fundamentals).score()

        roic = SafeMath.to_float(fundamentals.get("roic"))
        wacc = SafeMath.to_float(fundamentals.get("wacc"))
        eva  = EVACalculator.calculate(roic, wacc)

        red_flags = RedFlagDetector(fundamentals).detect(df)
        setup     = SetupDetector().detect(df)
        signal, action, score_global = DecisionEngine().decide(
            score_tech, score_fond, setup, red_flags, liquidity
        )

        valuation = ValuationEngine(fundamentals).calculate(price, liquidity)

        result = AnalysisResult(
            ticker=ticker,
            price=price,
            date=datetime.now(),
            setup=setup,
            signal=signal,
            action=action,
            score_technical=score_tech,
            score_fundamental=score_fond,
            score_global=score_global,
            red_flags=red_flags,
            valuation=valuation,
            eva=eva,
            liquidity=liquidity,
            technical_data=score_tech.raw_details,
            fundamental_data=fundamentals,
            live_data=live_data,
            source_files=[filename],
        )
        result.institutional_note = NoteGenerator().generate(result)
        return result

# ============================================================
# INTERFACE GOOGLE COLAB — PRATIQUE v4.0
# ============================================================

def run_colab_analysis(use_live: bool = True, github_url: str = GITHUB_URL) -> None:
    try:
        from google.colab import files as colab_files
        COLAB = True
    except ImportError:
        COLAB = False

    print(f"""
╔══════════════════════════════════════════════════════════════════╗
║     BVC ULTIMATE ANALYZER v{__version__} PRO — INSTITUTIONNEL       ║
║     Marché : BVC Casablanca | AMMC | IFRS/CGNC                  ║
║     Méthodologie : github.com/LKABAL-BVC/claude-skill-annual-*  ║
╚══════════════════════════════════════════════════════════════════╝
    """)

    analyzer = BVCAnalyzer(github_url=github_url, use_live_bvc=use_live)

    if COLAB:
        print("📥 Upload tes fichiers Excel BVC (PDF et autres formats ignorés)...")
        uploaded = colab_files.upload()
        filenames = [f for f in uploaded if f.lower().endswith((".xlsx", ".xlsm"))]
        ignored   = [f for f in uploaded if not f.lower().endswith((".xlsx", ".xlsm"))]
        if ignored:
            print(f"⚠️ Fichiers ignorés : {', '.join(ignored)}")
    else:
        import os
        filenames = [f for f in os.listdir(".") if f.lower().endswith((".xlsx", ".xlsm"))]
        if not filenames:
            print("❌ Aucun fichier Excel trouvé dans le répertoire courant.")
            return

    if not filenames:
        print("❌ Aucun fichier Excel valide.")
        return

    print(f"\n📊 {len(filenames)} fichier(s) à analyser...\n")

    results: Dict[str, AnalysisResult] = {}
    errors: List[Tuple[str, str]] = []

    for filename in filenames:
        print("=" * 80)
        print(f"  ⏳ Analyse : {filename}")
        print("=" * 80)
        try:
            result = analyzer.analyze(filename)
            if result.ticker in results:
                print(f"  ⚠️ {result.ticker} déjà analysé — ignoré.")
                continue
            results[result.ticker] = result
            print(result.institutional_note)
        except Exception as e:
            errors.append((filename, str(e)))
            print(f"  ❌ Erreur : {e}\n")

    if errors:
        print("\n⚠️ ERREURS D'ANALYSE :")
        for fname, err in errors:
            print(f"  • {fname} : {err}")

    if not results:
        print("\n❌ Aucune analyse réussie.")
        return

    rows = []
    for r in results.values():
        vb = r.valuation.base
        ub = r.valuation.upside_base
        rows.append({
            "Ticker":       r.ticker,
            "Prix (DH)":    round(r.price, 2),
            "Signal":       r.signal.value,
            "Score Global": r.score_global,
            "Technique":    r.score_technical.normalized,
            "Fondamental":  r.score_fundamental.normalized,
            "EVA Spread":   round(r.eva.spread, 1) if r.eva else None,
            "Setup":        r.setup.value,
            "Red Flags":    len(r.red_flags),
            "Liq. Tier":    r.liquidity.tier,
            "Base (DH)":    vb,
            "Bull (DH)":    r.valuation.bull,
            "Bear (DH)":    r.valuation.bear,
            "Upside Base%": ub,
            "Cours Live":   r.live_data.get("cours"),
            "Var. Live%":   r.live_data.get("variation"),
        })

    df_res = (
        pd.DataFrame(rows)
        .sort_values("Score Global", ascending=False)
        .reset_index(drop=True)
    )
    df_res.index += 1

    medals = ["🥇", "🥈", "🥉"]
    print(f"\n{'='*80}")
    print("  📊 CLASSEMENT GLOBAL — BVC ULTIMATE ANALYZER v4.0 PRO")
    print(f"{'='*80}")
    for i, row in df_res.iterrows():
        medal = medals[i - 1] if i <= 3 else f"  {i}."
        base_s  = f"{row['Base (DH)']:.2f}" if row["Base (DH)"] is not None \
                  and not (isinstance(row["Base (DH)"], float) and np.isnan(row["Base (DH)"])) \
                  else "N/A"
        up_s    = f"+{row['Upside Base%']:.1f}%" if row["Upside Base%"] is not None \
                  and not (isinstance(row["Upside Base%"], float) and np.isnan(row["Upside Base%"])) \
                  else "N/A"
        eva_s   = f"EVA {row['EVA Spread']:+.1f}pts" if row["EVA Spread"] is not None else "EVA N/A"
        print(
            f"  {medal} {row['Ticker']:5} | {row['Prix (DH)']:>8.2f} DH | "
            f"Score {row['Score Global']:4.1f} | {row['Signal']:12} | "
            f"Base {base_s} DH ({up_s}) | {eva_s} | Flags {row['Red Flags']}"
        )

    if COLAB:
        try:
            export = f"bvc_v40_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"
            df_res.to_excel(export, index=False)
            colab_files.download(export)
            print(f"\n✅ Export téléchargé : {export}")
        except Exception as e:
            print(f"\n⚠️ Export Excel : {e}")

    print(f"\n✅ ANALYSE TERMINÉE — {len(results)} titre(s) analysé(s)")
    print("  ⚠️ Ne constitue pas un conseil en investissement (AMMC).\n")

# ============================================================
# LANCEMENT
# ============================================================

if __name__ == "__main__":
    run_colab_analysis()
