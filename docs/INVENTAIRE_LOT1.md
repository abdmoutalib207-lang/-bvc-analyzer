# Inventaire du lot 1 — couverture réelle des données

Mesuré le 11/09/2026 sur le dépôt, pas sur une documentation.

## Vue d'ensemble

- univers : **80 titres**, dont 19 au MASI 1
- séries de chandelles : **74** (6 titres sans historique)
- profondeur : min **49**, médiane **543**, max **1170** séances
- au moins 250 séances : **42** · au moins 500 : **39**
- fondamentaux relus sur dépôt AMMC : **11**
- dividendes sur résolution d'assemblée : **12**
- price-to-book calculable : **4**

## Anomalies ouvertes

- **5 séries** comptent plus de la moitié de séances sans volume : DAR, MGL, MRL, STK, UNI.
  Une séance sans transaction n'est pas une transaction à volume nul ; la distinction
  reste à porter dans la donnée (lot 1).
- **DAT-10** : l'unité du volume historique de CMT (`v=67515` au 16/07) est présumée,
  non certifiée — le programme qui a écrit la bougie n'est pas enregistré.
- Aucun doublon de date, aucune série désordonnée, aucune incohérence OHLC.

## Candidats pour une chaîne historique vérifiable de bout en bout

Critère : les DEUX bouts de la chaîne doivent être vérifiables — un historique
profond ET des fondamentaux relus en source primaire. Le volume médian mesure
la possibilité d'exécution, pas l'attrait du titre.

| Titre | Séances | Volume médian 60j | Fondamentaux AMMC | Remarque |
|---|---:|---:|:---:|---|
| ADH | 797 | 124 625 | oui |  |
| ADI | 797 | 22 380 | oui |  |
| CMT | 514 | 4 670 | oui | suspendu depuis le 17/07 |
| CSR | 794 | 27 504 | oui |  |
| HPS | 789 | 9 915 | oui |  |
| MNG | 797 | 34 625 | oui |  |
| MSA | 566 | 17 220 | oui |  |
| RIS | 565 | 7 340 | oui |  |
| SNA | 69 | 711 | oui | historique trop court |
| SOT | 542 | 4 | oui | quasi sans échanges |
| TQA | 65 | 1 136 | oui | historique trop court |

## Univers proposé pour le lot 1 : **ADH, ADI, CSR, MNG**

Quatre titres, choisis pour la **qualité de leurs données** — jamais pour leurs
performances, que ce document ne mentionne pas et dont il ne tient pas compte.

**Pourquoi ces quatre**

1. **Historique profond et continu** : 794 à 797 séances chacun, soit plus de
   trois ans. La plus longue moyenne mobile du socle du lot 2 en demande 200 ;
   il faut de la marge au-delà pour que la fenêtre ne soit pas le facteur
   limitant.
2. **Fondamentaux relus en source primaire**, page par page, dans le rapport
   déposé à l'AMMC — et corrigés : ADH 2,50 → 1,13 · CSR 11 → 7,45.
3. **Échanges réguliers** : volume médian sur 60 séances de 22 380 à 124 625
   titres. Une exécution y est plausible ; un backtest sur un titre qui échange
   quatre titres par séance mesurerait surtout notre imagination.
4. **Quatre secteurs distincts** — immobilier, immobilier/BTP, agroalimentaire,
   mines. Un univers d'un seul secteur testerait un facteur commun plutôt
   qu'une méthode.
5. **Un cas d'opération sur titres** : Managem porte un split 10:1 au
   27/07/2026, déclaré au registre. La chaîne doit le traverser correctement,
   et c'est précisément ce qu'on veut vérifier de bout en bout.

**Pourquoi pas les autres**

| Écarté | Raison — de données, pas de performance |
|---|---|
| CMT | suspendu depuis le 17/07 : pas de chaîne d'exécution à vérifier |
| SNA, TQA | 69 et 65 séances : trop court pour une SMA 200 |
| SOT | volume médian de 4 titres sur 60 séances : exécution invérifiable |
| HPS, MSA, RIS | profondeur et fondamentaux corrects, mais n'ajoutent aucun cas de figure nouveau au lot ; réserves pour l'extension |

**Ce que cet univers permet de vérifier**

Collecte → chandelles → indicateurs → score → backtest → mesure, sur des
données dont chaque maillon est rattachable à une observation ou à un calcul
documenté. C'est le critère de réception du lot 1, et quatre titres suffisent à
l'établir.

**Ce qu'il ne permet pas** : aucune conclusion statistique. Quatre titres ne
valident pas une méthode — ils valident une **chaîne**.
