# Décisions structurantes

Une décision par section : ce qui a été choisi, contre quoi, et pourquoi.

## D-01 · La suspension entre par un registre tenu à la main

**Contre** : la déduire des cours.

Un titre suspendu et un titre délaissé produisent les mêmes nombres. Aucune
statistique ne les sépare, parce que la différence n'est pas dans la série :
elle est juridique, publiée par le régulateur. Même nature que `SPLITS`, même
remède.

## D-02 · La suspension se juge à la date d'ANALYSE

**Contre** : la date du cours.

Circulaire : sur un titre suspendu, le dernier cours précède toujours la
suspension. La question « était-il suspendu le jour de son dernier cours ? »
ne peut recevoir qu'un non. `BVC_DATE_ANALYSE` permet de rejouer une décision
passée ; `BVC_MODE_AUDIT=1` rend une date invalide fatale.

⚠️ Cela ne transforme pas le moteur en simulateur historique. D'autres parties
utilisent l'horloge, et fixer la date de décision ne substitue pas les
informations de l'époque.

## D-03 · Un price-to-book non sourcé n'est pas affiché

**Contre** : garder la constante avec un drapeau.

L'étiquette ne corrige pas le chiffre. Sur Alliances elle inversait le sens de
l'information. 76 titres sur 80 perdent leur PB ; c'est le prix de l'honnêteté.

⚠️ Vérifié avant la bascule : `pb` n'entre pas dans le score v5.3. Nullifier
ne déplace donc aucune note — R8 est sauve.

## D-04 · Le zéro d'un secteur sans objet n'est pas une mesure

**Contre** : appliquer le correctif « zéro est une valeur » partout.

Les huit zéros de `dette_nette_ebitda` sont six banques, un assureur et une
société industrielle. Pour un établissement financier le ratio n'a pas de sens :
ce zéro est un remplissage. Le correctif naïf relevait 19 titres de +0,08 sur
la foi d'un blanc.

Le fichier ne permet pas de distinguer « mesuré à zéro » de « sans objet » —
les deux s'écrivent `0.0`. Limite de la DONNÉE, consignée plutôt que masquée.

## D-05 · La suite entière bloque avant publication

**Contre** : une sélection de tests bloquants.

Treize fichiers relisent les données publiées et restaient hors de l'ensemble
bloquant. Choisir lesquels méritent de bloquer, c'est refaire chaque semaine un
arbitrage qu'on finira par rater. Le coût est assumé : un test rouge suspend le
bulletin du matin.

## D-06 · Le dossier de réception est un programme, pas une procédure

**Contre** : la vigilance.

Trois livraisons refusées sur la forme. `pipeline/livrer_candidat.py` refuse un
arbre sale, extrait depuis les commits, empreinte les sources exécutées,
exécute la suite SUR le candidat, compare l'empreinte du fichier testé à celle
du fichier livré, et écrit le manifeste en LISANT les fichiers.

## D-07 · Le manifeste constate une compatibilité, pas une causalité

**Contre** : « toute différence est imputable au code ».

Des cours identiques ne prouvent pas que toutes les réponses reçues le soient.
Mesuré : sur une exécution, 79 cours identiques et **14 volumes différents**.
Un rejeu réellement figé demanderait d'enregistrer les réponses externes une
fois puis de servir exactement les mêmes aux deux moteurs. Ce n'est pas fait.

## D-08 · Un test qui ne peut pas se prononcer s'abstient

**Contre** : l'échec, et contre le silence.

`test_data_est_ignore_par_git` interroge git ; hors dépôt il ne peut rien
affirmer. Il échouait dans toute copie extraite, et je l'écartais à la main en
l'expliquant. **Un échec qu'on explique à chaque fois est un échec qu'on
finira par ne plus lire.** Il s'ignore désormais, avec sa raison inscrite au
rapport JUnit.

Corollaire appliqué à `parse_cdg_bulletin` : « 0 écart » pouvait signifier
« 0 comparaison ». Le compte des comparaisons est désormais affiché, et une
vérification sans comparaison est annoncée comme telle.
