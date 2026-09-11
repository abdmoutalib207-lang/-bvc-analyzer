# Ordre de grandeur des volumes — une alerte, pas une réfutation

> ⚠️ **Généré** par `pipeline/unites_volume.py`. Ne pas modifier à la main.

## Ce que ce contrôle peut dire

**Verdict possible : « ordre de grandeur suspect sous l'hypothèse de quantités en titres ». Rien de plus.**

Si `v` comptait des **titres**, le montant échangé vaudrait approximativement `v × c`.

⚠️ **Trois limites restreignent la portée de ce contrôle.**

1. `VOLUME_MARCHE_DH` (300,000,000) et `SEUIL_INVRAISEMBLABLE` (5,000,000,000) sont des **hypothèses écrites dans le programme**. Aucune confrontation à des totaux officiels datés n'a lieu. Une version antérieure affirmait que le raisonnement « ne dépend d'aucune source extérieure » : **c'était faux**.
2. `quantité × clôture` **approxime** le montant échangé — les transactions ne se font pas toutes à la clôture.
3. Un grand écart entre titres **ne prouve pas** des unités différentes : des prix erronés, un ajustement incompatible ou un cumul produiraient le même effet.

## Ce qui a réellement tranché

Pas ce contrôle — **l'export de l'opérateur**. Il porte deux colonnes distinctes, `Volume (MAD)` et `Titres Échangés`, et la comparaison ligne datée par ligne datée montre que notre `v` suit le **montant en dirhams** sur **92 %** des 730 séances communes d'ADH. Voir `docs/CONFRONTATION_EXPORT.md`.

⚠️ Cela vaut pour **deux titres**. Rien ne permet de l'étendre aux 79 autres.

## Ce que la mesure donne

- **73 séries** mesurées sur leurs 120 dernières séances
- **2** dépassent le seuil posé de 5,000,000,000 DH par séance : MNG, ATW
- les montants impliqués s'étalent sur un facteur **25,167,623** entre le plus petit et le plus grand

| Titre | Volume médian | Cours médian | Montant impliqué (DH) | Ordre de grandeur |
|---|--:|--:|--:|---|
| MNG | 7,791,522 | 1,363.8 | 8,053,639,266 | **suspect** |
| ATW | 8,436,986 | 691.8 | 5,779,335,410 | **suspect** |
| LBV | 994,985 | 3,860.0 | 4,266,495,680 | non signalé |
| LHM | 1,771,905 | 1,778.5 | 3,012,238,500 | non signalé |
| JET | 1,222,704 | 2,151.5 | 2,661,077,860 | non signalé |
| BCP | 2,659,936 | 247.3 | 652,430,938 | non signalé |
| ADI | 1,337,527 | 415.5 | 566,846,000 | non signalé |
| HPS | 653,056 | 613.8 | 407,174,372 | non signalé |
| CDM | 377,746 | 1,003.5 | 392,478,094 | non signalé |
| IAM | 3,962,266 | 93.5 | 378,465,976 | non signalé |
| GAZ | 86,216 | 3,749.5 | 324,294,858 | non signalé |
| BOA | 789,039 | 200.0 | 161,042,860 | non signalé |
| … | | | | |
| IBM | 103 | 60.5 | 5,837 | non signalé |
| OUL | 2 | 1,165.0 | 2,330 | non signalé |
| REB | 5 | 95.0 | 475 | non signalé |
| UNI | 2 | 175.0 | 320 | non signalé |

## Ce qui est établi, et ce qui ne l'est pas

**Établi par ce contrôle** : rien de plus qu'une alerte d'ordre de grandeur, sous des seuils que nous avons posés nous-mêmes.

**Établi par l'export, et pour deux titres seulement** : notre `v` suit le montant en dirhams.

**Non établi** : la convention du champ pour les 79 autres titres.

## Conséquence tenue

Le registre `BASES_QUANTITES` reste **vide** et `unite_etablie` vaut **False**. Tout indicateur consommant des volumes — OBV en tête — reste refusé. Ce n'est plus une précaution de principe : c'est la conclusion d'une mesure.

