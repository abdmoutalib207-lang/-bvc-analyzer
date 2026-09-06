# Apprentissages durables — BVC Analyzer

> Ouvert le 28/08/2026. Ce que le projet a appris et qui ne doit pas se reperdre.
> À distinguer d'`ERRORS.md` : ici on note ce qui est VRAI, pas ce qui a raté.

---

## Sur le marché marocain

- **La BVC plafonne la variation à ±10 % par séance — SUR LE COURS D'UNE
  SOCIÉTÉ, pas sur l'indice** (R10). Toute variation calculée au-delà sur un
  titre est une erreur de données, jamais un mouvement réel. C'est un invariant
  réglementaire, donc un contrôle fiable et gratuit.
  - ⚠️ **Le MASI n'est pas soumis à ce plafond.** Précision d'Abd Moutalib le
    05/09/2026, après que j'aie justifié un contrôle sur l'indice « par R10 ».
    Le seuil de ±10 % sur l'indice reste défendable comme **borne dérivée** —
    une moyenne pondérée de titres chacun plafonné ne peut pas excéder le
    plafond — mais c'est une conséquence arithmétique, pas la règle, et elle
    tomberait si la composition changeait en séance.
  - **Leçon générale : ne pas invoquer une règle pour justifier un contrôle
    qu'elle ne couvre pas.** Le contrôle était bon, sa justification fausse ;
    c'est ainsi qu'un seuil finit par être appliqué là où il n'a pas de sens.
  - Amplitude réellement observée du MASI sur 185 séances (déc. 2025 →
    sept. 2026) : **-5,63 % le 03/03/2026, +4,46 % le 15/06/2026**.
- **Les jours fériés marocains sont en partie lunaires.** Le Mawlid n'a pas de
  date fixe et n'est confirmé par décret que peu de temps avant. **Ne jamais
  coder une liste de fériés complète** : elle vieillira sans prévenir. Seules
  les dates grégoriennes fixes sont dans `JOURS_FERIES_FIXES` ; le reste se
  déduit des données.
- **Une séance réelle ne reproduit jamais toutes les clôtures au centime près.**
  C'est le signal statistique le plus sûr dont dispose le projet : 71/71 un jour
  férié contre 6/44 un jour coté. La marge est telle qu'un seuil à 95 % ne peut
  pas se tromper de côté.
- **Beaucoup de titres sont très peu liquides** — quelques dizaines d'actions par
  séance. `chg=0` avec `vol>0` y est normal, pas suspect.

## Sur les sources

- ⚠️ **IDBourse peut rester bloquée sur la séance précédente pendant des
  heures.** Relevé le 31/08 par `veilleur-sources` : plus de deux heures après
  la clôture du lundi, ni `get_all_data` ni `masi-data` n'avaient une seule
  ligne datée du jour — 84 lignes sur 92 encore au vendredi. Le pipeline l'a
  correctement écartée (zéro ticker en source `idbourse` fraîche), mais la
  **capitalisation boursière** en dépend seule et se calcule alors sur le cours
  de la veille, sans drapeau propre pour le signaler.
- ⚠️ **CDG ne sert pas 80 titres sur 81 mais environ 65**, dont 63 avec un
  cours — chiffre stable sur quatre runs vérifiés du 27 au 31/08. La règle R3
  du CLAUDE.md annonce « 80/81 appariés » : c'est le taux d'APPARIEMENT du
  référentiel, pas la couverture d'une séance. Ne pas confondre les deux.

- **Aucune source n'est indépendante par défaut.** CDG et Wafabourse partagent
  l'éditeur `nt-soft.ma`, la convention de nommage et jusqu'à la faute de frappe
  « CoursDeReferance ». Leur accord ne prouve rien. BMCE (groupe Bank of Africa)
  est aujourd'hui la seule source techniquement distincte.
- **IDBourse est irremplaçable pour une seule raison** : elle est la seule à
  fournir la capitalisation boursière, absente des 26 champs de CDG.
- **Le contrôle d'accès d'IDBourse est un contrôle de provenance, pas d'IP.**
  Sans en-tête `Referer`, `/api/proxy/*` renvoie 403 depuis n'importe quelle
  machine. Un `curl` nu qui échoue ne prouve aucun blocage géographique.
- **Un navigateur ne peut pas envoyer de `Referer` choisi** — c'est un en-tête
  interdit au sens de la norme. Aucun proxy CORS public ne rétablira donc une
  couche temps réel ; seul un intermédiaire qu'on contrôle le pourrait.
