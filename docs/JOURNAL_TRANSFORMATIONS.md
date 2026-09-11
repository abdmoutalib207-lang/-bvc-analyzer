# Journal des transformations — lot 1B

> Ce qui a été appliqué aux données, ce qui ne l'a PAS été, et pourquoi.
> Tenu à jour à chaque passe. Une transformation absente de ce journal n'a pas
> le droit d'exister dans le code.

## Les deux couches, et ce qui les sépare

| | `datasets/lot1a/` | `datasets/lot1b/` |
|---|---|---|
| Nature | **instantané** | **couche dérivée** |
| Contenu | copie octet pour octet de `pipeline/candles/` | mêmes valeurs + qualification |
| Valeurs de prix | intactes | **intactes** |
| Valeurs de volume | intactes | **intactes** |
| Ce qui s'y ajoute | rien | statut de séance, état du volume, base de prix, admissibilité |
| Peut être régénéré | non — il est figé | oui, par `pipeline/normaliser.py` |

**L'instantané ne bouge pas.** Sa raison d'être est de pouvoir prouver, plus
tard, sur quoi une mesure portait. Les empreintes SHA-256 des sept séries sont
inscrites dans son manifeste et recopiées dans chaque fichier normalisé.

## ⚠️ Réserve de vocabulaire

Ni l'une ni l'autre couche ne contient de **données brutes fournisseur**. Le
dépôt ne conserve **aucune charge utile de source** — pas de réponse HTTP, pas
de PDF, pas d'export. Les séries ont été écrites par le moteur, à des dates et
par des versions de code que la donnée n'enregistre pas.

L'expression « données brutes fournisseur » est réservée aux charges utiles
effectivement conservées. Nous n'en gardons aucune à ce jour — c'est une
lacune, pas une convention.

## Transformations APPLIQUÉES

### T1 — Qualification des observations

**Quoi** : chaque ligne reçoit un statut de séance, un état de volume, une base
de prix déclarée et la liste des usages pour lesquels elle est admissible.

**Effet sur les valeurs** : **aucun**. Les champs `o`, `h`, `l`, `c`, `v` sont
recopiés tels quels. Le test `test_normalisation.py::test_aucune_valeur_modifiee`
le vérifie observation par observation contre l'instantané.

**Ce que ça remplace** : la convention `(b.get("v") or 0)`, qui transformait un
volume inconnu en zéro mesuré. Trois états distincts — mesuré, inconnu,
invalide — ne se replient plus sur une même écriture.

### T2 — Contrôle d'amplitude réglementaire

**Quoi** : une bougie dont le rapport plus-haut / plus-bas dépasse
`1,10 / 0,90 ≈ 1,222` est signalée et retirée de tout usage.

**Pourquoi ce seuil, et pas un autre** : R10 plafonne la séance à ±10 % du
cours de référence. Le plus-haut ne peut donc excéder `1,10 × référence`, ni le
plus-bas descendre sous `0,90 × référence`. Le rapport est borné par
construction. Le seuil n'est pas choisi, il se déduit de la règle.

**Mesure** : sur les **4 306 bougies** des sept séries figées, **une seule**
dépasse — SOT au 05/05/2026, rapport 4,607. Le contrôle ne disqualifie donc
rien d'autre au passage.

> ⚠️ **Le premier détecteur écrit pour ce contrôle était faux.** Il cherchait
> `plus-haut / plus-bas == ratio de l'opération` à 1 % près, et ne trouvait
> rien : le cours bouge en séance, donc le rapport ne retombe jamais sur le
> ratio. La bougie SOT vaut 4,607 et non 5,000. La formulation qui
> l'accompagnait — « le signal est que le rapport égale le ratio » — était une
> fausse précision. Corrigé, et consigné ici parce que l'erreur est instructive :
> un détecteur qui ne trouve rien peut se lire comme une absence d'anomalie.

## Transformations NON APPLIQUÉES — et la raison

### N1 — Ajustement des opérations sur titres

**État : NON APPLIQUÉ.** Aucun prix n'a été divisé, multiplié ni recalé.

| Titre | État diagnostiqué | Pourquoi rien n'est corrigé |
|---|---|---|
| **MNG** | ajusté une fois | La série est **déjà correcte**. Les clôtures 24/07 → 27/07 donnent un rapport de 1,091, continu à travers le split : la division par 10 a bien eu lieu. Réappliquer `adjust_splits()` produirait une double division. **Il n'y a rien à corriger — le risque est d'agir.** |
| **SOT** | double ajustement | La série antérieure au 05/05/2026 est **5× trop basse** (1 700 ÷ 25 = 68 au lieu de 1 700 ÷ 5 = 340). La correction serait arithmétiquement triviale — multiplier par 5 — mais elle **fabriquerait 486 prix qu'aucune source ne confirme**. Aucune source primaire pré-split n'est en notre possession. |
| 5 autres | non diagnostiqué | Aucune opération déclarée au registre `SPLITS`. « Sans opération déclarée » n'est pas « vérifié sans opération » : c'est l'absence d'entrée au registre. |

**Instruction de revue reçue** : *« N'applique aucune nouvelle correction
automatique avant ce diagnostic. Garde les fichiers figés intacts. »* Le
diagnostic est fait ; la correction reste suspendue à une décision qui n'est
pas la mienne.

**Conséquence assumée** : 487 observations de SOT sur 542 sortent avec une
liste d'usages **vide**. Le titre n'est pas exploitable en l'état sur son
historique long, et la couche normalisée le dit au lieu de le masquer.

### N2 — Comblement des trous de calendrier

**État : NON APPLIQUÉ.** Les 28 à 43 dates manquantes par série restent
manquantes.

Combler suppose de savoir si le marché était ouvert ce jour-là. Le calendrier
`pipeline/calendrier_bvc.json` ne contient que **deux dates établies** ; tout
le reste y est marqué `non_confirme`. Une date non confirmée produit un statut
`inconnue`, jamais « sans transaction ».

⚠️ La règle « des clôtures identiques sur tout le marché signalent une
fermeture » a été **écartée en revue** : une ressemblance de cours peut
déclencher une alerte, elle ne décide pas qu'un jour est férié. Elle reste
utilisable comme signal, pas comme preuve.

### N3 — Modification de la formule de score

**État : NON APPLIQUÉ**, et hors périmètre. R8 ; et l'instruction de revue est
explicite : *« Ne modifie pas encore la formule officielle et ne lance pas
d'optimisation de stratégie. »*

## Empreintes

Chaque fichier de `datasets/lot1b/` porte `empreinte_source`, le SHA-256 du
fichier de `datasets/lot1a/` dont il dérive. Un instantané modifié après coup
rendrait les empreintes discordantes et le test le verrait.

| Titre | Empreinte de l'instantané (12 premiers) | Lignes |
|---|---|---|
| ADH | `adfa99891b3c` | 797 |
| ADI | `6108a668b6dc` | 797 |
| CSR | `fe8fc84cedd9` | 794 |
| MNG | `4528629309e5` | 797 |
| CMT | `6514c01e3b38` | 514 |
| TQA | `b8104556ece6` | 65 |
| SOT | `34a984012087` | 542 |

Les empreintes complètes sont dans les deux manifestes.

## Ce que le lot 1B ne démontre pas

- Il ne démontre **aucune performance**. Aucun rendement n'est mesuré ici.
- Il ne démontre pas que les prix sont **exacts** : il déclare sur quelle base
  ils sont exprimés, ce qui est une question différente.
- Il ne rend SOT exploitable ni MNG définitivement sain — il rend l'état des
  deux **lisible**.
