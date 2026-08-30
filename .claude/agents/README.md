# L'équipe BVC Analyzer — qui fait quoi, et dans quel ordre

Six agents permanents. Chacun a un périmètre **exclusif** : deux agents ne
décident jamais de la même chose. C'est ce qui évite les avis contradictoires
et les corrections qui se marchent dessus.

| Agent | Décide de | Ne décide jamais de |
|---|---|---|
| `gardien-donnees` | publier ou refuser un jeu de données | comment corriger le code |
| `veilleur-sources` | l'état de santé des sources | l'écriture du pipeline |
| `relecteur-pipeline` | la conformité d'un diff aux règles R1–R10 | le contenu fonctionnel |
| `ingenieur-tests` | ce qui est vérifié automatiquement | les règles métier elles-mêmes |
| `analyste-nlp` | le calcul du champ `nlp` | la pondération du score (R8) |
| `quant-backtest` | la mesure de performance | la modification du scoring (R8) |

## Les deux séquences qui structurent le travail

**Séquence « je change du code »**
```
développement → relecteur-pipeline → ingenieur-tests → gardien-donnees → commit
```
Le relecteur vérifie les règles, l'ingénieur vérifie que le filet couvre le
changement, le gardien vérifie qu'aucune donnée ne régresse. **Aucun commit
touchant le moteur ne part sans ces trois avis.**

**Séquence « quelque chose ne va pas en production »**
```
veilleur-sources (est-ce la source ?) → gardien-donnees (qu'est-ce qui a bougé ?)
   → relecteur-pipeline (est-ce nous ?)
```
Toujours dans cet ordre : la cause la plus fréquente est extérieure. Chercher le
bug chez soi d'abord fait perdre des heures.

## Les trois règles de coopération

**1. Un chiffre, ou rien.** Aucun agent ne rend un verdict sans la mesure qui le
porte. « Ça a l'air bon » n'est pas un rapport.

**2. Personne ne corrige hors de son périmètre.** Un agent qui repère un
problème chez un autre le **signale** et passe la main. Le gardien ne réécrit
pas le pipeline ; le veilleur ne modifie pas le parseur.

**3. Tout incident nouveau va dans la mémoire.** `.claude/memory/ERRORS.md` pour
une erreur commise (avec sa cause et son signal), `LEARNINGS.md` pour un fait
durable. Un incident non écrit sera refait — le projet en a la preuve : le piège
`IDB_TICKER_MAP` était documenté et a quand même été retombé dedans.

## Priorité actuelle (28/08/2026)

L'ordre de la feuille de route est **délibéré** :

1. `ingenieur-tests` — le filet d'abord. 0 test aujourd'hui ; sans lui, aucun
   refactoring n'est raisonnable et aucune garantie n'est vérifiable.
2. `analyste-nlp` — 28 % du score ne pèse presque rien. C'est la promesse la
   plus forte du produit et la moins tenue.
3. `quant-backtest` — rendre la performance visible. C'est ce qui fait passer de
   « joli » à « crédible ».

`gardien-donnees`, `veilleur-sources` et `relecteur-pipeline` tournent en
continu, dès maintenant : ils protègent l'existant pendant que les trois autres
construisent.
