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

## Famille 8 — Un nombre qui change de sens en traversant le code

### Le champ `win` : trois horizons pour une seule valeur (05/09)
La légende du classement l'appelait « probabilité de surperformance **1 mois** »,
la fiche détaillée « WIN RATE **6M** », et `update_data.py` y injectait
`p_outperform_**12m**`. Le même nombre portait trois horizons contradictoires.

**Pire** : ce n'était pas une probabilité. Le repli de `phase13_prediction.py`
calcule `composite / 100 * 0.7`, puis multiplie par 0,9 à chaque horizon.
Vérifié sur `final_rankings.csv` : **12 lignes sur 12** retrouvent la formule à
moins de 0,002 près. Aucune fréquence n'a jamais été observée — c'est le score
remis à l'échelle et rebaptisé.

**Cause** : trois écrivains différents (`update_data.py`, `sync_sentiment.py`,
le front) alimentaient et affichaient le même champ sans contrat commun.
`sync_sentiment.py` y met même `p_outperform_1m` quand `update_data.py` y met
`p_outperform_12m` : selon qui écrit en dernier, l'horizon change.
**Signal** : un champ écrit par plus d'un programme et lu sous plus d'un nom.
**Correctif** : libellé unique `SM~`, mention « heuristique, non calibré »,
suffixe `%` retiré, et deux tests qui échouent si le mot « probabilité »
revient.

### Des chiffres de performance écrits en dur dans la page (05/09)
83 % de réussite, +38,3 % de rendement à 12 mois, inscrits dans `index.html`.
Le dépôt ne contient **ni jeu de données figé, ni commande, ni journal**
permettant de refaire le calcul.
**Leçon générale : un résultat qu'on ne peut pas reproduire n'est pas un
résultat, c'est une affirmation.** Elle est plus dangereuse qu'une donnée
manquante, parce qu'elle a l'air d'une mesure.

### Deux régimes de marché morts depuis l'origine (05/09)
`masi_ytd` recevait `masi["chg"]` — la variation de la **séance** — quand ses
deux seuils (-5 % et +10 %) décrivent une performance **annuelle**. Une
variation quotidienne vaut ±1 % et la BVC la plafonne à ±10 % par titre : le
mode défensif ne pouvait s'armer que le jour d'un krach de l'indice entier, et
le mode haussier jamais. Même famille : `"has_results": False` écrit en dur
faisait passer une absence d'information pour une décision.
**Cause** : le nom de la variable disait « ytd », rien ne le vérifiait.
**Signal** : une unité implicite. `chg`, `ytd`, `pct` — trois choses
différentes que le typage Python ne distingue pas.
**Et corriger l'appelant ne suffisait pas** : le projet ne conservait aucune
valeur passée de l'indice, donc il n'y avait rien à calculer. D'où
`pipeline/masi_history.py`.

**Trouvé par l'audit externe**, comme l'ADX ×14. Deux fois de suite, le défaut
structurant a été vu de l'extérieur — pas par les tests, pas par nous.

## Famille 9 — Combler une absence de donnée au lieu de la dire

### Le backtest fabriquait ses prix (corrigé le 05/09)
`load_or_generate_market_prices()` générait, faute de panel, une série
entièrement aléatoire : dérive de 8 % l'an, volatilité de 12 %, changements de
régime tirés au sort, **graine fixée à 42** pour que ce soit reproductible.
Le résultat était donc stable, plausible, et vide de sens.

**Ce qui rend ce défaut particulièrement dangereux : un backtest qui invente
ses prix produit TOUJOURS un résultat.** Rien dans la sortie ne signale que
l'entrée était fictive — au contraire, la reproductibilité de la graine lui
donne l'apparence du sérieux.

La phase 8 faisait de même pour la corrélation avance-retard : `rng.normal`
quand le panel manquait. Corréler le sentiment du groupe à des nombres tirés
au hasard ne mesure rien, mais produit un coefficient et un « décalage
optimal » que la phase 14 publie ensuite comme un résultat.

**Correctif** : `PrixIndisponibles` levée par défaut ; la génération reste
accessible pour éprouver le moteur, mais il faut la demander explicitement.
La phase 8 renvoie désormais une erreur plutôt qu'un chiffre.

