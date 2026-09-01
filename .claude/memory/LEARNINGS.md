# Apprentissages durables — BVC Analyzer

> Ouvert le 28/08/2026. Ce que le projet a appris et qui ne doit pas se reperdre.
> À distinguer d'`ERRORS.md` : ici on note ce qui est VRAI, pas ce qui a raté.

---

## Sur le marché marocain

- **La BVC plafonne la variation à ±10 % par séance** (R10). Toute variation
  calculée au-delà est une erreur de données, jamais un mouvement réel. C'est un
  invariant réglementaire, donc un contrôle fiable et gratuit.
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
