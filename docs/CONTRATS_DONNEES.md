# Contrats de données

Ce que chaque champ SIGNIFIE, dans quelle unité, à quelle date, et ce qu'il ne
dit pas. Écrit parce que plusieurs défauts graves venaient d'un champ dont le
sens variait selon l'endroit où on le lisait.

## La règle qui gouverne tout le reste

**Zéro mesuré, valeur inconnue et sans objet sont trois états distincts.**

Les confondre a produit deux défauts en deux jours :

- `BPA_DATA[t].get("div_dh")` testait une VALEUR : un dividende de zéro,
  vérifié au rapport annuel, retombait sur une constante. Sept sociétés.
- `f.get("dette_nette_ebitda") or 1.0` traitait un zéro comme absent — et ce
  zéro était en réalité un remplissage pour six banques et un assureur, à qui
  le ratio ne s'applique pas.

On teste donc la PRÉSENCE (`is not None`), jamais la valeur. Et lorsqu'une
grandeur n'a pas de sens pour un secteur, elle est **sans objet**, ce qui n'est
ni zéro ni inconnu.

## Les trois dates à ne jamais confondre

| Date | Ce qu'elle dit |
|---|---|
| date de marché | la séance à laquelle la transaction a eu lieu |
| date de récupération | quand nous avons interrogé le fournisseur |
| date d'analyse | quand la décision est réputée rendue |

`_meta.prix_asof` porte la **date de marché**. `updated` porte la date de
génération. `date_analyse` porte la date de décision, surchargeable par
`BVC_DATE_ANALYSE`.

⚠️ **Le défaut circulaire.** La suspension se jugeait à `prix_asof`. Sur un
titre suspendu, cette date précède toujours la suspension — puisque c'est elle
qui l'a arrêté. La question ne pouvait recevoir qu'une réponse : « non
suspendu ». La suspension se juge désormais à la date d'ANALYSE.

## Champs de cotation

| Champ | Unité | Sens | Ce qu'il ne dit pas |
|---|---|---|---|
| `price` | DH | dernier cours retenu | pas forcément une transaction du jour |
| `chg` | % | variation depuis la clôture précédente | vaut 0 pour un titre suspendu, par vérité et non par défaut |
| `vol` | **nombre de titres** | quantité échangée | ⚠️ CDG distingue `QteEchangee` (titres) de `Volumes` (dirhams) ; le moteur lit le premier |
| `cap` | MDH | capitalisation | |
| `open`/`close` | DH | | |

⚠️ **DAT-10, ouvert.** La bougie CMT du 16/07 porte `v=67515`. Le programme qui
l'a écrite n'est pas enregistré : l'unité y est PRÉSUMÉE, non certifiée.

## Statut de cotation

`_meta.suspendu` est un **fait juridique**, pas une déduction. Il vient du
registre `SUSPENSIONS` de `bvc_config.py`, sourcé sur l'avis du régulateur.

Une suspension **ne se déduit pas des cours** : un titre suspendu et un titre
délaissé produisent exactement les mêmes nombres — volume nul, variation nulle,
cours immobile. C'est le même raisonnement que `SPLITS`.

Pour un titre suspendu, `price` est ramené à la dernière bougie PORTANT UN
VOLUME, et `prix_asof` à sa date. Le cours que la source continue de diffuser
est conservé à part dans `_meta.prix_diffuse_source`, pour que l'écart reste
vérifiable plutôt qu'arbitré en silence.

## Provenance du prix

`_meta.source_prix` ∈ { `cdg`, `bmce`, `idbourse`, `medias24`, `candles`,
`idbourse_perime`, `historical`, `data_json_precedent`, `financial`, `static`,
`derniere_cotation_avant_suspension` }.

La dernière n'est **pas un repli de la chaîne R3** : c'est un choix délibéré,
décrit ci-dessus.

## Fondamentaux

`_meta.pb_source` ∈ { `faits_ammc`, `non_disponible` }.

Un price-to-book publié DOIT venir d'un dépôt AMMC — capitaux propres part du
groupe et nombre d'actions, chacun avec sa page. Ailleurs le champ est **vide**.

⚠️ Une constante étiquetée reste une constante. Sur Alliances, la table figée
annonçait 0,80 quand les comptes 2025 donnent 2,30 : le SENS de l'information
s'inversait. Publier un nombre faux avec un avertissement est pire que ne rien
publier — le lecteur retient le nombre.

`bpa.json` porte, pour chaque dividende corrigé : `div_exercice`, `div_ago`,
`div_detachement`, `div_paiement`, `div_statut`, `div_statut_source`.

⚠️ **Une date de paiement passée ne prouve pas un versement.** Le statut dit
« approuvé en assemblée ; paiement annoncé au JJ/MM/AAAA, versement non
vérifié » tant qu'aucun avis de paiement n'a été relevé.

## Confiance

`_meta.confidence` ∈ [0, 5] mesure des **conditions de disponibilité**. Ce
n'est pas une probabilité de hausse, et ce n'est pas une probabilité du tout.