### La référence n'était pas le MASI
Quand un panel existait, l'« indice » de comparaison était la moyenne
**équipondérée** des titres du panel, rebasée à 1000. Deux conséquences :
la référence se déforme avec l'univers testé, et une stratégie qui
surpondère les grandes valeurs « bat » mécaniquement une moyenne
équipondérée sans qu'aucune compétence n'entre en jeu.

**Cause** : le projet ne conservait aucun historique de l'indice. La
correction était impossible avant que `masi_history.json` n'existe.
**Signal** : une référence construite à partir de ce qu'on veut évaluer.

**Leçon générale : une absence de donnée doit se dire, jamais se combler.**
C'est la même famille que le `0` mis pour `masi_ytd` inconnu, et que le
`win = 50` du NLP quand la valeur manque. Trois endroits, un seul réflexe.

## Famille 10 — Mon propre outil, pris au même piège (08/09)

### « ONE » apparié à « S.M M-ONE-tique »
Le catalogue AMMC apparie les émetteurs par le NOM. Mon bonus de containment
testait `nb in na` sur les **chaînes brutes** : « one » est une sous-chaîne de
« monétique », et l'Office National de l'Électricité a décroché 0,80 face à
S2M — au-dessus du seuil, donc retenu sans alerte, avec zéro document.

**C'est exactement la faute que je venais de documenter** dans les collisions
d'identité du NLP : comparer des chaînes sans respecter les frontières de mots.
Écrire la leçon ne protège pas de la refaire.
**Correctif** : le containment se mesure sur des ENSEMBLES DE MOTS, jamais sur
les caractères. `{marsa, maroc} ⊆ {sodep, marsa, maroc}` est un vrai
sous-ensemble ; « one » dans « monétique » n'en est pas un.

### « 0 rapport annuel » pour Managem, dont je venais de lire les 121 pages
Le script annonçait 14 émetteurs sur 75 avec un rapport annuel, et 0 pour
Managem — alors que `Managem_RFA_2025.pdf` était ouvert dans le répertoire de
travail. La fiche émetteur de l'AMMC ne liste que les communiqués et les avis ;
le rapport annuel existe sous un nom voisin, non lié depuis cette page :

    fiche émetteur   Managem_2025.pdf       communiqué de résultats
    rapport annuel   Managem_RFA_2025.pdf   le document de 121 pages

**Signal** : un résultat contredit par ce qu'on a déjà sous la main. « 8 doc »
pour les 75 émetteurs sans exception aurait dû suffire à alerter — une
régularité parfaite décrit rarement le monde, elle décrit un artefact.
**Correctif** : dériver le nom du rapport, puis **VÉRIFIER qu'il est servi**.
Deviner une URL sans la tester aurait reproduit le travers combattu.
⚠️ Et vérifier le type MIME, pas le seul code HTTP : l'AMMC renvoie une page
d'erreur HTML de 105 ko avec un statut exploitable.

**Leçon générale, la troisième fois qu'elle se vérifie : contrôler le
RÉSULTAT, jamais le message de l'outil.** « Completely finished » l'avait déjà
menti deux fois lors de la purge de l'historique.

## Famille 11 — Un fait juridique qu'aucune donnée ne porte (09/09)

**Le terminal a recommandé « ACHETER ★★ » sur un titre qu'il est interdit
d'acheter.** CMT — MASI 1 — est suspendue de cotation depuis le 17/07/2026,
dans l'attente d'une OPA obligatoire (Ayrad / OSEAD / CIMR, avis AMMC
DO/EM/07/2026). Le moteur lui a en outre écrit **28 chandelles pour des
séances qui n'ont pas eu lieu**, du 17/07 au 01/09, toutes à 4 350 DH et
toutes à volume nul.

**Trois garde-fous s'en sont approchés sans pouvoir conclure**, et c'est ça
qui est instructif :

- **R9** (`chg=0` ET `vol=0`) a reconnu la donnée — c'est exactement sa
  signature. Mais elle conclut *stale*, « pas rafraîchi ». Le titre était donc
  marqué stale ET porteur d'un signal d'achat, sans contradiction apparente :
  les deux verdicts ne parlent pas de la même chose.
