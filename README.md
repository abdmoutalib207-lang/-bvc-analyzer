# BVC Ultimate Analyzer v4.0 PRO

Outil d'analyse de la Bourse de Valeurs de Casablanca (BVC) combinant indicateurs techniques et scoring fondamental.

## Fonctionnalités

- **Scoring technique** : RSI Wilder, MACD + accélération, Bollinger, Ichimoku, Stochastique, ATR, MA20/50/100/200, Volume Ratio
- **Scoring fondamental** : PER, Forward PER, croissance CA/BPA, ROIC/WACC, EVA, cash conversion, dette/EBITDA, dividende
- **Pondération dynamique** Tech/Fond selon liquidité BVC (5 tiers)
- **Décote liquidité** appliquée à la valorisation (0% à 20%)
- **Valorisation** : objectifs analyst JSON (bear/base/bull) avec décote, fallback multi-facteurs
- **Red Flags** : détection automatique avec sévérité (CRITIQUE/ÉLEVÉE/MOYENNE/FAIBLE)
- **Note institutionnelle** 8 sections : résultat, cash-flow, structure, EVA, catalyseurs, red flags, valorisation, technique
- **Données live BVC** : scraping temps réel casablanca-bourse.com
- **Export Excel** automatique sous Colab

## Utilisation sur Google Colab

```python
# Cellule 1 — Dépendances
!pip install openpyxl lxml html5lib -q

# Cellule 2 — Télécharger et lancer
!curl -sL "https://raw.githubusercontent.com/abdmoutalib207-lang/-bvc-analyzer/main/bvc_analyzer_v4.py" -o bvc_analyzer_v4.py
exec(open("bvc_analyzer_v4.py").read())
run_colab_analysis()
```

Uploader ensuite vos fichiers Excel BVC (format `.xlsx` ou `.xlsm`) quand la boîte de dialogue s'ouvre.

## Format fichier Excel BVC

Le lecteur détecte automatiquement les colonnes via mots-clés (cloture, haut, bas, volume).  
Colonnes par défaut si non détectées : Close=col 4, High=5, Low=6, Volume=7.  
Le ticker est lu en cellule C2, B2 ou A2.  
Minimum 30 séances requis.

## Fondamentaux

Les données fondamentales sont chargées depuis `fondamentaux.json` (ce dépôt, branche `main`).  
Tickers supportés : ADI, RDS, RIS, SMI, MNG, SOT, CSR, LHM.  
Pour ajouter un ticker, éditer `fondamentaux.json` en suivant la structure existante.

## Méthodologie

- WACC de référence BVC : Rf ~3% (Bons du Trésor 10Y) + ERP ~7% = ~10%
- Pont RN→FCF via cash conversion
- EVA = ROIC – WACC
- Méthodologie note institutionnelle : [LKABAL-BVC/claude-skill-annual-report-analyzer](https://github.com/LKABAL-BVC/claude-skill-annual-report-analyzer)

> ⚠️ Ne constitue pas un conseil en investissement ni une recommandation personnalisée (AMMC / réglementation BVC).
