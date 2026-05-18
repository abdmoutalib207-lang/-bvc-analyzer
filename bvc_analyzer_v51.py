# ╔══════════════════════════════════════════════════════════════════╗
# ║         BVC ANALYZER v5.1 — MOTEUR CORRIGÉ                      ║
# ║  5 corrections majeures :                                        ║
# ║  1. Signaux intelligents (7 niveaux, plus de EVITER brutal)      ║
# ║  2. MASI comme filtre de marché (Bullish/Neutral/Risk-off)       ║
# ║  3. Fibonacci automatique (zones entrée/sortie/stop)             ║
# ║  4. Classements multiples (5 tableaux)                           ║
# ║  5. ADX + OBV ajoutés aux indicateurs                            ║
# ╚══════════════════════════════════════════════════════════════════╝
#
# INSTALLATION :
# !pip install pdfplumber requests openpyxl pandas numpy -q
#
# UTILISATION COLAB :
# exec(open("bvc_analyzer_v51.py").read())
# results, scores = BVCAnalyzer().run_full_analysis()

import requests, json, time, warnings
import pandas as pd
import numpy as np
from datetime import datetime
from enum import Enum
warnings.filterwarnings("ignore")

# ── CONFIG ─────────────────────────────────────────────────────────
FOND_PATH    = "/content/fondamentaux.json"
BUY_FEE      = 0.01
SELL_FEE     = 0.01
TAX_RATE     = 0.15
ATR_MULT     = 2.5
MIN_VOL_DH   = 50_000
HEADERS_HTTP = {"User-Agent": "Mozilla/5.0", "Accept-Language": "fr-FR"}

ISIN_MAP = {
    "ADH":"MA0000011512","ADI":"MA0000011819","CMT":"MA0000011793",
    "CFGB":"MA0000012627","CMGP":"MA0000012718","CASH":"MA0000012767",
    "CSR":"MA0000012247","MNG":"MA0000011058","MSA":"MA0000012312",
    "RDS":"MA0000012239","RIS":"MA0000011462","SMI":"MA0000010068",
    "SOT":"MA0000012502","SRM":"MA0000011595","SGTM":"MA0000012783",
    "TGC":"MA0000012528","VCNE":"MA0000012759",
}

IDBOURSE_MAP = {
    "SMI":"SMI","MANAGEM":"MNG","RISMA":"RIS","RESIDENCES DAR SAADA":"RDS",
    "COSUMAR":"CSR","SOTHEMA":"SOT","ALLIANCES":"ADI",
    "SODEP-Marsa Maroc":"MSA","DOUJA PROM ADDOHA":"ADH","TGCC S.A":"TGC",
    "MINIERE TOUISSIT":"CMT","REALISATIONS MECANIQUES":"SRM",
    "CFG BANK":"CFGB","CMGP GROUP":"CMGP","VICENNE":"VCNE",
    "CASH PLUS S.A":"CASH","SGTM S.A":"SGTM",
}

# ══════════════════════════════════════════════════════════════════
# CORRECTION 1 — SIGNAUX INTELLIGENTS (7 niveaux)
# ══════════════════════════════════════════════════════════════════

class Signal(Enum):
    ACHAT_FORT      = "ACHAT FORT"
    ACHETER         = "ACHETER"
    ACCUMULER       = "ACCUMULER"
    SURVEILLER      = "SURVEILLER"
    ATTENDRE_REPLI  = "ATTENDRE REPLI"
    PRENDRE_PROFIT  = "PRENDRE PROFIT PARTIEL"
    EVITER          = "EVITER"

    def __str__(self): return self.value

    @property
    def emoji(self):
        return {
            "ACHAT FORT":             "🚀",
            "ACHETER":                "✅",
            "ACCUMULER":              "📈",
            "SURVEILLER":             "🟡",
            "ATTENDRE REPLI":         "⏳",
            "PRENDRE PROFIT PARTIEL": "💰",
            "EVITER":                 "🔴",
        }.get(self.value, "⚪")

    @property
    def couleur(self):
        return {
            "ACHAT FORT":             "#00C851",
            "ACHETER":                "#28A745",
            "ACCUMULER":              "#66BB6A",
            "SURVEILLER":             "#FFC107",
            "ATTENDRE REPLI":         "#FF9800",
            "PRENDRE PROFIT PARTIEL": "#FF6B35",
            "EVITER":                 "#DC3545",
        }.get(self.value, "#6C757D")


class MarketRegime(Enum):
    BULLISH  = "Bullish"
    NEUTRAL  = "Neutral"
    RISK_OFF = "Risk-off"


# ══════════════════════════════════════════════════════════════════
# CORRECTION 2 — MASI FILTRE DE MARCHÉ
# ══════════════════════════════════════════════════════════════════

