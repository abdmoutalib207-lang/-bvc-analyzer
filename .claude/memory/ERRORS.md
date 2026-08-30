# Erreurs commises — et pourquoi elles se sont produites

> Ce fichier était réclamé par le `CLAUDE.md` depuis le début du projet mais
> n'avait jamais été créé. Il est ouvert le 28/08/2026 et rempli à partir du
> journal des décisions.
>
> **Règle d'usage : une erreur n'entre ici qu'avec sa CAUSE et son SIGNAL.**
> Une liste de bourdes ne sert à rien ; ce qui sert, c'est de reconnaître la
> forme d'une erreur avant de la refaire.

---

## Famille 1 — Croire une source sur parole

### La séance fantôme du 14/08 (jour férié)
IDBourse et Médias24 ont rediffusé la clôture du 13 en l'estampillant du 14.
Les trois écrivains de chandelles ont suivi : 71 + 43 + 143 occurrences d'une
séance qui n'a pas eu lieu.
**Cause** : `updated_at` de la source était notre seule autorité sur la date.
**Signal** : il n'existe qu'à l'échelle du marché — 71/71 clôtures identiques
un jour férié, contre 6/44 un jour coté. La règle R9 ne voyait rien parce que
la source rediffusait aussi les variations.
**Correctif** : `_recaler_seance_fantome()` + `pipeline/seance.py`.

### Le drapeau `stale` mal interprété (14/08)
Le `stale` d'IDBourse veut dire « pas en direct », pas « périmé ». Il vaut vrai
dès la clôture. S'y fier allumait l'alerte en permanence — donc en permanence
pour un produit publié avant l'ouverture.
**Leçon générale : une alarme toujours allumée n'alerte plus.**

### Une source qui RECULE (28/08)
CDG a servi la séance précédente pendant quelques minutes après la clôture.
IDBourse ayant reculé en même temps, l'arbitrage par la date (R3) n'a rien vu :
il compare les sources entre elles, et elles s'étaient trompées ensemble.
`data.json` est passé de 73 titres à la séance à zéro.
**Cause profonde** : il manquait la comparaison avec ce que nous savions déjà.
**Correctif** : `_cliquet_seance()`.

---

## Famille 2 — Comparer des identifiants sans les traduire

### Le bulletin CDG contre nos chandelles
Le `SNA` du bulletin est **Stokvis**, notre `SNA` est **Sonasid**. Comparés
directement, l'écart affiché atteint 96 % et l'on croit à une panne majeure.
**Le passage par `IDB_TICKER_MAP` est obligatoire.** Cette erreur est documentée
dans le CLAUDE.md — et a malgré tout été refaite en août 2026.

### L'attribution des cotations IDBourse (10/08)
Le code de l'URL `/instruments/XXX` est le ticker officiel BVC, cherché tel quel
dans `ISIN_MAP`. 29 titres rejetés en silence, et Sonasid héritant des valeurs
de Stokvis — 74 DH au lieu de 2 000.

### L'appariement par préfixe trop court (28/08)
À 6 caractères, Maghrebail s'appariait avec une autre société : 58 % d'écart.
**Une identité fausse est pire qu'une identité manquante (R2).** Seuil porté à
9 caractères, complété par la table d'alias du projet.

---

## Famille 3 — Deux écrivains pour un même fichier

### Le pipeline v9 faisant reculer 57 cours (19/08)
v9 lit `data.json` au démarrage, calcule trente minutes, puis commite par-dessus
le run parti après lui.
**Correctif** : `data.json` n'a plus qu'un propriétaire, `update_bvc` ; v9
n'écrit que `financial_data.json` ; groupe de concurrence partagé.

### La boucle entre workflows
`update_bvc` déclenchait `fetch_news` qui déclenchait `update_bvc`. 112 commits
par jour pour un quota Pages d'environ 10 reconstructions par heure.
**Correctif** : coupée des DEUX côtés — une seule coupure laisse le cycle
repartir.

---

## Famille 4 — L'alarme branchée sur le courant qu'elle surveille

### Le contrôle de séance muet pendant trois jours (26–28/08)
`verifier_seance.yml` dépendait du déclencheur `schedule` de GitHub — le même
qui ne partait plus. Les trois jours où la clôture a été manquée, le contrôle
censé le signaler n'est pas parti non plus. **Personne n'a été prévenu ; c'est
le fondateur qui a vu l'écran figé.**
**Correctif** : le contrôle est attaché au run des prix, donc indépendant du
calendrier.

---

## Famille 5 — Nos propres impatiences

### Le run manuel de trop (28/08, 15h59)
Un run déclenché sans nécessité, sept minutes après un run parfait, est tombé
dans la fenêtre où CDG bascule de séance. Le bug préexistait ; c'est
l'impatience qui l'a déclenché en production.
**Consigne : ne pas déclencher de run juste après 15h30.**

### La bougie du jour figée au premier run (10/08)
L'étape 6c passait son tour dès qu'un point du jour existait. Le premier run —
souvent en pleine séance — gravait un cours de milieu de séance comme clôture
définitive. 57 bougies fausses sur 72 cotées.

---

## Le motif commun

Presque toutes ces erreurs ont la même forme : **une autorité unique à laquelle
on fait confiance sans contre-épreuve.** La date de la source, le ticker de
l'URL, le premier run de la journée, le cron de GitHub.

Le correctif a toujours la même forme aussi : **une seconde opinion, et un
arbitrage explicite entre les deux.**
