# Bilan du lot — mesuré dans les artefacts

> ⚠️ Ce fichier est **généré** par `pipeline/bilan_lot.py`, qui LIT `datasets/lot1b/`.
> Ne pas le modifier à la main : un chiffre recopié finit par contredire le fichier qu'il décrit.

**7 titres · 4306 observations**

| Titre | Lignes | Base prix | Base quantités | prix | volume | indic. | explor. | exéc. | sans usage |
|---|--:|---|---|--:|--:|--:|--:|--:|--:|
| ADH | 797 | état inconnu | état inconnu | 797 | 797 | 0 | 797 | 0 | 0 |
| ADI | 797 | état inconnu | état inconnu | 797 | 797 | 0 | 797 | 0 | 0 |
| CMT | 514 | état inconnu | état inconnu | 514 | 514 | 0 | 514 | 0 | 0 |
| CSR | 794 | état inconnu | état inconnu | 794 | 794 | 0 | 794 | 0 | 0 |
| MNG | 797 | ajustement probable, à confirmer | état inconnu | 797 | 26 | 0 | 797 | 0 | 0 |
| SOT | 542 | base incohérente ou suspecte | état inconnu | 0 | 55 | 0 | 0 | 0 | 487 |
| TQA | 65 | état inconnu | état inconnu | 65 | 65 | 0 | 65 | 0 | 0 |

## Ce que ces chiffres disent

- **7 titres sur 7** n'autorisent aucun indicateur **publiable**.
- **6 titres sur 7** autorisent un calcul **exploratoire**, qui n'alimente ni le signal officiel, ni une probabilité, ni une performance validée.
- **7 titres sur 7** n'autorisent aucune exécution simulée.
- **487 observations** sur 4306 n'autorisent **aucun** usage.

## SOT — portée exacte de la mise à l'écart

⚠️ La mise à l'écart porte sur **toute la série**, pas seulement sur l'historique antérieur à l'opération. Une formulation antérieure disait le contraire.

- `prix_analyse` accordé sur **0** observation(s) sur 542
- `indicateur` et `indicateur_exploratoire` : **0** et **0**

Répartition des combinaisons d'usages :

- `aucun` — 487 observation(s)
- `volume` — 55 observation(s)

⚠️ Ce constat ne justifie **aucune correction automatique** des prix de SOT.

