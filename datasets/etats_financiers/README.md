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

Cellule renseignée : `valeur_mdh` (MDH, signe tel que dans la pièce ; les montants par action ou en nombre de
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

`valeur_mdh` suit la convention de ms-screener, qui peut différer de l'impression : les **intérêts minoritaires** sont
stockés positifs (part des minoritaires) alors que le CPC les imprime souvent en déduction (« -547 634 », ATW) ; les
flux d'investissement sont négatifs quand ils sont des emplois, même si une pièce les imprime en positif (LHM FY2016,
rapprochement à la variation de trésorerie dans `signe_a_verifier`). `citation` montre toujours la ligne imprimée.

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