- **95 % des prix viennent de sources qui cherchent à filtrer leurs appelants.**
  La fragilité est technique et contractuelle. Le vrai chantier stratégique est
  un accès légitime, pas une machine de collecte plus astucieuse.

### La BVC elle-même — `casablanca-bourse.com/market-data/cours` (04/09/2026)

Relevé sur la page officielle, imprimée depuis un poste marocain (le domaine
est injoignable depuis le conteneur : TLS coupé à la poignée de main, tunnel
fermé code 1006 — ce n'est pas testable d'ici, seulement de là-bas).

- **La BVC publie l'historique par instrument, gratuitement, sur 3 ans**, avec
  un bouton **« Télécharger les données (Excel) »**. Au-delà de 3 ans, il faut
  passer par l'offre Market Data payante (« Obtenir un devis »).
- ⚠️ **C'est une page par titre, pas un instantané du marché.** Elle ne
  remplace pas la chaîne de collecte : il faudrait 81 requêtes pour une séance.
  Sa valeur est celle d'un **juge de paix**, au même titre que le bulletin CDG,
  et avec une autorité supérieure — c'est l'opérateur du marché lui-même.
- **La BVC compte 81 actions.** Chiffre affiché sur la page, « Nombre total
  d'actions / Instruments disponibles ». Cela tranche l'hésitation 77/80/81 du
  projet **du côté du référentiel** : `TICKERS_ALL` (81) est le bon univers.
  Attention, cela ne dit rien de la couverture d'une séance donnée.
- **Elle ne liste que les séances où l'instrument a réellement coté.** Pour ADI
  du 01/08 au 04/09 : 19 séances, sans les 20, 21, 25 et 26/08. C'est
  exactement l'information qui manque au projet — « ce titre a-t-il coté ce
  jour-là ? » — et qu'on déduit aujourd'hui par des détours statistiques.
- **Recoupement du 04/09, ADI, 10 séances : 10 dates et 10 ouvertures
  identiques aux nôtres.** Aucune séance inventée, aucune manquante. C'est le
  premier contrôle de nos chandelles contre l'opérateur du marché lui-même.
  ⚠️ Et c'est ce même recoupement qui a révélé l'incohérence OHLC — cf.
  `ERRORS.md`, famille 7 : ce qu'on cherche à confirmer n'est pas toujours ce
  qu'on trouve.

## Sur l'infrastructure

- **Le déclencheur `schedule` de GitHub n'est pas un rendez-vous.** Mesuré :
  30 à 50 minutes de retard le 24/08, puis **2 à 8 heures** les 26–28/08 — le
  cron de 17h00 UTC parti à 01h12 le lendemain. Un produit dont la promesse est
  horaire ne peut pas reposer dessus seul.
  ⚠️ **Le 31/08, DEUX créneaux de journée n'ont pas été déclenchés du tout** —
  ni 08h40 ni 14h45 UTC. Ce n'est plus du retard, c'est une absence. Les deux
  séances ont dû être déclenchées à la main. Ne jamais supposer qu'un cron est
  parti : le vérifier.
- **Pour un bulletin J+1, l'échéance est 8h du matin, pas l'heure du cron.**
  Un run qui aboutit à 1h du matin publie à temps — c'est ce qu'a fait celui du
  samedi 00h47, tenant la promesse avec sept heures de retard. C'est ce constat
  qui justifie la redondance du soir (18h, 20h, 22h) plutôt qu'une course à la
  ponctualité qu'on ne gagnera pas.
- ⚠️ **Une alarme attachée à un run ne peut pas s'alarmer d'une absence de run.**
  `verifier_seance` est solide quand il tourne, mais il ne tourne que si un run
  part. Le jour où rien ne part, rien ne prévient. Le seul remède est un
  observateur EXTÉRIEUR à la plateforme d'exécution.
- **Le quota de publication de GitHub Pages est la ressource rare du projet**,
  environ 10 reconstructions par heure. Chaque commit le consomme. Un contrôle
  qui commiterait chaque jour consommerait ce qu'il protège.
- **Casablanca est à UTC+1 toute l'année.** `datetime.now()` sur un runner GitHub
  donne l'heure UTC : l'étiqueter `+01:00` produit une heure fausse en permanence.

## Preuves de justesse — recoupements au bulletin CDG

- **Séance du 31/08/2026 : 70 titres comparés, ZÉRO écart.** Pas « inférieur à
  0,1 % » — exactement 0,000 % sur chaque titre. Premier recoupement complet
  d'une séance produite par la chaîne à trois sources (CDG 63 + BMCE 10 +
  IDBourse 6), et par un moteur refactoré trois fois dans la journée.
  Les 19 titres du MASI 1 sont couverts : 18 ont coté et concordent, CMT n'a pas
  coté — ce que nos données disaient déjà (`stale`, source `candles`).
  Les 11 titres non comparés affichent tous `cours = 0.0` au bulletin : ils
  n'ont pas coté. Ce n'est pas un trou de couverture, c'est le marché.
