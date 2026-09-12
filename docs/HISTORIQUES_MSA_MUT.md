# Marsa Maroc et Mutandis — ce qui concorde, ce qui diverge, ce qui reste incertain

> ⚠️ **Aucune correction n'est appliquée.** Les propositions sont dans
> `datasets/historiques_candidats/`, jamais dans `pipeline/candles/`.

```
python pipeline/confronter_historique.py  MSA MUT --ecrire
python pipeline/corrections_candidates.py MSA MUT --ecrire
```

## Les pièces, conservées intactes

| titre | fichier | octets | sha256 |
|---|---|--:|---|
| MSA | `b6dbe71c-Cours_MSA___2023-09-13_2026-09-12.csv` | 72 047 | `f4dba91cebc5d0da2f42fb42476dcc25…` |
| MUT | `a7f52999-Cours_MUT___2023-09-13_2026-09-12.csv` | 66 021 | `8e0e82bb89a5aa4aa3191b52dd9c9dd4…` |

Originaux dans `sources/MSA/` et `sources/MUT/`, chacun avec sa
`.provenance.json`. Ils ne sont jamais modifiés.

## L'identité, établie AVANT tout rapprochement

| titre | `Instrument` porté | `Ticker` | constant sur | autorisation |
|---|---|---|--:|---|
| MSA | **SODEP-Marsa Maroc** | `MSA` | 735 lignes | nom exact |
| MUT | **MUTANDIS SCA** | `MUT` | 735 lignes | nom exact |

Contre-épreuve : présenter « MUTANDIS SCA » pour MSA est **refusé** —
*« LE FOURNISSEUR A RENVOYÉ UNE AUTRE ENTREPRISE »*. C'est cet ordre qui
manquait en juin : on rapprochait des séries en supposant qu'elles désignaient
la même société.

## Colonnes et unités

| champ | colonne | unité |
|---|---|---|
| cours | `Ouverture`, `Dernier Cours`, `Plus Haut`, `Plus Bas` | dirhams |
| **montant échangé** | `Volume (MAD)` | **dirhams** |
| **quantité** | `Titres Échangés` | **nombre de titres** |
| activité | `Nb Transactions` | nombre |
| taille | `Capitalisation` | dirhams |

⚠️ **Les deux grandeurs restent distinctes.** Aucune conversion n'est
appliquée, nulle part.

## ═══ CE QUI CONCORDE ═══

| | MSA | MUT |
|---|--:|--:|
| séances communes | 568 | 71 |
| clôtures identiques | **519 (91,4 %)** | **46 (64,8 %)** |
| écarts > 20 % | 22 | **0** |

Hors la fenêtre de contamination, **l'historique de MSA concorde à 95,6 %**
(519 sur 543).

## ═══ CE QUI DIVERGE ═══

### 1. La contamination de juin est ÉTABLIE — 22 séances sur 22

`2026-05-13 → 2026-06-16`

| | concordance |
|---|--:|
| notre MSA = cours **Marsa Maroc** de l'opérateur | **0 / 22** |
| notre MSA = cours **Mutandis** de l'opérateur | **22 / 22** |

```
séance        NOUS (MSA)     op. MSA     op. MUT
2026-05-13        239.00      843.00      239.00
2026-06-16        235.00      868.00      235.00
```

Ce n'était jusqu'ici qu'un faisceau. Deux exports, chacun portant son
instrument **sur la ligne du cours**, le transforment en fait : pendant cinq
semaines, `pipeline/candles/MSA.json` a porté les cours de Mutandis.

Cause connue : `MANUAL_MAP` identifie par NOM ; l'entrée a été corrigée le
23/06/2026 (commit `48b3c583`) **sans que la donnée abîmée le soit**.

### 2. Trois séances manquent — les deux titres

`2026-06-22`, `2026-06-23`, `2026-06-24` : cotées par l'opérateur, absentes de
notre historique. C'est la panne de collecte déjà relevée (9 séries sur 74).

### 3. Une séance que nous sommes seuls à porter

`2026-07-30`, sur **72 de nos 74 titres**, dont 59 avec
`ouverture = plus-haut = plus-bas = clôture`. L'opérateur cote le 29 et le 31,
**pas le 30**.

