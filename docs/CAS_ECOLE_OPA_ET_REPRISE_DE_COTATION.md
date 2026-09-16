# Cas d'école — une OPA obligatoire remet le cours à zéro

> **Ce document ne décrit pas un incident : il décrit une MÉCANIQUE DE MARCHÉ
> parfaitement légale, prévue par la loi 26-03, qui se reproduira.**
>
> Écrit le 16/09/2026 à partir des deux avis de l'AMMC, archivés dans
> `datasets/pieces_ammc/`. Aucune affirmation de ce document ne repose sur un
> commentaire de presse ou sur une reconstitution : chaque chiffre est dans les
> pièces, à la page indiquée.

---

## 1. Les faits, et d'où ils viennent

| Pièce | Date | Empreinte sha256 (début) |
|---|---|---|
| `AMMC_avis_depot_OPA_CMT_2026-07-17.pdf` — avis de dépôt `DO/EM/07/2026` | 17/07/2026 | `568798921755ad80` |
| `AMMC_recevabilite_OPA_CMT_2026-09-15.pdf` — décision `DO/EM/010/2026` | 15/09/2026 | `8240a798df3c4ef0` |
| `pipeline/bulletins/CDG_indices_2026-09-16.pdf` — la séance de reprise | 16/09/2026 | `55f7c0790efc6243` |

**Le déclencheur n'est pas une décision d'acheter.** Le 13/07/2026, le pacte
d'actionnaires entre AYRAD GROUP LIMITED (37,04 %) et la CIMR (16,54 %) entre en
vigueur. Le seuil de 40 % des droits de vote est franchi, et l'article 18 de la
loi 26-03 **rend le dépôt d'une OPA obligatoire**. L'acheteur ne choisit pas de
lancer l'offre : elle lui est imposée par un calcul.

Le projet est déposé le 16/07. Le lendemain, l'AMMC demande à la Bourse de
Casablanca de **suspendre la cotation** (article 30). Le titre cesse de coter
sur une dernière séance à 4 501 DH.

La décision de recevabilité tombe le 15/09 et fixe le prix de l'offre. Elle
contient la phrase qui a tout changé pour nous :

> « L'AMMC demandera à la Bourse de Casablanca de reprendre la cotation de la
> valeur de CMT le 16 Septembre 2026. »

## 2. Le prix n'est pas une prime, c'est une moyenne

C'est ici que la théorie financière et la formule réglementaire divergent, et
c'est ce qui rend le cas contre-intuitif.

Dans une **OPA volontaire**, l'acheteur veut séduire le marché pour prendre le
contrôle : il offre une prime au-dessus du dernier cours. C'est le « parachute »
qu'un porteur attend spontanément.

Dans une **OPA obligatoire**, l'esprit de la loi est de donner un droit de
retrait aux minoritaires, pas de les enrichir. Le prix est encadré strictement
pour éviter les manipulations, par une analyse multicritère que l'AMMC examine.
Pour CMT (décision du 15/09, section 4) :

| Méthode | Prix par action | Pondération |
|---|---:|---:|
| Cours moyen pondéré par les volumes, 12 mois avant le 26/03/2026 | 2 523 MAD | 50 % |
| Transaction de référence — rachat par AYRAD des 37,04 % détenus via OSEAD | 1 910 MAD | 50 % |
| **Moyenne des méthodes** | **2 217 MAD** | **100 %** |

`(2 523 + 1 910) ÷ 2 = 2 216,5`, arrondi à **2 217 MAD**.

**Le cours de bourse ne pèse que la moitié, et sur douze mois glissants.**
L'autre moitié est le prix d'une transaction privée internationale, conclue
hors marché et bien plus bas. Un porteur entré à 4 500 DH ne reçoit donc aucune
protection à son prix de revient : il reçoit une moyenne pondérée dont il n'est
pas partie prenante.

⚠️ **Ce n'est ni une anomalie ni une erreur de marché. C'est la formule.**

## 3. Ce que la reprise fait au cours — et à nous

Le 16/09, le titre rouvre. Le bulletin de l'opérateur cote :

```
CMT   2 438,00   +9,97 %   1 titre échangé   15:30:00
```

`2 438 ÷ 1,0997 = 2 216,97`. **La référence de la séance de reprise est le prix
de l'OPA, 2 217 DH** — pas la dernière clôture de 4 501, ni le 4 350 diffusé
pendant la suspension.

Deux chemins indépendants donnent le même nombre :

- la décision AMMC : `(2 523 + 1 910) ÷ 2 = 2 217`
- le bulletin de séance : `2 438 ÷ 1,0997 = 2 216,97`

L'un vient du régulateur, l'autre du marché. Ils ne se recopient pas.

### Ce que cela signifie pour le terminal

**La continuité du cours est rompue, et la série historique est pourtant
juste.** Entre le 16/07 à 4 501 et le 16/09 à 2 438, il n'y a pas eu de chute
de 46 % : il y a eu une suspension de deux mois et une nouvelle référence.

⚠️ **CE N'EST PAS UN SPLIT, ET IL NE FAUT SURTOUT PAS AJUSTER L'HISTORIQUE.**
Un split multiplie le nombre de titres et divise le cours : la valeur de la
position ne bouge pas, et rétro-ajuster la série est alors *obligatoire* pour
que les moyennes gardent un sens. Ici, rien de tel. Le nombre d'actions est
inchangé — 1 681 233, confirmé par la décision AMMC comme par notre
référentiel. Les porteurs ont réellement perdu de la valeur. Les cours d'avant
sont ce qu'ils étaient, et les réécrire effacerait ce fait.

**Le test qui distingue les deux cas est le nombre d'actions**, pas l'ampleur
du décrochage :

