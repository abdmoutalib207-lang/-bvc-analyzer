# Proposition de fusion — dépendances mesurées, pas supposées

> ⚠️ **Proposition, pas exécution.** Rien n'est fusionné. La décision appartient
> au propriétaire du projet.

Mesures rejouables faites le **11/09/2026**, ancêtre commun `bfd13d94`,
branche `f803a370`, `origin/main` `27228f46`.

## Quatre affirmations que j'ai faites et qui étaient fausses

| Ce que j'avais écrit | Ce que la vérification donne |
|---|---|
| « Le site ne sert que `data.json` et `news.json` » | **Faux.** `fetchChart()` charge aussi `./pipeline/candles/${sym}.json` |
| J'annonçais le reste comme fusionnable sans réserve | **Faux.** La fusion ne s'applique pas proprement — voir le conflit |
| « Une fusion ferait reculer le site de trois jours » | **Non établi.** La fusion d'essai garde la version de `main` |
| « **La branche modifie 66 fichiers de chandelles** » | **Faux, et l'erreur porte sur le CÔTÉ.** La branche n'en modifie **aucun** |

## ⚠️ « Différence entre deux branches » ≠ « modification apportée par une branche »

C'est la correction la plus importante de cette version, et elle change le
risque annoncé. Les 66 chandelles ne viennent pas d'ici.

```
git merge-base HEAD origin/main                     → bfd13d94
git diff --name-only bfd13d94 HEAD        -- pipeline/candles/ | wc -l   →  0
git diff --name-only bfd13d94 origin/main -- pipeline/candles/ | wc -l   → 66
git diff --name-only HEAD     origin/main -- pipeline/candles/ | wc -l   → 66
```

| Comparaison | Ce qu'elle mesure | Résultat |
|---|---|---|
| ancêtre → **branche** | ce que la branche **introduit** | **0 chandelle** |
| ancêtre → **main** | ce que `main` a publié depuis | **66 chandelles** |
| branche ↔ main | ce qui **diffère** entre les deux | 66 chandelles |

La troisième ligne est celle que j'avais lue, et je l'ai attribuée au mauvais
côté. Les 66 fichiers sont les mises à jour quotidiennes de `main` des 09, 10
et 11 septembre. **Une fusion normale les conserve** : rien de ce côté-là n'est
en jeu.

Ce que la branche introduit réellement : **112 fichiers**, aucun sous
`pipeline/candles/`.

## Ce que la fusion d'essai donne réellement

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

## ⚠️ Le seul conflit — et comment il est résolu

```
pipeline/historical_data.json — CONFLIT
```

**74 entrées de part et d'autre, 62 divergent.** Ce fichier n'est pas lu par le
frontend, mais il alimente la chaîne de repli des prix.

> Consigne de la revue : *« N'arbitrez pas globalement sur la date du
> fichier. »* Elle est juste. `_updated` dit quand un fichier a été **écrit**,
> pas ce qu'il contient — le 28/08/2026, deux sources ont reculé d'une séance
> et le fichier le plus récent portait les cours les plus anciens.