- ⚠️ **Le bulletin « Indices » ne contient PAS la valeur des indices** — malgré
  son titre. C'est un tableau par instrument. L'indice MASI n'est donc pas
  vérifiable par cette pièce ; il faut une autre source pour le recouper.
- ⚠️ Rappel confirmé une fois de plus : le titre du bulletin porte la date de
  **publication**. « Indices du mardi 1er septembre » contient la séance du
  lundi 31 août.

### Maroclear — le dépositaire central, et notre meilleur référentiel d'ISIN

Relevé le **05/09/2026** sur `maroclear.com/fr/data-services/referentiel/valeurs`
(classe E, type S, statut ACTIVE), 81 valeurs, apporté par Abd Moutalib.

- ⚠️ **Passer par `IDB_TICKER_MAP` avant toute comparaison.** Les codes de
  Maroclear sont ceux de la BVC : leur `SNA` est **Stokvis**, pas Sonasid.
  Sans traduction, la comparaison est fausse sur une dizaine de titres.
- **78 de nos 80 ISIN concordent**, et **les 15 corrections accumulées depuis
  juillet sont TOUTES confirmées** — RIS, RDS, SMI, SRM, STR, SAF, SLM, NEJ,
  S2M, SNP, TMA, TQA, ZLD, STK, MNG post-split, et **MRL**, celui qui avait
  été tranché par l'arithmétique le 01/09 sans confirmation extérieure. La
  méthode du recoupement par le calcul est validée après coup.
- **`TIM` est radié.** Ni le symbole ni son ISIN `MA0000011686` n'apparaissent
  au référentiel des valeurs actives. Le doute datait du 02/07 ; il est levé.
- ⚠️ **Deux écarts restent ouverts** — `CFGB` (nous `MA0000012627`, Maroclear
  `MA0000011983`) et `SOT` (nous `MA0000012833`, Maroclear `MA0000012502`).
  Le cas SOT est le plus suspect : notre ISIN était déjà « introuvable dans le
  référentiel Médias24 » au 02/07. Deux sources indépendantes ne le trouvent
  donc pas. **Non corrigés — R2 exige l'accord explicite d'Abd Moutalib.**
- ⚠️ **`SAM` (SAMIR) est listé ACTIF chez Maroclear**, alors que la règle 4 du
  CLAUDE.md le dit radié/suspendu. Statut de dépositaire ≠ statut de cotation :
  un titre peut exister sans coter. Ne pas en conclure qu'il faut le réintégrer.
- Un ISIN faux ne corrompt plus les **prix** depuis que CDG et BMCE apparient
  par code et par nom — mais il corrompt tout ce qui est indexé par ISIN.
  SOT cotait 377 DH le 04/09, dans sa fourchette de référence, malgré un ISIN
  probablement erroné : **une donnée juste ne prouve pas que la clé est bonne.**

- **Pour valider une identité, chercher un recoupement ARITHMÉTIQUE, pas un
  second avis.** L'ISIN de Maroc Leasing est resté douteux deux mois parce qu'on
  cherchait une source qui le confirme. Ce qui a tranché le 01/09 n'est pas le
  code lu sur une fiche, c'est que `capital social ÷ valeur nominale` donne un
  nombre de titres qui, divisant la capitalisation publiée, redonne exactement
  notre cours. Deux sources peuvent se tromper ensemble — un calcul qui boucle,
  non. Réutiliser cette méthode pour TIM, seul ISIN encore non résolu.

## Sur la conception du produit

- **L'honnêteté est la fonctionnalité.** Le bloc `_meta`, l'indicateur de
  confiance 0–5 et le refus d'émettre un signal sous confiance ≤ 1 constituent le
  vrai avantage concurrentiel — pas le scoring lui-même.
- **Une alarme toujours allumée n'alerte plus.** Tout contrôle doit être conçu
  pour être vert en fonctionnement normal, sinon il sera ignoré puis désactivé.
- **Un contrôle doit se déduire des données, pas d'un calendrier écrit à la
  main** — c'est ce qui le rend durable.
- **Une identité fausse est pire qu'une identité manquante.** Mieux vaut un titre
  non apparié qu'un titre apparié à la mauvaise société.

## Sur la méthode de travail

