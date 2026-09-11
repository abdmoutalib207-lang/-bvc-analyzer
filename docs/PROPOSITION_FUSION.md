# Proposition de fusion — dépendances mesurées, pas supposées

> ⚠️ **Proposition, pas exécution.** Rien n'est fusionné. La décision appartient
> au propriétaire du projet.

## Trois affirmations que j'ai faites et qui étaient fausses

| Ce que j'avais écrit | Ce que la vérification donne |
|---|---|
| « Le site ne sert que `data.json` et `news.json` » | **Faux.** `fetchChart()` charge aussi `./pipeline/candles/${sym}.json` |
| J'annonçais le reste comme fusionnable sans réserve | **Faux.** La branche modifie **66 fichiers de chandelles**, que le frontend lit |
| « Une fusion ferait reculer le site de trois jours » | **Non établi.** La fusion d'essai garde la version de `main` |

La dernière mérite d'être détaillée, parce que je l'avais annoncée comme
certaine à partir des seules dates.

## Ce que la fusion d'essai donne réellement

Procédure, rejouable :

```
git worktree add --detach /tmp/essai_fusion origin/main
cd /tmp/essai_fusion && git merge --no-ff --no-commit claude/terminal-bvc-review-AmnBU
```

| Fichier | `main` | branche | **après fusion** |
|---|---|---|---|
| `data.json` (`updated`) | 11/09 14h01 | 08/09 20h40 | **11/09 14h01** |
| MASI | 18 713,38 | 18 811,95 | **18 713,38** |

**Aucun recul.** `data.json` et `news.json` sont identiques à l'ancêtre commun
côté branche : seul `main` a changé, et une fusion Git normale conserve son
état. L'ancienneté d'un fichier dans une branche ne démontre pas son
écrasement — la revue a eu raison de refuser ce raccourci.

Le risque de recul demeure, mais il porte sur une **copie forcée** ou une
**mauvaise résolution de conflit**, pas sur la fusion elle-même.

## ⚠️ La fusion ne s'applique PAS proprement

```
pipeline/historical_data.json — CONFLIT
```

77 entrées de part et d'autre, contenus divergents. Ce fichier n'est pas lu par
le frontend, mais il alimente la chaîne de repli des prix. **Le conflit doit
être résolu explicitement, jamais « au plus récent » par réflexe.**

## Ce que le site lit réellement

Relevé dans `index.html` :

| Ressource | Où |
|---|---|
| `data.json` | rafraîchissement principal |
| `news.json` | actualités |
| `./pipeline/candles/${sym}.json` | **`fetchChart()` — lecture directe** |

Les chandelles ne sont donc pas un détail d'arrière-boutique : **le graphique
du terminal les lit en direct**. La branche en modifie 66.

## Dépendances et comportements attendus

| Élément | Dépendance | Comportement attendu après fusion |
|---|---|---|
| `update_data.py` | produit `data.json` | même univers, mêmes 80 titres, fraîcheur inchangée |
| `.github/workflows/update_bvc.yml` | **produit et publie** `data.json` | ⚠️ ajoute des contrôles bloquants : **une actualisation légitime peut être interrompue** si un test de données échoue. Ce n'est pas une garantie gratuite — c'est un arbitrage entre publier vite et publier juste. |
| `pipeline/candles/*.json` (66) | **lus par `fetchChart()`** | le graphique doit continuer à s'afficher pour un titre pris au hasard |
| `pipeline/collect_history_bvcscrap.py` | écrit les chandelles | ⚠️ **refuse désormais d'écrire** une identité non établie. Sans identité capturée par la source, il n'écrit rien. |
| `index.html` | rendu | le JSX est compilé au navigateur : **aucun test Python ne voit une faute de syntaxe** |
| `bpa.json`, `pipeline/faits_financiers.json` | lus par le moteur | valeurs vérifiées sur dépôts AMMC |
| `pipeline/historical_data.json` | repli des prix | **en conflit — à résoudre explicitement** |

## Ce qu'il faut vérifier sur le candidat de fusion, pas avant

1. Résoudre le conflit `historical_data.json` et **dire comment**.
2. `gardien-donnees` en avant/après sur les 80 titres : aucun ticker perdu,
   aucune fraîcheur dégradée, aucune variation hors R10.
3. **Contrôle de rendu** : ouvrir le terminal fusionné, afficher un titre, et
   vérifier que le **graphique** se charge — c'est le seul moyen de voir une
   régression sur les chandelles ou une faute de JSX.
4. Suite complète sur le candidat.
5. Premier run du robot après fusion, **surveillé** : c'est lui qui régénérera
   `data.json` avec le moteur corrigé, et c'est là qu'un contrôle bloquant
   pourrait interrompre une publication légitime.

## Ce que la fusion changerait dans le fichier servi

Mesuré en exécutant les deux moteurs sur des entrées identiques :

| Champ | Titres |
|---|--:|
| `div` | 37 |
| `div_dh` | 32 |
| `pb` | 60 |
| `score_fond`, `score_nlp` | 80 |
| `v53` | 2 |

⚠️ Ces nombres viennent d'une **exécution comparée**, pas du site en production.
**Je n'ai pas relevé l'état servi aujourd'hui** : je ne peux donc pas dire
combien d'erreurs y subsistent, seulement ce que le moteur corrigé produit de
différent.

## Ce que la fusion ne corrigerait pas

- Les cinq semaines de cours Mutandis dans `pipeline/candles/MSA.json`. Le
  garde-fou empêche d'en écrire de nouvelles ; il ne nettoie pas l'existant.
- Les historiques d'ATL, CFGB et DAR, nommés par la pièce de juin.
- Le cron GitHub, premier risque du projet.
- Aucune performance n'est démontrée.
