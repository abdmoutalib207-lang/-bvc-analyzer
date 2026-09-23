/**
 * Déclencheur externe du run de clôture — Cloudflare Worker.
 *
 * ⚠️ POURQUOI CE FICHIER EXISTE
 * ─────────────────────────────
 * Le déclencheur `schedule` de GitHub n'est pas un rendez-vous. Mesuré sur
 * quatre jours ouvrés de septembre 2026 : **26 créneaux programmés par jour,
 * 4 honorés** — et un seul le 23/09, tombé à 13h50, avant la clôture. Ce
 * jour-là le terminal a publié des cours de 15h08 comme s'ils étaient la
 * clôture de 15h30 ; 35 titres sur 65 s'écartaient du bulletin.
 *
 * Ce Worker ne répare pas les crons GitHub — il les contourne.
 *
 * ⚠️ CE QU'IL FAIT DE PLUS QU'APPELER, ET QUI EST LA RAISON DE L'AVOIR CHOISI
 * Un déclencheur qui tombe en panne sans le dire ramène exactement la panne
 * qu'il devait empêcher, en pire : silencieuse. Ici, un second réveil cinq
 * minutes plus tard **vérifie que le run est bien parti** et ouvre une issue
 * sinon. L'alerte arrive par le canal déjà surveillé, sans service tiers ni
 * secret supplémentaire.
 *
 * ⚠️ CE QU'IL NE COUVRE PAS, ET IL FAUT LE SAVOIR
 * Si le jeton expire, ni le déclenchement ni l'ouverture d'issue ne
 * fonctionnent — l'alerte a le même point de défaillance que ce qu'elle
 * surveille. La parade est ailleurs :
 *   1. la date d'expiration notée dans `.claude/memory/EN_COURS.md` ;
 *   2. `verifier_seance.yml`, côté GitHub, dont l'échec envoie un courriel.
 *      Il dépend du cron GitHub, donc il tourne irrégulièrement — mais il
 *      finit par tourner, et c'est une couverture de NATURE DIFFÉRENTE.
 *
 * ⚠️ DEUX RÉVEILS PLUTÔT QU'UNE ATTENTE
 * Le Worker ne dort pas entre le déclenchement et la vérification : il est
 * réveillé deux fois. Une attente de cinq minutes dans un seul appel
 * dépendrait des limites de durée de la plateforme, qui changent ; deux crons
 * n'en dépendent pas.
 *
 * Configuration : voir `declencheur/README.md`.
 */

const DEPOT = { proprietaire: "abdmoutalib207-lang", nom: "-bvc-analyzer" };
const WORKFLOW = "update_bvc.yml";
const BRANCHE = "main";

// ⚠️ 15h45 UTC, et non 15h35. La clôture est à 15h30 LOCALES, et CDG sert
// encore la séance PRÉCÉDENTE dans une fenêtre transitoire de quelques minutes
// après — c'est ce qui a fait reculer 79 titres d'une journée le 28/08/2026.
// Quinze minutes de marge, c'est le créneau conçu pour cela.
//
// ⚠️ Et l'heure reste bonne dans les deux décalages possibles du Maroc : à
// UTC+0 elle vaut 15h45 locales, à UTC+1 elle vaut 16h45 — plus tard encore.
// Un cron est en UTC fixe et ne peut pas suivre un décret ; on choisit donc
// une heure valable quel que soit celui en vigueur.
const CRON_DECLENCHE = "45 15 * * 1-5";
const CRON_VERIFIE = "50 15 * * 1-5";

// Marge de recherche du run : assez large pour absorber l'horloge du Worker et
// la latence de l'API, assez étroite pour ne pas confondre avec un run plus
// ancien de la même journée.
const FENETRE_MINUTES = 15;

const ENTETES = (jeton) => ({
  "Authorization": `Bearer ${jeton}`,
  "Accept": "application/vnd.github+json",
  "X-GitHub-Api-Version": "2022-11-28",
  // ⚠️ GitHub REFUSE les requêtes sans User-Agent (403). Ce n'est pas
  // optionnel, et le message d'erreur ne le dit pas clairement.
  "User-Agent": "bvc-analyzer-declencheur",
});

const base = () =>
  `https://api.github.com/repos/${DEPOT.proprietaire}/${DEPOT.nom}`;

/** Le run a-t-il démarré ? Fonction pure, pour être testable sans réseau. */
export function runTrouve(runs, depuisISO) {
  const depuis = Date.parse(depuisISO);
  return (runs || []).some(
    (r) =>
      r &&
      r.event === "workflow_dispatch" &&
      Date.parse(r.created_at) >= depuis
  );
}

