# Lot candidat MSA — 22 séances contaminées

État : **candidat vérifié, non appliqué aux données servies**.
Base : `50ce655486431e2986af9d62691df21e2ea735c7` (publication du 13 septembre 2026).
Branche locale : `codex/msa-22-candidat`.

## Ce que contient ce lot

Les 22 clôtures MSA du 13 mai au 16 juin 2026 correspondent exactement à
l'export Mutandis. Les deux exports portent leur identité sur chacune de leurs
735 lignes : `MSA / SODEP-Marsa Maroc` et `MUT / MUTANDIS SCA`.
Le générateur vérifie les empreintes des sources, leur identité et chaque
valeur avant remplacement. Un état initial différent entraîne un refus.

La copie candidate remplace **110 valeurs OHLCV sur 22 séances**. Elle conserve
les **569 dates** et toutes les autres lignes. `journal.json` conserve chaque
ancienne bougie à côté de la proposition, de l'identité et de l'empreinte de sa
source. Les prix sont ceux de l'export, sans coefficient supplémentaire.
Le champ `v` désigne les titres échangés sur ces 22 lignes ; le montant en MAD
reste distinct. La base de prix et l'unité des autres lignes ne sont pas
certifiées par ce lot.

Les données sources se trouvent dans `datasets/historiques_candidats/MSA_22/sources/`.
Les résultats se trouvent dans `datasets/historiques_candidats/MSA_22/resultat/` :

- `MSA.json` : la série candidate entière, utilisable par le graphique ;
- `journal.json` : les 22 différences détaillées et leur provenance ;
- `cache_MSA_initial.json`, `cache_MSA_recalcule.json`, `cache_MSA_candidat.json` :
  les trois états de l'entrée MSA, avec la copie de 250 bougies du cache ;
- `rapport.json` : périmètre, empreintes et différences d'indicateurs ;
- `verification_moteur.json` : comparaison du parcours complet du moteur.

## Effet mesuré

Les vingt champs produits par `compute_indicators` sont recalculés pour MSA
seulement. La copie de 250 bougies contenue dans cette entrée est également
actualisée. Aucun cache global ni fichier servi n'est écrit.

Trois exécutions de `update_data.run(dry_run=True, push=False)` ont comparé :
A, le cache publié ; B, son recalcul sur la série initiale ; C, le recalcul sur
la série candidate. A et B ne diffèrent pas sur les valeurs rendues.

| Champ MSA | A / B | C candidat |
|---|---:|---:|
| Cours | 860,10 | 860,10 |
| RSI | 52,5 | 47,9 |
| MA200 | 810,25 | 875,64 |
| Plus-bas 52 semaines | 225,00 | 702,10 |
| Plus-bas 90 jours | 231,10 | 841,00 |
| MACD | 8,6495 | 1,0876 |
| Signal MACD | 11,6150 | 0,6424 |
| Histogramme MACD | −2,9656 | 0,4452 |
| ADX | 36,4 | 21,0 |
| Score technique | 4,2 | 5,2 |
| Score v5.3 | 5,87 | 6,07 |

Les champs de prix, variation, volume du jour, capitalisation et ratios restent
identiques entre les trois exécutions. Les **79 autres titres sont identiques
champ par champ**. CMT reste à 4 350 DH, RSI 42,0 et 681 bougies ; Sothema
conserve `h52w = 380`, SGTM `l52w = 508,1`.

L'OBV calculé passe de 20 503 021 à 20 300 631. Ce changement est mécanique :
**son interprétation reste non validée**, car l'unité des volumes de toute la
série n'est pas établie. Les indicateurs et scores présentés ici décrivent la
série partiellement corrigée ; ils ne certifient pas sa fiabilité complète.

## Portée de la vérification

Le moteur exécuté est celui de la base publiée. Ses seules interfaces de
collecte sont remplacées par des réponses fixes construites depuis le
`data.json` publié. L'historique Médias24 est vide pour exercer le chemin du
cache. L'horloge est fixée au 13 septembre 2026 ; le recalcul du cache utilise
minuit, la comparaison du moteur 16:54:19 UTC. Ces heures sont identiques
entre les variantes respectives. Aucun appel HTTP n'a été effectué et le
dry-run n'a écrit aucun fichier JSON dans ses copies de travail.

