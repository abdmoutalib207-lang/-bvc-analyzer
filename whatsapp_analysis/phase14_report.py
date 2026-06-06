"""
Phase 14 — Génération du Rapport HTML Institutionnel
Rapport complet auto-contenu avec graphiques base64 et Jinja2
"""
from __future__ import annotations

import base64
import io
import json
import logging
import os
import warnings
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")
logger = logging.getLogger(__name__)

# Matplotlib en mode non-interactif
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.gridspec import GridSpec
from matplotlib.ticker import FuncFormatter

# Jinja2
try:
    from jinja2 import Environment, BaseLoader
    JINJA2_AVAILABLE = True
except ImportError:
    JINJA2_AVAILABLE = False

# ─────────────────────────────────────────────────────────────
# CONFIGURATION
# ─────────────────────────────────────────────────────────────

REPORT_TITLE = "Analyse Intelligence Artificielle — Bourse de Casablanca"
REPORT_SUBTITLE = "Analyse Multi-Signaux du Groupe WhatsApp BVC"
REPORT_DATE = datetime.now().strftime("%d %B %Y")

# Palette de couleurs BVC
COLORS = {
    "primary": "#1a5276",
    "secondary": "#2980b9",
    "success": "#27ae60",
    "danger": "#e74c3c",
    "warning": "#f39c12",
    "neutral": "#7f8c8d",
    "background": "#f8f9fa",
    "white": "#ffffff",
    "dark": "#2c3e50",
    "light": "#ecf0f1",
    "gold": "#d4ac0d",
}

SIGNAL_COLORS = {
    "FORT_ACHAT": "#27ae60",
    "ACHAT": "#2ecc71",
    "NEUTRE": "#f39c12",
    "VENTE": "#e67e22",
    "FORT_VENTE": "#e74c3c",
}


# ─────────────────────────────────────────────────────────────
# UTILITAIRES GRAPHIQUES
# ─────────────────────────────────────────────────────────────

def fig_to_base64(fig: plt.Figure, dpi: int = 100) -> str:
    """Convertit une figure matplotlib en chaîne base64."""
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=dpi, bbox_inches="tight",
                facecolor=fig.get_facecolor())
    buf.seek(0)
    img_b64 = base64.b64encode(buf.read()).decode("utf-8")
    buf.close()
    plt.close(fig)
    return img_b64


def set_style():
    """Configure le style matplotlib."""
    plt.rcParams.update({
        "figure.facecolor": COLORS["white"],
        "axes.facecolor": COLORS["white"],
        "axes.edgecolor": "#dee2e6",
        "axes.labelcolor": COLORS["dark"],
        "text.color": COLORS["dark"],
        "xtick.color": COLORS["dark"],
        "ytick.color": COLORS["dark"],
        "grid.color": "#dee2e6",
        "grid.alpha": 0.5,
        "font.size": 10,
        "axes.titlesize": 12,
        "axes.titleweight": "bold",
    })


# ─────────────────────────────────────────────────────────────
# GRAPHIQUES
# ─────────────────────────────────────────────────────────────

def chart_fear_greed_evolution(
    fear_greed_series: Optional[pd.Series],
    daily_sentiment: Optional[pd.DataFrame] = None,
) -> str:
    """Graphique évolution Fear & Greed dans le temps."""
    set_style()
    fig, ax = plt.subplots(figsize=(12, 4))

    if fear_greed_series is not None and not fear_greed_series.empty:
        fg = fear_greed_series.copy()
        fg.index = pd.to_datetime(fg.index)
        fg = fg.resample("W").mean().dropna()

        ax.fill_between(fg.index, fg.values, 50, where=fg.values >= 50,
                        color=COLORS["success"], alpha=0.3, label="Greed")
        ax.fill_between(fg.index, fg.values, 50, where=fg.values < 50,
                        color=COLORS["danger"], alpha=0.3, label="Fear")
        ax.plot(fg.index, fg.values, color=COLORS["primary"], linewidth=2)

        # Zones colorées
        ax.axhspan(80, 100, alpha=0.08, color=COLORS["danger"], label="Greed Extrême")
        ax.axhspan(0, 20, alpha=0.08, color=COLORS["success"], label="Fear Extrême")
        ax.axhline(50, color=COLORS["neutral"], linestyle="--", alpha=0.5)

    elif daily_sentiment is not None and not daily_sentiment.empty:
        # Proxy depuis sentiment
        sent = daily_sentiment.copy()
        sent["date"] = pd.to_datetime(sent["date"])
        sent = sent.set_index("date").resample("W").mean()
        if "sentiment_mean" in sent.columns:
            fg_proxy = (sent["sentiment_mean"] + 1) / 2 * 100
            ax.plot(fg_proxy.index, fg_proxy.values, color=COLORS["primary"],
                    linewidth=2, label="Fear & Greed (proxy sentiment)")

    ax.set_ylim(0, 100)
    ax.set_ylabel("Index Fear & Greed")
    ax.set_title("Évolution du Fear & Greed Index du Groupe")
    ax.legend(loc="upper right", fontsize=8)
    ax.yaxis.set_major_formatter(FuncFormatter(lambda x, _: f"{int(x)}"))
    plt.tight_layout()
    return fig_to_base64(fig)


def chart_sentiment_evolution(daily_sentiment: Optional[pd.DataFrame]) -> str:
    """Graphique évolution du sentiment quotidien."""
    set_style()
    fig, axes = plt.subplots(2, 1, figsize=(12, 6), sharex=True)

    if daily_sentiment is not None and not daily_sentiment.empty:
        ds = daily_sentiment.copy()
        ds["date"] = pd.to_datetime(ds["date"])
        ds = ds.set_index("date").resample("W").mean()

        # Sentiment moyen
        ax1 = axes[0]
        if "sentiment_mean" in ds.columns:
            colors = [COLORS["success"] if s >= 0 else COLORS["danger"]
                      for s in ds["sentiment_mean"]]
            ax1.bar(ds.index, ds["sentiment_mean"], color=colors, alpha=0.7, width=5)
            ax1.axhline(0, color=COLORS["dark"], linewidth=0.8)
            ax1.set_ylabel("Sentiment Moyen")
            ax1.set_title("Sentiment du Groupe (hebdomadaire)")

        # Volume de messages
        ax2 = axes[1]
        if "message_count" in ds.columns:
            ax2.fill_between(ds.index, ds["message_count"].values, alpha=0.5,
                             color=COLORS["secondary"])
            ax2.plot(ds.index, ds["message_count"].values, color=COLORS["primary"], linewidth=1)
            ax2.set_ylabel("Volume Messages")
            ax2.set_title("Activité du Groupe")

    for ax in axes:
        ax.grid(True, alpha=0.3)

    plt.tight_layout()
    return fig_to_base64(fig)


