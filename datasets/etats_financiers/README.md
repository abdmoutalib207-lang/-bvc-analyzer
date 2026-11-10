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

Métriques : `chiffre_affaires` (PNB pour une banque), `ebe` (RBE pour une banque), `resultat_exploitation`,
`resultat_net_ensemble`, `resultat_net_part_groupe`, `interets_minoritaires`, `capitaux_propres_part_groupe`,
`dette_nette` (sans objet pour une banque), `flux_exploitation`, `flux_investissement`, `nombre_actions`,
`dividende_par_action_propose`.

Cellule renseignée : `valeur_mdh` (MDH, signe tel que dans la pièce ; les montants par action ou en nombre de
titres gardent leur unité propre), `unite_source` (KMAD / MMAD / MAD d'après la ligne), `valeur_source`
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
