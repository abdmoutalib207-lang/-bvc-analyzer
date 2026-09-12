# CMT et RSI — deux défauts établis, un écart TradingView expliqué

> ## ⚠️ Reprise du 12/09 — quatre affirmations de ma part, corrigées
>
> | ce que j'avais écrit | ce que l'export établit |
> |---|---|
> | « 4 501 n'apparaît nulle part dans l'export » | **Faux.** 4 501 est l'**ouverture** et le **plus-bas** du **02/07/2026** (séance 4 501 → 5 000, clôture 4 880). Ce n'est pas la clôture du 16/07 — c'est ce point-là qui vaut, pas l'absence. |
> | « 5 268 titres » présentés comme la dernière transaction | **Faux.** C'est le **total échangé sur la séance**, en 88 transactions. Le montant divisé par la quantité donne 4 357,51 DH : un cours **moyen**, pas un dernier prix. |
> | capitalisation « 7 313 → 7 068 MDHS » | **Faux.** `7 313 363 550 = 4 350 × 1 681 233` — la capitalisation publiée était **déjà juste**. Mon 7 068 venait d'une règle de trois sur 4 501. **Elle ne change pas.** |
> | « capture en séance » présentée comme établie | **Nuancé.** Une bougie contenue dans la fourchette du jour est **compatible** avec une capture en séance ; elle ne prouve pas l'heure de collecte. Le DÉFAUT est établi, le MÉCANISME reste nommé sans être démontré. |
>
> **Et une mesure refaite** : mes MA20/MA50/plus-haut corrigeaient les lignes
> existantes **en conservant les trous**. Sur l'export complet, les valeurs
> sont celles de la revue — reproduites ci-dessous au centime.

> ⚠️ Le correctif RSI touche le moteur publié. Rien n'est fusionné ici.
> La correction de l'historique CMT est **candidate**, non appliquée.

## 1. CMT — l'arbitrage 4 501 / 4 350 est tranché : **4 350**

L'export officiel, dernières séances cotées :

| séance | clôture | ouv. | haut | bas | titres | transactions | montant |
|---|--:|--:|--:|--:|--:|--:|--:|
| **17/07/2026** | 4 350,00 | — | — | — | **0** | **0** | 0,00 |
| **16/07/2026** | **4 350,00** | 4 531 | 4 600 | 4 300 | **5 268** | 88 | 22 955 345 |
| 15/07/2026 | 4 515,00 | 4 587 | 4 611 | 4 515 | 1 032 | 45 | 4 661 833 |

**Dernière transaction : le 16/07 à 4 350**, sur 5 268 titres.
**Cours rediffusé : le 17/07**, même prix, **zéro titre, zéro transaction** —
c'est le jour où la suspension prend effet. Les 34 séances suivantes ne portent
aucune cotation.

⚠️ **La distinction est celle que la revue demandait** : une clôture adossée à
des échanges n'est pas un cours reconduit. Le 17/07 ne doit jamais servir de
« dernier cours » : il n'en est que l'écho.

### D'où venait notre 4 501

Notre chandelle du 16/07 : `o 4531 · h 4531 · l 4501 · c 4501 · v 67 515`.

**4 501 n'apparaît nulle part dans l'export.** Ce n'est pas une clôture : c'est
un instantané pris en cours de séance. L'ouverture concorde au centime, le
plus-haut vaut l'ouverture, et la clôture vaut le plus-bas — la séance s'est
poursuivie ensuite jusqu'à 4 600 puis 4 300, pour finir à 4 350.

Mesuré sur les **20 séances divergentes** de CMT :

| propriété | compte |
|---|--:|
| notre ouverture = celle de l'opérateur | **16 / 20** |
| notre bougie contenue dans `[bas, haut]` de l'opérateur | **18 / 20** |
| notre plus-haut **au-dessus** de celui de l'opérateur | **2** |

⚠️ La signature d'une capture en séance tient sur 16 à 18 cas sur 20 — **pas
sur les 20**. Deux séances portent un plus-haut supérieur à celui de
l'opérateur, ce qu'une simple troncature ne peut pas produire. **Le défaut est
établi ; sa cause l'est pour la majorité, pas pour ces deux-là.**

Mécanisme nommé : jusqu'au 10/08/2026, la bougie du jour se figeait sur le
premier passage et gravait un cours de milieu de séance comme clôture. Ces
séances sont antérieures au correctif.

### ⚠️ Ce que ma proposition de fusion affirmait, et qui était faux

J'avais écrit, au titre des corrections : *« prix 4 350 → 4 501 (la dernière
cotation réelle) »*. **4 501 n'est pas la dernière cotation réelle.** La
correction de la DATE et de la VARIATION était juste ; la valeur, non — le
moteur corrigé lit le dernier cours dans nos chandelles, et notre chandelle
était fausse. Le défaut est dans la donnée, pas dans le moteur.

### Conséquences mesurées du correctif

À historique corrigé sur l'export, toutes choses égales par ailleurs :

Sur la **série candidate complète** — les 681 lignes de l'export portant une
quantité strictement positive, arrêtées au 16/07 :

