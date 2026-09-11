# Feuille de route — BVC Analyzer

Conduite par **lots vérifiables**, à la demande du propriétaire du projet
(Abd Moutalib) et sur instruction de la revue externe du 11/09/2026.

**Rien n'est clos par un test ajouté ou un commit poussé.** Un problème passe
par cinq états, et les deux derniers sont distincts :

    Ouvert → En cours → Livré pour revue → Vérifié sur candidat → Vérifié en production

Le suivi détaillé vit dans `AUDIT_TRACKER.csv` : **43 entrées**, dont
**33 vérifiées sur candidat, 4 livrées pour revue,
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

### Lot 1B — livré pour revue

| Livrable | Où | État |
|---|---|---|
| Contrat d'admissibilité | `pipeline/qualification.py` | 11 tests |
| Calendrier versionné | `pipeline/calendrier_bvc.json` | 2 dates établies, le reste `non_confirme` |
| Diagnostic des bases de prix | `docs/DIAGNOSTIC_SPLITS.md` | MNG et SOT tranchés |
| Couche normalisée | `datasets/lot1b/` | 7 séries, dérivée de l'instantané |
| Journal des transformations | `docs/JOURNAL_TRANSFORMATIONS.md` | appliqué **et** non appliqué |
| Tests de comportement | `tests/test_normalisation.py` | 46 tests |

**Deux résultats à retenir.**

- **MNG est déjà ajusté** : les clôtures 24/07 → 27/07 donnent un rapport de
  1,091, continu à travers le split. Le risque sur ce titre est **d'agir**, pas
  de s'abstenir — réappliquer l'ajustement produirait une double division.
- **SOT porte une double division par 5** avant le 05/05/2026. **487 des
  542 observations sortent sans aucun usage admissible.** La correction n'est
  pas appliquée : multiplier par 5 fabriquerait 486 prix qu'aucune source en
  notre possession ne confirme.

⚠️ **Aucune valeur de prix n'a été modifiée dans ce lot.** La couche normalisée
qualifie ; elle ne retouche pas. L'instantané `datasets/lot1a/` reste intact et
ses empreintes sont vérifiées par test.

## Lot 2 — Normaliser les indicateurs techniques

**État : non commencé.** Couche de calcul commune et versionnée, partagée par
le graphique et le scoring. Socle spécifié par la revue : SMA 20/50/200, RSI
de Wilder 14, MACD 12/26/9, ATR 14, ADX et DI± 14, Bollinger 20/2, activité et
liquidité sur 20 et 60 séances, force relative au MASI, niveaux de prix.

⚠️ Spécification de départ **à tester**, pas une formule de performance
validée. Leur contribution au scoring devra être évaluée séparément.

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
