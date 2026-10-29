# ADI, SMI et T2S — premier contrôle du 14 septembre 2026

**Travail partiel. Ce dossier n'est pas prêt pour application ou publication.**

Noure a fourni les historiques ADI et SMI du 15 septembre 2023 au 11 septembre 2026, et celui de T2S du 27 juillet au 11 septembre 2026, sous forme de texte dans la conversation. Le message complet reste la référence. Ce dossier conserve le bloc T2S et des extraits ADI/SMI; il ne prétend pas archiver ni vérifier les deux longs exports intégralement.

Base du contrôle : `059f02625cd6f73f0e959f9c94de65188409734a`.

## Résultats obtenus

- T2S : 29 dates uniques, OHLC cohérents, volumes enregistrés en nombres de titres. Aucun fichier `pipeline/candles/T2S.json` sur cette base. Un candidat de 29 bougies est conservé dans le dossier de travail.
- T2S au 11 septembre : clôture 226,80 DH; moyenne simple 20 séances 235,69; RSI14 de Wilder calculé indépendamment 19,74183066. Les moyennes 50 et 200 sont indisponibles. Les extrêmes observés sur ces 29 séances ne constituent pas un historique de 52 semaines.
- ADI : contrôle de 32 séances récentes, du 22 juillet au 11 septembre 2026, plus un exemple du 15 septembre 2023. 29 lignes en écart au total, dont 28 dans les 32 séances récentes. Le 11 septembre, le plus-bas du dépôt vaut 410 contre 409 dans le texte source. Le 15 septembre 2023, `v=6356129` correspond au montant MAD tronqué, alors que 63178 titres sont indiqués. Cela prouve un problème d'unité sur cette ligne, sans généralisation à toute la série.
- SMI : même sélection de 32 séances récentes, plus les exemples du 25 novembre 2025 et du 15 septembre 2023. 28 lignes récentes en écart. Le 11 septembre, plus-haut 6650 au dépôt contre 6690 dans la source; plus-bas 6586 contre 6583. Au 25 novembre 2025, la source laisse O/H/L/volume manquants, mais le dépôt contient une bougie et 4 titres; ces valeurs ne sont pas justifiées par cet export. La ligne du 15 septembre 2023 est absente du fichier historique actuel.

Les sources utilisent deux colonnes distinctes : `Volume (MAD)` et `Titres Échangés`. Le champ `v` du candidat T2S utilise la seconde. Les tirets restent des valeurs manquantes. Aucun prix n'est inventé. Aucune ligne du 14 septembre n'est remplacée par l'export terminé au 11 septembre.

## Vérification et limites

Sept contrôles JavaScript ont été exécutés dans la conversation : champs SMI manquants, séparation des unités, refus des doublons, refus d'une mauvaise identité, refus d'OHLC incohérents, absence de SMA50/200 avec 29 cours et bornes d'initialisation du RSI. Le script `verifier.cjs` reproduit les comparaisons et refuse des fichiers de référence modifiés.

**Le moteur Python n'a pas été exécuté pour ce lot : son environnement est devenu indisponible.** Les anciens 435 tests du lot MSA ne valident pas ce dossier. Le script Node n'a pas encore été exécuté depuis un checkout; les fonctions de calcul et comparaison ont été exécutées dans la conversation.

## Reprise

1. Archiver et comparer la totalité des historiques ADI/SMI déjà fournis dans la conversation; remplacer les extraits par les sources complètes sans perdre leur provenance.
2. Vérifier le registre d'identité T2S et les collecteurs quotidiens avant intégration.
3. Traiter explicitement les séances SMI sans détails; ne pas fabriquer d'OHLC ni de volume nul.
4. Construire les corrections complètes, puis recalculer uniquement les titres concernés dans le moteur existant.
5. Comparer cache initial, rafraîchissement seul et correction, vérifier les autres titres et conserver les protections CMT/SOT/SGTM.

Aucun fichier publié ni cache utilisé par le moteur n'est modifié par ce dossier. La PR MSA n°18 reste un lot distinct, encore ouvert lors du contrôle.