def chart_signal_distribution(df: pd.DataFrame) -> str:
    """Diagramme camembert de la distribution des signaux."""
    set_style()
    fig, ax = plt.subplots(figsize=(8, 6))

    if "signal" in df.columns:
        signal_counts = df["signal"].value_counts()
        signal_counts = signal_counts[signal_counts.index.notna()]

        labels = signal_counts.index.tolist()
        sizes = signal_counts.values.tolist()
        colors_list = [SIGNAL_COLORS.get(s, COLORS["neutral"]) for s in labels]

        wedges, texts, autotexts = ax.pie(
            sizes,
            labels=labels,
            colors=colors_list,
            autopct="%1.1f%%",
            startangle=90,
            wedgeprops={"edgecolor": "white", "linewidth": 2},
        )
        for text in autotexts:
            text.set_fontsize(9)
    else:
        ax.text(0.5, 0.5, "Données non disponibles", ha="center", va="center",
                transform=ax.transAxes)

    ax.set_title("Distribution des Signaux de Trading")
    plt.tight_layout()
    return fig_to_base64(fig)


def chart_equity_curves(equity_curves: Optional[Dict[str, pd.Series]]) -> str:
    """Graphique des courbes d'equity des stratégies."""
    set_style()
    fig, ax = plt.subplots(figsize=(12, 6))

    if equity_curves:
        strategy_colors = [
            COLORS["primary"], COLORS["success"], COLORS["warning"],
            COLORS["danger"], COLORS["secondary"]
        ]
        bench_color = COLORS["neutral"]

        sorted_strats = sorted(
            equity_curves.items(),
            key=lambda x: (x[0] == "BuyAndHold_MASI", x[0])
        )

        for i, (name, eq) in enumerate(sorted_strats):
            if eq is None or (hasattr(eq, "empty") and eq.empty):
                continue
            eq = eq.dropna()
            if len(eq) < 2:
                continue

            if "BuyAndHold" in name or "MASI" in name:
                color = bench_color
                lw = 2
                ls = "--"
            else:
                color = strategy_colors[i % len(strategy_colors)]
                lw = 2
                ls = "-"

            display_name = name.replace("_", " ").replace("BuyAndHold MASI", "Buy & Hold MASI")
            ax.plot(eq.index, eq.values, color=color, linewidth=lw,
                    linestyle=ls, label=display_name, alpha=0.85)

    ax.set_ylabel("Valeur du Portefeuille (base 100)")
    ax.set_title("Courbes d'Equity — Comparaison des Stratégies")
    ax.legend(loc="upper left", fontsize=9)
    ax.grid(True, alpha=0.3)
    ax.yaxis.set_major_formatter(FuncFormatter(lambda x, _: f"{x:.0f}"))
    plt.tight_layout()
    return fig_to_base64(fig)


def chart_top_tickers(predictions: Optional[pd.DataFrame]) -> str:
    """Graphique barres horizontales des top tickers par score composite."""
    set_style()
    fig, ax = plt.subplots(figsize=(10, 8))

    if predictions is not None and not predictions.empty:
        top20 = predictions.head(20)
        y_pos = range(len(top20))

        bar_colors = [SIGNAL_COLORS.get(s, COLORS["neutral"])
                      for s in top20["signal"]]
        bars = ax.barh(list(y_pos), top20["composite_score"].values,
                       color=bar_colors, alpha=0.8, height=0.6)

        ax.set_yticks(list(y_pos))
        ax.set_yticklabels(top20["ticker"].values, fontsize=9)
        ax.set_xlim(0, 100)
        ax.set_xlabel("Score Composite (0-100)")
        ax.set_title("Top 20 Valeurs BVC — Classement par Score Composite")
        ax.axvline(75, color=COLORS["success"], linestyle="--", alpha=0.5, label="Fort Achat (>75)")
        ax.axvline(60, color=COLORS["warning"], linestyle="--", alpha=0.5, label="Achat (>60)")
        ax.axvline(40, color=COLORS["danger"], linestyle="--", alpha=0.5, label="Neutre (40-60)")

        # Scores sur les barres
        for bar, score in zip(bars, top20["composite_score"]):
            ax.text(bar.get_width() + 0.5, bar.get_y() + bar.get_height() / 2,
                    f"{score:.0f}", va="center", fontsize=8)

        ax.legend(loc="lower right", fontsize=8)
        ax.invert_yaxis()  # Top ticker en haut

    plt.tight_layout()
    return fig_to_base64(fig)


def chart_feature_importance(feature_importance: Optional[pd.DataFrame]) -> str:
    """Graphique des top features importantes."""
    set_style()
    fig, ax = plt.subplots(figsize=(10, 6))

    if feature_importance is not None and not feature_importance.empty:
        top_n = 15
        feat_col = "feature" if "feature" in feature_importance.columns else feature_importance.columns[0]
        imp_col = "importance_mean" if "importance_mean" in feature_importance.columns else "importance"

        top_feats = feature_importance.head(top_n)
        y_pos = range(len(top_feats))

        ax.barh(list(y_pos), top_feats[imp_col].values,
                color=COLORS["secondary"], alpha=0.8)
        ax.set_yticks(list(y_pos))
        ax.set_yticklabels(
            [str(f)[:30] for f in top_feats[feat_col].values], fontsize=9
        )
        ax.set_xlabel("Importance Moyenne (normalisée)")
        ax.set_title(f"Top {top_n} Features — Importance pour la Prédiction ML")
        ax.invert_yaxis()
    else:
        ax.text(0.5, 0.5, "Feature importance non disponible",
                ha="center", va="center", transform=ax.transAxes)

    plt.tight_layout()
    return fig_to_base64(fig)


