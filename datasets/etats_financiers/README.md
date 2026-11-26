# États financiers publiés — historique par titre (lot 1 : ATW, IAM, ADI, LHM, MNG)

Un fichier par titre, `<TICKER>.json`. Chaque valeur est **relue dans un document officiel** (AMMC) :
document, page, ligne citée. ms-screener ne sert que de **repère** (quel document, quelle page) et de
**contrôle** ; aucune de ses valeurs n'est recopiée sans avoir été retrouvée sur une ligne du PDF.

## Méthode (et sa limite)

1. Les PDF sont téléchargés depuis les listes « États financiers » de l'AMMC par émetteur
   (`/fr/liste-etats-financiers-emetteurs?field_emetteur_target_id_verf=<id>`), sha256 calculé.
2. Pour chaque cellule, le texte des pages (`pdftotext -layout`) est parcouru : on retient la ligne dont
   le **libellé** correspond ET qui porte le nombre attendu (échelle KMAD / MMAD / MAD détectée à la ligne).
   Le document de la période est essayé d'abord, puis celui de la période suivante (colonne comparative).
3. **Limite assumée** : la recherche part de la valeur de ms-screener. Un chiffre de ms-screener qui
   n'est PAS sur une ligne du PDF ressort `non_verifie` (valeur `null`, la valeur ms est gardée dans
   `controle_ms.ms_valeur`), il n'est jamais écrit comme fait. Les erreurs de ms-screener qui restent
   sur une ligne de la pièce ne peuvent donc pas être détectées par cette méthode, sauf pour l'EBE
   (voir ci-dessous) : elles sont à rechercher dans un lot ultérieur par lecture indépendante.
4. Les retraitements ne sont détectés que lorsque la valeur de ms-screener (souvent lue dans la colonne
   comparative du rapport suivant) diffère de celle du document d'origine. Pas de détection systématique.
5. EBE des non-financières : lu sur la ligne **EBITDA / Excédent brut d'exploitation imprimée** par
   l'émetteur, dans la même colonne que le chiffre d'affaires déjà vérifié sur la même table ; ms-screener
   fournit un EBE parfois *dérivé* (écarts consignés avec `controle_ms.resultat = "ecart"`).
6. Dette nette : jamais lue telle quelle sauf si publiée ; sinon calculée comme somme signée de
   **composantes publiées** (chacune avec document/page/citation), formule dans `formule`.

## Schéma

```
{ "schema": "etats_financiers/1", "ticker", "nom", "emetteur_ammc_id", "unite": "MDH",
  "perimetre_principal": "consolide", "archetype": "bank|standard_nonfin|real_estate|…",
  "documents": { "<fichier>": { "fichier", "url", "page_emetteur_ammc", "sha256", "octets", "pages",
                                "type": "FY|H1", "annee_nom_fichier" } },
  "periodes": { "FY2016"…"FY2025", "H1-2019"…"H1-2026": {
      "type": "annuel|semestriel", "cloture": "AAAA-MM-JJ",
      "donnees": { "<metrique>": <cellule> } } },
  "couverture": { "remplies", "attendues", "ecarts" } }
```

