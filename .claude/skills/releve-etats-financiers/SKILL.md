---
name: releve-etats-financiers
description: Relève l'historique des états financiers d'un titre (exercices depuis 2016, semestres depuis 2019) dans les documents officiels — AMMC, site de l'émetteur — chaque chiffre avec document, page, citation, unité et périmètre, au format de datasets/etats_financiers/<TICKER>.json. Lecture indépendante d'abord, comparaison à un tiers ensuite ; contre-vérification par échantillon avant toute PR. Utilisée par l'agent lecteur-comptes, contrôlée par verificateur-finance.
---

# Relever les états financiers d'un titre

Méthode fixée le 11/11/2026 après le lot 1 (ATW, IAM, ADI, LHM, MNG), pièges
complétés le 12/11 par le lot 2 (ADH, CSR, TGCC, MSA) : voir
`ERRORS.md`, famille 29, et `datasets/etats_financiers/README.md` (schéma).

## 0. Définition de terminé — à recopier dans la consigne de l'agent

Un titre est TERMINÉ quand :
1. `datasets/etats_financiers/<TICKER>.json` existe et passe
   `tests/test_etats_financiers_schema.py` ;
2. chaque cellule non nulle porte document, URL, sha256, page, citation,
   unité de la pièce, périmètre, statut ; chaque cellule nulle porte sa raison
   (« non publié », « document introuvable », « non lu dans ce lot ») ;
3. la comparaison à la source tierce est faite APRÈS la lecture, et chaque
   écart > 1 % est tranché pièce en main ;
4. `verificateur-finance` a relu un échantillon tiré au hasard (graine
   écrite, au moins 12 cellules par titre, valeur masquée) et le rapport dit
   l'effectif et les erreurs ;
5. la branche est poussée ; la PR n'est fusionnée qu'après ce contrôle.

## 1. Lire d'abord, comparer ensuite

