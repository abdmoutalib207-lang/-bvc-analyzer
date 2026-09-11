# Journal des transformations — lot 1B.2

> Ce qui a été appliqué aux données, ce qui ne l'a PAS été, et pourquoi.
> Une transformation absente de ce journal n'a pas le droit d'exister dans le
> code.

## Les deux couches, et ce qui les sépare

| | `datasets/lot1a/` | `datasets/lot1b/` |
|---|---|---|
| Nature | **instantané** | **couche dérivée** |
| Contenu | copie octet pour octet de `pipeline/candles/` | mêmes valeurs + qualification |
| Valeurs de prix et de volume | intactes | **intactes** |
| Ce qui s'y ajoute | rien | statuts, niveau de preuve, usages admissibles, **motif de chaque refus** |
| Régénérable | non — il est figé | oui, par `pipeline/normaliser.py` |

**⚠️ Réserve de vocabulaire.** Ni l'une ni l'autre ne contient de **données
brutes fournisseur**. Le dépôt ne conserve **aucune charge utile de source**.
L'expression est réservée aux charges utiles effectivement conservées ; nous
n'en gardons aucune. C'est une lacune, pas une convention.

## Les cinq usages, et pourquoi ils sont séparés

| Usage | Ce qu'il autorise |
|---|---|
| `prix_analyse` | valoriser, comparer, mesurer une variation |
| `volume` | mesurer une quantité échangée |
| `indicateur` | alimenter un calcul de série **publiable** |
| `indicateur_exploratoire` | calculer **pour voir**, en signalant les limites |
| `execution_simulee` | rejouer une **comptabilité cohérente** prix × quantité |

### Trois situations, trois issues — et non deux

Une première version bloquait tout calcul dès qu'une base restait incertaine.
C'était trop : elle empêchait des essais utiles. La revue a précisé la règle.

| Situation | Issue |
|---|---|
| valeurs invalides, ou fenêtre traversant une anomalie non résolue | **refuser**, avec le motif |
| valeurs exploitables, provenance ou ajustement incomplets | **calcul exploratoire**, explicitement signalé |
| fenêtre qualifiée pour l'usage demandé | **permettre**, dans le périmètre documenté |

⚠️ Un calcul exploratoire n'alimente **ni** le signal officiel, **ni** une
probabilité, **ni** une performance présentée comme validée. C'est sa raison
d'être : pouvoir essayer sans pouvoir tricher.

### Exécution simulée — ce qui est exigé, et ce qui ne l'est pas

`execution_simulee` **n'exige pas** que les prix soient ajustés. Elle exige que
prix et quantités racontent la **même histoire** : ou bien des prix
effectivement cotés avec les opérations traitées explicitement, ou bien une
représentation transformée dont **toutes** les grandeurs suivent. Ce qui est
refusé, c'est le mélange — un cours divisé par dix multiplié par une quantité
qui ne l'a pas été.

⚠️ Et cette admissibilité **ne prouve pas** qu'un ordre aurait été exécuté. La
liquidité et les règles de remplissage appartiennent au protocole de backtest,
pas à la qualification des données.

### La preuve sur les prix ne vaut pas preuve sur les quantités

Deux registres distincts, deux provenances. `quantite_comparable()` acceptait
le niveau de preuve des **prix** pour lever la réserve sur les **volumes** :
c'était un raccourci. Le registre `BASES_QUANTITES` est vide, et l'unité
« nombre de titres » y est déclarée **présumée, non établie**.

## Transformations APPLIQUÉES

### T1 — Qualification des observations

Chaque ligne reçoit : l'état de ses quatre prix, la cohérence de son invariant
OHLC, l'état de son volume, le statut de sa séance, le niveau de preuve de sa
base de prix, le statut réglementaire de son amplitude, les usages accordés et
**le motif de chaque refus**.

**Effet sur les valeurs : aucun.** Vérifié observation par observation contre
l'instantané.

### T2 — Amplitude : ce qu'elle mesure, et ce qu'elle ne prouve pas

Une version antérieure répondait « conforme » et écrivait « licite sous tous
les régimes connus ». **C'était un verdict réglementaire rendu par une fonction
qui n'en a pas les moyens.** La revue l'a démontré :

> référence 100 · ouverture et plus-bas 200 · plus-haut 201 · clôture 200

