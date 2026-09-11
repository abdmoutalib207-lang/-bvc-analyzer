# Méthodologie — calculs, hypothèses, limites

## Le score v5.3

`Technique × 25 % + Fondamental × 47 % + NLP × 28 %`, modulé par contexte via
le WeightEngine. La formule est la référence versionnée ; elle ne change pas
sans backtest ni accord (R8).

Les trois composantes sont publiées séparément (`score_tech`, `score_fond`,
`score_nlp`) depuis le 10/09. Critère de raccordement vérifié : **à 100 %
technique la note égale `score_tech`, à 100 % fondamental elle égale
`score_fond`** — contrôlé sur ADI, ADH, TQA, HPS, BCP.

⚠️ Les pondérations personnalisées restent **exploratoires**. Elles n'ont pas
leur propre validation, et le signal y disparaît.

## Ce que le score n'est pas

Ni une probabilité, ni une prévision de rendement. Le champ `confidence` mesure
des conditions de disponibilité, pas une chance de hausse.

Toute probabilité affichée exigerait une cible, un horizon et une calibration
hors échantillon. Sans cela, le terme est « score ».

## Bénéfice par action

`BPA = RNPG ÷ nombre d'actions`, les deux issus du rapport déposé à l'AMMC,
chacun avec son numéro de page. Quand la société publie elle-même son résultat
par action, on le reprend tel quel plutôt que de le recalculer.

**Ordre de préséance du diviseur** — il compte :

1. nombre d'actions EXISTANT établi par une résolution d'AG ;
2. à défaut, le nombre retenu par la société (moyenne pondérée IAS 33) ;
3. à défaut, le total inscrit au rapport.

Risma a fait basculer 1 devant 2 : sa résolution établit 16 012 132 titres
quand le rapport en moyenne 14 326 947. **Les deux sont justes** — ils
répondent à deux questions différentes. Pour un ratio par action d'aujourd'hui,
c'est le nombre existant qui vaut.

## Price-to-book

`PB = cours × nombre d'actions ÷ capitaux propres PART DU GROUPE`.

Les capitaux propres consolidés, minoritaires inclus, sous-estimeraient le
ratio : le nombre d'actions est celui de la société mère.

Un split postérieur à la clôture de l'exercice n'est pas au rapport ; le
registre `SPLITS` l'applique.

## Backtest — comptabilité du portefeuille

`valeur = cash + quantité × cours`, frais intégrés à chaque opération.

Conventions : achat à `p × (1 + f)`, vente à `p × (1 − f)`, où `f` cumule frais
et slippage. Un aller-retour à prix inchangé coûte donc `(1 − f) / (1 + f)`,
soit **−0,399202 %** pour f = 0,2 % — et non −0,40 %. Le test vérifie la
formule au 1e-12, pas son arrondi.

Deux défauts corrigés, tous deux trouvés par la revue externe :

- le gain était compté deux fois à la vente (132 au lieu de 120) ;
- les frais d'ENTRÉE n'atteignaient pas la courbe — défaut de mon propre
  correctif du précédent.

⚠️ **Ce qui reste à faire** : journal daté, dividendes, règle d'exécution au
prochain prix exécutable, traitement des séances sans transaction, et
reproductibilité depuis un dataset figé. Aucune performance n'est publiable
avant.

## Indicateurs techniques — spécification du lot 2

Socle à IMPLÉMENTER et à TESTER, sans présomption d'utilité prédictive :

| Indicateur | Paramètres | Usage |
|---|---|---|
| SMA | 20, 50, 200 | tendance, pente, distance au cours |
| RSI de Wilder | 14 | momentum et ses changements |
| MACD | EMA 12/26, signal 9 | accélération, ralentissement |
| ATR de Wilder | 14 | volatilité ; normaliser les distances |
| ADX et DI± | 14 | séparer force et direction |
| Bollinger | 20, 2 σ | dispersion, compression, expansion |
| Activité/liquidité | 20 et 60 séances | régularité, exécution plausible |
| Force relative au MASI | 20 et 60 séances communes | comparaison à l'indice |
| Niveaux de prix | extrêmes antérieurs, pivots confirmés | surveillance, invalidation |

**Règles d'implémentation** : documenter formule, amorçage, fenêtre minimale,
traitement des trous et précision ; ne jamais calculer une moyenne de 200
périodes avec moins de 200 observations admissibles ; n'utiliser aucun point
futur pour identifier un signal passé ; distinguer bougie en formation et
bougie clôturée ; vérifier sur des séries de référence indépendantes.

**Règles d'interprétation** : un RSI bas ne dit pas « acheter » ; l'ADX mesure
la force, pas le sens ; l'ATR mesure la volatilité, pas la direction ; toucher
une bande de Bollinger n'est pas un signal ; des indicateurs corrélés ne
multiplient pas la conviction ; **l'absence d'échanges peut invalider une
lecture malgré un indicateur calculable**.

VWAP intraday, profil de volume par prix et carnet d'ordres restent
conditionnés à des données adaptées. Ne pas les reconstituer depuis des bougies
quotidiennes.
