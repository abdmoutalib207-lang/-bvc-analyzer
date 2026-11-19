# Feuille de route — de 6/10 à 9/10

> Demande d'Abd Moutalib, 19/11/2026 : « corriger tout ce qui est nécessaire
> pour arriver à 9/10 ; travail toujours automatisé et à jour ; collecte de
> toutes les publications ; interface sans bruit, lecture simple ».
>
> Point de départ : deux audits externes indépendants du 19/11/2026 —
> **Manus 6,0/10** et **GPT 6,1/10** (septembre : 5,6/10). Ce document est la
> référence du travail jusqu'au prochain audit. Il se met à jour à chaque lot
> fini (colonne « État »), jamais en silence.

## 1. Comment on saura qu'on a atteint 9/10

**Le juge n'est pas nous.** On rejoue le même audit externe (même consigne,
mêmes sept axes, deux auditeurs différents) quand la phase 5 est finie.
Objectif : **≥ 9,0 chez les deux**, aucun constat CRITIQUE, au plus deux MAJEUR.

| Axe | Manus / GPT au 19/11 | Cible | Ce qui fera la différence |
|---|---|---|---|
| 1. Exactitude des données | 6,3 / 6,0 | 9 | Phases 2 et 5 |
| 2. Honnêteté des chiffres absents | 5,5 / 7,0 | 9 | Phase 2 |
| 3. Score BVC | 8,0 / 7,0 | 9 | Phase 1 (mesure lue depuis l'artefact) |
| 4. Fiabilité de la production | 6,0 / 6,5 | 9 | Phase 3 |
| 5. Code et tests | 7,0 / 7,0 | 9 | Phases 3 et 5 |
| 6. Utilisabilité débutant | 6,5 / 6,5 | 9 | Phase 1 |
| 7. Juridique et réputation | 4,0 / 3,0 | 8 | Phase 4 — **une partie ne dépend pas de nous** |

⚠️ **Honnêteté sur l'axe 7.** La purge des références `refs/pull/8` et `/9`,
un accord écrit avec les fournisseurs de données et toute démarche CNDP ou
AMMC ne peuvent être faits que par Abd Moutalib. Sans eux, l'axe 7 plafonne
vers 5-6 et la note globale vers 8,5. Le code ne peut pas acheter cette note.

## 2. Règles de conduite pendant tout le chantier

1. **Un lot = une PR**, petite, relue par `relecteur-pipeline`, CI verte, puis
   fusion. Jamais deux chantiers dans la même PR (R7).
2. **Mesurer avant d'affirmer** (R12) : chaque lot dit son effet chiffré
   (titres touchés, scores qui bougent : en principe zéro).
3. **Le Score BVC ne change pas** sans mesure ni accord (R8). Aucun lot de
   cette feuille de route ne modifie sa formule.
4. **Rien ne se publie à moitié** : un écran modifié passe le contrôle
   navigateur (`qa-navigateur`) à 390, 768 et 1 440 px.
5. **Ce qui est fait s'automatise** : un contrôle manuel qui marche devient un
   test ou une tâche planifiée dans le même lot.
6. **La mémoire suit** : un incident → `ERRORS.md` ; une décision → journal
   du `CLAUDE.md` (sur accord) ; l'avancement → la colonne « État » ci-dessous.

## 3. Les phases

### Phase 0 — Déjà fait le 19/11 (audits)

| Lot | PR | État |
|---|---|---|
| Erreurs de calcul bloquées avant publication (PER, variation, rendement, BPA, dividende) | #365 | ✅ |
| Motifs et libellés trompeurs (ENK, NRJ, dividende 0, écart de capitalisation, « Upside ») | #366, #367 | ✅ |
| PER « n.s. » au-delà de 100x, comme MASI Screener | #364 | ✅ |
| Capitalisation de NRJ | #363 | ✅ |
| Mesure du score tel qu'affiché (hebdomadaire) | #368 | ✅ |

### Phase 1 — Une lecture simple et vraie (axes 3 et 6)

But : un débutant comprend la fiche en dix secondes, et l'écran ne promet que
ce que les données tiennent.

| Lot | Contenu | Agent | Critère de fin |
|---|---|---|---|
| 1.1 Inventaire du bruit | Liste de tout ce qui s'affiche sans servir une décision de lecture (doublons, badges, infobulles redondantes, libellés techniques). Chaque élément : garder / déplacer dans « Détail » / retirer. | `designer-vitrine` | Liste chiffrée, validée avant tout retrait |
| 1.2 Cours de séance dits comme tels | Pendant la séance : « Cours de séance · 14h56 · différé » ; après la clôture : « Clôture du JJ/MM ». La garantie de confiance « cours de la dernière séance » devient « cours de la séance, relevé à HHhMM » tant que la séance est ouverte. | `designer-vitrine` + `relecteur-pipeline` | Plus aucun « J+1 » ni « clôture » sur un cours de séance |
| 1.3 Une date par chiffre, quatre au plus par fiche | Cours (séance), score (semaine close), comptes (date d'arrêté), risque (date) : chacun porte sa date, au même endroit, même format | `designer-vitrine` | Contrôle navigateur sur 5 fiches |
| 1.4 Couleurs qui ne recommandent pas | Le vert/rouge reste réservé aux hausses/baisses ; les tranches du score passent à une échelle neutre (gris → bleu) | `designer-vitrine` | Aucune tranche de score dans la couleur des hausses |
| 1.5 Fiche en trois étages | 1) En bref : cours, variation, score de la semaine et sa phrase, trois chiffres clés ; 2) Comprendre : facteurs du score, ratios avec leur source ; 3) Détail : états financiers, risques, pièces | `designer-vitrine` | Le premier écran du téléphone tient sans défilement |
| 1.6 Glossaire et « Comment lire » en une page | PER, P/B, ROE, dividende, liquidité, Score BVC, « n.s. », « — » : une phrase chacun, accessible depuis chaque terme | `designer-vitrine` | Chaque terme technique de la fiche a son infobulle d'une phrase |
| 1.7 Mesure du score lue depuis l'artefact | Le terminal lit `score_bvc_hebdo_*.json` au lieu de chiffres écrits à la main ; test de synchronisation | `quant-backtest` + `ingenieur-tests` | Zéro chiffre de mesure écrit en dur |

