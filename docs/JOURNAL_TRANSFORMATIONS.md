# Journal des transformations — lot 1B.1

> Ce qui a été appliqué aux données, ce qui ne l'a PAS été, et pourquoi.
> Une transformation absente de ce journal n'a pas le droit d'exister dans le
> code.

## Les deux couches, et ce qui les sépare

| | `datasets/lot1a/` | `datasets/lot1b/` |
|---|---|---|
| Nature | **instantané** | **couche dérivée** |
| Contenu | copie octet pour octet de `pipeline/candles/` | mêmes valeurs + qualification |
| Valeurs de prix et de volume | intactes | **intactes** |
| Ce qui s'y ajoute | rien | statuts, niveau de preuve, usages admissibles, **motif de chaque refus** |
| Régénérable | non — il est figé | oui, par `pipeline/normaliser.py` |

**⚠️ Réserve de vocabulaire.** Ni l'une ni l'autre ne contient de **données
brutes fournisseur**. Le dépôt ne conserve **aucune charge utile de source**.
L'expression est réservée aux charges utiles effectivement conservées ; nous
n'en gardons aucune. C'est une lacune, pas une convention.

## Les quatre usages, et pourquoi ils sont séparés

| Usage | Ce qu'il autorise |
|---|---|
| `prix_analyse` | valoriser, comparer, mesurer une variation |
| `volume` | mesurer une quantité échangée |
| `indicateur` | alimenter un calcul de série |
| `execution` | **supposer qu'un ordre aurait pu être passé à ce prix** |

**`execution` est refusé par défaut**, et ce n'est pas une prudence de façade.
Une série ajustée porte des prix qui n'ont jamais été cotés : un titre divisé
par dix affiche 130 là où le marché traitait 1 300. Croiser ce prix avec une
quantité **non ajustée** fabrique un montant faux d'un facteur dix. L'exécution
exige donc un ajustement **documenté** — pas seulement probable.

Le corollaire vaut pour les quantités : avant une opération déclarée et sans
ajustement documenté, **le volume lui-même est refusé**. Une opération ne
change pas que les prix, elle change le nombre de titres.

## Transformations APPLIQUÉES

### T1 — Qualification des observations

Chaque ligne reçoit : l'état de ses quatre prix, la cohérence de son invariant
OHLC, l'état de son volume, le statut de sa séance, le niveau de preuve de sa
base de prix, le statut réglementaire de son amplitude, les usages accordés et
**le motif de chaque refus**.

**Effet sur les valeurs : aucun.** Vérifié observation par observation contre
l'instantané.

### T2 — Contrôle d'amplitude, indexé par régime

Voir `pipeline/regimes_variation.py`. Trois issues, et non deux :

| Statut | Quand | Effet |
|---|---|---|
| `conforme` | en deçà du régime le **plus strict** | rien à signaler |
| `contrôle réglementaire non concluant` | licite sous un régime, pas sous un autre | **ne refuse rien** |
| `amplitude suspecte` | au-delà du régime le **plus permissif** | écarte l'observation |

Nous ignorons, titre par titre et jour par jour, quel régime s'applique — ni le
mode de cotation, ni les dates d'admission. Le registre `REGIME_PAR_TITRE` est
donc **vide à dessein** : une entrée inventée rendrait le contrôle concluant à
tort.

Le contrôle reste néanmoins concluant dans un cas : quand l'amplitude dépasse
**tous** les régimes connus, aucune hypothèse de régime ne la rend licite — la
conclusion ne dépend plus de ce qu'on ignore.

Répartition sur les 4 306 bougies : **4 292 conformes, 13 non concluantes,
1 suspecte**.

> ⚠️ **« Suspecte » qualifie l'amplitude, jamais sa cause.** Un contrôle de
> forme ne diagnostique pas une opération sur titres. Un test vérifie que le
> résultat ne contient aucun des mots « base », « split », « opération »,
> « ajust ».

**Source des seuils** : circulaire AMMC du 25/06/2026 (±10 % en continu, ±6 %
au fixing, ±20 % pendant les cinq premières séances suivant l'admission, en
vigueur depuis le 23/06/2026), **relayée par la revue externe et NON vérifiée
par nous sur le texte original**. Le champ `verifie_sur_source_primaire` vaut
`False` et doit le rester tant que la pièce n'est pas jointe.

## Transformations NON APPLIQUÉES — et la raison

### N1 — Ajustement des opérations sur titres

**État : NON APPLIQUÉ.** Aucun prix n'a été divisé, multiplié ni recalé.

Les diagnostics portent désormais un **niveau de preuve**, et séparent trois
choses qui étaient confondues : le **fait observé**, l'**hypothèse** qu'on en
tire, et la **pièce qui manque**.

