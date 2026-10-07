---
name: design-vitrine
description: Améliore le VISUEL et la FLUIDITÉ du terminal (terminal.src.html) — espacements, typographie, contrastes, états des boutons, zones tactiles, mouvements, lisibilité sur téléphone — sans toucher au moteur ni aux données. Utilisée par l'agent designer-vitrine.
---

# Design de la vitrine

Deux références reprises du projet ECC (everything-claude-code, licence MIT,
`LICENSE-ECC.txt`), copiées telles quelles :

- `finition.md` — *make-interfaces-feel-better* : la liste concrète des
  détails qui font une interface soignée.
- `direction.md` — *frontend-design-direction* : comment fixer une direction
  visuelle propre au produit plutôt qu'un style générique.

## Ce qui s'ajoute pour BVC Analyzer

- **Le contenu prime sur le décor.** Le produit ne prédit pas : aucun effet
  visuel ne doit faire passer une fréquence ou une note pour une promesse
  (pas de vert « victoire », pas d'animation qui célèbre un chiffre).
- **Lisibilité des chiffres d'abord** : chiffres tabulaires, unités et
  effectifs (« n cas », « IC ») jamais tronqués, contraste suffisant sur fond
  sombre, téléphone 390 px en premier.
- **Un état incertain se voit** : « non vérifié », « Données insuffisantes »,
  ⚠ date — jamais atténués au point de disparaître.
- **Fluidité mesurable** : temps d'ouverture (mesuré à 0,8 s ordinateur,
  2,6 s téléphone le 29/09), pas de saut de mise en page au chargement,
  pas de re-rendu du graphique à chaque frappe.
- **Ne jamais toucher** : `update_data.py`, `pipeline/`, `data.json`,
  `bvc_config.py`, les notes, les seuils. Seuls `terminal.src.html`
  (puis `node tools/compiler_terminal.js`) et les tests d'affichage.
- **Toute livraison passe par `qa-navigateur`** (captures 390 / 768 / 1440 px).
