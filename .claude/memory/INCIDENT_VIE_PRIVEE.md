# Incident vie privée — 2 092 identités publiques (05/06 → 03/09/2026)

> Consigné le 03/09/2026 sur ordre ferme d'Abd Moutalib. C'est le plus grave
> défaut rencontré depuis le début du projet : il ne touchait pas une donnée
> de marché mais **des personnes réelles**, et il a duré trois mois.

## Ce qui était exposé

Le dépôt est **public**. Y étaient lisibles, sans compte GitHub :

    personnes nommées                     2 092
    dont numéros de téléphone                32
    commits concernés                       106
    depuis                        05/06/2026

Pas seulement des noms : chacun était accompagné de son **taux de réussite**,
de son **alpha**, de sa **régularité** et de son **influence dans le groupe**.
Un jugement public de compétence financière, sur des gens qui écrivaient dans
une conversation privée et n'avaient rien accepté.

## Où ils vivaient

    whatsapp_analysis/output/network_metrics.csv        2 013 lignes nommées
    whatsapp_analysis/output/smart_money_ranking.csv      141 lignes nommées
    whatsapp_analysis/output/report.html                   34 noms
    index.html                                             17 noms — LA PAGE PUBLIÉE

⚠️ **Et dans nos propres fichiers**, découvert en dernier :

    tests/test_pseudonymes.py                     70 occurrences
    whatsapp_analysis/pseudonymiser_sorties.py     6
    whatsapp_analysis/fils.py                      4
    whatsapp_analysis/pseudonymes.py               3
    .claude/memory/ERRORS.md                       2

Le nom d'un membre servait de **donnée de test** et d'**exemple de
documentation** — y compris dans les commentaires qui expliquent comment on
protège les gens. Écrit par Claude, en toute bonne foi, en croyant illustrer.

## Pourquoi ça a duré trois mois

- **Aucun test ne regardait.** 173 tests existent aujourd'hui ; aucun ne
  vérifiait le contenu des fichiers versionnés avant le 02/09.
- **`.gitignore` n'excluait que `.pkl` et `messages.csv`.** Les CSV de sortie
  n'étaient pas dans la liste, donc versionnés par défaut.
- **Personne ne relisait ces fichiers** : ils sont produits par le pipeline et
  commités par un automate.

## Comment on l'a réparé

Ordre exact, chaque étape ayant échoué au moins une fois avant de réussir.

1. **Pseudonymisation des fichiers courants** (02/09) — identifiants `M####`
   stables, tirés d'un condensat salé. Le sel et la table restent hors dépôt.
2. **Purge de l'historique** (03/09) — `git filter-repo` :
   - `--path <3 fichiers> --invert-paths` : ils n'existent plus dans aucun
     commit. Ce sont des sorties régénérables, pas du code.
   - `--replace-text` pour les 8 noms d'`index.html`, qu'on ne peut pas
     supprimer puisque c'est le site.
   - **21 secondes.**
3. **Poussée forcée** des 5 branches.
4. **Suppression du tag `v1.0-data`** — fait à la main par Abd Moutalib depuis
   Chrome sur iPhone, en mode « site pour ordinateur ».
5. **Nettoyage de nos propres fichiers** — noms remplacés par « Karim Doe »,
   manifestement inventés.

## ⚠️ CINQ PIÈGES, tous rencontrés pour de vrai

**1. `git filter-repo --blob-callback` attend le CORPS d'une fonction, pas un
module.** Lui passer un fichier contenant `def blob_callback(...)` produit une
fonction qui en définit une autre et ne fait rien. L'outil a renuméroté les
5 827 commits en annonçant « Completely finished », **sans rien nettoyer**.
Détecté parce que la vérification portait sur le RÉSULTAT, jamais sur le
message de l'outil.

**2. Un pré-filtre trop étroit saute des fichiers entiers.** Le premier ne
traitait que les blobs contenant le mot `author`. Le rapport HTML généré par la
phase 14 ne le contient pas — ses noms sont dans des cellules `<td>`. Un fichier
entier a donc échappé au nettoyage.

**3. Un TAG maintient des commits en vie.** `git push --all` ne pousse pas les
tags. `v1.0-data` pointait encore sur l'ancien historique et retenait à lui seul
**164 commits** avec tous les noms. Invisible si l'on ne regarde que les
branches.

**4. Les références de pull requests ne se suppriment pas.** GitHub garde
`refs/pull/N/head` pour chaque PR jamais ouverte. Celles de **PR #8 et #9**
pointent sur l'ancien historique. Ni `git push --delete`, ni l'interface, ni la
fermeture de la PR ne les enlèvent. **Seul GitHub Support peut les purger.**

**5. Le réseau du conteneur bloque la poussée des tags.** Branches acceptées,
tags refusés avec `the remote end hung up unexpectedly` puis un trompeur
`Everything up-to-date`. Quatorze tentatives. La manipulation a dû être faite
depuis le téléphone du propriétaire.

## État au 03/09/2026, mesuré et non supposé

    clone normal du dépôt              0 nom, 0 numéro   ✓
    bouton History sur GitHub          plus de fichier   ✓
    recherche de code GitHub           version courante propre   ✓
    refs/pull/8 et /9                  2 013 personnes · 588 numéros   ⚠️ OUVERT

**Reste à faire, et cela ne dépend plus de nous** : demander à GitHub Support
une purge des objets inatteignables (catégorie « Removing sensitive data »).
Le message est prêt dans l'échange du 03/09.

⚠️ **Ne pas rouvrir de pull request depuis une branche portant l'ancien
historique** — cela recréerait une référence.

## Les règles qui en découlent

1. **Un jeu de test ne porte jamais l'identité d'une personne réelle.**
   Inventer un nom coûte trois secondes.
2. **Un commentaire qui explique comment on protège quelqu'un ne le nomme pas.**
3. **Vérifier le résultat, jamais le message de l'outil.** « Completely
   finished » a menti deux fois de suite.
4. **Après une réécriture d'historique, contrôler les branches, LES TAGS, et
   les références de pull requests** — trois endroits distincts.
5. **`data/` est ignoré en entier**, avec liste blanche si besoin. Une liste de
   fichiers nommés un par un laisse passer le prochain fichier sensible.
6. **Le garde-fou qui compte est celui qui tourne en CI**, sans secret :
   `test_aucun_nom_reel_dans_les_csv_versionnes` relit les fichiers versionnés
   et refuse tout ce qui n'est pas un `M####`.
