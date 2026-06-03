import logging


def _clean(val, lo, hi, name, ticker):
    if val is None:
        return None
    try:
        v = float(val)
        if lo <= v <= hi:
            return round(v, 4)
        logging.getLogger(ticker).warning(f"{name}={v} hors plage [{lo},{hi}] — ignoré")
        return None
    except (TypeError, ValueError):
        return None


def validate_ticker_data(data: dict, ticker: str) -> dict:
    """Valide et nettoie les données d'un ticker."""
    t = data.get("technical", {})
    f = data.get("fundamentals", {})
    m = data.get("market", {})

    t["rsi_14"]  = _clean(t.get("rsi_14"),   0,   100, "rsi_14",       ticker)
    t["ma20"]    = _clean(t.get("ma20"),      0.1, 1e7, "ma20",         ticker)
    t["ma50"]    = _clean(t.get("ma50"),      0.1, 1e7, "ma50",         ticker)
    t["high_90d"]= _clean(t.get("high_90d"),  0.1, 1e7, "high_90d",     ticker)
    t["low_90d"] = _clean(t.get("low_90d"),   0.1, 1e7, "low_90d",      ticker)

    f["pe_ratio_ttm"]   = _clean(f.get("pe_ratio_ttm"),   0, 500, "pe_ratio_ttm",  ticker)
    f["pe_ratio_2026e"] = _clean(f.get("pe_ratio_2026e"), 0, 500, "pe_ratio_2026e",ticker)
    f["pb_ratio"]       = _clean(f.get("pb_ratio"),       0, 100, "pb_ratio",      ticker)
    f["eps_ttm"]        = _clean(f.get("eps_ttm"),      -1e5, 1e5, "eps_ttm",      ticker)
    f["dividend_yield"] = _clean(f.get("dividend_yield"), 0,  50, "div_yield",     ticker)

    m["price"]          = _clean(m.get("price"),        0.01, 1e6, "price",        ticker)
    m["variation_pct"]  = _clean(m.get("variation_pct"), -50,  50, "variation_pct",ticker)
    m["volume"]         = _clean(m.get("volume"),         0,  1e10,"volume",       ticker)

    data["technical"]    = t
    data["fundamentals"] = f
    data["market"]       = m
    return data
