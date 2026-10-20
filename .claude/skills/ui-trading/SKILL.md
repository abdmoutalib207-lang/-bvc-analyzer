---
name: ui-trading
description: Principes d'interface « plateforme de trading » pour le terminal (terminal.src.html), inspirés des maquettes Dribbble « Trading Platform UI » (relevées le 20/10/2026) et adaptés aux règles du projet. À appliquer avec le skill design-vitrine pour toute mise en page sur ordinateur — en particulier l'occupation de l'écran large, qui ne doit jamais reproduire la colonne du téléphone.
---

# UI « plateforme de trading » — BVC Analyzer

Source d'inspiration : recherche Dribbble « trading platform ui » (Naimur Rahman, Alamin Hossen,
Roobinium, ASCII STUDIO…), consultée au navigateur le 20/10/2026. On en garde la STRUCTURE,
pas le discours : ces maquettes vendent du trading ; le terminal publie des fréquences et des
constats (vision du projet : « le produit ne prédit pas »).

## 1. Ce que toutes ces maquettes ont en commun

1. **L'écran large est découpé en panneaux**, jamais une colonne centrée ou collée à gauche.
   Gabarit de référence au-delà de 1200 px :
   `liste des titres (260–320 px) | graphique + fiche (flexible) | panneau chiffres (300–360 px)`.
   Entre 768 et 1200 px : deux colonnes (liste repliable + contenu). Sous 768 px : une colonne.
2. **Le graphique occupe le centre et la hauteur** (≥ 45 % de la hauteur visible sur ordinateur).
3. **Des cartes denses à fond légèrement relevé**, bordure fine, rayon 8–12 px, espacement
   régulier (multiples de 8 px). Pas de carte flottante isolée au milieu du vide.
4. **Chiffres en police tabulaire** (`font-variant-numeric: tabular-nums`), alignés à droite
   dans les tableaux ; libellé petit et pâle au-dessus, valeur grande et nette dessous.
5. **La couleur ne sert qu'à la direction** (hausse/baisse) et aux états ; un seul accent.
6. **En-tête fixe et compact** : bandeau défilant des cours, recherche, état de séance.
7. **Hiérarchie en trois niveaux** au plus par panneau : titre, chiffre clé, détails.

## 2. Ce qui reste interdit ici (règles du projet)

- Aucun bouton « Acheter / Vendre », aucun objectif de cours, aucun « signal » mis en avant
  comme un ordre : la note est colorée sans mot d'action (voir « Couleur de la note »).
- Une estimation de société s'affiche toujours avec la mention « Estimation future (société) »,
  jamais dans la même cellule qu'un chiffre réalisé.
- Toute réserve (couverture partielle, donnée contestée, statut juridique) reste visible : la
  densité ne justifie jamais de la masquer.
- `terminal.src.html` est la source ; `index.html` se recompile (`node tools/compiler_terminal.js`).

## 3. Contrôle obligatoire

Après chaque changement : `node tools/qa_navigateur.js` (390 / 768 / 1440 px) doit rendre
PUBLIABLE, et une capture à 1440 et 1920 px de `#onglet=detail&sym=IAM` ne doit laisser
**aucune bande vide de plus de 25 % de la largeur** à droite du contenu.