Champs supplémentaires (hors des 12 métriques) : `resultat_exploitation_courant` (ligne « Résultat d'exploitation courant », avant éléments non courants ; `resultat_exploitation` est la ligne « Résultat d'exploitation » / « Résultat des activités opérationnelles » APRÈS non courant), `ebitda_ajuste` (indicateur de gestion non audité publié au rapport de gestion — EBITDA parfois « ajusté » d'IAM, EBE de gestion d'ADI et de Managem « * » ; `ebe` ne contient que l'EBE des états de synthèse, donc `null` pour ces titres), `dette_nette_publiee` (endettement net tel que l'émetteur l'écrit, quand il le publie ; `dette_nette` reste le calcul du projet sur composantes citées, avec `composantes_incluses` / `composantes_exclues`).

Métriques : `chiffre_affaires` (PNB pour une banque), `ebe` (RBE pour une banque), `resultat_exploitation`,
`resultat_net_ensemble`, `resultat_net_part_groupe`, `interets_minoritaires`, `capitaux_propres_part_groupe`,
`dette_nette` (sans objet pour une banque), `flux_exploitation`, `flux_investissement`, `nombre_actions`,
`dividende_par_action_propose`.

Cellule renseignée : `valeur_mdh` (MDH, signe selon la « Convention de signe » ci-dessous ; les montants par action ou en nombre de
titres gardent leur unité propre), `unite_source` (unité RÉELLE de la pièce, déduite du rapport jeton imprimé / valeur : KMAD, MMAD ou MDH, DH, milliards MAD, `actions`, `DH par action`), `valeur_source`
(jeton imprimé), `document` (clé de `documents`), `page` (page du PDF, 1 = première), `citation` (ligne),
`entete_colonnes` (ligne d'en-tête de dates la plus proche, pour justifier la colonne), `perimetre`
(`consolide`, `social`, `consolide_presume` = non écrit en toutes lettres sur la page), `referentiel`
(IFRS / CNC… ; `referentiel_source` dit s'il vient de ms-screener faute de mention sur la page), `statut` :
`publie` (document de la période), `lu_dans_document_ulterieur_comparatif` (pièce d'origine non retrouvée :
valeur lue dans la colonne comparative d'un rapport suivant — c'est potentiellement une valeur retraitée),
`calcule_depuis_composantes_publiees`. `signe_a_verifier` signale une valeur négative chez ms-screener
dont la ligne ne porte aucun signe. `controle_ms` : `concordant` | `ecart` (avec `ms_valeur`, `arbitrage`)
| `non_verifie` | `absent_ms` | `ms_indique_non_publie`.

Cellule vide : `valeur_mdh: null` + `raison_null` — jamais une estimation. Les raisons « non relevé dans ce
lot » signifient **non lu**, pas **non publié** ; seul « non publié » (constat de ms-screener, non reconfirmé
dans la pièce) et « sans objet » ont un autre sens.

Test : `tests/test_etats_financiers_schema.py` (toute valeur non nulle a document + page + citation).

## Convention de signe

Une seule règle : `valeur_mdh` suit la convention de ms-screener, pas l'impression de la pièce. Les **intérêts
minoritaires** sont stockés positifs (part des minoritaires), alors que le CPC les imprime en déduction : ATW H1-2023,
`-744 852` imprimé, `+744,852` stocké. Les flux d'investissement sont négatifs quand ils sont des emplois, même si une
pièce les imprime en positif (LHM FY2016, rapproché de la variation de trésorerie, signalé par `signe_a_verifier`).
`citation` montre toujours la ligne telle qu'imprimée.

## Indicateurs non comparables

`ebitda_ajuste` regroupe des **indicateurs de gestion non audités, de définitions différentes selon l'émetteur**
(« EBITDA ajusté » d'IAM, « EBE » de Managem et d'ADI) : ils ne sont **pas comparables entre sociétés** et ne
remplacent pas un EBE des états de synthèse. De même, la `dette_nette` calculée par le projet ne s'affiche **jamais
seule** quand l'émetteur publie sa dette nette (`dette_nette_publiee`) : écarts mesurés IAM +0,2 % (31/12/2018),
MNG +7 % (31/12/2019), ADI +38 % (30/06/2026).

## Réserves connues de ce lot

* IAM : l'EBITDA est celui du tableau « Résultats consolidés [ajustés] du Groupe » du rapport de gestion (indicateur de
  gestion). Les écarts avec l'EBE de ms-screener (dérivé) sont consignés dans `ebitda_ajuste.controle_ms`.
* ADI et Managem : l'EBE publié est un indicateur de gestion (rapport de gestion / d'activité), logé dans `ebitda_ajuste`.
  LHM : aucun EBE ni EBITDA lu.
* ATW : total « part du groupe » des capitaux propres (somme de lignes du bilan) et dividende proposé non lus pour
  plusieurs exercices ; semestres 2023 et 2025 : PDF d'origine sans couche texte (images), valeurs lues dans la colonne
  comparative du semestre suivant.
* Dette nette : les valeurs `dette_nette` sont des calculs du projet (définition propre) ; elles diffèrent de la dette
  nette publiée (IAM FY2024 22 463 contre 22 436 publiée ; ADI H1-2026 1 628 contre 1 179 ; MNG FY2019 4 455 contre 4 164).
* Managem : `nombre_actions` FY2025 (11 864 676) est AVANT la division par 10 du 27/07/2026 (118 646 760 actions
  aujourd'hui) — R11 : ne pas rapporter à un cours postérieur sans ajuster ; les montants en MDH ne changent pas.
* LHM FY2025 : 23 431 240 actions émises (23 319 589 hors autodétention). LHM H1-2026 : aucun dépôt dans la liste AMMC.
* `lu_dans_document_ulterieur_comparatif` : pièce d'origine non exploitée par la recherche automatique (fichier image,
  nom inattendu ou libellé différent) ; potentiellement valeur retraitée, à relire pièce en main.

## Lot 7 — assurances (WAF, SAF, ATL)

Archétype `insurance` (comme `bank`, seul le générateur en tient compte : libellé de la ligne de chiffre d'affaires et
raisons « sans objet »). `chiffre_affaires` = **primes émises** (WAF, SAF jusqu'à 2024 ; ATL : primes émises brutes Vie + Non-Vie,
ou « Primes émises » de l'état de soldes de gestion en 2016-2018) ou, en IFRS 17, le chiffre d'affaires que l'émetteur publie :
WAF 2025 / S1 2026 = « Produits des activités d'assurance » (aucun total de primes au compte de résultat consolidé ; 15 226 MDH de primes
émises au rapport de gestion 2025), SAF 2025 / S1 2025 / S1 2026 = « Chiffre d'affaires » du total de l'information sectorielle
(le produit des activités d'assurance est en note de cellule). **Rupture de série à l'IFRS 17** (WAF : 2025 ; SAF : 2025) : le
dépôt d'origine 2024 / S1 2024 est conservé, sa version « retraitée » est en réserve. `ebe`, `dette_nette` et indicateurs : sans objet.
`resultat_exploitation` = « Résultat opérationnel » (IFRS) ; **ATL (normes marocaines)** n'a aucune ligne équivalente : cellule vide motivée.
Intérêts minoritaires : ligne imprimée quand elle boucle (SAF 2016-18, ATL 2016-18), sinon ensemble − part du groupe (calcul cité).

* WAF : comptes consolidés publiés pour la première fois au 31/12/2021 (RFA 2021 p.16) : FY2016-2019 et S1 2019-2020 vides
  (« comptes consolidés non publiés ») ; FY2020 et S1 2021 = colonnes comparatives ; S1 2025 = comparatifs du S1 2026 (le dépôt d'origine est une
  présentation sans états de synthèse). Nombre d'actions non imprimé (3 500 000 selon ms-screener, non retenu).
  FY2025 : la ligne des flux d'investissement porte le libellé « activités opérationnelles » (coquille, identifiée par sa position).
* SAF : Saham Assurance puis Sanlam Maroc ; la fusion-absorption d'Allianz Maroc est actée le 02/07/2026, **après** la clôture du S1 2026
  (« indicateurs … avant la fusion », S1 2026 p.1-2) : aucune période relevée ne contient Allianz, rien n'est raccordé. Le nombre d'actions
  (4 116 874) est d'avant la fusion.
* ATL : le tableau des flux 2025 du RFA est décalé (valeurs et libellés non alignés) : flux 2025 lus dans la colonne comparative du S1 2026.
  Dépôts consolidés 2016-2018 en image : lus sur le rendu.
* Contre-vérification : graine 20261124 + somme des codes des lettres du ticker, 14 cellules non nulles tirées par titre, relues sur le rendu de la page ;
  0 erreur. Comparaison ms-screener : 0 écart numérique (l'écart de définition du chiffre d'affaires IFRS 17 est traité ci-dessus).

## Lot 9 — T2S, DHO (Delta Holding), ARD (Aradei Capital), HPS

BCI (code du tiers pour BMCI) n'existe pas comme ticker interne distinct : c'est `BMC`, traité au lot 8 ; remplacé par DHO.
Archétype `real_estate` pour ARD (immeubles de placement à la juste valeur), `standard_nonfin` pour les trois autres.

* **T2S** (introduit en bourse le 27/07/2026) : aucun dépôt avant le S1 2026 ; FY2023-FY2025 lus dans le document de référence de l'introduction
  (visa AMMC EN/EM/010/2026), FY2016-FY2022 « document introuvable ». S1 2025 = colonne comparative du rapport semestriel 2026 (pas de bilan au 30/06/2025).
  `nombre_actions` imprimé par période, **sans ajustement** (nominal 100 MAD ; fractionnement 2 pour 1 et augmentation de capital postérieurs à la clôture).
  Le tableau d'endettement du rapport semestriel est étiqueté « 30/06/2025 | 30/06/2026 » mais sa colonne de gauche porte les valeurs du 31/12/2025.
  Dette nette : FY2023-FY2025 hors dettes de crédit-bail isolées par l'émetteur (p.239, p.49) et OPCVM retranchés en 2025 (comptés en trésorerie au tableau des flux) ;
  S1 2026 : dettes de location non isolées (aucune note), titres non retranchés. L'endettement net publié par l'émetteur est à `dette_nette_publiee`.
* **DHO** : comptes consolidés CNC en dirhams exacts. FY2017 = colonne comparative du dépôt 2018 (aucun dépôt annuel 2017, S1 2017 en image) ; FY2016 et FY2018 :
  dépôts de une à deux pages à mise en page dense. Pas de ligne EBE ni EBITDA publié. Dette nette = dettes de financement + trésorerie passif − trésorerie actif ;
  crédit-bail (retraité en immobilisations, donc dans les dettes de financement) retiré quand une note « Emprunts à long terme » le chiffre (FY2019 à FY2025 — FY2019 lu dans la colonne comparative de la note du rapport 2020 —, S1 2022 à S1 2026),
  sinon compris : **rupture de définition** entre FY2016-FY2018 / S1 2019-S1 2021 (inclus) et les autres périodes (retiré). Titres de placement non retranchés : la trésorerie de clôture du tableau des flux = trésorerie actif − trésorerie passif, vérifiée sur 15 périodes.
  Nombre d'actions non imprimé (capital seul). Dividende relevé FY2022-FY2025.
* **ARD** : IFRS, KMAD (communiqué S1 2026 en MMAD à points de milliers). FY2017-FY2018 = colonnes comparatives du rapport 2019, identiques au dépôt 2018 dont le texte est encodé
  (rendu de sa p.1 relu). S1 2019 : lignes part du groupe, minoritaires, investissement et dettes encodées, non lues. S1 2020 : l'état s'arrête au « résultat net global ».
  `ebe` = ligne « Excédent brut d'exploitation » des états. Définition de foncière retenue pour la dette nette : dettes financières (part courante et non courante) − trésorerie et équivalents
  (valeurs mobilières comprises, comptées au tableau des flux), dettes de location-financement retirées quand la note les isole ; l'« endettement net » publié (qui les inclut, comme son ratio LTV) est la référence de l'émetteur et se lit à `dette_nette_publiee`. **Ruptures** : FY2018 (location 138 959 KMAD, note 25 du rapport 2019, ouverture) et FY2019-FY2025 avec retrait ; FY2017, S1 2019 et S1 2026 sans retrait.
  Le nombre d'actions est celui de la phrase du capital social, avec la date qu'elle indique.
* **HPS** : CNC. Le tiers marque « pro forma » 2020, 2021, 2023, 2024 : les valeurs relevées sont celles des états de chaque exercice. S1 2025 : dépôt = page de couverture, compte de résultat lu en comparatif du S1 2026.
  FY2023 : bilan à libellés décalés (« trésorerie passif 1 466 472 » est un montant d'impôts différés ; trésorerie passif nulle, établie par l'arithmétique du passif et la trésorerie de clôture).
  `nombre_actions` : 703 599 (nominal 100 DH) jusqu'en 2022, 7 406 190 ensuite (nominal 10 DH) = 7 035 990 (division par dix, RFA 2023 p.31) + 370 200 titres de l'augmentation de capital 2023 (p.40) — **imprimé, rien déduit ni ajusté** (R11) ; dividendes 2019-2022 par action d'avant la division du 10/2023. ⚠️ La division HPS de 2023 n'est PAS déclarée dans `bvc_config.SPLITS` (lot séparé, avec accord). Crédit-bail retiré seulement en FY2025 (≈ 18 % de la dette nette) : rupture de définition.
* Contre-vérification : graine 9 (tirage de 14 cellules non nulles par titre dans les 4 relevés, relues sur un `pdftotext` neuf de la page citée : libellé, jeton et page) ;
  pages rendues et relues : DHO 2018 p.1, ARD 2018 p.1, ARD S1 2026 p.3, HPS 2023 p.39 et p.63 de 2025 ; identité résultat ensemble − part du groupe − minoritaires vérifiée sur toutes les périodes.