class MASIConnector:
    """Récupère le MASI et calcule le régime de marché."""

    BASE = "https://www.idbourse.com"
    HDR  = {**HEADERS_HTTP, "Referer": "https://www.idbourse.com"}

    def get_masi(self):
        try:
            r = requests.get(
                f"{self.BASE}/api/proxy/masi-data?t={int(time.time())}",
                headers=self.HDR, timeout=10
            )
            if r.status_code == 200:
                d = r.json()
                return {
                    "value":      float(d.get("value", 0)),
                    "variation":  float(d.get("variation", 0)),
                    "volume":     float(d.get("volume_mad", 0)),
                    "ytd":        float(d.get("ytd", 0)),
                }
        except: pass
        return None

    def get_historique_masi(self, n=20):
        """Récupère l'historique MASI pour calculer MA20."""
        try:
            r = requests.get(
                f"{self.BASE}/api/proxy/masi-history",
                headers=self.HDR, timeout=10
            )
            if r.status_code == 200:
                data = r.json()
                closes = [float(d["close"]) for d in data[-n:] if "close" in d]
                return closes
        except: pass
        return []

    def get_regime(self):
        """
        Détermine le régime de marché MASI.
        Bullish  : MASI > MA20 ET variation > 0
        Risk-off : MASI < MA20 ET variation < -0.5%
        Neutral  : autres cas
        """
        masi = self.get_masi()
        if not masi:
            return MarketRegime.NEUTRAL, None

        histo = self.get_historique_masi(20)
        ma20  = np.mean(histo) if len(histo) >= 5 else masi["value"]

        value = masi["value"]
        var   = masi["variation"]

        if value > ma20 and var >= 0:
            regime = MarketRegime.BULLISH
        elif value < ma20 and var <= -0.5:
            regime = MarketRegime.RISK_OFF
        else:
            regime = MarketRegime.NEUTRAL

        masi["regime"] = regime
        masi["ma20"]   = round(ma20, 2)
        return regime, masi


# ══════════════════════════════════════════════════════════════════
# CORRECTION 3 — FIBONACCI AUTOMATIQUE
# ══════════════════════════════════════════════════════════════════

class FibonacciAnalyzer:
    """Calcule niveaux Fibonacci sur historique 20j/60j/120j."""

    NIVEAUX = [0.0, 0.236, 0.382, 0.5, 0.618, 0.786, 1.0]
    EXT     = [1.272, 1.618, 2.0]

    def calculer(self, historique: pd.Series, periode=60):
        """
        historique : pd.Series de prix de clôture
        Retourne dict avec supports, résistances, zones, stop
        """
        if len(historique) < 5:
            return None

        recent = historique.tail(min(periode, len(historique)))
        haut   = float(recent.max())
        bas    = float(recent.min())
        cours  = float(historique.iloc[-1])
        delta  = haut - bas

        if delta == 0:
            return None

        # Retracements (supports si tendance haussière)
        retracements = {}
        for n in self.NIVEAUX:
            prix = round(haut - n * delta, 2)
            retracements[f"{n*100:.1f}%"] = prix

        # Extensions (résistances)
        extensions = {}
        for n in self.EXT:
            prix = round(bas + n * delta, 2)
            extensions[f"{n*100:.1f}%"] = prix

        # Zone d'achat : entre 38.2% et 50%
        zone_achat_bas  = round(haut - 0.618 * delta, 2)
        zone_achat_haut = round(haut - 0.382 * delta, 2)

        # Stop : sous 61.8%
        stop            = round(haut - 0.786 * delta, 2)

        # Signal Fibo
        r382 = retracements["38.2%"]
        r618 = retracements["61.8%"]

        if cours <= zone_achat_haut and cours >= zone_achat_bas:
            signal_fibo = "ZONE ACHAT FIBO"
        elif cours < stop:
            signal_fibo = "SOUS SUPPORT CRITIQUE"
        elif cours >= haut * 0.97:
            signal_fibo = "PROCHE RESISTANCE"
        else:
            signal_fibo = "ENTRE NIVEAUX"

        return {
            "haut":           haut,
            "bas":            bas,
            "cours":          cours,
            "retracements":   retracements,
            "extensions":     extensions,
            "zone_achat":     (zone_achat_bas, zone_achat_haut),
            "stop_fibo":      stop,
            "support_38":     r382,
            "support_50":     retracements["50.0%"],
            "support_618":    r618,
            "resistance_127": extensions["127.2%"],
            "resistance_162": extensions["161.8%"],
            "signal_fibo":    signal_fibo,
        }

    def formater(self, fibo: dict) -> str:
        if not fibo:
            return "Données insuffisantes"
        z = fibo["zone_achat"]
        return (
            f"  Supports  : {fibo['support_38']} / {fibo['support_50']} / {fibo['support_618']} DH\n"
            f"  Résistances: {fibo['resistance_127']} / {fibo['resistance_162']} DH\n"
            f"  Zone achat : {z[0]} – {z[1]} DH\n"
            f"  Stop Fibo  : {fibo['stop_fibo']} DH\n"
            f"  Signal     : {fibo['signal_fibo']}"
        )


# ══════════════════════════════════════════════════════════════════
# CORRECTION 4 — INDICATEURS TECHNIQUES ENRICHIS (ADX + OBV)
# ══════════════════════════════════════════════════════════════════

