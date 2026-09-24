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

Trois familles d'information sont combinées en une note composite :

| Pilier | Poids de référence | Ce qu'il mesure |
|---|---:|---|
| **Fondamental** | 47 % | bénéfice, dividende, valorisation, endettement |
| **Technique** | 25 % | RSI(14), moyennes 20/50/200, MACD, Bollinger, ADX |
| **Comportemental** | 28 % | sentiment tiré d'un corpus d'investisseurs |

La pondération de référence est **modulée par titre** selon le contexte —
hors séance le fondamental pèse davantage, un titre porté par des opérateurs
performants voit son pilier comportemental renforcé. Le poids réellement
appliqué est affiché sur chaque fiche, avec la note de chaque pilier.

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
# → 67 comparés · 0 écart · VERDICT CONCORDANCE
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

## État du projet — 24 septembre 2026

### Ce qui est établi

| | |
|---|---|
| Titres suivis | **80** |
| Séances en base | **42 578** |
| Historiques certifiés contre l'export de l'opérateur | **40 / 80** |
| Tests automatisés | **1 191** |
| Contrôles quotidiens sur la séance échue | **13** |

### ⚠️ Ce qui ne l'est pas

Ces limites sont connues, mesurées, et ouvertes. Les taire rendrait le reste
suspect.

- **Aucun backtest n'existe.** La performance historique des signaux n'est pas
  démontrée. Six ans de données le permettraient ; ce n'est pas fait. **Tant
  que ce chiffre n'existe pas, la note est une mesure sans référence.**
- **Le pilier comportemental pèse 28 % et distingue peu** : écart-type de
  0,035 contre ~1,1 pour les deux autres, et 47 titres sur 80 à valeur nulle.
- **Les fondamentaux sont saisis à la main** : 94 jours d'âge médian, et 51
  titres sur 80 sans price-to-book.
- **Le déclenchement automatique est défaillant.** Le planificateur de GitHub
  Actions ne part plus de façon fiable depuis le 26/08/2026 ; un déclencheur
  externe est en place dans `declencheur/` mais attend sa mise en service.
- **La conformité n'est pas tranchée** : agrément AMMC pour une offre
  commerciale, et gouvernance des données personnelles du corpus.

---

## Architecture

```
index.html                     terminal (React 18, compilé au navigateur)
update_data.py                 moteur — propriétaire unique de data.json
bvc_config.py                  référentiel : ISIN, tickers, registres de faits

pipeline/
  parse_cdg_bulletin.py        recoupement au bulletin officiel
  diagnostiquer_export_bvc.py  comparaison à l'export de l'opérateur
  importer_export_bvc.py       réception documentée d'un historique
  coherence.py                 contrôles de cohérence du flux
  rang_sectoriel.py            situe un ratio dans son secteur
  redondance.py                mesure la corrélation entre indicateurs
  verifier_seance.py           13 contrôles quotidiens
  candles/                     chandelles OHLCV par titre

datasets/
  historiques_importes/        réceptions, avec source et empreinte SHA-256
  seances_retirees/            séances retirées, avec la bougie exacte
  pieces_ammc/                 avis du régulateur

declencheur/                   déclencheur externe (Cloudflare Worker)
tests/                         1 191 tests
```

⚠️ **Le dépôt paraît vanilla, il ne l'est pas.** `index.html` contient du JSX
compilé par Babel dans le navigateur : il n'y a pas d'étape de build, et une
faute de syntaxe casse le site entier sans qu'aucun test Python ne la voie.
La vérification passe par la compilation du JSX (voir `.claude/skills/run-tests`).

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

# les 13 contrôles quotidiens sur la dernière séance échue
python3 pipeline/verifier_seance.py

# le flux se contredit-il lui-même ?
python3 pipeline/coherence.py

# la suite complète
python3 -m pytest
```

---

## Licence et avertissement

Les données proviennent de sources publiques et sont republiées à des fins
d'analyse. **Les conditions d'utilisation des fournisseurs n'ont pas fait
l'objet d'un accord écrit** ; c'est un chantier ouvert avant tout usage
commercial.

Ce terminal ne constitue ni un conseil en investissement, ni une
recommandation personnalisée, ni une sollicitation d'achat ou de vente.
