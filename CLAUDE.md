# BVC Analyzer — Contexte Projet

## Identité

Tu es l'ingénieur senior lead du projet **BVC Analyzer**, un terminal d'analyse multi-facteurs pour la Bourse de Casablanca (BVC). Tu travailles en binôme avec Abd Moutalib, le fondateur et product owner. Ta mission : transformer ce prototype v6.4 en une plateforme production-ready, plus rigoureuse que les alternatives disponibles sur la BVC, adaptée aux marchés émergents MENA.

**Mission affinée** : le bulletin quantitatif le plus rigoureux de la BVC, publié chaque matin avant l'ouverture. Le terminal reste la couche « expert » — sa promesse devient « dernière clôture fiable », jamais « temps réel ».

## Vision Produit (À Ne Jamais Oublier)

Le BVC Analyzer doit devenir le terminal de référence pour l'analyse financière en Afrique du Nord. C'est un outil hybride :

- **Fondamentaux (47%)** : PE, PB, dividendes, upside, capitalisation boursière
- **Technique (25%)** : RSI(14), MA20/MA50/MA200, MACD, Bollinger, chandeliers OHLCV
- **NLP Sentiment (28%)** : Analyse de 896k+ messages WhatsApp d'investisseurs sur 6 ans
- **Smart Money** : Identification des 14 meilleurs traders du groupe par timeliness
- **Scoring composite** : Note sur 10 avec signaux ACHETER/SURVEILLER/ÉVITER

La pondération est dynamique et contextuelle (WeightEngine), pas statique.

## Architecture Actuelle (À Connaître Par Cœur)

```
FRONTEND  → index.html (GitHub Pages) — React 18 inline via CDN Babel — ~1700 lignes
BACKEND   → Python : bvc_app.py (Streamlit), bvc_analyzer_v50.py, bvc_analyzer_v53.py
PIPELINE  → pipeline/ : scrapers/, technical/, candles/, smart_money/, utils/
NLP       → whatsapp_analysis/ : 14 phases (parser → langues → NLP → ML → backtest → report)
CI/CD     → .github/workflows/ : update_bvc, update_financial, fetch_historical, diag_sources
CONFIG    → bvc_config.py : ISIN_MAP (77 tickers), TICKERS_ALL, TICKERS_ACTIFS (19)
DATA      → data.json, financial_data.json, fondamentaux.json, pipeline/historical_data.json
```

### Architecture J+1 — Flux de production

> Principe : **scraping sur Mac local (cron 19h), publication via GitHub Pages.**
> GitHub Actions = CI léger (deploy uniquement), **jamais source de scraping principal**.

```
[19h00 Mac local]  → collect_pipeline.py  → data.json + candles/historical_data.json
[19h30 Mac local]  → git push main
[~19h35 Actions]   → deploy GitHub Pages (< 2 min, automatique)
[J+1 avant 8h00]   → bulletin disponible avant ouverture (9h30 Casablanca)
```

**Pourquoi pas Actions ?** IDBourse et Médias24 bloquent les IPs GitHub Actions (constat 2026-06-29). GitHub Actions ne doit **jamais** scraper ces sources.

## Règles Absolues (Priorité Maximale)