class TechnicalIndicators:

    @staticmethod
    def sma(s, n):
        return s.rolling(n, min_periods=1).mean()

    @staticmethod
    def ema(s, n):
        return s.ewm(span=n, adjust=False).mean()

    @staticmethod
    def rsi(s, n=14):
        d = s.diff()
        g = d.clip(lower=0).rolling(n, min_periods=1).mean()
        l = (-d.clip(upper=0)).rolling(n, min_periods=1).mean()
        rs = g / l.replace(0, np.nan)
        return 100 - (100 / (1 + rs))

    @staticmethod
    def macd(s, fast=12, slow=26, sig=9):
        e1 = s.ewm(span=fast, adjust=False).mean()
        e2 = s.ewm(span=slow, adjust=False).mean()
        m  = e1 - e2
        return m, m.ewm(span=sig, adjust=False).mean()

    @staticmethod
    def bollinger(s, n=20, k=2):
        ma  = s.rolling(n, min_periods=1).mean()
        std = s.rolling(n, min_periods=1).std().fillna(0)
        return ma + k*std, ma, ma - k*std

    @staticmethod
    def atr(df, n=14):
        if {"high","low"}.issubset(df.columns):
            h, l, c = df["high"], df["low"], df["close"]
            tr = pd.concat([h-l, (h-c.shift()).abs(), (l-c.shift()).abs()], axis=1).max(axis=1)
        else:
            tr = df["close"].diff().abs().fillna(0)
        return tr.rolling(n, min_periods=1).mean()

    @staticmethod
    def adx(df, n=14):
        """Average Directional Index — mesure la force de tendance (0-100)."""
        if not {"high","low","close"}.issubset(df.columns):
            return pd.Series(np.nan, index=df.index)
        h, l, c = df["high"], df["low"], df["close"]
        tr   = pd.concat([h-l, (h-c.shift()).abs(), (l-c.shift()).abs()], axis=1).max(axis=1)
        atr  = tr.rolling(n, min_periods=1).mean()
        dm_p = (h - h.shift()).clip(lower=0)
        dm_n = (l.shift() - l).clip(lower=0)
        dm_p[dm_p < dm_n] = 0
        dm_n[dm_n < dm_p] = 0
        di_p = 100 * dm_p.rolling(n, min_periods=1).mean() / atr.replace(0, np.nan)
        di_n = 100 * dm_n.rolling(n, min_periods=1).mean() / atr.replace(0, np.nan)
        dx   = 100 * (di_p - di_n).abs() / (di_p + di_n).replace(0, np.nan)
        return dx.rolling(n, min_periods=1).mean()

    @staticmethod
    def obv(df):
        """On-Balance Volume — accumulation/distribution."""
        if "volume" not in df.columns:
            return pd.Series(np.nan, index=df.index)
        direction = np.sign(df["close"].diff().fillna(0))
        return (direction * df["volume"]).cumsum()

    @staticmethod
    def vwap(df, n=20):
        """VWAP roulant 20j."""
        if "volume" not in df.columns:
            return pd.Series(np.nan, index=df.index)
        tp = (df["close"] + df.get("high", df["close"]) + df.get("low", df["close"])) / 3
        return (tp * df["volume"]).rolling(n, min_periods=1).sum() / \
               df["volume"].rolling(n, min_periods=1).sum()

    @staticmethod
    def ichimoku(df):
        h, l = (df["high"] if "high" in df.columns else df["close"]), \
               (df["low"]  if "low"  in df.columns else df["close"])
        t  = (h.rolling(9,  min_periods=1).max() + l.rolling(9,  min_periods=1).min()) / 2
        k  = (h.rolling(26, min_periods=1).max() + l.rolling(26, min_periods=1).min()) / 2
        sa = ((t + k) / 2).shift(26)
        sb = ((h.rolling(52, min_periods=1).max() + l.rolling(52, min_periods=1).min()) / 2).shift(26)
        return t, k, sa, sb


# ══════════════════════════════════════════════════════════════════
# CONNECTEUR DE DONNÉES
# ══════════════════════════════════════════════════════════════════

class BVCDataConnector:

    M24_BASE = "https://medias24.com"
    IDB_BASE = "https://www.idbourse.com"
    HDR      = {**HEADERS_HTTP, "Referer": "https://medias24.com"}
    IDB_HDR  = {**HEADERS_HTTP, "Referer": "https://www.idbourse.com"}
    _idb_cache = {}
    _idb_ts    = 0

    def get_historique(self, ticker, isin=None):
        """Retourne DataFrame [date, close, high, low, volume]."""
        isin = isin or ISIN_MAP.get(ticker)
        if not isin:
            return pd.DataFrame()

        # Essayer splits SOT
        if ticker == "SOT":
            isin = "MA0000012833"  # post-split

        urls = [
            f"{self.M24_BASE}/content/api/getStockHistory?ISIN={isin}&period=365",
            f"{self.M24_BASE}/content/api/getStockHistory?ISIN={isin}&period=180",
        ]
        for url in urls:
            try:
                r = requests.get(url, headers=self.HDR, timeout=15)
                if r.status_code == 200:
                    data = r.json()
                    if isinstance(data, list) and len(data) > 10:
                        df = pd.DataFrame(data)
                        # Normaliser colonnes
                        col_map = {}
                        for c in df.columns:
                            cl = c.lower()
                            if "date" in cl:   col_map[c] = "date"
                            elif "close" in cl or "cloture" in cl or "dernier" in cl: col_map[c] = "close"
                            elif "high" in cl or "haut" in cl:  col_map[c] = "high"
                            elif "low"  in cl or "bas"  in cl:  col_map[c] = "low"
                            elif "vol"  in cl: col_map[c] = "volume"
                        df = df.rename(columns=col_map)
                        if "close" in df.columns:
                            df["close"] = pd.to_numeric(df["close"], errors="coerce")
                            df = df.dropna(subset=["close"]).sort_values("date")
                            return df
            except: pass
        return pd.DataFrame()

    def get_cours_live(self, ticker):
        """Retourne (cours, variation, volume, source)."""
        # 1. IDBourse
        try:
            r = requests.get(
                f"{self.IDB_BASE}/api/proxy/get_all_data",
                headers=self.IDB_HDR, timeout=10
            )
            if r.status_code == 200:
                for item in r.json():
                    nom = item.get("name","").strip()
                    if IDBOURSE_MAP.get(nom) == ticker:
                        cours = item.get("dernier_cours")
                        if cours:
                            return {
                                "cours":     float(cours),
                                "variation": float(item.get("variation", 0)),
                                "volume_mad":float(str(item.get("volume","0")).replace(" ","").replace(",",".") or 0),
                                "source":    "IDBourse",
                                "timestamp": datetime.now().strftime("%H:%M:%S"),
                            }
        except: pass

        # 2. Medias24 fallback
        isin = ISIN_MAP.get(ticker)
        if isin:
            try:
                r = requests.get(
                    f"{self.M24_BASE}/content/api/getStockInfo?ISIN={isin}",
                    headers=self.HDR, timeout=10
                )
                if r.status_code == 200:
                    d = r.json()
                    cours = d.get("dernierCours") or d.get("cours") or d.get("dernier_cours")
                    if cours:
                        return {
                            "cours":     float(cours),
                            "variation": float(d.get("variation", 0)),
                            "volume_mad":float(d.get("volumeMad") or d.get("volume_mad") or 0),
                            "source":    "Medias24",
                            "timestamp": datetime.now().strftime("%H:%M:%S"),
                        }
            except: pass

        return None

    def get_market_status(self):
        try:
            from zoneinfo import ZoneInfo
        except:
            from pytz import timezone as ZoneInfo

        tz   = ZoneInfo("Africa/Casablanca") if hasattr(ZoneInfo("Africa/Casablanca"), "key") else ZoneInfo("Africa/Casablanca")
        now  = datetime.now(tz)
        h, m = now.hour, now.minute
        is_open = (9 <= h < 15) or (h == 15 and m < 30)
        return "OPEN" if is_open else "CLOSED", now.strftime("%H:%M")


