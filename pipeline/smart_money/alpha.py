"""
Métriques Smart Money — issues du backtesting v5.3
896 907 messages · 6 ans · 8 membres · 1 994 signaux
Source : SENTIMENT_CORPUS (bvc_analyzer_v53.py)
"""

# Corpus backtesté — NE PAS MODIFIER sans nouvelle validation
SENTIMENT_CORPUS = {
    "CMT":  {"smart": 0.82, "win_rate_6m": 87, "alpha_12m": 42.1},
    "SMI":  {"smart": 0.78, "win_rate_6m": 83, "alpha_12m": 38.5},
    "MNG":  {"smart": 1.00, "win_rate_6m": 93, "alpha_12m": 55.3},
    "ADI":  {"smart":-0.05, "win_rate_6m": 69, "alpha_12m":  8.5},
    "CSR":  {"smart": 0.45, "win_rate_6m": 74, "alpha_12m": 19.2},
    "AKD":  {"smart": 0.60, "win_rate_6m": 78, "alpha_12m": 22.8},
    "CFGB": {"smart": 0.38, "win_rate_6m": 71, "alpha_12m": 14.6},
    "RIS":  {"smart": 0.25, "win_rate_6m": 67, "alpha_12m": 10.3},
    "MSA":  {"smart": 0.55, "win_rate_6m": 76, "alpha_12m": 21.0},
    "CMGP": {"smart": 0.30, "win_rate_6m": 68, "alpha_12m": 11.5},
    "TGCC": {"smart": 0.50, "win_rate_6m": 75, "alpha_12m": 18.7},
    "RDS":  {"smart":-0.15, "win_rate_6m": 62, "alpha_12m":  5.2},
    "ADH":  {"smart":-0.20, "win_rate_6m": 58, "alpha_12m":  3.1},
    "SOT":  {"smart": 0.35, "win_rate_6m": 70, "alpha_12m": 13.4},
    "SRM":  {"smart": 0.20, "win_rate_6m": 65, "alpha_12m":  9.8},
    "SNA":  {"smart": 0.15, "win_rate_6m": 63, "alpha_12m":  7.6},
    "SGTM": {"smart": 0.40, "win_rate_6m": 72, "alpha_12m": 15.9},
    "CASH": {"smart": 0.28, "win_rate_6m": 66, "alpha_12m": 10.1},
    "VCNE": {"smart": 0.10, "win_rate_6m": 60, "alpha_12m":  5.5},
}

_DEFAULT = {"smart": 0.0, "win_rate_6m": 60, "alpha_12m": 0.0}


def get_smart_money(sym: str) -> dict:
    """Retourne les métriques Smart Money pour un ticker."""
    s = SENTIMENT_CORPUS.get(sym, _DEFAULT)
    return {
        "alpha_12m":      s["alpha_12m"],
        "smart_sentiment": round((s["smart"] + 1) * 50, 1),  # normalise [-1,1] → [0,100]
        "win_rate_6m":    s["win_rate_6m"],
    }
