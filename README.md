# BVC Analyzer

**Analyse quantitative des 80 sociétés cotées à la Bourse de Casablanca.**
Une note sur 10 par titre, recalculée chaque jour de séance, sur des données
dont chaque chiffre porte sa source et sa date.

**[Terminal en ligne →](https://abdmoutalib207-lang.github.io/-bvc-analyzer/)**

> ⚠️ **Analyse quantitative, pas conseil en investissement.** Ce terminal
> n'est pas agréé par l'AMMC. Les signaux publiés sont le résultat d'un calcul
> documenté, pas une recommandation personnalisée.

---

## Ce que le terminal fait

Deux piliers sont combinés en une note composite ; un troisième est gelé :

| Pilier | Poids de référence | Ce qu'il mesure |
|---|---:|---|
| **Fondamental** | 65 % | rentabilité du capital, croissance, valorisation, bilan |
| **Technique** | 35 % | RSI(14), moyennes 20/50/200, position dans la fourchette 90 jours |
| **Comportemental** | **0 % — gelé** | sentiment tiré d'un corpus d'investisseurs arrêté au 02/07/2026 |

La pondération de référence est **modulée par le contexte de marché**, le
même pour tous les titres — hors séance le fondamental pèse davantage, un MASI
en forte baisse depuis janvier le renforce encore. Le poids réellement
appliqué est affiché sur chaque fiche, avec la note de chaque pilier.

Le pilier comportemental reste calculé et affiché pour la trace, mais il ne
pèse plus rien : son corpus est figé, il ne déplaçait que 0,37 point sur 10,
et son retrait n'a dégradé aucune mesure sur les notes publiées.

### Des fondamentaux lus dans les comptes publiés

Depuis le 01/10/2026, la note fondamentale lit d'abord ce qui est **calculé sur
les comptes déposés à l'AMMC**, chaque chiffre avec sa page :

- **ROIC, dette nette / EBITDA, conversion de trésorerie** — calculés sur les
  comptes 2025 (66 sociétés) ; les alertes affichées lisent la même valeur ;
- **PER** — cours du jour ÷ bénéfice par action sur douze mois glissants
  (exercice 2025 + semestre 2026 − semestre 2025), pour 64 sociétés ;
- **croissance** — celle des comptes semestriels, quand ils ont été lus.

La saisie manuelle de juin n'est plus lue que faute de chiffre publié, et elle
est datée à l'écran. Les dépôts semestriels sont repérés automatiquement sur la
liste de l'AMMC et mis en file d'attente de lecture.

Les objectifs de cours bear / base / bull ont été **retirés le 01/10/2026** :
ils venaient d'une table sans date, sans auteur ni méthode. Un objectif ne
reviendra que recalculé et sourcé.

### Un briefing par séance

Chaque séance produit un briefing de clôture — indice, largeur de marché,
concentration des échanges, titres à surveiller avec leurs critères, dépôts
AMMC du jour — archivé dans `briefings/` et relisible dans le terminal. La
lecture rédigée passe un contrôle : **chaque nombre écrit doit exister dans les
faits publiés par le moteur**, sinon le texte est refusé.

### Promesse de fraîcheur

**La dernière clôture fiable, jamais du temps réel.** Le run qui compte part
quinze minutes après la clôture de 15h30 et fixe le cours de la séance. Le
bulletin est disponible avant l'ouverture du lendemain.

---

## Ce qui distingue ce projet

### Chaque cours est recoupé avec le bulletin officiel

Le juge de paix n'est pas interne : c'est le bulletin PDF de fin de journée
publié par CDG Capital Bourse. Le recoupement se fait par une commande :

```bash
python3 pipeline/parse_cdg_bulletin.py <bulletin.pdf> --verifier 2026-09-24
# séance du 01/10/2026 → 69 comparés · 0 écart · VERDICT CONCORDANCE
```

### Chaque chiffre dit d'où il vient

Tout titre publié porte un bloc `_meta` : source du prix, date de la séance
retenue, âge des fondamentaux, nombre de chandelles disponibles, et un **score
de confiance de 0 à 5**. En dessous de 2, le signal est remplacé à l'écran par
« Données insuffisantes » — un score calculé sur des données de repli ne doit
pas se lire comme une conclusion.

### Les faits se constatent sur pièce, ils ne se déduisent pas

Un split, une suspension, une reprise après OPA, un jour de fermeture : chacun
est déclaré dans un registre de `bvc_config.py`, avec la source qui l'établit
— avis AMMC, bulletin d'opérateur, décret. Un décrochage dans une série de
prix n'est jamais une preuve : il peut être un split, une référence remise à
neuf ou une donnée fausse, et **les trois appellent des traitements opposés**.

### Le flux se contrôle lui-même

À chaque run, neuf familles de contrôles vérifient que les chiffres publiés
peuvent coexister — dont le principal : **la note doit se refaire à la main**
depuis les notes et poids publiés. Le résultat est publié dans `data.json`.

### Les conventions de calcul sont déclarées

`data.json` porte un bloc `_conventions` : une moyenne mobile 20 séances
inclut la séance du jour, les jours sans cotation sont exclus des fenêtres, le
volume est un nombre de titres et jamais un montant. Sans cela, tout
recoupement extérieur produit un écart qui passe pour une erreur de données.

---

## État du projet — 1er octobre 2026

### Ce qui est établi

| | |
|---|---|
| Titres suivis | **80** |
| Séances en base | **42 933** |
| Historiques reçus de l'export de l'opérateur | **40 / 80** |
| Sociétés avec ratios calculés sur comptes publiés | **66 / 77** |
| Sociétés avec bénéfice sur douze mois glissants | **64** |
| Tests automatisés | **1 654** |
| Contrôles quotidiens sur la séance échue | **15** |

### ⚠️ Ce qui ne l'est pas

Ces limites sont connues, mesurées, et ouvertes. Les taire rendrait le reste
suspect.

- **La note ne se montre pas prédictive.** Mesurée sur les notes réellement
  publiées depuis le 10/08 (observations à 5 séances), sa corrélation à la
  sur-performance est **négative**, autour de −0,05 à −0,06 selon la version.
  Un seul régime de marché, observations chevauchantes : c'est un constat,
  pas une conclusion. **Aucun rendement n'est promis.**
- **Les changements de note du 01/10 n'ont pas de backtest** : les ratios
  calculés sur comptes publiés n'existent que depuis le 29/09. Ils rendent la
  note fidèle aux comptes ; ils ne prouvent pas qu'elle prédit mieux.
- **La grille de notation est la même pour tous les secteurs.** Une banque ne
  se lit pas comme un promoteur ou une société de BTP ; une note sectorielle
  existe en mode fantôme (calculée, non appliquée), à mesurer avant usage.
- **Une partie des fondamentaux reste saisie à la main** (WACC, et tout chiffre
  sans équivalent publié), et son âge est affiché sur chaque fiche.
- **Le déclenchement repose sur un service externe.** Le planificateur de
  GitHub Actions saute des passages ; cron-job.org déclenche les passages
  depuis le 29/09/2026, avec les crons GitHub en filet.
- **La conformité n'est pas tranchée** : agrément AMMC pour une offre
  commerciale, et gouvernance des données personnelles du corpus.

---

## Architecture

```
terminal.src.html              terminal — la SOURCE (React 18 + JSX)
index.html                     sa compilation (tools/compiler_terminal.js) —
                               ne jamais la modifier à la main
update_data.py                 moteur — propriétaire unique de data.json
bvc_config.py                  référentiel : ISIN, tickers, registres de faits

pipeline/
  parse_cdg_bulletin.py        recoupement au bulletin officiel
  diagnostiquer_export_bvc.py  comparaison à l'export de l'opérateur
  importer_export_bvc.py       réception documentée d'un historique
  coherence.py                 contrôles de cohérence du flux
  rang_sectoriel.py            situe un ratio dans son secteur
  redondance.py                mesure la corrélation entre indicateurs
  verifier_seance.py           15 contrôles quotidiens
  smart_money/fond_score.py    note fondamentale ; ratio_effectif(), lecture
                               unique des ratios pour la note et les alertes
  ratios_financiers.py         ratios calculés sur les comptes publiés
  resultats_semestriels.py     bénéfice sur douze mois glissants
  depots_ammc.py               liste des dépôts de l'AMMC
  file_attente_comptes.py      comptes déposés, pas encore lus
  briefing.py · redaction.py   briefing de séance et contrôle de ses chiffres
  candles/                     chandelles OHLCV par titre

datasets/
  historiques_importes/        réceptions, avec source et empreinte SHA-256
  seances_retirees/            séances retirées, avec la bougie exacte
  pieces_ammc/                 avis du régulateur
  resultats_s1_2026.json       comptes semestriels lus, chaque chiffre avec sa page
  exercice_2025_rectifie.json  exercices 2025 rectifiés sur le document publié

briefings/                     un briefing archivé par séance

declencheur/                   déclencheur externe (Cloudflare Worker)
tests/                         1 654 tests
```

⚠️ **Le dépôt paraît vanilla, il ne l'est pas.** Le terminal est écrit en JSX
dans `terminal.src.html` et précompilé dans `index.html` par
`node tools/compiler_terminal.js`. Une faute de syntaxe casse le site entier ;
un test vérifie que `index.html` est exactement la compilation de la source.

---

## Sources de données

| Source | Apport | Rôle |
|---|---|---|
| **CDG Capital Bourse** | cours, chandelier complet, seuils ±10 % | tête de chaîne |
| **IDBourse** | cours et **capitalisation** | seule source de la capitalisation |
| **casablanca-bourse.com** | historique 3 ans par titre | l'opérateur — fait foi |
| **Bulletin PDF CDG** | cours, variation, extrêmes | juge de paix quotidien |
| **Maroclear** | ISIN officiels | dépositaire central |
| **AMMC** | états financiers, avis | régulateur |

⚠️ **CDG et Wafabourse ne sont pas des sources indépendantes** : même éditeur,
même convention de champs, même faute de frappe. Leur accord ne prouve rien.
Le seul contrôle réellement extérieur est le bulletin de fin de journée.

La chaîne de repli est arbitrée **par la date**, jamais par la préférence :
`CDG → IDBourse → chandelles → historique → table figée`.

---

## Vérifier soi-même

```bash
# la séance publiée est-elle conforme au bulletin officiel ?
python3 pipeline/parse_cdg_bulletin.py <bulletin.pdf> --verifier AAAA-MM-JJ

# les 15 contrôles quotidiens sur la dernière séance échue
python3 pipeline/verifier_seance.py

# le flux se contredit-il lui-même ?
python3 pipeline/coherence.py

# la suite complète
python3 -m pytest
```

---

## Licence et avertissement

**Tous droits réservés** (voir `LICENSE`) : le code et les contenus
originaux peuvent être consultés, pas réutilisés sans autorisation écrite.
Les versions antérieures au 07/10/2026 étaient sous licence MIT.

Les données proviennent de sources publiques et sont republiées à des fins
d'analyse. **Les conditions d'utilisation des fournisseurs n'ont pas fait
l'objet d'un accord écrit** ; c'est un chantier ouvert avant tout usage
commercial.

Ce terminal ne constitue ni un conseil en investissement, ni une
recommandation personnalisée, ni une sollicitation d'achat ou de vente.