# ══════════════════════════════════════════════════════════════════
# MOTEUR DE SCORING
# ══════════════════════════════════════════════════════════════════

class TechnicalScorer:

    def scorer(self, df: pd.DataFrame):
        if df.empty or len(df) < 10:
            return 0, []

        close  = df["close"]
        obs    = []
        score  = 0
        ind    = TechnicalIndicators()

        # MAs
        ma20  = ind.sma(close, 20).iloc[-1]
        ma50  = ind.sma(close, 50).iloc[-1]
        ma200 = ind.sma(close, 200).iloc[-1]
        c     = close.iloc[-1]

        if c > ma20 > ma50:
            score += 1; obs.append("Tendance haussière forte")
        elif c > ma50:
            score += 0.5; obs.append("Moyennes mobiles mixtes")
        else:
            obs.append("Moyennes mobiles dégradées")

        if c > ma200:
            score += 1; obs.append("Prix au-dessus MA200")
        else:
            obs.append("Prix sous MA200")

        # RSI
        rsi_val = ind.rsi(close).iloc[-1]
        if 40 <= rsi_val <= 65:
            score += 1.5; obs.append(f"RSI équilibré: {rsi_val:.1f}")
        elif 65 < rsi_val <= 75:
            score += 0.5; obs.append(f"RSI positif à surveiller: {rsi_val:.1f}")
        elif rsi_val > 75:
            score += 0; obs.append(f"RSI surchauffe: {rsi_val:.1f}")
        else:
            score += 0.5; obs.append(f"RSI bas: {rsi_val:.1f}")

        # MACD
        macd_l, sig_l = ind.macd(close)
        m, s = macd_l.iloc[-1], sig_l.iloc[-1]
        m2, s2 = macd_l.iloc[-2], sig_l.iloc[-2]
        if m > s and m > 0:
            score += 1.5; obs.append("MACD haussier accélérant")
        elif m > s:
            score += 0.5; obs.append("MACD en stabilisation")
        else:
            obs.append("MACD baissier dégradé")

        # ADX — force de tendance
        if "high" in df.columns and "low" in df.columns:
            adx_val = ind.adx(df).iloc[-1]
            if not np.isnan(adx_val):
                if adx_val > 25:
                    score += 1; obs.append(f"ADX fort: {adx_val:.0f} (tendance confirmée)")
                elif adx_val > 15:
                    score += 0.5; obs.append(f"ADX modéré: {adx_val:.0f}")
                else:
                    obs.append(f"ADX faible: {adx_val:.0f} (pas de tendance)")

        # OBV
        obv_s = ind.obv(df)
        if not obv_s.isna().all():
            obv_trend = obv_s.iloc[-1] > obv_s.iloc[-5] if len(obv_s) >= 5 else None
            if obv_trend is True:
                score += 1; obs.append("OBV haussier (accumulation)")
            elif obv_trend is False:
                obs.append("OBV baissier (distribution)")

        # Bollinger
        bup, bmid, bdn = ind.bollinger(close)
        if c > bup.iloc[-1]:
            obs.append("Excès Bollinger")
        elif c < bdn.iloc[-1]:
            score += 0.5; obs.append("Rebond Bollinger possible")
        else:
            score += 0.5; obs.append("Bollinger neutre")

        # Ichimoku
        t, k, sa, sb = ind.ichimoku(df)
        if not pd.isna(sa.iloc[-1]) and not pd.isna(sb.iloc[-1]):
            nuage_haut = max(sa.iloc[-1], sb.iloc[-1])
            nuage_bas  = min(sa.iloc[-1], sb.iloc[-1])
            if c > nuage_haut:
                score += 1; obs.append("Ichimoku positif")
            elif c < nuage_bas:
                obs.append("Prix sous le nuage")
            else:
                obs.append("Prix dans le nuage")

        # Volume
        if "volume" in df.columns:
            vol_moy = df["volume"].tail(20).mean()
            vol_rec = df["volume"].iloc[-1]
            if vol_rec > vol_moy * 1.5:
                score += 0.5; obs.append("Volume supérieur moyenne")
            elif vol_rec < vol_moy * 0.3:
                obs.append("Volume très faible")
            elif vol_rec < vol_moy * 0.5:
                obs.append("Volume faible")
            else:
                obs.append("Volume modéré")

        # Momentum
        if len(close) >= 5:
            mom5  = (c / close.iloc[-5]  - 1) * 100
            mom20 = (c / close.iloc[-20] - 1) * 100 if len(close) >= 20 else None
            if mom5 > 5:
                score += 0.5; obs.append(f"Momentum 5j: +{mom5:.1f}%")
            elif mom5 < -5:
                obs.append(f"Momentum 5j: {mom5:.1f}%")
            else:
                obs.append(f"Momentum 5j: {mom5:.1f}%")

        return round(min(score, 10), 2), obs, rsi_val


