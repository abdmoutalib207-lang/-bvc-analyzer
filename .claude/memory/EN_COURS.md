# En cours

## ⚠️ EN ATTENTE — ne pas oublier

**Demande à GitHub Support** : purger `refs/pull/8/head` et
`refs/pull/9/head`, qui exposent encore 2 013 personnes et 588 numéros de
téléphone (catégorie « Removing sensitive data »). Tout le reste est
nettoyé. Détail : `.claude/memory/INCIDENT_VIE_PRIVEE.md`.

⚠️ **Ne pas rouvrir de pull request depuis une branche portant l'ancien
historique** — cela recréerait une référence exposée.

# En cours — à lire au démarrage de chaque session

> Mis à jour le **31/08/2026, 20h00 Casablanca** (lundi soir, après clôture).
> Ce fichier est court par construction. Ce qui est terminé en sort et va dans
> le journal du CLAUDE.md ; ce qui est appris va dans LEARNINGS.md.

---

## ⚠️ EN ATTENTE — le jeton du déclencheur externe

**Date d'expiration à noter ici dès la création du jeton fine-grained**, avec
un rappel un mois avant.

Le jour où il expire, le déclenchement cesse **sans bruit** : cron-job.org
reçoit un `401`, GitHub ne lance rien, le bulletin porte la veille. C'est la
panne du 23/09 à nouveau, mais silencieuse.

Parade indispensable : activer les **notifications d'échec** de cron-job.org.
C'est la seule alerte qui vienne du bon côté — elle part même si GitHub ne
fait rien. Procédure complète : `docs/DECLENCHEUR_EXTERNE.md`.

  - [ ] jeton créé le ………, expire le ………
  - [ ] tâche « run de clôture » — `45 15 * * 1-5` UTC
  - [ ] tâche « contrôle de séance » — `30 18 * * 1-5` UTC
  - [ ] notifications d'échec activées
  - [ ] premier déclenchement vérifié dans l'onglet Actions

---

## ⚠️ EN ATTENTE — le jeton du déclencheur externe

**Date d'expiration à noter ici dès la création du jeton**, avec un rappel un
mois avant.

Le jour où il expire, tout s'arrête **sans bruit** : Cloudflare reçoit un
`401`, GitHub ne lance rien, et — c'est le pire — **l'alerte ne peut pas être
ouverte non plus, puisqu'elle passe par le même jeton**. La panne du 23/09
reviendrait, silencieuse.

Procédure complète : `declencheur/README.md`.

  - [ ] jeton créé le ………, **expire le ………**
  - [ ] secret `GITHUB_TOKEN` posé dans Cloudflare (type *Secret*, pas *Text*)
  - [ ] cron `45 15 * * 1-5` — déclenche le run de clôture
  - [ ] cron `50 15 * * 1-5` — vérifie qu'il est parti, alerte sinon
  - [ ] premier déclenchement vu dans l'onglet Actions

⚠️ Les crons GitHub sont **gardés tels quels**, et ce n'est pas de la
négligence : peu fiables, mais indépendants du jeton et de Cloudflare. Deux
mécanismes qui ne tombent pas ensemble valent mieux qu'un seul, meilleur.

---

## État au 23/09/2026 — ce qui vient d'être fait, et ce qui reste

> Objectif donné par Abd Moutalib : **un moteur stable, sans erreur dans le
> passé, et qu'on n'y revienne plus.** Traité par priorité.

### ✅ L'heure — le Maroc est passé à UTC+0 le 20/09 (PR #74, fusionnée)

Le cron « 15h45 » tombait à **14h45 locales, 45 min AVANT la clôture** : il
aurait figé la séance comme le 21/09. `DECALAGES_MAROC` dans `bvc_config.py`
porte désormais chaque décret avec sa source, entrées Ramadan comprises —
sans elles la même panne revient chaque année.

⚠️ **J'avais inscrit l'erreur moi-même la veille** : deux tests échouaient en
CI avec une heure d'écart, j'en ai conclu que le runner avait une base de
fuseaux périmée et j'ai forcé UTC+1 en dur. Le runner était à jour, moi non.