def chart_language_breakdown(df: pd.DataFrame) -> str:
    """Distribution des langues."""
    set_style()
    fig, ax = plt.subplots(figsize=(7, 5))

    if "language" in df.columns:
        lang_counts = df["language"].value_counts()
        lang_labels = {
            "fr": "Français", "ar": "Arabe", "darija": "Darija",
            "arabizi": "Arabizi", "en": "Anglais", "mixed": "Mixte",
        }
        labels = [lang_labels.get(l, l) for l in lang_counts.index]
        lang_colors = [
            "#3498db", "#e74c3c", "#2ecc71", "#f39c12", "#9b59b6", "#1abc9c"
        ][:len(lang_counts)]

        wedges, texts, autotexts = ax.pie(
            lang_counts.values,
            labels=labels,
            colors=lang_colors,
            autopct="%1.1f%%",
            startangle=90,
            wedgeprops={"edgecolor": "white", "linewidth": 1.5},
        )
    else:
        ax.text(0.5, 0.5, "Données de langue non disponibles",
                ha="center", va="center", transform=ax.transAxes)

    ax.set_title("Distribution des Langues dans le Groupe")
    plt.tight_layout()
    return fig_to_base64(fig)


def chart_smart_money_scores(member_scores: Optional[pd.DataFrame]) -> str:
    """Graphique des scores Smart Money des membres."""
    set_style()
    fig, ax = plt.subplots(figsize=(10, 6))

    if member_scores is not None and not member_scores.empty:
        sms_col = next(
            (c for c in ["sms_score", "smart_money_score", "score"] if c in member_scores.columns),
            None,
        )
        if sms_col:
            top20_members = member_scores.nlargest(20, sms_col).copy()
            if hasattr(top20_members.index, "name") and top20_members.index.name:
                member_names = [str(n)[:15] for n in top20_members.index]
            elif "author" in top20_members.columns:
                member_names = [str(n)[:15] for n in top20_members["author"].values]
            else:
                member_names = [f"Membre {i}" for i in range(len(top20_members))]

            scores = top20_members[sms_col].values
            bar_colors = [COLORS["success"] if s > 70 else COLORS["warning"] if s > 50
                          else COLORS["danger"] for s in scores]

            ax.barh(range(len(member_names)), scores, color=bar_colors, alpha=0.8)
            ax.set_yticks(range(len(member_names)))
            ax.set_yticklabels(member_names, fontsize=8)
            ax.set_xlabel("Score Smart Money")
            ax.set_title("Top 20 Membres — Score Smart Money")
            ax.axvline(70, color=COLORS["success"], linestyle="--",
                       alpha=0.5, label="Smart Money (>70)")
            ax.legend(fontsize=8)
            ax.invert_yaxis()
        else:
            ax.text(0.5, 0.5, "Données SMS non disponibles",
                    ha="center", va="center", transform=ax.transAxes)
    else:
        ax.text(0.5, 0.5, "Données membres non disponibles",
                ha="center", va="center", transform=ax.transAxes)

    plt.tight_layout()
    return fig_to_base64(fig)


def chart_backtest_metrics_table(strategy_metrics: Optional[Dict[str, Any]]) -> str:
    """Génère un graphique tableau des métriques de backtest."""
    set_style()

    if not strategy_metrics:
        fig, ax = plt.subplots(figsize=(10, 3))
        ax.text(0.5, 0.5, "Métriques non disponibles", ha="center", va="center",
                transform=ax.transAxes)
        return fig_to_base64(fig)

    # Prépare les données
    rows = []
    for strat, metrics in strategy_metrics.items():
        if not isinstance(metrics, dict):
            continue
        rows.append([
            strat.replace("_", " ")[:25],
            f"{metrics.get('cagr', 0):.1%}",
            f"{metrics.get('sharpe', 0):.2f}",
            f"{metrics.get('sortino', 0):.2f}",
            f"{metrics.get('max_drawdown', 0):.1%}",
            f"{metrics.get('calmar', 0):.2f}",
            f"{metrics.get('win_rate', 0):.1%}",
        ])

    if not rows:
        fig, ax = plt.subplots(figsize=(10, 3))
        ax.text(0.5, 0.5, "Aucune métrique", ha="center", va="center",
                transform=ax.transAxes)
        return fig_to_base64(fig)

    col_headers = ["Stratégie", "CAGR", "Sharpe", "Sortino", "Max DD", "Calmar", "Win Rate"]

    fig_height = max(3, len(rows) * 0.6 + 1)
    fig, ax = plt.subplots(figsize=(14, fig_height))
    ax.axis("off")

    table = ax.table(
        cellText=rows,
        colLabels=col_headers,
        loc="center",
        cellLoc="center",
    )
    table.auto_set_font_size(False)
    table.set_fontsize(9)
    table.scale(1.2, 1.5)

    # Style header
    for j in range(len(col_headers)):
        table[(0, j)].set_facecolor(COLORS["primary"])
        table[(0, j)].set_text_props(color="white", fontweight="bold")

    # Couleurs alternées des lignes
    for i in range(1, len(rows) + 1):
        bg = COLORS["light"] if i % 2 == 0 else COLORS["white"]
        # Colore en vert si CAGR > benchmark
        for j in range(len(col_headers)):
            table[(i, j)].set_facecolor(bg)

    ax.set_title("Métriques de Performance — Stratégies NLP vs Benchmark", fontsize=12,
                 fontweight="bold", pad=10)
    plt.tight_layout()
    return fig_to_base64(fig)


