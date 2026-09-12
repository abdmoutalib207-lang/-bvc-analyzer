# Historiques — lot 2 : HPS, Managem, Sothema, Ciments du Maroc, Stokvis

> ⚠️ **Aucune correction appliquée.** Tout est dans `datasets/historiques_candidats/`.

## ⚠️ Deux fichiers portaient le code de L'OPÉRATEUR, pas le nôtre

| fichier reçu | `Instrument` porté | déposé sous | chez nous, ce code désigne |
|---|---|---|---|
| `Cours_SNA` | **STOKVIS NORD AFRIQUE** | `sources/STK/` | `SNA` = **Sonasid** |
| `Cours_CMA` | **CIMENTS DU MAROC** | `sources/CIM/` | `CMA` = aucun titre |

Déposer `Cours_SNA` sous `SNA` aurait rejoué la faute de juin à l'identique.
Le garde-fou refuse les deux : *« LE FOURNISSEUR A RENVOYÉ UNE AUTRE
ENTREPRISE »*. C'est la colonne `Instrument` qui a tranché, pas le nom du
fichier.

## Vue d'ensemble

| titre | instrument | communes | identiques | > 20 % | manque | fantôme |
|---|---|--:|--:|--:|--:|--:|
| HPS | HPS | 724 | **700 (96.7 %)** | 0 | 11 | 68 |
| MNG | MANAGEM | 732 | **709 (96.9 %)** | 0 | 3 | 68 |
| SOT | SOTHEMA | 544 | **25 (4.6 %)** | 486 | 26 | 1 |
| CIM | CIMENTS DU MAROC | 76 | **27 (35.5 %)** | 20 | 4 | 1 |
| STK | STOKVIS NORD AFRIQUE | 52 | **24 (46.2 %)** | 3 | 3 | 1 |

## Ce qui est établi

### 1. Sothema : 486 séances à la mauvaise échelle

Nos cours d'avant le 05/05/2026 valent **0,0434 fois** ceux de l'opérateur,
avec une dispersion de **1,7 %** sur 486 séances. Un rapport constant n'est
pas du bruit : c'est un **facteur 4,61 appliqué de trop**. Après le split,
nous concordons à **1,0001**.

Le ratio du split est vérifié **par la capitalisation de l'opérateur**, jamais
par notre registre : 7 661 900 → 38 309 500 titres, soit **×5,0000**. Notre
registre déclare 5 — il a raison. C'est notre historique qui est faux.

### 2. HPS : un split 1:10 réel, absent de notre registre

| séance | cours | titres déduits |
|---|--:|--:|
| 2023-10-06 | 6 400,00 | 740 619 |
| 2023-10-09 | 658,00 | **7 406 190** |

**×10 exactement.** La rupture signalée par le validateur depuis le 01/08
n'était donc pas une donnée fausse : c'est une **opération sur titres non
déclarée**. Ni nous ni l'opérateur ne l'ajustons — nos deux séries portent la
même chute de −90 %, et tout indicateur qui la traverse est faux.

### 3. Managem : rien d'anormal, une fois le split pris en compte

96,9 % de concordance, **zéro** écart supérieur à 20 %. Ratio vérifié par la
capitalisation : 11 864 676 → 118 646 760 titres, **×10,0000**.

⚠️ Sans ajustement, la comparaison aurait affiché 704 écarts. Mon générateur
de corrections les a réellement produits avant que je ne corrige : **un
programme qui compare deux échelles ne propose pas des corrections, il en
fabrique.**

### 4. La séance fantôme du 30/07 touche les cinq titres

Comme MSA et MUT. L'opérateur ne la cote pour aucun d'eux.

### 5. Stokvis : la fuite du repli statique, retrouvée

Trois séances (30/06 → 02/07) où nous portons **490,00** contre **73,00** chez
l'opérateur. C'est la valeur figée de `static_fallback.json` documentée depuis
le 01/08 — la fuite est confirmée sur pièce.

## Ce qui reste incertain

### Ciments du Maroc : 20 séances sans explication

Du 11/05 au 11/06/2026, nos cours valent ~**5 000 DH** quand l'opérateur cote
~**1 690 DH**. La fenêtre recouvre presque exactement celle de MSA.

⚠️ Nos valeurs ne correspondent à **aucun** des sept exports disponibles. Je
ne nomme donc aucune société : un export du titre soupçonné trancherait, comme
il l'a fait pour Marsa Maroc. **Cause non établie.**

### Les petits écarts de fin juin à août

Présents sur les sept titres (23 à 49 séances chacun). Même profil que MSA et
MUT, même hypothèse non vérifiée — la capture en milieu de séance, corrigée le
10/08. Aucun remplacement proposé.

## Deux défauts de mon propre outillage, corrigés

1. il comparait Managem **sans ajuster le split** — 704 faux écarts ;
2. il proposait de **supprimer 68 séances** de HPS et de Managem, dont 67
   antérieures au premier jour de l'export. L'export ne les cote pas parce
   qu'il commence plus tard, pas parce qu'elles n'ont pas eu lieu. Les
   supprimer aurait détruit de l'historique valide.

Deux tests permanents interdisent désormais l'un et l'autre.

