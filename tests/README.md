# Le filet de sécurité — ce qui est couvert, et ce qui ne l'est pas

Ouvert le **28/08/2026**. Constat de départ : **0 fichier de test, 1 assertion
dans tout le dépôt, 0 workflow de test**. Toutes les garanties du projet
reposaient sur une vérification manuelle.

```
pip install -r requirements_dev.txt
python -m pytest
```

La suite tourne en **moins d'une seconde** et ne touche ni le réseau ni les
fichiers de production. Ces deux propriétés ne sont pas négociables : une suite
lente est contournée, une suite qui dépend d'un serveur tiers devient une alarme
peu fiable, et une alarme peu fiable finit désactivée.

## Couverture des dix règles absolues

| Règle | Ce qu'elle exige | Couverture |
|---|---|---|
| **R1** | 81 tickers, 19 MASI 1 avec prix | ✅ automatique |
| **R2** | `ISIN_MAP` est la vérité unique | ✅ format, unicité, alias documentés |
| **R3** | La chaîne de repli s'étend et la date arbitre | ✅ fusion des trois sources, arbitrage MASI et cliquet |
| **R4** | Toute dépendance déclarée | ❌ non couvert |
| **R5** | Pas de `filterwarnings` silencieux | ❌ non couvert |
| **R6** | Testé avant commit | ✅ c'est ce fichier |
| **R8** | `Tech + Fond + NLP = 100 %`, score dans [0, 10] | ✅ automatique |
| **R9** | `chg=0` ET `vol=0` ⇒ donnée périmée | 🟡 borné, question ouverte (voir plus bas) |
| **R10** | Variation plafonnée à ±10 %/séance | ✅ sur les données publiées ET sur la fonction de recalcul |

## Ce que chaque fichier protège

| Fichier | Incident qu'il empêche de revenir |
|---|---|
| `test_cliquet_seance.py` | 28/08 — une source recule, `data.json` passe de 73 titres à la séance à zéro |
| `test_arbitrage_masi.py` | 28/08 — l'indice reste sur la source en retard quand les prix ont migré |
| `test_seance_fantome.py` | 14/08 — 114 bougies écrites un jour férié |
| `test_config.py` | 01/07 — un ISIN dupliqué fait afficher le cours d'une autre société |
| `test_regles_donnees.py` | Toute collecte dégradée qui atteindrait le terminal |
| `test_contrat_data_json.py` | 29/06 — trois champs disparaissent, écran blanc en production |
| `test_fusion_sources.py` | Les deux bugs jumeaux : une source oubliée dans la chaîne |
| `test_variation_et_isin.py` | Une variation impossible affichée comme un mouvement réel ; un ISIN croisé qui contamine les indicateurs |

## Ce que les tests ont trouvé en s'écrivant

- **`est_ferie_fixe(None)` levait `TypeError`.** La fonction absorbait
  `ValueError` et `AttributeError`, mais `None[:10]` lève `TypeError`. Or
  `prix_asof` vaut `None` dès qu'un titre n'a pas de séance connue. Corrigé.
- **Le vocabulaire des signaux est plus riche que la documentation.** Le
  CLAUDE.md annonce ACHETER / SURVEILLER / ÉVITER ; le moteur émet aussi
  ATTENDRE, ÉVITER FORT et ACHAT FORT.
- **Deux ISIN sont partagés** — `TGC`/`TGCC` et `SON`/`SNA`. Ce sont des alias
  hérités, inoffensifs car hors univers collecté, désormais figés par un test
  pour qu'un vrai doublon saute aux yeux.

## ⚠️ Où la suite tourne réellement — corrigé le 01/09/2026

Elle est lancée à **deux endroits**, et il a fallu un échec pour le comprendre :

| Déclencheur | Ce qu'il valide |
|---|---|
| `tests.yml` sur un push | les commits **humains**, avant qu'ils n'atteignent la production |
| étape d'`update_bvc.yml` | le `data.json` **réellement publié**, juste après l'écriture |

⚠️ **Le commentaire d'origine de `tests.yml` était faux.** Il affirmait que le
workflow tournait sur les commits des automates. Mesuré le 01/09 : sur six
exécutions, **toutes portaient sur un commit humain, aucune sur un commit
« data: BVC update »**. GitHub ne déclenche pas de workflow sur les commits
poussés avec son propre jeton — protection contre les boucles infinies. Le
filtre `paths: data.json` était donc purement décoratif, et les tests des
règles R1–R10 n'examinaient jamais le fichier publié.

D'où l'étape ajoutée dans `update_bvc.yml`. Elle est **non bloquante** : un run
qui a déjà écrit et poussé ne doit pas être marqué en échec pour un test. Le
contrôle de séance, lui, échoue et alerte.

## ⚠️ Ce qui reste découvert — à traiter, pas à oublier

1. ~~La fusion des sources~~ — ✅ **couverte le 31/08**. Extraite de `run()` en
   `fusionner_cotations()`, qui accepte ses sources en paramètres : c'est ce qui
   permet de la tester sans réseau. 12 cas, dont l'arbitrage dans les DEUX sens,
   la capitalisation IDBourse jamais perdue, et BMCE qui comble sans jamais
   remplacer une ligne CDG.
   L'extraction a été validée en comparant `data.json` avant et après sur
   **4 779 champs de 81 titres : aucun écart hors horodatage.**
2. **`_recaler_seance_fantome()`** n'est couvert qu'indirectement, via
   `pipeline/seance.py`. Elle lit le dossier de chandelles réel sans paramètre
   pour le rediriger.
   ⚠️ **La chaîne de repli par ticker reste le plus gros trou** : les quatre
   niveaux de repli (chandelles → historique → financial → statique) vivent
   encore dans la boucle de 405 lignes. C'est la tranche 3 du découpage.
3. **`compute_v53()`** — le calcul du score lui-même. Il demande un contexte
   riche ; sa couverture appartient à `quant-backtest`.
4. **Les parseurs de sources** (`fetch_all_cdg`, `_bmce_parser`) attendent des
   charges utiles enregistrées dans `tests/fixtures/`. Prochaine tranche.
5. **La question R9 ouverte** : 8 titres portent `chg=0` et `vol=0` sans être
   marqués périmés. Ils n'ont simplement pas coté et affichent leur cours de
   référence. Faut-il les marquer ? Le test borne le nombre à 16 pour détecter
   une dérive, sans trancher. **Avis de `gardien-donnees` attendu.**
