# Candidat de fusion limité — construit, mesuré, pas fusionné

> ⚠️ **Rien n'est fusionné ni publié.** Ce document décrit un arbre qui existe
> et se reconstruit à la commande. La décision appartient au propriétaire.

```
python pipeline/candidat_fusion.py --sortie /tmp/candidat
```

| | |
|---|---|
| base | `origin/main` `27228f46` — 11/09/2026 15h57 |
| apport | branche `claude/terminal-bvc-review-AmnBU` `0c4c53ea` |
| fichiers repris | **24** |
| conflit | `pipeline/historical_data.json`, **résolu entrée par entrée** |
| suite sur ce candidat | **373 passés, 0 ignoré, 0 échec** |
| construction | **déterministe** — deux exécutions, 26 fichiers, 0 écart |

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

**Une seule pièce du lot B remonte dans le lot A, et elle est nommée** :
`pipeline/resoudre_historique.py`, parce que la résolution du conflit en
dépend. Rien d'autre.

**Une pièce a été retirée du lot A après mesure** : `pipeline/calendrier_bvc.json`
n'est lu que par `normaliser.py` et deux tests du lot B. Le laisser entrer
aurait brouillé la coupure sans rien apporter.

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

> ### ⚠️ La correction n°4 retire un chiffre de 56 fiches
>
> C'est le changement le plus visible du candidat, et il faut le décider en le
> sachant. Les 56 valeurs retirées portaient **toutes** `pb_fige: true` : elles
> venaient de la table figée de juin, pas d'un dépôt. Les 4 conservées portent
> `pb_source: faits_ammc`.
>
> Le terminal affichera **« — »** en P/BOOK pour 56 titres sur 80. Ce n'est pas
> une perte de données : c'est l'arrêt d'une affirmation sans source. Mais
> l'utilisateur verra un tableau plus vide qu'hier.

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

## 3. Le conflit, résolu sans perte ni recul

```
pipeline/historical_data.json — 74 entrées de part et d'autre, 62 divergent
```

> Consigne de la revue : *« N'arbitrez pas globalement sur la date du
> fichier. »* `_updated` dit quand un fichier a été **écrit**, pas ce qu'il
> contient. Le 28/08/2026, deux sources ont reculé d'une séance et le fichier
> le plus récent portait les cours les plus anciens.

La résolution est donc **une décision par entrée**, produite par
`pipeline/resoudre_historique.py`, qui **ne lit `_updated` nulle part** — un
test le vérifie sur l'arbre syntaxique.

| Cas | Règle | Entrées |
|---|---|--:|
| dernière séance plus récente | l'entrée qui porte la séance la plus récente | **58** |
| séance et contenu identiques | rien à trancher | **12** |
| séance identique, seul un extremum glissant diffère | `h52w`/`l52w`/`h90`/`l90` dépendent de la **date d'ancrage de la fenêtre**, pas de la séance : les deux valeurs sont justes, on retient celle du run le plus récent **en le disant** | **4** |
| désaccord sur un autre champ | **non arbitré** — signalé, conservé tel quel | **0** |

Les quatre du troisième cas : `AFM` (h52w 1367,0 → 1360,0), `SBS` (h90 2199,0 →
2175,0), `SRM` (h52w 555,9 → 555,0), `DAR` (l90 161,2 → 165,25). `last_date` et
`n_candles` identiques des deux côtés.

**Contrôles d'acceptation, mesurés sur le fichier résolu :**

```
titres          : 74   (aucun perdu)
séances en recul : 0
non arbitrés     : 0
```

Le résultat porte sa propre trace : le fichier écrit contient un bloc
`_resolution` avec la règle et le décompte par cas.

⚠️ **Résoudre ce conflit n'assainit rien.** Aucune des deux versions n'a été
produite par le collecteur muni du garde-fou d'identité — ce sont deux sorties
de l'ancien moteur.

---

## 4. Tests exécutés sur ce candidat précis

```
/tmp/candidat2 (base 27228f46 + 24 fichiers + conflit résolu)
```

| Moment | Résultat |
|---|---|
| avant le run du moteur | **1 échec** — `test_un_titre_suspendu_ne_porte_aucun_signal[CMT]` |
| après le run du moteur | **373 passés, 0 ignoré, 0 échec** |

