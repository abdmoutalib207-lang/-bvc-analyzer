# Datation des bulletins CDG — ce qui est établi, et ce qui ne l'est pas

La revue externe a demandé de justifier que le bulletin intitulé
« Indices du mercredi 9 septembre 2026 » décrive la séance du **8** septembre.
Le titre du PDF ne suffit pas à l'établir.

## Ce qui est mesuré

    bulletin « 9 septembre »   vs séance 08/09 :  61 comparés,  0 écart
    bulletin « 9 septembre »   vs séance 09/09 :   0 comparé          non concluant
    bulletin « 9 septembre »   vs séance 10/09 :   0 comparé          non concluant
    bulletin « 10 septembre »  vs séance 08/09 :  56 comparés, 47 écarts

**Tolérance : 0,1 %.** La formulation exacte est donc « 61 titres comparés,
aucun écart dépassant 0,1 % », et non « aucun écart ». La revue a eu raison
d'exiger que le seuil soit nommé : `TOLERANCE` est désormais une constante de
`pipeline/parse_cdg_bulletin.py`.

Les deux lignes à zéro comparaison ne sont pas des concordances : nos
chandelles ne portent pas ces dates. L'outil les classe **NON CONCLUANT** et
sort avec le code 2.

## Ce que cela établit

Une **forte concordance du bulletin intitulé 9 septembre avec les chandelles
datées du 8**, sur 61 titres, à 0,1 % près.

Le fait que l'autre bulletin diffère sur 47 des 56 titres comparables rend
cette observation plus informative : le résultat ne serait pas le même contre
n'importe quel bulletin.

## Ce que cela n'établit PAS

- que le bulletin du 10 décrive la séance du 9 — aucune comparaison n'a pu être
  faite, nos chandelles s'arrêtant au 8 ;
- qu'une **règle générale J−1** s'applique à tous les bulletins. Une observation
  sur un bulletin n'est pas une règle.

**Statut retenu** : correspondance OBSERVÉE pour le bulletin du 9, selon la
référence de chandelles utilisée. Règle générale **non certifiée**.

## La question de circularité

La revue a posé la bonne question : si les chandelles avaient été datées depuis
ces mêmes bulletins par application d'une règle J−1, la comparaison serait
circulaire et ne prouverait rien.

**Elles ne le sont pas.** `pipeline/parse_cdg_bulletin.py` LIT les chandelles
pour comparer ; il n'en écrit aucune. Les dates proviennent des champs de date
des charges utiles des fournisseurs — `DateDernierCours` et `DateCotation` —
jamais du titre d'un PDF.

## Mais l'indépendance n'est que partielle, et il faut le dire

Répartition des sources du prix pour la séance du 08/09, celle qui a servi au
recoupement :

| Source | Titres |
|---|---:|
| CDG | 64 |
| BMCE | 13 |
| IDBourse | 2 |

**Soixante-quatre des soixante-dix-neuf titres viennent de CDG** — le même
éditeur que le bulletin. Pour ceux-là, la concordance compare deux canaux d'une
même maison : l'API et le PDF. C'est un contrôle de cohérence interne utile,
pas une confirmation par une source indépendante.

Seuls **15 titres** (BMCE et IDBourse) apportent une datation d'origine
réellement distincte. C'est peu, et cela borne ce que l'observation démontre.

⚠️ Le projet documente déjà que CDG et Wafabourse partagent un éditeur
(`nt-soft.ma`) et que leur accord ne prouve donc pas l'exactitude. Le même
raisonnement s'applique ici, entre deux canaux du même fournisseur.

## Ce qu'il faudrait pour certifier la règle

Comparer plusieurs bulletins consécutifs à des chandelles dont la date provient
majoritairement d'une source distincte de CDG, et vérifier que l'écart
publication/séance est constant à travers les jours fériés et les week-ends.
Ce n'est pas fait.