Le rapport plus-haut / plus-bas vaut 1,005 — amplitude minuscule, donc
« conforme ». Sous ±20 % autour de 100, ces prix sont pourtant **tous** hors
bornes. La fonction ne reçoit pas le cours de référence : elle voit de combien
les prix s'écartent entre eux, jamais **où** ils se situent.

Second défaut de portée, plus large encore : la source citée n'entre en vigueur
qu'au 23/06/2026, et **3 999 de nos 4 306 observations lui sont antérieures —
93 %**. L'étiquette réglementaire était apposée sur des données que le texte
invoqué ne couvre pas.

**Les deux questions sont désormais séparées.**

| Fonction | Répond à | Exige |
|---|---|---|
| `evaluer_amplitude` | de combien les prix s'écartent **entre eux** | la bougie seule |
| `evaluer_conformite` | respectent-ils la limite **autour de la référence** | référence + régime + période de validité |

`evaluer_amplitude` rend trois états, et **aucun n'est un verdict de
conformité** :

| Statut | Quand | Effet sur les usages |
|---|---|---|
| `compatible avec l'enveloppe testée` | sous l'enveloppe la plus étroite | rien — ⚠️ compatible ≠ conforme |
| `enveloppe non concluante` | entre les deux enveloppes | **ne refuse rien** |
| `hors enveloppe testée — alerte de cohérence` | au-delà de l'enveloppe la plus large | écarte l'observation |

Chaque résultat porte `conformite_reglementaire`, qui vaut **toujours** « non
vérifiable » aujourd'hui et **nomme ce qui manque** — à commencer par le cours
de référence, qu'aucune de nos chandelles ne conserve.

Répartition sur les 4 306 bougies : **4 292 compatibles, 13 non concluantes,
1 alerte**.

> ⚠️ **L'alerte qualifie l'amplitude, jamais sa cause, jamais sa légalité.**
> Elle ne s'appuie sur aucun texte — elle vaut donc à toute période, y compris
> avant l'entrée en vigueur de la circulaire. Un test vérifie que le résultat
> ne contient aucun des mots « base », « split », « opération », « ajust ».

