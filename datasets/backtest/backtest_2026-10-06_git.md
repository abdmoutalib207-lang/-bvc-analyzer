# Backtest des notes publiées — séances 2026-06-03 → 2026-10-06

Mesure, pas promesse. Fichier JSON jumeau : empreintes sha256 de toutes les entrées.

## Limites (écrites avant les résultats)

- Un seul régime de marché, quelques semaines d'historique de notes.
- Observations chevauchantes : t naïf surestimé, Newey-West retenu.
- MASI en cours seuls contre titres en rendement total : biais favorable aux titres, non chiffré.
- Plusieurs versions du score et deux pondérations dans l'échantillon, non séparées.
- Entrée à la clôture du jour de publication ; aucune fourchette ni impact de marché.
- Grille de confiance : v1 avant le 06/10/2026, v2 ensuite, jamais mélangées.
- Aucune conclusion sous 20 jours distincts ni sous 10 dates non chevauchantes.

Source : `git` · 97 séances · 5835 notes · commit `29a0bf0d7f` · frais 2% aller-retour

## grille_v1 — 5 séances

1643 observations, 23 jours, 76 titres.

- Corrélation de rang note → alpha : moyenne -0.109546 sur 23 jours ; t naïf -5.591, Newey-West -6.279 (retenu), non chevauchant -2.869 (5 dates) → insuffisant : 23 jours (min 20), 5 dates non chevauchantes (min 10)
- Écart décile haut − bas : moyenne -0.011212 sur 23 jours ; t naïf -3.902, Newey-West -3.25 (retenu), non chevauchant -0.737 (5 dates) → insuffisant : 23 jours (min 20), 5 dates non chevauchantes (min 10)

| palier | obs. | jours | titres | alpha brut | alpha net frais | bon sens |
|---|---|---|---|---|---|---|
| ACHETER | 195 | 23 | 17 | -0.0038 | -0.0238 | 0.2256 |
| SURVEILLER | 901 | 23 | 66 | 8.6e-05 | -0.019914 | — |
| ATTENDRE | 506 | 23 | 50 | 0.00749 | -0.01251 | — |
| ÉVITER | 41 | 23 | 3 | 0.003167 | -0.016833 | 0.5366 |

## grille_v1 — 20 séances

611 observations, 9 jours, 75 titres.

- Corrélation de rang note → alpha : moyenne -0.157918 sur 9 jours ; t naïf -9.345, Newey-West -15.02 (retenu), non chevauchant None (1 dates) → insuffisant : 9 jours (min 20), 1 dates non chevauchantes (min 10)
- Écart décile haut − bas : moyenne -0.04695 sur 9 jours ; t naïf -6.976, Newey-West -9.207 (retenu), non chevauchant None (1 dates) → insuffisant : 9 jours (min 20), 1 dates non chevauchantes (min 10)

| palier | obs. | jours | titres | alpha brut | alpha net frais | bon sens |
|---|---|---|---|---|---|---|
| ACHETER | 74 | 9 | 13 | -0.012412 | -0.032412 | 0.3378 |
| SURVEILLER | 396 | 9 | 60 | 0.008634 | -0.011366 | — |
| ATTENDRE | 124 | 9 | 34 | 0.024033 | 0.004033 | — |
| ÉVITER | 17 | 9 | 2 | 0.010417 | -0.009583 | 0.2941 |

## grille_v2 — 5 séances

0 observations, 0 jours, 0 titres.

Aucune observation : horizon non atteint ou grille trop récente.

## grille_v2 — 20 séances

0 observations, 0 jours, 0 titres.

Aucune observation : horizon non atteint ou grille trop récente.

## Verdict

- grille_v1 h5 : insuffisant (23 jours, 5 dates non chevauchantes, 1643 observations) — on ne conclut pas ; IC moyen observé -0.109546, sans valeur probante.
- grille_v1 h20 : insuffisant (9 jours, 1 dates non chevauchantes, 611 observations) — on ne conclut pas ; IC moyen observé -0.157918, sans valeur probante.
- grille_v2 h5 : insuffisant (0 jours, 0 dates non chevauchantes, 0 observations) — on ne conclut pas.
- grille_v2 h20 : insuffisant (0 jours, 0 dates non chevauchantes, 0 observations) — on ne conclut pas.
