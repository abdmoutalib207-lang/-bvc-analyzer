# 27 exports « Cours » de l'opérateur — relevé du 23/09/2026

> **Ce dossier PROPOSE, il n'instruit pas.** Rien n'a été écrit dans
> `pipeline/candles/`. L'import se fait par réception documentée dans
> `datasets/historiques_importes/`, comme les douze titres déjà traités.

Source : `casablanca-bourse.com`, export « Cours » 3 ans, fourni par
Abd Moutalib les 22 et 23/09/2026. Période couverte : **24/09/2023 → 23/09/2026**,
734 séances par titre. Empreintes SHA-256 des fichiers reçus dans
`empreintes.json`.

Identité résolue par le code **lu dans la colonne `Ticker`**, via
`IDB_TICKER_MAP` inversé, et le nom d'instrument vérifié. 27/27 résolus —
dont `TGC` → TGCC et `NKL` → ENK, qu'un nom de fichier n'aurait pas donnés.

## Ce qu'on cherchait, et ce qu'on a trouvé

On cherchait **un** défaut : le volume stocké en dirhams. Il y en a **trois**,
et le troisième n'est pas un défaut de volume.

| Défaut | Séances | Portée |
|---|---:|---|
| 1. volume en **dirhams** au lieu de titres | **13 636** | les 27 titres |
| 2. volume valant le **cours**, les séances sans échange | **3 019** | 25 titres |
| 3. **clôtures fausses** | **534** | les 27 titres |
| 4. séances **absentes** de nos séries | **842** | les 27 titres |

### 1 — Le volume en dirhams

L'export porte **deux** colonnes de volume : `Volume (MAD)`, un montant en
dirhams, et `Titres Échangés`, un nombre de titres. Un chargeur qui retient
« la première colonne contenant *vol* » prend le montant. ATW le 22/09 :
23 343 966,70 DH échangés pour **33 778 titres** — nous publiions le premier
nombre comme s'il était le second.

La cause était **déjà écrite** dans `datasets/historiques_importes/AKD.json`,
champ `_colonne_de_volume`. Elle avait été comprise sur un titre sans être
appliquée aux autres.

### 2 — Le cours recopié dans le volume

Les séances où l'export écrit `-` (pas d'échange), nous portons un volume non
nul — et ce nombre **est le cours**. CDM, 25/09/2023 : `v = 700` pour un titre
qui cote 700,00. Le défaut est systématique sur 131 séances de CDM, 466 d'AGMA,
612 d'Auto Nejma.

Conséquence : un titre qui n'a pas échangé apparaît comme ayant échangé, et
son volume suit mécaniquement son cours. Tout indicateur de liquidité construit
là-dessus est faux — c'est précisément le sujet de l'étude que vous m'aviez
transmise.

### 3 — ⚠️ Les clôtures fausses : ce n'est plus un problème de volume

**534 séances où notre clôture ne vaut pas celle de l'opérateur**, concentrées
sur une fenêtre nette : **18/06 → 06/08/2026**, les mêmes 32 dates sur presque
tous les titres.

Sur CDM, 8 des 24 valent **exactement la clôture de la veille**. Et trois
séances manquent à l'appel chez les 27 titres : **22, 23 et 24 juin 2026**.
La série reprend le 25 en portant les valeurs du 24.

C'est cohérent avec une panne de collecte de trois jours suivie d'une reprise
sur une source qui servait la séance précédente — le même mécanisme que
l'incident du 28/08, mais non détecté à l'époque parce que `_cliquet_seance()`
n'existait pas encore.

**Ce défaut relève de R1, pas d'un champ d'affichage.** Un cours faux fausse le
RSI, les moyennes mobiles, le MACD, et donc le pilier technique — 25 % du score.

### 4 — Les séances absentes

842 au total, dont les 4 communes à tous (`22`, `23`, `24/06` et `17/09/2026`).
Le reste est inégal : **676 pour ENK**, dont la série chez nous est quasi vide.
AGMA en manque 16, BALIMA 10, ATL 11.

## Ce que cet export ne dit pas

- Il s'arrête au **23/09/2026** : la séance du jour continue d'entrer
  normalement par le moteur, comme pour les douze titres déjà importés.
- Il ne couvre que **27 des 80 titres**. Les 53 autres portent très
  probablement les mêmes trois défauts — le défaut n°1 est structurel, il ne
  dépend pas du titre.
- Il donne `Ouverture`, `Plus Haut`, `Plus Bas`, `Dernier Cours` : la bougie
  complète, pas seulement la clôture.

## Reproduire le relevé

```
python3 pipeline/diagnostiquer_export_bvc.py <export.csv> [...]
python3 pipeline/diagnostiquer_export_bvc.py --detail <export.csv>
```

`tableau.txt` et `releve.json` sont les sorties de ces deux commandes sur les
27 fichiers reçus.
