# Contaminations entre entreprises — inventaire

> ⚠️ **Généré** par `pipeline/contamination.py`.

⚠️ Les dates ci-dessous sont des dates de SÉANCE, inscrites dans la donnée. Elles ne disent NI quand la ligne a été écrite, NI quand le code a été corrigé. Un import du 6 juin peut écrire des cours datés du 13 mai.

⚠️ NE JAMAIS déduire les cours d'une société de ceux d'une autre. Savoir que MSA porte les cours de Mutandis ne dit rien de ce que valait Marsa Maroc.

| Titre | Suspect | Fenêtre (séances) | Niveau | Mesure |
|---|---|---|---|---|
| **MSA** | MUT | 2026-05-13 → 2026-06-16 | établi par la mesure | 18/18 identiques |
| **ATL** | HAL | 2026-06-05 → 2026-06-16 | nommé par une pièce, NON reproduit | aucune date commune |
| **CFGB** | BMC | 2026-05-13 → 2026-06-16 | nommé par une pièce, NON reproduit | aucune date commune |
| **DAR** | RDS | 2026-05-13 → 2026-06-23 | nommé par une pièce, NON reproduit | 0/1 identiques |
| **SBS** | — | — | risque ouvert, aucune fenêtre datée | — |

## MSA

- **Niveau** : établi par la mesure
- **Fait observé** : sur les dates où les deux séries existent, les clôtures de MSA sont identiques à celles de MUT
- **Hypothèse** : le collecteur a demandé « Mutandis » pour MSA et déversé les cours reçus dans le fichier de MSA
- **Pièce** : commit 48b3c583 du 23/06/2026 — MANUAL_MAP : MSA « Mutandis » → « Marsa Maroc »
- **Ce qui manque** : la date d'ÉCRITURE des lignes. Le commit est daté du 23/06 et les séances contaminées s'arrêtent au 16/06 : sans journal d'import, le lien reste une inférence.
- **Usages atteints** : prix_analyse, indicateur, execution_simulee

**Table reproductible — 18 correspondance(s) exacte(s) sur 18 date(s) comparable(s)**

| Date | MSA | MUT | |
|---|--:|--:|---|
| 2026-05-19 | 236.20 | 236.20 | **identiques** |
| 2026-05-20 | 232.00 | 232.00 | **identiques** |
| 2026-05-21 | 234.00 | 234.00 | **identiques** |
| 2026-05-22 | 234.00 | 234.00 | **identiques** |
| 2026-05-25 | 225.00 | 225.00 | **identiques** |
| 2026-05-26 | 230.05 | 230.05 | **identiques** |
| 2026-06-01 | 232.20 | 232.20 | **identiques** |
| 2026-06-02 | 235.00 | 235.00 | **identiques** |
| 2026-06-03 | 234.90 | 234.90 | **identiques** |
| 2026-06-04 | 230.00 | 230.00 | **identiques** |
| 2026-06-05 | 231.50 | 231.50 | **identiques** |
| 2026-06-08 | 236.00 | 236.00 | **identiques** |
| 2026-06-09 | 231.00 | 231.00 | **identiques** |
| 2026-06-10 | 230.00 | 230.00 | **identiques** |
| 2026-06-11 | 226.15 | 226.15 | **identiques** |
| 2026-06-12 | 229.00 | 229.00 | **identiques** |
| 2026-06-15 | 234.05 | 234.05 | **identiques** |
| 2026-06-16 | 235.00 | 235.00 | **identiques** |

## ATL

- **Niveau** : nommé par une pièce, NON reproduit
- **Fait observé** : rupture aller-retour des clôtures sur la période
- **Hypothèse** : ATL a reçu les cours d'Auto Hall
- **Pièce** : commit 48b3c583 — ATL « Auto Hall » → « AtlantaSanad »
- **Ce qui manque** : la série de HAL ne commence qu'au 19/06/2026 : aucune date commune, la correspondance ne peut pas être mesurée. L'absence de recouvrement n'est ni une confirmation ni une infirmation.
- **Usages atteints** : prix_analyse, indicateur, execution_simulee

⚠️ AUCUNE date commune : le recouvrement ne peut pas être mesuré. Ce n'est ni une confirmation ni une infirmation.

## CFGB

- **Niveau** : nommé par une pièce, NON reproduit
- **Fait observé** : rupture aller-retour des clôtures sur la période
- **Hypothèse** : CFGB a reçu les cours de BMCI
- **Pièce** : commit 48b3c583 — CFGB « BMCI » → « CFG Bank »
- **Ce qui manque** : la série de BMC ne commence qu'au 19/06/2026 : aucune date commune sur la période suspecte.
- **Usages atteints** : prix_analyse, indicateur, execution_simulee

⚠️ AUCUNE date commune : le recouvrement ne peut pas être mesuré. Ce n'est ni une confirmation ni une infirmation.

## DAR

- **Niveau** : nommé par une pièce, NON reproduit
- **Fait observé** : rupture de 176,00 à 4 190,00 au 24/06/2026
- **Hypothèse** : DAR a reçu les cours de Résidences Dar Saada
- **Pièce** : commit 48b3c583 — DAR « Res.Dar Saada » → « Dari Couspate »
- **Ce qui manque** : sur la période, DAR et RDS n'ont qu'UNE date commune — le 19/06 — et leurs clôtures y diffèrent. Un seul point discordant ne tranche rien.
- **Usages atteints** : prix_analyse, indicateur, execution_simulee

**Table reproductible — 0 correspondance(s) exacte(s) sur 1 date(s) comparable(s)**

| Date | DAR | RDS | |
|---|--:|--:|---|
| 2026-06-19 | 171.80 | 173.80 |  |

## SBS

- **Niveau** : risque ouvert, aucune fenêtre datée
- **Fait observé** : le collecteur demande encore « Super Cereales » alors que le référentiel dit « Société des Boissons du Maroc », ISIN MA0000010365
- **Hypothèse** : un rafraîchissement d'historique écrirait les cours d'une autre société
- **Pièce** : commit 48b3c583 — SBS « Ste Boissons » → « Super Cereales », correction qui contredit notre propre référentiel
- **Ce qui manque** : la réponse du fournisseur. Aucune fenêtre passée n'est démontrée contaminée : le risque porte sur l'AVENIR, pas sur les données existantes.
- **Usages atteints** : aucun usage passé