- **le plafond de liquidité du 01/09** a ramené la confiance à 2, le volume
  médian étant nul. Le garde-fou d'affichage, lui, se déclenche à 1. Il s'en
  est fallu d'un point — et le raisonnement écrit ce jour-là était pourtant le
  bon mot pour mot : « un signal sur un titre que personne ne peut acheter ni
  vendre n'est pas actionnable ».
- **l'étape 6c** refuse d'écrire une bougie depuis un prix stale, et elle a
  joué : les 28 bougies datent d'avant, quand la source estampillait encore le
  cours du jour.

**La leçon.** Une suspension **ne se déduit pas des cours**. Un titre suspendu
et un titre délaissé produisent rigoureusement les mêmes nombres — volume nul,
variation nulle, cours immobile. Aucune statistique ne les sépare, parce que
la différence n'est pas dans la série : elle est juridique, et publiée
ailleurs. Elle doit donc **entrer par un registre tenu à la main**, comme
`SPLITS` — même nature de fait, même remède.

C'est le prolongement de la famille 9 (« combler une absence au lieu de la
dire ») avec une nuance qui compte : ici l'absence n'était pas une absence de
donnée, mais une absence de **droit d'agir**. Le score restait légitime ; c'est
la conclusion qui ne l'était pas. D'où le correctif retenu — on garde le score
affiché, on supprime la recommandation.

**Le signal qui aurait dû alerter, et qui existait :** le bulletin CDG donne
CMT à `0.00` sur toutes les colonnes, sans même une heure de dernier échange
(`NaN:NaN:NaN`), là où IDBourse rediffuse 4 350 DH estampillé du jour. R3 le
dit depuis le 27/08 — « CDG laisse les champs VIDES quand un titre n'a pas
coté au lieu de rediffuser la veille » — mais un prix à zéro est rejeté en
amont comme invalide, et l'information se perdait là. **Un champ vide est une
information ; le traiter comme une donnée manquante la détruit.**

⚠️ **Piste non traitée** : combien d'autres titres CDG donne-t-il à zéro ?
Le bulletin du 09/09 compte 81 instruments pour **64 cotés**. Les 17 autres
n'ont pas coté ce jour-là — la plupart par simple illiquidité, mais rien ne
distingue aujourd'hui ces deux cas dans le moteur.

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

---

## Famille — Un contrôle qui ne mord plus (16/09/2026)

### Le cliquet laissé à 21 quand le référentiel en portait 30
Le plancher « au moins 21 émetteurs avec des fonds propres » protégeait contre
une régression. Après le lot suivant il y en avait 30 : retirer un fait
laissait le test vert.
**Cause** : un plancher est une mesure datée, pas une règle. Il vieillit dès
que le travail avance.
**Signal** : la mutation « retirer un fait » est passée verte alors qu'elle
était rouge la veille.
**Correctif** : remonter le plancher à chaque lot. **Un cliquet qu'on oublie de
remonter n'est plus un cliquet.**

### Deux défauts que la vérification par mutation a seuls révélés
Le contrôle de citation renonçait devant un jeton de douze chiffres — donc
devant exactement les lignes les plus difficiles. Conséquence : prendre le
total consolidé pour la part du groupe (CFG Bank), ou lire deux colonnes
recollées comme un seul montant (CTM, mille fois trop), ne déclenchait rien.
**Leçon** : un contrôle qui s'abstient sur les cas durs contrôle les cas
faciles. Compter combien de fois il s'applique, et l'inscrire dans le test.

### Le millésime 2075
`Communique%20Visa%20CIH%20AUK%20750.pdf` contient « 2075 » — dans
l'échappement d'une espace, pas dans une date. Cet exercice imaginaire devenait
le plus récent et écrasait 2025 : CIH Bank était déclarée sans rapport annuel
alors que le sien est servi.
**Leçon** : borner ce qu'on accepte comme une année. Un motif `20\d\d` trouve
des années partout, y compris là où il n'y en a pas.

### J'ai annulé un cycle d'intégration qui se portait bien
Croyant voir une étape bloquée « depuis trente minutes », j'ai annulé un run,
puis perdu plusieurs tentatives à le relancer. La machine se met en veille
entre deux tours : le temps que je croyais écoulé ne l'était pas. L'étape avait
en réalité vingt secondes.
**Signal** : comparer `date -u` du conteneur aux horodatages de l'API AVANT de
conclure qu'un travail est bloqué.