class FundamentalScorer:

    def scorer(self, fond: dict):
        if not fond:
            return 0, []

        score = 0
        obs   = []

        per     = fond.get("per")
        fwd_per = fond.get("forward_per")
        cro     = fond.get("croissance_ca", 0) or 0
        dette   = fond.get("dette_nette_ebitda", 0) or 0
        roic    = fond.get("roic", 0) or 0
        wacc    = fond.get("wacc", 10) or 10
        marge   = fond.get("marge_nette", 0) or 0
        cash    = fond.get("cash_conversion", 0) or 0
        div     = fond.get("div_yield", 0) or 0

        # PER
        if per:
            if per < 12:   score += 2; obs.append("PER attractif")
            elif per < 20: score += 1.5; obs.append("PER raisonnable")
            elif per < 30: score += 0.5; obs.append("PER élevé")
            else:           obs.append("PER très élevé")

        # Forward PER
        if fwd_per and per and fwd_per < per * 0.85:
            score += 1; obs.append("Forward PER en rerating")

        # Croissance
        if cro > 30:   score += 2; obs.append("Croissance forte")
        elif cro > 10: score += 1; obs.append("Croissance solide")
        elif cro > 0:  score += 0.5; obs.append("Croissance faible")
        else:           obs.append("Croissance nulle/négative")

        # Dette
        if dette < 1:    score += 1.5; obs.append("Dette très faible")
        elif dette < 2:  score += 1;   obs.append("Dette faible")
        elif dette < 3:  score += 0.5; obs.append("Dette modérée")
        elif dette < 4:  obs.append("Dette élevée")
        else:             obs.append("Dette très élevée")

        # EVA
        eva = roic - wacc
        if eva > 8:    score += 2; obs.append("Forte création de valeur")
        elif eva > 3:  score += 1.5; obs.append("Création de valeur")
        elif eva > 0:  score += 0.5; obs.append("Création de valeur faible")
        else:           obs.append("ROIC inférieur au WACC")

        # Marge
        if marge > 20:   score += 1; obs.append("Marge nette élevée")
        elif marge > 10: score += 0.5; obs.append("Marge solide")
        elif marge > 5:  obs.append("Marge correcte")
        else:             obs.append("Marge faible")

        # Cash conversion
        if cash > 80:   score += 0.5; obs.append("Cash conversion excellente")
        elif cash > 60: obs.append("Cash conversion correcte")
        elif cash > 40: obs.append("Cash conversion moyenne")
        else:            obs.append("Cash conversion faible")

        # Dividende
        if div > 4:     score += 1; obs.append("Dividende élevé")
        elif div > 2:   score += 0.5; obs.append("Dividende modeste")

        return round(min(score, 10), 2), obs


class RedFlagDetector:

    NIVEAUX = {
        "CRITIQUE": 3,
        "ELEVEE":   2,
        "MOYENNE":  1,
    }

    def detecter(self, fond, score_tech, rsi_val=None):
        flags = []

        per   = fond.get("per")
        dette = fond.get("dette_nette_ebitda", 0) or 0
        roic  = fond.get("roic", 0) or 0
        wacc  = fond.get("wacc", 10) or 10
        marge = fond.get("marge_nette", 0) or 0
        cash  = fond.get("cash_conversion", 0) or 0

        if dette > 5:
            flags.append(("CRITIQUE", "Structure", "Dette critique > 5x EBITDA", True))
        elif dette > 3:
            flags.append(("ELEVEE", "Structure", "Dette élevée", False))

        if roic < wacc:
            flags.append(("ELEVEE", "Rentabilité", "ROIC inférieur au WACC", False))

        if marge < 3 and marge > 0:
            flags.append(("MOYENNE", "Rentabilité", "Marge nette faible", False))

        if cash < 40:
            flags.append(("MOYENNE", "Cash-flow", "Cash conversion faible", False))

        # RSI — plus jamais CRITIQUE bloquant seul
        if rsi_val and rsi_val > 80:
            flags.append(("MOYENNE", "Technique", f"RSI surchauffe extrême ({rsi_val:.0f})", False))
        elif rsi_val and rsi_val > 70:
            flags.append(("INFO", "Technique", f"RSI surchauffe ({rsi_val:.0f})", False))

        return flags