**Jamais partir de la valeur d'un tiers** pour la chercher dans le PDF : cette
méthode confirme qu'un nombre existe dans la pièce, pas qu'il est sur la bonne
ligne (lot 1 : résultat d'exploitation COURANT pris pour le résultat
d'exploitation, signe inversé sur MNG 2019).

Pour chaque période : ouvrir l'état (compte de résultat, bilan, flux),
repérer la ligne par son LIBELLÉ EXACT et la colonne par sa DATE, lire la
valeur, PUIS seulement comparer.

## 2. Pièges connus

| Piège | Parade |
|---|---|
| « Résultat d'exploitation courant » / « Résultat opérationnel courant » | `resultat_exploitation` = ligne SANS « courant » ; la courante va dans `resultat_exploitation_courant` |
| EBITDA « ajusté », EBE de rapport de gestion (« * ») | `ebitda_ajuste`, indicateur non audité, jamais dans `ebe` |
| Unité : états en milliers de dirhams, communiqués en millions | `unite_source` = unité de la PIÈCE ; la valeur stockée est en MDH ; le test contrôle le rapport |
| Séparateur de milliers : espace OU point (« 1.603.939 »), parfois mêlés dans un même rapport | lire le nombre entier avec sa colonne, vérifier l'ordre de grandeur contre le chiffre d'affaires de la même table |
| Ordre des colonnes « ancien à gauche » (Managem 2020) | vérifier la colonne sur une valeur connue de la même table |
| Colonne comparative d'un document ultérieur (retraitement possible) | statut `lu_dans_document_ulterieur_comparatif` ; garder la valeur d'origine si elle est lisible |
| PDF en image, sans couche texte | le dire dans la cellule ; ne pas déduire |
| Dette nette | calcul avec `composantes_incluses` / `composantes_exclues` ; `dette_nette_publiee` à côté quand l'émetteur la publie ; jamais affichée seule |
| Intérêts minoritaires | stockés positifs (convention du README), même si la pièce les imprime en déduction |
| Nombre d'actions autour d'une opération sur titres | registre `SPLITS` / `HISTORIQUE_ACTIONS` de `bvc_config` (R11) ; réserve dans la cellule |
| Banque | PNB, RBE ; pas de dette nette |
| Liste AMMC « États financiers » incomplète | essayer l'URL directe `https://www.ammc.ma/sites/default/files/<Nom>_RFA_<AAAA>.pdf` et `_RFS_S1_<AA>` |
| Colonnes en ordre CROISSANT, et pas les mêmes d'un état à l'autre (Marsa Maroc S1 2022 : bilan « 31/12/2021 \| 30/06/2022 », compte de résultat « 30/06/2021 \| 30/06/2022 ») | lire l'en-tête de date de CHAQUE état, jamais déduire la colonne d'un état voisin |
| Colonne « proforma » en plus des deux périodes (TGCC S1 2025 : trois colonnes) | compter les colonnes sur l'en-tête ; prendre « les deux dernières » a donné le S1 2024 pour le S1 2025 |
| Flux retraités dans le document suivant (Marsa Maroc 2022 : flux d'exploitation 968,4 au rapport 2022, 1 501,4 en comparatif du rapport 2023) | garder la valeur du dépôt d'ORIGINE ; signaler l'écart dans la cellule |
| Sous-total mal libellé dans la pièce (Cosumar 2025 : « Autres produits et charges… non courants » imprimé sur le résultat des activités opérationnelles) | refaire l'addition des lignes au-dessus ; la ligne est celle que l'arithmétique désigne, le libellé fautif se cite en réserve |
| Signe des minoritaires qui change d'un document à l'autre (Addoha) | retenir le sens qui boucle « ensemble − part du groupe − minoritaires », et le dire dans la cellule |
| Dépôt en image (Marsa Maroc 2016-2017, coupure de presse Addoha 2016) | cellule vide « image sans texte » ; lire la colonne comparative du dépôt suivant seulement avec le statut comparatif |
| Société cotée récemment (TGCC, fin 2021) | aucun dépôt AMMC avant la cotation : « document introuvable », jamais un chiffre de prospectus présenté comme publié ; nombre d'actions d'avant l'introduction signalé non comparable |
| Dette nette publiée qui ne recoupe pas la nôtre (TGCC : titres de placement retranchés) | garder les deux, dire la différence de composantes ; une dette nette publiée dont le périmètre consolidé n'est pas établi n'est pas retenue (Cosumar) |
| Tableau des flux semestriel dont le comparatif est l'exercice précédent (TGCC S1 2022 : « 30/06/2022 \| 31/12/2021 ») | lire l'en-tête de date de CHAQUE état ; une valeur de semestre égale à celle de l'exercice de la même année est suspecte ; sans colonne 30/06, la cellule est vide |
| Dette nette après IFRS 16 (Cosumar 2019 : 86,7 de dettes de contrats à droit d'usage dans les dettes non courantes, 13,0 de dérivés dans les courantes) | retirer les dettes de location et les dérivés quand la pièce les isole (montants cités dans `composantes_exclues`), sinon réserve « comprend des dettes de location non isolées dans la pièce » |
| Dette de location absente du bilan mais chiffrée dans la note des dettes financières (TGCC, crédit-bail ; Sothema, « Dont crédit-bail » de la note 14 / 4.11) | lire la note avant de déclarer « non isolée » ; prendre chaque exercice dans SA propre pièce, la ventilation peut changer dans le comparatif suivant à total égal ; deuxième récidive (TGCC lot 2, Sothema lot 3) : ouvrir la note des dettes financières de CHAQUE exercice AVANT d'écrire toute réserve de location |
| Signe des minoritaires imprimé inversé d'un dépôt à l'autre (Sothema 2020-2023 et S1 2020-2024) | recalculer résultat net ensemble − part du groupe ; le signe qui boucle est retenu, la réserve dit le signe imprimé |
| Ligne « Résultat opérationnel » absente de l'état (Sothema 2021-2023) | somme de lignes publiées (courant + autres produits et charges opérationnels, dernier sous-total), statut calculé, dite dérivée ; vérifier par l'identité jusqu'au résultat net |
| Dividende dont le texte extrait perd le premier chiffre (Sothema « 8 MAD » pour 28) | rendre la page et lire ; la citation reprend le chiffre lu, la note le dit |
| Ligature « ﬁ » (« ﬁnancières ») et caractère « � » dans les libellés extraits | écrire les regex de libellé avec les variantes (`(fi\|ﬁ)`, `\S*`) ; un libellé introuvable n'est pas une ligne absente |
| Dette financière non courante = dette de location (Sonasid, note 23) | la retirer au chiffre du BILAN (123,192), pas au chiffre arrondi de la note (123,2) ; même règle partout où la note identifie les deux |
| Colonnes d'un en-tête que le texte extrait réordonne (Risma S1 2026 : texte « 30/06/26 » en premier, page rendue « 30/06/25 publié, 30/06/25 pro forma, 30/06/26 ») ; ancien exercice à gauche dans les rapports annuels Risma | rendre la page avant de choisir la colonne ; le même rapport peut ranger le compte de résultat et le bilan dans des sens différents |
| Unité qui change dans un même émetteur (Risma : KMAD jusqu'au S1 2023, MDH arrondis ensuite) ; minoritaires = ensemble − part du groupe arrondis, qui diffère de 1 de la valeur imprimée | `unite_source` par cellule ; stocker la valeur imprimée avec le signe qui boucle (le test d'unité exige le jeton) |
| Ligne seule dans une colonne (CMT « Trésorerie - Passif 3 192 138,82 ») : la colonne n'est pas imprimée | placer le montant par l'équilibre du bilan (total passif moins les autres masses) |
| Tableau des flux semestriel « 30/06/N \| 31/12/N-1 \| variation » (RDS, CMGP) | la 2e colonne est un exercice complet : elle donne le flux de l'exercice précédent en comparatif, jamais celui du semestre précédent |
| Compte de produits et charges social marocain à quatre colonnes dont les vides ne sont pas imprimées (SRM) | 3 jetons = propres, total, précédent ; 4 jetons = propres, antérieurs, total, précédent ; lire l'en-tête avant de choisir la colonne |
| Texte extrait à espaces parasites (RDS RFA 2023 : « (27 80 9) ») | le jeton se lit sans ses espaces intérieurs mais le libellé brouillé fausse les tests de citation ; rendre la page, citer ce qui est lu et le dire dans `note` |
| Libellé coupé sur deux lignes avec les montants entre les deux (Risma FY2024 flux d'investissement) | citer les trois fragments d'une seule chaîne |
| Retraitement silencieux d'un comparatif (RDS : changement de méthode de reconnaissance du chiffre d'affaires, 2024 : −79,7 retraité contre −82,8 d'origine) | garder la valeur du dépôt d'origine et mettre la valeur retraitée en réserve |
| Communiqué ou page d'un autre format dans le rapport (SRM RFA 2019 : CA semestriel 130,9 à la p.106, états annuels p.109) | repérer la page des états de synthèse de l'exercice avant de conclure qu'un chiffre est étranger ; lire le sha256 et la page du dépôt d'origine |
| Deux lignes « TOTAL III » sur la même page de bilan (trésorerie actif et trésorerie passif, SRM 2020) | citer le libellé de la masse (« TRÉSORERIE - PASSIF »), jamais un « TOTAL » seul ; relire la colonne et la masse pièce en main |

## 3. Contre-vérification (verificateur-finance)

Tirage stratifié par métrique et par période, graine écrite, au moins 12
cellules par titre, en priorité les statuts à risque
(`lu_dans_document_ulterieur_comparatif`, `calcule_depuis_composantes_publiees`,
`signe_a_verifier`, `consolide_presume`). Pour chaque cellule : lire la pièce
SANS regarder la valeur du fichier, puis comparer. Le rapport donne
l'effectif exact ; il ne conclut pas au-delà de l'échantillon.

Une erreur trouvée ⇒ chercher sa CAUSE, la corriger sur toutes les cellules
qu'elle touche, l'ajouter au tableau ci-dessus, puis second contrôle.

## 4. Jamais

- recopier une valeur tierce sans l'avoir lue dans la pièce ;
- désactiver la vérification TLS (le site de la Bourse se lit avec
  Playwright, pas avec `curl -k`) ;
- écrire dans le dépôt principal : l'agent travaille dans son arbre et pousse
  sa branche ;
- fusionner sa propre PR.