---

## Famille 12 — Un raisonnement juste, appliqué à un fait qu'il ne couvre pas (16/09/2026)

> Cette famille est la plus difficile à voir, parce qu'**aucun des trois
> raisonnements ci-dessous n'est faux**. Chacun est même un garde-fou que nous
> avons écrit exprès. Ils échouent tous les trois sur le même fait : Minière
> Touissit a repris sa cotation après une OPA obligatoire, avec une **référence
> de cours remise à 2 217 DH** au lieu des 4 501 d'avant suspension.
>
> Le cas d'école complet : `docs/CAS_ECOLE_OPA_ET_REPRISE_DE_COTATION.md`.

### Un contrôle nourri d'une valeur périmée (le mien, posé le matin même)

Le contrôle de capitalisation compare la valeur servie à `prix × actions`. Le
16/09, il a trouvé 3 727 MDHS servis contre 7 313 calculés, et a remplacé la
première par la seconde. Or `3 727 000 000 ÷ 1 681 233 = 2 216,83`, exactement
le prix de l'OPA : **la source avait raison, et notre prix était le périmé.**
**Cause** : l'arbitre du contrôle était un cours gelé depuis deux mois par notre
propre logique de suspension. Le contrôle vérifiait la source avec une valeur
que la source avait cessé d'alimenter.
**Signal** : le nombre d'actions implicite. `cap_servie ÷ actions_sourcées`
redonnait un prix rond et plausible — 2 216,83 — pendant que notre prix, lui,
ne correspondait à rien de récent.
**Correctif** : `_capitalisation()` s'abstient dès que `src_prix` n'est pas une
source de cotation vivante. Un contrôle sans arbitre valable ne tranche pas.
**Règle** : *un contrôle qui s'appuie sur une valeur périmée est pire que pas de
contrôle — il remplace du juste par du faux, et avec autorité.*

### Des indicateurs qui survivent à leur objet

MA20 4 624 et MA50 4 769 décrivaient un régime de prix disparu. Un cours de
2 438 lu sous ces moyennes se lit « survendu », donc « acheter » : le moteur a
publié **ACHETER ★★ avec 5/5 de confiance**, sur un titre dont **un seul titre**
avait été échangé.
**Cause** : `neutraliser_si_isin_suspect` cherche un facteur 3 entre prix et
MA20. L'écart n'était que de 1,65. Ce garde-fou attrape une **identité croisée**,
pas un **changement de référence** — deux accidents différents.
**Signal** : le volume. Une séance de reprise à 1 titre échangé ne fonde rien.
**Correctif** : `reprise_trop_recente()` neutralise les indicateurs tant que
moins de 20 séances ont suivi la reprise, et le signal devient « Données
insuffisantes ».

### R10 appliquée à ce qui n'est pas une variation

Comparé au 4 350 diffusé, le cours de reprise donnait −43,95 %. Le plafond des
±10 % a conclu « erreur de source » et ramené la variation à **0,00 %** — un
jour où le titre avait fait **+9,97 %**, ce que R9 interdit explicitement.
**Cause** : R10 parle de **variations de cours**. Elle ne dit rien d'une
**référence remise à neuf par le régulateur**. C'est la même faute que le
05/09 sur le MASI : invoquer une règle pour un cas qu'elle ne couvre pas.
**Signal** : trois chiffres justes qui produisent un résultat impossible. Quand
un contrôle rend 0 % sur un titre qui a échangé, c'est le contrôle qu'il faut
regarder, pas la donnée.
**Correctif** : le jour d'une reprise inscrite au registre, la variation se
calcule sur la référence sourcée. Hors de ce jour, R10 s'applique inchangée.

### ⚠️ Et le correctif a d'abord été posé au mauvais endroit

Première tentative : la règle à côté du plafond ±10 %. Le journal affichait
« +9,97 % » et le fichier publiait toujours **0,00 %**. `chg` est réécrit plus
bas par `recalculer_variation()`, qui repartait des chandelles.
**Règle** : *une règle posée ailleurs que chez le dernier écrivain ne tient
pas.* Avant de corriger une valeur publiée, établir QUI l'écrit en dernier —
le journal ment par omission, il montre l'avant-dernier.

### Le piège dormant trouvé au passage

