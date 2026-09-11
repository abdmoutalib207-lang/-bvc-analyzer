# Candidat de fusion limité — construit, mesuré, pas fusionné

> ⚠️ **Rien n'est fusionné ni publié.** Ce document décrit un arbre qui existe
> et se reconstruit à la commande. La décision appartient au propriétaire.

```
python pipeline/candidat_fusion.py --sortie /tmp/candidat
```

| | |
|---|---|
| **branche de livraison** | `release/bvc-correctifs-valides-20260911` |
| **commit** | `9a95d5cdbf3707ec4006c8f7333d913eca9fda63` |
| base | `origin/main` `27228f46` — 11/09/2026 15h57 |
| apport | branche `claude/terminal-bvc-review-AmnBU` `0c4c53ea` |
| fichiers repris | **27** |
| historique | `pipeline/historical_data.json` **conservé à l'identique** — assainissement hors périmètre |
| suite sur ce candidat | **373 passés, 0 ignoré, 0 échec** — sur le fichier généré par ce code |
| construction | **déterministe** |
| artefacts de revue | `data_teste.json` + rapport JUnit + 3 captures + bibliothèques épinglées |

---

## 1. La coupure, et ce qui la justifie

Une seule question sépare les deux lots : **est-ce que cela change ce que le
site sert ?**

| | Lot A — **mis en ligne** | Lot B — **retenu** |
|---|---|---|
| quoi | le moteur qui écrit `data.json`, le terminal qui l'affiche, les pièces qu'ils lisent, les garde-fous de publication, et leurs tests | la couche de qualification et d'identité (lots 1A à 1G) |
| effet sur le site | **visible immédiatement** | **aucun** — elle juge ce qui a le droit d'ENTRER dans l'historique |
| état devant la revue | corrections **confirmées par l'auditeur** le 09/09 et le 10/09 | **non réceptionné** — livré le 11/09, pas encore relu |

### ⚠️ La dépendance que cette coupure suppose est mesurée, pas supposée

Si le lot A importait quoi que ce soit du lot B, l'arbre fusionné ne
démarrerait pas — et on s'en apercevrait sur le run du matin, en production.

