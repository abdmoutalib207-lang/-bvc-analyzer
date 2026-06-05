"""
Pipeline principal — Orchestrateur des 14 phases d'analyse BVC WhatsApp
Usage : python -m whatsapp_analysis.pipeline --input data/_chat.txt --output output/
"""
from __future__ import annotations

import argparse
import pickle
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd

REPO_ROOT = Path(__file__).parent.parent


# ─────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────

def _save(obj: Any, name: str, out: Path) -> None:
    with open(out / f"{name}.pkl", "wb") as f:
        pickle.dump(obj, f)


def _load(name: str, out: Path) -> Optional[Any]:
    p = out / f"{name}.pkl"
    if p.exists():
        with open(p, "rb") as f:
            return pickle.load(f)
    return None


def _header(name: str, num: int) -> None:
    print(f"\n{'─'*60}")
    print(f"  PHASE {num:02d} — {name}")
    print(f"{'─'*60}")


def _ok(t0: float) -> None:
    print(f"  ✓ Terminé en {time.time()-t0:.1f}s")


def _err(e: Exception, phase_name: str) -> None:
    import traceback
    print(f"  ✗ ERREUR Phase {phase_name}: {e}", file=sys.stderr)
    traceback.print_exc(file=sys.stderr)


# ─────────────────────────────────────────────
# PIPELINE
# ─────────────────────────────────────────────