**Source des seuils** : circulaire AMMC du 25/06/2026 (±10 % en continu, ±6 %
au fixing, ±20 % pendant les cinq premières séances suivant l'admission),
**relayée par la revue et NON vérifiée par nous sur le texte original**.
`verifie_sur_source_primaire` vaut `False` et doit le rester.

### T3 — Qualification par fenêtre datée et par besoins réels

`pipeline/fenetre.py`. Deux principes :

- **par fenêtre**, pour ne pas exiger de certifier tout l'historique d'un titre
  avant de calculer quoi que ce soit ;
- **par besoins**, parce qu'une moyenne de clôtures n'exige pas les colonnes
  OHLC, tandis qu'un indicateur de volume doit vérifier leur disponibilité
  **et** leur comparabilité.

Surdéclarer un besoin refuse des calculs légitimes ; le sous-déclarer calcule
sur des champs absents. Les deux sont des fautes, la seconde est pire.

## Transformations NON APPLIQUÉES — et la raison

### N1 — Ajustement des opérations sur titres

**État : NON APPLIQUÉ.** Aucun prix n'a été divisé, multiplié ni recalé.

Les diagnostics portent désormais un **niveau de preuve**, et séparent trois
choses qui étaient confondues : le **fait observé**, l'**hypothèse** qu'on en
tire, et la **pièce qui manque**.

| Titre | Niveau | Fait observé | Hypothèse | Ce qui manque |
|---|---|---|---|---|
| **MNG** | ajustement probable, à confirmer | rapport des clôtures 24/07 → 27/07 = 1,091, sans discontinuité | la division par 10 a été appliquée une fois | le journal des écritures. La continuité montre qu'une division a eu lieu ; elle ne prouve pas qu'elle n'a eu lieu qu'**une** fois |
| **SOT** | base incohérente ou suspecte | rapport 04/05 → 05/05 = 5,000 ; ouverture du 05/05 incompatible avec sa clôture ; niveau médian antérieur 5× trop bas | double division par 5 | une source primaire pré-split. Ni l'hypothèse ni sa **portée exacte** ne sont établies observation par observation |
| 5 autres | état inconnu | aucun diagnostic conduit | — | un diagnostic |

> ⚠️ **« Aucune opération au registre » ne prouve rien.** Le registre `SPLITS`
> recense ce que nous y avons inscrit, pas ce qui s'est produit. Il n'établit
> ni l'absence d'opération sur tout l'historique, ni la validité des bases. Le
> défaut est donc « état inconnu », pour tout le monde.

**Conséquence, mesurée dans les artefacts** (`docs/BILAN_LOT1B.md`) :
« état inconnu » interdit l'usage `indicateur` **publiable**, mais autorise
l'`indicateur_exploratoire`. Aucun des 7 titres n'a d'indicateur publiable ;
6 sur 7 ont un exploratoire.

⚠️ Une version antérieure annonçait un titre de moins que ce que les fichiers
montraient. Le bilan est désormais **généré** par `pipeline/bilan_lot.py`, qui
lit `datasets/lot1b/` ; un test vérifie qu'il n'a pas vieilli, et un autre
interdit la formulation fautive dans la documentation.

### N2 — Comblement des trous de calendrier

**État : NON APPLIQUÉ.**

L'entrée du **14 août 2026** était marquée « fermé », justifiée par « 71
clôtures sur 71 identiques à la veille, recoupé au bulletin CDG ». C'est
exactement le raisonnement que la revue avait écarté, **réintroduit sous forme
de source**. Elle est déclassée en `non_confirme`.

Les deux éléments dont nous disposons sont conservés comme **indices**, chacun
marqué `vaut_preuve: false` :

1. l'observation des 71 clôtures — compatible avec une fermeture, une
   rediffusion par la source, ou une panne de collecte ; n'établit aucune des
   trois ;
2. l'entrée `(8, 14)` de `JOURS_FERIES_FIXES` — registre du projet, sans
   citation, et un férié national n'établit pas par lui-même la fermeture de la
   Bourse.

**Pièce qui trancherait** : le calendrier officiel des séances de la Bourse de
Casablanca, ou un bulletin CDG couvrant le 13 au 17/08/2026.

Le fichier ne contient donc **aucune date « fermée » établie** et une seule
date « ouverte ».

### N3 — Modification de la formule de score

**NON APPLIQUÉ**, hors périmètre. R8, et instruction de revue explicite.

## Défauts corrigés dans cette passe

| Défaut | Relevé par | État avant |
|---|---|---|
| Ouverture et clôture absentes ⇒ tous les usages, exécution comprise | revue | un volume positif suffisait |
| Base « inconnu » ⇒ exécution autorisée | revue | — |
| Volume `+∞` classé « mesuré » | revue | le test portait sur NaN et le signe ; l'infini passe les deux |
| Amplitude : seuil 1,222 tenu pour universel | revue | une bougie `h=120, l=80`, licite sous ±20 %, était déclarée impossible |
| Calendrier : le 14 août déclaré fermé sur des cours immobiles | revue | raisonnement écarté, revenu comme source |
| Diagnostics énoncés comme des faits | revue | « ajusté une fois », « double division » sans niveau de preuve |
| **Invariant OHLC rompu ⇒ tous les usages** | trouvé en vérifiant les siens | `l=99 > h=5` passait intégralement |
| **Couverture calculée sur les lignes reçues** | trouvé en vérifiant les siens | une fenêtre de 60 avec **une** observation ressortait à 100 % |
| **Bougie pile à la limite déclarée suspecte** | trouvé en corrigeant l'amplitude | `1.2/0.8 = 1.4999999999999998` en flottant, contre `120/80 = 1.5` |
| **« Non concluant » refusait l'indicateur** | trouvé en relisant ma propre correction | convertissait notre ignorance en verdict |

Sur la couverture : la correction **n'a déplacé aucun chiffre publié** — les
73 médianes de l'inventaire restent calculables et identiques, la série la plus
courte comptant 50 lignes pour une fenêtre de 60. Elle aurait faussé la
première fenêtre réellement creuse.

## Ce que le lot ne démontre pas

- **Aucune performance.** Aucun rendement n'est mesuré ici.
- Pas que les prix sont **exacts** : il déclare sur quelle base ils s'expriment,
  et avec quel niveau de preuve.
- Pas que SOT soit exploitable ni MNG sain — il rend l'état des deux **lisible**.
- **Aucune observation du lot n'autorise l'exécution.** Constat, pas objectif :
  aucune série ne porte d'ajustement documenté.
