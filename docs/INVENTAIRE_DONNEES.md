# Inventaire des données — calculé

Produit par `pipeline/inventaire.py`. **Aucun chiffre n'est recopié.**
Chaque grandeur porte sa définition ; un désaccord se règle sur la
formule, pas sur le résultat.

⚠️ Le premier inventaire, écrit à la main, portait quatre volumes
médians faux : `sorted(v)[len(v)//2]` rend l'élément supérieur du
milieu, pas la médiane. Sur un effectif pair, la médiane est la MOYENNE
des deux valeurs centrales.

## Vue d'ensemble

- univers : **80 titres**, dont 19 au MASI 1
- séries présentes : **73**
- sans série : DIS, DLM, MDP, PPM, SAF, SLM, T2S
- **74 fichiers présents**, dont **73 rattachés à l'univers actuel**
  - fichier(s) orphelin(s), hors `TICKERS_ALL` : **TGC**
  - ⚠️ ce n'est PAS une disparition de données : le fichier existe,
    son code n'appartient simplement plus à l'univers déclaré
- profondeur : min **49**, médiane **543**, max **1170** lignes
- au moins 250 lignes : **41** · au moins 500 : **39**
- fondamentaux relus en source primaire : **11** (ADH ADI CMT CSR HPS MNG MSA RIS SNA SOT TQA)
- dividendes sur résolution d'assemblée : **12**

## Volume — unité et certitude

- unité retenue : **nombre de titres**
- certitude : *présumée — convention du moteur (QteEchangee), non enregistrée dans la chandelle elle-même*
- fenêtre d'activité : **60** dernières lignes présentes
- formule : `statistics.median` sur les valeurs d'état « mesuré » ;
  les inconnues et invalides sont EXCLUES, jamais remplacées par zéro
- couverture minimale pour publier la statistique : **60%**
  — en deçà, la statistique est **non calculable**, ce qui n'est pas zéro

## Séries

