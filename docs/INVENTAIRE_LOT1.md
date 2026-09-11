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
- profondeur : min **49**, médiane **543**, max **1170** lignes
- au moins 250 lignes : **41** · au moins 500 : **39**
- fondamentaux relus en source primaire : **11** (ADH ADI CMT CSR HPS MNG MSA RIS SNA SOT TQA)
- dividendes sur résolution d'assemblée : **12**

## Volume — unité et certitude

- unité retenue : **nombre de titres**
- certitude : *présumée — convention du moteur (QteEchangee), non enregistrée dans la chandelle elle-même*
- fenêtre d'activité : **60** dernières lignes présentes
- formule : `statistics.median`, valeurs absentes comptées comme 0

## Séries

| Titre | Secteur | Lignes | Première | Dernière | Médiane vol. | Sans vol. | Trous |
|---|---|---:|---|---|---:|---:|---:|
| ADH | Immobilier | 797 | 2023-06-05 | 2026-09-08 | 121 846.0 | 1% | 28 |
| ADI | Immobilier | 797 | 2023-06-05 | 2026-09-08 | 21 984.0 | 1% | 28 |
| AFI | Matériaux de construction | 797 | 2023-06-05 | 2026-09-08 | 199.0 | 1% | 28 |
| AFM | Assurances | 796 | 2023-06-05 | 2026-09-08 | 0.0 | 5% | 29 |
| AGM | Assurances | 792 | 2023-06-05 | 2026-09-03 | 0.0 | 5% | 30 |
| AKD | Santé & Pharmacie | 69 | 2026-05-19 | 2026-09-08 | 15 091.0 | 7% | 9 |
| ALU | Sidérurgie & Métallurgie | 68 | 2026-05-19 | 2026-09-08 | 37.0 | 15% | 10 |
| ARD | Immobilier | 797 | 2023-06-05 | 2026-09-08 | 3 498.0 | 1% | 28 |
| ATL | Assurances | 797 | 2023-06-05 | 2026-09-08 | 4 543.0 | 1% | 28 |
| ATW | Banques | 797 | 2023-06-05 | 2026-09-08 | 57 340.5 | 1% | 28 |
| BAL | Immobilier | 797 | 2023-06-05 | 2026-09-07 | 0.0 | 4% | 27 |
| BCP | Banques | 797 | 2023-06-05 | 2026-09-08 | 30 805.0 | 1% | 28 |
| BMC | Banques | 50 | 2026-06-19 | 2026-09-08 | 507.5 | 40% | 5 |
| BOA | Banques | 797 | 2023-06-05 | 2026-09-08 | 19 823.5 | 1% | 28 |
| CAR | Agroalimentaire | 69 | 2026-05-19 | 2026-09-08 | 4 925.5 | 7% | 9 |
| CASH | Sociétés de financement | 162 | 2025-12-08 | 2026-09-08 | 23 876.0 | 4% | 29 |
| CDM | Banques | 797 | 2023-06-05 | 2026-09-08 | 2 057.0 | 1% | 28 |
| CFGB | Banques | 566 | 2024-05-13 | 2026-09-08 | 13 751.5 | 1% | 20 |
| CIH | Banques | 797 | 2023-06-05 | 2026-09-08 | 9 664.0 | 1% | 28 |
| CIM | Matériaux de construction | 74 | 2026-05-11 | 2026-09-08 | 3 205.5 | 11% | 10 |
| CMGP | Distribution | 403 | 2024-12-16 | 2026-09-08 | 17 419.5 | 1% | 34 |
| CMT | Mines | 514 | 2024-05-13 | 2026-07-16 | 4 660.0 | 0% | 37 |
| COL | Chimie | 797 | 2023-06-05 | 2026-09-08 | 1 628.0 | 1% | 28 |
| CSR | Agroalimentaire | 794 | 2023-06-05 | 2026-09-08 | 25 440.5 | 0% | 31 |
| CTM | Transport & Logistique | 797 | 2023-06-05 | 2026-09-08 | 45.5 | 2% | 28 |
| DAR | Agroalimentaire | 65 | 2026-05-25 | 2026-09-07 | 0.0 | 65% | 8 |
| DHO | Holdings | 794 | 2023-06-05 | 2026-09-08 | 17 708.0 | 1% | 31 |
| DSW | Distribution IT | 69 | 2026-05-19 | 2026-09-08 | 192.5 | 12% | 9 |
| DTT | Distribution IT | 69 | 2026-05-19 | 2026-09-08 | 2 555.0 | 7% | 9 |
| ENK | Distribution | 50 | 2026-06-19 | 2026-09-08 | 3 655.5 | 10% | 5 |
| EQD | Sociétés de financement | 796 | 2023-06-05 | 2026-09-04 | 0.0 | 5% | 27 |
| FNB | Distribution | 50 | 2026-06-19 | 2026-09-08 | 5 310.5 | 18% | 5 |
| GAZ | Énergie | 797 | 2023-06-05 | 2026-09-08 | 225.0 | 1% | 28 |
| HAL | Distribution | 50 | 2026-06-19 | 2026-09-08 | 5 502.0 | 10% | 5 |
| HPS | Technologies | 789 | 2023-06-05 | 2026-09-08 | 8 648.0 | 1% | 36 |
| IAM | Télécommunications | 797 | 2023-06-05 | 2026-09-08 | 144 149.5 | 1% | 28 |
| IBM | Technologies | 66 | 2026-05-21 | 2026-09-08 | 34.5 | 29% | 10 |
| IMI | Immobilier | 69 | 2026-05-19 | 2026-09-08 | 5 447.5 | 7% | 9 |
| INV | Technologies | 797 | 2023-06-05 | 2026-09-08 | 181.0 | 1% | 28 |
| JET | BTP & Construction | 797 | 2023-06-05 | 2026-09-08 | 595.5 | 2% | 28 |
| LBV | Distribution | 797 | 2023-06-05 | 2026-09-08 | 3 077.5 | 2% | 28 |
| LES | Agroalimentaire | 797 | 2023-06-05 | 2026-09-08 | 80.5 | 3% | 28 |
| LHM | Matériaux de construction | 791 | 2023-06-05 | 2026-09-08 | 13 433.5 | 1% | 34 |
| M2M | Technologies | 796 | 2023-06-05 | 2026-09-08 | 14.0 | 2% | 29 |
| MGL | Sociétés de financement | 49 | 2026-06-19 | 2026-09-08 | 0.0 | 55% | 6 |
| MIC | Technologies | 68 | 2026-05-19 | 2026-09-07 | 80.0 | 22% | 9 |
| MNG | Mines | 797 | 2023-06-05 | 2026-09-08 | 34 574.0 | 1% | 28 |
| MOX | Chimie | 797 | 2023-06-05 | 2026-09-08 | 3.0 | 3% | 28 |
| MRL | Sociétés de financement | 64 | 2026-05-25 | 2026-09-07 | 0.0 | 61% | 9 |
| MSA | Transport & Logistique | 566 | 2024-05-13 | 2026-09-08 | 17 143.0 | 1% | 20 |
| MUT | Agroalimentaire | 69 | 2026-05-19 | 2026-09-08 | 3 877.0 | 6% | 9 |
| NEJ | Distribution | 795 | 2023-06-05 | 2026-09-01 | 0.0 | 5% | 25 |
| OUL | Boissons | 64 | 2026-05-25 | 2026-09-04 | 0.0 | 48% | 8 |
| RDS | Immobilier | 543 | 2024-05-13 | 2026-09-08 | 45 040.0 | 1% | 43 |
| REB | Holdings | 68 | 2026-05-25 | 2026-09-08 | 0.5 | 44% | 6 |
| RIS | Tourisme & Loisirs | 565 | 2024-05-13 | 2026-09-08 | 6 991.0 | 1% | 21 |
| S2M | Technologies | 65 | 2026-05-19 | 2026-09-08 | 374.0 | 22% | 13 |
| SBS | Boissons | 67 | 2026-05-19 | 2026-09-08 | 43.0 | 22% | 11 |
| SGTM | BTP & Construction | 155 | 2025-12-17 | 2026-09-08 | 408 353.5 | 3% | 29 |
| SMI | Mines | 566 | 2024-05-13 | 2026-09-08 | 1 621.5 | 2% | 20 |
| SNA | Sidérurgie & Métallurgie | 69 | 2026-05-19 | 2026-09-08 | 671.5 | 14% | 9 |
| SNP | Chimie | 65 | 2026-05-19 | 2026-09-08 | 448.0 | 9% | 13 |
| SOT | Santé & Pharmacie | 542 | 2024-05-14 | 2026-09-08 | 4.0 | 5% | 43 |
| SRM | Ingénierie & Industrie | 562 | 2024-05-13 | 2026-09-08 | 1.5 | 5% | 24 |
| STK | Distribution | 50 | 2026-06-19 | 2026-09-08 | 0.0 | 62% | 5 |
| STR | Ingénierie & Industrie | 57 | 2026-05-19 | 2026-09-08 | 1 380.0 | 16% | 21 |
| TGCC | BTP & Construction | 1170 | 2021-12-16 | 2026-09-08 | 40 005.5 | 0% | 33 |
| TMA | Énergie | 65 | 2026-05-19 | 2026-09-08 | 391.5 | 17% | 13 |
| TQA | Énergie | 65 | 2026-05-19 | 2026-09-08 | 1 134.0 | 14% | 13 |
| UNI | Agroalimentaire | 62 | 2026-05-25 | 2026-09-07 | 0.0 | 58% | 11 |
| VCNE | Santé & Pharmacie | 259 | 2025-07-15 | 2026-09-08 | 19 477.5 | 2% | 30 |
| WAF | Assurances | 67 | 2026-05-19 | 2026-09-07 | 3.5 | 40% | 10 |
| ZLD | Mines | 64 | 2026-05-26 | 2026-09-08 | 3.5 | 31% | 9 |

