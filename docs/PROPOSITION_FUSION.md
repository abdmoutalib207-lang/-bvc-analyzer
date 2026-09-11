# Proposition de fusion — périmètre limité aux corrections destinées au site

> ⚠️ **Proposition, pas exécution.** Rien n'est fusionné. La décision appartient
> au propriétaire du projet.

## Ce que j'avais affirmé, et qui était faux

J'ai écrit que les deux ensembles de la branche — corrections et outillage —
étaient « sans danger pour le site ». **La revue a refusé cette affirmation, et
la vérification lui donne raison.**

La branche modifie `.github/workflows/update_bvc.yml`, c'est-à-dire **le
workflow qui écrit `data.json`**. Un changement de workflow n'est jamais neutre
pour les données servies : il produit le fichier que le site sert.

## Ce que le site sert réellement

Vérifié dans `index.html` : le terminal ne va chercher que **deux fichiers** —
`data.json` et `news.json`. Tout le reste du dépôt ne l'atteint que par ce que
le moteur y écrit.

## ⚠️ Le danger principal : une fusion naïve ferait RECULER le site

| | `origin/main` | notre branche |
|---|---|---|
| `data.json` daté du | **2026-09-11 14h01** | 2026-09-08 20h40 |
| MASI | 18 713,38 | 18 811,95 |

Notre instantané a **trois jours de retard**. Le robot continue d'écrire sur
`main` pendant que nous travaillons.

Fusionner la branche telle quelle réécrirait `data.json` et `news.json` avec
notre copie périmée. **Le projet a déjà subi exactement cette régression** — le
journal du 25/08 la décrit : « Le pipeline v9 faisait reculer les cours […]
57 cours ramenés à ceux de 11h31. »

## Périmètre proposé

### À FUSIONNER — le moteur et ce qu'il produit

| Fichier | Ce que ça corrige |
|---|---|
| `update_data.py` | suspension jugée à la date d'analyse · price-to-book sourcé · dividendes · composantes du score publiées |
| `bvc_config.py` | registre des suspensions · CMT |
| `bpa.json`, `pipeline/faits_financiers.json` | 8 BPA et 29 dividendes vérifiés sur dépôts AMMC |
| `index.html` | curseur de pondération réparé · puce SUSPENDU |
| `.github/workflows/update_bvc.yml` | **contrôles bloquants avant publication** |

⚠️ Le changement de workflow est le seul qui touche la production de manière
structurelle. Il **ajoute une barrière** : la suite de tests s'exécute sur le
fichier fraîchement écrit, avant publication, et un échec des contrôles de
données interrompt la diffusion. C'est une garantie supplémentaire, pas un
risque — mais c'est un changement de production et il doit être annoncé comme
tel.

### À EXCLURE de la fusion

| Fichier | Pourquoi |
|---|---|
| `data.json` | **propriété du robot.** Notre copie a 3 jours de retard. Il se régénère au prochain run. |
| `news.json` | idem |

### Sans effet sur le site, fusionnables sans risque

`pipeline/` (les modules de qualification, d'identité, de contamination),
`docs/`, `tests/`, `datasets/`, `sources/`, `ROADMAP.md`, `AUDIT_TRACKER.csv`.
Aucun n'est lu par `index.html` ni par le moteur de publication.

⚠️ Une exception à surveiller : `pipeline/collect_history_bvcscrap.py` reçoit
le garde-fou d'identité. Il n'écrit pas `data.json`, mais il écrit
`pipeline/candles/`, dont le moteur se sert en repli. Le garde-fou **refuse**
des écritures ; il ne peut donc pas en fabriquer de fausses.

## Ce qu'il faut vérifier avant de fusionner

1. **Contrôle avant/après par `gardien-donnees`** sur les 80 titres : aucun
   ticker perdu, aucune fraîcheur dégradée, aucune variation hors R10.
2. **Suite complète sur le candidat** — 621 tests au dépôt à ce jour.
3. **Rendu du terminal** : le JSX est compilé au navigateur, aucun test Python
   ne voit une faute de syntaxe. Un rendu réel est nécessaire.
4. **Premier run du robot après fusion**, surveillé : c'est lui qui régénérera
   `data.json` avec le moteur corrigé.

## Ce que la fusion corrigerait sur le site

Vérifié en comparant le `data.json` produit par les deux moteurs sur des
entrées identiques :

| Champ | Titres concernés |
|---|--:|
| `div` (dividende) | 37 |
| `div_dh` | 32 |
| `pb` (price-to-book) | 60 |
| `score_fond`, `score_nlp` | 80 |
| `v53` | 2 |
| `pe`, `bpa`, `price`, `chg` | 1 à 2 |

⚠️ Ces nombres viennent d'une exécution comparée des deux moteurs, pas du site
en production. **Ce que le site sert aujourd'hui n'a pas été relevé
séparément** : je ne peux donc pas affirmer combien d'erreurs y subsistent
exactement, seulement ce que le moteur corrigé produit de différent.

## Ce que la fusion ne corrigerait PAS

- Les **cinq semaines de cours Mutandis dans `pipeline/candles/MSA.json`**.
  Le garde-fou empêche d'en écrire de nouvelles ; il ne nettoie pas l'existant.
- Les **historiques des titres nommés au commit de juin** — ATL, CFGB, DAR.
- Le **cron GitHub**, premier risque du projet, non traité.
- **Aucune performance** n'est démontrée, et rien ici ne s'en approche.