`appliquer_serie.py` réécrivait le fichier de chandelles **entier**. Tant que
CMT était suspendue, cela ne se voyait pas : il n'y avait rien après. Le jour
de la reprise, réappliquer le lot aurait effacé la séance nouvelle et remis
4 350 — sans erreur, sans message.
**Cause** : un lot réceptionné avait un droit d'écriture sans borne temporelle.
**Règle** : *un lot instruit sur SA période. Ce qui lui est postérieur lui est
étranger, et ne peut donc pas être nié par lui.*

### Ce que cette famille apprend

Quatre garde-fous corrects, un fait réglementaire qu'aucun ne connaissait. La
parade n'est pas d'assouplir les garde-fous — c'est de **porter le fait dans le
registre, sourcé**, pour qu'ils puissent le consulter. Un contrôle ne peut pas
déduire d'une série de prix qu'une autorité a remis une référence à neuf : il
faut le lui dire, avec la pièce.

---

## Famille 13 — Identifier par le NOM, et croire le fournisseur sur parole (17/09/2026)

> Deux titres servaient publiquement les cours d'un autre émetteur. Ce n'est pas
> une erreur de calcul : c'est une erreur d'identité, et elle est restée invisible
> trois mois parce que rien ne relisait le RÉSULTAT de l'appariement.

### Maroc Leasing portait l'historique de Marsa Maroc

`MANUAL_MAP` contenait, commentaire compris :

    "MRL": "SODEP",   # SODEP = ancien nom BVCscrap pour Marsa Maroc (MRL)

MRL est **Maroc Leasing**. Sodep-Marsa Maroc est **MSA**, mappé dix lignes plus
bas sur « Marsa Maroc ». Le commentaire confond les deux sociétés et le code a
suivi : 22 séances entre 800 et 869 DH sur un titre qui cote 367, dont 14
égalant au centime les clôtures de MSA.
**Cause** : une note de travail prise pour une vérification. Personne n'a
recoupé « SODEP » avec la société que MRL désigne.
**Signal** : le niveau de prix. Un cours ne quitte pas son ordre de grandeur.
367 contre 850, c'est un facteur 2,3 — aucune séance ne fait ça.

### AtlantaSanad portait l'historique d'Auto Hall

7 séances du 08 au 16/06 à 66-69 DH sur un titre qui cote 130, les 7 clôtures
égalant celles de HAL. `MANUAL_MAP` dit pourtant « AtlantaSanad », et porte même
ce commentaire : « ATL = AtlantaSanad (assurance) — PAS Auto Hall (= HAL) ».
**Cause** : la résolution du nom se fait CHEZ LE FOURNISSEUR. BVCscrap apparie
« AtlantaSanad » contre une table servie par medias24.com, que nous ne pouvons
ni lire ni auditer. Écrire le bon nom chez nous ne garantit rien.
**Signal** : **la contamination commence exactement là où s'arrête la source
fiable.** L'export XLSX d'ATL finit le 05/06 ; le programme demande la suite au
fournisseur ; la contamination démarre le 08/06, séance suivante. Pour MRL, sans
export, la date de départ vaut « aujourd'hui moins 31 jours » — et la
contamination démarre 31 jours avant le run.

### Ce que la réparation a appris sur les tests eux-mêmes

Il a fallu **quatre versions** du détecteur avant qu'il n'accuse que les
coupables. Chaque version ratée est une leçon :

1. « bougie entière identique (o,h,l,c,v) » — ne trouvait RIEN. Les volumes
   diffèrent : la contamination passe par le cours, pas par la bougie.
2. « trois clôtures identiques » — accusait ADI et M2M sur trois égalités
   espacées de **dix-neuf mois**. Deux titres finissent toujours par se croiser.
3. « trois clôtures identiques D'AFFILÉE » — accusait AFI et RISMA, qui cotaient
   tous deux **350,00** trois séances durant, avec des volumes sans rapport
   (37 334 contre 30 246). Un prix rond est un rendez-vous.
4. La bonne règle : une plage de ≥3 séances calées sur un autre titre, **dont le
   niveau est incompatible avec celui du titre lui-même** (rapport > 1,5).

