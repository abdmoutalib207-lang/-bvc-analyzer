# BVC Analyzer v6.3

Terminal d'analyse multi-facteurs pour la Bourse de Casablanca — Technique 25% · Fondamental 47% · NLP 28%.

## Site live

**[https://abdmoutalib207-lang.github.io/-bvc-analyzer/](https://abdmoutalib207-lang.github.io/-bvc-analyzer/)**

## Fonctionnalités

- **19 titres MASI** suivis en temps réel
- **Scoring multi-facteurs** : Technique 25% · Fondamental 47% · NLP 28%
- **RSI(14) calculé** depuis l'historique réel (Wilder EMA — jamais scrapé)
- **Données live** : IDBourse → Médias24 → Yahoo Finance (fallback automatique)
- **Graphiques** : chandeliers OHLCV + Volume + MACD (3 panneaux synchronisés)
- **Smart Money** : corpus backtesté sur 896 907 messages · 6 ans · 1 994 signaux
- **Red Flags** : détection automatique avec sévérité (CRITIQUE/ÉLEVÉE/MOYENNE/FAIBLE)
- **Backtesting ATR** : stratégie stop-loss sur historique réel
- **Mise à jour automatique** : GitHub Actions 5×/jour aux horaires BVC (9h30–15h30)

## Architecture

```
index.html          — Frontend React standalone (GitHub Pages)
bvc_app.py          — Backend Streamlit (Streamlit Cloud)
bvc_analyzer_v50.py — Moteur de scoring v5.0 (production)
bvc_analyzer_v53.py — Enrichissement NLP v5.3
bvc_config.py       — Constantes partagées (ISIN_MAP, tickers)
update_data.py      — Script de mise à jour data.json
pipeline/           — Pipeline v9.0 collecte multi-sources
```

## Méthodologie

- **Pondération** : Fond 47% / NLP 28% / Tech 25% (WeightEngine contextuel)
- **RSI** : Wilder Smoothed Moving Average (TA-Lib ou pandas)
- **WACC BVC** : Rf ~3% (Bons du Trésor 10Y) + ERP ~7% = ~10%
- **EVA** = ROIC – WACC
- **NLP** : SENTIMENT_CORPUS backtesté sur 6 ans de messages groupe

## Tickers suivis

ADI · ADH · AKD · CASH · CFGB · CMGP · CMT · CSR · MNG · MSA · RDS · RIS · SGTM · SMI · SNA · SOT · SRM · TGCC · VCNE

---

> ⚠️ Ne constitue pas un conseil en investissement ni une recommandation personnalisée (AMMC / réglementation BVC).
