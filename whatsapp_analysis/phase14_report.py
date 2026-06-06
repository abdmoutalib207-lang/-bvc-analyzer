"""
Phase 14 — Génération du Rapport HTML Institutionnel
Rapport complet auto-contenu avec ApexCharts et Jinja2
Style Bloomberg Terminal — BVC WhatsApp Intelligence System
"""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# Jinja2
try:
    from jinja2 import Environment, BaseLoader
    JINJA2_AVAILABLE = True
except ImportError:
    JINJA2_AVAILABLE = False

# ─────────────────────────────────────────────────────────────
# CONFIGURATION
# ─────────────────────────────────────────────────────────────

REPORT_DATE = datetime.now().strftime("%d %B %Y")


# ─────────────────────────────────────────────────────────────
# SÉRIALISATION DES DONNÉES POUR APEXCHARTS
# ─────────────────────────────────────────────────────────────

def _ts_ms(ts) -> int:
    """Convert pandas Timestamp to milliseconds."""
    return int(pd.Timestamp(ts).timestamp() * 1000)


def serialize_fear_greed(fear_greed_series):
    """Resample weekly, return list of {x: ms, y: float}."""
    if fear_greed_series is None or (hasattr(fear_greed_series, "empty") and fear_greed_series.empty):
        return []
    fg = fear_greed_series.copy()
    fg.index = pd.to_datetime(fg.index)
    fg = fg.resample("W").mean().dropna()
    return [{"x": _ts_ms(ts), "y": round(float(v), 1)} for ts, v in fg.items()]


def serialize_sentiment(daily_sentiment):
    """Resample weekly, return list of {x: ms, y: float}."""
    if daily_sentiment is None or (hasattr(daily_sentiment, "empty") and daily_sentiment.empty):
        return []
    ds = daily_sentiment.copy()
    ds["date"] = pd.to_datetime(ds["date"])
    ds = ds.set_index("date")
    if "sentiment_mean" in ds.columns:
        w = ds["sentiment_mean"].resample("W").mean().dropna()
        return [{"x": _ts_ms(ts), "y": round(float(v), 3)} for ts, v in w.items()]
    return []


def serialize_equity_curves(equity_curves):
    """Resample monthly for performance. Return list of {name, data: [{x,y}]}."""
    if not equity_curves:
        return []
    result = []
    for name, eq in equity_curves.items():
        if eq is None or (hasattr(eq, "empty") and eq.empty):
            continue
        eq = eq.dropna()
        if len(eq) < 2:
            continue
        if len(eq) > 200:
            eq = eq.resample("ME").last().dropna()
        data = []
        for ts, val in eq.items():
            try:
                data.append({"x": _ts_ms(ts), "y": round(float(val), 2)})
            except Exception:
                pass
        if data:
            result.append({
                "name": name.replace("_", " "),
                "data": data,
                "bench": "BuyAndHold" in name or "MASI" in name,
            })
    return result


def _compute_sms_score(ms: pd.DataFrame) -> pd.Series:
    """Compute a proxy Smart Money score from available columns when sms_score is all NaN."""
    sms_col = next((c for c in ["sms_score", "smart_money_score", "score"] if c in ms.columns), None)
    if sms_col and ms[sms_col].notna().any():
        return ms[sms_col].fillna(0)
    # Fallback: compose from normalized columns that exist
    score = pd.Series(0.0, index=ms.index)
    if "win_rate_norm" in ms.columns:
        score += ms["win_rate_norm"].fillna(0) * 0.40
    if "timeliness_norm" in ms.columns:
        score += ms["timeliness_norm"].fillna(0) * 0.35
    if "n_calls" in ms.columns:
        c = ms["n_calls"].fillna(0)
        mx = c.max()
        if mx > 0:
            score += (c / mx * 100) * 0.25
    elif "n_signals" in ms.columns:
        c = ms["n_signals"].fillna(0)
        mx = c.max()
        if mx > 0:
            score += (c / mx * 100) * 0.25
    return score.clip(0, 100)


def serialize_smart_money(member_scores, n=20):
    """Return {categories: [names], data: [scores]}."""
    if member_scores is None or (hasattr(member_scores, "empty") and member_scores.empty):
        return {"categories": [], "data": []}
    ms = member_scores.copy()
    ms["_score"] = _compute_sms_score(ms)
    top = ms.nlargest(n, "_score")
    names, scores = [], []
    for idx, row in top.iterrows():
        name = str(row.get("author", idx))[:18]
        names.append(name)
        scores.append(round(float(row["_score"]), 1))
    return {"categories": names[::-1], "data": scores[::-1]}


def serialize_ml_models(phase9_results):
    """Return list of {model, auc, f1, precision, recall, is_best}."""
    if not phase9_results or "model_results" not in phase9_results:
        return []
    best = phase9_results["model_results"].get("_best_model_name", "")
    result = []
    for model, metrics in phase9_results["model_results"].items():
        if model.startswith("_") or not isinstance(metrics, dict):
            continue
        result.append({
            "model": model,
            "auc": round(float(metrics.get("auc_roc", 0.5)), 4),
            "f1": round(float(metrics.get("f1", 0)), 4),
            "precision": round(float(metrics.get("precision", 0)), 4),
            "recall": round(float(metrics.get("recall", 0)), 4),
            "is_best": model == best,
        })
    return result


# ─────────────────────────────────────────────────────────────
# TEMPLATE HTML — DARK BLOOMBERG TERMINAL THEME
# ─────────────────────────────────────────────────────────────

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1.0"/>
<title>BVC WhatsApp Intelligence System — Rapport Phase 14</title>
<meta name="theme-color" content="#080d1a"/>
<link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@300;400;500;600;700&display=swap" rel="stylesheet"/>
<script src="https://cdn.jsdelivr.net/npm/apexcharts@3.45.2/dist/apexcharts.min.js"></script>
<style>
:root {
  --bg: #080d1a;
  --bg2: #0d1829;
  --bg3: #0a1220;
  --bd: #1a2540;
  --text: #c8d3e8;
  --dim: #8892a4;
  --green: #00e5a0;
  --blue: #4db8ff;
  --yel: #ffd740;
  --red: #ff4f5a;
  --pur: #b388ff;
  --org: #ff8f00;
  --font: 'IBM Plex Mono', 'Courier New', monospace;
}
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
html { scroll-behavior: smooth; }
body {
  background: var(--bg);
  color: var(--text);
  font-family: var(--font);
  font-size: 13px;
  line-height: 1.6;
  min-height: 100vh;
}
::-webkit-scrollbar { width: 5px; height: 5px; }
::-webkit-scrollbar-track { background: var(--bg); }
::-webkit-scrollbar-thumb { background: var(--bd); border-radius: 3px; }

/* ── NAV ── */
.nav {
  position: sticky;
  top: 0;
  z-index: 100;
  background: var(--bg3);
  border-bottom: 1px solid var(--bd);
  display: flex;
  align-items: center;
  padding: 0 24px;
  height: 44px;
  gap: 24px;
}
.nav-logo {
  font-size: 14px;
  font-weight: 700;
  color: var(--green);
  letter-spacing: 2px;
  white-space: nowrap;
  text-shadow: 0 0 12px rgba(0,229,160,0.5);
}
.nav-tabs {
  display: flex;
  gap: 4px;
  flex: 1;
  overflow-x: auto;
}
.nav-tabs::-webkit-scrollbar { height: 2px; }
.nav-tab {
  color: var(--dim);
  text-decoration: none;
  font-size: 11px;
  font-weight: 500;
  letter-spacing: 1px;
  padding: 4px 10px;
  border-radius: 3px;
  white-space: nowrap;
  transition: color .2s, background .2s;
}
.nav-tab:hover {
  color: var(--blue);
  background: rgba(77,184,255,0.08);
}
.nav-status {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 11px;
  color: var(--dim);
  white-space: nowrap;
}
.status-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: var(--green);
  box-shadow: 0 0 6px var(--green);
  animation: pulse 2s infinite;
}
@keyframes pulse { 0%,100% { opacity: 1; } 50% { opacity: 0.4; } }

/* ── LAYOUT ── */
.page { max-width: 1400px; margin: 0 auto; padding: 24px 24px 80px; }

/* ── HEADER BLOCK ── */
.report-header {
  background: var(--bg2);
  border: 1px solid var(--bd);
  border-radius: 6px;
  padding: 32px 36px;
  margin-bottom: 24px;
  position: relative;
  overflow: hidden;
}
.report-header::before {
  content: '';
  position: absolute;
  top: 0; left: 0; right: 0;
  height: 2px;
  background: linear-gradient(90deg, var(--green), var(--blue), var(--pur));
}
.report-header-title {
  font-size: 22px;
  font-weight: 700;
  color: var(--green);
  letter-spacing: 3px;
  text-shadow: 0 0 20px rgba(0,229,160,0.4);
  margin-bottom: 8px;
}
.report-header-sub {
  font-size: 13px;
  color: var(--dim);
  letter-spacing: 1px;
}
.report-header-meta {
  margin-top: 16px;
  font-size: 11px;
  color: var(--dim);
}
.report-header-meta span { color: var(--blue); }