- **Petits pas vérifiés** (R7) : dix améliorations mesurées valent mieux qu'une
  refonte risquée.
- **Archiver plutôt que supprimer** (dossier `archive/`).
- **Ne jamais commiter un `data.json` produit localement** si celui de production
  est plus riche : BMCE n'est pas joignable depuis un conteneur Claude, et le run
  local couvre donc moins de titres. C'est une régression R1 déguisée en mise à
  jour.
- **Extraire avant de tester.** La logique enfouie dans `run()` (768 lignes,
  126 variables locales) n'est pas testable ; sortie en fonction nommée, elle se
  vérifie en une seconde. Le cliquet de séance et l'arbitrage MASI l'ont prouvé
  le 28/08.

## Sur le corpus WhatsApp (02/09/2026)

- **Un filtre de bruit se justifie par une mesure, jamais par l'intuition.**
  Le hors-sujet football semblait un nettoyage évident. Mesuré : 3 953 messages
  de football dans 919 372, mais seulement **111 mentionnent aussi un ticker**
  — 0,23 % du corpus réellement scoré. Le filtre est juste, il ne change
  presque rien. L'écrire était bon marché ; en attendre un effet visible aurait
  été une erreur.
- **⚠️ Le danger d'un filtre n'est pas ce qu'il laisse passer, c'est ce qu'il
  détruit.** Les mots « évidents » sont des pièges mesurés : « but » est à
  97 % « dans le but de », « transfert » à 99 % un virement bancaire, « match »
  à 92 % « ça match avec ». Les inclure aurait supprimé ~2 900 messages pour
  n'écarter que ~150 de football : **19 messages financiers détruits par
  message de foot**. `TERMES_ECARTES_A_DESSEIN` et son test figent ce constat.
- **Vérifier les collisions de sigles avant d'écrire un filtre par mots-clés.**
  Les clubs marocains portent des sigles (RCA, WAC, MAS, FAR, FUS, RSB) qui
  auraient pu heurter un ticker BVC. Vérifié sur les 110 sigles connus : aucune
  collision. La vérification a coûté une minute ; la collision aurait coûté un
  titre entier.
- **Un drapeau posé et jamais lu ne protège rien.** `is_spam` est calculé par
  `phase1_parser` depuis l'origine et **consommé nulle part**. Le filtre
  hors-sujet est donc appliqué dans `_explode_tickers` — le passage obligé de
  toute métrique par titre — et non en phase 1 où il aurait été décoratif.
  Même défaut que le drapeau `suspect` ignoré par son appelant (28/08).
- **Seuls 48 832 messages sur 919 372 mentionnent un ticker** (5,3 %), et
  67 titres seulement sont cités. C'est le vrai plafond du pilier NLP : le
  corpus est vaste, la matière exploitable l'est beaucoup moins.

## ⚠️ Données personnelles dans le dépôt public (02/09/2026)

- **Le dépôt est PUBLIC et contient les noms de 2 013 personnes.**
  `whatsapp_analysis/output/smart_money_ranking.csv` et `network_metrics.csv`
  sont versionnés depuis le 5 juin 2026 et portent les noms WhatsApp réels des
  membres du groupe, associés à un jugement de compétence (taux de réussite,
  alpha, régularité) et à leur influence dans le réseau. **Deux entrées sont
  des numéros de téléphone en clair.**
- Ces personnes n'ont pas consenti à ce traitement. Sur le plan légal c'est un
  traitement de données personnelles non déclaré (CNDP) ; sur le plan pratique
  c'est ce qui fait perdre l'accès au groupe le jour où quelqu'un le découvre —
  et le groupe est la seule source du pilier NLP.
- **Règle désormais : aucun nom, numéro ou identifiant direct ne doit atteindre
  un fichier du dépôt.** Les sorties NLP doivent être pseudonymisées (`M0417`)
  avant tout commit. La table de correspondance reste hors dépôt. Le moteur n'a
  besoin que de la performance d'un membre, jamais de son identité.
- ⚠️ Retirer les noms des fichiers ne suffit pas : ils restent dans l'historique
  git. Un effacement réel demande une réécriture d'historique.

## Sur le filtrage du corpus (02/09/2026)

- **Décision du product owner : aucun filtre thématique.** Le filtre football
  écrit puis retiré le même jour. La mesure qui l'avait motivé reste valable et
  documentée plus haut ; c'est le choix produit qui a tranché, pas la mesure.
  Ne pas le réintroduire sans instruction explicite.

## Sur la lecture des drapeaux « périmé » (02/09/2026)