/** Le début de la fenêtre de recherche, en ISO. Pure elle aussi. */
export function debutFenetre(maintenant, minutes = FENETRE_MINUTES) {
  return new Date(maintenant.getTime() - minutes * 60_000).toISOString();
}

/**
 * Le corps de l'issue d'alerte.
 *
 * ⚠️ Il porte le diagnostic, pas seulement le constat. Une alerte qui dit
 * « ça n'a pas marché » oblige à tout reprendre ; celle-ci dit quoi regarder
 * en premier, et dans quel ordre.
 */
export function corpsAlerte(quand, detail) {
  return [
    `Le déclencheur externe a appelé GitHub à ${quand}, et **aucun run \``,
    `${WORKFLOW}\` n'est parti** dans les ${FENETRE_MINUTES} minutes qui ont suivi.`,
    ``,
    `Conséquence si rien n'est fait : le bulletin de demain portera la clôture`,
    `de la veille, et le terminal publiera des cours de milieu de séance.`,
    ``,
    `### À regarder, dans cet ordre`,
    ``,
    `1. **Le jeton a-t-il expiré ?** C'est la cause la plus fréquente, et elle`,
    `   est silencieuse. Un jeton fine-grained a une date de fin ; la nôtre est`,
    `   notée dans \`.claude/memory/EN_COURS.md\`.`,
    `2. **L'onglet Actions** — le run est-il parti puis tombé en échec ? Ce`,
    `   n'est alors pas le déclencheur qui est en cause.`,
    `3. **Le workflow accepte-t-il toujours \`workflow_dispatch\` ?** Une`,
    `   modification du fichier a pu retirer cette porte.`,
    ``,
    `### Réparation immédiate, quelle que soit la cause`,
    ``,
    `Lancer \`${WORKFLOW}\` à la main depuis l'onglet Actions, puis recouper au`,
    `bulletin CDG : \`python3 pipeline/parse_cdg_bulletin.py <pdf> --verifier <date>\`.`,
    ``,
    `⚠️ Ne pas lancer de run dans les quinze minutes suivant 15h30 : CDG sert`,
    `encore la séance précédente dans cette fenêtre.`,
    ``,
    `<details><summary>Détail technique</summary>`,
    ``,
    "```",
    String(detail ?? "aucun run workflow_dispatch trouvé dans la fenêtre"),
    "```",
    `</details>`,
  ].join("\n");
}

async function declencher(env) {
  const r = await fetch(`${base()}/actions/workflows/${WORKFLOW}/dispatches`, {
    method: "POST",
    headers: { ...ENTETES(env.GITHUB_TOKEN), "Content-Type": "application/json" },
    body: JSON.stringify({ ref: BRANCHE }),
  });
  // ⚠️ 204 signifie que GitHub a ACCEPTÉ la demande, pas que le run a réussi —
  // ni même qu'il a démarré. D'où le second réveil.
  if (r.status !== 204) {
    console.log(`déclenchement refusé : HTTP ${r.status} ${await r.text()}`);
    return;
  }
  console.log("déclenchement accepté (204)");
}

async function verifier(env, maintenant = new Date()) {
  const depuis = debutFenetre(maintenant);
  const r = await fetch(
    `${base()}/actions/workflows/${WORKFLOW}/runs?per_page=20`,
    { headers: ENTETES(env.GITHUB_TOKEN) }
  );
  if (!r.ok) {
    console.log(`vérification impossible : HTTP ${r.status}`);
    // ⚠️ On n'alerte PAS ici : si l'API est injoignable ou le jeton mort, on
    // ne sait rien du run. Ouvrir une issue dirait « le run n'est pas parti »
    // alors qu'on l'ignore — et une alerte qui se trompe finit par être
    // ignorée. Le journal du Worker garde la trace.
    return;
  }
  const { workflow_runs: runs } = await r.json();
  if (runTrouve(runs, depuis)) {
    console.log("run confirmé");
    return;
  }
  await alerter(env, maintenant);
}

async function alerter(env, maintenant) {
  const quand = maintenant.toISOString().slice(0, 16).replace("T", " ") + " UTC";
  const r = await fetch(`${base()}/issues`, {
    method: "POST",
    headers: { ...ENTETES(env.GITHUB_TOKEN), "Content-Type": "application/json" },
    body: JSON.stringify({
      title: `⚠️ Le run de clôture n'est pas parti (${quand})`,
      body: corpsAlerte(quand, null),
    }),
  });
  console.log(
    r.ok ? "alerte ouverte" : `alerte impossible : HTTP ${r.status}`
  );
}

export default {
  async scheduled(event, env, _ctx) {
    if (event.cron === CRON_DECLENCHE) return declencher(env);
    if (event.cron === CRON_VERIFIE) return verifier(env);
    console.log(`cron inattendu, ignoré : ${event.cron}`);
  },
};