⚠️ Le détecteur de séance fantôme ne pouvait pas la voir : il exige que le
marché rediffuse la veille à 95 %. Mesuré ici : **31,9 %**. C'est une **autre
espèce de fantôme** — des prix qui varient, un jour sans cotation.

Le 30/07 est la Fête du Trône. ⚠️ Nous n'avons aucun calendrier officiel des
fériés : **l'absence de cotation est un fait, l'attribution est une hypothèse.**

### 4. Le champ « v » ne suit pas la même grandeur d'un titre à l'autre

| titre | suit le **montant MAD** | suit le **nombre de titres** |
|---|--:|--:|
| ADH, CSR (mesuré le 11/09) | **92 %** | — |
| **MSA** | **0 %** | **90,3 %** |
| **MUT** | 1,4 % | 54,9 % |

⚠️ **C'est un résultat nouveau et gênant.** Nous savions le champ instable dans
le temps ; il l'est aussi **d'un titre à l'autre**. Deux titres suivent les
dirhams, un autre les quantités. Toute lecture globale de `v` — OBV en tête —
reste donc refusée, et cette mesure ne s'étend à aucun autre titre.

## ═══ LE REMPLACEMENT DE LA FENÊTRE, DOCUMENTÉ ═══

`datasets/historiques_candidats/journal_MSA_2026-05-13_2026-06-16.json`

**22 séances, cinq champs, l'ancien état conservé à côté du proposé.**

| | o | h | l | c | v |
|---|--:|--:|--:|--:|--:|
| champs modifiés | 22 | 22 | 22 | 22 | 22 |
| absents dans l'export | 0 | 0 | 0 | 0 | 0 |

```
2026-05-13   brut 843.00 · base retenue 843.00 · nous 239.00 · rapport 0.2835
   o: 239.0 → 850.0   h: 240.5 → 864.9   l: 239.0 → 843.0
   c: 239.0 → 843.0   v: 659   → 5857
```

⚠️ **L'ancien état ne dépend d'aucune sauvegarde extérieure** : chaque ligne
porte `ancien` à côté de `propose`, et rien n'est écrit dans
`pipeline/candles/`. Marsa Maroc n'ayant subi aucune opération sur titres, la
base brute et la base retenue sont ici la même série — c'est dit, pas supposé.

## ═══ CE QUI PEUT ÊTRE CORRIGÉ ═══

Dans `datasets/historiques_candidats/`, **non appliqué** :

| titre | proposition | séances | niveau de preuve |
|---|---|--:|---|
| MSA | **remplacer** `2026-05-13 → 2026-06-16` | 22 | `etabli_par_la_mesure` |
| MSA · MUT | **ajouter** `2026-06-22 → 24` | 3 | `etabli_par_la_mesure` |
| MSA · MUT | **retirer** `2026-07-30` | 1 | `etabli_par_l_absence` |
| MSA | **signaler** 27 écarts | 27 | `hypothese_a_confirmer` |
| MUT | **signaler** 25 écarts | 25 | `hypothese_a_confirmer` |

## ═══ CE QUI RESTE INCERTAIN ═══

**Les 52 petits écarts de fin juin à août.** MSA : médian 2,05 %, hors
contamination de −1,54 % à +0,76 %. MUT : médian 0,61 %, max 3,94 %.

La piste du **décalage de date est écartée par la mesure** : sur 22 séances de
juillet, 16 ne correspondent ni au jour, ni à la veille, ni au lendemain de
l'opérateur.

⚠️ **Hypothèse nommée, non vérifiée** : jusqu'au 10/08/2026, la bougie du jour
se figeait sur le premier run et gravait un cours de **milieu de séance** comme
clôture — 57 bougies fausses sur 72 le jour où le défaut fut mesuré. Ces écarts
sont antérieurs au correctif. **Rien ne l'établit ici**, et aucun remplacement
n'est proposé : corriger sur une hypothèse reviendrait à réécrire l'historique
sur une conviction.

**Ce que l'export n'établit pas** : qu'il ait raison. C'est la publication de
l'opérateur, la source la plus proche du marché dont nous disposions — pas une
preuve d'exactitude.

**Les 164 séances antérieures au 13/05/2024** (MSA) et **661** (MUT) sont une
profondeur que nous n'avons pas, pas un défaut. Elles restent disponibles si la
profondeur devient un objectif.