# ══════════════════════════════════════════════════════════════════
# MOTEUR DE DÉCISION INTELLIGENT
# ══════════════════════════════════════════════════════════════════

class DecisionEngine:
    """
    Décision basée sur :
    - Score global
    - Régime MASI
    - RSI
    - Red flags
    - Fibonacci
    """

    def decider(self, score_global, score_tech, score_fond,
                red_flags, regime, rsi_val, fibo, fond):

        # Flags critiques (bloquants)
        flags_critiques = [f for f in red_flags if f[0] == "CRITIQUE"]

        # Ajustement par régime MASI
        bonus_regime = {
            MarketRegime.BULLISH:  0.5,
            MarketRegime.NEUTRAL:  0.0,
            MarketRegime.RISK_OFF: -0.5,
        }.get(regime, 0.0)

        score_ajuste = score_global + bonus_regime

        # Cas RSI surchauffe > 80 — PRENDRE PROFIT si bons fondamentaux
        if rsi_val and rsi_val > 80:
            if score_fond >= 7:
                return Signal.PRENDRE_PROFIT, "Fondamentaux forts mais RSI surchauffe — sécuriser gains"
            else:
                return Signal.ATTENDRE_REPLI, "RSI surchauffe — attendre respiration"

        # Cas RSI surchauffe modéré 70-80
        if rsi_val and 70 < rsi_val <= 80:
            if score_ajuste >= 7:
                return Signal.SURVEILLER, "Tendance forte — entrée tardive, surveiller pullback"

        # Blocage par flag critique fondamental (pas technique)
        flags_crit_fond = [f for f in flags_critiques if f[1] != "Technique"]
        if flags_crit_fond:
            return Signal.EVITER, f"Flag critique : {flags_crit_fond[0][2]}"

        # Zone Fibo achat
        fibo_achat = fibo and fibo.get("signal_fibo") == "ZONE ACHAT FIBO"

        # Décision principale
        if score_ajuste >= 8.5 and regime != MarketRegime.RISK_OFF:
            if fibo_achat:
                return Signal.ACHAT_FORT, "Score élevé + zone Fibo + marché favorable"
            return Signal.ACHAT_FORT, "Score élevé + marché favorable"

        elif score_ajuste >= 7.5:
            if fibo_achat:
                return Signal.ACHETER, "Bon score + zone entrée Fibo confirmée"
            return Signal.ACHETER, "Bon score global"

        elif score_ajuste >= 6.5:
            if fibo_achat:
                return Signal.ACCUMULER, "Score correct + zone Fibo favorable"
            return Signal.SURVEILLER, "Score correct — surveiller point d'entrée"

        elif score_ajuste >= 5.0:
            if fibo and fibo.get("signal_fibo") == "PROCHE RESISTANCE":
                return Signal.PRENDRE_PROFIT, "Proche résistance Fibo — alléger"
            return Signal.SURVEILLER, "Score moyen"

        elif score_ajuste >= 3.5:
            if regime == MarketRegime.RISK_OFF:
                return Signal.EVITER, "Score faible + marché Risk-off"
            return Signal.ATTENDRE_REPLI, "Score insuffisant — attendre meilleur point"

        else:
            return Signal.EVITER, "Score trop faible"


# ══════════════════════════════════════════════════════════════════
# RÉSULTAT D'ANALYSE
# ══════════════════════════════════════════════════════════════════

class AnalysisResult:
    def __init__(self):
        self.ticker         = ""
        self.price          = 0.0
        self.signal         = Signal.SURVEILLER
        self.raison_signal  = ""
        self.score_global   = 0.0
        self.score_technical= 0.0
        self.score_fundamental = 0.0
        self.rsi            = 0.0
        self.red_flags      = []
        self.obs_tech       = []
        self.obs_fond       = []
        self.fibo           = None
        self.live_data      = {}
        self.fundamental_data = {}
        self.regime         = MarketRegime.NEUTRAL
        self.valuation      = None
        self.date           = datetime.now()
        self.setup          = ""

    @property
    def signal_emoji(self):
        return self.signal.emoji

    @property
    def signal_couleur(self):
        return self.signal.couleur


# ══════════════════════════════════════════════════════════════════
# CORRECTION 5 — CLASSEMENTS MULTIPLES
# ══════════════════════════════════════════════════════════════════

