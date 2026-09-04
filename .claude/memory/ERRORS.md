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

## Famille 6 — Un garde-fou écrit mais pas branché

### Le drapeau d'ISIN suspect jeté par son appelant (31/08)
`neutraliser_si_isin_suspect()` renvoyait bien un booléen `suspect`, et sa
docstring promettait que « le score de confiance retombera de lui-même ». Or
l'appelant le déballait dans un `_` : le drapeau mourait sur place.
**Conséquence** : un titre à l'ISIN croisé gardait 5 sur 5 — ses chandelles sont
nombreuses (celles de la mauvaise société), ses fondamentaux présents, son
corpus fourni. Le terminal affichait un ACHETER en couleur pleine sur une donnée
dont le moteur venait lui-même de journaliser l'incohérence.
**Trouvé par `relecteur-pipeline`**, pas par les tests : la validation par
comparaison de `data.json` ne pouvait pas le voir, aucun titre n'étant suspect
ce jour-là. **Une docstring qui affirme un comportement non implémenté est un
mensonge dans le code** — plus dangereux qu'un commentaire absent, parce qu'on
s'y fie.

## Famille 7 — Un objet composite qu'aucun test ne relit entier

### 3 238 bougies impossibles, depuis l'origine (trouvé le 04/09)
L'étape 6c d'`update_data.py` amorçait les extrêmes sur la seule clôture
(`"h": c_price, "l": c_price`) puis ne les étendait qu'avec les cours des runs
suivants. **L'ouverture, qui vient d'une autre source, n'entrait jamais dans la
fourchette.** Dès que `o ≠ c`, la bougie naissait impossible : plus haut sous
l'ouverture quand le titre baissait, plus bas au-dessus quand il montait.

    ADI 28/08   o=438,00  h=434,10   ← le plus haut sous l'ouverture
    ADI 24/08   o=430,00  l=436,20   ← le plus bas au-dessus

**Portée** : 3 238 bougies sur 32 677 (**9,9 %**), **73 tickers sur 74**.
**Cause** : les quatre champs d'une bougie sont écrits séparément et personne
ne relisait l'objet entier. Le projet vérifiait les **dates** des bougies
(séance fantôme, cliquet), leurs **ruptures** entre séances (`validate_candles`,
±50 %), leur **nombre** — jamais leur cohérence interne. Une bougie fausse mais
plausible ligne à ligne passe tous ces filtres.
**Signal** : un invariant arithmétique gratuit — `l ≤ min(o,c) ≤ max(o,c) ≤ h`.
Il ne demande aucune source extérieure et ne peut pas produire de faux positif.
**Trouvé** parce qu'Abd Moutalib a imprimé la page officielle de la BVC depuis
un poste marocain et l'a envoyée : les dates et les ouvertures concordaient
10/10, ce qui a mis l'œil sur des colonnes qu'on ne regardait jamais.
**Correctif** : source corrigée (l'ouverture entre dans la fourchette),
`seance.reparer_ohlc()` pour l'existant, contrôle dans `verifier_seance.py`,
7 tests.

**Leçon générale : ce qui n'est jamais relu comme un tout se casse comme un
tout.** Chercher les invariants internes des objets composites du projet —
il en reste (`_meta` contre le prix qu'il décrit, cap contre prix × titres).

## Le motif commun

Presque toutes ces erreurs ont la même forme : **une autorité unique à laquelle
on fait confiance sans contre-épreuve.** La date de la source, le ticker de
l'URL, le premier run de la journée, le cron de GitHub.

Le correctif a toujours la même forme aussi : **une seconde opinion, et un
arbitrage explicite entre les deux.**

## 02/09/2026 — 17 membres nommés sur le SITE PUBLIÉ, pas seulement dans les données

**Signal** : un balayage des fichiers suivis par git, lancé pour vérifier la
pseudonymisation des sorties NLP, a trouvé « karim doe » et « doe karim »
dans `index.html`.

**Cause** : les tables de démonstration `MEMBERS` et `CHAT` du frontend étaient
remplies avec de vrais membres du groupe — nom, rang, taux de réussite, alpha,
et des messages qui leur étaient attribués. Ce n'était pas un fichier de
données mais **la page publiée sur GitHub Pages** : lisible sans savoir ce
qu'est un dépôt.

**Ce qui a failli le faire manquer** : le premier balayage a signalé 85
fichiers, dont `CLAUDE.md` et les définitions d'agents. C'étaient des fausses
alertes — des membres se sont nommés « Bourse » ou « IDBourse », et le
détecteur les retrouvait dans du texte projet ordinaire. **Le bruit a bien
failli enterrer les deux vraies fuites.** Un détecteur d'identité doit filtrer
sur les noms composés, pas sur toute chaîne de six caractères.

**Leçon** : chercher les données personnelles là où on ne les a pas mises. La
pseudonymisation visait `whatsapp_analysis/output/` ; l'exposition la plus
grave était ailleurs, à la racine, dans le fichier le plus consulté du dépôt.

## 02/09/2026 — Un nettoyage relancé qui se mord la queue

**Signal** : « Membres connus : 3 988 (+1 994 nouveaux) » — la table avait
exactement doublé.

**Cause** : `pseudonymiser_sorties` relancé sur des fichiers déjà nettoyés
prenait les pseudonymes du premier passage (`M0745`) pour de nouveaux noms de
membres et leur attribuait des numéros à leur tour.

**Leçon** : tout script de nettoyage sera relancé — par prudence, par erreur,
ou parce qu'un run a échoué au milieu. Il doit reconnaître son propre résultat
et le laisser tel quel. `DEJA_PSEUDO` + un test dédié.

## 03/09/2026 — 2 092 identités publiques pendant trois mois

**Détail complet dans `.claude/memory/INCIDENT_VIE_PRIVEE.md`.** Résumé :

- **Cause** : les CSV de sortie du pipeline NLP étaient versionnés sur un dépôt
  PUBLIC avec les noms réels des membres, leur taux de réussite et leur
  influence. `.gitignore` n'excluait que `.pkl` et `messages.csv`.
- **Signal qui aurait dû alerter** : aucun test ne lisait le contenu des
  fichiers versionnés. Le garde-fou qui existe aujourd'hui
  (`test_aucun_nom_reel_dans_les_csv_versionnes`) échouait dès sa création — il
  décrivait un défaut réel, pas une précaution théorique.
- **Aggravation par Claude** : le nom d'un membre servait de donnée de test
  dans 70 endroits et d'exemple dans la documentation, y compris dans les
  commentaires expliquant comment on protège les gens.
- **⚠️ Trois pièges de réécriture d'historique** : `--blob-callback` attend un
  CORPS de fonction (sinon l'outil annonce « finished » sans rien faire) ; un
  TAG maintient des commits en vie et `push --all` ne le pousse pas ; les
  `refs/pull/N/head` ne se suppriment PAS — seul GitHub Support les purge.
- **Reste ouvert** : demande à GitHub Support pour purger `refs/pull/8` et
  `refs/pull/9`, qui exposent encore 2 013 personnes et 588 numéros.
