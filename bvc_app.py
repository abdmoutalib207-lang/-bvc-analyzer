import importlib.util
import json as _json
import shutil
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

st.set_page_config(
    page_title="BVC Analyzer v5.0",
    page_icon="📈",
    layout="wide",
)

# ── HEADER ────────────────────────────────────────────────────────────────────

st.markdown("""
<h1 style='margin-bottom:0'>📈 BVC ANALYZER v5.0</h1>
<p style='color:gray;margin-top:4px'>Technique × Fondamental × NLP — Bourse de Casablanca</p>
""", unsafe_allow_html=True)

_meta_path = Path(__file__).parent / "data.json"
_meta = {}
if _meta_path.exists():
    try:
        _meta = _json.loads(_meta_path.read_text())
    except Exception:
        pass

col1, col2, col3, col4 = st.columns(4)
col1.metric("Titres suivis",  str(_meta.get("n_tickers",  17)))
col2.metric("Historique",     str(_meta.get("n_sessions", "492")) + " séances")
col3.metric("Corpus NLP",     str(_meta.get("n_nlp_msgs", "896 907")) + " msgs")
col4.metric("Backtesting",    str(_meta.get("n_signals",  "1 994")) + " signaux")

st.divider()

# ── CONTRÔLES ─────────────────────────────────────────────────────────────────

with st.sidebar:
    st.header("⚙️ Paramètres")
    run_backtest = st.checkbox("Backtest (ATR stop)", value=False)
    tickers_input = st.text_area(
        "Tickers (un par ligne, vide = tous)",
        placeholder="CMT\nSMI\nMNG",
    )
    custom_tickers = [t.strip().upper() for t in tickers_input.splitlines() if t.strip()] or None
    run_btn = st.button("🚀 Lancer l'analyse", type="primary", use_container_width=True)


@st.cache_resource
def load_analyzer():
    """Charge le moteur BVC depuis les fichiers locaux du repo (Streamlit Cloud)."""
    repo_dir = Path(__file__).parent

    fond_src = repo_dir / "fondamentaux.json"
    if fond_src.exists():
        shutil.copy2(fond_src, Path("/tmp/fondamentaux.json"))

    spec = importlib.util.spec_from_file_location(
        "bvc_analyzer_v50",
        repo_dir / "bvc_analyzer_v50.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# ── ANALYSE ───────────────────────────────────────────────────────────────────

if run_btn:
    with st.spinner("Chargement du moteur…"):
        try:
            ns = load_analyzer()
        except Exception as e:
            st.error(f"Impossible de charger le moteur : {e}")
            st.stop()

    BVCAnalyzer = getattr(ns, "BVCAnalyzer", None)
    if BVCAnalyzer is None:
        st.error("Classe BVCAnalyzer introuvable.")
        st.stop()

    with st.spinner("Analyse en cours… (peut prendre 1-2 min)"):
        try:
            analyzer = BVCAnalyzer()
            results, backtests, fond, scores = analyzer.run_full_analysis(
                tickers=custom_tickers,
                backtest=run_backtest,
            )
        except Exception as e:
            st.error(f"Erreur durant l'analyse : {e}")
            st.stop()

    st.success(f"✅ {len(results)} titres analysés")

    # ── TABLE CLASSEMENT ──────────────────────────────────────────────────────

    rows = []
    for ticker, r in results.items():
        rows.append({
            "Ticker":      ticker,
            "Prix (DH)":   round(r.price, 2),
            "Signal":      r.signal.value,
            "Score /10":   round(r.score_global, 2),
            "Technique":   round(r.score_technical.normalized, 2),
            "Fondamental": round(r.score_fundamental.normalized, 2),
            "Setup":       r.setup.value,
            "Red Flags":   len(r.red_flags),
        })

    df = pd.DataFrame(rows).sort_values("Score /10", ascending=False).reset_index(drop=True)
    df.index += 1

    def style_signal(val):
        colors = {
            "ACHAT FORT": "background-color:#00e5a020;color:#00ffb3",
            "ACHETER":    "background-color:#00e5a010;color:#00e5a0",
            "SURVEILLER": "background-color:#ffd74010;color:#ffd740",
            "ATTENDRE":   "background-color:#88888810;color:#aaa",
            "EVITER":     "background-color:#ff8f0010;color:#ff8f00",
            "EVITER FORT":"background-color:#ff4f5a20;color:#ff4f5a",
        }
        return colors.get(val, "")

    st.subheader("🏆 Classement Global")
    st.dataframe(
        df.style.map(style_signal, subset=["Signal"]),
        use_container_width=True,
        column_config={
            "Score /10": st.column_config.ProgressColumn(
                min_value=0, max_value=10, format="%.2f"
            ),
            "Red Flags": st.column_config.NumberColumn(format="%d ⚠️"),
        },
    )

    # ── DÉTAIL TICKER ─────────────────────────────────────────────────────────
    st.subheader("🔍 Détail par ticker")
    sel = st.selectbox("Ticker", options=list(results.keys()))
    if sel:
        r = results[sel]
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Prix", f"{r.price:.2f} DH")
        c2.metric("Score global", f"{r.score_global:.2f}/10")
        c3.metric("Signal", r.signal.value)
        c4.metric("Setup", r.setup.value)

        c5, c6 = st.columns(2)
        with c5:
            st.markdown("**Score technique**")
            st.progress(r.score_technical.normalized / 10)
            st.caption(f"{r.score_technical.normalized:.2f}/10")
            for reason in r.score_technical.reasons[:6]:
                st.caption(f"  • {reason}")
        with c6:
            st.markdown("**Score fondamental**")
            st.progress(r.score_fundamental.normalized / 10)
            st.caption(f"{r.score_fundamental.normalized:.2f}/10")
            for reason in r.score_fundamental.reasons[:6]:
                st.caption(f"  • {reason}")

        if r.red_flags:
            st.markdown("**Red Flags**")
            sev_icon = {"CRITIQUE": "🔴", "ELEVEE": "🟠", "MOYENNE": "🟡", "FAIBLE": "🟢"}
            for flag in r.red_flags:
                icon = sev_icon.get(flag.severity.value, "⚪")
                st.warning(f"{icon} [{flag.severity.value}] {flag.category} — {flag.message}")

        if r.institutional_note:
            with st.expander("📄 Note institutionnelle complète"):
                st.text(r.institutional_note)

    # ── BACKTEST ──────────────────────────────────────────────────────────────
    if run_backtest and backtests:
        st.subheader("📊 Résultats Backtesting")
        bt_rows = []
        for ticker, bt in backtests.items():
            if isinstance(bt, dict) and bt.get("status") == "OK":
                bt_rows.append({
                    "Ticker":      ticker,
                    "Stratégie %": bt.get("strategy_return_%", "N/A"),
                    "Buy&Hold %":  bt.get("buyhold_return_%", "N/A"),
                    "Alpha %":     bt.get("alpha_%", "N/A"),
                    "Trades":      bt.get("trades", 0),
                    "Win Rate %":  bt.get("win_rate_%", "N/A"),
                })
        if bt_rows:
            st.dataframe(pd.DataFrame(bt_rows), use_container_width=True)