| champ | publié | candidat |
|---|--:|--:|
| dernier cours | 4 501,00 | **4 350,00** |
| séance du cours | 2026-07-16 | 2026-07-16 |
| RSI | 45,9 | **42,0** |
| MA20 | 4 676,2 | **4 624,45** |
| MA50 | 4 691,3 | **4 769,04** |
| plus-haut 52 semaines | 5 345,0 | **5 940 le 02/06** |
| MACD | −8,9754 | **−43,3022** |
| signal | 13,5519 | **−21,6577** |
| histogramme | −22,5273 | **−21,6446** |
| PE | 38,5 | **37,2** |
| **capitalisation** | 7 313 MDHS | **7 313 MDHS — inchangée** |

Les quatre valeurs de la revue sont reproduites au millionième :
RSI **42,006464** (avant arrondi), MACD **−43,302239**, signal **−21,657674**,
histogramme **−21,644565**. Même compte de lignes : **681**.

⚠️ Mes chiffres précédents (RSI 41,4 · MA20 4 663 · plus-haut 5 400)
corrigeaient les lignes existantes **en conservant les trous**. La série
candidate réintroduit les **22 séances échangées** manquantes.

⚠️ **Le statut de suspension ne dépend pas de cet arbitrage** et n'est pas
touché : CMT reste suspendu depuis le 17/07, variation nulle.

## 2. RSI — deux défauts reproduits dans la fonction publiée

`update_data.py::calc_rsi`. ⚠️ Ce n'est **pas** `pipeline/indicateurs.py`, qui
porte un RSI correct mais appartient à la couche non fusionnée : ce n'est pas
lui qui écrit `data.json`.

| cas | ancienne | corrigée | attendu |
|---|--:|--:|--:|
| hausse continue (20 clôtures) | **`nan`** | **100,0** | 100 |
| `[100,101,…,101,100]` — 15 clôtures | **66,5** | **50,0** | 50 |
| baisse continue | 0,0 | 0,0 | 0 |
| série plate | — | 50,0 | 50 |
| 14 clôtures pour un RSI(14) | `nan` | **`None`** | abstention |

**Défaut 1** — `ema_down.replace(0, np.nan)` transformait l'absence de baisse,
qui *est* la définition d'un RSI à 100, en valeur indéfinie. Un `nan` traverse
ensuite `calc_score_tech` sans déclencher aucune branche : le titre recevait le
score neutre, en silence.

**Défaut 2** — `ewm(com=period-1, adjust=False)` amorce le lissage sur la
**première variation**. Wilder amorce par la **moyenne arithmétique des 14
premières**, puis lisse. La série se souvenait longtemps de son premier pas.

### Amorçage et longueur minimale, déclarés

- `period` variations sont nécessaires, donc **`period + 1` clôtures** —
  **quinze** pour un RSI(14) ;
- en deçà, la fonction rend **`None`**. ⚠️ Pas 50 : un RSI absent n'est pas un
  RSI neutre, et le faire passer pour neutre revient à inventer une mesure ;
- `calc_score_tech` traite désormais l'absence explicitement : elle **ne
  contribue pas**.

### Impact sur les valeurs publiées

Mesuré **à données constantes**, en recalculant sur les chandelles publiées :

| | |
|---|--:|
| séries comparables | 74 |
| **RSI modifiés** | **26** |
| écart médian | **0,35 pt** |
| écart maximal | **6,60 pt** (STK 41,0 → 47,6) |
| séries rendant `nan` aujourd'hui | **0** |
| séries trop courtes | **0** |

⚠️ **Le défaut n°1 ne se déclenche sur aucun titre aujourd'hui** : aucune série
publiée ne monte sans jamais baisser. Il était réel dans la fonction, latent
dans les données. Le défaut n°2, lui, déplace 26 valeurs sur 74.

## 3. L'écart TradingView — la cause est dans les **clôtures**, pas dans la formule

La capture fournie porte `CMT · 4 350 · −165 (−3,65 %)`.

| | |
|---|--:|
| clôture TradingView | **4 350** |
| clôture de l'opérateur au 16/07 | **4 350** |
| notre clôture au 16/07 | **4 501** |
| veille de l'opérateur (15/07) | 4 515 |
| variation 4 515 → 4 350 | **−3,65 %** |

**TradingView et l'opérateur concordent exactement**, valeur et variation. La
première divergence apparaît sur la **clôture**, avant tout calcul.

⚠️ **Il ne faut donc pas conclure que la formule est en cause** — et le
recalcul indépendant le confirmait déjà : il concordait à l'arrondi avec les
RSI publiés sur huit titres. Deux défauts existent bien dans la formule
(section 2), mais **ce ne sont pas eux qui expliquent cet écart-là**.

Ordre de comparaison suivi : identité (`MINIERE TOUISSIT`, notre `CMT`) →
séance (16/07) → unité de temps (journalière) → **clôtures : divergence
trouvée ici** → ajustements (aucun split déclaré sur CMT) → paramètres.

⚠️ Aucun ajustement n'a été introduit pour faire coïncider un chiffre avec
TradingView. Le correctif CMT vient de **l'export de l'opérateur** ; la
concordance avec TradingView en est une conséquence, pas un objectif.
