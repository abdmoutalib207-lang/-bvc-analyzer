# Ruptures de cours observées

> ⚠️ **Généré** par `pipeline/ruptures.py`. Ne pas modifier à la main.
> Une rupture est une **alerte à expliquer**, jamais une preuve de division d'action ni de corruption de fichier.

## La règle de détection

Rapport de deux clôtures consécutives hors de **[1/1.5 ; 1.5]**.

Sous la limite de variation la plus permissive que nous ayons testée (±20 %), deux clôtures consécutives ne peuvent s'écarter que d'un facteur 1,20. Le seuil de 1.5 laisse une marge au-delà de tout régime connu.

⚠️ « Consécutives » veut dire **dans notre fichier**. L'écart de dates est publié pour que l'on voie si des séances manquent entre les deux lignes.

## Le compte

- **74 séries** examinées
- **13 ruptures** sur **9 titres** : ATL, CFGB, CIM, DAR, HPS, MRL, MSA, SOT, STK
- **1** couverte(s) par une pièce datée, **12** sans pièce
- **8** en **aller-retour**, **5** à **sens unique**
- **3** sans aucune transaction de part et d'autre — le prix a changé dans le fichier, pas sur le marché

⚠️ La distinction aller-retour / sens unique est le tri le plus utile de ce tableau. **Une opération sur titres ne revient jamais** : un cours qui chute puis remonte au même niveau quelques séances plus tard décrit une valeur injectée dans l'historique, pas un événement de marché. Les ruptures à sens unique sont les seules candidates à une opération — et il reste à le vérifier pièce en main.

## Les observations

| Titre | Avant | Après | Jours | Clôture avant | Clôture après | Rapport | Vol. avant | Vol. après | Pièce | Forme |
|---|---|---|--:|--:|--:|--:|--:|--:|---|---|
| ATL | 2026-06-05 | 2026-06-08 | 3 | 132.00 | 68.99 | 0.5227 | 215,672 | 5,062 | — | aller-retour |
| ATL | 2026-06-16 | 2026-06-18 | 2 | 66.60 | 130.15 | 1.9542 | 13,790 | 690 | — | aller-retour |
| CFGB | 2026-05-12 | 2026-05-13 | 1 | 207.00 | 582.00 | 2.8116 | 8,437 | 1,778 | — | aller-retour |
| CFGB | 2026-06-16 | 2026-06-18 | 2 | 630.00 | 202.80 | 0.3219 | 400 | 176,233 | — | aller-retour |
| CIM | 2026-06-11 | 2026-06-12 | 1 | 4,770.00 | 1,650.00 | 0.3459 | 0 | 11,550 | — | sens unique |
| DAR | 2026-06-23 | 2026-06-24 | 1 | 176.00 | 4,190.00 | 23.8068 | 12,120 | 0 | — | sens unique |
| HPS | 2023-10-06 | 2023-10-09 | 3 | 6,400.00 | 658.00 | 0.1028 | 5,974,585 | 432,074 | oui | sens unique |
| MRL | 2026-06-29 | 2026-06-30 | 1 | 868.00 | 235.00 | 0.2707 | 0 | 0 | — | sens unique · sans transaction |
| MSA | 2026-05-12 | 2026-05-13 | 1 | 859.90 | 239.00 | 0.2779 | 844 | 659 | — | aller-retour |
| MSA | 2026-06-16 | 2026-06-18 | 2 | 235.00 | 860.00 | 3.6596 | 152 | 18,244 | — | aller-retour · = repli figé |
| SOT | 2026-05-04 | 2026-05-05 | 1 | 73.80 | 369.00 | 5.0 | 576 | 613 | — | sens unique |
| STK | 2026-06-29 | 2026-06-30 | 1 | 73.09 | 490.00 | 6.7041 | 0 | 0 | — | aller-retour · sans transaction |
| STK | 2026-07-02 | 2026-07-03 | 1 | 490.00 | 74.20 | 0.1514 | 0 | 0 | — | aller-retour · sans transaction |

## Hypothèses compatibles avec une rupture

Toutes, tant qu'une pièce n'a pas tranché :

1. opération sur titres (division, regroupement, attribution) non appliquée à l'historique
2. opération sur titres appliquée DEUX fois
3. valeur erronée injectée dans l'historique par une source de repli
4. confusion d'instrument — deux titres différents fusionnés sous un ticker
5. séances manquantes entre les deux lignes, l'écart recouvrant plusieurs jours

⚠️ Une pièce établit l'**événement**. Elle n'établit pas la manière dont notre fichier l'a traité — c'est une question distincte, qui se règle en examinant la série, pas le document.