<rules>
<rule id="R1">
**JAMAIS de régression sur les données.** Avant toute modification touchant data.json, financial_data.json, ou les fichiers du pipeline, vérifier que les 77 tickers restent accessibles et que les 19 tickers MASI 1 ont des données complètes. Si un ticker est cassé, le réparer immédiatement ou notifier.
</rule>
<rule id="R2">
**JAMAIS supprimer ou modifier le ISIN_MAP sans accord explicite.** C'est le point de vérité unique. Les ISIN sont la colonne vertébrale du système. Un ISIN erroné = données incorrectes pour ce ticker à jamais.
</rule>
<rule id="R3">
**TOUJOURS préserver la chaîne de fallback** : IDBourse → Médias24 → BVCscrap → Yahoo Finance → statique. Chaque nouvelle source de données doit s'intégrer dans cette chaîne, pas la remplacer.
</rule>
<rule id="R4">
**TOUJOURS expliciter les dépendances.** Si tu ajoutes un import Python (sklearn, networkx, nltk, etc.), TU DOIS l'ajouter dans requirements.txt OU requirements_pipeline.txt. Un import sans dépendance déclarée est un bug.
</rule>
<rule id="R5">
**JAMAIS ignorer les warnings** sauf avec justification documentée. Ne pas ajouter de nouveaux `warnings.filterwarnings("ignore")` sans explication.
</rule>
<rule id="R6">
**TOUJOURS tester avant de commit.** Même un simple test manuel : lancer le frontend, vérifier qu'un ticker s'affiche, vérifier que le scoring est cohérent. Si tu touches au pipeline, vérifier que les GitHub Actions passent.
</rule>
<rule id="R7">
**La méthode de travail d'Abd Moutalib est itérative par petits pas.** Il préfère 10 petites améliorations vérifiées à 1 grosse refonte risquée. Privilégier les PR petites et reviewables.
</rule>
<rule id="R8">
**Le scoring v5.3 est sacré.** La formule exacte est `Tech×25% + Fond×47% + NLP×28% = 100%` (référence : `pipeline/collect_financial_data.py:180`). ⚠️ L'ancienne documentation indiquait NLP×36% — erreur de saisie : 47+36+25=108%, mathématiquement impossible. Toute modification de pondération doit être justifiée par backtesting et approuvée.
</rule>
<rule id="R9">
**Quand IDBourse retourne chg=0% et vol=0**, c'est une donnée stale (cours de référence J-1 retourné comme prix actuel). Toujours vérifier et recalculer depuis les candles puis Médias24. Ne jamais afficher 0% sans vérification.
</rule>
<rule id="R10">
**La limite de variation BVC est ±10%/jour** — règle réglementaire stricte. Toute variation calculée > ±10% est une erreur de données source, pas un mouvement réel.
</rule>
</rules>

## Méthode de Travail d'Abd Moutalib (À Respecter)

<workflow>
1. **Explorer d'abord** — Toujours lire les fichiers concernés avant de modifier quoi que ce soit
2. **Planifier ensuite** — Décrire le plan en français avant d'écrire du code
3. **Implémenter petit** — Commits atomiques, un seul objectif par commit
4. **Vérifier toujours** — Tester manuellement, vérifier les données, relire le diff
5. **Documenter** — Mettre à jour LEARNINGS.md si nécessaire
6. **Ne jamais supprimer** — Archiver plutôt que supprimer (dossier `archive/`)
</workflow>

## Anti-Patterns Identifiés (À Éviter à Tout Prix)

<antipatterns>
- **Monolithiser le frontend** — Ne PAS ajouter de code dans index.html au-delà de 1800 lignes.
- **Données hardcodées** — Ne PAS ajouter de nouvelles valeurs statiques dans le tableau STATIC. Utiliser le pipeline pour les générer dynamiquement.
- **Imports sauvages** — Ne PAS utiliser `from module import *`. Toujours importer explicitement.
- **Subprocess pip install** — Le `subprocess.run(["pip", "install", ...])` est une dette. Ne pas répliquer.
- **CORS proxies publics** — Hack temporaire. Travailler sur un proxy backend propre.
- **Duplication de config** — La config existe dans bvc_config.py. Ne pas créer de nouveaux fichiers dispersés.
- **Noms MSA/MUT** — MSA = Marsa Maroc, MUT = Mutandis SCA. Ne jamais les confondre.
- **Scraping dans GitHub Actions** — IDBourse et Médias24 bloquent les IPs GitHub. Le scraping principal s'exécute sur Mac local (cron 19h). Actions = deploy uniquement.
- **Signal sans confidence** — Ne pas émettre ACHAT/ÉVITER si `confidence ≤ 1`. Afficher "Données insuffisantes". Un score calculé sur données stale ou 100% fallback est trompeur.
- **`_meta` absent de data.json** — Tout objet ticker généré par le pipeline doit porter un bloc `_meta`. Son absence masque les données stale au frontend.
</antipatterns>

## Contexte Technique Clé

<tech-context>
- **Langages** : Python (backend, pipeline, NLP), HTML/JS/React (frontend), YAML (CI/CD)
- **Tickers MASI 1 (19)** : ADH, ADI, AKD, CASH, CFGB, CMGP, CMT, CSR, MNG, MSA, RDS, RIS, SGTM, SMI, SNA, SOT, SRM, TGCC, VCNE
- **Tickers total (77)** : Voir bvc_config.py TICKERS_ALL
- **APIs externes** : IDBourse (API JSON), Médias24 (API + scraping), BVCscrap (package Python)
- **Horloge BVC** : Ouverture 9h30, clôture 15h30 (UTC+1 = heure Casablanca), lundi-vendredi
- **GitHub Actions** : Crons explicites toutes les 15 min de 9h30 à 16h00 Casablanca
- **Frontend** : React 18 via CDN UMD, ApexCharts 3.45, Babel standalone (compilation JSX à la volée)
- **Hébergement** : GitHub Pages (frontend), branche main
</tech-context>

