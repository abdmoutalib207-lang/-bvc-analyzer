# Contrat d'identité — à qui appartiennent les cours écrits ?

> ⚠️ **Généré** par `pipeline/identites.py`.

## Pourquoi ce contrôle existe

MSA a porté les cours de **Mutandis** pendant cinq semaines — 18 clôtures identiques au centime sur les dates comparables.

**Aucun contrôle portant sur les nombres ne pouvait l'attraper.** Les cours de Mutandis sont valides : invariant OHLC respecté, variation dans les limites, série continue. Ils appartiennent simplement à une autre entreprise. C'est un défaut d'**identité**.

## Les trois sources qui doivent s'accorder

| Source | Ce qu'elle dit |
|---|---|
| `bvc_config.py` | notre référentiel : ISIN, nom, ticker fournisseur |
| `MANUAL_MAP` | le nom que le collecteur **demande** |
| la réponse reçue | l'identité que le fournisseur **renvoie** |

Les deux premières se vérifient hors ligne. **Seule la troisième protège vraiment** : une table peut être cohérente avec elle-même et fausse.

## État mesuré

**81 titres examinés.**

| Niveau | Titres |
|---|--:|
| abréviation, troncature ou variante du même nom | 58 |
| le collecteur demande le ticker, pas un nom | 12 |
| le nom demandé ne partage rien avec le nôtre | 6 |
| jamais confrontée à une réponse de fournisseur | 4 |
| le nom demandé désigne mieux un AUTRE titre du référentiel | 1 |

⚠️ AUCUNE identité n'est aujourd'hui « vérifiée » : le dépôt ne conserve aucune réponse de fournisseur. « Non confrontée » est donc l'état normal, et il ne vaut PAS approbation.

## ⚠️ Collisions d'identité — écriture REFUSÉE

Le nom demandé désigne **mieux un autre titre** du référentiel. C'est le seul signal qui compte : le fournisseur renverra les cours de cette autre société.

| Ticker | Le collecteur demande | Le référentiel dit | Désigne plutôt |
|---|---|---|---|
| **MRL** | `SODEP` | Maroc Leasing | **MSA** — Sodep-Marsa Maroc (50%) |

⚠️ **Ne pas remplacer ces chaînes par un nom supposé exact.** C'est ainsi que le défaut a été introduit : en juin 2026, cinq entrées ont été « corrigées » depuis des noms jugés corrects, et l'une d'elles contredit notre propre référentiel. Une identité s'établit contre la **réponse du fournisseur**.

## ⚠️ Désaccords de fond — écriture REFUSÉE

Le nom demandé ne partage **ni mot, ni acronyme, ni troncature** avec le nôtre. Il peut désigner une société réelle absente de notre référentiel : le fournisseur renverrait alors **ses** cours.

| Ticker | Le collecteur demande | Le référentiel dit |
|---|---|---|
| **ENK** | `Enkaje` | Ennakl |
| **IAM** | `Maroc Telecom` | Itissalat Al-Maghrib |
| **IMI** | `Immr Invest` | Immorente Invest |
| **PPM** | `Papelera Tetuan` | Promopharm SA |
| **SBS** | `Super Cereales` | Société des Boissons du Maroc |
| **VCNE** | `Vivo Energy` | Vicenne |

⚠️ Certains peuvent être des **noms commerciaux légitimes** — « Maroc Telecom » pour Itissalat Al-Maghrib en est un. Le contrôle ne sait pas les distinguer d'une vraie substitution, et il ne doit pas : dans le doute, il refuse et demande la confrontation. Un faux refus se lève en une vérification ; une fausse écriture reste cinq semaines dans l'historique.

## Désaccords de forme — 58 titres

Le nom demandé s'écrit autrement mais **ne désigne aucun autre titre** du référentiel : abréviations et noms commerciaux. L'écriture n'est pas refusée pour ce motif seul.

| Ticker | Demandé | Référentiel |
|---|---|---|
| ADH | `Addoha` | Douja Prom Addoha |
| ADI | `Alliances` | Alliances |
| AFI | `Afric Indus` | Afric Industries SA |
| AFM | `AFMA` | AFMA |
| AGM | `Agma` | Agma |
| AKD | `Akdital` | Akdital |
| ALU | `Aluminium Maroc` | Aluminium du Maroc |
| ARD | `Aradei Capital` | Aradei Capital |
| ATL | `AtlantaSanad` | AtlantaSanad |
| ATW | `Attijariwafa` | Attijariwafa Bank |
| BAL | `BALIMA` | Balima |
| BMC | `BMCI` | BMCI |
| CAR | `Cartier Saada` | Cartier Saada |
| CASH | `Cash Plus` | Cash Plus SA |
| CFGB | `CFG Bank` | CFG Bank |
| CIM | `Ciments du Maroc` | Ciments du Maroc |
| CMGP | `CMGP Group` | CMGP Group |
| COL | `Colorado` | Colorado |
| CSR | `Cosumar` | Cosumar |
| DAR | `Dari Couspate` | Dari Couspate |
| DHO | `Delta Holding` | Delta Holding |
| DSW | `DISWAY` | Disway |
| DTT | `Disty Technolog` | Disty Technologies |
| EQD | `EQDOM` | Crédit Eqdom |
| FNB | `Fenie Brossette` | Fénie Brossette |
| GAZ | `Afriquia Gaz` | Afriquia Gaz |
| HAL | `Auto Hall` | Auto Hall |
| IBM | `IBMaroc` | IB Maroc.com |
| INV | `INVOLYS` | Involys |
| JET | `Jet Contractors` | Jet Contractors |
| LBV | `LABEL VIE` | Label Vie |
| LES | `Lesieur Cristal` | Lesieur Cristal |
| LHM | `LafargeHolcim` | Holcim Maroc SA |
| M2M | `M2M Group` | M2M Group |
| MGL | `Maghrebail` | Maghrebail |
| MIC | `Microdata` | Microdata |
| MNG | `Managem` | Managem |
| MOX | `Maghreb Oxygene` | Maghreb Oxygène |
| MSA | `Marsa Maroc` | Sodep-Marsa Maroc |
| MUT | `Mutandis` | Mutandis SCA |
| NEJ | `Auto Nejma` | Auto Nejma |
| OUL | `Oulmes` | Oulmès |
| RDS | `Dar Saada` | Résidences Dar Saada |
| REB | `Rebab Company` | Rebab |
| RIS | `Risma` | Risma |
| SAF | `Sanlam Maroc` | Sanlam Maroc |
| SLM | `SALAFIN` | Salafin |
| SNA | `Sonasid` | Sonasid |
| SNP | `SNEP` | SNEP |
| SOT | `SOTHEMA` | Sothema |
| STK | `Stokvis Nord Afr` | Stokvis Nord Afrique |
| STR | `STROC Indus` | Stroc Industrie |
| TIM | `Timar` | Timar |
| TMA | `Total Maroc` | TotalEnergies Marketing Maroc |
| TQA | `TAQA Morocco` | Taqa Morocco |
| UNI | `Unimer` | Unimer |
| WAF | `Wafa Assur` | Wafa Assurance |
| ZLD | `Zellidja` | Zellidja |

⚠️ Une version antérieure de ce contrôle les classait tous comme contradictoires — vingt titres signalés, dont « BOA » pour Bank of Africa. Un contrôle qui crie au loup vingt fois n'est plus lu la vingt-et-unième.

