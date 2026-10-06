---
name: qa-navigateur
description: Contrôle le terminal dans un vrai navigateur (téléphone 390 px, tablette 768 px, bureau 1440 px) avant ou après publication — erreur de rendu, erreurs console, classement vide, débordement horizontal, fiche ou graphique absent, bouton FIB. Lecture seule. Rend PUBLIABLE ou À CORRIGER. À lancer sur toute modification de terminal.src.html, après compilation.
---

# Contrôle navigateur du terminal

Adapté de la compétence `browser-qa` du projet ECC (MIT), réduit à ce qui a
déjà cassé chez nous :

- 04/10/2026 : « Cannot access 'sym' before initialization » → écran
  « Erreur de rendu » sur tout le terminal, invisible aux tests Python ;
- graphique plein écran piégé par un `transform` de `.carte` ;
- débordement horizontal sur téléphone.

## Procédure

```bash
node tools/compiler_terminal.js            # index.html à jour
npm install --no-save --no-package-lock playwright react@18 react-dom@18 \
    lightweight-charts@4.2.0 @babel/standalone@7.29.9
python3 -m http.server 8818 &               # depuis la racine du dépôt
node tools/qa_navigateur.js IAM VCNE MNG --sortie <scratchpad>/qa
```

- Les titres en argument sont ouverts un par un ; choisir ceux que la
  modification touche, plus un titre MASI 1.
- Les bibliothèques des CDN sont servies depuis `node_modules` : aucun appel
  réseau, aucune action d'écriture sur le site.
- `QA_URL=…` pour viser une autre adresse ; ne viser le site publié qu'en
  lecture.
- Code de sortie 0 = PUBLIABLE, 1 = À CORRIGER.

## Contrôle négatif (à refaire si le script change)

Le 06/10/2026 : copie de `index.html` avec une exception volontaire dans
`StockChart` pour IAM → le script rend « aucun graphique » et l'erreur
console, code 1. Un contrôle qui n'a jamais été vu rouge ne prouve rien.

## Ce qu'il ne fait pas

- Pas de comparaison d'images avec une référence : regarder les captures
  de `--sortie` quand la modification est visuelle.
- Pas d'audit d'accessibilité automatique (axe-core non installé).
- Il ne remplace pas les tests de `tests/test_graphique_interactif.py`, qui
  vérifient le code sans navigateur et tournent en CI.