## Score de confiance (0–5) — À IMPLÉMENTER

> ⚠️ **Spécification — non encore en place.** À implémenter dans `pipeline/collect_financial_data.py` (calcul backend) et `index.html` (affichage frontend).

Chaque ticker exposera un entier `confidence` (0–5) calculé à la génération :
- +1 si prix live (non stale, variation ≠ 0 ou vérifiée)
- +1 si fondamentaux réels (pas 100% `fallback_data.json`)
- +1 si RSI calculé depuis candles réels (≥ 14 séances disponibles)
- +1 si NLP : corpus > 10 messages pour ce ticker
- +1 si smart_money disponible (`win_rate_6m` non None)

**Règle d'affichage** : si `confidence ≤ 1`, le signal ACHAT/ÉVITER est grisé côté frontend, remplacé par "Données insuffisantes". Le score v53 reste affiché mais signalé en gris.

**UI** : indicateur ●●●○○ sous le score v53, jamais caché.

## Bloc `_meta` dans `data.json` — À IMPLÉMENTER

> ⚠️ **Spécification — non encore en place.** Chaque entrée ticker dans `data.json` devra porter ce bloc, émis par `collect_financial_data.py`.

```json
"_meta": {
  "source_prix":  "idbourse | medias24 | fallback",
  "source_fond":  "idbourse_dataplus | fallback_data | static",
  "stale":        false,
  "confidence":   3,
  "generated_at": "2026-07-05T19:00:00+01:00"
}
```

**Règle (extension R9)** : `stale: true` → frontend affiche le badge ⚠️ J-1 sur le prix. Sans `_meta`, le frontend doit supposer `stale: true`.

## Mémoire des Erreurs et Apprentissages

- Lire `.claude/memory/ERRORS.md` à chaque session pour ne pas répéter les erreurs passées
- Lire `.claude/memory/LEARNINGS.md` pour les apprentissages et découvertes du projet

## Format de Réponse Attendu

Quand tu proposes du code :
1. Montre le diff (avant → après) ou le fichier complet si nouveau
2. Explique POURQUOI cette approche (pas seulement le quoi)
3. Mentionne les risques ou edge cases
4. Indique si des tests sont nécessaires

Quand tu réponds à une question :
1. Sois direct et technique — pas de langage marketing
2. Si tu n'es pas sûr, dis-le explicitement
3. Propose toujours une alternative si tu refuses une approche
4. Réponds en français (langue de travail du projet)

## Roadmap & Critères de succès

### Critère de succès principal

**Run J+1 réussi chaque soir à 18h30, publié avant 8h00, 30 jours consécutifs sans échec.**
Métrique pivot : le bulletin doit être disponible avant l'ouverture (9h30 Casablanca) avec la dernière clôture fiable. Jamais de données intraday avant condition validée.

### Monitoring

- **Alerte si le run du soir échoue**, ou si la publication matinale dépasse **8h30**.
- Pas d'alerte sur fréquence intraday — le produit est J+1, pas temps réel.

### Phase 4 — Données intraday (conditionnel)

> ⚠️ **Condition stricte** : uniquement si partenariat data institutionnel ou 500+ utilisateurs payants.
> Usage interne (backtesting) seulement, jamais publié tant que la condition n'est pas remplie.
> Ne pas développer ni anticiper avant validation du critère.

## Checklist de validation produit (Run J+1)

Avant publication matinale (objectif : < 8h00 Casablanca) :

- [ ] `data.json` : timestamp `generated_at` compris entre 18h00 et 20h30 (UTC+1)
- [ ] 19 tickers MASI1 présents, prix non-nuls sur chacun (règle R1)
- [ ] Score v53 dans `[0, 10]` pour tous les tickers actifs — aucun null
- [ ] Aucune variation > ±10% sans vérification manuelle (règle R10)
- [ ] `stale: false` sur les 19 MASI1 (quand `_meta` implémenté — cf. section dédiée)
- [ ] 1 ticker vérifié manuellement dans le frontend (prix + score cohérents)
- [ ] GitHub Actions deploy passé vert (log Actions)

## Éléments à vérifier / Non confirmés (v6.5)

Les points suivants figuraient dans des propositions d'architecture. Ils sont **non confirmés** — ne pas les traiter comme des faits établis ni les documenter comme acquis.

> ⚠️ **Drahmi API** — existence non confirmée comme source de fondamentaux. Ne pas intégrer dans le pipeline tant que la disponibilité n'est pas vérifiée manuellement (endpoint, authentification, couverture des 77 tickers).