| Titre | Niveau | Fait observé | Hypothèse | Ce qui manque |
|---|---|---|---|---|
| **MNG** | ajustement probable, à confirmer | rapport des clôtures 24/07 → 27/07 = 1,091, sans discontinuité | la division par 10 a été appliquée une fois | le journal des écritures. La continuité montre qu'une division a eu lieu ; elle ne prouve pas qu'elle n'a eu lieu qu'**une** fois |
| **SOT** | base incohérente ou suspecte | rapport 04/05 → 05/05 = 5,000 ; ouverture du 05/05 incompatible avec sa clôture ; niveau médian antérieur 5× trop bas | double division par 5 | une source primaire pré-split. Ni l'hypothèse ni sa **portée exacte** ne sont établies observation par observation |
| 5 autres | état inconnu | aucun diagnostic conduit | — | un diagnostic |

> ⚠️ **« Aucune opération au registre » ne prouve rien.** Le registre `SPLITS`
> recense ce que nous y avons inscrit, pas ce qui s'est produit. Il n'établit
> ni l'absence d'opération sur tout l'historique, ni la validité des bases. Le
> défaut est donc « état inconnu », pour tout le monde.

**Conséquence mesurée, et elle est lourde** : « état inconnu » interdit
l'usage `indicateur`, parce que rien ne garantit que deux points consécutifs
s'expriment sur la même base. **Cinq titres sur sept n'autorisent aujourd'hui
aucun indicateur.**

Ce n'est pas un effet de bord : c'est l'état réel de notre connaissance, rendu
visible. Le lot 2 ne peut pas se brancher sur ces séries avant que les
diagnostics soient conduits.

### N2 — Comblement des trous de calendrier

**État : NON APPLIQUÉ.**

L'entrée du **14 août 2026** était marquée « fermé », justifiée par « 71
clôtures sur 71 identiques à la veille, recoupé au bulletin CDG ». C'est
exactement le raisonnement que la revue avait écarté, **réintroduit sous forme
de source**. Elle est déclassée en `non_confirme`.

Les deux éléments dont nous disposons sont conservés comme **indices**, chacun
marqué `vaut_preuve: false` :

1. l'observation des 71 clôtures — compatible avec une fermeture, une
   rediffusion par la source, ou une panne de collecte ; n'établit aucune des
   trois ;
2. l'entrée `(8, 14)` de `JOURS_FERIES_FIXES` — registre du projet, sans
   citation, et un férié national n'établit pas par lui-même la fermeture de la
   Bourse.

**Pièce qui trancherait** : le calendrier officiel des séances de la Bourse de
Casablanca, ou un bulletin CDG couvrant le 13 au 17/08/2026.

Le fichier ne contient donc **aucune date « fermée » établie** et une seule
date « ouverte ».

### N3 — Modification de la formule de score

**NON APPLIQUÉ**, hors périmètre. R8, et instruction de revue explicite.

## Défauts corrigés dans cette passe

| Défaut | Relevé par | État avant |
|---|---|---|
| Ouverture et clôture absentes ⇒ tous les usages, exécution comprise | revue | un volume positif suffisait |
| Base « inconnu » ⇒ exécution autorisée | revue | — |
| Volume `+∞` classé « mesuré » | revue | le test portait sur NaN et le signe ; l'infini passe les deux |
| Amplitude : seuil 1,222 tenu pour universel | revue | une bougie `h=120, l=80`, licite sous ±20 %, était déclarée impossible |
| Calendrier : le 14 août déclaré fermé sur des cours immobiles | revue | raisonnement écarté, revenu comme source |
| Diagnostics énoncés comme des faits | revue | « ajusté une fois », « double division » sans niveau de preuve |
| **Invariant OHLC rompu ⇒ tous les usages** | trouvé en vérifiant les siens | `l=99 > h=5` passait intégralement |
| **Couverture calculée sur les lignes reçues** | trouvé en vérifiant les siens | une fenêtre de 60 avec **une** observation ressortait à 100 % |
| **Bougie pile à la limite déclarée suspecte** | trouvé en corrigeant l'amplitude | `1.2/0.8 = 1.4999999999999998` en flottant, contre `120/80 = 1.5` |
| **« Non concluant » refusait l'indicateur** | trouvé en relisant ma propre correction | convertissait notre ignorance en verdict |

Sur la couverture : la correction **n'a déplacé aucun chiffre publié** — les
73 médianes de l'inventaire restent calculables et identiques, la série la plus
courte comptant 50 lignes pour une fenêtre de 60. Elle aurait faussé la
première fenêtre réellement creuse.

## Ce que le lot ne démontre pas

- **Aucune performance.** Aucun rendement n'est mesuré ici.
- Pas que les prix sont **exacts** : il déclare sur quelle base ils s'expriment,
  et avec quel niveau de preuve.
- Pas que SOT soit exploitable ni MNG sain — il rend l'état des deux **lisible**.
- **Aucune observation du lot n'autorise l'exécution.** Constat, pas objectif :
  aucune série ne porte d'ajustement documenté.