class ClassementEngine:
    """5 classements intelligents."""

    def generer(self, results: dict):
        items = list(results.values())

        def top(lst, n=5):
            return sorted(lst, key=lambda r: r.score_global, reverse=True)[:n]

        # 1. Top Momentum — meilleur score technique + RSI entre 50-70
        momentum = sorted(
            [r for r in items if 50 <= r.rsi <= 72],
            key=lambda r: r.score_technical, reverse=True
        )[:5]

        # 2. Top Fondamental — meilleur score fondamental
        fondamental = sorted(
            items, key=lambda r: r.score_fundamental, reverse=True
        )[:5]

        # 3. Top Rebond — RSI < 40, score fond > 4
        rebond = sorted(
            [r for r in items if r.rsi < 45 and r.score_fundamental >= 4],
            key=lambda r: r.score_fundamental, reverse=True
        )[:5]

        # 4. Top Risque Faible — pas de red flag ELEVEE/CRITIQUE
        risque_faible = sorted(
            [r for r in items if not any(f[0] in ("CRITIQUE","ELEVEE") for f in r.red_flags)],
            key=lambda r: r.score_global, reverse=True
        )[:5]

        # 5. Top Opportunité Prix — upside > 10% + signal pas EVITER
        def upside(r):
            v = r.valuation
            if v and r.price:
                base = getattr(v, "base", None)
                if base:
                    return (base / r.price - 1) * 100
            return -999

        opportunite = sorted(
            [r for r in items if upside(r) > 10 and r.signal != Signal.EVITER],
            key=upside, reverse=True
        )[:5]

        # Alertes
        surchauffe   = [r for r in items if r.rsi > 75]
        breakout     = [r for r in items if r.fibo and r.fibo.get("signal_fibo") == "PROCHE RESISTANCE"]
        support_fibo = [r for r in items if r.fibo and r.fibo.get("signal_fibo") == "ZONE ACHAT FIBO"]
        a_eviter     = [r for r in items if r.signal == Signal.EVITER]

        return {
            "top_momentum":   momentum,
            "top_fondamental":fondamental,
            "top_rebond":     rebond,
            "top_risque_faible": risque_faible,
            "top_opportunite": opportunite,
            "surchauffe":     surchauffe,
            "breakout":       breakout,
            "support_fibo":   support_fibo,
            "a_eviter":       a_eviter,
        }

    def afficher(self, classements):
        print("\n" + "="*65)
        print(" CLASSEMENTS MULTIPLES BVC v5.1")
        print("="*65)

        sections = [
            ("🚀 TOP MOMENTUM",         "top_momentum"),
            ("📊 TOP FONDAMENTAL",       "top_fondamental"),
            ("🔄 TOP REBOND",            "top_rebond"),
            ("🛡️  TOP RISQUE FAIBLE",    "top_risque_faible"),
            ("💰 TOP OPPORTUNITÉ PRIX",  "top_opportunite"),
        ]

        for titre, key in sections:
            lst = classements.get(key, [])
            print(f"\n{titre}")
            print("-"*40)
            if not lst:
                print("  Aucun titre")
            for i, r in enumerate(lst, 1):
                v    = r.valuation
                base = getattr(v, "base", None) if v else None
                ups  = f"{(base/r.price-1)*100:+.0f}%" if base and r.price else "—"
                print(f"  {i}. {r.ticker:<6} {r.signal.emoji} {str(r.signal):<22} "
                      f"Score:{r.score_global}  Upside:{ups}")

        print("\n⚠️  ALERTES")
        print("-"*40)
        if classements["surchauffe"]:
            print(f"  RSI>75 : {', '.join(r.ticker for r in classements['surchauffe'])}")
        if classements["support_fibo"]:
            print(f"  Zone Fibo achat : {', '.join(r.ticker for r in classements['support_fibo'])}")
        if classements["a_eviter"]:
            print(f"  À éviter : {', '.join(r.ticker for r in classements['a_eviter'])}")


# ══════════════════════════════════════════════════════════════════
# VALORISATION
# ══════════════════════════════════════════════════════════════════

class ValuationResult:
    def __init__(self, base, bear, bull, premium, confiance):
        self.base = base; self.bear = bear; self.bull = bull
        self.premium = premium; self.confiance = confiance


class ValuationEngine:

    def valoriser(self, ticker, cours, fond, liquidity_decote=0):
        if not fond or not cours:
            return None

        per   = fond.get("per")
        fwd   = fond.get("forward_per")
        bpa26 = fond.get("bpa_2026")
        cro   = fond.get("croissance_ca", 10) or 10
        eva   = (fond.get("roic", 10) or 10) - (fond.get("wacc", 10) or 10)

        targets = []

        if bpa26 and fwd:
            targets.append(bpa26 * fwd)
        if bpa26 and per:
            targets.append(bpa26 * per * 1.1)

        if not targets:
            # Fallback PEG
            if per and cro > 0:
                peg_fair = per * (1 + cro/100)
                targets.append(cours * peg_fair / per)

        if not targets:
            return None

        base    = round(np.mean(targets) * (1 - liquidity_decote/100), 2)
        premium = round((base / cours - 1) * 100, 1)

        # Bear/Bull
        adj = 0.30 + min(abs(eva) * 0.02, 0.20)
        bear = round(base * (1 - adj), 2)
        bull = round(base * (1 + adj), 2)

        confiance = "Haute" if (bpa26 and fwd) else "Moyenne"

        return ValuationResult(base, bear, bull, premium, confiance)


# ══════════════════════════════════════════════════════════════════
# ORCHESTRATEUR PRINCIPAL
# ══════════════════════════════════════════════════════════════════