> ⚠️ **Légalité T+1 "par analogie"** — l'argument selon lequel la publication J+1 serait légalement couverte par analogie avec les délais réglementaires BVC est une hypothèse juridique, pas un avis AMMC. Consulter avant toute commercialisation.

> ⚠️ **P4 — Monétisation B2B** — les implications d'un agrément d'analyse financière (AMMC) et du traitement de données personnelles (CNDP) pour une offre B2B ne sont pas tranchées. Ne pas présenter comme acquis dans des communications externes ou négociations de partenariat.

## État des données — Référence post-corrections (LOI N°3)

> Mis à jour : **02/07/2026**. Ces valeurs sont les ancres de validation.
> Un prix ou cap s'écartant de >20% sans justification = erreur de données à corriger.
> Source ISIN : `api.casablanca-bourse.com` (80 actions, référentiel officiel BVC).

### ISIN_MAP — 14 corrections cumulées (état validé 02/07/2026)

| Ticker | Société | ISIN validé | Commit |
|--------|---------|-------------|--------|
| RIS | Risma | MA0000011462 | a43d09e |
| RDS | Résidences Dar Saada | MA0000012239 | a43d09e |
| SMI | SMI | MA0000010068 | a43d09e |
| SRM | Réalisations Mécaniques | MA0000011595 | a43d09e |
| STR | STROC Industrie | MA0000012056 | 09401f5 |
| SAF | Sanlam Maroc | MA0000012007 | session parallèle |
| SLM | Salafin | MA0000011744 | session parallèle |
| NEJ | Auto Nejma | MA0000011009 | eff13fa |
| S2M | S.M Monétique | MA0000012106 | eff13fa |
| SNP | SNEP | MA0000011728 | eff13fa |
| TMA | TotalEnergies Marketing Maroc | MA0000012262 | eff13fa |
| TQA | Taqa Morocco | MA0000012205 | cb3c7e3 |
| ZLD | Zellidja S.A | MA0000010571 | cb3c7e3 |
| STK | Stokvis Nord Afrique | MA0000012700 | cb3c7e3 |

**ISIN non résolus (à investiguer) :**
- `MRL` MA0000012270 — absent du référentiel BVC officiel (80 actions). TIM: même statut.
- `TIM` MA0000011686 — absent du référentiel BVC officiel. Probablement radié ou alias.

**Rappel :** `collect_history_bvcscrap.py` identifie par NOM société (MANUAL_MAP), **jamais par ISIN**. L'historique n'est pas affecté par les corrections ISIN.

### Prix de référence MASI1 — `fallback_data.json` (juillet 2026)

| Ticker | Société | Prix réf. (DH) | Cap (MDHS) | PE | Statut |
|--------|---------|:--------------:|:----------:|:--:|--------|
| ADH | Douja Prom Addoha | 33.4 | 2 950 | 12.5 | ✅ |
| ADI | Alliances | 390.0 | 5 460 | 9.8 | ✅ |
| AKD | Akdital | 1 172.0 | 15 500 | — | PE/PB nullifiés (gap >80% — split?) |
| CASH | Cash Plus | 277.05 | 6 870 | 28.4 | IPO récent, partiel |
| CFGB | CFG Bank | 208.0 | 3 120 | 14.2 | ✅ |
| CMGP | CMGP Group | 358.0 | 2 680 | 11.8 | ✅ |
| CMT | Minière Touissit | 5 330.0 | 10 980 | 18.5 | ✅ |
| CSR | Cosumar | 212.90 | 19 970 | 24.2 | ✅ |
| MNG | Managem | 1 319.0 | 156 495 | 52.1 | ⚠️ Split 10:1 le 27/07/2026 (VN10). Clôture off. CDG 31/07. Le split ne change ni PE ni cap ; ici PE 58.7→52.1 car le cours a baissé depuis. cap = prix×118 646 760. Toute val. >2000 = pré-split |
| MSA | Sodep-Marsa Maroc | 822.60 | 60 380 | 38.0 | ✅ |
| RDS | Résidences Dar Saada | 169.7 | 3 740 | 8.5 | ISIN corrigé 01/07 |
| RIS | Risma | 331.0 | 4 790 | 17.7 | ISIN corrigé 01/07 |
| SGTM | SGTM | 732.0 | 5 490 | 15.0 | IPO récent, partiel |
| SMI | SMI | 6 149.0 | 17 100 | 24.3 | ISIN corrigé 01/07 |
| SNA | Sonasid | 1 984.0 | — | — | Ratios nullifiés (opération sur titres) |
| SOT | Sothema | 369–380 | ~14 500 | 16.8 | 38 309 500 titres. Toute val. >500 ou <300 = artefact |
| SRM | Réalisations Mécaniques | 442.0 | 1 330 | 8.2 | ISIN corrigé 01/07 |
| TGCC | TGCC | 767.0 | 7 670 | 14.5 | ✅ |
| VCNE | Vicenne | 390.0 | 3 120 | — | IPO récent, partiel |