def run_pipeline(
    input_file: str,
    output_dir: str,
    phases: Optional[List[int]] = None,
    skip_ml: bool = False,
    fast: bool = False,
    resume: bool = True,
) -> Dict[str, Any]:
    """Exécute le pipeline complet d'analyse WhatsApp BVC (14 phases)."""
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    run_all = phases is None
    def _run(n: int) -> bool:
        return run_all or n in phases

    R: Dict[str, Any] = {}   # résultats accumulés
    t_global = time.time()

    # ── PHASE 1 — Parsing ────────────────────────────────
    if _run(1):
        _header("Ingénierie des données / Parsing WhatsApp", 1)
        t0 = time.time()
        cached_df = _load("df", out) if resume else None
        if cached_df is not None:
            print("  → Chargé depuis cache")
            df = cached_df
            R["activity_stats"] = _load("activity_stats", out) or {}
        else:
            try:
                from whatsapp_analysis.phase1_parser import parse_chat
                from whatsapp_analysis.config import DEFAULT_CONFIG
                cfg = DEFAULT_CONFIG
                if fast:
                    cfg = DEFAULT_CONFIG.__class__(**{
                        **DEFAULT_CONFIG.__dict__,
                        "chunk_size": 5_000
                    })
                df, activity_stats = parse_chat(input_file, cfg=cfg)
                _save(df, "df", out)
                _save(activity_stats, "activity_stats", out)
                df.to_csv(out / "messages.csv", index=False)
                print(f"  → {len(df):,} messages | {df['author'].nunique()} membres")
                R["activity_stats"] = activity_stats
            except Exception as e:
                _err(e, "Parsing")
                df = pd.DataFrame()
        R["df"] = df
        _ok(t0)
    else:
        df = _load("df", out) or pd.DataFrame()
        R["df"] = df

    if df.empty:
        print("DataFrame vide — abandon du pipeline.", file=sys.stderr)
        return R

    # ── PHASE 2 — Détection langue ───────────────────────
    if _run(2):
        _header("Détection multilingue", 2)
        t0 = time.time()
        try:
            from whatsapp_analysis.phase2_languages import (
                add_language_to_df,
                build_member_language_profiles,
            )
            df = add_language_to_df(df)
            lang_profiles = build_member_language_profiles(df)
            _save(df, "df", out)
            _save(lang_profiles, "lang_profiles", out)
            dist = df["language"].value_counts().to_dict()
            print(f"  → Distribution : {dist}")
            R["lang_profiles"] = lang_profiles
        except Exception as e:
            _err(e, "Langues")
            R["lang_profiles"] = pd.DataFrame()
        _ok(t0)

    # ── PHASE 3 — NLP avancé ─────────────────────────────
    if _run(3):
        _header("NLP avancé — signaux, NER, prix cibles", 3)
        t0 = time.time()
        try:
            from whatsapp_analysis.phase3_nlp import enrich_dataframe
            df = enrich_dataframe(df)
            _save(df, "df", out)
            sig_dist = df["signal"].value_counts().to_dict() if "signal" in df.columns else {}
            print(f"  → Signaux : {sig_dist}")
            R["df"] = df
        except Exception as e:
            _err(e, "NLP")
        _ok(t0)

    # ── PHASE 4 — Finance comportementale ────────────────
    if _run(4):
        _header("Finance comportementale — Fear & Greed BVC", 4)
        t0 = time.time()
        fear_greed = pd.Series(dtype=float)
        try:
            from whatsapp_analysis.phase4_behavioral import run_behavioral_analysis
            fear_greed, regimes, inflections, herd_df, beh_stats = run_behavioral_analysis(df)
            _save(fear_greed, "fear_greed", out)
            _save(regimes, "regimes", out)
            _save(beh_stats, "beh_stats", out)
            if not fear_greed.empty:
                current = float(fear_greed.iloc[-1])
                print(f"  → Fear & Greed actuel : {current:.1f}")
                print(f"  → Régimes : {len(regimes)} | Inflexions : {len(inflections)}")
            R["fear_greed"] = fear_greed
            R["regimes"]    = regimes
            R["beh_stats"]  = beh_stats
        except Exception as e:
            _err(e, "Comportemental")
            R["fear_greed"] = fear_greed
        _ok(t0)
    else:
        R["fear_greed"] = _load("fear_greed", out) or pd.Series(dtype=float)

    # ── PHASE 5 — Smart Money ────────────────────────────
    if _run(5):
        _header("Smart Money — scoring membres", 5)
        t0 = time.time()
        try:
            from whatsapp_analysis.phase5_smart_money import run_smart_money_analysis
            member_scores, sm_list, calls = run_smart_money_analysis(df)
            _save(member_scores, "member_scores", out)
            _save(sm_list, "sm_list", out)
            if isinstance(member_scores, pd.DataFrame) and not member_scores.empty:
                member_scores.to_csv(out / "smart_money_ranking.csv")
                print(f"  → {len(member_scores)} membres scorés")
                sms_col = "smart_money_score" if "smart_money_score" in member_scores.columns else member_scores.columns[0]
                top3 = member_scores[sms_col].nlargest(3).to_dict()
                print(f"  → Top 3 SMS : {list(top3.items())}")
            R["member_scores"] = member_scores
            R["sm_list"]       = sm_list
        except Exception as e:
            _err(e, "Smart Money")
            R["member_scores"] = pd.DataFrame()
            R["sm_list"]       = []
        _ok(t0)
    else:
        R["member_scores"] = _load("member_scores", out) or pd.DataFrame()
        R["sm_list"]       = _load("sm_list", out) or []

    # ── PHASE 6 — Analyse réseau ─────────────────────────
    if _run(6):
        _header("Analyse réseau — graphe d'interactions", 6)
        t0 = time.time()
        try:
            from whatsapp_analysis.phase6_network import run_network_analysis
            G, node_metrics, communities, propagation_df = run_network_analysis(
                df, smart_money_list=R.get("sm_list", [])
            )
            _save(node_metrics, "node_metrics", out)
            _save(communities, "communities", out)
            node_metrics.to_csv(out / "network_metrics.csv")
            print(f"  → Nœuds : {G.number_of_nodes()} | Arêtes : {G.number_of_edges()}")
            print(f"  → Communautés : {len(set(communities.values())) if isinstance(communities, dict) else len(communities)}")
            R["node_metrics"] = node_metrics
            R["communities"]  = communities
            R["graph"]        = G
        except Exception as e:
            _err(e, "Réseau")
            R["node_metrics"] = pd.DataFrame()
            R["communities"]  = {}
        _ok(t0)
    else:
        R["node_metrics"] = _load("node_metrics", out) or pd.DataFrame()

    # ── PHASE 7 — Stock picking ──────────────────────────
    if _run(7):
        _header("Stock picking — scoring par valeur BVC", 7)
        t0 = time.time()
        try:
            from whatsapp_analysis.phase7_stocks import compute_stock_scores
            stock_scores = compute_stock_scores(df, R.get("member_scores", pd.DataFrame()))
            _save(stock_scores, "stock_scores", out)
            stock_scores.to_csv(out / "stock_scores.csv")
            print(f"  → {len(stock_scores)} valeurs analysées")
            if not stock_scores.empty:
                sm_col = "smart_sentiment" if "smart_sentiment" in stock_scores.columns else stock_scores.columns[0]
                top3 = stock_scores[sm_col].nlargest(3).index.tolist()
                print(f"  → Top 3 SM sentiment : {top3}")
            R["stock_scores"] = stock_scores
        except Exception as e:
            _err(e, "Stock Picking")
            R["stock_scores"] = pd.DataFrame()
        _ok(t0)
    else:
        R["stock_scores"] = _load("stock_scores", out) or pd.DataFrame()

    # ── PHASE 8 — Corrélations marché ────────────────────
    if _run(8):
        _header("Corrélations marché — lead-lag, Granger", 8)
        t0 = time.time()
        try:
            from whatsapp_analysis.phase8_correlations import run_phase8
            p8 = run_phase8(
                df,
                stock_scores=R.get("stock_scores"),
                member_scores=R.get("member_scores"),
                fear_greed_series=R.get("fear_greed"),
                graph_metrics=R.get("node_metrics"),
            )
            _save(p8, "phase8", out)
            lead = p8.get("lead_lag_results", {})
            if lead:
                print(f"  → Lead-lag calculé sur {len(lead)} tickers")
            R["phase8"] = p8
        except Exception as e:
            _err(e, "Corrélations")
            R["phase8"] = {}
        _ok(t0)
    else:
        R["phase8"] = _load("phase8", out) or {}

    # ── PHASE 9 — Machine Learning ───────────────────────
    if _run(9) and not skip_ml:
        _header("Machine Learning — modèles prédictifs", 9)
        t0 = time.time()
        try:
            from whatsapp_analysis.phase9_ml import run_phase9
            p9 = run_phase9(
                df,
                stock_scores=R.get("stock_scores"),
                member_scores=R.get("member_scores"),
                fear_greed_series=R.get("fear_greed"),
                graph_metrics=R.get("node_metrics"),
                phase8_results=R.get("phase8"),
            )
            _save(p9, "phase9", out)
            for mname, metrics in list(p9.get("model_results", {}).items())[:3]:
                auc = metrics.get("auc", "N/A")
                f1  = metrics.get("f1", "N/A")
                if isinstance(auc, float):
                    print(f"  → {mname}: AUC={auc:.3f} F1={f1:.3f}")
            R["phase9"] = p9
        except Exception as e:
            _err(e, "ML")
            R["phase9"] = {}
        _ok(t0)
    else:
        R["phase9"] = _load("phase9", out) or {}

    # ── PHASE 10 — Topic Modeling ────────────────────────
    if _run(10):
        _header("LLM & thèmes latents — LDA / topics", 10)
        t0 = time.time()
        try:
            from whatsapp_analysis.phase10_topics import run_phase10
            p10 = run_phase10(
                df,
                stock_scores=R.get("stock_scores"),
                phase8_results=R.get("phase8"),
            )
            _save(p10, "phase10", out)
            labels = p10.get("topic_labels", {})
            print(f"  → {len(labels)} topics identifiés")
            for tid, lbl in list(labels.items())[:5]:
                print(f"     Topic {tid}: {lbl}")
            R["phase10"] = p10
        except Exception as e:
            _err(e, "Topics")
            R["phase10"] = {}
        _ok(t0)
    else:
        R["phase10"] = _load("phase10", out) or {}

    # ── PHASE 11 — Backtesting ───────────────────────────
    if _run(11):
        _header("Backtesting quantitatif", 11)
        t0 = time.time()
        try:
            from whatsapp_analysis.phase11_backtest import run_phase11
            p11 = run_phase11(
                df,
                stock_scores=R.get("stock_scores"),
                member_scores=R.get("member_scores"),
                fear_greed_series=R.get("fear_greed"),
                graph_metrics=R.get("node_metrics"),
                phase8_results=R.get("phase8"),
            )
            _save(p11, "phase11", out)
            for strat, metrics in p11.get("strategy_metrics", {}).items():
                sharpe = metrics.get("sharpe", "N/A")
                ret    = metrics.get("total_return_pct", "N/A")
                if isinstance(sharpe, float):
                    print(f"  → {strat}: Return={ret:.1f}% Sharpe={sharpe:.2f}")
            R["phase11"] = p11
        except Exception as e:
            _err(e, "Backtesting")
            R["phase11"] = {}
        _ok(t0)
    else:
        R["phase11"] = _load("phase11", out) or {}

    # ── PHASE 12 — Tests statistiques ───────────────────
    if _run(12):
        _header("Tests statistiques — robustesse, p-values", 12)
        t0 = time.time()
        try:
            from whatsapp_analysis.phase12_stats import run_phase12
            p12 = run_phase12(
                df,
                stock_scores=R.get("stock_scores"),
                member_scores=R.get("member_scores"),
                fear_greed_series=R.get("fear_greed"),
                graph_metrics=R.get("node_metrics"),
                phase8_results=R.get("phase8"),
                phase9_results=R.get("phase9"),
                phase11_results=R.get("phase11"),
            )
            _save(p12, "phase12", out)
            warnings_n = len(p12.get("warnings", []))
            print(f"  → Tests statistiques complets | {warnings_n} avertissements")
            R["phase12"] = p12
        except Exception as e:
            _err(e, "Stats")
            R["phase12"] = {}
        _ok(t0)
    else:
        R["phase12"] = _load("phase12", out) or {}

    # ── PHASE 13 — Prédiction finale ─────────────────────
    if _run(13):
        _header("Moteur de prédiction final — score composite", 13)
        t0 = time.time()
        try:
            from whatsapp_analysis.phase13_prediction import run_phase13
            p13 = run_phase13(
                df,
                stock_scores=R.get("stock_scores"),
                member_scores=R.get("member_scores"),
                fear_greed_series=R.get("fear_greed"),
                graph_metrics=R.get("node_metrics"),
                phase8_results=R.get("phase8"),
                phase9_results=R.get("phase9"),
                phase12_results=R.get("phase12"),
            )
            _save(p13, "phase13", out)
            rankings = p13.get("final_rankings", pd.DataFrame())
            if not rankings.empty:
                rankings.to_csv(out / "final_rankings.csv")
                print(f"  → {len(rankings)} valeurs classées")
                top5 = rankings.head(5)
                for _, row in top5.iterrows():
                    ticker = row.name if hasattr(row, 'name') else row.get('ticker', '')
                    score  = row.get("composite_score", row.get("final_score", "N/A"))
                    signal = row.get("signal", "")
                    print(f"     {ticker}: {score:.1f} [{signal}]" if isinstance(score, float) else f"     {ticker}")
            R["phase13"] = p13
        except Exception as e:
            _err(e, "Prédiction")
            R["phase13"] = {}
        _ok(t0)
    else:
        R["phase13"] = _load("phase13", out) or {}

    # ── PHASE 14 — Rapport HTML ──────────────────────────
    if _run(14):
        _header("Rapport institutionnel HTML", 14)
        t0 = time.time()
        try:
            from whatsapp_analysis.phase14_report import run_phase14
            p14 = run_phase14(
                df,
                stock_scores=R.get("stock_scores"),
                member_scores=R.get("member_scores"),
                fear_greed_series=R.get("fear_greed"),
                graph_metrics=R.get("node_metrics"),
                phase8_results=R.get("phase8"),
                phase9_results=R.get("phase9"),
                phase10_results=R.get("phase10"),
                phase11_results=R.get("phase11"),
                phase12_results=R.get("phase12"),
                phase13_results=R.get("phase13"),
                output_dir=str(out),
            )
            report_path = p14.get("report_path", out / "rapport_bvc_whatsapp.html")
            if Path(report_path).exists():
                size_kb = Path(report_path).stat().st_size // 1024
                print(f"  → Rapport : {report_path} ({size_kb} Ko)")
            R["phase14"] = p14
        except Exception as e:
            _err(e, "Rapport")
            R["phase14"] = {}
        _ok(t0)

    # ── RÉSUMÉ FINAL ─────────────────────────────────────
    total = time.time() - t_global
    print(f"\n{'═'*60}")
    print(f"  PIPELINE TERMINÉ en {total:.0f}s ({total/60:.1f} min)")
    print(f"  Sorties : {out}/")
    if R.get("phase13"):
        rankings = R["phase13"].get("final_rankings", pd.DataFrame())
        if not rankings.empty and "composite_score" in rankings.columns:
            top5 = rankings["composite_score"].nlargest(5)
            print(f"  TOP 5 : {top5.index.tolist()}")
    print(f"{'═'*60}\n")

    return R


