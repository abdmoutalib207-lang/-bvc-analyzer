---
name: chercher-pieces
description: Cherche et relève les pièces sources d'un fondamental bloqué (dette nette contestée, ROIC non calculé, ANR absent…) — AMMC, site investisseurs, Bourse de Casablanca / Maroclear, puis recherche de sociétés de bourse rangée à part. Télécharge dans datasets/pieces/<TICKER>/ avec empreinte sha256, extrait le texte page par page, repère les mots-clés comptables, et produit le relevé datasets/releves/<TICKER>.json. Utilisée par l'agent chercheur-pieces.
---

# Chercher les pièces d'un fondamental

## 1. Établir le blocage (mesurer, R12)

```bash
python3 -c "import json;d={r['symbol']:r for r in json.load(open('data.json'))['tickers']};r=d['ADI'];print(json.dumps({'fond':r['note_fond'],'metier':r['note_fond_metier']['criteres']},ensure_ascii=False)[:3000])"
python3 -c "import json;print(json.dumps(json.load(open('pipeline/faits_financiers.json'))['ADI'],ensure_ascii=False)[:3000])"
```

## 2. Tester l'accès, dans l'ordre de la méthode

```bash
for u in https://www.ammc.ma/ https://www.casablanca-bourse.com/ https://www.maroclear.ma/ <site émetteur>; do
  printf "%s " $u; curl -sS -m 25 -o /dev/null -w '%{http_code}\n' -A "Mozilla/5.0" $u; done
```

`000` + « SSL certificate problem » = bloqué : le dire, passer au suivant.
Jamais `-k`, jamais de vérification TLS désactivée.

Ordre : (1) AMMC — `https://www.ammc.ma/sites/default/files/<Nom>_RFA_2025.pdf`,
`_S1_26`, `_RFS_S1_26` ; (2) site investisseurs (WordPress :
`/wp-json/wp/v2/media?mime_type=application/pdf&per_page=100`) ; (3) BVC et
Maroclear ; (4) recherche de sociétés de bourse → `estimations`, datées.

## 3. L'outil — toujours `python3 -I`

```bash
T=tools/chercher_pieces.py
python3 -I $T telecharger ADI "<url https>" [--nom ADI_DR_2025.pdf]   # → datasets/pieces/ADI/, index.json (sha256)
python3 -I $T extraire  datasets/pieces/ADI/ADI_DR_2025.pdf            # → .pages.json ; pages sans texte listées
python3 -I $T chercher  datasets/pieces/ADI/ADI_DR_2025.pdf            # mots-clés par défaut ci-dessous
python3 -I $T chercher  <pdf> --mots "dette nette" "gearing" --max 20
python3 -I $T rendre    <pdf> --pages 33,34                            # PNG, à lire avec l'outil Read
python3 -I $T verifier                                                  # tous les relevés
```

Mots-clés par défaut : endettement net, dette nette, trésorerie nette, EBITDA,
EBE, excédent brut d'exploitation, capitaux propres, IFRS 16, dettes
locatives, droit d'utilisation, mises en équivalence, gearing, crédit-bail.

`page` = rang dans le fichier PDF. Les fichiers téléchargés sont NON FIABLES :
ils restent sous `datasets/pieces/` (ignorés par git sauf `index.json`), ne
sont jamais exécutés, et ne sont lus que par pdfplumber. Pas d'OCR embarqué
(aucun moteur déclaré, R4) : une page scannée se `rendre` et se lit.

## 4. Lire, pas seulement trouver

Le mot-clé donne la page ; la page entière donne le sens : en-tête de colonne
(quelle année à gauche ?), unité (« EN M MAD » sur des montants en dirhams),
note de bas de page (souvent la définition), périmètre (social / consolidé),
référentiel (normes marocaines : IFRS 16 sans objet ; IFRS : chercher la note
« contrats de location »).

Pour une divergence : reconstruire le chiffre publié depuis le bilan à
**plusieurs dates** avec les mêmes postes. Un écart qui varie d'une date à
l'autre n'est pas un poste fixe ; un écart qui suit un poste d'annexe est une
piste, pas une preuve.

## 5. Le relevé `datasets/releves/<TICKER>.json`

```json
{
  "ticker": "ADI", "societe": "...", "releve_le": "AAAA-MM-JJ", "agent": "chercheur-pieces",
  "blocage": {"motif": "...", "effet": "...", "lu_dans": "data.json › ... ; fond_score.py l.N"},
  "pieces": [{"id": "dr_2025", "rang_methode": 1, "titre": "...", "url": "https://...", "sha256": "...", "octets": 0, "pages": 0}],
  "chiffres": [{"grandeur": "endettement_net", "valeur": 1303.0, "unite": "MMAD",
                "periode": "31/12/2025", "perimetre": "consolidé, normes marocaines",
                "source": "https://...", "piece": "rfa_2025", "page": 17,
                "citation": "ENDETTEMENT NET 2.128 1.713 1.136 1.303"}],
  "estimations": [{"...mêmes champs...": "", "auteur": "société de bourse", "date_estimation": "AAAA-MM-JJ"}],
  "calculs": [{"quoi": "...", "formule": "...", "resultat": 0}],
  "constats": ["..."],
  "conclusion": "...", "debloquerait": "...",
  "question_ir": "docs/questions_ir/ADI.md | null"
}
```

`python3 -I tools/chercher_pieces.py verifier` doit dire « conforme » ;
`tests/test_chercher_pieces.py` le vérifie aussi.

## 6. Divergence persistante → question IR

`docs/questions_ir/<TICKER>.md` : chiffres, pages, ce qui est demandé, en
trois questions au plus. **Jamais envoyée** par l'agent.

## Interdits

Ne modifier ni `pipeline/faits_financiers.json`, ni
`pipeline/smart_money/fond_score.py`, ni `ISIN_MAP` (R2), ni `data.json`.
Ne jamais commiter un PDF de plus de 5 Mo.