/* ── KPI STRIP ── */
.kpi-strip {
  display: grid;
  grid-template-columns: repeat(6, 1fr);
  gap: 12px;
  margin-bottom: 24px;
}
@media (max-width: 1100px) { .kpi-strip { grid-template-columns: repeat(3, 1fr); } }
@media (max-width: 640px)  { .kpi-strip { grid-template-columns: repeat(2, 1fr); } }
.kpi-card {
  background: var(--bg2);
  border: 1px solid var(--bd);
  border-radius: 6px;
  padding: 16px 14px;
  position: relative;
  overflow: hidden;
}
.kpi-card::after {
  content: '';
  position: absolute;
  bottom: 0; left: 0; right: 0;
  height: 2px;
  background: var(--green);
  box-shadow: 0 0 8px var(--green);
}
.kpi-label {
  font-size: 10px;
  color: var(--dim);
  letter-spacing: 1px;
  text-transform: uppercase;
  margin-bottom: 6px;
}
.kpi-value {
  font-size: 22px;
  font-weight: 700;
  color: var(--green);
  text-shadow: 0 0 12px rgba(0,229,160,0.35);
  letter-spacing: 1px;
}
.kpi-sub { font-size: 10px; color: var(--dim); margin-top: 4px; }

/* ── SECTION WRAPPER ── */
.section {
  background: var(--bg2);
  border: 1px solid var(--bd);
  border-radius: 6px;
  padding: 28px;
  margin-bottom: 20px;
}
.section-header {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 20px;
  padding-bottom: 12px;
  border-bottom: 1px solid var(--bd);
}
.section-tag {
  background: rgba(0,229,160,0.12);
  color: var(--green);
  border: 1px solid rgba(0,229,160,0.25);
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 2px;
  padding: 3px 8px;
  border-radius: 3px;
}
.section-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--text);
  letter-spacing: 2px;
  text-transform: uppercase;
}
.section-dim { font-size: 11px; color: var(--dim); margin-left: auto; }

/* ── GRID LAYOUTS ── */
.grid-2 { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }
.grid-3 { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 16px; }
@media (max-width: 900px) { .grid-2 { grid-template-columns: 1fr; } }
@media (max-width: 900px) { .grid-3 { grid-template-columns: 1fr 1fr; } }

/* ── PICKS GRID ── */
.picks-grid {
  display: grid;
  grid-template-columns: repeat(5, 1fr);
  gap: 12px;
  margin-bottom: 16px;
}
@media (max-width: 1100px) { .picks-grid { grid-template-columns: repeat(3, 1fr); } }
@media (max-width: 640px)  { .picks-grid { grid-template-columns: repeat(2, 1fr); } }
.pick-card {
  background: var(--bg3);
  border: 1px solid var(--bd);
  border-radius: 6px;
  padding: 16px 12px;
  text-align: center;
  transition: transform .2s, border-color .2s;
}
.pick-card:hover { transform: translateY(-2px); }
.pick-card.FORT_ACHAT { border-color: var(--green); box-shadow: 0 0 16px rgba(0,229,160,0.15); }
.pick-card.ACHAT      { border-color: rgba(0,229,160,0.4); }
.pick-card.NEUTRE     { border-color: var(--yel); }
.pick-card.VENTE      { border-color: var(--org); }
.pick-card.FORT_VENTE { border-color: var(--red); }
.pick-ticker { font-size: 20px; font-weight: 700; color: var(--text); letter-spacing: 2px; }
.pick-name   { font-size: 10px; color: var(--dim); margin: 4px 0 8px; }
.pick-score  { font-size: 18px; font-weight: 700; }
.pick-card.FORT_ACHAT .pick-score { color: var(--green); text-shadow: 0 0 10px rgba(0,229,160,0.5); }
.pick-card.ACHAT      .pick-score { color: var(--green); }
.pick-card.NEUTRE     .pick-score { color: var(--yel); }
.pick-card.VENTE      .pick-score { color: var(--org); }
.pick-card.FORT_VENTE .pick-score { color: var(--red); }

/* ── SIGNAL BADGE ── */
.badge {
  display: inline-block;
  padding: 2px 8px;
  border-radius: 3px;
  font-size: 10px;
  font-weight: 600;
  letter-spacing: 1px;
}
.badge-FORT_ACHAT { background: rgba(0,229,160,0.18); color: var(--green); border: 1px solid rgba(0,229,160,0.35); box-shadow: 0 0 8px rgba(0,229,160,0.2); }
.badge-ACHAT      { background: rgba(0,229,160,0.1);  color: var(--green); border: 1px solid rgba(0,229,160,0.2); }
.badge-NEUTRE     { background: rgba(255,215,64,0.12); color: var(--yel);  border: 1px solid rgba(255,215,64,0.25); }
.badge-VENTE      { background: rgba(255,143,0,0.12);  color: var(--org);  border: 1px solid rgba(255,143,0,0.25); }
.badge-FORT_VENTE { background: rgba(255,79,90,0.15);  color: var(--red);  border: 1px solid rgba(255,79,90,0.3); }

/* ── CHARTS ── */
.chart-wrap { background: var(--bg3); border: 1px solid var(--bd); border-radius: 6px; padding: 16px; }
.chart-title { font-size: 11px; font-weight: 600; color: var(--dim); letter-spacing: 2px; text-transform: uppercase; margin-bottom: 12px; }

/* ── TABLES ── */
.tbl-wrap { overflow-x: auto; }
.tbl-search {
  width: 100%;
  background: var(--bg3);
  border: 1px solid var(--bd);
  border-radius: 4px;
  color: var(--text);
  font-family: var(--font);
  font-size: 12px;
  padding: 8px 12px;
  margin-bottom: 12px;
  outline: none;
  transition: border-color .2s;
}
.tbl-search:focus { border-color: var(--blue); }
table { width: 100%; border-collapse: collapse; font-size: 12px; }
th {
  background: var(--bg3);
  color: var(--dim);
  font-weight: 600;
  font-size: 10px;
  letter-spacing: 1.5px;
  text-transform: uppercase;
  padding: 10px 12px;
  border-bottom: 1px solid var(--bd);
  text-align: left;
  cursor: pointer;
  white-space: nowrap;
  user-select: none;
}
th:hover { color: var(--blue); }
th.sort-asc::after  { content: ' ▲'; color: var(--green); }
th.sort-desc::after { content: ' ▼'; color: var(--green); }
td {
  padding: 8px 12px;
  border-bottom: 1px solid rgba(26,37,64,0.5);
  color: var(--text);
  white-space: nowrap;
}
tr:hover td { background: rgba(77,184,255,0.05); }

/* ── STAT ROW ── */
.stat-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 0;
  border-bottom: 1px solid rgba(26,37,64,0.6);
}
.stat-label { color: var(--dim); font-size: 12px; }
.stat-value { color: var(--text); font-weight: 600; }

/* ── KEY FINDINGS ── */
.finding {
  padding: 8px 12px;
  border-left: 2px solid var(--blue);
  background: rgba(77,184,255,0.05);
  margin-bottom: 8px;
  border-radius: 0 4px 4px 0;
  font-size: 12px;
  color: var(--text);
}

/* ── ALERTS ── */
.alert {
  padding: 12px 16px;
  border-radius: 4px;
  border-left: 3px solid;
  font-size: 12px;
  margin: 10px 0;
}
.alert-warning { background: rgba(255,215,64,0.08); border-color: var(--yel); color: var(--yel); }
.alert-danger   { background: rgba(255,79,90,0.08);  border-color: var(--red); color: var(--red); }
.alert-info     { background: rgba(77,184,255,0.08); border-color: var(--blue); color: var(--blue); }
.alert-success  { background: rgba(0,229,160,0.08);  border-color: var(--green); color: var(--green); }

/* ── PROGRESS BAR ── */
.prog-wrap { display: inline-flex; align-items: center; gap: 6px; }
.prog-bar { background: var(--bd); border-radius: 2px; height: 5px; width: 60px; overflow: hidden; }
.prog-fill { height: 100%; border-radius: 2px; }
.prog-val  { font-size: 12px; font-weight: 600; }