La résolution est donc **une décision par entrée**, produite par
`pipeline/resoudre_historique.py`, qui **ne lit `_updated` nulle part** (un
test le vérifie sur l'arbre syntaxique, pas sur le texte).

| Cas | Règle | Entrées |
|---|---|--:|
| dernière séance plus récente | l'entrée qui porte la séance la plus récente | **58** |
| séance identique, contenu identique | rien à trancher | **12** |
| séance identique, seul un extremum glissant diffère | `h52w`/`l52w`/`h90`/`l90` dépendent de la **date d'ancrage de la fenêtre**, pas de la séance : les deux valeurs sont justes, on retient celle du run le plus récent **en le disant** | **4** |
| désaccord sur un autre champ | **non arbitré** — signalé, conservé tel quel | **0** |

Les quatre entrées du troisième cas : `AFM` (h52w 1367,0 → 1360,0), `SBS`
(h90 2199,0 → 2175,0), `SRM` (h52w 555,9 → 555,0), `DAR` (l90 161,2 → 165,25).
Fenêtres glissées d'une journée, `last_date` et `n_candles` identiques.

**Résultat mesuré : 74 titres, aucun perdu, aucune séance en recul, aucun
désaccord laissé ouvert.**

⚠️ **Le contenu retenu coïncide avec celui de `main` — mais pas la
justification.** Ce sont 74 décisions distinctes, et la raison mesurée de la
coïncidence est que **la branche ne porte de séance plus récente pour aucun
titre**. Si elle en avait porté une, la règle l'aurait conservée : un test le
démontre sur un cas construit où le fichier le plus frais perd sur un titre.

⚠️ **Résoudre ce conflit n'assainit rien.** Aucune des deux versions n'a été
produite par le collecteur muni du garde-fou : ce sont deux sorties de
l'ancien moteur. Les cinq semaines de cours Mutandis dans l'historique de MSA
sont dans les deux.

## Ce que le site lit réellement

| Ressource | Où |
|---|---|
| `data.json` | rafraîchissement principal |
| `news.json` | actualités |
| `./pipeline/candles/${sym}.json` | **`fetchChart()` — lecture directe** |

Les chandelles ne sont donc pas un détail d'arrière-boutique : le graphique du
terminal les lit en direct. **La branche n'en modifie aucune** ; le contrôle de
rendu reste néanmoins nécessaire, parce que le moteur fusionné les réécrira au
premier run.

## Dépendances et comportements attendus

| Élément | Dépendance | Comportement attendu après fusion |
|---|---|---|
| `update_data.py` | produit `data.json` | **inchangé par cette branche** — voir « protections incomplètes » |
| `.github/workflows/update_bvc.yml` | **produit et publie** `data.json` | ⚠️ ajoute des contrôles bloquants : **une actualisation légitime peut être interrompue** si un test de données échoue. Arbitrage entre publier vite et publier juste. |
| `pipeline/candles/*.json` | **lus par `fetchChart()`** | conservés tels quels par la fusion ; réécrits au premier run |
| `pipeline/collect_history_bvcscrap.py` | écrit les chandelles | ⚠️ **refuse désormais d'écrire** une identité non établie. Au premier run : **2 titres importés, 79 refusés.** |
| `pipeline/historical_data.json` | repli des prix | **conflit résolu entrée par entrée** (ci-dessus) |
| `index.html` | rendu | le JSX est compilé au navigateur : **aucun test Python ne voit une faute de syntaxe** |
| `bpa.json`, `pipeline/faits_financiers.json` | lus par le moteur | valeurs vérifiées sur dépôts AMMC |

## ⚠️ Le premier run après fusion refusera 79 titres sur 81

Ce n'est pas un effet de bord : c'est la conséquence directe de la règle
adoptée. L'identité doit venir des **données importées**, et seules deux
sources en portent une — les exports `sources/ADH/` et `sources/CSR/`, dont la
colonne `Instrument` voyage sur la ligne du cours.

| Source | Porte une identité ? | État |
|---|---|---|
| XLSX local | **non** — le fichier est nommé d'après NOTRE ticker | **désactivée** |
| bibliothèque d'extension | **non** — interrogée par nom, rend des cours sans instrument | **désactivée** |
| export CSV de l'opérateur | **oui** — colonnes `Ticker` + `Instrument` | **active**, 2 titres |

Ce que cela donne, mesuré :

```
ADH : 735 bougies depuis l'export — identité portée : « DOUJA PROM ADDOHA »
CSR : 735 bougies depuis l'export — identité portée : « COSUMAR »
MSA : SOURCES DÉSACTIVÉES — aucune source ne peut prouver son identité
```

**Les 79 refusés ne perdent rien** : `save()` conserve leurs entrées anciennes
et les marque `_reimport_refuse`. Conserver une donnée et autoriser sa
réutilisation sont deux décisions distinctes ; on garde, et on marque.

**Ce qui débloquerait les 79** : un export par titre, au même format. C'est une
démarche auprès de l'opérateur, pas un développement.

## Périmètre exact des protections — ce qui n'est PAS protégé

| Écrivain | Protégé par le garde-fou d'identité ? |
|---|---|
| `pipeline/collect_history_bvcscrap.py` | **oui** — identité lue dans les données importées |
| `update_data.py` (étape 6c, écrit des chandelles) | **NON — inchangé** |
| `generate_candles.py` | **NON — inchangé** |

⚠️ **Ne pas cocher « moteur publié protégé ».** Le moteur qui alimente le site
chaque jour est `update_data.py`, et il n'est pas touché par cette branche.

## Ce qu'il faut vérifier sur le candidat de fusion, pas avant

1. ~~Résoudre le conflit `historical_data.json` et dire comment.~~ **Fait** —
   `pipeline/resoudre_historique.py`, 74 décisions, 0 non arbitrée.
2. `gardien-donnees` en avant/après sur les 81 titres : aucun ticker perdu,
   aucune fraîcheur dégradée, aucune variation hors R10.
3. **Contrôle de rendu** : ouvrir le terminal fusionné, afficher un titre, et
   vérifier que le **graphique** se charge — seul moyen de voir une régression
   sur les chandelles ou une faute de JSX.
4. Suite complète sur le candidat.
5. Premier run du robot après fusion, **surveillé** : c'est là qu'un contrôle
   bloquant pourrait interrompre une publication légitime, et là que les
   79 refus se produiront pour de vrai.

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
- `update_data.py` et `generate_candles.py`, qui écrivent des chandelles sans
  contrôle d'identité.
- Le cron GitHub, premier risque du projet.
- Aucune performance n'est démontrée.