Il s'agit d'un **contrôle d'intégration hors réseau**, pas d'un rejeu des
réponses brutes des fournisseurs, d'une exécution GitHub Actions ou d'une
vérification du site après publication.

La suite locale compte **435 tests réussis**, dont 11 nouveaux cas couvrant
le périmètre exact, les quantités distinctes des montants, les données non
finies ou incohérentes, l'identité même après changement d'empreinte, le refus
d'un état initial différent et la préservation des fichiers servis.
Les fixtures de ces tests sont figées pour qu'une actualisation quotidienne
de `main` ne change pas silencieusement leur scénario.

## Reproduction

Installer les dépendances de développement et du moteur prévues par le dépôt.
Depuis cette branche, sur la base indiquée :

```bash
python pipeline/preparer_msa.py --date-calcul 2026-09-13 --sortie datasets/historiques_candidats/MSA_22/reproduction
python pipeline/verifier_candidat_msa.py --instant 2026-09-13T16:54:19+00:00 --candidat datasets/historiques_candidats/MSA_22/reproduction
python -m pytest -o addopts= -q
```

Le premier programme refuse d'écraser une sortie existante ou d'écrire dans
les dossiers servis. Le second vérifie les empreintes du candidat et de ses
entrées avant de lancer les comparaisons. Si la base a évolué, il faut
reconstruire le candidat et refaire la mesure, sans reprendre les anciens
chiffres.

## Travail restant

La confrontation de cette copie à l'export MSA laisse **27 écarts de clôture**
du 18 juin au 3 août 2026. Les séances négociées des **22, 23 et 24 juin** restent
absentes. Le **30 juillet** reste présent chez nous et absent de cet export ;
aucune suppression n'est effectuée par ce programme. Les lignes antérieures
au début de notre série ne sont pas classées comme séances manquantes.

Ce lot ne remplace pas l'assainissement de Sothema, les autres corrections
historiques ou le correctif du message superposé au graphique.

La mise en ligne nécessitera une réception du candidat, puis une application
ciblée de MSA avec recalcul complet de sa seule entrée de cache.

## Contrôle de livraison du 14 septembre 2026

L'accès GitHub en écriture a été vérifié par la création de la branche
`codex/msa-22-candidat` et le transfert de ses fichiers. Cette livraison reste
un dossier candidat ; elle ne modifie ni le moteur publié ni les fichiers servis.

La base contrôlée est `688ce1ad3ee31416f2d7925eee563ababf924d22`, dont le
`data.json` est daté du 14 septembre à 11:50:29 (Casablanca). La série MSA
possède désormais 570 bougies, avec une bougie du jour encore en séance.
Les fichiers `resultat/` conservent les preuves figées du 13 septembre.
Le nouveau contrôle est enregistré dans `docs/REVALIDATION_MSA_20260914.json`.

Une reconstruction du candidat sur cette base confirme 22 remplacements,
110 valeurs et aucune date ajoutée ou supprimée. Les trois exécutions du
moteur conservent les 79 autres titres, ainsi que prix, variation, volume et
capitalisation MSA. Les fichiers servis sont identiques avant et après.
Les **435 tests locaux passent** sur cette base.

Cette fois, le simple rafraîchissement du cache (A vers B) change notamment
le RSI de 52,5 à 52,9 et la MA200 de 810,25 à 809,75. L'effet propre des
22 corrections (B vers C) porte le RSI de **52,9 à 48,4**, la MA200 de
**809,75 à 875,15**, l'ADX de **35,9 à 21,1** et le score technique de
**4,2 à 5,2**. Les anciens chiffres ne doivent donc pas servir de valeurs
attendues pour une publication future.

CMT reste à 4 350 DH, RSI 42,0 et 681 bougies ; SOT conserve 380 et SGTM
508,1 pour les extrema surveillés. Les limites sur les autres écarts MSA
et les unités de volume restent valables. Ce contrôle local hors réseau
ne vaut pas exécution GitHub Actions ni validation de la collecte du jour.