⚠️ **ET LE RAPPORT DOIT ÊTRE SYMÉTRIQUE.** Écrit `dedans/ref - 1`, il donnait
−48 % pour ATL (67 contre 130) et passait sous un seuil de 50 % : le titre
échappait au contrôle de deux points. Une division par deux est aussi suspecte
qu'un doublement.

### Et R10 n'est pas une loi de la bande

Mon premier test bloquait toute variation supérieure à ±10 % entre deux bougies.
Il a accusé :
- **VCNE** d'un −15 % qui s'étalait sur un MOIS — sa série a un trou du 12/05 au
  11/06. « Deux bougies voisines » n'est pas « deux séances voisines » ; le
  calendrier du marché se déduit des données (une date où plus de trente titres
  ont coté est une séance).
- **Crédit Eqdom** d'un −14,3 % le 11/02/2025 que **l'export de l'opérateur
  porte lui-même**, après plusieurs séances sans échange réel.

**R10 est un contrôle de NOTRE qualité, pas un invariant du marché.** Un test qui
l'applique aveuglément refuse les données de la Bourse.

### La parade

Ne pas chercher à vérifier l'appariement — il est hors de portée. **Juger le
résultat** : `extension_credible()` refuse un historique rapatrié qui ne se
raccorde pas au dernier cours connu (±10 %) ou qui tombe sur la série d'un autre
émetteur trois séances de suite. Les deux épreuves, parce qu'aucune ne suffit :
le raccord est muet quand on ne connaît rien du titre — le cas de Maroc Leasing.

---

## Famille 14 — Mes propres contrôles ont bloqué la publication (17/09/2026)

> ⚠️ CETTE FAMILLE EST LA PLUS GÊNANTE DU FICHIER. Les quatre tests qui ont
> empêché le terminal de se mettre à jour pendant une séance ouverte sont les
> miens, écrits la veille et l'avant-veille. Aucun ne décrivait une règle : tous
> figeaient l'état du jour où je les ai écrits.

    17/09/2026, 10h11 UTC — séance ouverte depuis 9h30 (Casablanca).
    Le moteur tourne, produit data.json, et les contrôles bloquants refusent.
    Le terminal reste sur la clôture de la veille.

### 1. « la série publiée EST l'export » — interdisait aux titres de coter

    assert [b["d"] for b in serie] == sorted(export)

L'export de l'opérateur s'arrête au 16/09. Dès que le moteur a ajouté la bougie
du 17, cinq titres ont été déclarés fautifs.
**Cause** : j'ai confondu « l'export fait foi » avec « l'export est tout ».
**Règle** : sur la période QUE L'EXPORT COUVRE, la série est l'export. Après,
elle est libre.
⚠️ **J'avais corrigé exactement cette faute sur CMT l'avant-veille**, en écrivant
qu'« un test qui exige que la série s'arrête à une date n'énonce plus une règle :
il interdit au titre de coter ». Je l'ai refaite deux jours plus tard, sur cinq
titres d'un coup. Savoir énoncer la leçon n'est pas la même chose que l'appliquer.

### 2 et 3. « aucune bougie à volume nul » — interdisait une séance sans échange

    assert all(b["v"] > 0 for b in serie)

À 11h, CMT — rouverte la veille après deux mois de suspension — n'avait pas
encore trouvé de contrepartie. Sa bougie du jour avait un volume nul.
**Cause** : j'ai généralisé à toute la série une signature qui ne valait que
dans la fenêtre de suspension. Les 28 fantômes de juillet étaient des bougies à
volume nul PENDANT la suspension ; c'est la fenêtre qui les caractérisait, pas
le volume.
**Signal** : un contrôle qui se déclenche sur un titre peu liquide un jour
ordinaire ne décrit pas une anomalie.

### 4. « opération de masse » — un run quotidien en est une

    bouges = {titres dont le fichier de chandelles diffère de origin/main}
    assert len(bouges) < univers / 3

Le moteur ajoute une bougie à chaque titre coté, tous les jours. Le contrôle a
compté **52 séries modifiées sur 75** et conclu à une opération de masse.
**Cause** : j'ai mesuré « le fichier a changé » là où je voulais dire « l'histoire
déjà publiée a été réécrite ». Ajouter la séance du jour n'est pas réécrire.
**Règle** : ne comparer que la partie commune — jusqu'à la dernière date que
`origin/main` publiait pour ce titre.