class BVCAnalyzer:

    def __init__(self, fond_path=FOND_PATH):
        self.data      = BVCDataConnector()
        self.tech      = TechnicalScorer()
        self.fond_sc   = FundamentalScorer()
        self.red       = RedFlagDetector()
        self.decision  = DecisionEngine()
        self.fibo_an   = FibonacciAnalyzer()
        self.val_eng   = ValuationEngine()
        self.classem   = ClassementEngine()
        self.masi_con  = MASIConnector()

        with open(fond_path, "r", encoding="utf-8") as f:
            self.fond_data = json.load(f)

        self.tickers = list(self.fond_data.keys())

    def analyser_ticker(self, ticker, regime):
        r = AnalysisResult()
        r.ticker = ticker
        r.regime = regime

        fond = self.fond_data.get(ticker, {})
        r.fundamental_data = fond

        # Cours live
        live = self.data.get_cours_live(ticker)
        r.live_data = live or {}

        # Historique
        df = self.data.get_historique(ticker)

        # Prix de référence
        if not df.empty:
            r.price = float(df["close"].iloc[-1])
        elif live:
            r.price = live["cours"]
        else:
            r.price = 0

        # Score technique
        if not df.empty:
            result_tech = self.tech.scorer(df)
            r.score_technical = result_tech[0]
            r.obs_tech        = result_tech[1]
            r.rsi             = result_tech[2] if len(result_tech) > 2 else 50.0
        else:
            r.score_technical = 0
            r.obs_tech        = ["Pas d'historique disponible"]
            r.rsi             = 50.0

        # Score fondamental
        r.score_fundamental, r.obs_fond = self.fond_sc.scorer(fond)

        # Red flags
        r.red_flags = self.red.detecter(fond, r.score_technical, r.rsi)

        # Liquidité
        liq_tier   = 1.0
        liq_decote = 0
        if live:
            vol = live.get("volume_mad", 0) or 0
            if vol > 10_000_000:   liq_tier = 1.0; liq_decote = 0
            elif vol > 5_000_000:  liq_tier = 0.9; liq_decote = 5
            elif vol > 1_000_000:  liq_tier = 0.8; liq_decote = 10
            elif vol > 500_000:    liq_tier = 0.7; liq_decote = 15
            else:                  liq_tier = 0.6; liq_decote = 20

        # Pondération dynamique
        poids_tech = 0.6 * liq_tier + 0.4 * (1 - liq_tier)
        poids_fond = 1 - poids_tech

        r.score_global = round(
            r.score_technical * poids_tech + r.score_fundamental * poids_fond, 2
        )

        # Fibonacci
        if not df.empty:
            r.fibo = self.fibo_an.calculer(df["close"])

        # Setup
        if r.rsi > 75:
            r.setup = "MOMENTUM CONFIRMÉ"
        elif r.rsi < 35:
            r.setup = "SURVENTE"
        elif r.fibo and r.fibo.get("signal_fibo") == "ZONE ACHAT FIBO":
            r.setup = "PULLBACK HAUSSIER"
        else:
            r.setup = "NEUTRE"

        # Valorisation
        r.valuation = self.val_eng.valoriser(ticker, r.price, fond, liq_decote)

        # Décision intelligente
        r.signal, r.raison_signal = self.decision.decider(
            r.score_global, r.score_technical, r.score_fundamental,
            r.red_flags, regime, r.rsi, r.fibo, fond
        )

        return r

    def run_full_analysis(self):
        print("\n" + "="*65)
        print(" BVC ANALYZER v5.1 — ANALYSE COMPLÈTE")
        print(" Signaux intelligents + MASI + Fibonacci + Classements")
        print("="*65)
        print(f" Heure : {datetime.now().strftime('%d/%m/%Y %H:%M')}")

        # Régime MASI
        regime, masi_data = self.masi_con.get_regime()
        status, heure = self.data.get_market_status()

        if masi_data:
            print(f" MASI  : {masi_data['value']:,.2f} pts ({masi_data['variation']:+.2f}%)")
            print(f" Régime: {regime.value} | Marché: {status} {heure}")
        else:
            print(f" Régime MASI: {regime.value} | Marché: {status} {heure}")

        print("="*65)
        print(f"\n Analyse de {len(self.tickers)} titres...\n")

        results = {}
        for ticker in self.tickers:
            try:
                r = self.analyser_ticker(ticker, regime)
                results[ticker] = r
                live_cours = r.live_data.get("cours", r.price) if r.live_data else r.price
                live_var   = r.live_data.get("variation", 0) if r.live_data else 0
                print(f"  ✅ {ticker:<6} | {live_cours:>9.2f} DH | "
                      f"{live_var:>+6.2f}% | {r.signal.emoji} {str(r.signal):<22} "
                      f"| Score {r.score_global}")
            except Exception as e:
                print(f"  ❌ {ticker:<6} | Erreur: {e}")

        # Classements
        classements = self.classem.generer(results)
        self.classem.afficher(classements)

        # Classement global
        print("\n" + "="*65)
        print(" CLASSEMENT GLOBAL")
        print("="*65)
        print(f"{'#':<3} {'TICKER':<6} {'LIVE':>8} {'VAR':>7} {'SIGNAL':<24} "
              f"{'SCORE':>6} {'FIBO':>12} {'UPSIDE':>7} {'RÉGIME'}")
        print("-"*95)

        classes = sorted(results.items(), key=lambda x: x[1].score_global, reverse=True)
        for i, (t, r) in enumerate(classes, 1):
            live  = r.live_data.get("cours", r.price) if r.live_data else r.price
            var   = r.live_data.get("variation", 0) if r.live_data else 0
            fibo_s = r.fibo.get("signal_fibo","—")[:12] if r.fibo else "—"
            base  = getattr(r.valuation, "base", None) if r.valuation else None
            ups   = f"{(base/r.price-1)*100:+.0f}%" if base and r.price else "—"
            print(f"{i:<3} {t:<6} {live:>8.1f} {var:>+6.1f}%  "
                  f"{r.signal.emoji}{str(r.signal):<22} {r.score_global:>5}  "
                  f"{fibo_s:>12} {ups:>7}  {r.regime.value}")

        print("="*65)
        print("\n✅ ANALYSE TERMINÉE — BVC Analyzer v5.1\n")

        return results, classements