| | Split | Reprise après OPA |
|---|---|---|
| Nombre d'actions | multiplié | **inchangé** |
| Valeur de la position | inchangée | **réellement modifiée** |
| Série historique | à rétro-ajuster | **à ne pas toucher** |
| Registre concerné | `SPLITS` | `SUSPENSIONS[...]["reprise"]` |

## 4. Les trois pièges que ce cas a tendus au moteur

Chacun est un raisonnement juste qui devient faux dans ce contexte précis. Ce
sont eux qui font de ce cas un cas d'école.

**1. Un contrôle qui s'appuie sur une valeur périmée.** Notre contrôle de
capitalisation comparait les 3 727 MDHS servis par la source à
`prix × actions`. Le prix, lui, était figé à 4 350 depuis deux mois. Le contrôle
a donc « corrigé » 3 727 en 7 313 — alors que
`3 727 000 000 ÷ 1 681 233 = 2 216,83`, c'est-à-dire exactement le prix de
l'OPA. **La source avait raison et le contrôle avait tort.**

> Un contrôle qui s'appuie sur une valeur périmée est pire que pas de contrôle :
> il remplace du juste par du faux, et il le fait avec autorité.

**2. Des indicateurs techniques qui survivent à leur objet.** MA20 à 4 624 et
MA50 à 4 769 décrivent un régime de prix qui n'existe plus. Un cours de 2 438
lu sous ces moyennes signifie « survendu », donc « acheter ». Le moteur a
publié **ACHETER ★★ avec 5/5 de confiance**, sur un titre qui venait de changer
de référence et dont **un seul titre** avait été échangé.

**3. Le plafond des ±10 % appliqué à ce qui n'est pas une variation.** R10 dit
qu'aucun cours de société ne bouge de plus de 10 % en une séance, donc qu'un
écart supérieur est une erreur de source. Comparé au 4 350 diffusé, le cours de
reprise donnait −43,95 % ; le plafond a donc ramené la variation à **0,00 %**,
un jour où le titre a fait **+9,97 %**. R9 interdit précisément ce zéro-là.

> R10 parle de **variations de cours**. Elle ne dit rien d'une **référence
> remise à neuf**. Invoquer une règle pour un cas qu'elle ne couvre pas est la
> même faute que celle relevée le 05/09 sur le MASI.

## 5. Ce qu'il faut faire la prochaine fois

Une suspension pour OPA dure des semaines, et la reprise se prépare : la date
figure **dans la décision de recevabilité, publiée la veille**. Il y a donc un
délai pour agir, à condition de lire la pièce.

1. **À la suspension** — inscrire la période dans `SUSPENSIONS` avec l'avis de
   dépôt AMMC en pièce. Geler la série via `datasets/series_acceptees/` pour
   qu'aucun import ne la réécrive.
2. **Pendant** — surveiller la publication de la décision de recevabilité sur
   `ammc.ma`. Elle porte le prix de l'offre **et la date de reprise**.
3. **À la reprise** — inscrire `reprise`, `cours_de_reprise` et la référence
   retenue, chacun adossé à sa pièce. Ne PAS ajuster la série.
4. **Après** — considérer les indicateurs techniques comme non calculables tant
   que la nouvelle série est trop courte, et le dire à l'écran plutôt que de
   publier un signal.
5. **Toujours** — vérifier que le prix qui sert d'arbitre à un contrôle vient
   d'une cotation vivante. Un contrôle nourri d'un cours gelé n'arbitre rien.

## 6. Portée, et ce que ce document ne dit pas

- **Ce cas n'est pas propre à CMT.** Tout franchissement du seuil de 40 % des
  droits de vote déclenche le même enchaînement. La BVC compte plusieurs
  sociétés à actionnariat concentré.
- **Aucune conclusion d'investissement n'est tirée ici**, et aucune n'a à
  l'être. Ce document décrit une mécanique réglementaire et ses conséquences
  sur le calcul d'un terminal. Il ne dit ni d'apporter ses titres à l'offre, ni
  de les conserver.
- **Les initiateurs ont déclaré vouloir maintenir CMT à la cote** (décision du
  15/09, section 3), et n'ont pas l'intention de poursuivre leurs achats après
  la clôture de l'offre. C'est un fait cité, pas une prévision.
- **Le calendrier de l'offre n'était pas fixé** à la date de la décision : « le
  calendrier définitif de l'opération sera fixé ultérieurement ». Nous n'avons
  donc pas la date de clôture de l'OPA, et il ne faut pas la supposer.

---

## Annexe — répartition du capital à la veille du dépôt

Telle que publiée dans la décision de recevabilité du 15/09/2026, section 1.

| Actionnaire | Nombre d'actions | % capital et droits de vote |
|---|---:|---:|
| OMM (OSEAD Maroc Mining) | 622 690 | 37,04 % |
| CIMR | 278 136 | 16,54 % |
| Axa Assurance Maroc | 69 294 | 4,12 % |
| RCAR | 50 341 | 2,99 % |
| CDG | 36 961 | 2,20 % |
| Atlantic RE | 11 913 | 0,71 % |
| Divers actionnaires | 611 898 | 36,40 % |
| **Total** | **1 681 233** | **100,00 %** |

L'offre porte sur les 611 898 actions des divers actionnaires — Atlantic RE,
Axa, la CDG et le RCAR ayant renoncé à apporter leurs titres.

⚠️ **Ce total de 1 681 233 est le même que celui de notre référentiel**
(`pipeline/faits_financiers.json`, relevé au rapport annuel). Deux sources
indépendantes, le même nombre : c'est ce qui permet d'affirmer que la
capitalisation de 3 727 MDHS servie le 16/09 était juste.
