# Confrontation à l'export de l'opérateur

> ⚠️ **Généré** par `pipeline/confronter_export.py`.
> Un écart **oppose** deux sources ; il ne désigne pas la fautive.

## Le schéma, observé et non deviné

L'export porte **deux colonnes distinctes** là où notre chandelle n'a qu'un champ `v` :

| Colonne de l'export | Ce qu'elle contient |
|---|---|
| `Volume (MAD)` | un **montant** en dirhams |
| `Titres Échangés` | un **nombre** de titres |

La question « `v` est-il un nombre de titres ? » cesse donc d'être une conjecture d'ordre de grandeur.

## ADH

- export : `f83947b8-Cours_ADH_20230912_20260911.3a7c1847c131.csv`
- période de l'export : 2023-09-12 → 2026-09-10 (735 séances)
- période de notre série : 2023-06-05 → 2026-09-08 (797 lignes)
- dates communes : **730**
- séances dans l'export et **absentes de notre série** : **5**
- lignes chez nous et **absentes de l'export** : **67**
- écarts de prix au-delà de 0.1% : **105**

**Unité du champ `v`** — notre champ « v » correspond à le MONTANT EN DIRHAMS sur 92.2% des 730 lignes comparées

| concordance | lignes |
|---|--:|
| égale aux titres échangés | 25 |
| égale au montant en dirhams | 673 |
| ni l'un ni l'autre | 32 |

Exemples de lignes qui ne correspondent à aucune des deux colonnes :

| Date | notre `v` | Titres échangés | Montant (MAD) |
|---|--:|--:|--:|
| 2026-06-18 | 1,282,337 | 239,064 | 8,591,230.51 |
| 2026-06-19 | 8,591,230 | 212,784 | 7,484,109.48 |
| 2026-06-25 | 69,299 | 21,907 | 769,412.89 |
| 2026-06-26 | 21,907 | 39,578 | 1,378,582.03 |
| 2026-06-29 | 39,578 | 7,082 | 244,582.39 |
| 2026-06-30 | 29,514 | 131,647 | 4,587,701.06 |
| 2026-07-01 | 82,782 | 11,134 | 383,931.99 |
| 2026-07-02 | 49,083 | 92,633 | 3,232,592.83 |

**Les écarts sont bornés dans le temps.** Répartition par mois :

| Mois | Écarts de prix | `v` non concordants |
|---|--:|--:|
| 2026-06 | 30 | 6 |
| 2026-07 | 50 | 22 |
| 2026-08 | 23 | 4 |
| 2026-09 | 2 | 0 |

⚠️ Sur les mois **absents de ce tableau**, nos valeurs et celles de l'opérateur concordent à la tolérance près. Le désaccord n'est pas diffus : il est daté.

**Hypothèse testée puis écartée** — un décalage d'une séance : 1 cas sur 32 non-concordances. ÉCARTÉE — le cas ne se reproduit pas assez pour constituer un motif.

Premiers écarts de prix :

| Date | Champ | Export | Notre série | Écart |
|---|---|--:|--:|--:|
| 2026-06-08 | ouverture | 31.90 | 32.00 | +0.31% |
| 2026-06-09 | ouverture | 32.00 | 32.20 | +0.62% |
| 2026-06-10 | ouverture | 31.70 | 31.20 | -1.58% |
| 2026-06-11 | ouverture | 31.19 | 30.00 | -3.82% |
| 2026-06-12 | ouverture | 31.02 | 31.99 | +3.13% |
| 2026-06-15 | ouverture | 32.64 | 35.00 | +7.23% |
| 2026-06-16 | ouverture | 36.04 | 36.70 | +1.83% |
| 2026-06-18 | ouverture | 36.70 | 36.04 | -1.80% |
| 2026-06-18 | plus_haut | 36.80 | 36.04 | -2.07% |
| 2026-06-18 | plus_bas | 35.20 | 35.34 | +0.40% |
| 2026-06-18 | cloture | 35.98 | 35.34 | -1.78% |
| 2026-06-19 | ouverture | 35.00 | 36.70 | +4.86% |

Séances présentes chez l'opérateur et **absentes de notre série** — 5 au total, les dix premières : 2026-06-22, 2026-06-23, 2026-06-24, 2026-09-09, 2026-09-10