---

## Univers du lot 1A : **ADH, ADI, CSR, MNG** — et trois cas de contrôle

Choisis sur la **qualité des données**. Leurs performances ne sont ni
mentionnées, ni consultées, ni utilisées comme critère.

⚠️ **Correction d'un argument que j'avais donné à tort.** J'avais annoncé
« quatre secteurs distincts ». ADH et ADI sont **tous deux Immobilier** dans
notre propre référentiel : il y a **trois** secteurs — Immobilier (deux
titres), Agroalimentaire, Mines. La revue externe l'a relevé. Le choix reste
valable pour une recette technique, mais l'argument de diversification était
faux et je le retire.

| Titre | Lignes | Période | Secteur | Rôle |
|---|---:|---|---|---|
| ADH | 797 | 2023-06-05 → 2026-09-08 | Immobilier | chaîne |
| ADI | 797 | 2023-06-05 → 2026-09-08 | Immobilier | chaîne |
| CSR | 794 | 2023-06-05 → 2026-09-08 | Agroalimentaire | chaîne |
| MNG | 797 | 2023-06-05 → 2026-09-08 | Mines | opération sur titres |

**Ce que chacun apporte à la recette**

- **ADH, ADI, CSR** : profondeur au-delà de 200 lignes (la fenêtre de la SMA la
  plus longue), fondamentaux relus page par page en source primaire et
  corrigés, échanges réguliers rendant une exécution plausible.