| Titre | Secteur | Lignes | Première | Dernière | Médiane vol. | Vol. mesuré nul | Vol. inconnu | Trous |
|---|---|---:|---|---|---:|---:|---:|---:|
| ADH | Immobilier | 797 | 2023-06-05 | 2026-09-08 | 121 846.0 | 1% | 0% | 28 |
| ADI | Immobilier | 797 | 2023-06-05 | 2026-09-08 | 21 984.0 | 1% | 0% | 28 |
| AFI | Matériaux de construction | 797 | 2023-06-05 | 2026-09-08 | 199.0 | 1% | 0% | 28 |
| AFM | Assurances | 796 | 2023-06-05 | 2026-09-08 | 0.0 | 5% | 0% | 29 |
| AGM | Assurances | 792 | 2023-06-05 | 2026-09-03 | 0.0 | 5% | 0% | 30 |
| AKD | Santé & Pharmacie | 69 | 2026-05-19 | 2026-09-08 | 15 091.0 | 7% | 0% | 9 |
| ALU | Sidérurgie & Métallurgie | 68 | 2026-05-19 | 2026-09-08 | 37.0 | 15% | 0% | 10 |
| ARD | Immobilier | 797 | 2023-06-05 | 2026-09-08 | 3 498.0 | 1% | 0% | 28 |
| ATL | Assurances | 797 | 2023-06-05 | 2026-09-08 | 4 543.0 | 1% | 0% | 28 |
| ATW | Banques | 797 | 2023-06-05 | 2026-09-08 | 57 340.5 | 1% | 0% | 28 |
| BAL | Immobilier | 797 | 2023-06-05 | 2026-09-07 | 0.0 | 4% | 0% | 27 |
| BCP | Banques | 797 | 2023-06-05 | 2026-09-08 | 30 805.0 | 1% | 0% | 28 |
| BMC | Banques | 50 | 2026-06-19 | 2026-09-08 | 507.5 | 40% | 0% | 5 |
| BOA | Banques | 797 | 2023-06-05 | 2026-09-08 | 19 823.5 | 1% | 0% | 28 |
| CAR | Agroalimentaire | 69 | 2026-05-19 | 2026-09-08 | 4 925.5 | 7% | 0% | 9 |
| CASH | Sociétés de financement | 162 | 2025-12-08 | 2026-09-08 | 23 876.0 | 4% | 0% | 29 |
| CDM | Banques | 797 | 2023-06-05 | 2026-09-08 | 2 057.0 | 1% | 0% | 28 |
| CFGB | Banques | 566 | 2024-05-13 | 2026-09-08 | 13 751.5 | 1% | 0% | 20 |
| CIH | Banques | 797 | 2023-06-05 | 2026-09-08 | 9 664.0 | 1% | 0% | 28 |
| CIM | Matériaux de construction | 74 | 2026-05-11 | 2026-09-08 | 3 205.5 | 11% | 0% | 10 |
| CMGP | Distribution | 403 | 2024-12-16 | 2026-09-08 | 17 419.5 | 1% | 0% | 34 |
| CMT | Mines | 514 | 2024-05-13 | 2026-07-16 | 4 660.0 | 0% | 0% | 37 |
| COL | Chimie | 797 | 2023-06-05 | 2026-09-08 | 1 628.0 | 1% | 0% | 28 |
| CSR | Agroalimentaire | 794 | 2023-06-05 | 2026-09-08 | 25 440.5 | 0% | 0% | 31 |
| CTM | Transport & Logistique | 797 | 2023-06-05 | 2026-09-08 | 45.5 | 2% | 0% | 28 |
| DAR | Agroalimentaire | 65 | 2026-05-25 | 2026-09-07 | 0.0 | 65% | 0% | 8 |
| DHO | Holdings | 794 | 2023-06-05 | 2026-09-08 | 17 708.0 | 1% | 0% | 31 |
| DSW | Distribution IT | 69 | 2026-05-19 | 2026-09-08 | 192.5 | 12% | 0% | 9 |
| DTT | Distribution IT | 69 | 2026-05-19 | 2026-09-08 | 2 555.0 | 7% | 0% | 9 |
| ENK | Distribution | 50 | 2026-06-19 | 2026-09-08 | 3 655.5 | 10% | 0% | 5 |
| EQD | Sociétés de financement | 796 | 2023-06-05 | 2026-09-04 | 0.0 | 5% | 0% | 27 |
| FNB | Distribution | 50 | 2026-06-19 | 2026-09-08 | 5 310.5 | 18% | 0% | 5 |
| GAZ | Énergie | 797 | 2023-06-05 | 2026-09-08 | 225.0 | 1% | 0% | 28 |
| HAL | Distribution | 50 | 2026-06-19 | 2026-09-08 | 5 502.0 | 10% | 0% | 5 |
| HPS | Technologies | 789 | 2023-06-05 | 2026-09-08 | 8 648.0 | 1% | 0% | 36 |
| IAM | Télécommunications | 797 | 2023-06-05 | 2026-09-08 | 144 149.5 | 1% | 0% | 28 |
| IBM | Technologies | 66 | 2026-05-21 | 2026-09-08 | 34.5 | 29% | 0% | 10 |
| IMI | Immobilier | 69 | 2026-05-19 | 2026-09-08 | 5 447.5 | 7% | 0% | 9 |
| INV | Technologies | 797 | 2023-06-05 | 2026-09-08 | 181.0 | 1% | 0% | 28 |
| JET | BTP & Construction | 797 | 2023-06-05 | 2026-09-08 | 595.5 | 2% | 0% | 28 |
| LBV | Distribution | 797 | 2023-06-05 | 2026-09-08 | 3 077.5 | 2% | 0% | 28 |
| LES | Agroalimentaire | 797 | 2023-06-05 | 2026-09-08 | 80.5 | 3% | 0% | 28 |
| LHM | Matériaux de construction | 791 | 2023-06-05 | 2026-09-08 | 13 433.5 | 1% | 0% | 34 |
| M2M | Technologies | 796 | 2023-06-05 | 2026-09-08 | 14.0 | 2% | 0% | 29 |
| MGL | Sociétés de financement | 49 | 2026-06-19 | 2026-09-08 | 0.0 | 55% | 0% | 6 |
| MIC | Technologies | 68 | 2026-05-19 | 2026-09-07 | 80.0 | 22% | 0% | 9 |
| MNG | Mines | 797 | 2023-06-05 | 2026-09-08 | 34 574.0 | 1% | 0% | 28 |
| MOX | Chimie | 797 | 2023-06-05 | 2026-09-08 | 3.0 | 3% | 0% | 28 |
| MRL | Sociétés de financement | 64 | 2026-05-25 | 2026-09-07 | 0.0 | 61% | 0% | 9 |
| MSA | Transport & Logistique | 566 | 2024-05-13 | 2026-09-08 | 17 143.0 | 1% | 0% | 20 |
| MUT | Agroalimentaire | 69 | 2026-05-19 | 2026-09-08 | 3 877.0 | 6% | 0% | 9 |
| NEJ | Distribution | 795 | 2023-06-05 | 2026-09-01 | 0.0 | 5% | 0% | 25 |
| OUL | Boissons | 64 | 2026-05-25 | 2026-09-04 | 0.0 | 48% | 0% | 8 |
| RDS | Immobilier | 543 | 2024-05-13 | 2026-09-08 | 45 040.0 | 1% | 0% | 43 |
| REB | Holdings | 68 | 2026-05-25 | 2026-09-08 | 0.5 | 44% | 0% | 6 |
| RIS | Tourisme & Loisirs | 565 | 2024-05-13 | 2026-09-08 | 6 991.0 | 1% | 0% | 21 |
| S2M | Technologies | 65 | 2026-05-19 | 2026-09-08 | 374.0 | 22% | 0% | 13 |
| SBS | Boissons | 67 | 2026-05-19 | 2026-09-08 | 43.0 | 22% | 0% | 11 |
| SGTM | BTP & Construction | 155 | 2025-12-17 | 2026-09-08 | 408 353.5 | 3% | 0% | 29 |
| SMI | Mines | 566 | 2024-05-13 | 2026-09-08 | 1 621.5 | 2% | 0% | 20 |
| SNA | Sidérurgie & Métallurgie | 69 | 2026-05-19 | 2026-09-08 | 671.5 | 14% | 0% | 9 |
| SNP | Chimie | 65 | 2026-05-19 | 2026-09-08 | 448.0 | 9% | 0% | 13 |
| SOT | Santé & Pharmacie | 542 | 2024-05-14 | 2026-09-08 | 4.0 | 5% | 0% | 43 |
| SRM | Ingénierie & Industrie | 562 | 2024-05-13 | 2026-09-08 | 1.5 | 5% | 0% | 24 |
| STK | Distribution | 50 | 2026-06-19 | 2026-09-08 | 0.0 | 62% | 0% | 5 |
| STR | Ingénierie & Industrie | 57 | 2026-05-19 | 2026-09-08 | 1 380.0 | 16% | 0% | 21 |
| TGCC | BTP & Construction | 1170 | 2021-12-16 | 2026-09-08 | 40 005.5 | 0% | 0% | 33 |
| TMA | Énergie | 65 | 2026-05-19 | 2026-09-08 | 391.5 | 17% | 0% | 13 |
| TQA | Énergie | 65 | 2026-05-19 | 2026-09-08 | 1 134.0 | 14% | 0% | 13 |
| UNI | Agroalimentaire | 62 | 2026-05-25 | 2026-09-07 | 0.0 | 58% | 0% | 11 |
| VCNE | Santé & Pharmacie | 259 | 2025-07-15 | 2026-09-08 | 19 477.5 | 2% | 0% | 30 |
| WAF | Assurances | 67 | 2026-05-19 | 2026-09-07 | 3.5 | 40% | 0% | 10 |
| ZLD | Mines | 64 | 2026-05-26 | 2026-09-08 | 3.5 | 31% | 0% | 9 |