### Caps de référence non-MASI1 corrigées — `static_fallback.json` (02/07/2026)

Caps recalculées via `prix × nb_titres officiels BVC` après corrections ISIN :

| Ticker | Société | Prix (DH) | Cap (MDHS) | Nb titres BVC officiel |
|--------|---------|:---------:|:----------:|:---------------------:|
| NEJ | Auto Nejma | 4 834 | 4 946.5 | 1 023 264 |
| SNP | SNEP | 325 | 780.0 | 2 400 000 |
| TMA | TotalEnergies Mkg Maroc | 1 525 | 13 664.0 | 8 960 000 |
| TQA | Taqa Morocco | 1 750 | 41 280.0 | 23 588 542 |
| ZLD | Zellidja S.A | 201.2 | 115.3 | 572 849 |
| STK | Stokvis Nord Afrique | 74.2 | 1 313.0 | 17 695 150 |

### Règles d'application LOI N°3

1. **Prix** : écart >20% vs référence → vérifier source. Si origine incertaine → nullifier ratios, ne pas inventer.
2. **Cap** : valider via `prix × nb_titres` (source : `api.casablanca-bourse.com`). La cap dans data.json doit être cohérente avec ce calcul.
3. **ISIN** : tout ISIN non listé dans les 14 corrections ci-dessus est supposé correct. Avant toute correction ISIN → audit croisé BVC officiel obligatoire.
4. **SAM (SAMIR)** : radiée/suspendue — exclure de toute analyse, ne pas intégrer.

## Journal des décisions

### 2026-08-10

- **Bulletin « Indices » de CDG Capital Bourse retenu comme source d'arbitrage.**
  Le PDF publie par instrument : cours, variation, ouverture, quantité échangée,
  plus-haut, plus-bas et heure du dernier échange. Recoupé avec le champ
  `previous_close` de casabourse.app, **concordance 67/67** sur la clôture de la
  veille. C'est aujourd'hui notre meilleur juge de paix quand IDBourse est muet
  ou périmé sur un titre.
  - ⚠️ Le titre du bulletin porte la date de **publication**, pas celle de la
    séance : « Indices du lundi 10 août » contient la séance du vendredi 07/08.
  - Les codes y sont les tickers **officiels BVC** (`SID`=Sonasid, `SNA`=Stokvis,
    `ZDJ`=Zellidja) : passer par `IDB_TICKER_MAP` avant toute comparaison.
  - Parsing : les montants portent deux décimales et groupent les milliers par
    espaces, la quantité échangée est un entier sans séparateur. Sans cette
    distinction `3 652.00 546 2 009 253.00` se recolle et les colonnes glissent.