/* ── TRANSPARENCY TABLE ── */
.transp-table { width: 100%; border-collapse: collapse; font-size: 12px; }
.transp-table th { background: rgba(26,37,64,0.9); color: var(--blue); font-size: 10px; letter-spacing: 1.5px; text-transform: uppercase; padding: 10px 12px; border-bottom: 1px solid var(--bd); text-align: left; cursor: default; }
.transp-table td { padding: 8px 12px; border-bottom: 1px solid rgba(26,37,64,0.5); }
.transp-table tr:nth-child(odd) td { background: rgba(10,18,32,0.4); }
.transp-note { margin-top: 12px; padding: 12px 16px; border-radius: 4px; font-size: 12px; }
.transp-note.warn { background: rgba(255,215,64,0.08); border-left: 3px solid var(--yel); color: var(--dim); }
.transp-note.ok   { background: rgba(0,229,160,0.08);  border-left: 3px solid var(--green); color: var(--dim); }

/* ── FOOTER ── */
.footer {
  position: fixed;
  bottom: 0; left: 0; right: 0;
  background: var(--bg3);
  border-top: 1px solid var(--bd);
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 24px;
  font-size: 11px;
  z-index: 90;
}
.footer-left  { color: var(--green); font-weight: 700; letter-spacing: 1px; text-shadow: 0 0 8px rgba(0,229,160,0.4); }
.footer-center { color: var(--dim); text-align: center; flex: 1; }
.footer-right { color: var(--dim); }