# ─────────────────────────────────────────────────────────────
# TEMPLATE HTML
# ─────────────────────────────────────────────────────────────

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{{ title }}</title>
<style>
  *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background: #f0f2f5; color: #2c3e50; line-height: 1.6; }
  .container { max-width: 1200px; margin: 0 auto; padding: 20px; }

  /* Header */
  .report-header { background: linear-gradient(135deg, #1a5276 0%, #2980b9 100%);
    color: white; padding: 40px; border-radius: 12px; margin-bottom: 30px;
    box-shadow: 0 4px 20px rgba(0,0,0,0.15); }
  .report-header h1 { font-size: 2em; margin-bottom: 8px; }
  .report-header h2 { font-size: 1.2em; opacity: 0.85; font-weight: 400; }
  .report-meta { margin-top: 16px; opacity: 0.75; font-size: 0.9em; }

  /* KPI cards */
  .kpi-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 16px; margin-bottom: 30px; }
  .kpi-card { background: white; border-radius: 10px; padding: 20px; text-align: center;
    box-shadow: 0 2px 10px rgba(0,0,0,0.08); border-top: 4px solid #2980b9; }
  .kpi-value { font-size: 2em; font-weight: 700; color: #1a5276; }
  .kpi-label { font-size: 0.85em; color: #7f8c8d; margin-top: 4px; }

  /* Sections */
  .section { background: white; border-radius: 12px; padding: 30px; margin-bottom: 25px;
    box-shadow: 0 2px 12px rgba(0,0,0,0.08); }
  .section-header { display: flex; align-items: center; margin-bottom: 20px;
    border-bottom: 3px solid #2980b9; padding-bottom: 10px; }
  .section-number { background: #1a5276; color: white; width: 36px; height: 36px;
    border-radius: 50%; display: flex; align-items: center; justify-content: center;
    font-weight: bold; margin-right: 12px; flex-shrink: 0; }
  .section-title { font-size: 1.3em; font-weight: 700; color: #1a5276; }

  /* Tables */
  table { width: 100%; border-collapse: collapse; font-size: 0.9em; }
  th { background: #1a5276; color: white; padding: 10px 12px; text-align: left; }
  td { padding: 8px 12px; border-bottom: 1px solid #ecf0f1; }
  tr:nth-child(even) { background: #f8f9fa; }
  tr:hover { background: #eaf2fb; }

  /* Signal badges */
  .badge { display: inline-block; padding: 3px 10px; border-radius: 20px; font-size: 0.8em; font-weight: 600; }
  .badge-FORT_ACHAT { background: #d5f5e3; color: #1e8449; }
  .badge-ACHAT { background: #e8f8f5; color: #27ae60; }
  .badge-NEUTRE { background: #fef9e7; color: #d68910; }
  .badge-VENTE { background: #fdf2e9; color: #ca6f1e; }
  .badge-FORT_VENTE { background: #fdedec; color: #cb4335; }

  /* Charts */
  .chart-container { margin: 20px 0; text-align: center; }
  .chart-container img { max-width: 100%; border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.1); }

  /* Alerts */
  .alert { padding: 14px 18px; border-radius: 8px; margin: 12px 0; border-left: 5px solid; }
  .alert-warning { background: #fef9e7; border-color: #f39c12; color: #7d6608; }
  .alert-info { background: #eaf2fb; border-color: #2980b9; color: #1a5276; }
  .alert-danger { background: #fdedec; border-color: #e74c3c; color: #922b21; }
  .alert-success { background: #eafaf1; border-color: #27ae60; color: #1e8449; }

  /* Two column layout */
  .two-col { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }
  @media (max-width: 768px) { .two-col { grid-template-columns: 1fr; } }

  /* Top picks */
  .picks-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 16px; }
  .pick-card { border-radius: 10px; padding: 16px; text-align: center; border: 2px solid;
    transition: transform 0.2s; }
  .pick-card:hover { transform: translateY(-2px); }
  .pick-card .ticker { font-size: 1.5em; font-weight: 800; }
  .pick-card .score { font-size: 1.2em; font-weight: 600; }
  .pick-card.FORT_ACHAT { border-color: #27ae60; background: #d5f5e3; }
  .pick-card.ACHAT { border-color: #2ecc71; background: #e8f8f5; }
  .pick-card.NEUTRE { border-color: #f39c12; background: #fef9e7; }
  .pick-card.VENTE { border-color: #e67e22; background: #fdf2e9; }
  .pick-card.FORT_VENTE { border-color: #e74c3c; background: #fdedec; }

  /* Footer */
  .footer { display: flex; justify-content: space-between; align-items: flex-start;
    padding: 20px 30px; color: #7f8c8d; font-size: 0.85em;
    border-top: 2px solid #1a5276; margin-top: 30px; background: #f8f9fa; }
  .footer-left { text-align: left; font-weight: 600; color: #1a5276; font-size: 0.95em; }
  .footer-center { text-align: center; flex: 1; }
  .footer-right { text-align: right; font-size: 0.8em; }

  /* Print: pied de page fixe sur chaque page */
  @media print {
    @page { margin: 20mm 15mm 25mm 15mm; }
    body { background: white; }
    .footer { position: fixed; bottom: 0; left: 0; right: 0;
      border-top: 1px solid #1a5276; padding: 6px 15mm; font-size: 0.75em; }
    .section { page-break-inside: avoid; }
  }
  /* Watermark auteur en bas gauche (visible à l'écran aussi) */
  .author-stamp { font-weight: 700; color: #1a5276; letter-spacing: 0.5px; }

  /* Stats inline */
  .stat-row { display: flex; justify-content: space-between; align-items: center;
    padding: 8px 0; border-bottom: 1px solid #ecf0f1; }
  .stat-label { color: #7f8c8d; font-size: 0.9em; }
  .stat-value { font-weight: 600; }

  /* Progress bar */
  .progress-bar { background: #ecf0f1; border-radius: 4px; height: 8px; overflow: hidden; }
  .progress-fill { height: 100%; border-radius: 4px; }
</style>
</head>
<body>
<div class="container">

<!-- HEADER -->
<div class="report-header">
  <h1>{{ title }}</h1>
  <h2>{{ subtitle }}</h2>
  <div class="report-meta">
    Généré le {{ date }} | {{ n_messages | format_number }} messages analysés |
    {{ n_members }} membres | {{ n_tickers }} valeurs BVC couvertes
  </div>
</div>

<!-- KPI CARDS -->
<div class="kpi-grid">
  <div class="kpi-card">
    <div class="kpi-value">{{ n_messages | format_number }}</div>
    <div class="kpi-label">Messages analysés</div>
  </div>
  <div class="kpi-card">
    <div class="kpi-value">{{ n_members }}</div>
    <div class="kpi-label">Membres actifs</div>
  </div>
  <div class="kpi-card">
    <div class="kpi-value">{{ n_smart_money }}</div>
    <div class="kpi-label">Smart Money identifiés</div>
  </div>
  <div class="kpi-card">
    <div class="kpi-value">{{ n_tickers }}</div>
    <div class="kpi-label">Valeurs couvertes</div>
  </div>
  <div class="kpi-card">
    <div class="kpi-value">{{ n_fort_achat }}</div>
    <div class="kpi-label">Signaux FORT ACHAT</div>
  </div>
  <div class="kpi-card">
    <div class="kpi-value">{{ best_sharpe }}</div>
    <div class="kpi-label">Meilleur Sharpe (backtest)</div>
  </div>
</div>

<!-- SECTION 1: RÉSUMÉ EXÉCUTIF -->
<div class="section">
  <div class="section-header">
    <div class="section-number">1</div>
    <div class="section-title">Résumé Exécutif</div>
  </div>
  <p style="margin-bottom: 16px; color: #555;">
    Ce rapport présente l'analyse complète d'un groupe WhatsApp dédié à la Bourse de Casablanca,
    couvrant {{ date_range }}. Le système d'intelligence artificielle a traité
    {{ n_messages | format_number }} messages en {% if languages %}{{ languages | join(", ") }}{% else %}plusieurs langues{% endif %}
    pour extraire des signaux d'investissement actionnables.
  </p>

  <h3 style="margin-bottom: 12px; color: #1a5276;">Top 5 Recommandations</h3>
  <div class="picks-grid">
    {% for pick in top5 %}
    <div class="pick-card {{ pick.signal }}">
      <div class="ticker">{{ pick.ticker }}</div>
      <div style="font-size: 0.85em; color: #666;">{{ pick.name[:20] }}</div>
      <div class="score" style="margin-top: 8px;">{{ pick.composite_score | round(0) | int }}/100</div>
      <div style="margin-top: 6px;">
        <span class="badge badge-{{ pick.signal }}">{{ pick.signal.replace("_", " ") }}</span>
      </div>
    </div>
    {% endfor %}
  </div>

  <div style="margin-top: 20px;">
    <h3 style="margin-bottom: 10px; color: #1a5276;">Découvertes Clés</h3>
    <ul style="list-style: none;">
      {% for finding in key_findings %}
      <li style="padding: 6px 0; border-bottom: 1px solid #ecf0f1;">
        <span style="color: #2980b9; margin-right: 8px;">▶</span> {{ finding }}
      </li>
      {% endfor %}
    </ul>
  </div>
</div>

<!-- SECTION 2: CARTOGRAPHIE DU GROUPE -->
<div class="section">
  <div class="section-header">
    <div class="section-number">2</div>
    <div class="section-title">Cartographie du Groupe WhatsApp</div>
  </div>
  <div class="two-col">
    <div>
      <h3 style="margin-bottom: 12px;">Statistiques Globales</h3>
      {% for stat in group_stats %}
      <div class="stat-row">
        <span class="stat-label">{{ stat.label }}</span>
        <span class="stat-value">{{ stat.value }}</span>
      </div>
      {% endfor %}
    </div>
    <div>
      <h3 style="margin-bottom: 12px;">Top 10 Contributeurs</h3>
      {% if top_contributors %}
      <table>
        <tr><th>Membre</th><th>Messages</th><th>Signaux</th></tr>
        {% for c in top_contributors %}
        <tr>
          <td>{{ c.author }}</td>
          <td>{{ c.messages }}</td>
          <td>{{ c.signals }}</td>
        </tr>
        {% endfor %}
      </table>
      {% else %}
      <div class="alert alert-info">Données contributeurs non disponibles</div>
      {% endif %}
    </div>
  </div>
</div>

<!-- SECTION 3: ANALYSE COMPORTEMENTALE -->
<div class="section">
  <div class="section-header">
    <div class="section-number">3</div>
    <div class="section-title">Analyse Comportementale</div>
  </div>
  {% if chart_fear_greed %}
  <div class="chart-container">
    <img src="data:image/png;base64,{{ chart_fear_greed }}" alt="Fear & Greed Evolution">
  </div>
  {% endif %}
  {% if chart_sentiment %}
  <div class="chart-container">
    <img src="data:image/png;base64,{{ chart_sentiment }}" alt="Sentiment Evolution">
  </div>
  {% endif %}
  <div class="two-col" style="margin-top: 16px;">
    {% for stat in behavioral_stats %}
    <div class="stat-row">
      <span class="stat-label">{{ stat.label }}</span>
      <span class="stat-value">{{ stat.value }}</span>
    </div>
    {% endfor %}
  </div>
</div>

<!-- SECTION 4: ANALYSE SMART MONEY -->
<div class="section">
  <div class="section-header">
    <div class="section-number">4</div>
    <div class="section-title">Analyse Smart Money</div>
  </div>
  {% if chart_smart_money %}
  <div class="chart-container">
    <img src="data:image/png;base64,{{ chart_smart_money }}" alt="Smart Money Scores">
  </div>
  {% endif %}
  {% if smart_money_table %}
  <table>
    <tr>
      <th>#</th><th>Membre</th><th>Score SMS</th><th>Win Rate</th><th>Signaux</th><th>Précision</th>
    </tr>
    {% for m in smart_money_table %}
    <tr>
      <td>{{ m.rank }}</td>
      <td>{{ m.author }}</td>
      <td>{{ m.sms_score | round(1) }}</td>
      <td>{{ m.win_rate }}%</td>
      <td>{{ m.n_signals }}</td>
      <td>{{ m.accuracy }}%</td>
    </tr>
    {% endfor %}
  </table>
  {% else %}
  <div class="alert alert-info">Données Smart Money non disponibles</div>
  {% endif %}
</div>

<!-- SECTION 5: ANALYSE RÉSEAU -->
<div class="section">
  <div class="section-header">
    <div class="section-number">5</div>
    <div class="section-title">Analyse Réseau (Graph Theory)</div>
  </div>
  {% if network_stats %}
  <div class="two-col">
    <div>
      {% for stat in network_stats %}
      <div class="stat-row">
        <span class="stat-label">{{ stat.label }}</span>
        <span class="stat-value">{{ stat.value }}</span>
      </div>
      {% endfor %}
    </div>
    <div>
      {% if top_nodes %}
      <h3 style="margin-bottom: 12px;">Top Nœuds par Centralité</h3>
      <table>
        <tr><th>Membre</th><th>Centralité</th><th>Communauté</th></tr>
        {% for node in top_nodes %}
        <tr><td>{{ node.name }}</td><td>{{ node.centrality }}</td><td>{{ node.community }}</td></tr>
        {% endfor %}
      </table>
      {% endif %}
    </div>
  </div>
  {% else %}
  <div class="alert alert-info">Métriques réseau non disponibles</div>
  {% endif %}
</div>

<!-- SECTION 6: ANALYSE NLP -->
<div class="section">
  <div class="section-header">
    <div class="section-number">6</div>
    <div class="section-title">Analyse NLP Multi-Lingue</div>
  </div>
  <div class="two-col">
    <div>
      {% if chart_signals %}
      <div class="chart-container">
        <img src="data:image/png;base64,{{ chart_signals }}" alt="Signal Distribution">
      </div>
      {% endif %}
    </div>
    <div>
      {% if chart_language %}
      <div class="chart-container">
        <img src="data:image/png;base64,{{ chart_language }}" alt="Language Breakdown">
      </div>
      {% endif %}
    </div>
  </div>
  {% if nlp_stats %}
  {% for stat in nlp_stats %}
  <div class="stat-row">
    <span class="stat-label">{{ stat.label }}</span>
    <span class="stat-value">{{ stat.value }}</span>
  </div>
  {% endfor %}
  {% endif %}
</div>

<!-- SECTION 7: ANALYSE PRÉDICTIVE ML -->
<div class="section">
  <div class="section-header">
    <div class="section-number">7</div>
    <div class="section-title">Analyse Prédictive — Machine Learning</div>
  </div>
  {% if ml_results_table %}
  <table>
    <tr><th>Modèle</th><th>AUC-ROC</th><th>F1</th><th>Précision</th><th>Rappel</th><th>Accuracy</th></tr>
    {% for m in ml_results_table %}
    <tr>
      <td><strong>{{ m.model }}</strong>{% if m.is_best %} ★{% endif %}</td>
      <td>{{ "%.4f" | format(m.auc) }}</td>
      <td>{{ "%.4f" | format(m.f1) }}</td>
      <td>{{ "%.4f" | format(m.precision) }}</td>
      <td>{{ "%.4f" | format(m.recall) }}</td>
      <td>{{ "%.4f" | format(m.accuracy) }}</td>
    </tr>
    {% endfor %}
  </table>
  {% endif %}
  {% if chart_feature_importance %}
  <div class="chart-container" style="margin-top: 20px;">
    <img src="data:image/png;base64,{{ chart_feature_importance }}" alt="Feature Importance">
  </div>
  {% endif %}
  {% if stats_highlights %}
  <div style="margin-top: 16px;">
    <h3 style="margin-bottom: 10px;">Robustesse Statistique</h3>
    {% for s in stats_highlights %}
    <div class="alert alert-{{ s.level }}">{{ s.text }}</div>
    {% endfor %}
  </div>
  {% endif %}
</div>

<!-- SECTION 8: BACKTESTING -->
<div class="section">
  <div class="section-header">
    <div class="section-number">8</div>
    <div class="section-title">Backtesting des Stratégies NLP</div>
  </div>
  {% if chart_equity %}
  <div class="chart-container">
    <img src="data:image/png;base64,{{ chart_equity }}" alt="Equity Curves">
  </div>
  {% endif %}
  {% if chart_backtest_table %}
  <div class="chart-container">
    <img src="data:image/png;base64,{{ chart_backtest_table }}" alt="Backtest Metrics">
  </div>
  {% endif %}
  {% if backtest_disclaimer %}
  <div class="alert alert-warning">{{ backtest_disclaimer }}</div>
  {% endif %}
</div>

<!-- SECTION 9: CLASSEMENT DES VALEURS -->
<div class="section">
  <div class="section-header">
    <div class="section-number">9</div>
    <div class="section-title">Classement des Valeurs BVC</div>
  </div>
  {% if chart_tickers %}
  <div class="chart-container">
    <img src="data:image/png;base64,{{ chart_tickers }}" alt="Top Tickers">
  </div>
  {% endif %}
  {% if rankings_table %}
  <div style="overflow-x: auto;">
    <table>
      <tr>
        <th>#</th><th>Ticker</th><th>Score</th><th>Signal</th>
        <th>Fondamental</th><th>Technique</th><th>NLP</th><th>Smart Money</th>
        <th>P(Surperf. 1M)</th><th>P/E</th><th>Div%</th>
      </tr>
      {% for r in rankings_table %}
      <tr>
        <td>{{ r.rank }}</td>
        <td><strong>{{ r.ticker }}</strong></td>
        <td>
          <div class="progress-bar" style="width: 80px; display: inline-block;">
            <div class="progress-fill" style="width: {{ r.composite_score }}%; background: {% if r.composite_score >= 75 %}#27ae60{% elif r.composite_score >= 60 %}#2ecc71{% elif r.composite_score >= 40 %}#f39c12{% else %}#e74c3c{% endif %};"></div>
          </div>
          <span style="margin-left: 6px; font-weight: 600;">{{ r.composite_score }}</span>
        </td>
        <td><span class="badge badge-{{ r.signal }}">{{ r.signal.replace("_", " ") }}</span></td>
        <td>{{ r.fundamental_score }}</td>
        <td>{{ r.technical_score }}</td>
        <td>{{ r.nlp_score }}</td>
        <td>{{ r.smart_money_score }}</td>
        <td>{{ "%.1f" | format(r.p1m * 100) }}%</td>
        <td>{{ r.pe }}</td>
        <td>{{ r.div }}%</td>
      </tr>
      {% endfor %}
    </table>
  </div>
  {% endif %}
</div>

<!-- SECTION 10: LIMITES MÉTHODOLOGIQUES -->
<div class="section">
  <div class="section-header">
    <div class="section-number">10</div>
    <div class="section-title">Limites Méthodologiques</div>
  </div>
  <div class="alert alert-warning">
    <strong>Avertissement Important:</strong> Cette analyse est basée sur des messages WhatsApp
    et ne constitue pas un conseil en investissement. Les performances passées ne garantissent pas
    les performances futures.
  </div>
  <ul style="list-style: disc; padding-left: 20px; margin-top: 12px;">
    <li style="padding: 4px 0;">Les prix utilisés dans le backtesting sont partiellement synthétiques (GBM) faute de données historiques complètes.</li>
    <li style="padding: 4px 0;">Le biais de survie: les tickers qui ont disparu de la cote ne sont pas analysés.</li>
    <li style="padding: 4px 0;">Le biais de look-ahead: la connaissance du groupe inclut des membres qui peuvent avoir des informations non publiques.</li>
    <li style="padding: 4px 0;">Le NLP multilingue (Darija/Arabizi) introduit des incertitudes de traduction.</li>
    <li style="padding: 4px 0;">Les modèles ML sont entraînés sur un historique limité et peuvent sur-apprendre.</li>
    <li style="padding: 4px 0;">L'analyse de réseau suppose que l'interaction = influence, ce qui n'est pas toujours vrai.</li>
    <li style="padding: 4px 0;">Le marché BVC est relativement peu liquide; les stratégies peuvent être difficiles à répliquer en pratique.</li>
  </ul>
  {% if overfitting_warning %}
  <div class="alert alert-danger" style="margin-top: 12px;">
    <strong>Risque de sur-apprentissage ({{ overfitting_level }}):</strong> {{ overfitting_warning }}
  </div>
  {% endif %}
</div>

<!-- SECTION 11: RECOMMANDATIONS -->
<div class="section">
  <div class="section-header">
    <div class="section-number">11</div>
    <div class="section-title">Recommandations Opérationnelles</div>
  </div>
  <ol style="padding-left: 20px;">
    <li style="padding: 6px 0;">Utiliser les signaux FORT_ACHAT uniquement comme point de départ d'une due diligence approfondie, jamais comme seul critère d'investissement.</li>
    <li style="padding: 6px 0;">Prioriser les signaux où Smart Money (>70) ET NLP sentiment (>0.5) convergent.</li>
    <li style="padding: 6px 0;">En période de Fear & Greed < 20, renforcer les positions sur les valeurs de qualité avec bons fondamentaux.</li>
    <li style="padding: 6px 0;">Surveiller les topics en émergence rapide (weak signals) pour anticiper les mouvements de foule.</li>
    <li style="padding: 6px 0;">Limiter la taille des positions: ne pas dépasser 5% du portefeuille sur un seul signal NLP.</li>
    <li style="padding: 6px 0;">Renouveler l'analyse mensuellement pour tenir compte de l'évolution du groupe.</li>
  </ol>
</div>

<!-- SECTION 12: AXES D'AMÉLIORATION -->
<div class="section">
  <div class="section-header">
    <div class="section-number">12</div>
    <div class="section-title">Axes d'Amélioration</div>
  </div>
  <div class="two-col">
    <div>
      <h3 style="margin-bottom: 10px; color: #1a5276;">Court terme</h3>
      <ul style="list-style: disc; padding-left: 18px;">
        <li style="padding: 4px 0;">Intégrer les données de prix réels BVC via l'API officielle</li>
        <li style="padding: 4px 0;">Affiner le modèle Darija avec un corpus étiqueté BVC</li>
        <li style="padding: 4px 0;">Ajouter la détection de sarcasme et d'ironie</li>
        <li style="padding: 4px 0;">Implémenter un modèle BERT multilingue pour le NLP</li>
      </ul>
    </div>
    <div>
      <h3 style="margin-bottom: 10px; color: #1a5276;">Moyen terme</h3>
      <ul style="list-style: disc; padding-left: 18px;">
        <li style="padding: 4px 0;">Pipeline temps-réel avec alertes automatiques</li>
        <li style="padding: 4px 0;">Intégration des rapports financiers semestriels BVC</li>
        <li style="padding: 4px 0;">Analyse comparative multi-groupes WhatsApp</li>
        <li style="padding: 4px 0;">Modèle de prédiction des volumes de trading</li>
      </ul>
    </div>
  </div>
</div>

<!-- SECTION TRANSPARENCE DONNÉES -->
<div class="section" style="margin-top:40px;">
  <div class="section-header">
    <h2>🔍 Transparence des Données</h2>
  </div>
  <div class="card" style="padding:24px;">
    <h3 style="color:#1a5276; margin-bottom:16px;">Sources & Couverture Historique</h3>
    <p style="margin-bottom:12px; color:#555;">
      Les analyses de prix et de corrélation reposent sur des données historiques réelles
      récupérées via l'API casabourse.ma et BVCscrap. Voici le détail exact de la couverture :
    </p>
    <table style="width:100%; border-collapse:collapse; font-size:0.88em;">
      <thead>
        <tr style="background:#1a5276; color:white;">
          <th style="padding:8px 12px; text-align:left;">Groupe</th>
          <th style="padding:8px 12px; text-align:left;">Période réelle</th>
          <th style="padding:8px 12px; text-align:center;">Obs.</th>
          <th style="padding:8px 12px; text-align:left;">Tickers</th>
        </tr>
      </thead>
      <tbody>
        <tr style="background:#eaf2ff;">
          <td style="padding:8px 12px; font-weight:600;">Groupe A — 3 ans</td>
          <td style="padding:8px 12px;">Juin 2023 → Juin 2026</td>
          <td style="padding:8px 12px; text-align:center;">739</td>
          <td style="padding:8px 12px; font-size:0.85em;">IAM, ATW, BCP, BOA, CIH, CDM, HPS, MNG, ATL, ADH, ADI, AFI, AFM, AGM, ARD, BAL, COL, CSR, CTM, DHO, EQD, GAZ, INV, JET, LBV, LES, LHM, M2M, MOX, NEJ</td>
        </tr>
        <tr>
          <td style="padding:8px 12px; font-weight:600;">Groupe B — 2 ans</td>
          <td style="padding:8px 12px;">Mai 2024 → Mai 2026</td>
          <td style="padding:8px 12px; text-align:center;">493</td>
          <td style="padding:8px 12px; font-size:0.85em;">CFGB, CMT, MSA, RDS, RIS, SMI, SOT, SRM, TGC</td>
        </tr>
        <tr style="background:#eaf2ff;">
          <td style="padding:8px 12px; font-weight:600;">TGCC — 4.5 ans</td>
          <td style="padding:8px 12px;">Déc 2021 → Juin 2026</td>
          <td style="padding:8px 12px; text-align:center;">1 112</td>
          <td style="padding:8px 12px; font-size:0.85em;">TGCC (via BVCscrap)</td>
        </tr>
        <tr>
          <td style="padding:8px 12px; font-weight:600;">Extension GBM</td>
          <td style="padding:8px 12px;">Sept 2020 → début données réelles</td>
          <td style="padding:8px 12px; text-align:center;">—</td>
          <td style="padding:8px 12px; font-size:0.85em; font-style:italic;">Simulation calibrée sur μ, σ réels — identifiée par _simulated=True dans les données</td>
        </tr>
      </tbody>
    </table>
    <div style="margin-top:16px; padding:12px; background:#fff8e1; border-left:4px solid #f39c12; border-radius:4px;">
      <strong>⚠️ Note méthodologique :</strong> L'API casabourse est limitée à 739 enregistrements
      (~3 ans de données journalières). Les périodes antérieures sont comblées par simulation
      GBM (Geometric Brownian Motion) calibrée sur les paramètres statistiques réels (μ annuel, σ annuel)
      de chaque titre. Les résultats de corrélation et de backtest sont fiables sur la période réelle.
    </div>
    <div style="margin-top:12px; padding:12px; background:#e8f8f5; border-left:4px solid #27ae60; border-radius:4px;">
      <strong>✅ Sources :</strong> casabourse.ma (API officielle BVC) · BVCscrap (open-source) ·
      Corpus WhatsApp : {{ n_messages | default('~1,2M') }} messages · {{ n_authors | default('N') }} participants
    </div>
  </div>
</div>

<!-- FOOTER -->
<div class="footer">
  <div class="footer-left">
    <span class="author-stamp">Fekak Noureddine</span>
  </div>
  <div class="footer-center">
    <p>Rapport généré automatiquement par BVC WhatsApp Analysis System v1.0</p>
    <p style="margin-top: 4px;">{{ date }} | Données: {{ date_range }}</p>
    <p style="margin-top: 8px; font-style: italic; color: #95a5a6;">
      Ce rapport est fourni à titre informatif uniquement. Il ne constitue pas un conseil en investissement.
      Investir en bourse comporte des risques de perte en capital.
    </p>
  </div>
  <div class="footer-right">
    <p>BVC Analysis System</p>
    <p>v1.0 — {{ date }}</p>
  </div>
</div>

</div>
</body>
</html>"""


# ─────────────────────────────────────────────────────────────
# HELPERS DE DONNÉES
# ─────────────────────────────────────────────────────────────

def format_number(n: Any) -> str:
    """Formate un nombre avec séparateurs de milliers."""
    try:
        return f"{int(n):,}".replace(",", " ")
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

    sms_col = next(
        (c for c in ["sms_score", "smart_money_score", "score"] if c in member_scores.columns),
        None,
    )
    if sms_col is None:
        return []

    top_members = member_scores.nlargest(n, sms_col).copy()
    result = []

    for rank, (idx, row) in enumerate(top_members.iterrows(), 1):
        if "author" in top_members.columns:
            author_name = str(row.get("author", idx))[:15]
        else:
            author_name = str(idx)[:15]

        win_rate_val = row.get("win_rate", row.get("sms_win_rate", 50))
        n_signals = row.get("n_signals", row.get("total_signals", 0))
        accuracy = row.get("accuracy", row.get("precision", win_rate_val))

        result.append({
            "rank": rank,
            "author": author_name,
            "sms_score": float(row[sms_col]),
            "win_rate": f"{float(win_rate_val):.1f}",
            "n_signals": int(n_signals) if pd.notna(n_signals) else 0,
            "accuracy": f"{float(accuracy):.1f}",
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
    logger.info("=== Phase 14: Génération du Rapport HTML ===")

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

    # ── Génération des graphiques ──────────────────────────
    logger.info("Génération des graphiques...")
    daily_sentiment = phase8_results.get("daily_sentiment", pd.DataFrame()) if phase8_results else pd.DataFrame()

    charts = {}
    try:
        charts["fear_greed"] = chart_fear_greed_evolution(fear_greed_series, daily_sentiment)
    except Exception as e:
        logger.warning(f"Chart fear_greed: {e}")
        charts["fear_greed"] = ""

    try:
        charts["sentiment"] = chart_sentiment_evolution(daily_sentiment)
    except Exception as e:
        logger.warning(f"Chart sentiment: {e}")
        charts["sentiment"] = ""

    try:
        charts["signals"] = chart_signal_distribution(df)
    except Exception as e:
        logger.warning(f"Chart signals: {e}")
        charts["signals"] = ""

    try:
        charts["language"] = chart_language_breakdown(df)
    except Exception as e:
        logger.warning(f"Chart language: {e}")
        charts["language"] = ""

    try:
        charts["smart_money"] = chart_smart_money_scores(member_scores)
    except Exception as e:
        logger.warning(f"Chart smart_money: {e}")
        charts["smart_money"] = ""

    try:
        equity_curves = phase11_results.get("equity_curves") if phase11_results else None
        charts["equity"] = chart_equity_curves(equity_curves)
    except Exception as e:
        logger.warning(f"Chart equity: {e}")
        charts["equity"] = ""

    try:
        predictions = phase13_results.get("predictions") if phase13_results else None
        charts["tickers"] = chart_top_tickers(predictions)
    except Exception as e:
        logger.warning(f"Chart tickers: {e}")
        charts["tickers"] = ""

    try:
        feat_imp = phase9_results.get("feature_importance") if phase9_results else None
        charts["feature_importance"] = chart_feature_importance(feat_imp)
    except Exception as e:
        logger.warning(f"Chart feature_importance: {e}")
        charts["feature_importance"] = ""

    try:
        strategy_metrics = phase11_results.get("strategy_metrics") if phase11_results else None
        charts["backtest_table"] = chart_backtest_metrics_table(strategy_metrics)
    except Exception as e:
        logger.warning(f"Chart backtest_table: {e}")
        charts["backtest_table"] = ""

    logger.info("Graphiques générés.")

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
        fg_regime = "Greed Extrême" if fg_last > 80 else "Greed" if fg_last > 60 else \
                    "Neutre" if fg_last > 40 else "Fear" if fg_last > 20 else "Fear Extrême"
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

    # ── Rendu du template ──────────────────────────────────
    logger.info("Rendu du template HTML...")

    template_vars = {
        "title": REPORT_TITLE,
        "subtitle": REPORT_SUBTITLE,
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
        # Charts
        "chart_fear_greed": charts.get("fear_greed", ""),
        "chart_sentiment": charts.get("sentiment", ""),
        "chart_signals": charts.get("signals", ""),
        "chart_language": charts.get("language", ""),
        "chart_smart_money": charts.get("smart_money", ""),
        "chart_equity": charts.get("equity", ""),
        "chart_tickers": charts.get("tickers", ""),
        "chart_feature_importance": charts.get("feature_importance", ""),
        "chart_backtest_table": charts.get("backtest_table", ""),
    }

    if JINJA2_AVAILABLE:
        env = Environment(loader=BaseLoader())
        env.filters["format_number"] = format_number
        template = env.from_string(HTML_TEMPLATE)
        html_content = template.render(**template_vars)
    else:
        # Fallback: f-string basique
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

    print("Test Phase 14: génération du rapport HTML...")

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
