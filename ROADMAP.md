# Feuille de route — BVC Analyzer

Conduite par **lots vérifiables**, à la demande du propriétaire du projet
(Abd Moutalib) et sur instruction de la revue externe du 11/09/2026.

**Rien n'est clos par un test ajouté ou un commit poussé.** Un problème passe
par cinq états, et les deux derniers sont distincts :

    Ouvert → En cours → Livré pour revue → Vérifié sur candidat → Vérifié en production

Le suivi détaillé vit dans `AUDIT_TRACKER.csv` : **73 entrées**, dont
**35 vérifiées sur candidat, 32 livrées pour revue,
6 ouvertes, et 0 vérifiée EN PRODUCTION** — parce que rien n'est fusionné.

⚠️ Cette synthèse est recalculée à chaque mise à jour du registre. Une version
antérieure annonçait encore 27 entrées quand le fichier en portait 33 : la
revue externe l'a relevé.

---

## Lot 0 — Fermer la chaîne de livraison

**État : livré pour revue.** La partie « arrêt automatique » est acquise et a
été vérifiée indépendamment par la revue externe sur trois scénarios (test en
échec, erreur interne de pytest, aucun test exécuté). Ne pas la refaire.

| Point | État |
|---|---|
| Code de retour de pytest conservé et bloquant | acquis, vérifié en externe |
| Dossier de diagnostic marqué « non validé » | acquis |
| Rapport JUnit avec échecs, erreurs et raisons des exclusions | acquis |
| Note sur les unités du volume CMT jointe | acquis |
| **Empreinte du JSON testé = empreinte du JSON empaqueté** | **ajouté, à revoir** |
| **Phrase résiduelle d'attribution retirée** | **ajouté, à revoir** |

**Robot** — lot distinct. Les journaux expurgés, la cause établie et la preuve
d'un déclenchement réussi restent à fournir. ⚠️ Ne pas confondre la réussite
d'un workflow avec la fraîcheur du fichier réellement servi.

## Lot 1 — Fiabiliser les données et les historiques

**État : inventaire fourni, univers proposé.** Voir `docs/CONTRATS_DONNEES.md`
pour la définition des champs et `docs/INVENTAIRE_LOT1.md` pour la couverture
mesurée titre par titre.

### Lot 1B.2 — livré pour revue

Le lot 1B.1 a été **reçu partiellement** : corrections numériques vérifiées
indépendamment, **portée du contrat d'usage à corriger**. Cette passe traite
les six points de la revue.

| Livrable | Où |
|---|---|
| Contrat d'admissibilité | `pipeline/qualification.py` |
| Régimes de variation sourcés | `pipeline/regimes_variation.py` |
| Calendrier versionné | `pipeline/calendrier_bvc.json` |
| Couche normalisée | `datasets/lot1b/` — 7 séries |
| Journal des transformations | `docs/JOURNAL_TRANSFORMATIONS.md` |
| Tests de comportement | `tests/test_normalisation.py`, `test_qualification.py`, `test_fenetre.py` |
| Qualification par fenêtre datée | `pipeline/fenetre.py` |
| Bilan mesuré dans les artefacts | `docs/BILAN_LOT1B.md` ← `pipeline/bilan_lot.py` |

**Cinq usages, séparés** : `prix_analyse`, `volume`, `indicateur`,
`indicateur_exploratoire`, `execution_simulee`. Chaque refus porte son motif.

**Trois situations, trois issues** — et non deux : refuser · calculer à titre
exploratoire en le signalant · permettre. Le niveau exploratoire est la porte
que la revue a demandé d'ouvrir : on peut essayer, à condition de dire qu'on
essaie.

**L'amplitude ne démontre pas la conformité.** `evaluer_amplitude` mesure
l'écart des prix entre eux ; `evaluer_conformite` vérifie leur position autour
du cours de référence, et répond « non vérifiable » tant qu'il lui manque la
référence, le régime ou la période de validité — c'est le cas partout
aujourd'hui.

**La preuve sur les prix ne vaut pas preuve sur les quantités.** Deux
registres, deux provenances. L'exécution simulée n'exige pas des prix ajustés,
mais une comptabilité cohérente ; et elle n'établit pas qu'un ordre aurait été
rempli — cela relève du protocole de backtest.

**Les diagnostics portent un niveau de preuve** : ajustement documenté ·
ajustement probable, à confirmer · base incohérente ou suspecte · état inconnu.
Le fait observé, l'hypothèse et la pièce manquante sont consignés séparément.

⚠️ **Conséquence, mesurée dans les artefacts** — voir `docs/BILAN_LOT1B.md`,
généré par `pipeline/bilan_lot.py` : **aucun des 7 titres** n'autorise
d'indicateur **publiable**, **6 sur 7** autorisent un calcul **exploratoire**,
et **aucune observation** n'autorise l'exécution simulée.