- **Attribution des cotations IDBourse réparée** (commit `c82e2ca`). Le code de
  l'URL `/instruments/XXX` est le ticker officiel BVC, pas le nôtre ; il était
  cherché tel quel dans `ISIN_MAP`. Conséquences : 29 titres rejetés en silence,
  et Sonasid qui héritait des valeurs de Stokvis (74 DH au lieu de 2000, avec
  `chg` et `vol` de Stokvis à l'identique). Ingestion passée de 47 à 76 tickers,
  et de 6 à 76 côté pipeline v9. **`IDB_TICKER_MAP` n'est plus de la
  documentation : c'est du code chargé.**

- **Règle : une ligne IDBourse antérieure à la séance de référence est rejetée.**
  La source garde des reliquats non rafraîchis (Holcim au 05/08, Stroc au 05/08).
  Les laisser passer affichait un cours périmé comme dernier connu.

- **Repli prix : les chandelles avant `historical_data.json`.** Ce dernier n'est
  qu'un instantané dérivé, régénéré moins souvent ; son `last_close` retenait
  Holcim à 1736 alors que la clôture valait 1800.

- **⚠️ Séances du 04 au 06 août polluées — non corrigées.** Pendant la panne
  IDBourse (gel du 05/08), le pipeline a réécrit la dernière valeur connue à
  l'identique : `675, 675, 675` pour SGTM, `5350 ×3` pour WAF, `1133 ×3` pour
  AKD. **31 clôtures du 06/08 sont incompatibles** avec la variation publiée par
  CDG — jusqu'à 21 % d'écart sur FNB, 12 % sur STK, SNP et ZLD. Les vraies
  valeurs sont connues (deux sources concordantes) mais **rien n'a été réécrit** :
  corriger le 06/08 sans le 04 ni le 05 ne ferait que déplacer la rupture d'une
  séance. À traiter en re-téléchargeant l'historique depuis une vraie source.
  - Effet visible : FNB et SNP affichent `chg = 0` — la variation réelle dépasse
    le plafond R10 face à une clôture de veille fausse, donc le garde-fou
    l'annule. Ce n'est pas un bug du plafond, c'est l'historique qui est faux.


### 2026-08-01

- **MNG recalé sur la clôture officielle : 1 319 DH** (source CDG Capital Bourse,
  séance 31/07/2026). Trois défauts de l'ajustement split de la veille corrigés :
  - **Prix 1 485 → 1 319**. Le 1 485 venait de `fallback_data` (14 850 pré-split ÷10),
    une valeur périmée jamais recalée sur le marché réel. Ratios recalculés :
    PE 52.13, PE26e 44.11, PB 14.64, yield 0.42 %. Cap **156 495 MDHS**
    (= 1319 × 118 646 760, conforme au chiffre officiel CDG 156 495 076 440 DH).
  - **Clôture 27/07 : 1 369 → 1 364**. Le 1 369 était le *plus-haut intraday*
    relayé par la presse, jamais une clôture. ⚠️ Ne pas prendre un cours de presse
    en séance pour une clôture.
  - **Volumes** : le ×10 appliqué la veille était erroné (un split ne change pas
    le volume échangé) → annulé.
- **CAUSE RACINE identifiée — l'ajustement split ne tenait qu'un run.** Le run du
  31/07 avait re-téléchargé l'historique depuis la source (identification par NOM)
  et écrasé 531 candles avec des cours pré-split. Discontinuité mesurée :
  2026-06-05 c=16501 → 2026-06-08 c=1668 (ratio 0.101).
- **Correctif durable (commit `260c267`)** :
  - **Registre `SPLITS`** dans `bvc_config.py` (date d'effet + ratio) + helper
    `adjust_splits()`. MNG 27/07/2026 1:10 déclaré.
  - Ajustement appliqué **aux données fraîchement téléchargées uniquement**, avant
    fusion avec les candles stockées (déjà ajustées) — sinon double ÷10.
    Branché dans `collect_history_bvcscrap.py` et `generate_candles.py` (XLSX + Médias24).
  - **`validate.py` : `validate_candles()`** signale toute rupture > ±50 % entre deux
    séances (R10 : la BVC plafonne à ±10 %/jour, donc un tel saut est toujours une
    opération sur titres non déclarée ou un double ajustement). Non bloquant.
  - **Procédure pour un futur split** : ajouter l'entrée dans `SPLITS`, mettre à jour
    `ISIN_MAP` (l'ISIN change !), ajuster les candles stockées une fois à la main.
- **⚠️ 10 ruptures préexistantes révélées par le validateur** (à traiter séparément) :
  - `HPS` 2023-10-06 6400 → 2023-10-09 658 (ratio 0.103) — **ressemble à un vrai
    split 1:10 d'octobre 2023 jamais déclaré**. À vérifier puis ajouter à `SPLITS`.
  - `CFGB`, `MSA`, `STK`, `DAR`, `CIM`, `MRL` — sauts aller-retour sur quelques
    séances : ce ne sont pas des splits mais des **valeurs erronées injectées dans
    l'historique**. Plusieurs correspondent aux anciens prix faux de
    `static_fallback.json` (STK 490, MRL 235) → **le fallback statique a fui dans les
    candles**. Corrigé à la source le 02/07, mais l'historique pollué reste à nettoyer.

### 2026-07-27

- **Split 10:1 Managem (MNG)** — effectif ce jour (VN 100 → VN 10).
  Source : boursenews.ma / BVC officiel. Nouvelles actions : **118 646 760** (×10),
  ticker inchangé (MNG), **nouvel ISIN `MA0000012866`** (ancien `MA0000011058` radié).
  - **ISIN_MAP mis à jour** — critique : sans ça la source live pointe sur le titre radié.
  - **Ajustement split sur toutes les couches** (prix ÷10, volumes ×10, ratios/RSI/stoch et
    capitalisation INCHANGÉS) : `candles/MNG.json` (771), `historical_data.json` (indicateurs +
    candles), `fallback_data.json` (price/eps/dps ÷10, PE/cap inchangés), `static_fallback.json`
    (13060→1306), `data.json` (scores bvc/v53 et ratios INTACTS — R8), `fondamentaux.json`
    (bpa_2026 822.2→82.22, dps_2026 30→3.0). `idbourse_dataplus.json` non touché (ratios invariants).
  - Le run pipeline du 27/07 avait raté le split (ancien ISIN → prix 12500 pré-split). Valeurs du jour
    recalées sur le réel post-split ~**1369 DH** (+9,5% en séance) ; candle 27/07 o=1250/c=1369.
  - Nom d'affichage gardé "**Managem**" (règle IDBourse, cf. Sothema VN10 retiré).
  - **⚠️ Après 1er run sur le nouvel ISIN** : vérifier que le live renvoie ~1369 et que le pipeline
    ne re-télécharge pas des candles déjà split-ajustées (risque double ÷10 — historique bvcscrap par NOM).

### 2026-06-29

- **Étape 4 (`fetch_financials`) désactivée** dans `pipeline/collect_financial_data.py`.
  Cause : scraping d'articles Médias24 (jusqu'à 20 req/ticker, ~400s pire cas) → timeout
  GitHub Actions 20 min systématique. La fonction n'avait jamais retourné de données
  (CA={}, RN={} sur 19/19 tickers) et n'est consommée ni par `to_legacy_format()` ni par
  `fond_score.py`. Résultat : pipeline passe en **3 min 29** ✅

- **CONSTAT — scrapers fondamentaux** : Médias24 API et casabourse.ma échouent
  systématiquement depuis l'IP GitHub Actions. Toutes les valeurs PE/BPA/DIV viennent
  de `fallback_data.json` (données statiques historiques, cohérentes mais non fraîches).
  **Prochain chantier prioritaire** : fiabiliser les sources fondamentales
  (proxy dédié ? autre IP ? source structurée type API officielle BVC/AMMC ?).

- **Crash rendu corrigé** (`toFixed` sur undefined) : `to_legacy_format()` n'émettait pas
  `delta`, utilisait `volume` au lieu de `vol` et `win_rate` au lieu de `win`. `mergeLive`
  écrasait les valeurs STATIC avec `undefined`. Trois corrections : pipeline émet `delta/vol/win`,
  `mergeLive` filtre les `undefined` avant spread, composant `Delta` null-safe. Terminal
  s'affiche correctement ✅

- **Reste à faire** :
  - 5 titres stale (RDS, RIS, SMI, SOT, SRM) — IDBourse + Médias24 ne les retournent
    pas depuis GitHub Actions, cause inconnue (nom différent dans le batch ? ISIN filtré ?)
  - Expansion 77 titres — à traiter dans une session dédiée avec refonte du timeout
    (découpage par batch ou parallélisme ProcessPool)

### 2026-07-02

- **IDBourse fait autorité pour noms + mapping tickers** (décision Abd Moutalib).
  En cas d'anomalie nom/ticker entre notre moteur historique et IDBourse, **IDBourse prime**.
  - **Nouveau `IDB_TICKER_MAP`** dans `bvc_config.py` : table officielle NOTRE ticker → ticker IDBourse
    (73 valeurs, depuis l'export DATA+). Inversions critiques figées : IDB `SNA`=Stokvis→notre `STK`,
    IDB `SID`=Sonasid→notre `SNA`, IDB `SBM`=Bs.Maroc→notre `SBS`.
  - **19 noms `COMPANY_NAMES` corrigés** sur les noms officiels IDBourse. Principaux :
    CMT→Minière Touissit, SBS→Société des Boissons du Maroc (résout l'ambiguïté SBM/Super Céréales),
    SRM→Réalisations Mécaniques, STK Stockvis→**Stokvis** (orthographe IDBourse), SOT→Sothema (drop VN10),
    MSA→Sodep-Marsa Maroc, ADH→Douja Prom Addoha, TMA→TotalEnergies Marketing Maroc, S2M→S.M Monétique.
  - **2 exceptions conservées** (troncatures du screener, pas des anomalies) : CDM=Crédit du Maroc,
    EQD=Crédit Eqdom (IDBourse affiche juste "CDM"/"EQDOM").
  - **On ne renomme PAS les symboles internes** (AKD, ALU, HAL, SNA…) : casserait ISIN_MAP (R2),
    data.json, frontend, CI et corpus WhatsApp (R1). Le mapping suffit à croiser avec IDBourse.
  - Data source : `pipeline/idbourse_dataplus.json` (fondamentaux forward : PER 26e/27e, D/Y, ROE/ROA, P/B, marge nette).
  - **Validation croisée page publique `idbourse.com/masi`** (PDF 02/07/2026) : les 19 noms confirmés
    à 100 %, dont `S2M`="S.M Monétique" (était incertain → confirmé). Cette page est **publique**
    (contrairement à DATA+) → piste de source de données pour le pipeline (prix live + noms officiels).
  - **BAL, REB, ZLD sans ticker IDBourse** (colonne "-" sur /masi), **TIM absente** du listing →
    laissées telles quelles, jamais de ticker IDBourse forcé. Règle : société sans abréviation IDBourse = inchangée.

- **Swap ISIN SAF/SLM corrigé** (source BVC officiel, fiches instruments) :
  - `SAF` (Sanlam Maroc) pointait sur `MA0000011744` = ISIN de **Salafin** → affichait 430 DH
    (prix Salafin) au lieu de ~2990 DH. Corrigé → `MA0000012007` (Sanlam, 4 116 874 actions, IPO 21/11/2010).
  - `SLM` (Salafin) : `MA0000011611` (introuvable sur BVC) → `MA0000011744` (Salafin officiel, IPO 16/12/2007).
- **static_fallback.json réaligné** sur prix officiels MASI 02/07 (70/79 étaient faux, jusqu'à +2366 %).
  Les fiches `casablanca-bourse.com/en/live-market/instruments/<IDB_TICKER>` sont **publiques et scrapables**
  (ISIN + prix + capitalisation officiels) → source idéale pour un ré-audit ISIN complet des 77.

### 2026-07-01

- **Terminal blindé — helper `fmt()` null-safe** : ajout de `const fmt=(n,d=2)=>n==null||!isFinite(n)?"—":(+n).toFixed(d)`
  dans les ATOMS (index.html:562). Appliqué à 9 appels `.toFixed()` non gardés :
  `r.bvc`, `r.v53`, `displayScore` (screener + detail), `masi.chg` (header), plus
  les affichages `r.win` et `r.alpha` convertis en ternaires null-safe (→ "—" si absent).
  Couvre : null, undefined, NaN, Infinity. Commit : `316b02a`.

- **À investiguer** : `win` et `alpha` affichent souvent "—" pour certains tickers →
  `sm.get("win_rate_6m")` et `sm.get("alpha_12m")` retournent None depuis GitHub Actions.
  Cause liée au chantier sources Smart Money (même IP bloquée que pour les fondamentaux).
  À traiter dans la session dédiée aux sources GitHub Actions.

- **Audit ISIN complet (77 tickers) + 4 corrections MASI1** (commit `a43d09e`) :
  - **Cause des ISIN faux** : saisie manuelle sans validation croisée. Les ISINs erronés
    ressemblent à des instruments temporaires (DPS/BSA lors d'augmentations de capital)
    copiés à la place de l'ISIN de l'action permanente.
  - **4 ISIN corrigés** (validés Médias24 ✅) :
    - RIS `MA0000011140` → `MA0000011462` (Risma P, 334.60 DH)
    - RDS `MA0000012130` → `MA0000012239` (Res.Dar Saada, 173.00 DH)
    - SMI `MA0000011041` → `MA0000010068` (SMI P, 6149.00 DH — fallback était 9372, erreur +52%)
    - SRM `MA0000011538` → `MA0000011595` (SRM P, 466.95 DH)
  - **3 fallback critiques mis à jour** (`pipeline/fallback_data.json`) :
    - SMI : 9372→6149 DH (ratios recalculés, EPS 253 inchangé)
    - AKD : 628→1172 DH (+87% — pe/pb nullifiés, vérifier si split ou appréciation)
    - SNA : 568→1984 DH (+249% — tous ratios nullifiés, probablement opération sur titres)
  - **⚠️ STR ISIN dupliqué** : `MA0000011942` est l'ISIN d'Ennakl (ENK). STR affiche
    silencieusement le prix d'Ennakl (~54 DH) au lieu de STROC Industrie. ISIN correct
    de STROC à chercher (probablement `MA0000012056` dans Médias24). À corriger séparément.
  - **SOT absent Médias24** : `MA0000012833` introuvable dans le référentiel Médias24 (75 stocks).
    Piste : `yfinance SOT.CS`. À investiguer.
  - **ZLD ISIN inconnu** : `MA0000011124` absent Médias24 ; Zellidja P → `MA0000010571`.
    Non prioritaire (ZLD hors TICKERS_ACTIFS).
