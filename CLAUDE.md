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

> Chiffres mesurés le 25/08/2026. Les remettre à jour lors d'une passe de
> documentation plutôt que de les laisser vieillir : le bloc annonçait encore
> « ~1700 lignes » pour un fichier qui en compte 2 547, et citait trois
> fichiers archivés depuis des mois.

```
FRONTEND  → index.html      2 547 lignes — React 18 + JSX compilé au navigateur
             radar.html       564 lignes — console de veille (JS sans framework)
             audience.html    154 lignes — fréquentation, non liée, non indexée
             ⚠️ Aucune étape de build : Babel compile le JSX à la volée. Pas de
             package.json, pas de node_modules. Le dépôt PARAÎT vanilla, il ne
             l'est pas.

MOTEUR    → update_data.py   ~1 700 lignes — propriétaire unique de data.json
             bvc_config.py                 — le référentiel (voir CONFIG)
             sync_sentiment.py
             ⚠️ bvc_app.py, bvc_analyzer_v50/v53.py sont dans archive/ depuis
             la phase A3 — ne plus les citer comme faisant partie du moteur.

PIPELINE  → pipeline/ : 15 modules, 4 753 lignes
             candles/ scrapers/ technical/ smart_money/ utils/

NLP       → whatsapp_analysis/ : 14 phases, 18 modules, 11 866 lignes
             (parser → langues → NLP → ML → backtest → report)
             ⚠️ Aucun workflow ne le déclenche : il tourne hors ligne et
             dépose ses résultats en CSV dans whatsapp_analysis/output/.

CI/CD     → .github/workflows/ : 9 workflows, 13 crons
             update_bvc · fetch_news · update_candles · fetch_historical_data
             update_financial_data · update_fondamentaux · verifier_seance
             validate_data · diag_sources
             92 % des commits du dépôt sont produits par ces automates.

CONFIG    → bvc_config.py : ISIN_MAP (83) · TICKERS_ALL (81) · TICKERS_ACTIFS (19)
             IDB_TICKER_MAP (78) · COMPANY_SECTORS (22 secteurs)
             JOURS_FERIES_FIXES · SPLITS · SIGLES_AMBIGUS

DATA      → data.json (81 titres) · news.json (~290 articles) · fondamentaux.json
             financial_data.json · pipeline/historical_data.json
             pipeline/candles/ : 74 fichiers, 32 260 séances
```

### Architecture J+1 — Flux de production

> Principe : **collecte depuis GitHub Actions, publication via GitHub Pages.**
> Quatre passages par jour ouvré, celui de 15h45 fixant le cours définitif.

```
[≈09h30 Actions]   → update_data.py → data.json + candles/   (le terminal ne
                                       reste pas figé sur la veille)
[≈12h00 Actions]   → update_data.py
[≈15h45 Actions]   → update_data.py → LE run qui compte : 15 min après la
                                       clôture de 15h30, il fixe le cours
[≈17h00 Actions]   → generate_candles.py
[≈18h00 Actions]   → update_data.py → filet de sécurité
[J+1 avant 8h00]   → bulletin disponible avant ouverture (9h30 Casablanca)
```

**⚠️ Le constat du 29/06 « IDBourse et Médias24 bloquent les IP GitHub Actions »
est PÉRIMÉ.** Mesuré le 18/08/2026 sur cinq runs consécutifs d'`update_bvc` :
**77 titres sur 81 servis directement par IDBourse, zéro repli statique**. La
collecte depuis Actions fonctionne.

Ce qui bloquait réellement le 05/08 n'était pas l'adresse IP mais un contrôle
de provenance : sans en-tête `Referer`, `/api/proxy/*` renvoie HTTP 403. Un
`curl` nu reçoit ce 403 depuis n'importe quelle machine, Mac marocain compris —
ce n'est donc pas un test de blocage d'IP. `idb_get()` envoie le Referer depuis
le 05/08 et l'accès est rétabli.