### Ce que cette famille apprend

**Un test écrit sur l'état du jour hérite de tout ce que cet état a
d'accidentel.** Les quatre sont passés au vert chez moi : j'avais lancé le
moteur, donc mes données portaient déjà la séance du jour, et je les ai figées
sans le voir.

⚠️ **LA PARADE N'EST PAS DE RELIRE PLUS ATTENTIVEMENT.** C'est de se demander,
pour chaque assertion : *« qu'est-ce qui, demain, la ferait rougir sans que rien
soit cassé ? »* Une date qui avance, un titre qui ne traite pas, une séance qui
s'ajoute. Si la réponse existe, l'assertion décrit un instantané.

⚠️ **ET LA PORTE BLOQUANTE A BIEN FONCTIONNÉ.** Elle a refusé de publier un
fichier que les contrôles rejetaient — c'est exactement son rôle. Le défaut
n'était pas dans la porte, il était dans ce que je lui avais demandé de vérifier.

---

## Famille 15 — Une séance qui a eu lieu, puis n'a plus existé (17/09/2026)

> ⚠️ CELLE-CI N'A ÉTÉ TROUVÉE PAR AUCUN CONTRÔLE DU DÉPÔT. C'est Abd Moutalib
> qui a signalé l'information, depuis un article de presse. Aucune de nos trois
> sources ne l'aurait dite.

    09h30   la Bourse de Casablanca ouvre, les échanges démarrent
    10h39   Alphabourse : « la séance suspendue », incident technique
    11h18   dernier échange, tous titres confondus
    11h47   toujours rien — 47 484 titres au total, contre 216,3 MDH la veille
    le soir la Bourse ARRÊTE DÉFINITIVEMENT la séance. Toutes les transactions,
            saisies, modifications et annulations d'ordres sont annulées. La
            reprise se fera sur les carnets arrêtés à la clôture du 16.

### Pourquoi aucun garde-fou ne pouvait la voir

| | Se reconnaît par | Le 17/09 |
|---|---|---|
| **Férié** | un calendrier écrit d'avance | la date n'y est pas |
| **Séance fantôme** | ≥95 % de clôtures identiques à la veille | **17 %** |
| **Séance annulée** | *rien dans les données* | — |

Les cours étaient **authentiques** : volumes réels, heures d'échange
échelonnées de 09h30 à 11h18, variations plausibles. **C'est leur existence
juridique qui a été retirée, pas leur vraisemblance.**

⚠️ **AUCUNE SOURCE DE COTATION NE PUBLIE LE STATUT D'UNE SÉANCE.** Elles
servent des cours. BMCE a continué de servir 55 titres datés du 17/09 *après*
l'annulation. Il n'existe aucun signal interne : la seule défense est une
déclaration écrite à la main, `SEANCES_ANNULEES`.

### Ce que la réparation a révélé au passage

**La capitalisation retombait sur la table figée dès que les sources se
taisaient.** Le code disait `lp.get("cap") or fd.get("cap")` : en écartant les
lignes de la séance annulée, la capitalisation de la moitié de la cote est
tombée sur `FOND_DATA`, où Wafa Assurance vaut 6 500 MDHS contre 18 200 au
marché et Taqa 8 500 contre 41 068. Quatre contrôles ont rougi ensemble.

⚠️ **CE DÉFAUT EXISTAIT DEPUIS TOUJOURS.** Il suffisait que les sources soient
muettes une journée. L'annulation ne l'a pas créé, elle l'a exposé. La
capitalisation publiée la veille passe désormais avant la table, et le champ
`cap_source` le dit : `publiee_la_veille`, jamais « servie ».

### Deux erreurs dans mon propre correctif, trouvées en le mesurant

1. **J'ai écarté 77 lignes au lieu de 55.** Presque toutes les sources datent
   leurs lignes du jour, même quand elles portent le cours de la veille.
   Écarter par la date est juste — mais il ne restait que trois lignes.
2. **La séance de référence est tombée au 05/08**, six semaines en arrière,
   parce que je la recalculais sur le maximum des lignes SURVIVANTES. Elle se
   reprend aux chandelles, qui tiennent la dernière séance réellement valide —
   exactement comme le fait `_cliquet_seance` depuis le 28/08.

