# Déplacer les créneaux après la clôture — le détail

> Établi le 23/09/2026, à la demande d'Abd Moutalib : « pourquoi pas tout
> simplement régler à nouveau les horaires des runs comme au début ».

## Ce qui est déjà en place

26 créneaux par jour ouvré, en UTC :

```
40 9         09h40 — dix minutes après l'ouverture
0 12         12h00 — mi-séance
45 15        15h45 — LE run qui fixe le cours
0 18         18h00 — filet, après generate_candles
25,55 8-18   22 rattrapages, deux par heure de 8h à 18h
```

**Ce n'est donc pas un problème de densité.** La redondance existe ; elle ne
produit pas de runs.

## Ce que GitHub en fait

| jour | créneaux programmés | runs honorés dans la fenêtre 8h-18h |
|---|---:|---:|
| 18/09 | 26 | **4** |
| 21/09 | 26 | **4** |
| 22/09 | 26 | **4** |
| 23/09 | 26 | **1** |

Quatre, trois jours de suite. Et les runs partent à des heures qui ne
correspondent à aucun créneau : 00h46, 06h09, 19h06, 19h13.

**Conclusion : ajouter des créneaux n'ajoutera pas de runs.** C'est aussi ce
qui explique que la réduction de 27 crons à 4, le 18/08, n'ait rien dégradé —
ce n'était pas la densité qui produisait les runs.

## ⚠️ Ce qui est exploitable, en revanche

**Un run collecte le cours au moment où il s'exécute, pas à l'heure de son
créneau.**

  - un créneau de **16h05 déclenché à 19h** donne quand même la bonne clôture :
    le cours ne bouge plus après 15h30 ;
  - un créneau de **09h25 déclenché à 11h** donne un cours de mi-séance —
    inutile pour un bulletin J+1, et c'est ce qui a été publié le 23/09.

Donc tous les créneaux ne se valent pas. Aujourd'hui, **17 sur 26 tombent avant
la clôture** : deux tiers de la redondance ne servent pas la promesse du
produit.

## La proposition

```
40 9           09h40 — le terminal ne reste pas figé sur la veille
0 12           12h00 — mi-séance
45 15          15h45 — LE run qui fixe le cours
35,55 15-20    12 rattrapages, TOUS après la clôture
0 18           18h00 — filet, après generate_candles
```

**16 créneaux au lieu de 26, mais 13 utiles au lieu de 9.**

`35` et non `25` : la clôture est à 15h30 **locales**, et le Maroc peut être à
UTC+0 ou UTC+1 selon le décret en vigueur. Un cron GitHub, lui, est en UTC fixe
et ne peut pas suivre un décret. `15h35 UTC` est après la clôture dans les deux
cas ; `15h25` ne le serait pas si le pays repassait à UTC+0… ce qui est
précisément arrivé le 20/09.

Fin de fenêtre à 20h55 UTC : au-delà, `generate_candles` (17h) et le filet
(18h) ont déjà tourné, et un run plus tardif n'apporte rien.

## Ce que ça change, et ce que ça ne change pas

### Le coût : rien

Chaque run honoré produit un commit — `data.json` porte `updated`, qui change à
chaque fois, donc la garde `git diff --cached --quiet` ne l'arrête jamais.
Mais GitHub honore ~4 créneaux **quel que soit leur nombre** : déplacer ne
change pas le nombre de commits. Le quota de publication de Pages, ressource
rare du projet, n'est pas touché.

### Le gain : une estimation, pas une mesure

Si l'on suppose que GitHub tire ses ~4 runs au hasard parmi les créneaux
programmés — **hypothèse plausible mais NON ÉTABLIE** —, la probabilité qu'au
moins un tombe après la clôture passe d'environ **75 % à plus de 99 %**.

⚠️ **Ce chiffre est un modèle, pas un relevé.** Trois jours d'observation ne
prouvent pas que le tirage soit uniforme. Ce qui est mesuré, et qui suffit à
décider : le 23/09, **un seul créneau a été honoré de toute la journée**, et il
est tombé à 13h50 — avant la clôture. Avec la proposition, ce run unique aurait
eu 13 chances sur 16 d'être utile au lieu de 9 sur 26.

### ⚠️ Ce que ça ne règle pas

**Rien ne garantit qu'un créneau parte.** Le 23/09 en a honoré un seul sur
vingt-six. Un jour où GitHub n'en honore aucun, le bulletin du lendemain porte
la veille, et personne ne le sait avant le contrôle du soir — **qui dépend du
même cron**.

C'est le défaut de fond : la sentinelle a la même faiblesse que ce qu'elle
surveille. Seul un déclencheur extérieur à GitHub y répond.

## Risque de la proposition

Passer de 26 à 16 créneaux **réduirait le nombre de runs si GitHub en honorait
un POURCENTAGE plutôt qu'un nombre fixe**. L'observation — exactement 4, trois
jours de suite, malgré 26 créneaux — plaide pour le nombre fixe, mais trois
jours ne l'établissent pas.

Parade si le doute gêne : garder la densité totale à 26 en épaississant la
fenêtre d'après-clôture (`15,35,55 15-20` = 18 créneaux + les 4 principaux + 4
le matin). On ne perd rien et on ne teste pas l'hypothèse.

**C'est la variante prudente, et je la recommande** si le choix doit être fait
sans mesure supplémentaire.