/* ── APEXCHARTS overrides ── */
.apexcharts-tooltip { font-family: var(--font) !important; font-size: 11px !important; }
.apexcharts-menu { background: #0d1829 !important; border-color: #1a2540 !important; }
.apexcharts-menu-item { color: #c8d3e8 !important; }

/* ── PRINT ── */
@media print {
  @page { margin: 20mm 15mm 25mm 15mm; }
  .nav  { display: none; }
  .footer { position: fixed; bottom: 0; left: 0; right: 0; }
  .section { page-break-inside: avoid; }
  body { background: #080d1a; -webkit-print-color-adjust: exact; print-color-adjust: exact; }
}
</style>
</head>
<body>

<!-- ── FIXED NAV ── -->
<nav class="nav">
  <div class="nav-logo">BVC// ANALYZER</div>
  <div class="nav-tabs">
    <a class="nav-tab" href="#section-synthese">SYNTHÈSE</a>
    <a class="nav-tab" href="#section-smart-money">SMART MONEY</a>
    <a class="nav-tab" href="#section-sentiment">SENTIMENT</a>
    <a class="nav-tab" href="#section-backtest">BACKTEST</a>
    <a class="nav-tab" href="#section-ml">ML</a>
    <a class="nav-tab" href="#section-classement">CLASSEMENT</a>
    <a class="nav-tab" href="#section-network">RÉSEAU</a>
    <a class="nav-tab" href="#section-transparence">TRANSPARENCE</a>
  </div>
  <div class="nav-status">
    <div class="status-dot"></div>
    <span>{{ date }}</span>
  </div>
</nav>

<!-- ── DATA INJECTION ── -->
<script>
const DATA = {{ chart_json | safe }};
</script>

<div class="page">

<!-- ── HEADER ── -->
<div class="report-header">
  <div class="report-header-title">BVC WHATSAPP INTELLIGENCE SYSTEM</div>
  <div class="report-header-sub">
    {{ n_messages | format_number }} messages · {{ n_members }} membres · {{ date_range }}
  </div>
  <div class="report-header-meta">
    Généré le <span>{{ date }}</span> &nbsp;|&nbsp;
    <span>{{ n_tickers }}</span> valeurs analysées &nbsp;|&nbsp;
    Phases 1–14 complètes
  </div>
</div>

<!-- ── KPI STRIP ── -->
<div class="kpi-strip">
  <div class="kpi-card">
    <div class="kpi-label">Messages</div>
    <div class="kpi-value">{{ n_messages | format_number }}</div>
    <div class="kpi-sub">corpus total</div>
  </div>
  <div class="kpi-card">
    <div class="kpi-label">Membres</div>
    <div class="kpi-value">{{ n_members }}</div>
    <div class="kpi-sub">participants actifs</div>
  </div>
  <div class="kpi-card">
    <div class="kpi-label">Smart Money</div>
    <div class="kpi-value">{{ n_smart_money }}</div>
    <div class="kpi-sub">identifiés (score &gt;70)</div>
  </div>
  <div class="kpi-card">
    <div class="kpi-label">Tickers</div>
    <div class="kpi-value">{{ n_tickers }}</div>
    <div class="kpi-sub">valeurs couvertes</div>
  </div>
  <div class="kpi-card">
    <div class="kpi-label">Meilleur Sharpe</div>
    <div class="kpi-value">{{ best_sharpe }}</div>
    <div class="kpi-sub">backtest NLP</div>
  </div>
  <div class="kpi-card">
    <div class="kpi-label">FORT ACHAT</div>
    <div class="kpi-value">{{ n_fort_achat }}</div>
    <div class="kpi-sub">signaux forts</div>
  </div>
</div>

<!-- ── SECTION SYNTHÈSE ── -->
<div class="section" id="section-synthese">
  <div class="section-header">
    <div class="section-tag">01</div>
    <div class="section-title">SYNTHÈSE — TOP 5 PICKS</div>
    <div class="section-dim">Scores composites 0-100</div>
  </div>

  <div class="picks-grid">
    {% for pick in top5 %}
    <div class="pick-card {{ pick.signal }}">
      <div class="pick-ticker">{{ pick.ticker }}</div>
      <div class="pick-name">{{ pick.name[:22] if pick.name else '' }}</div>
      <div class="pick-score">{{ pick.composite_score | round(0) | int }}<span style="font-size:12px;color:var(--dim)">/100</span></div>
      <div style="margin-top:8px;">
        <span class="badge badge-{{ pick.signal }}">{{ pick.signal.replace("_", " ") }}</span>
      </div>
    </div>
    {% else %}
    <div style="color:var(--dim);font-size:12px;grid-column:1/-1;padding:20px 0;">
      Données top 5 non disponibles
    </div>
    {% endfor %}
  </div>

  <div style="margin-top:20px;">
    <div class="chart-title" style="margin-bottom:10px;">DÉCOUVERTES CLÉS</div>
    {% for finding in key_findings %}
    <div class="finding">{{ finding }}</div>
    {% endfor %}
  </div>
</div>

<!-- ── SECTION SMART MONEY ── -->
<div class="section" id="section-smart-money">
  <div class="section-header">
    <div class="section-tag">02</div>
    <div class="section-title">SMART MONEY — SCORES MEMBRES</div>
    <div class="section-dim">Top 20 par score SMS</div>
  </div>

  <div class="chart-wrap" style="margin-bottom:20px;">
    <div class="chart-title">DISTRIBUTION SMART MONEY SCORES</div>
    <div id="chart-smart-money"></div>
  </div>

  {% if smart_money_table %}
  <div class="tbl-wrap">
    <table id="tbl-smart-money">
      <thead>
        <tr>
          <th onclick="sortTable('tbl-smart-money',0)">#</th>
          <th onclick="sortTable('tbl-smart-money',1)">MEMBRE</th>
          <th onclick="sortTable('tbl-smart-money',2)">SCORE SMS</th>
          <th onclick="sortTable('tbl-smart-money',3)">WIN RATE</th>
          <th onclick="sortTable('tbl-smart-money',4)">SIGNAUX</th>
          <th onclick="sortTable('tbl-smart-money',5)">PRÉCISION</th>
        </tr>
      </thead>
      <tbody>
        {% for m in smart_money_table %}
        <tr>
          <td style="color:var(--dim)">{{ m.rank }}</td>
          <td style="color:var(--blue);font-weight:600">{{ m.author }}</td>
          <td style="color:var(--green)">{{ m.sms_score | round(1) }}</td>
          <td>{{ m.win_rate }}%</td>
          <td>{{ m.n_signals }}</td>
          <td>{{ m.accuracy }}%</td>
        </tr>
        {% endfor %}
      </tbody>
    </table>
  </div>
  {% else %}
  <div class="alert alert-info">Données Smart Money non disponibles pour cette session.</div>
  {% endif %}
</div>

<!-- ── SECTION SENTIMENT & FEAR GREED ── -->
<div class="section" id="section-sentiment">
  <div class="section-header">
    <div class="section-tag">03</div>
    <div class="section-title">SENTIMENT &amp; FEAR GREED INDEX</div>
    <div class="section-dim">Évolution hebdomadaire</div>
  </div>

  <div class="grid-2">
    <div class="chart-wrap">
      <div class="chart-title">FEAR &amp; GREED INDEX (HEBDO)</div>
      <div id="chart-fear-greed"></div>
    </div>
    <div class="chart-wrap">
      <div class="chart-title">SENTIMENT MOYEN (HEBDO)</div>
      <div id="chart-sentiment"></div>
    </div>
  </div>

  {% if behavioral_stats %}
  <div style="margin-top:20px;">
    {% for stat in behavioral_stats %}
    <div class="stat-row">
      <span class="stat-label">{{ stat.label }}</span>
      <span class="stat-value">{{ stat.value }}</span>
    </div>
    {% endfor %}
  </div>
  {% endif %}
</div>

<!-- ── SECTION BACKTEST ── -->
<div class="section" id="section-backtest">
  <div class="section-header">
    <div class="section-tag">04</div>
    <div class="section-title">BACKTEST — COURBES D'EQUITY</div>
    <div class="section-dim">Base 100 — frais 0.2% + slippage 0.1%</div>
  </div>

  <div class="chart-wrap" style="margin-bottom:20px;">
    <div class="chart-title">PERFORMANCE DES STRATÉGIES NLP</div>
    <div id="chart-equity"></div>
  </div>

  {% if backtest_table %}
  <div class="tbl-wrap">
    <table id="tbl-backtest">
      <thead>
        <tr>
          <th onclick="sortTable('tbl-backtest',0)">STRATÉGIE</th>
          <th onclick="sortTable('tbl-backtest',1)">CAGR</th>
          <th onclick="sortTable('tbl-backtest',2)">SHARPE</th>
          <th onclick="sortTable('tbl-backtest',3)">SORTINO</th>
          <th onclick="sortTable('tbl-backtest',4)">MAX DD</th>
          <th onclick="sortTable('tbl-backtest',5)">WIN RATE</th>
        </tr>
      </thead>
      <tbody>
        {% for b in backtest_table %}
        <tr>
          <td style="color:var(--blue)">{{ b.strategy }}</td>
          <td style="color:{% if b.cagr_raw > 0 %}var(--green){% else %}var(--red){% endif %}">{{ b.cagr }}</td>
          <td style="color:{% if b.sharpe_raw > 1 %}var(--green){% elif b.sharpe_raw > 0 %}var(--yel){% else %}var(--red){% endif %}">{{ b.sharpe }}</td>
          <td>{{ b.sortino }}</td>
          <td style="color:var(--red)">{{ b.max_dd }}</td>
          <td>{{ b.win_rate }}</td>
        </tr>
        {% endfor %}
      </tbody>
    </table>
  </div>
  {% endif %}

  <div class="alert alert-warning" style="margin-top:14px;">{{ backtest_disclaimer }}</div>
</div>

<!-- ── SECTION MACHINE LEARNING ── -->
<div class="section" id="section-ml">
  <div class="section-header">
    <div class="section-tag">05</div>
    <div class="section-title">MACHINE LEARNING — MODÈLES PRÉDICTIFS</div>
    <div class="section-dim">AUC-ROC · F1 · Précision · Rappel</div>
  </div>

  <div class="chart-wrap" style="margin-bottom:20px;">
    <div class="chart-title">COMPARAISON DES MODÈLES ML</div>
    <div id="chart-ml"></div>
  </div>

  {% if ml_results_table %}
  <div class="tbl-wrap">
    <table>
      <thead>
        <tr>
          <th>MODÈLE</th>
          <th>AUC-ROC</th>
          <th>F1</th>
          <th>PRÉCISION</th>
          <th>RAPPEL</th>
          <th>STATUT</th>
        </tr>
      </thead>
      <tbody>
        {% for m in ml_results_table %}
        <tr>
          <td style="color:{% if m.is_best %}var(--green){% else %}var(--blue){% endif %};font-weight:{% if m.is_best %}700{% else %}400{% endif %}">
            {{ m.model }}{% if m.is_best %} ★{% endif %}
          </td>
          <td style="color:{% if m.auc > 0.6 %}var(--green){% elif m.auc > 0.55 %}var(--yel){% else %}var(--red){% endif %}">
            {{ "%.4f" | format(m.auc) }}
          </td>
          <td>{{ "%.4f" | format(m.f1) }}</td>
          <td>{{ "%.4f" | format(m.precision) }}</td>
          <td>{{ "%.4f" | format(m.recall) }}</td>
          <td>
            {% if m.is_best %}
            <span class="badge badge-FORT_ACHAT">BEST</span>
            {% else %}
            <span class="badge badge-NEUTRE">—</span>
            {% endif %}
          </td>
        </tr>
        {% endfor %}
      </tbody>
    </table>
  </div>
  {% else %}
  <div class="alert alert-info">Résultats ML non disponibles pour cette session.</div>
  {% endif %}

  {% if stats_highlights %}
  <div style="margin-top:16px;">
    {% for s in stats_highlights %}
    <div class="alert alert-{{ s.level }}">{{ s.text }}</div>
    {% endfor %}
  </div>
  {% endif %}
</div>

<!-- ── SECTION CLASSEMENT ── -->
<div class="section" id="section-classement">
  <div class="section-header">
    <div class="section-tag">06</div>
    <div class="section-title">CLASSEMENT VALEURS BVC</div>
    <div class="section-dim">Score composite multi-facteurs</div>
  </div>

  <input
    type="text"
    class="tbl-search"
    placeholder="Filtrer par ticker, signal..."
    oninput="filterTable('tbl-rankings', this.value)"
  />

  {% if rankings_table %}
  <div class="tbl-wrap">
    <table id="tbl-rankings">
      <thead>
        <tr>
          <th onclick="sortTable('tbl-rankings',0)">#</th>
          <th onclick="sortTable('tbl-rankings',1)">TICKER</th>
          <th onclick="sortTable('tbl-rankings',2)">SCORE</th>
          <th onclick="sortTable('tbl-rankings',3)">SIGNAL</th>
          <th onclick="sortTable('tbl-rankings',4)">FOND.</th>
          <th onclick="sortTable('tbl-rankings',5)">TECH.</th>
          <th onclick="sortTable('tbl-rankings',6)">NLP</th>
          <th onclick="sortTable('tbl-rankings',7)">SMART$</th>
          <th onclick="sortTable('tbl-rankings',8)">P(SURPERF 1M)</th>
          <th onclick="sortTable('tbl-rankings',9)">P/E</th>
          <th onclick="sortTable('tbl-rankings',10)">DIV%</th>
        </tr>
      </thead>
      <tbody>
        {% for r in rankings_table %}
        <tr>
          <td style="color:var(--dim)">{{ r.rank }}</td>
          <td style="color:var(--blue);font-weight:700;letter-spacing:1px">{{ r.ticker }}</td>
          <td>
            <div class="prog-wrap">
              <div class="prog-bar">
                <div class="prog-fill" style="width:{{ r.composite_score }}%;background:{% if r.composite_score >= 75 %}var(--green){% elif r.composite_score >= 60 %}#7bc47f{% elif r.composite_score >= 40 %}var(--yel){% else %}var(--red){% endif %}"></div>
              </div>
              <span class="prog-val" style="color:{% if r.composite_score >= 75 %}var(--green){% elif r.composite_score >= 60 %}var(--text){% elif r.composite_score >= 40 %}var(--yel){% else %}var(--red){% endif %}">{{ r.composite_score }}</span>
            </div>
          </td>
          <td><span class="badge badge-{{ r.signal }}">{{ r.signal.replace("_", " ") }}</span></td>
          <td>{{ r.fundamental_score }}</td>
          <td>{{ r.technical_score }}</td>
          <td>{{ r.nlp_score }}</td>
          <td>{{ r.smart_money_score }}</td>
          <td style="color:var(--pur)">{{ "%.1f" | format(r.p1m * 100) }}%</td>
          <td style="color:var(--dim)">{{ r.pe }}</td>
          <td style="color:var(--dim)">{{ r.div }}%</td>
        </tr>
        {% endfor %}
      </tbody>
    </table>
  </div>
  {% else %}
  <div class="alert alert-info">Classement non disponible — données phase 13 absentes.</div>
  {% endif %}
</div>

<!-- ── SECTION RÉSEAU ── -->
<div class="section" id="section-network">
  <div class="section-header">
    <div class="section-tag">07</div>
    <div class="section-title">ANALYSE RÉSEAU</div>
    <div class="section-dim">Graph Theory — Centralité &amp; Communautés</div>
  </div>

  <div class="grid-2">
    <div>
      <div class="chart-title" style="margin-bottom:10px;">STATISTIQUES RÉSEAU</div>
      {% if network_stats %}
        {% for stat in network_stats %}
        <div class="stat-row">
          <span class="stat-label">{{ stat.label }}</span>
          <span class="stat-value">{{ stat.value }}</span>
        </div>
        {% endfor %}
      {% else %}
      <div class="alert alert-info">Métriques réseau non disponibles.</div>
      {% endif %}
    </div>
    <div>
      {% if top_nodes %}
      <div class="chart-title" style="margin-bottom:10px;">TOP 10 NOEUDS PAR CENTRALITÉ</div>
      <div class="tbl-wrap">
        <table>
          <thead>
            <tr>
              <th>MEMBRE</th>
              <th>CENTRALITÉ</th>
              <th>COMMUNAUTÉ</th>
            </tr>
          </thead>
          <tbody>
            {% for node in top_nodes %}
            <tr>
              <td style="color:var(--blue)">{{ node.name }}</td>
              <td style="color:var(--green)">{{ node.centrality }}</td>
              <td style="color:var(--dim)">{{ node.community }}</td>
            </tr>
            {% endfor %}
          </tbody>
        </table>
      </div>
      {% endif %}
    </div>
  </div>
</div>

<!-- ── SECTION TRANSPARENCE ── -->
<div class="section" id="section-transparence">
  <div class="section-header">
    <div class="section-tag">08</div>
    <div class="section-title">TRANSPARENCE DES DONNÉES</div>
    <div class="section-dim">Sources &amp; Couverture Historique</div>
  </div>

  <p style="margin-bottom:14px;color:var(--dim);font-size:12px;">
    Les analyses de prix et de corrélation reposent sur des données historiques réelles
    récupérées via l'API casabourse.ma et BVCscrap. Voici le détail exact de la couverture :
  </p>

  <div class="tbl-wrap">
    <table class="transp-table">
      <thead>
        <tr>
          <th>GROUPE</th>
          <th>PÉRIODE RÉELLE</th>
          <th>OBS.</th>
          <th>TICKERS</th>
        </tr>
      </thead>
      <tbody>
        <tr>
          <td style="font-weight:600;color:var(--blue)">Groupe A — 3 ans</td>
          <td style="color:var(--text)">Juin 2023 → Juin 2026</td>
          <td style="color:var(--green);text-align:center">739</td>
          <td style="color:var(--dim);font-size:11px">IAM, ATW, BCP, BOA, CIH, CDM, HPS, MNG, ATL, ADH, ADI, AFI, AFM, AGM, ARD, BAL, COL, CSR, CTM, DHO, EQD, GAZ, INV, JET, LBV, LES, LHM, M2M, MOX, NEJ</td>
        </tr>
        <tr>
          <td style="font-weight:600;color:var(--blue)">Groupe B — 2 ans</td>
          <td style="color:var(--text)">Mai 2024 → Mai 2026</td>
          <td style="color:var(--green);text-align:center">493</td>
          <td style="color:var(--dim);font-size:11px">CFGB, CMT, MSA, RDS, RIS, SMI, SOT, SRM, TGC</td>
        </tr>
        <tr>
          <td style="font-weight:600;color:var(--blue)">TGCC — 4.5 ans</td>
          <td style="color:var(--text)">Déc 2021 → Juin 2026</td>
          <td style="color:var(--green);text-align:center">1 112</td>
          <td style="color:var(--dim);font-size:11px">TGCC (via BVCscrap)</td>
        </tr>
        <tr>
          <td style="font-weight:600;color:var(--yel)">Extension GBM</td>
          <td style="color:var(--dim)">Sept 2020 → début données réelles</td>
          <td style="color:var(--dim);text-align:center">—</td>
          <td style="color:var(--dim);font-size:11px;font-style:italic">Simulation calibrée sur μ, σ réels — identifiée par _simulated=True dans les données</td>
        </tr>
      </tbody>
    </table>
  </div>

  <div class="transp-note warn" style="margin-top:14px;">
    <strong style="color:var(--yel)">NOTE MÉTHODOLOGIQUE :</strong>
    <span style="color:var(--dim)">
      L'API casabourse est limitée à 739 enregistrements (~3 ans de données journalières).
      Les périodes antérieures sont comblées par simulation GBM (Geometric Brownian Motion)
      calibrée sur les paramètres statistiques réels (μ annuel, σ annuel) de chaque titre.
      Les résultats de corrélation et de backtest sont fiables sur la période réelle.
    </span>
  </div>

  <div class="transp-note ok" style="margin-top:10px;">
    <strong style="color:var(--green)">SOURCES :</strong>
    <span style="color:var(--dim)">
      casabourse.ma (API officielle BVC) · BVCscrap (open-source) ·
      Corpus WhatsApp : {{ n_messages | format_number }} messages · {{ n_members }} participants
    </span>
  </div>
</div>

</div><!-- end .page -->

<!-- ── FOOTER ── -->
<div class="footer">
  <div class="footer-left">Fekak Noureddine</div>
  <div class="footer-center">
    BVC WhatsApp Analysis System v1.0 &nbsp;|&nbsp; {{ date }} &nbsp;|&nbsp; Données: {{ date_range }}
  </div>
  <div class="footer-right">BVC ANALYZER v1.0</div>
</div>

<!-- ── APEXCHARTS INIT ── -->
<script>
(function() {

const APEX_BASE = {
  theme: { mode: "dark" },
  chart: {
    background: "#0d1829",
    foreColor: "#c8d3e8",
    toolbar: { show: true },
    zoom: { enabled: true },
    fontFamily: "'IBM Plex Mono', 'Courier New', monospace",
  },
  grid: { borderColor: "#1a2540" },
  tooltip: { theme: "dark" },
  xaxis: { labels: { style: { colors: "#8892a4", fontFamily: "'IBM Plex Mono', monospace" } } },
  yaxis: { labels: { style: { colors: "#8892a4", fontFamily: "'IBM Plex Mono', monospace" } } },
};

/* ── Smart Money Bar ── */
(function() {
  const el = document.getElementById("chart-smart-money");
  if (!el) return;
  const sm = DATA.smart_money || { categories: [], data: [] };
  if (!sm.categories || sm.categories.length === 0) {
    el.innerHTML = '<div style="color:#8892a4;padding:40px;text-align:center;font-size:12px;">Données Smart Money non disponibles</div>';
    return;
  }
  const opts = Object.assign({}, APEX_BASE, {
    chart: Object.assign({}, APEX_BASE.chart, { type: "bar", height: Math.max(280, sm.categories.length * 22) }),
    plotOptions: { bar: { horizontal: true, borderRadius: 3, barHeight: "60%" } },
    colors: ["#00e5a0"],
    series: [{ name: "Score SMS", data: sm.data }],
    xaxis: Object.assign({}, APEX_BASE.xaxis, { categories: sm.categories }),
    dataLabels: { enabled: true, style: { colors: ["#080d1a"], fontSize: "10px" } },
    fill: { opacity: 0.85 },
  });
  new ApexCharts(el, opts).render();
})();

/* ── Fear & Greed Area ── */
(function() {
  const el = document.getElementById("chart-fear-greed");
  if (!el) return;
  const fg = DATA.fear_greed || [];
  if (fg.length === 0) {
    el.innerHTML = '<div style="color:#8892a4;padding:40px;text-align:center;font-size:12px;">Données Fear &amp; Greed non disponibles</div>';
    return;
  }
  const opts = Object.assign({}, APEX_BASE, {
    chart: Object.assign({}, APEX_BASE.chart, { type: "area", height: 240 }),
    colors: ["#4db8ff"],
    fill: { type: "gradient", gradient: { shadeIntensity: 1, opacityFrom: 0.5, opacityTo: 0.05, stops: [0, 100] } },
    stroke: { curve: "smooth", width: 2 },
    series: [{ name: "Fear & Greed", data: fg }],
    xaxis: Object.assign({}, APEX_BASE.xaxis, {
      type: "datetime",
      labels: { style: { colors: "#8892a4" }, datetimeUTC: false },
    }),
    yaxis: Object.assign({}, APEX_BASE.yaxis, {
      min: 0, max: 100,
      tickAmount: 5,
      labels: Object.assign({}, APEX_BASE.yaxis.labels, {
        formatter: function(v) { return v.toFixed(0); }
      }),
    }),
    annotations: {
      yaxis: [
        { y: 80, y2: 100, fillColor: "rgba(255,79,90,0.08)", label: { text: "Greed Extrême", style: { color: "#ff4f5a", background: "transparent", fontSize: "10px" } } },
        { y: 0,  y2: 20,  fillColor: "rgba(0,229,160,0.08)", label: { text: "Fear Extrême", style: { color: "#00e5a0", background: "transparent", fontSize: "10px" } } },
      ]
    },
    dataLabels: { enabled: false },
  });
  new ApexCharts(el, opts).render();
})();

/* ── Sentiment Bar ── */
(function() {
  const el = document.getElementById("chart-sentiment");
  if (!el) return;
  const sent = DATA.sentiment || [];
  if (sent.length === 0) {
    el.innerHTML = '<div style="color:#8892a4;padding:40px;text-align:center;font-size:12px;">Données sentiment non disponibles</div>';
    return;
  }
  const colors = sent.map(function(d) { return d.y >= 0 ? "#00e5a0" : "#ff4f5a"; });
  const opts = Object.assign({}, APEX_BASE, {
    chart: Object.assign({}, APEX_BASE.chart, { type: "bar", height: 240 }),
    colors: ["#00e5a0"],
    plotOptions: { bar: { borderRadius: 2, colors: { ranges: [{ from: -999, to: 0, color: "#ff4f5a" }, { from: 0, to: 999, color: "#00e5a0" }] } } },
    series: [{ name: "Sentiment", data: sent }],
    xaxis: Object.assign({}, APEX_BASE.xaxis, {
      type: "datetime",
      labels: { style: { colors: "#8892a4" }, datetimeUTC: false },
    }),
    yaxis: Object.assign({}, APEX_BASE.yaxis, {
      labels: Object.assign({}, APEX_BASE.yaxis.labels, {
        formatter: function(v) { return v.toFixed(2); }
      }),
    }),
    dataLabels: { enabled: false },
  });
  new ApexCharts(el, opts).render();
})();

/* ── Equity Curves Line ── */
(function() {
  const el = document.getElementById("chart-equity");
  if (!el) return;
  const ec = DATA.equity_curves || [];
  if (ec.length === 0) {
    el.innerHTML = '<div style="color:#8892a4;padding:40px;text-align:center;font-size:12px;">Données backtest non disponibles</div>';
    return;
  }
  const palette = ["#00e5a0","#4db8ff","#ffd740","#b388ff","#ff8f00","#ff4f5a"];
  const series = ec.map(function(s, i) {
    return { name: s.name, data: s.data };
  });
  const strokeWidths = ec.map(function(s) { return s.bench ? 1.5 : 2; });
  const strokeDashes = ec.map(function(s) { return s.bench ? 5 : 0; });
  const opts = Object.assign({}, APEX_BASE, {
    chart: Object.assign({}, APEX_BASE.chart, { type: "line", height: 320 }),
    colors: ec.map(function(s, i) { return s.bench ? "#8892a4" : palette[i % palette.length]; }),
    stroke: { curve: "smooth", width: strokeWidths, dashArray: strokeDashes },
    series: series,
    xaxis: Object.assign({}, APEX_BASE.xaxis, {
      type: "datetime",
      labels: { style: { colors: "#8892a4" }, datetimeUTC: false },
    }),
    yaxis: Object.assign({}, APEX_BASE.yaxis, {
      labels: Object.assign({}, APEX_BASE.yaxis.labels, {
        formatter: function(v) { return v.toFixed(0); }
      }),
    }),
    legend: { labels: { colors: "#c8d3e8" } },
    dataLabels: { enabled: false },
    markers: { size: 0 },
  });
  new ApexCharts(el, opts).render();
})();

/* ── ML Models Grouped Bar ── */
(function() {
  const el = document.getElementById("chart-ml");
  if (!el) return;
  const ml = DATA.ml_models || [];
  if (ml.length === 0) {
    el.innerHTML = '<div style="color:#8892a4;padding:40px;text-align:center;font-size:12px;">Données ML non disponibles</div>';
    return;
  }
  const cats  = ml.map(function(m) { return m.model; });
  const auc   = ml.map(function(m) { return m.auc; });
  const f1    = ml.map(function(m) { return m.f1; });
  const prec  = ml.map(function(m) { return m.precision; });
  const rec   = ml.map(function(m) { return m.recall; });
  const opts = Object.assign({}, APEX_BASE, {
    chart: Object.assign({}, APEX_BASE.chart, { type: "bar", height: 280 }),
    colors: ["#00e5a0","#4db8ff","#ffd740","#b388ff"],
    plotOptions: { bar: { horizontal: false, columnWidth: "65%", borderRadius: 2 } },
    series: [
      { name: "AUC-ROC",   data: auc },
      { name: "F1",        data: f1 },
      { name: "Précision", data: prec },
      { name: "Rappel",    data: rec },
    ],
    xaxis: Object.assign({}, APEX_BASE.xaxis, {
      categories: cats,
      labels: { style: { colors: "#8892a4" }, rotate: -20 },
    }),
    yaxis: Object.assign({}, APEX_BASE.yaxis, {
      min: 0, max: 1,
      labels: Object.assign({}, APEX_BASE.yaxis.labels, {
        formatter: function(v) { return v.toFixed(2); }
      }),
    }),
    legend: { labels: { colors: "#c8d3e8" } },
    dataLabels: { enabled: false },
  });
  new ApexCharts(el, opts).render();
})();

})(); // end IIFE


/* ── TABLE SORT ── */
const sortState = {};
function sortTable(id, colIdx) {
  const table = document.getElementById(id);
  if (!table) return;
  const key = id + "_" + colIdx;
  const asc = !sortState[key];
  sortState[key] = asc;
  // Reset all headers
  Array.from(table.querySelectorAll("th")).forEach(function(th) {
    th.classList.remove("sort-asc", "sort-desc");
  });
  const th = table.querySelectorAll("th")[colIdx];
  if (th) th.classList.add(asc ? "sort-asc" : "sort-desc");

  const tbody = table.querySelector("tbody");
  const rows = Array.from(tbody.querySelectorAll("tr"));
  rows.sort(function(a, b) {
    const aText = (a.querySelectorAll("td")[colIdx] || {}).textContent || "";
    const bText = (b.querySelectorAll("td")[colIdx] || {}).textContent || "";
    const aNum = parseFloat(aText.replace(/[^0-9.\-]/g, ""));
    const bNum = parseFloat(bText.replace(/[^0-9.\-]/g, ""));
    if (!isNaN(aNum) && !isNaN(bNum)) {
      return asc ? aNum - bNum : bNum - aNum;
    }
    return asc ? aText.localeCompare(bText) : bText.localeCompare(aText);
  });
  rows.forEach(function(r) { tbody.appendChild(r); });
}

/* ── TABLE FILTER ── */
function filterTable(id, query) {
  const table = document.getElementById(id);
  if (!table) return;
  const q = query.toLowerCase();
  Array.from(table.querySelectorAll("tbody tr")).forEach(function(row) {
    row.style.display = row.textContent.toLowerCase().includes(q) ? "" : "none";
  });
}
</script>

</body>
</html>"""


# ─────────────────────────────────────────────────────────────
# HELPERS DE DONNÉES
# ─────────────────────────────────────────────────────────────

def format_number(n: Any) -> str:
    """Formate un nombre avec séparateurs de milliers."""
    try:
        return f"{int(n):,}".replace(",", " ")
    except Exception:
        return str(n)


def extract_group_stats(df: pd.DataFrame) -> List[Dict[str, str]]:
    """Extrait les statistiques globales du groupe."""
    stats = []
    if df.empty:
        return stats

    if "timestamp" in df.columns:
        ts = pd.to_datetime(df["timestamp"])
        stats.append({"label": "Première activité", "value": str(ts.min().date())})
        stats.append({"label": "Dernière activité", "value": str(ts.max().date())})
        days = (ts.max() - ts.min()).days
        stats.append({"label": "Durée couverte", "value": f"{days} jours"})

    if "author" in df.columns:
        stats.append({"label": "Membres uniques", "value": str(df["author"].nunique())})
        daily = df.groupby(pd.to_datetime(df["timestamp"]).dt.date).size()
        stats.append({"label": "Moy. messages/jour", "value": f"{daily.mean():.0f}"})

    if "language" in df.columns:
        top_lang = df["language"].value_counts().index[0] if not df["language"].isna().all() else "N/A"
        stats.append({"label": "Langue dominante", "value": str(top_lang)})

    return stats


def extract_top_contributors(df: pd.DataFrame, n: int = 10) -> List[Dict]:
    """Extrait les top N contributeurs."""
    if df.empty or "author" not in df.columns:
        return []

    msg_counts = df.groupby("author").size()
    top_authors = msg_counts.nlargest(n)

    result = []
    for author, count in top_authors.items():
        signals_count = 0
        if "signal" in df.columns:
            signals_count = int(df[df["author"] == author]["signal"].notna().sum())
        result.append({
            "author": str(author)[:15],
            "messages": int(count),
            "signals": signals_count,
        })
    return result


def extract_smart_money_table(
    member_scores: Optional[pd.DataFrame],
    df: Optional[pd.DataFrame],
    n: int = 20,
) -> List[Dict]:
    """Extrait les données Smart Money pour le tableau."""
    if member_scores is None or member_scores.empty:
        return []

    ms = member_scores.copy()
    ms["_score"] = _compute_sms_score(ms)
    top_members = ms.nlargest(n, "_score")
    result = []

    for rank, (idx, row) in enumerate(top_members.iterrows(), 1):
        author_name = str(row.get("author", idx))[:18]

        # win_rate peut être 0.021 (fraction) ou 21.0 (pourcentage)
        wr_raw = row.get("win_rate", row.get("sms_win_rate", 0))
        if pd.isna(wr_raw):
            wr_raw = 0.0
        wr_float = float(wr_raw)
        wr_pct = wr_float * 100 if wr_float <= 1.0 else wr_float

        n_signals = row.get("n_calls", row.get("n_signals", row.get("total_signals", 0)))
        precision = row.get("precision", row.get("accuracy", 0))
        if pd.isna(precision):
            precision = 0.0
        prec_float = float(precision)
        prec_pct = prec_float * 100 if prec_float <= 1.0 else prec_float

        result.append({
            "rank": rank,
            "author": author_name,
            "sms_score": round(float(row["_score"]), 1),
            "win_rate": f"{wr_pct:.1f}",
            "n_signals": int(n_signals) if pd.notna(n_signals) else 0,
            "accuracy": f"{prec_pct:.1f}",
        })

    return result


def extract_rankings_table(predictions: Optional[pd.DataFrame]) -> List[Dict]:
    """Prépare les données pour le tableau de classement."""
    if predictions is None or predictions.empty:
        return []

    result = []
    for _, row in predictions.iterrows():
        result.append({
            "rank": int(row.get("rank", 0)),
            "ticker": str(row.get("ticker", "")),
            "composite_score": round(float(row.get("composite_score", 0)), 1),
            "signal": str(row.get("signal", "NEUTRE")),
            "fundamental_score": round(float(row.get("fundamental_score", 0)), 1),
            "technical_score": round(float(row.get("technical_score", 0)), 1),
            "nlp_score": round(float(row.get("nlp_sentiment_score", 0)), 1),
            "smart_money_score": round(float(row.get("smart_money_score", 0)), 1),
            "p1m": float(row.get("p_outperform_1m", 0)),
            "pe": f"{float(row.get('pe_ratio', 0)):.1f}" if row.get("pe_ratio") else "N/A",
            "div": f"{float(row.get('div_yield', 0)):.1f}" if row.get("div_yield") else "0.0",
        })
    return result


def build_key_findings(
    summary_data: Dict[str, Any],
    phase8_summary: Optional[Dict] = None,
    phase9_results: Optional[Dict] = None,
    phase11_summary: Optional[Dict] = None,
    phase12_stats: Optional[Dict] = None,
) -> List[str]:
    """Génère les découvertes clés pour le résumé exécutif."""
    findings = []

    n_messages = summary_data.get("n_messages", 0)
    n_members = summary_data.get("n_members", 0)

    findings.append(
        f"Le groupe compte {n_members} membres actifs avec {format_number(n_messages)} messages analysés"
    )

    if phase8_summary:
        lag = phase8_summary.get("global_optimal_lag_days", 0)
        corr = phase8_summary.get("global_max_correlation", 0)
        if lag and abs(corr) > 0.1:
            findings.append(
                f"Le sentiment NLP précède les mouvements de prix de {lag} jours "
                f"(corrélation={corr:.3f})"
            )
        sm_lead = phase8_summary.get("smart_money_lead_days", 0)
        if sm_lead:
            findings.append(
                f"Le sentiment Smart Money anticipe le MASI de {sm_lead} jours en moyenne"
            )

    if phase9_results and "model_results" in phase9_results:
        best = phase9_results["model_results"].get("_best_model_name", "")
        if best:
            auc = phase9_results["model_results"].get(best, {}).get("auc_roc", 0.5)
            findings.append(
                f"Meilleur modèle ML: {best} (AUC={auc:.3f}) — "
                f"{'significativement supérieur au hasard' if auc > 0.55 else 'performance proche du hasard'}"
            )

    if phase11_summary:
        best_strat = phase11_summary.get("best_strategy_sharpe", "N/A")
        best_sharpe = phase11_summary.get("best_sharpe", 0)
        bench_cagr = phase11_summary.get("benchmark_cagr", 0)
        findings.append(
            f"Stratégie NLP la plus performante: {best_strat} (Sharpe={best_sharpe:.2f}) "
            f"vs Buy&Hold MASI ({bench_cagr:.1%} CAGR)"
        )

    if phase12_stats:
        sr = phase12_stats.get("stats_report", {})
        n_sig = sr.get("summary", {}).get("n_significant_after_correction", 0)
        n_total = sr.get("summary", {}).get("n_tests_total", 0)
        if n_total > 0:
            findings.append(
                f"Tests statistiques: {n_sig}/{n_total} résultats significatifs après correction FDR"
            )
        ov_risk = sr.get("summary", {}).get("overfitting_risk", "INCONNU")
        findings.append(f"Risque de sur-apprentissage évalué: {ov_risk}")

    return findings


# ─────────────────────────────────────────────────────────────
# POINT D'ENTRÉE PRINCIPAL
# ─────────────────────────────────────────────────────────────

def run_phase14(
    df: pd.DataFrame,
    stock_scores: Optional[pd.DataFrame] = None,
    member_scores: Optional[pd.DataFrame] = None,
    fear_greed_series: Optional[pd.Series] = None,
    graph_metrics: Optional[pd.DataFrame] = None,
    phase8_results: Optional[Dict[str, Any]] = None,
    phase9_results: Optional[Dict[str, Any]] = None,
    phase10_results: Optional[Dict[str, Any]] = None,
    phase11_results: Optional[Dict[str, Any]] = None,
    phase12_results: Optional[Dict[str, Any]] = None,
    phase13_results: Optional[Dict[str, Any]] = None,
    output_dir: str = "output",
) -> Dict[str, Any]:
    """
    Génère le rapport HTML institutionnel complet.
    Retourne: {'report_path': str, 'summary': dict}
    """
    logger.info("=== Phase 14: Génération du Rapport HTML (Dark Terminal Theme) ===")

    os.makedirs(output_dir, exist_ok=True)
    report_path = os.path.join(output_dir, "report.html")

    # ── Collecte des méta-données ──────────────────────────
    n_messages = len(df) if not df.empty else 0
    n_members = df["author"].nunique() if "author" in df.columns else 0
    n_tickers = len(phase13_results.get("predictions", pd.DataFrame())) if phase13_results else 0

    # Date range
    if "timestamp" in df.columns and not df.empty:
        ts = pd.to_datetime(df["timestamp"])
        date_range = f"{ts.min().strftime('%d/%m/%Y')} — {ts.max().strftime('%d/%m/%Y')}"
    else:
        date_range = "N/A"

    # Langues
    languages = []
    if "language" in df.columns:
        lang_labels = {"fr": "Français", "ar": "Arabe", "darija": "Darija",
                       "arabizi": "Arabizi", "en": "Anglais"}
        top_langs = df["language"].value_counts().head(4).index.tolist()
        languages = [lang_labels.get(l, l) for l in top_langs]

    # Smart Money count
    n_smart_money = 0
    if member_scores is not None and not member_scores.empty:
        sms_col = next(
            (c for c in ["sms_score", "smart_money_score", "score"] if c in member_scores.columns),
            None,
        )
        if sms_col:
            n_smart_money = int((member_scores[sms_col] > 70).sum())

    # KPI backtest
    best_sharpe_str = "N/A"
    if phase11_results:
        best_s = phase11_results.get("summary", {}).get("best_sharpe", 0)
        best_sharpe_str = f"{best_s:.2f}"

    # Signaux FORT_ACHAT
    n_fort_achat = 0
    if phase13_results:
        n_fort_achat = phase13_results.get("summary", {}).get("n_fort_achat", 0)

    # ── Données sentiment quotidien ────────────────────────
    daily_sentiment = (
        phase8_results.get("daily_sentiment", pd.DataFrame())
        if phase8_results else pd.DataFrame()
    )

    # ── Sérialisation des données pour ApexCharts ──────────
    logger.info("Sérialisation des données pour ApexCharts...")

    equity_curves = phase11_results.get("equity_curves") if phase11_results else {}

    chart_data = {
        "fear_greed": serialize_fear_greed(fear_greed_series),
        "sentiment": serialize_sentiment(daily_sentiment),
        "equity_curves": serialize_equity_curves(equity_curves if equity_curves else {}),
        "smart_money": serialize_smart_money(member_scores),
        "ml_models": serialize_ml_models(phase9_results),
    }
    chart_json = json.dumps(chart_data, default=str)

    # ── Préparation des données template ──────────────────
    summary_data = {
        "n_messages": n_messages,
        "n_members": n_members,
    }

    # Key findings
    key_findings = build_key_findings(
        summary_data=summary_data,
        phase8_summary=phase8_results.get("summary") if phase8_results else None,
        phase9_results=phase9_results,
        phase11_summary=phase11_results.get("summary") if phase11_results else None,
        phase12_stats=phase12_results,
    )

    # Group stats
    group_stats = extract_group_stats(df)

    # Top contributors
    top_contributors = extract_top_contributors(df, n=10)

    # Smart Money table
    smart_money_table = extract_smart_money_table(member_scores, df, n=20)

    # ML results table
    ml_results_table = []
    if phase9_results and "model_results" in phase9_results:
        best_name = phase9_results["model_results"].get("_best_model_name", "")
        for model_name, metrics in phase9_results["model_results"].items():
            if model_name.startswith("_") or not isinstance(metrics, dict):
                continue
            ml_results_table.append({
                "model": model_name,
                "auc": float(metrics.get("auc_roc", 0.5)),
                "f1": float(metrics.get("f1", 0)),
                "precision": float(metrics.get("precision", 0)),
                "recall": float(metrics.get("recall", 0)),
                "accuracy": float(metrics.get("accuracy", 0.5)),
                "is_best": model_name == best_name,
            })

    # Stats highlights
    stats_highlights = []
    if phase12_results:
        sr = phase12_results.get("stats_report", {})
        ov = sr.get("overfitting", {})
        risk = ov.get("risk_level", "INCONNU")
        ov_level_map = {"FAIBLE": "success", "MODÉRÉ": "warning", "ÉLEVÉ": "danger", "CRITIQUE": "danger"}
        stats_highlights.append({
            "level": ov_level_map.get(risk, "info"),
            "text": f"Risque de sur-apprentissage: {risk} | IS AUC={ov.get('is_auc', 0):.3f} → OOS AUC={ov.get('oos_auc', 0):.3f}",
        })
        mc_auc = sr.get("monte_carlo_auc", {}).get("best_model", {})
        if mc_auc:
            sig = mc_auc.get("significant", False)
            p_val = mc_auc.get("p_value", 1.0)
            stats_highlights.append({
                "level": "success" if sig else "warning",
                "text": f"Monte Carlo AUC: p-value={p_val:.4f} — {'Significatif' if sig else 'Non significatif'} (α=0.05)",
            })

    # Rankings table
    rankings_table = extract_rankings_table(
        phase13_results.get("predictions") if phase13_results else None
    )

    # Top 5 picks
    top5 = phase13_results.get("top5", []) if phase13_results else []

    # Network stats
    network_stats = []
    top_nodes = []
    if graph_metrics is not None and not graph_metrics.empty:
        network_stats.append({"label": "Nœuds dans le réseau", "value": str(len(graph_metrics))})
        centrality_col = next(
            (c for c in ["degree_centrality", "betweenness_centrality", "pagerank"]
             if c in graph_metrics.columns), None
        )
        if centrality_col:
            top_gm = graph_metrics.nlargest(10, centrality_col)
            for idx_val, row in top_gm.iterrows():
                comm = row.get("community", row.get("cluster", "N/A"))
                top_nodes.append({
                    "name": str(idx_val)[:15],
                    "centrality": f"{float(row[centrality_col]):.4f}",
                    "community": str(comm),
                })

    # Behavioral stats
    behavioral_stats = []
    if daily_sentiment is not None and not daily_sentiment.empty:
        avg_sent = daily_sentiment["sentiment_mean"].mean() if "sentiment_mean" in daily_sentiment.columns else 0
        sent_trend = "Haussier" if avg_sent > 0.1 else "Baissier" if avg_sent < -0.1 else "Neutre"
        behavioral_stats.append({"label": "Sentiment moyen global", "value": f"{avg_sent:.3f} ({sent_trend})"})

    if fear_greed_series is not None and not fear_greed_series.empty:
        fg_last = float(fear_greed_series.dropna().iloc[-1])
        fg_regime = ("Greed Extrême" if fg_last > 80 else "Greed" if fg_last > 60 else
                     "Neutre" if fg_last > 40 else "Fear" if fg_last > 20 else "Fear Extrême")
        behavioral_stats.append({"label": "Fear & Greed actuel", "value": f"{fg_last:.0f} ({fg_regime})"})

    # NLP stats
    nlp_stats = []
    if not df.empty:
        if "signal" in df.columns:
            buy_count = (df["signal"].isin(["ACHAT_FORT", "ACHETER", "RENFORCEMENT"])).sum()
            sell_count = (df["signal"].isin(["VENTE", "PANIQUE"])).sum()
            nlp_stats.append({"label": "Signaux d'achat total", "value": format_number(buy_count)})
            nlp_stats.append({"label": "Signaux de vente total", "value": format_number(sell_count)})
            nlp_stats.append({"label": "Ratio achat/vente", "value": f"{buy_count / max(sell_count, 1):.2f}"})

    # Overfitting for disclaimer
    overfitting_warning = ""
    overfitting_level = "INCONNU"
    if phase12_results:
        sr = phase12_results.get("stats_report", {})
        ov = sr.get("overfitting", {})
        overfitting_level = ov.get("risk_level", "INCONNU")
        if ov.get("warnings"):
            overfitting_warning = " | ".join(ov["warnings"][:2])

    # Backtest disclaimer
    backtest_disclaimer = (
        "Note: Les courbes d'equity sont basées sur des données partiellement synthétiques. "
        "Les frais de transaction (0.2%) et le slippage (0.1%) sont inclus. "
        "Ces résultats ne constituent pas une garantie de performance future."
    )

    # Backtest table from strategy_metrics
    backtest_table = []
    if phase11_results:
        strategy_metrics = phase11_results.get("strategy_metrics", {})
        for strat, metrics in strategy_metrics.items():
            if not isinstance(metrics, dict):
                continue
            cagr_v = float(metrics.get("cagr", 0))
            sharpe_v = float(metrics.get("sharpe", 0))
            backtest_table.append({
                "strategy": strat.replace("_", " ")[:28],
                "cagr": f"{cagr_v:.1%}",
                "cagr_raw": cagr_v,
                "sharpe": f"{sharpe_v:.2f}",
                "sharpe_raw": sharpe_v,
                "sortino": f"{float(metrics.get('sortino', 0)):.2f}",
                "max_dd": f"{float(metrics.get('max_drawdown', 0)):.1%}",
                "win_rate": f"{float(metrics.get('win_rate', 0)):.1%}",
            })

    # ── Rendu du template ──────────────────────────────────
    logger.info("Rendu du template HTML (dark terminal theme)...")

    template_vars = {
        "date": REPORT_DATE,
        "date_range": date_range,
        "n_messages": n_messages,
        "n_authors": n_members,
        "n_members": n_members,
        "n_tickers": n_tickers,
        "n_smart_money": n_smart_money,
        "n_fort_achat": n_fort_achat,
        "best_sharpe": best_sharpe_str,
        "languages": languages,
        "key_findings": key_findings,
        "top5": top5,
        "group_stats": group_stats,
        "top_contributors": top_contributors,
        "smart_money_table": smart_money_table,
        "ml_results_table": ml_results_table,
        "stats_highlights": stats_highlights,
        "rankings_table": rankings_table,
        "network_stats": network_stats,
        "top_nodes": top_nodes,
        "behavioral_stats": behavioral_stats,
        "nlp_stats": nlp_stats,
        "overfitting_warning": overfitting_warning,
        "overfitting_level": overfitting_level,
        "backtest_disclaimer": backtest_disclaimer,
        "backtest_table": backtest_table,
        # ApexCharts JSON data
        "chart_json": chart_json,
    }

    if JINJA2_AVAILABLE:
        env = Environment(loader=BaseLoader())
        env.filters["format_number"] = format_number
        template = env.from_string(HTML_TEMPLATE)
        html_content = template.render(**template_vars)
    else:
        # Fallback: simple string replacement
        html_content = HTML_TEMPLATE
        for key, value in template_vars.items():
            placeholder = "{{ " + key + " }}"
            html_content = html_content.replace(placeholder, str(value))

    with open(report_path, "w", encoding="utf-8") as f:
        f.write(html_content)

    report_size_kb = os.path.getsize(report_path) / 1024
    logger.info(f"Rapport généré: {report_path} ({report_size_kb:.0f} KB)")

    summary = {
        "report_path": report_path,
        "report_size_kb": report_size_kb,
        "n_messages": n_messages,
        "n_members": n_members,
        "n_tickers_analyzed": n_tickers,
        "n_smart_money": n_smart_money,
        "n_fort_achat": n_fort_achat,
        "date_range": date_range,
        "top5": top5,
        "key_findings": key_findings,
    }

    return {"report_path": report_path, "summary": summary}


# ─────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    print("Test Phase 14: génération du rapport HTML (dark terminal theme)...")

    rng = np.random.RandomState(42)
    dates = pd.date_range("2022-01-01", "2024-12-31", freq="h")[:3000]

    test_df = pd.DataFrame({
        "timestamp": dates,
        "author": [f"user_{i % 50}" for i in range(3000)],
        "message_text": ["test message"] * 3000,
        "sentiment": rng.choice(["positif", "negatif", "neutre"], 3000),
        "signal": rng.choice(["ACHAT_FORT", "ACHETER", "VENTE", "DOUTE", None], 3000),
        "language": rng.choice(["fr", "darija", "arabizi", "ar"], 3000),
        "tickers_mentioned": [[] for _ in range(3000)],
    })

    results = run_phase14(test_df, output_dir="/tmp/bvc_test_report")

    print(f"\nRapport généré: {results['report_path']}")
    print(f"Taille: {results['summary']['report_size_kb']:.0f} KB")
    print(f"Messages analysés: {results['summary']['n_messages']}")
    print(f"Membres: {results['summary']['n_members']}")
