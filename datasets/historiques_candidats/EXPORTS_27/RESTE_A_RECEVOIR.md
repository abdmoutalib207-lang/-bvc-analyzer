# Les 41 exports qui manquent encore

> Établi le 23/09/2026, après réception des 27 premiers.
> **39 titres sur 80 sont désormais sourcés sur l'export de l'opérateur** —
> 27 reçus le 23/09, 12 le 16/09.

## Comment les récupérer

`casablanca-bourse.com` → fiche du titre → export « Cours », 3 ans.
Le fichier arrive nommé `Cours_<CODE>_<début>_<fin>.csv`.

⚠️ **Le code du nom de fichier est celui de l'OPÉRATEUR, pas le nôtre.**
`TGC` est notre TGCC, `NKL` notre ENK, `SNA` est Stokvis et non Sonasid.
Inutile de renommer quoi que ce soit : l'import résout l'identité sur le code
lu **dans** le fichier et refuse ce qu'il ne reconnaît pas.

## ⚠️ Les 16 MASI 1 d'abord

Ce sont eux qui portent le score et le classement du terminal. Aucun n'a
encore été recoupé — le défaut de volume étant structurel, ils le portent
très probablement tous.

| notre | export | société |
|---|---|---|
| **ADH** | ADH | Douja Prom Addoha |
| **ADI** | ADI | Alliances |
| **CASH** | CAP | Cash Plus SA |
| **CFGB** | CFG | CFG Bank |
| **CMGP** | CMG | CMGP Group |
| **CMT** | CMT | Minière Touissit |
| **CSR** | CSR | Cosumar |
| **MNG** | MNG | Managem |
| **MSA** | MSA | Sodep-Marsa Maroc |
| **RDS** | RDS | Résidences Dar Saada |
| **RIS** | RIS | Risma |
| **SGTM** | GTM | SGTM SA |
| **SMI** | SMI | Société Métallurgique d'Imiter |
| **SOT** | SOT | Sothema |
| **SRM** | SRM | Société de Réalisations Mécaniques |
| **VCNE** | VCN | Vicenne |

⚠️ **Quatre d'entre eux demandent une attention particulière à l'import** :

- **MNG** — split 10:1 du 27/07/2026. L'export de l'opérateur donne-t-il la
  série **rétro-ajustée** ou les cours pré-split tels qu'ils étaient ? À
  établir sur le fichier avant d'écrire : les deux sont défendables, et
  `SPLITS` suppose l'une des deux.
- **CMT** — reprise de cotation après OPA le 16/09, sur une référence remise à
  neuf. R11 : **la série ne doit PAS être rétro-ajustée**, le nombre d'actions
  n'a pas changé et la perte des porteurs est réelle.
- **CMGP** et **CFGB** — portent des corrections déjà réceptionnées. Un
  `recalculer_cache.py --complet` aveugle les annulerait. Vérifier avant.

## Les 25 autres

| notre | export | société |
|---|---|---|
| ALU | ALM | Aluminium du Maroc |
| BMC | BCI | BMCI |
| CAR | CRS | Cartier Saada |
| CIM | CMA | Ciments du Maroc |
| DAR | DRI | Dari Couspate |
| DIS | DIS | Diac Salaf |
| DLM | DLM | Delattre Levivier Maroc |
| DSW | DWY | Disway |
| DTT | DYT | Disty Technologies |
| HPS | HPS | HPS |
| IBM | IBC | IB Maroc.com |
| IMI | IMO | Immorente Invest |
| MDP | MDP | Med Paper |
| MIC | MIC | Microdata |
| OUL | OUL | Oulmès |
| REB | REB | Rebab |
| S2M | S2M | S2M |
| SAF | SAH | Sanlam Maroc |
| SBS | SBM | Société des Boissons du Maroc |
| SLM | SLF | Salafin |
| SNP | SNP | SNEP |
| STR | STR | Stroc Industrie |
| T2S | T2S | T2S Group Holding |
| UNI | UMR | Unimer |
| ZLD | ZDJ | Zellidja |

⚠️ **HPS** porte une rupture de série au 06/10/2023 (6 400 → 658, ratio 0,103)
signalée depuis le 01/08/2026 et jamais tranchée : *« ressemble à un vrai split
1:10 d'octobre 2023 jamais déclaré »*. L'export de l'opérateur permettra de
trancher **sur pièce** plutôt que de le déduire de la série — c'est R11.

## Ce que l'import fera de chacun, sans qu'il y ait à y penser

1. le volume en **titres**, jamais en dirhams ;
2. les séances sans échange à **v = 0**, jamais au cours ;
3. les clôtures du **18/06 → 06/08/2026** reprises ;
4. les **22, 23 et 24 juin** ajoutés ;
5. le **30/07** retiré — Fête du Trône, la Bourse n'a pas ouvert. Une
   quarantaine de titres la portent encore ;
6. le **17/09** maintenu retiré — séance annulée par la Bourse, alors même que
   l'export la contient.

## ⚠️ Par lots de neuf

`test_hors_series_corrigees…` refuse toute livraison qui touche plus d'un tiers
des séries : *« opération de masse, quelle que soit la qualité des instructions
qui l'accompagnent »*. Le garde-fou n'est pas à desserrer — c'est la livraison
qui se découpe.