⚠️ **L'échec initial n'est pas un défaut : c'est la démonstration.** Ce test
relit le **fichier publié**, pas le code. Il échoue parce que le `data.json` de
`main` a été écrit par l'ancien moteur, qui laissait CMT à −3,35 %. Le moteur
corrigé écrit 0,00 %, et le test passe.

C'est exactement ce que le garde-fou n°7 institue : **tester le fichier
fraîchement écrit, avant publication**, et non le dépôt.

---

## 5. Prévisualisation du terminal

> ⚠️ **Ce que le bac d'aperçu substitue, et ce qu'il ne prouve donc pas.**
> Le navigateur du conteneur n'atteint pas les CDN (`ERR_CONNECTION_RESET`).
> Les quatre bibliothèques épinglées (React 18, ReactDOM 18, Babel 7.23.10,
> lightweight-charts 4.2.0) ont été téléchargées par le proxy autorisé et
> servies localement, **aux mêmes versions**. L'`index.html` du bac est celui du
> candidat, **aux quatre URL près**.
> Cet aperçu ne dit donc **rien** sur la disponibilité des CDN en production.

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
> l'instant contredirait sa raison d'être. Le correctif tient en une ligne
> (vider le conteneur avant de créer le graphique) et peut faire l'objet d'un
> lot séparé.

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

## 6. Contrôles d'acceptation sur les 80 titres

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

## 7. Limites qui subsistent après cette mise en ligne

1. **Le moteur publié n'est pas protégé contre la contamination d'identité.**
   `update_data.py` et `generate_candles.py` écrivent des chandelles sans
   aucun contrôle d'identité. **Ne pas cocher « moteur publié protégé ».**
2. **Les cinq semaines de cours Mutandis dans `pipeline/candles/MSA.json`
   restent en place.** Le lot B empêche d'en écrire de nouvelles ; il ne
   nettoie pas l'existant, et il est retenu.
3. **Les historiques d'ATL, CFGB et DAR**, nommés par la pièce de juin, sont
   inchangés.
4. **Le cron GitHub reste le premier risque du projet** — journées entières
   sans déclenchement. Rien ici ne le traite.
5. **Le garde-fou bloquant est une arme à deux tranchants** : un test rouge
   suspend une publication légitime. C'est le sens même d'un contrôle
   bloquant, mais il faut le savoir avant, pas le découvrir un matin.
6. **56 fiches perdent leur P/BOOK.** Correction voulue, régression visible.
7. **La mention « Données historiques non disponibles »** s'affiche par-dessus
   les graphiques — préexistant, non corrigé ici.
8. **Aucune performance n'est démontrée**, et rien dans ce candidat n'y touche.

---

## 8. Procédure de retour arrière

### Point de retour

```
origin/main = 27228f46   (11/09/2026 15h57, avant toute fusion)
```

### Si la fusion pose problème

⚠️ **Ne pas utiliser `reset --hard` :** le robot pousse des commits de données
toutes les quelques heures, et un `reset` les effacerait. Il faut **annuler la
fusion sans effacer ce qui a suivi**.

```bash
git fetch origin main
git checkout main && git pull
git log --oneline --merges -3          # repérer le commit de fusion
git revert -m 1 <commit-de-fusion>     # annule l'apport, garde les données
git push origin main
```

### Si seul le garde-fou bloquant pose problème

Il suspend la publication sans rien casser d'autre. Le retirer seul suffit, et
c'est la réponse proportionnée :

```bash
git checkout 27228f46 -- .github/workflows/update_bvc.yml
git commit -m "Retour au workflow antérieur : le contrôle bloquant suspend une publication légitime"
git push origin main
```

### ⚠️ Ce que le retour arrière NE défait PAS

Le premier run du robot après fusion réécrit `data.json` avec le moteur
corrigé. **Annuler le code n'annule pas ce fichier** : il faut attendre le run
suivant, où l'ancien moteur le réécrira à son tour. Le délai est donc d'**un
run**, pas instantané — et un run peut être sauté (limite n°4).

Les chandelles écrites entre-temps ne sont pas réécrites automatiquement.
Elles restent bien formées : le candidat ne change pas la manière dont une
bougie est calculée.

### Vérifier que le retour a pris

```bash
python3 -c "import json;d=json.load(open('data.json'));\
t={x['symbol']:x for x in d['tickers']};print(t['CMT']['chg'], t['IAM'].get('score_fond'))"
```

`-3.35` et `None` : l'ancien moteur a repris la main.
`0.0` et `7.25` : le moteur corrigé écrit encore.
