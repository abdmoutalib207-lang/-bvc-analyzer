# Déclencheur externe — mise en place

> Décidé le 23/09/2026, après la démonstration du jour : GitHub n'a honoré
> **qu'un seul créneau sur vingt-six**, et le terminal a publié des cours de
> 15h08 comme s'ils étaient la clôture de 15h30. 35 titres sur 65 s'écartaient
> du bulletin.

Le Worker ne répare pas les crons GitHub — il les contourne.

## Ce qui est déjà fait

✅ `workflow_dispatch` est présent sur les onze workflows.
✅ `update_bvc.yml` traite cet appel comme un `schedule` et lance le run sans
condition d'heure. Vérifié en conditions réelles le 23/09 à 16h30 : run
réussi, **66/66 cours conformes au bulletin**.
✅ Le code du Worker et ses seize tests sont dans ce dossier, et tournent avec
`pytest` comme le reste du dépôt.

Il ne reste que la partie qui doit être faite par vous, parce qu'elle touche
un compte et un secret.

## 1 — Le jeton GitHub

`Settings` → `Developer settings` → `Personal access tokens` →
**Fine-grained tokens** → `Generate new token`.

| champ | valeur |
|---|---|
| Nom | `BVC Analyzer — déclencheur` |
| Expiration | **notez la date**, voir l'avertissement plus bas |
| Repository access | `Only select repositories` → **`-bvc-analyzer`** |
| Permissions → Actions | **Read and write** |
| Permissions → Issues | **Read and write** |

`Actions` sert à déclencher le run. `Issues` sert à **ouvrir l'alerte quand le
run ne part pas** — c'est la raison d'avoir choisi un Worker plutôt qu'un
simple service de cron. Rien d'autre n'est nécessaire : ni `Contents`, ni
`Workflows`, ni quoi que ce soit en écriture sur le code.

⚠️ **Le jeton ne doit jamais transiter par une conversation avec l'assistant,
ni être écrit dans le dépôt.** Il se pose directement dans les secrets
Cloudflare. Un test du dépôt vérifie qu'aucun jeton n'apparaît dans
`worker.js`.

## 2 — Le Worker

Sur `dash.cloudflare.com` → `Workers & Pages` → `Create` → `Start with Hello
World` → `Deploy`. Puis `Edit code` : remplacer tout le contenu par celui de
`declencheur/worker.js`, et déployer.

### Le secret

`Settings` → `Variables and Secrets` → `Add` :

| type | nom | valeur |
|---|---|---|
| **Secret** | `GITHUB_TOKEN` | le jeton créé à l'étape 1 |

⚠️ **Secret**, pas *Text* : un secret est chiffré au repos et n'est plus
réaffiché après la saisie.

### Les deux réveils

`Settings` → `Triggers` → `Cron Triggers` → `Add` :

```
45 15 * * 1-5     déclenche le run de clôture
50 15 * * 1-5     vérifie qu'il est parti, alerte sinon
```

⚠️ **15h45, et non 15h35.** La clôture est à 15h30 **locales**, et CDG sert
encore la séance **précédente** dans une fenêtre transitoire de quelques
minutes après — c'est ce qui a fait reculer 79 titres d'une journée le
28/08/2026. Quinze minutes de marge, c'est le créneau conçu pour cela.

⚠️ Et l'heure reste bonne dans les deux décalages possibles du Maroc : à UTC+0
elle vaut 15h45 locales, à UTC+1 elle vaut 16h45 — plus tard encore. Un cron
est en UTC fixe et **ne peut pas suivre un décret** ; on choisit donc une heure
valable quel que soit celui en vigueur.

## 3 — Vérifier

Cloudflare ne propose pas de bouton « lancer maintenant » pour un cron. Deux
façons de vérifier :

- **attendre le prochain jour ouvré à 15h45 UTC** et regarder l'onglet
  *Actions* du dépôt : un run `workflow_dispatch` doit y figurer ;
- **ou** ajouter temporairement un troisième cron dans deux ou trois minutes
  (`M H * * *` avec l'heure UTC courante), observer, puis le retirer.

Dans l'onglet *Logs* du Worker, le déclenchement réussi écrit
`déclenchement accepté (204)` et la vérification `run confirmé`.

⚠️ **Un 204 signifie que GitHub a accepté la demande, pas que le run a
réussi.** Le résultat se lit dans *Actions*, et le juge de paix reste le
recoupement au bulletin CDG :

```
python3 pipeline/parse_cdg_bulletin.py <bulletin.pdf> --verifier <AAAA-MM-JJ>
```

## ⚠️ Le piège de l'expiration, et pourquoi il mérite son paragraphe

Un jeton fine-grained expire. **Le jour où il expire, tout s'arrête sans
bruit** : Cloudflare reçoit un `401`, GitHub ne lance rien, et — c'est le pire
— **l'alerte ne peut pas être ouverte non plus, puisqu'elle passe par le même
jeton**. La panne du 23/09 reviendrait, mais silencieuse.

Le Worker ne peut pas se protéger de ça tout seul. Trois parades, à faire
toutes les trois :

1. **Noter la date d'expiration** dans `.claude/memory/EN_COURS.md` dès la
   création, avec un rappel un mois avant. La case à cocher y est déjà.
2. **Garder les crons GitHub** tels quels. Peu fiables, mais indépendants du
   jeton et de Cloudflare : ils finissent par produire un run.
3. **`verifier_seance.yml`**, côté GitHub, dont l'échec envoie un courriel au
   propriétaire du dépôt. Il dépend du cron GitHub, donc il tourne
   irrégulièrement — mais c'est une couverture **de nature différente**, et
   c'est précisément ce qu'on veut : deux mécanismes qui ne tombent pas
   ensemble.

## Ce que ce déclencheur ne règle pas

- **Les jours fériés.** Le run partira quand même. Les gardes internes
  empêchent d'écrire une bougie fantôme — registre `SEANCES_SANS_COTATION`,
  `_recaler_seance_fantome()` — mais le run consommera un commit pour rien.
- **La dépendance à un tiers.** Cloudflare devient un point de défaillance de
  plus, et détient un jeton.
- **Le fond.** Les crons GitHub restent inutilisables pour un rendez-vous.

## Modifier le Worker

Le code vit dans le dépôt, pas dans un formulaire web : il se relit, se teste
et se révise comme le reste.

```
python3 -m pytest tests/test_declencheur_worker.py   # avec le reste de la suite
node --test declencheur/worker.test.mjs              # directement
```

⚠️ **Viser le fichier, pas le dossier.** `node --test declencheur/` charge
aussi `worker.js`, qui ne contient aucun test, et le compte comme un échec.

Après modification, recoller le contenu dans l'éditeur Cloudflare et déployer.
Il n'y a pas de déploiement automatique depuis le dépôt — c'est volontaire :
une chaîne de déploiement de plus serait une dépendance de plus, pour vingt-cinq
lignes qui changent une fois par an.
