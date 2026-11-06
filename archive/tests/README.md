# Tests archivés

Copies, telles qu'elles étaient, de tests qui vérifiaient une fonctionnalité
retirée du terminal. Ils ne sont pas collectés (`pytest.ini` : `testpaths = tests`).

| Fichier | Retiré le | Pourquoi |
|---|---|---|
| `test_ponderations_front_v53_2026-11-06.py` | 06/11/2026 | Les vues de pondération (OFFICIEL, 70/30…) recalculaient la note v5.3 dans le navigateur. Décision d'Abd Moutalib du 06/11/2026 : la note v5.3 quitte le terminal, le Score BVC devient le score unique ; les vues partent avec elle. Remplacé par `tests/test_ponderations_front.py` (garde-fous du retrait). |
| `test_raccordement_composantes_v53_2026-11-06.py` | 06/11/2026 | Ses tests du score personnalisé (`computeDisplayScore`) portent sur la même machinerie retirée. Les tests du transport de `score_fond`/`score_tech` (moteur et `loadData`) restent dans `tests/test_raccordement_composantes.py` ; les contrôles de tri et d'export y sont repris pour le Score BVC. |

La note v5.3 elle-même reste calculée et publiée par le moteur (`v53`, `sig`
dans data.json) : ses tests côté moteur ne sont pas touchés.
