# Journal des différences — ancien historique contre candidat

> ⚠️ **Généré** par `pipeline/journal_differences.py`.
> Une différence **oppose** deux sources ; elle ne désigne pas la fautive. **Aucune correction n'est appliquée.**

Le détail complet vit dans `datasets/candidat/journal_<titre>.json` — il n'est **pas** tronqué.

## ADH

- candidat : `f83947b8-Cours_ADH_20230912_20260911.3a7c1847c131.csv`
- période candidat 2023-09-12 → 2026-09-10 · ancien 2023-06-05 → 2026-09-08
- dates communes : **730**

### Prix — trois mesures qui ne se confondent pas

| Mesure | Nombre |
|---|--:|
| champs OHLC différents au-delà de 0.1% | **105** |
| dates comportant au moins un de ces écarts | **48** |
| clôtures différentes | **24** |
| champs non comparables (candidat non renseigné) | 0 |

Répartition par mois :

| Mois | Champs différents |
|---|--:|
| 2026-06 | 30 |
| 2026-07 | 50 |
| 2026-08 | 23 |
| 2026-09 | 2 |

### Volumes — trois hypothèses distinctes

| Hypothèse | Lignes |
|---|--:|
| valeur différente | 27 |
| date différente | 5 |

⚠️ « unité différente », « date différente » et « valeur différente » sont trois explications distinctes. Les confondre fait perdre l'information.

**Les 5 cas « date différente »** — notre valeur correspond à une séance ANTÉRIEURE :

| Date | Notre `v` | Quantité du jour | Détail |
|---|--:|--:|---|
| 2026-06-18 | 1,282,337.00 | 239,064.00 | notre valeur égale le/la quantité du 2026-06-16, soit 1 séance(s) disponible(s) plus tôt |
| 2026-06-19 | 8,591,230.00 | 212,784.00 | notre valeur égale le/la montant du 2026-06-18, soit 1 séance(s) disponible(s) plus tôt |
| 2026-06-25 | 69,299.00 | 21,907.00 | notre valeur égale le/la quantité du 2026-06-24, soit 1 séance(s) disponible(s) plus tôt |
| 2026-06-26 | 21,907.00 | 39,578.00 | notre valeur égale le/la quantité du 2026-06-25, soit 1 séance(s) disponible(s) plus tôt |
| 2026-06-29 | 39,578.00 | 7,082.00 | notre valeur égale le/la quantité du 2026-06-26, soit 1 séance(s) disponible(s) plus tôt |

⚠️ Ces cas forment des **chaînes consécutives**, ce qui n'est pas le profil d'une coïncidence. L'hypothèse d'un décalage reste **ouverte** — un contrôle antérieur l'avait déclarée écartée après l'avoir cherchée sur les seuls montants, là où le champ n'avait pas changé.

### Dates

- **absentes de notre historique, INTERNES** : 3 — 2026-06-22, 2026-06-23, 2026-06-24
- absentes de notre historique, **extension** au-delà du 2026-09-08 : 2026-09-09, 2026-09-10
- présentes chez nous et absentes du candidat : 67

une date INTERNE manque au milieu de notre historique ; une EXTENSION est postérieure à sa dernière séance et ne constitue pas un manque

## CSR

- candidat : `971aceda-Cours_CSR___20230912_20260911.979b62ded595.csv`
- période candidat 2023-09-12 → 2026-09-10 · ancien 2023-06-05 → 2026-09-08
- dates communes : **727**

### Prix — trois mesures qui ne se confondent pas

| Mesure | Nombre |
|---|--:|
| champs OHLC différents au-delà de 0.1% | **105** |
| dates comportant au moins un de ces écarts | **45** |
| clôtures différentes | **29** |
| champs non comparables (candidat non renseigné) | 6 |

Répartition par mois :

| Mois | Champs différents |
|---|--:|
| 2026-06 | 32 |
| 2026-07 | 53 |
| 2026-08 | 16 |
| 2026-09 | 4 |

### Volumes — trois hypothèses distinctes

| Hypothèse | Lignes |
|---|--:|
| valeur différente | 27 |
| date différente | 8 |
| non comparable | 2 |
| transformation | 2 |

⚠️ « unité différente », « date différente » et « valeur différente » sont trois explications distinctes. Les confondre fait perdre l'information.

**Les 8 cas « date différente »** — notre valeur correspond à une séance ANTÉRIEURE :

| Date | Notre `v` | Quantité du jour | Détail |
|---|--:|--:|---|
| 2026-06-12 | 6,406.00 | 78,743.00 | notre valeur égale le/la quantité du 2026-06-11, soit 1 séance(s) disponible(s) plus tôt |
| 2026-06-15 | 78,743.00 | 16,371.00 | notre valeur égale le/la quantité du 2026-06-12, soit 1 séance(s) disponible(s) plus tôt |
| 2026-06-16 | 16,371.00 | 688.00 | notre valeur égale le/la quantité du 2026-06-15, soit 1 séance(s) disponible(s) plus tôt |
| 2026-06-18 | 688.00 | 4,254.00 | notre valeur égale le/la quantité du 2026-06-16, soit 1 séance(s) disponible(s) plus tôt |
| 2026-06-19 | 790,230.00 | 49,809.00 | notre valeur égale le/la montant du 2026-06-18, soit 1 séance(s) disponible(s) plus tôt |
| 2026-06-25 | 1,571.00 | 2,360.00 | notre valeur égale le/la quantité du 2026-06-24, soit 1 séance(s) disponible(s) plus tôt |
| 2026-06-26 | 2,360.00 | 27,559.00 | notre valeur égale le/la quantité du 2026-06-25, soit 1 séance(s) disponible(s) plus tôt |
| 2026-06-29 | 27,559.00 | 2,857.00 | notre valeur égale le/la quantité du 2026-06-26, soit 1 séance(s) disponible(s) plus tôt |

⚠️ Ces cas forment des **chaînes consécutives**, ce qui n'est pas le profil d'une coïncidence. L'hypothèse d'un décalage reste **ouverte** — un contrôle antérieur l'avait déclarée écartée après l'avoir cherchée sur les seuls montants, là où le champ n'avait pas changé.

**Les 2 cas « transformation »** :

| Date | Notre `v` | Candidat | Hypothèse |
|---|--:|--:|---|
| 2024-04-02 | 399.00 | 399.70 | notre 399 est le montant 399.7 amputé de ses décimales — hypothèse de troncature, à vérifier |
| 2024-11-04 | 196.00 | 196.80 | notre 196 est le montant 196.8 amputé de ses décimales — hypothèse de troncature, à vérifier |

**Les 2 cas non comparables** — le candidat ne renseigne rien. ⚠️ Ce n'est **pas** un écart, et ce n'est **pas** un zéro :

| Date | Notre `v` | Candidat montant | Candidat quantité |
|---|--:|---|---|
| 2023-11-08 | 202.00 | *non renseigné* | *non renseigné* |
| 2024-03-21 | 193.00 | *non renseigné* | *non renseigné* |

### Dates

- **absentes de notre historique, INTERNES** : 6 — 2026-06-08, 2026-06-09, 2026-06-10, 2026-06-22, 2026-06-23, 2026-06-24
- absentes de notre historique, **extension** au-delà du 2026-09-08 : 2026-09-09, 2026-09-10
- présentes chez nous et absentes du candidat : 67

une date INTERNE manque au milieu de notre historique ; une EXTENSION est postérieure à sa dernière séance et ne constitue pas un manque