**Conséquence : le projet de migration vers le Mac local est abandonné.** Il
résolvait un problème qui n'existe plus. Ne pas le relancer sans avoir d'abord
constaté un vrai blocage — c'est-à-dire des runs Actions retombant en masse sur
`static` ou `data_json_precedent` dans `_meta.source_prix`.

**⚠️ Dépendance à surveiller, en revanche** : IDBourse a installé ce contrôle
délibérément, et 95 % de nos prix viennent d'une source qui cherche à filtrer
ses appelants. La fragilité est technique — ils peuvent resserrer du jour au
lendemain — et contractuelle si le produit devient payant. Le chantier
stratégique est un accès légitime (API officielle BVC, ou accord IDBourse dont
l'export DATA+ est déjà utilisé), pas une machine de collecte différente.

## Règles Absolues (Priorité Maximale)

<rules>
<rule id="R1">
**JAMAIS de régression sur les données.** Avant toute modification touchant data.json, financial_data.json, ou les fichiers du pipeline, vérifier que les **81** tickers restent accessibles et que les 19 tickers MASI 1 ont des données complètes. Si un ticker est cassé, le réparer immédiatement ou notifier.
</rule>
<rule id="R2">
**JAMAIS supprimer ou modifier le ISIN_MAP sans accord explicite.** C'est le point de vérité unique. Les ISIN sont la colonne vertébrale du système. Un ISIN erroné = données incorrectes pour ce ticker à jamais.
</rule>
<rule id="R3">
**TOUJOURS préserver la chaîne de fallback.** Ordre au 27/08/2026 :
**CDG Capital Bourse → IDBourse → chandelles → historique → statique.**
Chaque nouvelle source s'intègre dans la chaîne, elle ne la remplace pas, et
c'est la **date** qui arbitre ligne par ligne — jamais la préférence.

- **CDG en tête** depuis le 27/08 : société de bourse agréée, son univers est
  celui de la BVC (80/81 appariés), elle laisse les champs **vides** quand un
  titre n'a pas coté au lieu de rediffuser la veille, et elle fournit le
  chandelier complet plus les seuils ±10 %.
- **IDBourse reste indispensable** : elle est la SEULE à fournir la
  **capitalisation boursière**, absente des 26 champs de CDG.
- ⚠️ **Médias24 est HORS SERVICE** : HTTP 403 derrière Cloudflare (vérifié le
  27/08). Le CLAUDE.md la disait « non testée » — elle l'est, et elle échoue.
- ⚠️ **Wafabourse n'est pas exploitable** : API en 403 derrière un pare-feu
  applicatif. Utilisable seulement en PDF exporté à la main.
- ⚠️ **CDG et Wafabourse ne sont PAS indépendantes** : même éditeur
  (`nt-soft.ma`), même convention de champs, faute de frappe comprise
  (« CoursDeReferance »). Leur accord ne prouve pas l'exactitude. Le seul
  contrôle réellement extérieur reste le bulletin PDF de fin de journée.
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
- **Monolithiser le frontend** — Le plafond de 1 800 lignes pour index.html est
  **déjà franchi : 2 547 au 25/08**. Ce n'est donc plus une limite à respecter
  mais une dette constatée. Toute fonctionnalité substantielle devrait sortir
  du fichier plutôt que s'y ajouter ; à défaut, l'écart se creuse.
- **Données hardcodées** — Ne PAS ajouter de nouvelles valeurs statiques dans le tableau STATIC. Utiliser le pipeline pour les générer dynamiquement.
- **Imports sauvages** — Ne PAS utiliser `from module import *`. Toujours importer explicitement.
- **Subprocess pip install** — Le `subprocess.run(["pip", "install", ...])` est une dette. Ne pas répliquer.
- **CORS proxies publics** — Hack temporaire. Travailler sur un proxy backend propre.
- **Duplication de config** — La config existe dans bvc_config.py. Ne pas créer de nouveaux fichiers dispersés.
- **Noms MSA/MUT** — MSA = Marsa Maroc, MUT = Mutandis SCA. Ne jamais les confondre.
- **Boucle entre workflows** — Ne PAS faire se déclencher deux workflows l'un l'autre par `workflow_run`. `update_bvc` et `fetch_news` le faisaient : cycle de 3 à 5 min pendant toute la séance, 112 commits par jour pour un quota Pages d'environ 10 reconstructions par heure. Rompu le 18/08.
- **Multiplier les crons** — Le produit est J+1. Vingt-sept passages quotidiens ne servaient aucune promesse tenue. Quatre suffisent, et chaque commit consomme le quota de publication dont dépend le bulletin matinal.
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

## Score de confiance (0–5) — EN PLACE

> ✅ Implémenté le 10/08/2026 dans `update_data.py` (`_meta_ticker()`) et
> `index.html` (composant `Confiance`). ⚠️ `pipeline/collect_financial_data.py`
> ne l'émet pas encore : les deux pipelines écrivent `data.json`, celui-ci
> produirait des tickers sans `_meta`.

Chaque ticker expose un entier `confidence` (0–5), un point par garantie :
- +1 prix de la dernière séance cotée — ni périmé, ni statique
- +1 fondamentaux réels — présents dans `fondamentaux.json`, pas la table figée
- +1 RSI calculable — au moins 14 chandelles réelles
- +1 corpus NLP significatif — plus de 10 mentions
- +1 smart money disponible — `win` renseigné

**Règle d'affichage** : si `confidence ≤ 1`, le signal est remplacé par
« Données insuffisantes », en gris, dans le classement ET sur la fiche. Le
score v53 reste affiché mais passe en gris — il ne doit pas se lire comme une
conclusion.

**UI** : indicateur ●●●○○ sous le score v53, jamais caché. Couleur graduée —
rouge ≤1, orange 2, jaune 3, vert ≥4.

Relevé du 10/08 sur 81 titres : `{0: 1, 1: 4, 2: 5, 3: 37, 4: 2, 5: 32}`.
Le palier 3 domine parce que les fondamentaux viennent encore de la table
figée pour la majorité — c'est le chantier ouvert depuis le 29/06.

## Bloc `_meta` dans `data.json` — EN PLACE

> ✅ Émis par `update_data.py` depuis le 10/08/2026, pour les 81 tickers.

```json
"_meta": {
  "source_prix":  "idbourse",          // voir la liste ci-dessous
  "source_fond":  "fondamentaux_json | table_statique",
  "prix_asof":    "2026-08-10",        // séance du cours retenu, null si inconnue
  "stale":        false,
  "confidence":   5,
  "n_candles":    781,
  "generated_at": "2026-08-10T16:18:48+01:00"
}
```

`source_prix`, par ordre de préséance dans la chaîne de repli :
`idbourse` → `medias24` → `candles` → `idbourse_perime` → `historical` →
`data_json_precedent` → `financial` → `static`.

**Règle (extension R9)** : `stale: true` → le frontend affiche un badge
⚠️ portant la date réelle du cours (« ⚠ 05/08 »), pas un simple « J-1 ».
Sans `_meta`, le frontend suppose `stale: true` et `confidence: 0`.

Est `stale` tout cours dont la séance est antérieure à la dernière séance
cotée, **ainsi que** tout cours issu d'une source sans date propre —
`static`, `financial`, `data_json_precedent`. Ces dernières recopient un run
antérieur et se reconduiraient indéfiniment sans jamais le signaler.

⚠️ **Ne jamais écrire de chandelle depuis un prix `stale`.** L'étape 6c le
refuse désormais. Sans cette garde, un titre non rafraîchi par la source se
confirmait lui-même : le prix retombait sur la dernière chandelle, qu'on
réécrivait ensuite à la date du jour. Holcim s'est ainsi vu attribuer une
clôture au 10/08 alors qu'IDBourse ne l'avait plus coté depuis le 05/08.

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

### Monitoring — EN PLACE

> ✅ Implémenté le 25/08/2026 : `pipeline/verifier_seance.py`, déclenché par
> `.github/workflows/verifier_seance.yml` chaque jour ouvré à 19h32 Casablanca.

Dix contrôles sur la **dernière séance échue** : data.json lisible, horodatage
du jour, ≥50 titres au prix de la séance, sources réelles et non des replis
muets, les 19 MASI 1 avec un prix, v5.3 dans [0, 10], aucune variation > ±10 %
(R10), `_meta` sur chaque titre, MASI daté et non périmé, ≥50 bougies écrites.

**L'alerte est l'échec du workflow** : GitHub envoie alors un courriel au
propriétaire du dépôt. Pas de service tiers, pas de secret à gérer.

⚠️ **Le contrôle ne commite rien.** Le quota de publication de Pages est la
ressource rare du projet ; un contrôle qui produirait un commit par jour
consommerait ce qu'il protège. Le détail va dans le résumé du workflow.

⚠️ Il vise la dernière séance **échue**, jamais la date du jour — sinon il
échouerait chaque matin sur une séance qui n'a pas encore eu lieu. Seuil à
17h, parce que **GitHub décale ses tâches programmées de 30 à 50 minutes**
(mesuré trois fois le 24/08 : 34, 49 et 39 min). Un jour sans séance —
week-end ou férié à date fixe — sort en silence.

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

> ⚠️ **Drahmi API** — existence non confirmée comme source de fondamentaux. Ne pas intégrer dans le pipeline tant que la disponibilité n'est pas vérifiée manuellement (endpoint, authentification, couverture des 81 tickers).

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

### 2026-08-25

- **Le critère de succès devient mesurable.** « Trente jours consécutifs sans
  échec » ne l'était pas : rien ne prévenait quand un run manquait, il fallait
  que quelqu'un regarde. `verifier_seance.py` regarde désormais chaque jour
  ouvré à 19h32, et l'échec du workflow déclenche le courriel de GitHub.
  - **L'alerte passe par le canal déjà en place.** Aucun service tiers, aucun
    secret : un code de sortie non nul suffit.
  - **Aucun commit produit.** Un contrôle quotidien qui commiterait
    consommerait le quota de publication qu'il est censé protéger.

- **⚠️ GitHub décale ses tâches programmées de 30 à 50 minutes.** Mesuré trois
  fois le 24/08 : 34, 49 et 39 minutes. L'heure inscrite dans un cron est une
  intention, pas un rendez-vous. Deux conséquences : le contrôle vise la
  dernière séance **échue** et non la date du jour, et **le run de 15h45 est
  un point unique de défaillance** depuis la réduction à quatre crons — s'il
  est sauté, seul le filet de 18h rattrape la séance.

- **Séance du 19/08 recoupée au bulletin CDG : 68 cours exacts sur 70.** Les
  deux écarts sont STR et LHM, que **IDBourse ne sert plus depuis le 10/08**.
  Le bulletin les cote pourtant — STROC 184,95 pour 514 titres, Holcim 1 800
  pour 1 939 titres. Réparés à la main ; leur série garde un trou du 11 au 18.
  - ⚠️ Comparer le bulletin à nos chandelles **exige** de passer par
    `IDB_TICKER_MAP` : le `SNA` du bulletin est Stokvis, pas Sonasid. Sans
    traduction, l'écart affiché est de 96 %.

- **Le pipeline v9 faisait reculer les cours.** Il lit `data.json` au démarrage,
  calcule une demi-heure, puis commite par-dessus le run d'`update_bvc` parti
  après lui. Mesuré le 19/08 : 57 cours ramenés à ceux de 11h31. `data.json`
  n'a plus qu'un propriétaire, `update_bvc` ; v9 n'écrit que
  `financial_data.json`, et les deux partagent un groupe de concurrence.

- **⚠️ Le champ `updated` retardait d'une heure en permanence.**
  `datetime.now().strftime("...+01:00")` écrit l'heure UTC du runner en
  l'étiquetant Casablanca. Le message de commit, lui, utilisait la vraie
  horloge — d'où un data.json marqué 11h31 dans un commit intitulé 12h31.

- **Les proxys CORS du terminal sont hors d'usage, et irréparables.**
  corsproxy.io fonctionne encore (gratuit pour `github.io`) mais IDBourse
  exige un `Referer` depuis le 05/08, et **un navigateur n'a pas le droit de
  choisir cet en-tête** — il est « interdit » au sens de la norme. Aucun proxy
  public ne rétablira la couche live ; seul un intermédiaire qu'on contrôle le
  peut. Sans objet tant que la condition intraday de la Phase 4 n'est pas
  remplie.

### 2026-08-18

- **Le blocage d'IP par IDBourse n'existe pas — le constat du 29/06 était
  périmé.** Mesure sur cinq runs consécutifs d'`update_bvc` (tous depuis
  GitHub Actions, l'identité git `BVC Bot` étant posée par le workflow) :
  `idbourse=77, medias24=0, static=0` à chaque fois. La collecte depuis Actions
  fonctionne, et le projet de migration vers le Mac local est **abandonné**.
  - Le HTTP 403 obtenu par un `curl` nu depuis le Mac ne prouvait rien : depuis
    le 05/08, `/api/proxy/*` exige un `Referer`, et le refus est identique
    depuis n'importe quelle machine. `idb_get()` l'envoie déjà.
  - ⚠️ `medias24=0` ne signifie pas que Médias24 échoue : IDBourse couvrant
    tout, le repli n'est jamais atteint. Vérifié sur trente runs — jamais
    utilisé. Son accès depuis Actions reste donc **non testé**.

- **Boucle entre workflows rompue — cause réelle des 112 commits/jour.**
  `update_bvc` se déclenchait à la fin de `fetch_news`, qui se déclenchait à la
  fin d'`update_bvc`. Le commentaire du fichier l'assumait : « cycle BVC → news
  → BVC → news pendant toute la session (≈3-5 min/cycle) ». Sur six heures de
  séance, quatre-vingt-dix à cent vingt runs à soi seul.
  - Coupé **des deux côtés** : une seule coupure laisserait le cycle repartir.
  - Le déclenchement après le pipeline v9 est conservé — v9 écrit `data.json`
    sans émettre `_meta`, un run derrière lui les rétablit.
  - `update_bvc` passe de 27 crons à 4 : ouverture, mi-séance, 15h45 (quinze
    minutes après la clôture, c'est celui qui fixe le cours définitif) et 18h.
  - Attendu : au plus 28 runs/jour contre plus de 140, et seuls ceux qui
    modifient un fichier commitent.

- **Fondamentaux prévisionnels DATA+ publiés** dans un espace de noms `fwd`,
  jamais fondu dans `pe`/`pb`/`div`. DATA+ donne du prévisionnel, ces champs du
  réalisé — Managem à 7,5 réalisé et 29,0 attendu ne se contredisent pas, ils
  disent que le bénéfice est prévu en baisse. Le score v5.3 n'y touche pas (R8).
  - Seuil d'aberration déduit de la distribution : médiane 18, Q3 23, puis 40,
    46, 50 — et un saut à 102, 204, 404. Le seuil de 100 tombe dans ce vide et
    n'écarte que Lesieur et Unimer. Un PER ou un price-to-book négatif est
    écarté de même. Cinq valeurs nullifiées, journalisées à chaque run.
  - Les autres champs de ces sociétés sont conservés : le ROE de 0,5 % de
    Lesieur explique précisément pourquoi son PER n'avait aucun sens.
  - ⚠️ L'export se rafraîchit **à la main** et vieillit — celui-ci date du
    01/07. La fiche affiche la date complète pour que ça se voie.

- **⚠️ Le drapeau `stale` d'IDBourse ne veut pas dire « périmé » mais « pas en
  direct ».** Il passe à vrai dès la clôture. Le correctif MASI du 14/08 s'y
  fiait et allumait donc l'alerte en permanence hors séance — c'est-à-dire en
  permanence pour un bulletin publié avant l'ouverture. Une alerte toujours
  allumée n'alerte plus. Seule la date de la charge utile fait foi désormais,
  et elle suffisait : au 14/08 la valeur était datée du 10.

### 2026-08-14

- **⚠️ Séance fantôme un jour férié — 114 bougies écrites pour un jour sans
  cotation.** Le 14/08 est férié au Maroc, la Bourse n'a pas ouvert. IDBourse
  et Médias24 ont l'une et l'autre rediffusé la clôture du 13/08 en
  l'estampillant du 14. `updated_at` étant notre seule autorité sur la date de
  séance, **les trois écrivains de chandelles ont suivi** : 71 bougies par
  l'étape 6c de `update_data.py`, 43 de plus par `generate_candles.py`,
  143 occurrences dans `historical_data.json` par `collect_history_bvcscrap.py`,
  et 77 tickers étiquetés d'une séance fictive dans `_meta.prix_asof`.
  - **La règle R9 ne détecte pas ce cas.** Les sources rediffusent aussi la
    variation de la veille : 67 titres sur 77 portaient un `chg` non nul, donc
    le test `chg=0 ET vol=0` ne voyait rien. Le signal n'existe **qu'à l'échelle
    du marché** — une séance réelle ne reproduit jamais toutes les clôtures au
    centime près. Mesuré sur les deux cas : **71/71 clôtures identiques le
    14/08** (férié), **6/44 le 13/08** (séance cotée). La marge est telle qu'un
    seuil à 95 % ne peut pas se tromper de côté.
  - **Aucun calendrier de jours fériés n'a été introduit** — le test se déduit
    des données. C'est ce qui le rend fiable : les fériés marocains suivent en
    partie le calendrier lunaire et cette liste ne serait pas maintenue.
  - **Deux points d'application**, parce que les deux problèmes sont distincts :
    `_recaler_seance_fantome()` dans `update_data.py` ramène `IDB_ASOF` et la
    date de chaque ligne à la séance réelle dès la sortie de la source — c'est
    ce qui corrige `_meta.prix_asof` ; et `pipeline/seance.py`, balayage
    **après écriture** appelé par les trois écrivains. Les sources livrent
    ticker par ticker et aucune n'a la vue d'ensemble au moment d'écrire : le
    contrôle ne peut être que global et postérieur. C'est aussi la seule forme
    qui répare l'existant, y compris ce qu'un autre pipeline vient de déposer.
  - Les prix n'ont jamais été faux : ils étaient et restent la clôture du
    13/08, exacte. **Seule la date annoncée était une fiction.**
  - ⚠️ **`n_candles` compte la série source, pas la liste stockée** (tronquée à
    250 points). `compute_indicators()` renvoie `candles`, `last_close`,
    `last_date` et `n_candles` décrivant *sa* série tronquée : les recopier en
    bloc fait retomber `n_candles` de 784 à 249. D'où `_CHAMPS_SERIE`.

- **Séance du 13/08 vérifiée exacte** — bulletin CDG (« Indices du vendredi
  14 août », qui contient la séance du 13) : **0 écart > 0,1 % sur les 69 titres
  cotés**. Aucune réparation nécessaire.

- **MASI : l'indice affiché datait du 10/08 sans le dire.** La charge utile
  porte `date`, `status.message` et `stale`, dont nous ne lisions ni l'un ni
  l'autre — seuls `value` et `variation`. Les trois sont désormais lus et
  propagés.

### 2026-08-10

- **⚠️ La bougie du jour se figeait sur le premier run de la journée.** L'étape
  6c passait son tour dès qu'un point du jour existait (`if existing[-1].d ==
  today_str: continue`). Le premier run — souvent en pleine séance — gravait
  donc un cours de milieu de séance comme clôture définitive, et aucun run
  ultérieur ne le corrigeait. Relevé sur la séance du 10/08 : **57 bougies
  fausses sur 72 cotées**, la bougie disant IAM 100,70 et Managem 1 660 là où
  la clôture réelle valait 99,85 et 1 624.
  - `data.json`, lui, était juste : il se régénère intégralement à chaque run.
    L'écart ne se voyait donc que sur les graphiques et les indicateurs.
  - Corrigé : la bougie du jour se **rafraîchit** à chaque run. L'ouverture
    reste celle du premier point, les extrêmes s'étendent, la clôture suit le
    dernier cours connu. Le dernier run après 15h30 fixe la clôture.
  - Séance du 10/08 recalée depuis le bulletin CDG : 0 écart > 0,1 % sur les
    72 titres cotés.


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

- **Séances du 05 et 06 août réparées.** Pendant la panne IDBourse, le pipeline
  a réécrit la clôture du 04/08 à l'identique les deux jours suivants (`1133 ×3`
  pour AKD, `5350 ×3` pour WAF, `295 ×3` pour FNB). Le **04/08 lui-même est
  sain** — c'est ce qu'établit l'ancrage à deux bornes ci-dessous.
  - Source : colonne `DataChart` de la variante « graphique » du bulletin CDG,
    qui publie 30 clôtures par instrument. 60 de nos titres y figurent.
  - **Méthode d'ancrage** : une série n'est retenue pour un titre que si ses deux
    bornes tombent juste — `series[-4]` = notre 04/08 ET `series[-1]` = notre
    07/08. Les deux encadrent `[-3]` et `[-2]`, donc les 05 et 06 août, sans
    supposer aucun calendrier de séances (jours fériés compris). 51 titres ont
    passé l'ancrage.
  - Le 06/08 est recoupé une seconde fois avec le `previous_close` de
    casabourse : 60/61. Le seul désaccord, TGCC, venait de la série (788 contre
    773) — le contrôle croisé l'a écarté, et le titre a été traité par l'autre
    voie.
  - Pour les 5 titres cotés sans série (CASH, CMGP, MNG, SGTM, SOT), le 06/08
    est déduit du bulletin lui-même (`cours ÷ (1 + variation)`) et confirmé par
    casabourse. **Leur 05/08 reste non vérifié** : aucune source ne le donne.
  - Seule la clôture est publiée. Pour les séances réparées on écrit
    `o = h = l = c` et `v = 0`, plutôt que de conserver des extrêmes et des
    volumes qui sont des copies fabriquées du 04/08.
  - Résultat : **65/65 prix et 61/65 variations** conformes au bulletin. Les 4
    restants (ARD, IBM, IMI, RDS) sont des écarts inférieurs à 0,2 % où le
    bulletin se contredit lui-même — sa colonne `variation` et sa série
    `DataChart` ne donnent pas la même clôture de veille.

- **⚠️ Reste faux : les séances antérieures au 04/08.** Les séries CDG montrent
  que nos clôtures des 31/07 et 03/08 divergent aussi (STK à 74,2 au lieu de
  66,16 — la fuite de `static_fallback.json` dans les chandelles, déjà repérée
  le 01/08). Non traité : réparer plus loin demande un ancrage sur des séances
  dont nous n'avons pas la liste exacte. Les 10 ruptures signalées par
  `validate_candles()` restent ouvertes.

- **Outil : `pipeline/parse_cdg_bulletin.py`.** Lit les deux variantes du
  bulletin, traduit les codes officiels BVC via `IDB_TICKER_MAP`, et compare à
  nos chandelles (`--verifier AAAA-MM-JJ`). Dépendance `pdfplumber`, déjà
  déclarée dans `requirements.txt`.


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