# ─────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────

def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="BVC WhatsApp Analysis Pipeline — 14 phases",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemples :
  # Pipeline complet
  python -m whatsapp_analysis.pipeline --input data/_chat.txt

  # Phases 1-3 seulement (rapide, pour tester)
  python -m whatsapp_analysis.pipeline --input data/_chat.txt --phases 1,2,3

  # Mode rapide (10%% du corpus)
  python -m whatsapp_analysis.pipeline --input data/_chat.txt --fast

  # Sans ML (plus rapide)
  python -m whatsapp_analysis.pipeline --input data/_chat.txt --skip-ml

  # Reprendre depuis la phase 7 (utilise caches 1-6)
  python -m whatsapp_analysis.pipeline --input data/_chat.txt --phases 7,8,9,10,11,12,13,14
        """
    )
    parser.add_argument("--input",    "-i", default="data/_chat.txt")
    parser.add_argument("--output",   "-o", default="whatsapp_analysis/output")
    parser.add_argument("--phases",   "-p", default=None,
                        help="Ex: 1,2,3 (défaut: toutes)")
    parser.add_argument("--skip-ml",  action="store_true")
    parser.add_argument("--fast",     action="store_true",
                        help="Sous-échantillonner 10%% pour test rapide")
    parser.add_argument("--no-resume", action="store_true",
                        help="Ignorer les caches (repart de zéro)")
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()

    phases_list = None
    if args.phases:
        phases_list = [int(p.strip()) for p in args.phases.split(",")]

    input_path = Path(args.input)
    if not input_path.is_absolute():
        input_path = REPO_ROOT / input_path

    if not input_path.exists():
        print(f"ERREUR : fichier introuvable : {input_path}", file=sys.stderr)
        sys.exit(1)

    output_path = Path(args.output)
    if not output_path.is_absolute():
        output_path = REPO_ROOT / output_path

    run_pipeline(
        input_file  = str(input_path),
        output_dir  = str(output_path),
        phases      = phases_list,
        skip_ml     = args.skip_ml,
        fast        = args.fast,
        resume      = not args.no_resume,
    )
