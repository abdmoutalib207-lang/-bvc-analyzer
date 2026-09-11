# L'unité du champ « v » n'est pas établie

> ⚠️ **Généré** par `pipeline/unites_volume.py`. Ne pas modifier à la main.

## Le raisonnement

Si `v` comptait des **titres**, le montant échangé vaudrait `v × c`. Ce produit s'oppose à un ordre de grandeur connu : le volume quotidien de **toute** la Bourse de Casablanca se compte en centaines de millions de dirhams (~300,000,000 DH).

Le raisonnement ne dépend d'aucune source extérieure : il oppose la donnée à sa propre conséquence arithmétique.

## Ce que la mesure donne

- **73 séries** mesurées sur leurs 120 dernières séances
- **2** dépassent à elles seules 5,000,000,000 DH par séance : MNG, ATW
- les montants impliqués s'étalent sur un facteur **25,167,623** entre le plus petit et le plus grand

| Titre | Volume médian | Cours médian | Montant impliqué (DH) | En titres ? |
|---|--:|--:|--:|---|
| MNG | 7,791,522 | 1,363.8 | 8,053,639,266 | **incompatible** |
| ATW | 8,436,986 | 691.8 | 5,779,335,410 | **incompatible** |
| LBV | 994,985 | 3,860.0 | 4,266,495,680 | possible |
| LHM | 1,771,905 | 1,778.5 | 3,012,238,500 | possible |
| JET | 1,222,704 | 2,151.5 | 2,661,077,860 | possible |
| BCP | 2,659,936 | 247.3 | 652,430,938 | possible |
| ADI | 1,337,527 | 415.5 | 566,846,000 | possible |
| HPS | 653,056 | 613.8 | 407,174,372 | possible |
| CDM | 377,746 | 1,003.5 | 392,478,094 | possible |
| IAM | 3,962,266 | 93.5 | 378,465,976 | possible |
| GAZ | 86,216 | 3,749.5 | 324,294,858 | possible |
| BOA | 789,039 | 200.0 | 161,042,860 | possible |
| … | | | | |
| IBM | 103 | 60.5 | 5,837 | possible |
| OUL | 2 | 1,165.0 | 2,330 | possible |
| REB | 5 | 95.0 | 475 | possible |
| UNI | 2 | 175.0 | 320 | possible |

## Ce qui est établi, et ce qui ne l'est pas

**Établi** : une unité unique « nombre de titres » sur l'ensemble des séries est **incompatible** avec ces montants.

**Non établi** : ce que `v` est réellement. Un montant en dirhams est l'hypothèse la plus simple ; un facteur d'échelle, un cumul, ou un champ hérité d'une autre source la produiraient aussi. Seule la convention écrite du fournisseur trancherait, et nous ne l'avons pas.

## Conséquence tenue

Le registre `BASES_QUANTITES` reste **vide** et `unite_etablie` vaut **False**. Tout indicateur consommant des volumes — OBV en tête — reste refusé. Ce n'est plus une précaution de principe : c'est la conclusion d'une mesure.

