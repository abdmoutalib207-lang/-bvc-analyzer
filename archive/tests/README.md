# Tests archivés

Copies, telles qu'elles étaient, de tests qui vérifiaient une fonctionnalité
retirée du terminal. Ils ne sont pas collectés (`pytest.ini` : `testpaths = tests`).

| Fichier | Retiré le | Pourquoi |
|---|---|---|
| `test_ponderations_front_v53_2026-11-06.py` | 06/11/2026 | Les vues de pondération (OFFICIEL, 70/30…) recalculaient la note v5.3 dans le navigateur. Décision d'Abd Moutalib du 06/11/2026 : la note v5.3 quitte le terminal, le Score BVC devient le score unique ; les vues partent avec elle. Remplacé par `tests/test_ponderations_front.py` (garde-fous du retrait). |
| `test_raccordement_composantes_v53_2026-11-06.py` | 06/11/2026 | Ses tests du score personnalisé (`computeDisplayScore`) portent sur la même machinerie retirée. Les tests du transport de `score_fond`/`score_tech` (moteur et `loadData`) restent dans `tests/test_raccordement_composantes.py` ; les contrôles de tri et d'export y sont repris pour le Score BVC. |
| `test_raccordement_composantes_transport_2026-11-06.py` | 06/11/2026 (lot 2) | Le reste du fichier : le moteur publiait `score_fond` et `score_tech` et `loadData` les transportait via `CHAMPS_SCORE`. Le producteur de la note v5.3 est retiré (décision d'Abd Moutalib : « l'ancien scoring doit disparaître ») ; plus rien à transporter. Garde-fou inverse : `tests/test_interface_moteur.py::test_la_fusion_ne_transporte_plus_la_note_v53`. |

⚠️ **Lot 2 du 06/11/2026** : la note v5.3 n'est plus calculée ni publiée par
le moteur (`v53`, `sig`, `score_fond`, `score_tech`, `poids`, `bonus`, `setup`,
`verdict_plafonne`, `score_version`). Son historique reste dans
`pipeline/score_history.json` et dans l'historique git de `data.json`.
