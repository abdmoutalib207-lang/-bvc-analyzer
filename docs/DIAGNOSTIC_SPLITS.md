# Diagnostic des bases de prix autour des opérations sur titres

Demandé par la revue externe avant toute correction automatique. **Aucune
transformation n'a été appliquée** ; les fichiers figés sont intacts.

## Pourquoi les contrôles OHLC ne suffisaient pas

La revue l'avait annoncé : « une série peut respecter low ≤ open/close ≤ high
tout en mélangeant des bases incompatibles ». La bougie SOT du 05/05/2026 en
est la démonstration :

    o = 1700,00   h = 1700,00   l = 369,00   c = 369,00
    369 ≤ min(1700, 369) ≤ max(1700, 369) ≤ 1700   →   invariant RESPECTÉ

L'ouverture est un prix **pré-split**, la clôture un prix **post-split**. Une
seule bougie porte deux bases, et aucun contrôle existant ne pouvait le voir.

## Les deux titres sont dans des états OPPOSÉS

### MNG — split 1:10 au 2026-07-27

| | date | ouverture | plus haut | plus bas | clôture |
|---|---|---:|---:|---:|---:|
| dernière avant | 2026-07-24 | 1267.5 | 1280.0 | 1250.0 | **1250.0** |
| première après | 2026-07-27 | 1340.0 | 1369.0 | 1290.0 | **1364.0** |

Rapport des clôtures : **1.091**

### SOT — split 1:5 au 2026-05-05

| | date | ouverture | plus haut | plus bas | clôture |
|---|---|---:|---:|---:|---:|
| dernière avant | 2026-05-04 | 73.8 | 77.23 | 72.98 | **73.8** |
| première après | 2026-05-05 | 1700.0 | 1700.0 | 369.0 | **369.0** |

Rapport des clôtures : **5.000**

### MNG — série continue, ajustement déjà appliqué UNE fois

Le rapport de 1,091 est une variation de marché ordinaire, pas une
discontinuité. Les cours antérieurs au 27/07 sont donc **déjà divisés par 10**.

**Conséquence opérationnelle** : appliquer `adjust_splits()` à cette série la
diviserait une SECONDE fois. Le registre déclare l'opération ; rien dans le
fichier ne dit qu'elle a déjà été appliquée. C'est cette absence de
déclaration qui rend le double ajustement possible.

### SOT — l'historique porte un DOUBLE ÷5

Trois bases coexistent dans un seul fichier :

| Base | Où | Ordre de grandeur |
|---|---|---:|
| pré-split réelle | ouverture du 05/05 | 1 700 |
| actuelle | clôtures depuis le 05/05, et `data.json` | 340 à 380 |
| historique | toutes les clôtures avant le 05/05 | 40 à 85 |

L'ajustement **correct** donnerait 1 700 ÷ 5 = 340, cohérent avec la base
actuelle. L'historique correspond à 1 700 ÷ 25 = 68.

**L'historique de Sothema a été divisé par 5 deux fois.** C'est le défaut que
le journal du projet redoutait, écrit dans `adjust_splits()` : « ⚠️ Ne JAMAIS
appliquer à des candles déjà stockées/ajustées : le second passage
re-diviserait les cours ».

## Ce que cela implique

1. **Les deux séries ne peuvent pas recevoir le même traitement.** MNG est
   correcte et doit être protégée d'un nouvel ajustement ; SOT est fausse d'un
   facteur 5 sur toute sa profondeur antérieure au 05/05.
2. **Aucun indicateur calculé sur SOT à cheval sur le 05/05 n'est
   interprétable.** Une moyenne mobile qui traverse cette date mélange deux
   bases.
3. **La base de prix doit être DÉCLARÉE dans la donnée**, pas déduite. Son
   absence a permis les deux états, et empêche aujourd'hui de savoir ce qui a
   déjà été appliqué à un fichier donné.

## Ce que je NE fais pas dans ce lot

Aucune correction automatique. Les fichiers de `datasets/lot1a/` sont intacts,
empreintes inchangées.

## Ce qui manque pour corriger sûrement

- **Source et date d'effet** : le registre porte MNG au 27/07 (ratio 10) et SOT
  au 05/05 (ratio 5). ⚠️ Pour SOT, l'ISIN reste contesté entre `MA0000012833`
  et `MA0000012502` — R2, non tranché.
- **Transformations déjà appliquées** : irretrouvables. Les chandelles ne
  conservent aucune trace de ce qui leur a été fait. C'est la lacune centrale.
- **Une source primaire de cours pré-split** pour reconstruire SOT : bulletin
  CDG du 05/05 ou série DataChart de cette période. Nous ne les avons pas.

**Sans ces éléments, corriger SOT reviendrait à multiplier par 5 sur la foi
d'un raisonnement.** Le raisonnement est solide ; la trace ne l'est pas.

## Contrôle retenu contre le double ajustement

À défaut de base déclarée, un contrôle de continuité : un rapport de clôtures
proche du ratio du split signale une série NON ajustée ; un rapport proche de 1
signale une série DÉJÀ ajustée. C'est ce contrôle qui distingue aujourd'hui MNG
de SOT, et il est posé en test permanent.
