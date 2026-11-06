# Tests archivés

Copies, telles qu'elles étaient, de tests qui vérifiaient une fonctionnalité
retirée du terminal. Ils ne sont pas collectés (`pytest.ini` : `testpaths = tests`). Les copies « lot2 » sont les
fichiers TELS QU'ILS ÉTAIENT avant le retrait du producteur v5.3 ; leur version courante, allégée,
reste dans `tests/` quand une partie vérifie encore quelque chose.

| Fichier | Retiré le | Pourquoi |
|---|---|---|
| `test_ponderations_front_v53_2026-11-06.py` | 06/11/2026 | Les vues de pondération (OFFICIEL, 70/30…) recalculaient la note v5.3 dans le navigateur. Décision d'Abd Moutalib du 06/11/2026 : la note v5.3 quitte le terminal, le Score BVC devient le score unique ; les vues partent avec elle. Remplacé par `tests/test_ponderations_front.py` (garde-fous du retrait). |
| `test_raccordement_composantes_v53_2026-11-06.py` | 06/11/2026 | Ses tests du score personnalisé (`computeDisplayScore`) portent sur la même machinerie retirée. Les tests du transport de `score_fond`/`score_tech` (moteur et `loadData`) restaient dans `tests/test_raccordement_composantes.py` (archivé à son tour au lot 2, ligne suivante) ; les contrôles de tri et d'export y sont repris pour le Score BVC. |
| `test_raccordement_composantes_transport_2026-11-06.py` | 06/11/2026 (lot 2) | Le reste du fichier : le moteur publiait `score_fond` et `score_tech` et `loadData` les transportait via `CHAMPS_SCORE`. Le producteur de la note v5.3 est retiré (décision d'Abd Moutalib : « l'ancien scoring doit disparaître ») ; plus rien à transporter. Garde-fou inverse : `tests/test_interface_moteur.py::test_la_fusion_ne_transporte_plus_la_note_v53`. |
| `test_poids_sans_heure_lot2_2026-11-06.py` | 06/11/2026 (lot 2) | Fichier entier : `get_weights` / `compute_v53` sans dépendance à l'heure (accord R8 du 03/11). Fonctions retirées. |
| `test_precision_poids_publies_lot2_2026-11-06.py` | 06/11/2026 (lot 2) | Fichier entier : précision des `poids` publiés et recomposition de `v53`. Champs retirés. |
| `test_gel_nlp_lot2_2026-11-06.py` | 06/11/2026 (lot 2) | Copie d'origine. Retirés : invariance de `compute_v53`, ACHAT FORT, bonus, seconde formule (`sig` de collect_financial_data). Reste dans `tests/` : aucun modulateur du corpus dans le moteur. |
| `test_ponderation_lot2_2026-11-06.py` | 06/11/2026 (lot 2) | Copie d'origine. Retirés : les tests de `get_weights` (régimes `masi_ytd`, `has_results`). Restent dans `tests/` : ceux de `masi_history`. |
| `test_couverture_partielle_lot2_2026-11-06.py` | 06/11/2026 (lot 2) | Copie d'origine. Retirés : le seuil `COUVERTURE_VERDICT_MIN` et le signal « Couverture partielle ». |
| `test_non_comparable_lot2_2026-11-06.py` | 06/11/2026 (lot 2) | Copie d'origine. Retirés : le signal « Non comparable (liquidité) », sa précédence dans `_signal_publie`, la règle B. Reste : `_meta.non_comparable` décidé par sa condition. |
| `test_note_sectorielle_branchement_lot2_2026-11-06.py` | 06/11/2026 (lot 2) | Copie d'origine. Retirés : poids des piliers, linéarité de v53, signal sans note, v53 de la famille, garde-fou de la note partielle (règle 11). |
| `test_score_canonique_lot2_2026-11-06.py` | 06/11/2026 (lot 2) | Copie d'origine. Retirés : `SCORE_VERSION`, `score_version` publié, malus figés dans `compute_v53`. |
| `test_suspension_lot2_2026-11-06.py` | 06/11/2026 (lot 2) | Copie d'origine. Retirés : le signal SUSPENDU (`_signal_publie`) et son journal. La suspension se lit dans `_meta.suspendu`. |
| `test_suspension_mng_lot2_2026-11-06.py` | 06/11/2026 (lot 2) | Copie d'origine. Le signal de MNG pendant et après sa suspension → `_suspendu_maintenant`. |
| `test_technique_fiable_lot2_2026-11-06.py` | 06/11/2026 (lot 2) | Copie d'origine. Retirés : part du technique reversée au fondamental, plafond ACHETER → SURVEILLER. |

⚠️ **Lot 2 du 06/11/2026** : la note v5.3 n'est plus calculée ni publiée par
le moteur (`v53`, `sig`, `score_fond`, `score_tech`, `poids`, `bonus`, `setup`,
`verdict_plafonne`, `score_version`). Son historique reste dans
`pipeline/score_history.json` et dans l'historique git de `data.json`.