`candidat_fusion.verifier_independance()` le vérifie **sur l'arbre
syntaxique** (une mention en commentaire n'est pas un import), et
`tests/test_candidat_fusion.py` l'exécute à chaque suite, avec un contre-test
qui prouve que le contrôle sait échouer.

```
independant : true · imports_interdits : [] · fichiers_absents : []
```

**Aucune pièce du lot B ne remonte dans le lot A.** La coupure n'a plus
d'exception, et un test l'exige.

Deux pièces ont été **retirées** du lot A après mesure :

- `pipeline/calendrier_bvc.json` — lu seulement par `normaliser.py` et deux
  tests du lot B.
- `pipeline/resoudre_historique.py` — voir §3 : il n'y a pas de conflit à
  résoudre dans cette méthode de construction.

Deux pièces ont été **ajoutées** après mesure, et elles ne portent aucune
correction : `tests/test_faits_financiers.py` et `tests/test_univers.py` sont
repris parce qu'ils **lisent le fichier publié**. Les laisser en arrière ferait
lire à une partie de la suite la livraison et à l'autre le dépôt — voir §5.

---

## 2. Ce qui serait mis en ligne — liste exacte

Chaque ligne est mesurée sur le `data.json` produit par le candidat, comparé à
celui que le site sert aujourd'hui.

### Corrections visibles sur le terminal

| # | Correction | Effet mesuré (avant → candidat) |
|---|---|---|
| 1 | **Un titre suspendu ne porte plus de variation** — CMT affichait −3,35 % et une séance du 11/09 alors qu'il ne cote plus depuis le 17/07 | `chg` **−3,35 → 0,00** · `prix_asof` **11/09 → 16/07** · `stale` **false → true** · `source_prix` `idbourse` → `derniere_cotation_avant_suspension` · prix **4 350 → 4 501** (la dernière cotation réelle) |
| 2 | **Le mode personnalisé combine enfin les vraies composantes** — il lisait `bvc` (la note BVC de référence) à la place de `score_fond` : il ne changeait pas les poids mais les **ingrédients** | ADH en 70/30 : **5,01 → 6,32**. Le `score_fond` d'ADH vaut bien **6,15**, le chiffre que l'audit du 09/09 réclamait |
| 3 | **Les composantes sont émises** — `score_fond` et `score_nlp` n'existaient dans aucun fichier : le terminal ne pouvait pas les utiliser même en le voulant | `score_fond` **0 → 80 titres** · `score_nlp` **0 → 80 titres** |
| 4 | **Le price-to-book vient des dépôts AMMC, ou n'est pas affiché** | `pb` **60 → 4 titres**. ⚠️ Voir l'encadré ci-dessous |
| 5 | **Dividendes sur résolution d'assemblée générale** — la table avait un an de retard hors MASI 1 | `div` corrigé sur **37 titres**, `div_dh` sur **32** (ex. BCP 4,29 % → 4,49 %, 10,50 → 11,00 DH) |
| 6 | **Sept BPA corrigés sur pièces** | ex. RIS **18,82 → 16,84** |

> ### ⚠️ La correction n°4 — le compte exact
>
> | | titres |
> |---|--:|
> | **P/BOOK disponible** — `pb_source: faits_ammc` | **4** |
> | **P/BOOK indisponible** | **76** |
> | dont **valeurs retirées** par cette correction | **56** |
> | dont déjà absentes avant | 20 |
>
> Les 56 retirées portaient **toutes** `pb_fige: true` : elles venaient de la
> table figée de juin, pas d'un dépôt. Ce n'est pas une perte de données —
> c'est l'arrêt d'une affirmation sans source. Mais l'utilisateur verra un
> tableau plus vide qu'hier, et c'est la décision qui revient au propriétaire.
>
> ⚠️ **Un ratio absent n'est jamais présenté comme zéro.** Le terminal rend
> `r.pb?.toFixed(2) || "—"` : une valeur absente affiche **« — »**, jamais
> `0.00`. Vérifié à l'écran (§5).

### Corrections invisibles sur le terminal, mais décisives

| # | Correction | Ce qu'elle change |
|---|---|---|
| 7 | **La publication est bloquée par les tests** — l'ordre était générer → **publier** → tester, avec `continue-on-error`. Le 09/09 à 23h50, un fichier fautif est parti en production et la suite l'a « signalé » après coup | la **suite entière** tourne sur le fichier fraîchement écrit, **avant** publication. ⚠️ Coût assumé : un test rouge suspend le bulletin du matin |
| 8 | **Le bulletin matinal n'a jamais été envoyé** — 12 exécutions, 12 échecs depuis le 03/09, sur un secret `MAIL_TO` absent que le message d'erreur ne nommait pas | l'étape échoue **avant** la tentative d'envoi, en nommant le secret manquant et où le poser |
| 9 | **Séances fantômes et cliquet de séance** (`pipeline/seance.py`, `generate_candles.py`) | conservés depuis la branche, couverts par les tests du lot A |

### Ce qui bouge sans être une correction

⚠️ À ne pas porter au crédit du candidat : `obv` (56 titres), `adx` et ses
composantes (24 à 27), `vol_median20` (23) et `vol` (8) changent parce que le
moteur a recalculé sur des chandelles plus fraîches — **pas** parce qu'un
défaut a été corrigé. `setup` de CSR passe de NEUTRE à CONTRARIEN pour la même
raison.

---

## 3. L'historique : conservé tel quel, assainissement hors périmètre

**`pipeline/historical_data.json` n'est pas repris.** Celui de `main` est
conservé **à l'octet près** — empreinte `711b851b0048`, vérifiée à chaque
construction.

> ### ⚠️ Ce que je faisais, et pourquoi c'était une dépendance inutile
>
> La version précédente importait ce fichier depuis la branche et
> « résolvait » le conflit de la fusion globale. La revue a montré que ce
> conflit **n'existe pas dans cette méthode** : en partant de `main` par
> reprise de fichiers choisis, il suffit de ne pas y toucher.
>
> Le patch ne changeait d'ailleurs **aucune valeur**. Il ajoutait un bloc
> `_resolution` — et ce bloc **déclarait** quatre arbitrages d'extrema que la
> revue n'avait pas validés. Écrire « la fenêtre a glissé, les deux valeurs
> sont justes » est une **affirmation**, pas une mesure : retenir l'argument de
> droite ne prouve ni l'un ni l'autre.
>
> `pipeline/resoudre_historique.py` sort donc du périmètre. Il reste sur la
> branche de recherche, avec la couche retenue.

**Ce candidat ne prétend rien sur la justesse de cet historique.** Il n'y
touche pas. Les cinq semaines de cours Mutandis dans l'historique de MSA y
restent, comme elles y sont aujourd'hui.

---

## 4. Tests : le nouveau code jugé sur un fichier écrit par lui

### ⚠️ Le problème que la revue a relevé, et qui bloquait la demande de fusion

`.github/workflows/tests.yml` lançait la suite **juste après l'installation**,
donc sur le `data.json` du dépôt — écrit par le moteur **précédent**. Les
contrôles qui relisent les données publiées échouaient donc sur toute demande
de fusion touchant le moteur.

**Et ils avaient raison** : le fichier publié ne satisfait pas encore le nouveau
contrat. Ce n'est pas un défaut de la demande.

**La mauvaise réponse aurait été de déclarer ces échecs « attendus »** et de
fusionner par-dessus. Un échec qu'on apprend à ignorer ne protège plus rien —
c'est exactement l'habitude qui a laissé publier, le 09/09 à 23h50, un
rendement sur une société qui n'a rien versé.

### La procédure

| Étape | Ce qu'elle fait | Pourquoi |
|---|---|---|
| 1. **Générer** | `python update_data.py` écrit `data.json` **et** les chandelles | juger le code sur un fichier écrit **par lui** |
| 2. **Identifier** | empreinte sha256, horodatage, 80 titres, **provenance des prix par source** | un rouge doit être attribuable sans relire les journaux |
| 3. **Juger** | la suite entière, sur l'état complet que le moteur vient d'écrire | même règle que la garde de publication |
| 4. **Joindre** | le fichier jugé et le rapport JUnit, en artefacts | permettre de **rejouer** ce vert ailleurs |

⚠️ **Rien n'est restauré entre 1 et 3.** Remettre les chandelles du dépôt
ferait juger un `data.json` neuf contre des séries anciennes — une paire
incohérente que personne n'aura jamais en production. C'est une erreur que j'ai
commise en écrivant cette procédure, et que la mesure a rattrapée : avec les
chandelles restaurées, la suite passe de **373 passés, 0 ignoré** à
**1 échec, 367 passés, 5 ignorés**.

⚠️ **Cette étape sort du réseau.** C'est le seul endroit de la chaîne de tests
qui le fasse, et elle est **en dehors** de la suite : la règle « aucun test ne
touche le réseau » (`tests/conftest.py`) reste intacte.

⚠️ **Si la collecte est dégradée, cela se voit avant le résultat.** L'étape 2
compte les titres servis par un repli muet (`static`, `data_json_precedent`,
`financial`) et le dit dans le résumé. Un rouge peut alors venir d'une source
en panne, pas de la modification — **il faut établir la cause, pas écarter le
contrôle**.

### Rejouer ce vert ailleurs — `BVC_DATA_JSON`

`tests/conftest.py` expose un **point d'entrée unique** vers le fichier publié
soumis aux contrôles. `BVC_DATA_JSON` le désigne :

```bash
BVC_DATA_JSON=data_teste.json python -m pytest
```

⚠️ **Ce n'est pas une soupape pour rendre la suite verte.** Pointer vers un
fichier arbitraire ne prouve rien : le fichier doit être **identifié** —
empreinte et provenance — et c'est ce que la CI et ce dossier publient à côté
du résultat. Un chemin qui n'existe pas lève une erreur au lieu de retomber en
silence sur le dépôt, et un test le vérifie.

⚠️ **Le point d'entrée doit être le SEUL.** Une première version ne branchait
que la fixture partagée : **six lectures en dur subsistaient** dans cinq
fichiers, et une relecture hors ligne jugeait alors un mélange — une partie de
la suite lisant la livraison, l'autre le dépôt. Un mécanisme à moitié branché
est pire que pas de mécanisme ; c'est la faute que ce projet a déjà payée cette
semaine avec un garde-fou défini et appelé de nulle part. Un test parcourt
désormais l'arbre syntaxique de tous les fichiers de tests et refuse toute
lecture directe de `data.json`.

### Ce que le candidat donne

| Moment | Résultat |
|---|---|
| sur le `data.json` du dépôt (celui de `main`) | **1 échec** — `test_un_titre_suspendu_ne_porte_aucun_signal[CMT]` |
| après l'étape 1, sur le fichier généré | **373 passés, 0 ignoré, 0 échec** |

L'échec initial n'est pas un défaut : c'est le test qui relit le **fichier
publié**, écrit par l'ancien moteur, qui laissait CMT à −3,35 %.

---

## 5. Prévisualisation du terminal

> ⚠️ **Ce que le bac d'aperçu substitue, et ce qu'il ne prouve donc pas.**
> Le navigateur du conteneur n'atteint pas les CDN (`ERR_CONNECTION_RESET`).
> Les quatre bibliothèques épinglées (React 18, ReactDOM 18, Babel 7.23.10,
> lightweight-charts 4.2.0) ont été téléchargées par le proxy autorisé et
> servies localement, **aux mêmes versions**. L'`index.html` du bac est celui du
> candidat, **aux quatre URL près**.
> Cet aperçu ne dit donc **rien** sur la disponibilité des CDN en production.
>
> **Versions exactes conservées dans le dossier de réception** (`apercu/vendor/`) :
>
> | fichier | bibliothèque | taille | sha256 |
> |---|---|--:|---|
> | `react.js` | React 18 `react.production.min.js` | 10 751 o | `d949f1c3687aedadcedac85261865f29…` |
> | `react-dom.js` | ReactDOM 18 `react-dom.production.min.js` | 131 835 o | `35f4f974f4b2bcd44da73963347f8952…` |
> | `babel.js` | `@babel/standalone` 7.23.10 | 2 849 975 o | `85ba0c7207cf1b1850e40372f26a7e69…` |
> | `lwc.js` | `lightweight-charts` 4.2.0 standalone | 163 551 o | `46fc69534ec098f095bbcd1d9a26d693…` |

| Contrôle | Résultat |
|---|---|
| compilation JSX (aucun test Python ne la voit) | **aucune erreur** — la page se rend |
| titres affichés au classement | **80** |
| erreurs JavaScript | **aucune** (hors `favicon.ico`, absent du bac seulement) |

### Graphiques

| Contrôle | Résultat |
|---|---|
| `fetchChart()` lit `./pipeline/candles/<sym>.json` | **HTTP 200** sur CMT, IAM, ADH |
| toile de tracé | **1 178 × 192 px**, chandelles, MA20/MA50, volume, MACD, Fibonacci |
| titres éprouvés | CMT (suspendu), IAM, ADH |

> ### ⚠️ Défaut trouvé à l'aperçu — **préexistant, pas introduit par le candidat**
>
> La mention **« Données historiques non disponibles pour ce titre »** reste
> affichée **par-dessus un graphique qui s'est correctement tracé**, sur les
> trois titres testés.
>
> Cause : `index.html:790` injecte ce message par `innerHTML` au premier rendu,
> quand la série n'est pas encore chargée ; la bibliothèque ajoute ensuite sa
> toile dans le même conteneur, mais le message n'est jamais retiré.
>
> **Le bloc est rigoureusement identique dans `main`** (vérifié caractère par
> caractère) : le site le fait déjà aujourd'hui. Ce n'est donc **pas une
> régression**, mais c'est une phrase fausse montrée à l'utilisateur.
>
> **Non corrigé ici, délibérément** : ce candidat ne contient que des
> corrections déjà constatées et éprouvées. Y glisser un correctif écrit à
> l'instant contredirait sa raison d'être.
>
> **Inscrit comme prochain petit correctif**, avec les trois états à vérifier :
>
> | état | ce que le terminal doit montrer |
> |---|---|
> | **chargement** — la série n'est pas encore arrivée | un indicateur d'attente, **pas** « données non disponibles » |
> | **données présentes** | le graphique seul, **sans message résiduel** |
> | **données absentes** — titre sans chandelles | le message, **et pas de toile vide** |
>
> Le correctif tient en une ligne — vider le conteneur avant de créer le
> graphique — mais les trois états doivent être éprouvés, faute de quoi on
> déplacerait le défaut au lieu de le corriger.

### CMT

```
CMT · 4 501 DH  ⚠ 16/07  ▼ 0.00%     6.68 Score composite / 10
SUSPENDU depuis le 17/07 — OPA obligatoire (Ayrad / OSEAD / CIMR)
PE RATIO 38.5 · P/BOOK 8.40 · DIVIDENDE — · CAP. 7,3 Md
```

Le badge porte la **séance réelle** (16/07), la variation est nulle, la
suspension et son motif sont affichés, et le P/BOOK conservé est l'un des
quatre issus des dépôts AMMC.

### Pondérations

Six boutons : `OFFICIEL` · `70/30` · `60/40` · `50/50` · `40/60` · `30/70`.

| | OFFICIEL | 70/30 |
|---|---|---|
| bandeau | — | **« MODE PERSONNALISÉ · SIMULATION — signal masqué »** |
| colonne SIGNAL | `ACHETER ★★` | **`—`** (le signal n'existe que pour la pondération officielle) |
| colonne POIDS | `F52·N28·T20` | `F70·N0·T30` |
| score | `6,51` | `6,32✱` |

**Vérification arithmétique du correctif n°2**, sur trois témoins :

| titre | `score_fond` | `score_tech` | `(F×70 + T×30)/100` | à l'écran | avec `bvc` on aurait eu |
|---|--:|--:|--:|--:|--:|
| IAM | 7,25 | 6,70 | **7,08** | 7,08 ✔ | 6,97 |
| ADH | 6,15 | 6,70 | **6,32** | 6,32 ✔ | 5,01 |
| HPS | 6,40 | 6,70 | **6,49** | 6,49 ✔ | 7,01 |

Les trois écarts avec la colonne de droite établissent que le mode
personnalisé lit bien `score_fond`, et non plus `bvc`.

---

## 6. Séquence de déploiement — ce qui devient accessible, et quand

> ⚠️ **« Le premier run après fusion » ne doit pas rester une étape supposée.**
> Elle est ici mesurée, et elle a une conséquence que je n'avais pas vue.

**Aucun workflow ne déploie GitHub Pages** : il n'existe pas de `pages.yml`.
Pages sert donc **directement depuis `main`**. Tout commit sur `main` déclenche
une reconstruction ; le délai est une caractéristique de GitHub que nous ne
contrôlons pas.

| # | Événement | Ce qui devient accessible | Délai |
|---|---|---|---|
| 1 | fusion sur `main` | **le nouveau `index.html`** — et lui seul | reconstruction Pages |
| 2 | — | **`data.json` est encore l'ancien** | ⚠️ jusqu'au run suivant |
| 3 | `update_bvc` s'exécute | garde bloquante : suite entière sur le fichier fraîchement écrit | — |
| 4 | la garde passe | `data.json` corrigé poussé sur `main` | |
| 5 | reconstruction Pages | **les corrections 1 à 6 deviennent visibles** | |

### ⚠️ L'étape 2 n'est pas neutre — mesurée dans le bac d'aperçu

J'ai servi le **nouveau `index.html` avec l'ancien `data.json`** :

| | attendu après le run | pendant la fenêtre |
|---|--:|--:|
| ADH en 70/30 | 6,32 | **5,01** |
| IAM en 70/30 | 7,08 | **6,97** |
| CMT, variation | 0,00 % | **−3,35 %** |
| IAM, P/BOOK | — | **6,20** |

**Rien ne casse** — 80 titres rendus, aucune erreur JavaScript. Mais
`score_fond` étant absent de l'ancien fichier, `computeDisplayScore` retombe
sur son repli `r.bvc` : **pendant cette fenêtre, le mode personnalisé affiche à
nouveau la valeur que l'audit du 09/09 avait signalée.**

Seuls les éléments purement frontaux sont immédiats : le bandeau
« SIMULATION », le signal masqué hors pondération officielle, l'affichage des
poids.

### Fermer la fenêtre au lieu de l'attendre

Les crons sont à ≈09h40, 12h00, 15h45, 18h00 (Casablanca), avec un décalage
**mesuré de 2 à 8 heures** et des journées entières sans déclenchement. Attendre
le prochain run peut donc durer un jour.

`update_bvc.yml` accepte `workflow_dispatch`, et sa porte d'entrée s'ouvre sur
ce déclencheur. **La séquence doit donc être :**

```
1. fusionner
2. déclencher update_bvc À LA MAIN, immédiatement  (Actions → update_bvc → Run workflow)
3. surveiller ce run : c'est la garde bloquante qui décide
4. vérifier le terminal une fois data.json publié
```

⚠️ **Ne pas lancer ce run entre 15h30 et 16h00** : une source a servi la séance
précédente dans cette fenêtre le 28/08, et un run manuel non nécessaire avait
provoqué l'incident.

### Vérifier que l'étape 5 a eu lieu

```bash
python3 -c "import json,urllib.request as u; \
d=json.load(u.urlopen('https://<site>/data.json')); \
t={x['symbol']:x for x in d['tickers']}; \
print('CMT chg =', t['CMT']['chg'], '| IAM score_fond =', t['IAM'].get('score_fond'))"
```

`0.0` et `7.25` : les corrections sont en ligne.
`-3.35` et `None` : le run n'a pas encore publié — la fenêtre de l'étape 2 est
toujours ouverte.

---

## 7. Le candidat comme objet applicable

Le candidat n'est pas qu'un dossier : il existe aussi comme **patch qui
s'applique sur `origin/main`**.

```
candidat_fusion_27228f46.patch   182 Ko   sha256 2ccac6960fc3fb69…
25 fichiers · 2 650 insertions · 126 suppressions
```

Vérifié dans un arbre neuf tiré de `origin/main` :

```
git apply --check candidat_fusion_27228f46.patch   → s'applique proprement
git apply         candidat_fusion_27228f46.patch
python -m pytest                                    → 1 échec attendu (§4),
                                                      0 après le run du moteur
```

⚠️ Le patch ne contient **ni `data.json`, ni les chandelles, ni
`masi_history.json`, ni `snapshot_cloture.json`** : ces fichiers sont produits
par le robot, pas apportés par la fusion. Les inclure ferait passer pour un
apport ce qui n'est qu'une sortie de moteur.

La branche `release/bvc-correctifs-valides-20260911` porte le même contenu —
voir §10.

---

## 8. Contrôles d'acceptation sur les 80 titres

| Contrôle | avant | candidat |
|---|--:|--:|
| titres servis | 80 | **80** |
| MASI 1 avec un prix (R1) | 19 | **19** |
| titres sans bloc `_meta` | 0 | **0** |
| `v53` hors [0, 10] | 0 | **0** |
| variations > ±10 % (R10) | 0 | **0** |
| titres suspendus portant une variation | **1** | **0** |
| `score_fond` émis | 0 | **80** |
| price-to-book affiché | 60 | **4** ⚠️ |
| dividendes renseignés | 64 | 65 |
| répartition de la confiance | `{0:3, 1:2, 2:18, 3:27, 5:30}` | **identique** |

Aucun ticker perdu, aucune fraîcheur dégradée, aucune variation hors R10.

---

## 9. Limites qui subsistent après cette mise en ligne

1. **Le moteur publié n'est pas protégé contre la contamination d'identité.**
   `update_data.py` et `generate_candles.py` écrivent des chandelles sans
   aucun contrôle d'identité. **Ne pas cocher « moteur publié protégé ».**
2. **L'historique n'est pas assaini, et ce candidat n'y touche pas.** Les cinq
   semaines de cours Mutandis dans `pipeline/candles/MSA.json` et dans
   `pipeline/historical_data.json` restent exactement où elles sont. Le lot B
   empêche d'en écrire de nouvelles ; il ne nettoie pas l'existant, et il est
   retenu.
3. **Les historiques d'ATL, CFGB et DAR**, nommés par la pièce de juin, sont
   inchangés.
4. **Le cron GitHub reste le premier risque du projet** — journées entières
   sans déclenchement. Rien ici ne le traite.
5. **Le garde-fou bloquant est une arme à deux tranchants** : un test rouge
   suspend une publication légitime. C'est le sens même d'un contrôle
   bloquant, mais il faut le savoir avant, pas le découvrir un matin.
6. **56 fiches perdent leur P/BOOK.** Correction voulue, régression visible.
7. **La mention « Données historiques non disponibles »** s'affiche par-dessus
   les graphiques — préexistant, non corrigé ici, inscrit comme prochain petit
   correctif avec ses trois états (§5).
8. **Une fenêtre suit la fusion** pendant laquelle le nouveau terminal sert
   l'ancien `data.json`, et le mode personnalisé y réaffiche la valeur
   signalée par l'audit (§6). Elle se ferme en déclenchant `update_bvc` à la
   main.
9. **Aucune performance n'est démontrée**, et rien dans ce candidat n'y touche.

---

## 10. Branche de livraison et retour arrière

### La branche

```
release/bvc-correctifs-valides-20260911
```

Partie de `origin/main` `27228f46`, elle contient **uniquement** le candidat
limité. **La branche de recherche n'y est pas fusionnée** — ni en tout, ni en
partie au-delà des 27 fichiers listés.

⚠️ **Mode de fusion, et ce qu'il change pour le retour arrière.** La branche
n'a qu'un commit au-dessus de `main`. Deux modes sont possibles, et ils
n'annulent pas de la même façon :

| mode | ce que `main` reçoit | comment on annule |
|---|---|---|
| **fusion sans avance rapide** (`--no-ff`, recommandé) | un commit de fusion | `git revert -m 1 <fusion>` — une seule commande, et l'apport est nommé dans l'historique |
| avance rapide / écrasement | un commit ordinaire | `git revert <commit>` — l'apport se confond avec les commits de données du robot |

Le premier est recommandé **parce qu'il rend l'annulation évidente** : le
commit de fusion porte l'apport entier et se désigne d'un coup d'œil.

### Contrôles de cette branche, avant publication

| contrôle | résultat |
|---|--:|
| la branche part bien de `main` retenu | `27228f46` |
| fichiers apportés | **27** |
| `pipeline/historical_data.json` conservé à l'identique | ✔ `711b851b0048` |
| le lot A n'importe rien de la couche retenue | ✔ 0 import interdit |
| suite sur le fichier généré par ce code | **373 passés, 0 ignoré** |
| titres servis · MASI 1 · variations hors R10 | 80 · 19 · 0 |

### Annuler

⚠️ **Ne pas utiliser `reset --hard` :** le robot pousse des commits de données
toutes les quelques heures, et un `reset` les effacerait.

```bash
git fetch origin main && git checkout main && git pull
git log --oneline --merges -3          # repérer le commit de fusion
git revert -m 1 <commit-de-fusion>     # annule l'apport, garde les données
git push origin main
```

### Si seule la garde bloquante pose problème

⚠️ **Ne pas la retirer parce qu'un test échoue.** Un contrôle qu'on désactive
au premier rouge ne protège plus rien — c'est la configuration qui a laissé
publier le 09/09 à 23h50. **Établir d'abord la cause** : l'étape « Identifier
le fichier testé » dit si la collecte était dégradée.

Si, la cause établie, le retrait reste la bonne décision :

```bash
git checkout 27228f46 -- .github/workflows/update_bvc.yml
git commit -m "Retour au workflow antérieur — cause établie : <la cause>"
git push origin main
```

Le message de commit doit **nommer la cause**. Un retrait sans cause écrite se
reconduit indéfiniment.

### ⚠️ Ce que le retour arrière NE défait PAS

Le run qui suit la fusion réécrit `data.json` avec le moteur corrigé. **Annuler
le code n'annule pas ce fichier** : il faut attendre le run suivant, où
l'ancien moteur le réécrira. Le délai est d'**un run** — et un run peut être
sauté pendant une journée entière (§9, limite 4). Pour ne pas attendre :
déclencher `update_bvc` à la main, comme à l'aller.

Les chandelles écrites entre-temps ne sont pas réécrites automatiquement. Elles
restent bien formées : ce candidat ne change pas la manière dont une bougie est
calculée.

### Vérifier que le retour a pris

```bash
python3 -c "import json;d=json.load(open('data.json'));\
t={x['symbol']:x for x in d['tickers']};print(t['CMT']['chg'], t['IAM'].get('score_fond'))"
```

`-3.35` et `None` : l'ancien moteur a repris la main.
`0.0` et `7.25` : le moteur corrigé écrit encore.