## CSR

- export : `971aceda-Cours_CSR___20230912_20260911.979b62ded595.csv`
- période de l'export : 2023-09-12 → 2026-09-10 (735 séances)
- période de notre série : 2023-06-05 → 2026-09-08 (794 lignes)
- dates communes : **727**
- séances dans l'export et **absentes de notre série** : **8**
- lignes chez nous et **absentes de l'export** : **67**
- écarts de prix au-delà de 0.1% : **105**

**Unité du champ `v`** — notre champ « v » correspond à le MONTANT EN DIRHAMS sur 92.0% des 727 lignes comparées

| concordance | lignes |
|---|--:|
| égale aux titres échangés | 19 |
| égale au montant en dirhams | 669 |
| ni l'un ni l'autre | 39 |

Exemples de lignes qui ne correspondent à aucune des deux colonnes :

| Date | notre `v` | Titres échangés | Montant (MAD) |
|---|--:|--:|--:|
| 2023-11-08 | 202 | 0 | 0.00 |
| 2024-03-21 | 193 | 0 | 0.00 |
| 2024-04-02 | 399 | 2 | 399.70 |
| 2024-11-04 | 196 | 1 | 196.80 |
| 2026-06-12 | 6,406 | 78,743 | 14,138,354.75 |
| 2026-06-15 | 78,743 | 16,371 | 3,031,338.20 |
| 2026-06-16 | 16,371 | 688 | 128,316.45 |
| 2026-06-18 | 688 | 4,254 | 790,230.80 |

**Les écarts sont bornés dans le temps.** Répartition par mois :

| Mois | Écarts de prix | `v` non concordants |
|---|--:|--:|
| 2023-11 | 0 | 1 |
| 2024-03 | 0 | 1 |
| 2024-04 | 0 | 1 |
| 2024-11 | 0 | 1 |
| 2026-06 | 32 | 9 |
| 2026-07 | 53 | 22 |
| 2026-08 | 16 | 4 |
| 2026-09 | 4 | 0 |

⚠️ Sur les mois **absents de ce tableau**, nos valeurs et celles de l'opérateur concordent à la tolérance près. Le désaccord n'est pas diffus : il est daté.

**Hypothèse testée puis écartée** — un décalage d'une séance : 1 cas sur 39 non-concordances. ÉCARTÉE — le cas ne se reproduit pas assez pour constituer un motif.

Premiers écarts de prix :

| Date | Champ | Export | Notre série | Écart |
|---|---|--:|--:|--:|
| 2026-06-11 | ouverture | 180.00 | 178.00 | -1.11% |
| 2026-06-11 | plus_haut | 180.00 | 178.00 | -1.11% |
| 2026-06-12 | ouverture | 180.00 | 178.00 | -1.11% |
| 2026-06-12 | plus_haut | 181.90 | 178.00 | -2.14% |
| 2026-06-12 | plus_bas | 179.00 | 178.00 | -0.56% |
| 2026-06-12 | cloture | 179.70 | 178.00 | -0.95% |
| 2026-06-15 | ouverture | 182.00 | 179.70 | -1.26% |
| 2026-06-15 | plus_haut | 185.50 | 179.70 | -3.13% |
| 2026-06-15 | plus_bas | 182.00 | 179.70 | -1.26% |
| 2026-06-15 | cloture | 185.50 | 179.70 | -3.13% |
| 2026-06-16 | ouverture | 186.80 | 185.50 | -0.70% |
| 2026-06-16 | plus_haut | 187.00 | 185.50 | -0.80% |

Séances présentes chez l'opérateur et **absentes de notre série** — 8 au total, les dix premières : 2026-06-08, 2026-06-09, 2026-06-10, 2026-06-22, 2026-06-23, 2026-06-24, 2026-09-09, 2026-09-10

## Ce que cette confrontation n'établit pas

- Elle ne dit pas **qui a raison**. L'export n'a pas été établi comme faisant autorité ; il est une seconde source, pas un juge.
- Elle ne couvre que **deux titres**. Rien ne permet d'étendre ses conclusions aux 79 autres.
- **Aucune correction n'est appliquée**, ni sur les prix, ni sur les volumes, ni sur les séances manquantes.