- **Dix titres périmés un soir n'est pas une anomalie.** Vérifié le 02/09 :
  sept portaient un volume identique AU TITRE PRÈS à celui de la veille, pour
  une clôture identique (MRL 15 titres à 389,55 deux jours de suite, UNI 200 à
  173,00). La source rejoue sa séance précédente ; `_est_rediffusion` les
  attrape correctement. Les trois autres ont `vol=0` — R9 littérale.
- **⚠️ Ne pas conclure d'un `prix_asof` daté du jour que le cours est frais.**
  C'est la date que la SOURCE annonce, pas la preuve d'une cotation. Neuf des
  dix périmés du 02/09 portaient la date du jour. Le volume est le juge, pas
  la date.
- **⚠️ Un titre MASI 1 périmé n'est pas forcément une régression R1.** CMT
  affichait `vol=0` le 02/09 : il n'a réellement pas coté. C'est un fait de
  marché, pas une défaillance de collecte. R1 exige que le titre reste
  accessible et renseigné — il l'était.
- **Ne pas prendre le diagnostic d'une autre session pour argent comptant.**
  Une session lancée sur une copie locale a signalé « DLM et DIS absents de
  bvc_config.py, à documenter ». Les deux y sont, avec ISIN et raison sociale
  (Delattre Levivier Maroc, Diac Salaf). Vérifier avant d'agir.

## Le fil de discussion vaut douze fois la mention (03/09/2026)

**Idée d'Abd Moutalib, mesurée et confirmée.** Compter les messages qui
*contiennent* le code d'un titre sous-estime la matière d'un facteur douze.
Quand quelqu'un écrit « ADI ? », les quinze messages suivants parlent d'ADI
sans jamais le nommer — un lecteur humain suit le fil, notre compteur le
jetait.

Mesure sur les 919 372 messages, fil suivi tant que l'écart entre deux
messages reste sous 10 minutes et qu'aucun autre titre n'est cité :

    messages exploitables      48 832  →  591 430     (×12,1)
    part du corpus utilisée       5 %  →      64 %
    taille médiane d'un fil                11 messages

Et surtout, le chiffre qui décidait de tout :

    titre    mentions/jour        fil/jour
    ADI            4          →      49
    RDS            4          →      58
    ADH            3          →      35

    titres avec ≥10 messages/jour :  0  →  15
    (ADH ADI ATW CIH CMT HPS IAM JET MDP MNG MSA RDS SMI SNA TGCC)

**Conséquence : un sentiment quotidien par titre est possible sur 15 valeurs.**
La conclusion inverse, tirée le 02/09, reposait sur un comptage littéral et
était fausse.

⚠️ **C'est une heuristique, pas une vérité.** Un fil peut dériver sans citer
d'autre titre, et le seuil de 10 minutes est arbitraire (30 min donne ×15,1).
À valider en relisant des blocs à l'œil avant d'en faire un signal publié.

⚠️ **Leçon de méthode** : une mesure qui contredit l'intuition du propriétaire
du produit doit être suspectée AVANT d'être opposée. Il connaît son corpus ;
ici il savait comment se lit une discussion, et le compteur ne le savait pas.

## Sur les données personnelles (03/09/2026)

- **Un jeu de test ne porte jamais l'identité d'une personne réelle.** Inventer
  un nom coûte trois secondes ; le retirer de 106 commits a coûté une journée.
- **Un commentaire qui explique comment on protège quelqu'un ne le nomme pas.**
- **⚠️ Vérifier le RÉSULTAT, jamais le message de l'outil.** `git filter-repo`
  a annoncé « Completely finished » deux fois de suite sans avoir nettoyé quoi
  que ce soit. Seule la relecture du dépôt réécrit l'a montré.
- **Supprimer un fichier ne l'efface pas de git.** Cela ajoute un commit qui
  dit « ce fichier n'existe plus » ; toutes les versions passées restent
  lisibles en deux clics. C'est la question qu'a posée Abd Moutalib, et c'est
  le piège central de git.
- **Après une réécriture d'historique, contrôler TROIS endroits distincts** :
  les branches, les tags, les références de pull requests. Un seul oublié
  maintient tout le reste en vie — le tag `v1.0-data` retenait 164 commits.
- **Purger un fichier vaut mieux que le réécrire ligne à ligne**, quand c'est
  une sortie régénérable : 21 secondes contre 75 minutes, et le résultat est
  total au lieu d'être approché.
- **Ne pas confondre « introuvable » et « effacé ».** Après réparation, un
  clone normal ne donne rien — mais les objets existent encore. Le dire
  autrement serait mentir au propriétaire.
