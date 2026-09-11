# Anomalies des données — lot 1A

Relevées par `pipeline/inventaire.py`. Chaque entrée porte ce qui est
MESURÉ, puis le traitement envisagé — qui n'est pas encore appliqué.

## A-01 · Séances sans volume

**5 séries** comptent plus de la moitié de lignes à volume nul :

| Titre | Part sans volume | Lignes |
|---|---:|---:|
| DAR | 65% | 65 |
| STK | 62% | 50 |
| MRL | 61% | 64 |
| UNI | 58% | 62 |
| MGL | 55% | 49 |

**Ce que la donnée ne dit pas** : une ligne à `v = 0` peut signifier une séance
sans transaction, une valeur non renseignée par la source, ou une séance où le
titre n'a pas coté. Les trois sont aujourd'hui indistinguables.

**Traitement envisagé** — porter un statut par observation :
`negociee` / `sans_transaction` / `non_cotee` / `inconnue`. Une séance sans
transaction ne doit jamais devenir une transaction à volume nul. Si une valeur
est reportée pour valoriser un portefeuille, l'opération est une VALORISATION,
distincte d'un échange.

⚠️ Conséquence pour le lot 2 : une moyenne mobile reste calculable sur une
série comportant de telles lignes. Elle n'est pas « fausse » — sa fiabilité
dépend d'une politique d'admissibilité qui reste à définir explicitement, comme
l'a relevé la revue. La définir fait partie du lot 1, pas du lot 2.

## A-02 · Trous du calendrier attendu

| Titre | Trous | Jours ouvrés attendus | Lignes présentes |
|---|---:|---:|---:|
| SOT | 43 | 584 | 542 |
| RDS | 43 | 585 | 543 |
| CMT | 37 | 551 | 514 |
| HPS | 36 | 824 | 789 |
| LHM | 34 | 824 | 791 |
| CMGP | 34 | 436 | 403 |
| TGCC | 33 | 1201 | 1170 |
| DHO | 31 | 824 | 794 |

⚠️ **Ce compte n'est pas un décompte d'erreurs.** Le calendrier attendu exclut
les week-ends et les fériés à DATE FIXE. Les fériés marocains suivent en partie
le calendrier lunaire et le projet ne maintient pas leur liste : un « trou »
peut être un jour férié parfaitement normal.

**Traitement envisagé** : distinguer `ferie` / `seance_manquante` /
`suspension` au niveau de l'observation, à partir d'un signal de marché — une
séance réelle ne reproduit jamais toutes les clôtures au centime près — plutôt
que d'une liste de dates à maintenir.

## A-03 · Unité du volume — DAT-10, ouvert

Les chandelles ne conservent pas le programme qui les a écrites. Pour une
bougie ancienne, l'unité est déduite de la convention du moteur — il lit
`QteEchangee`, que le bulletin CDG distingue explicitement de `Volumes`
(montant en dirhams) — et non lue dans la donnée.

L'inventaire déclare donc `unite = "nombre de titres"` avec
`certitude = "présumée"`. Le cas nommé par la revue reste ouvert : la bougie
CMT du 16/07 porte `v = 67515`.

**Traitement envisagé** : porter l'unité et la source d'écriture DANS
l'observation, pour les séries futures ; pour l'historique, ne pas rétro-
certifier ce qu'aucune trace ne permet d'établir.

## A-04 · Séries absentes

7 titres de l'univers n'ont aucune série :
DIS, DLM, MDP, PPM, SAF, SLM, T2S.

**Traitement envisagé** : ces titres restent hors de toute mesure tant
qu'aucun historique n'existe. Leur absence doit rester VISIBLE, jamais
comblée par un repli.

## A-05 · Profondeur insuffisante pour le socle du lot 2

**32 séries** comptent moins de 200 lignes, donc moins que la
fenêtre de la plus longue moyenne mobile du socle :

MGL (49), BMC (50), ENK (50), FNB (50), HAL (50), STK (50), STR (57), UNI (62), MRL (64), OUL (64), ZLD (64), DAR (65), S2M (65), SNP (65), TMA (65), TQA (65), IBM (66), SBS (67), WAF (67), ALU (68), MIC (68), REB (68), AKD (69), CAR (69), DSW (69), DTT (69), IMI (69), MUT (69), SNA (69), CIM (74), SGTM (155), CASH (162).

**Traitement envisagé** : une SMA 200 ne sera pas calculée avec moins de
200 observations admissibles. Le champ restera absent — pas approximé,
pas rempli par une fenêtre plus courte sous le même nom.