### Phase 2 — Des chiffres complets et à jour (axes 1 et 2)

| Lot | Contenu | Agent | Critère de fin |
|---|---|---|---|
| 2.1 Collecte automatique des publications | Chaque jour ouvré : AMMC (comptes annuels, semestriels, trimestriels, avis d'AG, communiqués) + Bourse (avis : dividendes, opérations sur titres, suspensions, introductions). Chaque nouveauté est classée et mise en file. | `collecteur-publications` (nouveau) | Rapport quotidien ; aucune publication de plus de 3 jours ouvrés non classée |
| 2.2 Registres tenus par la collecte | Dividendes, `SPLITS`, `SUSPENSIONS`, `INTRODUCTIONS` : chaque nouvelle pièce donne une PR de registre, avec sa page | `collecteur-publications` → `relecteur-pipeline` | Délai pièce → registre ≤ 2 jours ouvrés |
| 2.3 Lecture des comptes sans retard | La tâche du soir lit jusqu'à 3 dossiers par soir ; objectif : file vide sous 5 jours ouvrés après un dépôt | `lecteur-comptes` + `verificateur-finance` | File des comptes ≤ 5 jours d'ancienneté |
| 2.4 Motifs pour tous les « — » | 15 des 18 grandeurs absentes n'avaient pas de motif stocké (Manus). Chaque absence porte son motif, tiré des registres | `chercheur-pieces` + `designer-vitrine` | 0 « — » sans motif |
| 2.5 Dénominateurs après opérations sur capital | CIH, CDM et tout titre ayant émis des actions après ses comptes : PER et P/B sur une base dite et cohérente | `verificateur-finance` | Décision D5 appliquée ; test par titre |
| 2.6 Médianes de secteur robustes | Un titre à une transaction (UNI : +27 % sur la médiane agroalimentaire) n'entre pas dans une médiane | `quant-backtest` | Règle de volume minimal, testée |
| 2.7 Comptes en attente | NRJ, STK, ENK (devise), dette nette contestée (ADI, MUT, VCNE, CMGP) : chaque cas soit résolu sur pièce, soit dit à l'écran avec sa cause | `chercheur-pieces` | Question écrite à la société quand la pièce ne suffit pas |

### Phase 3 — Une production qui ne lâche pas (axes 4 et 5)

| Lot | Contenu | Agent | Critère de fin |
|---|---|---|---|
| 3.1 État publié | Une page « État du service » : dernière collecte réussie, dernière clôture, tâches en retard, file des comptes | `operateur-production` (nouveau) | Visible depuis l'accueil |
| 3.2 Alerte réelle | Un échec de publication prévient en moins d'une heure (courriel GitHub + notification de la tâche planifiée) | `operateur-production` | Test d'alerte provoqué et reçu |
| 3.3 Pas d'écriture sans séance | Aucun commit de données un week-end ou un jour férié (Manus MJ-10) | `relecteur-pipeline` | Zéro commit de données hors séance sur 30 jours |
| 3.4 Exceptions avalées | Les `except` qui masquent une erreur de données deviennent visibles dans `_meta` ou dans le journal (Manus : 149 dans le moteur) | `ingenieur-tests` | Inventaire, puis 0 sur les chemins de données |
| 3.5 Trente jours sans échec | Le critère de succès du projet, mesuré par `verifier_seance` | `operateur-production` | Compteur publié sur la page d'état |

### Phase 4 — Hygiène juridique et vie privée (axe 7)

| Lot | Contenu | Qui | Critère de fin |
|---|---|---|---|
| 4.1 Purge des références git | Relance du support GitHub pour `refs/pull/8` et `/9` (message préparé) | **Abd Moutalib** | Réponse de GitHub ; vérification de l'inaccessibilité |
| 4.2 Pièces PDF hors du site public | Les 21 PDF suivis par git ne sont plus servis par Pages ; on garde lien, page et empreinte | `gardien-conformite` (nouveau) | 0 PDF servi par le site |
| 4.3 Mentions et sources | Page « Sources et conditions » : d'où vient chaque donnée, à quelle fréquence, avec quelles réserves ; mention de non-conseil lisible (pas 11 px) | `gardien-conformite` + `designer-vitrine` | Page en ligne |
| 4.4 Droit des données | Accord écrit avec CDG Capital Bourse / la Bourse de Casablanca avant toute monétisation | **Abd Moutalib** | Accord ou décision « usage personnel » |
| 4.5 CNDP | Dossier du traitement passé (corpus WhatsApp supprimé) | **Abd Moutalib**, préparé par `gardien-conformite` | Décision documentée |

### Phase 5 — Contrôle continu et re-audit

| Lot | Contenu | Agent | Critère de fin |
|---|---|---|---|
| 5.1 Auto-audit hebdomadaire | Chaque semaine : 15 titres tirés au sort recoupés sur pièce officielle, + 3 injections d'erreurs ; note sur les 7 axes | `auditeur-interne` (nouveau) | 4 semaines consécutives ≥ 9 en interne |
| 5.2 Re-audit externe | Même consigne qu'au 19/11, deux auditeurs | Abd Moutalib | ≥ 9,0 chez les deux |

## 4. Décisions

| # | Sujet | Choix retenu | Statut |
|---|---|---|---|
| D1 | Cours en séance | **Option A** : on les garde, dits « cours de séance, différé » ; la clôture reste la référence du bulletin | Délégué le 19/11 (« corrige ce qu'il faut ») — réversible |
| D2 | Mesure du score à l'écran | Lire l'artefact hebdomadaire, variante sans rentabilité, mention à côté | Délégué le 19/11 |
| D3 | PDF publiés | Retirés du site, lien + page + empreinte conservés | Délégué le 19/11 (archivés, pas supprimés) |
| D4 | AGM (PR #362) | Score 33,3 → 44,4 par une donnée relevée sur pièce (ROE 2025) | **R8 : accord explicite attendu** |
| D5 | P/B CIH, CDM | Pro forma (livre + produit de l'augmentation), étiqueté « calcul BVC Analyzer » | **Accord attendu** |
| D6 | PER NRJ | Publié avec la mention « dont 21,9 MDH exceptionnels » | **Accord attendu** |
| D7 | STK | PER refusé tant que la réserve chiffrée des CAC dépasse le bénéfice | Recommandé ; accord attendu |
| D8 | Dette nette contestée | Publier notre formule + le chiffre de la société, « définition non publiée » | **Accord attendu** (changement de règle) |

## 5. Ce qui tourne sans personne (cible)

| Quoi | Quand | Statut |
|---|---|---|
| Collecte des cours (moteur) | toutes les heures en séance + 15h45 + 18h | en place |
| Réveil des robots | 4 fois par jour ouvré | en place |
| Contrôle de séance (12 + contrôle arithmétique) | chaque soir | en place |
| Lecture des comptes déposés (PR, jamais de fusion) | 20h17 chaque jour ouvré | en place |
| Rédaction du briefing | 23h40 chaque jour ouvré | en place |
| **Collecte des publications AMMC + Bourse** | chaque matin ouvré | **à créer (lot 2.1)** |
| **Auto-audit** | chaque samedi | **à créer (lot 5.1)** |
| **État du service publié** | à chaque passage | **à créer (lot 3.1)** |

## 6. Ordre d'exécution

1. Phase 1 (lots 1.1 → 1.7) **et** lot 2.1 en parallèle : ce sont les deux
   demandes explicites (lecture simple ; collecte automatique).
2. Phase 3 (3.1 → 3.5).
3. Phase 2 restante.
4. Phase 4 (les lots « Abd Moutalib » se lancent dès maintenant, ils sont lents).
5. Phase 5.
