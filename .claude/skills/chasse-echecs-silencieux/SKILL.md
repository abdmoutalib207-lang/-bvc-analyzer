---
name: chasse-echecs-silencieux
description: Traque les échecs SILENCIEUX — une source qui cesse de répondre sans le dire, un repli qui recopie une vieille donnée comme fraîche, une exception avalée — dans le code du moteur ET dans les données publiées. À lancer après un incident, avant une refonte du pipeline, ou une fois par semaine. Lecture seule ; rend une liste de constats, ne corrige rien.
---

# Chasse aux échecs silencieux

Adapté de l'agent `silent-failure-hunter` du projet ECC (MIT), récrit pour la
BVC : ici, l'échec silencieux le plus coûteux n'est pas l'exception avalée,
c'est **la donnée périmée présentée comme fraîche**.

## Pourquoi

Incidents réels, tous passés sans alerte :

| Date | Ce qui s'est tu | Comment on l'a vu |
|---|---|---|
| 05/10/2026 | BPA de JET pris sur un site tiers : 104,21 au lieu de 73,39 | relecture externe |
| 05/10/2026 | volumes CDG arrêtés avant le fixing (HPS 5 851 au lieu de 7 818) | bulletin PDF |
| 05/10/2026 | MASI servi au 02/10 en pleine séance du 05/10 | test du briefing |
| 05/10/2026 | essai à blanc qui écrivait `marche_history.json` | git status |
| 14/08/2026 | jour férié : 114 bougies écrites pour une séance fictive | contrôle global |
| 10/08/2026 | bougie figée sur le premier run de la journée (57 fausses) | bulletin PDF |

## Volet 1 — les DONNÉES publiées (le plus rentable, commencer ici)

Sur `origin/main`, sans rien écrire :

1. **Dates** : `data.json` → `masi.asof`, `_meta.prix_asof` de chaque titre,
   `_meta.fond_asof`. Toute date antérieure à la dernière séance doit porter
   `stale: true` ou un motif (suspension).
2. **Sources** : compter `_meta.source_prix` ; tout `static`, `financial`,
   `data_json_precedent` est un repli muet à nommer.
3. **Étiquettes de provenance** : dans `bpa.json`, aucune entrée d'un titre
   réel ne doit rester `casablancabourse_derive` (source tierce).
4. **Recoupement** : si un bulletin CDG du jour est fourni, `python3
   pipeline/parse_cdg_bulletin.py <pdf> --verifier <séance>` pour les cours,
   et comparer `qte` / `volume` du bulletin aux chandelles et à
   `masi.volume_mad` (les cours peuvent concorder et les volumes non).
5. **Constantes déguisées en mesures** : un champ qui vaut la même chose sur
   80/80 titres (ex. `conv` = « DIVERGE » relevé le 25/09) est suspect.

## Volet 2 — le CODE (update_data.py, pipeline/)

Rechercher, et pour chaque occurrence dire ce que voit l'utilisateur si ça
échoue :

- `except Exception` suivi de `pass`, `return None`, `return {}` ou d'un
  simple `logger.warning` : le repli est-il **daté** et **signalé** dans
  `_meta`, ou recopie-t-il en silence ?
- `.get(..., 0)` / `or 0` sur un prix, un volume, une variation : un 0
  inventé passe pour « inchangé » (R9).
- Appels réseau sans `timeout=`.
- Écritures disque (`write_text`, `json.dump`) atteignables en
  `dry_run=True`.
- Un contrôle qui compare deux chiffres sans vérifier qu'ils portent sur la
  même séance (cas du briefing, 05/10).

## Ce que la chasse NE fait PAS

- Elle ne corrige rien : chaque constat part vers `relecteur-pipeline`, puis
  une PR petite (R7).
- Elle n'affaiblit aucun contrôle bloquant pour faire taire une alerte (R12).
- Un `except` qui protège la publication d'une collecte ANNEXE est légitime
  s'il journalise : le signaler seulement s'il masque une donnée publiée.

## Format du rendu

Un tableau, du plus grave au moins grave :

| Où | Gravité (publiée fausse / masquée / journal seul) | Ce qui se tait | Ce que voit l'utilisateur | Correctif proposé |

Puis une ligne : nombre de constats par gravité, et l'échantillon examiné
(fichiers lus, titres comptés) — R12 : pas de chiffre sans échantillon.
