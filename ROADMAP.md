# Feuille de route — BVC Analyzer

Conduite par **lots vérifiables**, à la demande du propriétaire du projet
(Abd Moutalib) et sur instruction de la revue externe du 11/09/2026.

**Rien n'est clos par un test ajouté ou un commit poussé.** Un problème passe
par cinq états, et les deux derniers sont distincts :

    Ouvert → En cours → Livré pour revue → Vérifié sur candidat → Vérifié en production

Le suivi détaillé vit dans `AUDIT_TRACKER.csv` : 27 entrées au 11/09/2026,
dont **21 vérifiées sur candidat, 0 vérifiée en production** — parce que rien
n'est fusionné.

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

**État : partiellement acquis.** Les prix synthétiques sont refusés par défaut
depuis le 05/09 et la comptabilité du portefeuille est corrigée (BT-01, BT-02).
Reste le journal daté, les dividendes, la règle d'exécution au prochain prix
et la reproductibilité depuis un dataset figé.

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
