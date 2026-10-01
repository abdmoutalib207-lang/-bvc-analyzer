---
name: rediger-briefing
description: Rédige la lecture d'analyste du briefing de clôture à partir des SEULS faits publiés par le moteur (briefing_cloture.json), puis la soumet au contrôle des chiffres avant publication. Utilisée chaque soir par la routine de rédaction ; à lancer aussi à la main pour une séance donnée.
---

# Rédiger le briefing de clôture

Tu écris comme un analyste — une lecture claire, hiérarchisée, qui dit ce qui
compte et pourquoi — mais **tu n'apportes aucun chiffre**. Tous les nombres
viennent de `briefing_cloture.json`, produit par le moteur et contrôlé.

## Pourquoi cette règle

Le 30/09/2026, un briefing rédigé par un autre assistant annonçait RDS
« 173,90 DH, +3,45 % » : c'était le plus HAUT de la séance, la clôture valait
171,00 (+1,73 %). TGCC y était en hausse alors qu'il avait clôturé en baisse,
et des scénarios « 45 / 30 / 25 % » n'avaient aucun calibrage. Le style était
bon, les chiffres faux. Ici, la plume est libre et les chiffres ne le sont pas.

## Étapes

1. `git pull` sur `main`. Lire `briefing_cloture.json`. Vérifier que
   `seance` est la dernière séance close (celle de `data.json`). Si le fichier
   porte une séance plus ancienne, **ne rien écrire** et s'arrêter : le moteur
   n'a pas tourné, ce n'est pas à la rédaction de le masquer.
2. Lire les faits : `constats`, `a_surveiller` (avec `chiffres` lus dans les
   dépôts, `volume_rapport`, `chg`), `trajectoire`, `veille`, `depots`,
   `secteurs`, `matieres`, `niveaux`, `non_mesurable`.
3. Ouvrir, si utile, les dépôts AMMC cités (`url`) pour le CONTEXTE qualitatif
   (activité, explication donnée par l'émetteur). ⚠️ Un nombre lu dans un
   dépôt mais absent des faits ne s'écrit pas : le contrôle le refusera.
   Écrire « la dette nette augmente nettement, selon le communiqué » plutôt
   que le montant.
4. Rédiger dans `/tmp/redaction.md`, en français, 250 à 450 mots :
   - **L'essentiel** — l'indice, la veille, le volume ; ce que la séance a été.
   - **Valeurs à retenir** — celles d'`a_surveiller`, publications d'abord :
     ce qui a été publié (chiffres des faits), puis la réaction du cours
     (`chg`, `volume_rapport`).
   - **Ce qui a changé aujourd'hui** — deux ou trois phrases de synthèse.
   - **Ce que cette lecture ne dit pas** — reprendre `non_mesurable` utile.
5. Contrôler : `python pipeline/redaction.py --controler /tmp/redaction.md`.
   Chaque nombre refusé se corrige en reprenant la valeur des faits, ou se
   retire. Recommencer jusqu'à `"ok": true`.
6. Appliquer : `python pipeline/redaction.py --appliquer /tmp/redaction.md
   --auteur claude`, puis commiter `briefing_cloture.json` et
   `briefings/<séance>.json` seulement, et pousser sur `main`.

## Interdits

- Aucune probabilité, aucun scénario chiffré, aucun objectif de cours.
- Aucune cause affirmée : « le titre recule après la publication » oui ;
  « le titre recule À CAUSE de la publication » non.
- Nommer chaque nombre par ce qu'il est : une clôture est une clôture, un plus
  haut est un plus haut. Le contrôle vérifie qu'un nombre EXISTE dans les
  faits, pas qu'il est bien nommé : cette part-là repose sur toi.
- Aucune recommandation d'achat ou de vente.
- Ne toucher à aucun autre fichier que les deux cités à l'étape 6.