- **MNG** : porte un split 10:1 au 27/07/2026, déclaré au registre. La chaîne
  doit le traverser correctement — c'est précisément ce qu'on veut éprouver.
  ⚠️ Ses données avant et après l'opération restent à vérifier séparément.

**Les trois cas de contrôle, conservés à la demande de la revue**

| Titre | Ce qu'il éprouve |
|---|---|
| CMT | suspension : le système doit **refuser** l'exécution. Ne pas l'écarter parce qu'on ne peut pas y passer d'ordre — c'est exactement le cas qu'il doit savoir refuser. |
| TQA | 65 lignes : indicateur non calculable. La SMA 200 doit être **absente**, pas approximée. |
| SOT | volume médian de 4 titres sur 60 séances : absence de transaction, données manquantes, liquidité dégradée. |

**Ce que cet univers permet** : éprouver la chaîne collecte → chandelles →
indicateurs → score → backtest, sur des données dont chaque maillon est
rattachable à une observation ou à un calcul documenté.

**Ce qu'il ne permet pas** : aucune conclusion statistique, aucune allocation,
aucune proposition d'investissement. Sept titres ne valident pas une méthode —
ils éprouvent une **architecture**.

Dataset brut figé : `datasets/lot1a/`, avec `MANIFESTE.json` portant empreinte,
période, unité du volume et son niveau de certitude pour chaque série.