### ✅ Le volume n'était pas un volume (PR #75)

Trois défauts, pas un — voir ERRORS.md famille 18 :
13 636 volumes en dirhams · 3 019 volumes valant le COURS · **534 clôtures
fausses** (18/06→06/08, R1) · 842 séances absentes.

- **La cause est fermée** : `pipeline/volume_titres.py`, branché aux quatre
  points d'appel, dont un que mon relevé manuel avait oublié et que le test a
  trouvé.
- **18 séries reprises** sur l'export de l'opérateur (lots 1 et 2).

### ✅ Aussi fait le 23/09

- **Les 27 exports sont tous instruits** (#75, #76) : 39 titres sur 80 sourcés
  sur l'opérateur, 0 sur les quatre défauts.
- **Le run de clôture du 23/09 manquait** (#77) — réparé, recoupé au bulletin :
  **0 écart sur 66**, verdict CONCORDANCE, 13 contrôles sur 13.
- **La bougie fantôme du 30/07 a disparu des 34 titres** (#78, #79), registre
  `SEANCES_SANS_COTATION` + 36 instructions + garde armée.
- **Une PR de pures données ne lançait aucun test** (#76) — le garde-fou
  d'opération de masse ne s'armait pas sur une livraison de séries.

### ⏳ Ce qui reste, dans l'ordre

1. **41 exports à recevoir**, dont **16 MASI 1** — liste et codes de
   téléchargement dans
   `datasets/historiques_candidats/EXPORTS_27/RESTE_A_RECEVOIR.md`.
   ⚠️ Quatre demandent une décision AVANT import : **MNG** (split 10:1 —
   l'export est-il rétro-ajusté ?), **CMT** (reprise après OPA — R11 interdit
   le rétro-ajustement), **CMGP** et **CFGB** (corrections reçues qu'un
   `--complet` aveugle annulerait).
   ⚠️ **HPS** porte la rupture du 06/10/2023 (ratio 0,103) ouverte depuis le
   01/08 : l'export permettra de la constater sur pièce.
2. ⚠️ **Le créneau de 15h45 est un point unique de défaillance — démontré le
   23/09.** Il a sauté, et le terminal a publié des cours de 15h08 pendant une
   heure. Personne ne l'aurait su avant le contrôle de 19h32, soit quatre
   heures après. Aucun correctif de code n'y peut rien : il faut un
   déclencheur externe appelant l'API GitHub. **Décision à prendre.**
3. **655 bougies OHLC incohérentes dans le cache** — voir plus bas ; à
   reprendre à la lumière des séries réimportées, une partie peut avoir
   disparu.
4. **Fondamentaux** : 51/80 sans P/B, saisie manuelle de juin.

### ⚠️ Trois leçons de méthode du 23/09, à ne pas reperdre

- **On branche une garde quand le terrain est nettoyé.** Branchée au premier
  lot, elle purge tout au premier run et rend le découpage illusoire
  (ERRORS famille 20).
- **La suite locale ne lance pas `update_data.py`.** Certains défauts
  n'apparaissent qu'à l'étape CI qui le lance pour de vrai.
- **Un contrôle qui refuse dit souvent ce qu'il faut faire.** Deux fois ce
  jour-là : « écrire l'instruction qui manquait » plutôt qu'élargir
  l'exception, et découper la livraison plutôt que desserrer le seuil.

## 🔔 EN ATTENTE DE FUSION — PR #63, le moteur (19/09/2026)

- [ ] **`fix/bougie-rattrapage-seance-echue` — CI verte, non fusionnée.**
  Le moteur publie de nouveau `data.json` (séance du 18/09, 79 titres) depuis
  le 19/09 15h04, mais **les chandelles s'arrêtent au 16/09**. La PR ouvre la
  porte de rattrapage, crée l'entrée de cache manquante de T2S, et répare deux
  tests qui auraient rebloqué la publication lundi.
  - ⚠️ **Sans cette fusion, la séance du 18/09 reste sans bougie**, et le
    contrôle quotidien continue d'échouer chaque soir.
  - Mesuré : 65 tickers rattrapés, invariant OHLC intact, R10 respectée,
    second run idempotent au bit près, `verifier_seance.py` 12/12.

- [ ] **Recoupement du 18/09 au bulletin CDG — non fait.** Les bulletins sont
  déposés à la main ; le dernier sur disque est celui du 16/09. Les clôtures
  concordent avec les prix publiés, mais **le juge de paix externe n'a pas
  parlé**. Déposer le PDF dans `pipeline/bulletins/` puis
  `python pipeline/parse_cdg_bulletin.py <pdf> --verifier 2026-09-18`.

- [ ] **655 bougies OHLC incohérentes dans le cache, 11 titres, 8 MASI 1.**
  Les fichiers de chandelles sont sains ; c'est `historical_data.json` qui n'a
  jamais été re-dérivé après la réparation du 04/09. SGTM affiche un plus-bas
  52 semaines de 508,10 au lieu de 461,95.
  ⚠️ CFGB et CMGP portent des corrections réceptionnées — un `--complet`
  aveugle les annulerait (piège SOT). Passer par `gardien-donnees`.

- [ ] **PR #62 — sa prémisse est inversée.** Elle rattrapait `data.json` depuis
  les chandelles ; depuis le run du 19/09, c'est `data.json` qui est frais et
  les chandelles qui retardent. 81 fichiers, +5 118/−4 013 : la fusionner
  telle quelle ferait reculer `data.json`. À relire avant toute décision.

---

## ✅ MOTEUR REMIS EN MARCHE — 22/09/2026

- [x] **Séance du 21/09 réparée** depuis le bulletin CDG : 56 bougies
  complétées, 8 ajoutées, **68/68 conformes**. Le moteur republie (PR #66).
- [x] **T2S ne disparaîtra plus du cache** — `conserver_orphelins()` + un
  invariant du dépôt qui rouge si une série exploitable perd son entrée.
- [ ] ⚠️ **Le cron reste le premier risque.** Le 21/09 comme le 18/09, la
  séance a été perdue parce que les runs d'après-clôture ont échoué ET que
  personne ne regardait. Le rattrapage existe désormais (bougie manquante ET
  bougie figée), mais il faut toujours un bulletin déposé à la main.
- [ ] **655 bougies OHLC incohérentes dans le cache**, 11 titres dont 8 MASI 1
  — toujours ouvert, voir le bloc ci-dessous.

---

## 🔔 UNE DÉCISION À PRENDRE — reprise de cotation CMT (16/09/2026)

- [ ] **Le registre porte une référence CALCULÉE là où une SOURCÉE existe.**
  `SUSPENSIONS["CMT"][0]["reference_impliquee"]` vaut **2 216,97**, obtenu en
  divisant le cours de reprise du bulletin par sa variation (2 438 ÷ 1,0997).
  La décision AMMC du 15/09, désormais archivée dans `datasets/pieces_ammc/`,
  établit le prix de l'offre à **2 217 MAD exactement**.
  - **La variation publiée est identique** dans les deux cas : +9,97 %. Ce
    changement ne déplacerait aucun chiffre à l'écran.
  - Mais un nombre déduit d'un bulletin n'a pas le même statut qu'un nombre lu
    dans une décision du régulateur. C'est la différence entre « nous pensons »
    et « l'AMMC a fixé ».
  - ⚠️ **Non appliqué** : Abd Moutalib a demandé le 16/09 de ne pas toucher au
    moteur dans ce lot. La correction tient en une ligne de `bvc_config.py` et
    attend son accord.

---

## 🔔 UNE DÉCISION À PRENDRE — la séance fantôme du 30/07/2026

- [ ] **Soixante-sept titres portent une bougie un jour où la Bourse était
  fermée.** Le 30 juillet est la Fête du Trône, et `(7, 30)` figure dans
  `JOURS_FERIES_FIXES` depuis toujours. L'export 3 ans de l'opérateur le
  confirme sans ambiguïté : il liste TOUTES les séances réelles — Dari Couspate
  y figure 629 fois sans le moindre échange — et omet exactement les fériés
  (30/07, 14/08, 20/08, 21/08, 01/05, 11/01).
  - **Pourquoi le garde-fou ne l'a pas vu** : `purger_seance_fantome` juge sur
    une signature statistique — au moins 95 % de clôtures identiques à la
    veille. Seules 26 des 72 bougies du 30/07 recopiaient la veille. Le seuil
    n'a pas été atteint, et la liste de fériés que le projet POSSÈDE n'a jamais
    été confrontée aux chandelles écrites.
  - **Ce qui est déjà fait** : les 5 titres importés le 16/09 (AKD, HAL, MUT,
    TMA, TQA) en sont purgés — leur série est exactement celle de l'opérateur —
    et `tests/test_historiques_importes.py` interdit désormais toute bougie sur
    un férié à date fixe, pour ces cinq titres.
  - **Ce qui reste** : 67 séries. Les purger est une modification de données sur
    67 titres, hors du périmètre d'un import d'historique. ⚠️ **Non appliqué,
    en attente d'arbitrage.**
  - Le correctif durable serait de brancher `JOURS_FERIES_FIXES` sur le
    balayage de `pipeline/seance.py`, à côté de la signature statistique qui,
    elle, attrape les fériés lunaires.

---

## 🔴 LA SOURCE D'HISTORIQUE AUTOMATIQUE EST MORTE (constaté le 17/09/2026)

- [ ] **`BVCscrap` n'interroge pas la Bourse de Casablanca : il interroge
  `medias24.com`**, qui répond **HTTP 403 derrière Cloudflare**. Vérifié en
  direct : `getPriceHistory` et `getMasiHistory` renvoient tous deux la page
  « Just a moment… ».
  - **Conséquence** : seuls les titres pour lesquels Abd Moutalib fournit un
    export Excel ont un historique long. 44 en ont un ; **28 titres sont sous un
    an et 6 n'ont aucune bougie**.
  - **Ce n'est pas une perte** : l'historique git montre une progression
    monotone (CIM : 19 → 41 → 63 → 79). Ces séries sont NÉES courtes le
    10/06/2026 et grossissent d'une séance par jour.
  - ⚠️ **Le workflow `fetch_historical_data` tourne chaque jour ouvré et sortait
    VERT en ne rapatriant rien** — `except ImportError` journalisait
    « BVCscrap non disponible » et continuait. Depuis le 15/09 il échouait
    franchement sur `KeyError: 'refus'` (corrigé le 17/09).
  - **À trancher** : chercher une source d'historique qui tienne (API officielle
    BVC ? accord IDBourse ?), ou assumer que l'historique entre à la main.

---

## 🔔 DETTE CONNUE — anomalies sans source (17/09/2026)

- [ ] **Sept variations hors plafond restent dans les séries publiées**, sur des
  titres sans export Excel : FNB (04/08), IBM (16/07, 29/07, 30/07),
  REB (04/08), ZLD (03/08). Ce sont des bougies à volume nul dont la valeur
  saute. **Aucune source ne peut les corriger** — ni export, ni bulletin
  archivé (les bulletins ne remontent qu'à septembre).
  - ⚠️ **Ne pas les retirer à l'aveugle.** Contrairement à ATL et MRL, rien ne
    prouve qu'elles appartiennent à un autre émetteur : elles sont seulement
    invraisemblables. `datasets/seances_retirees/` exige la preuve, pas le
    soupçon.
  - Elles disparaîtront le jour où ces titres recevront un export 3 ans.

---

## 🔔 ATTENDU DE ABD MOUTALIB

- [ ] **Les trois secrets du bulletin par courriel — ⚠️ LE BULLETIN N'EST
  JAMAIS PARTI.** Relevé le 16/09 : **20 exécutions depuis le 02/09, 20 échecs,
  zéro envoi**. Le bulletin se compose parfaitement à chaque fois ; seul
  l'envoi manque, faute de configuration.
  - À poser dans **Settings → Secrets and variables → Actions → New repository
    secret** :
    `MAIL_TO` (l'adresse destinataire) · `MAIL_USERNAME` (l'adresse Gmail
    expéditrice) · `MAIL_PASSWORD` (un **mot de passe d'application** Google,
    pas le mot de passe du compte).
  - ⚠️ **Ne jamais demander ces valeurs ni les faire transiter par le fil de
    discussion.** Elles se posent directement dans GitHub.
  - Depuis le 16/09, l'absence de configuration ne fait PLUS échouer le
    workflow : elle produisait deux courriels d'alerte par matinée sans rien
    réparer, et noyait les vrais échecs. Le job se termine vert et l'explique
    dans son résumé. **Conséquence : plus rien ne le rappellera tout seul —
    c'est cette ligne-ci qui s'en charge.**

- [ ] **Les 31 exports Excel d'historique** — `data/historique/`. La
  profondeur de nos chandelles est exactement celle de ces exports : 31 titres
  en ont trois ans, 31 autres n'en ont aucun et commencent le jour où la
  collecte a démarré. Liste exacte : `python pipeline/profondeur_historique.py
  --manquants`. Les plus utiles d'abord : CIM, AKD, MUT, SNA, TQA, WAF, TMA,
  STK, DAR, STR.

- [ ] **Corpus WhatsApp à jour — ⚠️ ÉCHÉANCE DÉPASSÉE.**
  Annoncé le 28/08 au soir pour « demain », soit le samedi 29/08. Non reçu à ce
  jour. **Le lui rappeler dès le premier échange**, sans insister : c'est un
  week-end, et rien ne bloque tant que l'étape 2 n'a pas commencé.
  - Destination : `whatsapp_analysis/` — les sorties actuelles datent du
    **04/08/2026**, soit 24 jours de retard.
  - Dès réception, passer la main à l'agent `analyste-nlp`.
  - ⚠️ **Pseudonymiser les participants avant tout traitement publié** (CNDP).
    Aucun nom, numéro ou identifiant direct ne doit atteindre un fichier du
    dépôt.
  - Il a aussi évoqué de produire des fenêtres glissantes **3 mois et 6 mois**
    en plus de l'historique complet.

---

## ⚠️ LE DÉCLENCHEMENT — le point faible du produit

- [x] **Le réveil externe se déclenche mais n'agit pas.** Constaté le 31/08 :
  la routine a bien démarré à 9h45, une session a été créée, et **rien ne s'est
  passé**. Cause : son message lui demandait d'utiliser les outils GitHub MCP,
  qu'elle n'a pas, tout en lui interdisant de commiter — elle n'avait donc ni
  moyen d'agir, ni droit d'agir autrement. Silence total, aucune notification.
  - **Correctif remis à Abd Moutalib** : un texte de remplacement à coller dans
    la routine (claude.ai → Routines → « BVC — réveil des robots »), qui ajoute
    une voie B autonome — faire tourner le pipeline soi-même et pousser, avec
    l'autorisation explicite de commiter dans ce cas.
  - ✅ **VÉRIFIÉ le 31/08 à 19h56**, la session déclenchée a rendu son rapport :
    elle a bien une copie du dépôt (clone git) mais **en LECTURE SEULE**.
    `GITHUB_TOKEN` répond 403 « GitHub access to this repository is not enabled
    for this session. Use add_repo to request access with push », aucun outil
    MCP GitHub n'est chargé, et `gh` n'est pas installé.
  - ⚠️ **Ma voie B était donc fausse elle aussi** : elle se terminait par un
    `git push` que la session ne peut pas faire. Le texte de remplacement doit
    commencer par un appel à **`add_repo` avec `access: "push"`**, sans quoi
    aucune des deux voies ne fonctionne.

- ✅ **La redondance du soir a fonctionné dès le premier soir.** Deux runs
  `schedule` le 31/08 — 16h22 et 17h57 UTC — après que les créneaux de 08h40 et
  14h45 aient été sautés. Résultat : **79 titres sur 81 à la séance du jour**,
  publiés sans intervention. La promesse J+1 est tenue pour demain matin.

- ⚠️ **Attention aux inférences causales sur les titres en retard.** Le réveil
  a rapporté « 16 titres bloqués au 28/08, correspond exactement aux 3 jours de
  panne du schedule ». C'était FAUX : ces titres attendaient simplement
  qu'IDBourse rattrape le week-end, comme `veilleur-sources` l'avait diagnostiqué
  à 17h33. IDBourse a rattrapé vers 18h et ils sont passés à 79/81. Un chiffre
  juste peut porter une explication fausse.

- [x] **Redondance du soir posée le 31/08** (dans `update_bvc.yml`).
  Trois créneaux — 18h, 20h, 22h — au lieu d'un. L'observation qui la justifie :
  pour un bulletin J+1, l'échéance est **8h du matin, pas 18h**. Un run qui
  aboutit à 1h du matin publie à temps. Le cron de vendredi 17h UTC est parti
  samedi à 00h47 : il a tenu la promesse malgré 7h de retard.
  Coût nul — un run sans changement de fichier ne commite pas.

- ⚠️ **Le décalage de GitHub n'est plus de 30–50 min mais de 2 à 8 HEURES**, et
  certains crons ne partent pas du tout (lundi 31/08, 08h40 UTC : jamais parti).
  Ne plus se fier à l'heure inscrite dans un cron.

- ⚠️ **La promesse J+1 a été TENUE lundi matin** malgré tout : à 8h, le terminal
  affichait la clôture de vendredi, correctement datée. Ce qui a manqué est le
  rafraîchissement intraday, qui est un confort. Ne pas confondre les deux —
  c'est une erreur d'appréciation commise le 31/08.

## 📋 FEUILLE DE ROUTE — 8 semaines vers un produit stable

L'ordre est délibéré. Ne pas le réordonner sans raison écrite.

1. ~~**Filet de tests**~~ — ✅ **fait le 30/08**. 69 tests, 7 fichiers, moins
   d'une seconde, CI verte au premier run. Trois défauts trouvés en l'écrivant,
   dont un vrai bug (`est_ferie_fixe(None)` levait TypeError).
   ⚠️ Reste découvert et écrit dans `tests/README.md` : la fusion des sources,
   cœur de R3, **n'est pas testable tant qu'elle vit dans `run()`**. C'est
   l'argument de l'étape 5.
2. **Réveiller le NLP** (`analyste-nlp`) — 1 semaine. ← **prochaine étape**
   28 % du score ; 29 titres sur 81 seulement ont un score non nul.
3. ~~**Mentions légales**~~ — ✅ fait le 28/08 (composant `MentionLegale`).
   ⚠️ Reste à faire relire par un juriste connaissant l'AMMC.
4. **Publier le backtest** (`quant-backtest`) — 3 à 4 jours.
   `phase11_backtest.py` existe, ses résultats ne sont nulle part dans l'UI.
5. **Découper `run()`** — en cours, par tranches.
   ✅ Tranche 1 faite le 31/08 : `fusionner_cotations()` extraite, 12 tests,
   validée sur 4 779 champs sans aucun écart. run() : 768 → 738 lignes.
   🔜 Tranche 2 : la boucle par ticker — c'est elle qui porte les 8 niveaux
   d'imbrication et la chaîne de repli complète (R1 + R3 en même temps).
6. **Accessibilité et mobile** — 3 jours. 1 seul attribut `aria` dans tout le
   frontend (ajouté avec la mention légale).

## ✅ Refermé le 01/09

- **ISIN de Maroc Leasing** — MA0000012270 → **MA0000010035**, validé par
  recoupement arithmétique sur la fiche CDG. Question ouverte depuis le 02/07.
- **Séance du 31/08 recoupée au bulletin CDG** : 70 titres, zéro écart.

## 🧑‍💼 Recrutements humains prioritaires

Les agents couvrent l'exécution ; ces trois rôles couvrent ce qu'un agent ne
peut pas trancher :
- **Juriste AMMC / CNDP** — droit de publier, puis de monétiser.
- **Data scientist NLP** — valider la méthode, pas seulement la brancher.
- **Quant** — valider empiriquement la pondération 25 / 47 / 28, jamais testée.