**Un correctif se mesure avant d'être cru.** Les deux défauts ne se voyaient
pas à la lecture ; ils ont sauté aux yeux au premier run.

### La règle

*Un cours peut être exact et sans objet.* Notre chaîne vérifie la
vraisemblance — dates, continuité, identité, plafonds. Elle ne vérifie pas
l'existence, parce que l'existence n'est pas dans les chiffres. Pour ça, il
faut une déclaration reçue.

---

## Famille 16 — Une règle juste, sans issue de secours (18–19/09/2026)

**La séance du 18/09 a été cotée, publiée en prix, et n'a jamais eu de bougie.**

### L'enchaînement

```
18/09  les cinq tests de la famille 14 échouent à nouveau — dont un qui
       épinglait deux dates — et font échouer TOUS les runs de séance.
       Les deux runs tardifs (17h47, 17h57) « réussissent » sans rien faire :
       la porte horaire saute les étapes 4 à 12.
       → aucune bougie du 18/09 n'est jamais commitée
19/09  l'étape 6c : « dernière séance cotée = 2026-09-18, pas aujourd'hui
       — aucune bougie ajoutée »
       → le trou devient DÉFINITIF
```

### Ce qui distingue cette famille de la 14

La règle de l'étape 6c **était juste**. Elle protégeait contre un vrai défaut :
un run du week-end reçoit la clôture de vendredi et l'écrivait comme une séance
du samedi. Elle n'avait simplement **aucune issue de secours**. Une journée
dont tous les runs échouent perdait sa bougie pour toujours, et rien dans le
système ne pouvait plus la rattraper.

⚠️ **Un garde-fou sans porte de sortie transforme une panne d'un jour en perte
définitive.** C'est la leçon. Chaque refus d'écrire devrait répondre à la
question : « et si personne n'écrit aujourd'hui, qui écrira demain ? »

### Le symptôme était lisible, et on le prenait pour du bruit

`verifier_seance.py` échouait chaque jour avec deux contrôles rouges. Il ne
criait pas au loup : il comparait la séance portée par `data.json` (18/09) à
celle déduite des chandelles (16/09) et signalait exactement le trou. Une fois
la bougie rattrapée, les douze contrôles sont passés au vert sans qu'on touche
au contrôle lui-même.

⚠️ **Avant de corriger une alerte qui se répète, vérifier qu'elle n'a pas
raison.** Ici elle décrivait le défaut avec précision depuis le premier jour.

### Trouvé en chemin — deux mines amorcées pour le lundi

1. **T2S**, seul titre à avoir des chandelles sans entrée de cache. Dès qu'une
   séance ordinaire modifie ses bougies, `--sync-ajouts` refuse — il
   synchronise, il ne crée pas — et sort en **code 2**, ce qui bloque la
   publication. Le refus est juste ; il manquait l'entrée.

2. **`tests.yml` jugeait un état que la production ne publie jamais.** Il lance
   le moteur pour de vrai, mais n'avait pas l'étape de synchronisation du cache
   que `update_bvc.yml` exécute entre la génération et les contrôles. L'écart
   restait invisible tant que le moteur n'ajoutait qu'une bougie par jour.

⚠️ Ces deux-là auraient bloqué le moteur lundi **indépendamment** du correctif.
Elles n'ont été vues que parce que le rattrapage a fait entrer 65 bougies d'un
coup. Une panne les a révélées ; sans elle, elles explosaient en séance.

### Et un défaut de données, non traité

**11 titres portent 655 bougies OHLC incohérentes dans le cache**, alors que
tous les fichiers de chandelles sont sains : la réparation du 04/09 a corrigé
les fichiers sans re-dériver `historical_data.json`.

```
TGC 92 · SMI 83 · SRM 80 · VCNE 62 · RIS 60 · RDS 57
CMGP 55 · MSA 54 · SGTM 47 · CASH 34 · CFGB 31
```

Huit sont des MASI 1. C'est ce que lit le graphique du terminal, et ça se
propage : SGTM affiche un plus-bas 52 semaines de **508,10 au lieu de 461,95**.

⚠️ **CFGB et CMGP portent des corrections réceptionnées** : un `--complet`
aveugle risquerait de les annuler — c'est le piège SOT documenté le 18/08.
À traiter avec `gardien-donnees`, pas en passant.