Le calcul exploratoire est la porte que la revue a demandé d'ouvrir : on peut
essayer, à condition de signaler qu'on essaie. Il n'alimente ni le signal
officiel, ni une probabilité, ni une performance présentée comme validée.

⚠️ **Aucune valeur de prix n'a été modifiée.** L'instantané `datasets/lot1a/`
reste intact et ses empreintes sont vérifiées par test.

## Lot 2 — Normaliser les indicateurs techniques

**État : socle mathématique livré, branchement exploratoire démontré.**

`pipeline/indicateurs.py` — fonctions pures, sans TA-Lib : SMA, EMA, RSI de
Wilder, MACD, Bollinger, ATR, OBV. Trois règles non négociables :

1. **aucune valeur absente n'est comblée** — un trou produit `None`, jamais un
   zéro ni un report ;
2. **la longueur de sortie égale celle de l'entrée** — décaler une série
   d'indicateur par rapport à ses dates est la faute classique, et invisible ;
3. **aucune performance n'est calculée ici** — des nombres, pas des signaux.

Les 29 tests du socle établissent leurs attendus **indépendamment** : soit par
une arithmétique écrite dans le test, soit par un cas limite déduit de la
définition. Les séries de contrôle portent le préfixe `SERIE_CONSTRUITE_` et un
test vérifie qu'aucune ne se trouve sous `datasets/`.

**Premier branchement réel** : `pipeline/calculer_indicateur.py` enchaîne la
couche normalisée, la qualification par fenêtre et le calcul. Le résultat porte
toujours son verdict et sa réserve.

| Démonstration | Fenêtre | Verdict | Points |
|---|---|---|--:|
| ADH · SMA 20 | 01/06 → 08/09/2026, 63 lignes | exploratoire | 44 |
| CSR · RSI 14 | 01/06 → 08/09/2026, 60 lignes | exploratoire | 46 |
| SOT · SMA 20 | depuis 06/2024 | **refusé** | 0 |

Le refus de SOT nomme ses motifs : la fenêtre traverse l'alerte du 05/05/2026
et 473 observations sans usage admissible.

⚠️ Reste à faire : ADX et DI±, force relative au MASI, niveaux de prix. Et
surtout — la contribution de ces indicateurs au scoring n'est **pas** évaluée.
Spécification à tester, pas formule de performance validée.

## Lot 3 — Graphique de référence

**État : non commencé.** TradingView Lightweight Charts, version fixée,
compilation avant livraison, obligations d'attribution respectées.

## Lot 4 — Unifier scores et signaux

**État : partiellement acquis.** Les composantes `score_tech`, `score_fond` et
`score_nlp` sont désormais publiées et le mode personnalisé les utilise
(UI-03). Reste à séparer explicitement qualité des données, signal et
éligibilité à une décision.

## Lot 5 — Remplacer les historiques synthétiques dans la recherche

**État : OUVERT.** ⚠️ Une version antérieure de ce fichier annonçait que « les
prix synthétiques sont refusés par défaut depuis le 05/09 ». **C'était faux
par généralisation** : le refus porte sur `phase11_backtest.py` seulement. La
revue externe a retrouvé, au commit livré :

- `phase8_correlations.py:186` — `generate_synthetic_price_series()` est
  toujours appelée dans `build_price_panel()` ;
- `phase9_ml.py:227` — `rng.binomial(1, 0.35, …)` produit encore des étiquettes
  de résultat tirées au sort en l'absence de prix.

Ce sont **deux problèmes distincts** de la comptabilité du portefeuille, qui
est corrigée (BT-01, BT-02). Les inscrire sous les identifiants déjà clos
aurait présenté un chantier ouvert comme acquis. Ils portent donc des
identifiants neufs : **RCH-01, RCH-02, RCH-03**.

Reste aussi : journal daté, dividendes, exécution au prochain prix exécutable,
reproductibilité depuis un dataset figé.

## Lot 6 — Valider hors échantillon

**État : non commencé.** Protocole à écrire AVANT les expériences.

## Lot 7 — Rendre le NLP utile et contrôlable

**État : non commencé.** Le corpus existe ; sa contribution financière n'a
jamais été mesurée séparément de sa qualité linguistique.

## Lot 8 — Observation prospective

**État : non commencé.** Conditionné aux lots précédents.

---

## Ce qui n'est promis nulle part

Aucun rendement, aucun niveau de performance, aucune supériorité prédictive.
Le terminal organise de l'information traçable et explique ses limites. Le
passage d'« information organisée » à « décision fiable » demande le lot 6, et
il n'est pas franchi.
