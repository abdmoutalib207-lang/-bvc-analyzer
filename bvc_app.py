import streamlit as st
import requests, os
from pathlib import Path

st.set_page_config(page_title="BVC Analyzer v5.2.1", page_icon="📈", layout="wide")
REPO = "https://raw.githubusercontent.com/abdmoutalib207-lang/-bvc-analyzer/main"

st.title("📈 BVC ANALYZER v5.2.1")
st.caption("Technique + Fondamental + NLP | Groupe MASI 1")

col1, col2, col3 = st.columns(3)
col1.metric("Titres suivis", "17")
col2.metric("Historique", "492 séances")
col3.metric("Corpus NLP", "896 907 msgs")

if st.button("🚀 Lancer l analyse", type="primary", use_container_width=True):
    with st.spinner("Analyse en cours..."):
        try:
            token = st.secrets.get("GITHUB_TOKEN", "")
            headers = {"Authorization": f"token {token}"} if token else {}
            r = requests.get(
                f"https://raw.githubusercontent.com/abdmoutalib207-lang/-bvc-analyzer/main/fondamentaux.json",
                headers=headers)
            Path("/tmp/fondamentaux.json").write_text(r.text)
            os.chdir("/tmp")
            code = requests.get(
                f"https://raw.githubusercontent.com/abdmoutalib207-lang/-bvc-analyzer/main/bvc_analyzer_v50.py",
                headers=headers).text
            exec(code, globals())
            results, backtests, fond, scores = BVCAnalyzer().run_full_analysis(backtest=False)
            st.success("✅ Analyse terminée")
            import pandas as pd
            rows = []
            for ticker, r in results.items():
                rows.append({
                    "Ticker": ticker,
                    "Prix DH": r.current_price,
                    "Signal": r.signal,
                    "Score": round(r.score_global, 2),
                    "Tech": round(r.score_technical, 2),
                    "Fond": round(r.score_fundamental, 2),
                    "Setup": r.setup,
                    "Flags": len(r.red_flags or []),
                })
            df = pd.DataFrame(rows).sort_values("Score", ascending=False)
            st.subheader("🏆 Classement Global")
            st.dataframe(df, use_container_width=True, hide_index=True,
                column_config={"Score": st.column_config.ProgressColumn(min_value=0, max_value=10)})
        except Exception as e:
            st.error(f"Erreur: {e}")
