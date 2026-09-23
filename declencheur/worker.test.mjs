/**
 * Ce que le déclencheur doit faire, et surtout ce qu'il ne doit pas faire.
 *
 * ⚠️ CE QUE CES TESTS DÉFENDENT
 * ─────────────────────────────
 * Le Worker existe parce qu'un rendez-vous manqué se voit quatre heures trop
 * tard. Ses deux fautes possibles sont opposées, et les deux sont graves :
 *
 *   ne pas alerter quand le run manque   → la panne redevient silencieuse,
 *                                          c'est-à-dire pire qu'avant ;
 *   alerter quand tout va bien           → une alerte qui se trompe finit par
 *                                          être ignorée, et alors elle ne
 *                                          protège plus rien.
 *
 * Le cas limite qui sépare les deux : l'API GitHub injoignable. On ne SAIT
 * PAS si le run est parti — il ne faut donc rien affirmer.
 *
 * Lancer : node --test declencheur/
 */

import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

import worker, { runTrouve, debutFenetre, corpsAlerte } from "./worker.js";

const SOURCE = readFileSync(new URL("./worker.js", import.meta.url), "utf8");
const MAINTENANT = new Date("2026-09-23T15:50:00Z");
const run = (event, created_at) => ({ event, created_at });

// ── Reconnaître le run qu'on vient de déclencher ───────────────────────────

test("un run workflow_dispatch dans la fenêtre est reconnu", () => {
  const runs = [run("workflow_dispatch", "2026-09-23T15:45:30Z")];
  assert.equal(runTrouve(runs, debutFenetre(MAINTENANT)), true);
});

test("⚠️ un run ANTÉRIEUR à la fenêtre ne compte pas", () => {
  // Sans cette borne, le run de la veille — ou celui de 13h50, qui a publié
  // des cours de mi-séance le 23/09 — passerait pour une confirmation.
  const runs = [run("workflow_dispatch", "2026-09-23T13:50:00Z")];
  assert.equal(runTrouve(runs, debutFenetre(MAINTENANT)), false);
});

test("⚠️ un run déclenché par le CRON GitHub ne confirme rien", () => {
  // Il peut tomber n'importe quand ; c'est précisément le défaut qu'on
  // contourne. Seul un `workflow_dispatch` atteste que NOTRE appel a abouti.
  const runs = [run("schedule", "2026-09-23T15:46:00Z")];
  assert.equal(runTrouve(runs, debutFenetre(MAINTENANT)), false);
});

test("une liste vide ou absente ne fait pas tomber le calcul", () => {
  const depuis = debutFenetre(MAINTENANT);
  assert.equal(runTrouve([], depuis), false);
  assert.equal(runTrouve(null, depuis), false);
  assert.equal(runTrouve([null, undefined], depuis), false);
});

test("la fenêtre remonte bien de quinze minutes", () => {
  assert.equal(debutFenetre(MAINTENANT), "2026-09-23T15:35:00.000Z");
});

// ── Le routage des deux réveils ────────────────────────────────────────────

function faux() {
  const appels = [];
  globalThis.fetch = async (url, opts = {}) => {
    appels.push({ url: String(url), methode: opts.method || "GET" });
    if (String(url).endsWith("/dispatches")) {
      return { status: 204, ok: true, text: async () => "" };
    }
    if (String(url).includes("/runs?")) {
      return {
        status: 200, ok: true,
        json: async () => ({
          workflow_runs: [run("workflow_dispatch", new Date().toISOString())],
        }),
      };
    }
    return { status: 201, ok: true, json: async () => ({}) };
  };
  return appels;
}

test("le premier réveil déclenche, et ne fait que cela", async () => {
  const appels = faux();
  await worker.scheduled({ cron: "45 15 * * 1-5" }, { GITHUB_TOKEN: "x" });
  assert.equal(appels.length, 1);
  assert.ok(appels[0].url.endsWith("/dispatches"));
  assert.equal(appels[0].methode, "POST");
});

test("le second réveil vérifie, et n'alerte pas si le run est là", async () => {
  const appels = faux();
  await worker.scheduled({ cron: "50 15 * * 1-5" }, { GITHUB_TOKEN: "x" });
  assert.equal(appels.length, 1, "aucune issue ne doit être ouverte");
  assert.ok(appels[0].url.includes("/runs?"));
});

test("⚠️ le second réveil OUVRE une issue quand le run manque", async () => {
  // La raison d'être du Worker. Sans cela, il ne vaut pas mieux qu'un service
  // de cron ordinaire : la panne redevient silencieuse.
  const appels = [];
  globalThis.fetch = async (url, opts = {}) => {
    appels.push({ url: String(url), methode: opts.method || "GET", body: opts.body });
    if (String(url).includes("/runs?")) {
      return { status: 200, ok: true, json: async () => ({ workflow_runs: [] }) };
    }
    return { status: 201, ok: true, json: async () => ({}) };
  };
  await worker.scheduled({ cron: "50 15 * * 1-5" }, { GITHUB_TOKEN: "x" });
  const issue = appels.find((a) => a.url.endsWith("/issues"));
  assert.ok(issue, "aucune issue ouverte alors que le run manquait");
  assert.equal(issue.methode, "POST");
});

test("⚠️ API injoignable : on n'alerte PAS — on ne sait rien", async () => {
  // LE CAS LIMITE. Ouvrir une issue dirait « le run n'est pas parti » alors
  // qu'on l'ignore. Une alerte qui se trompe finit par être ignorée, et
  // alors elle ne protège plus rien.
  const appels = [];
  globalThis.fetch = async (url, opts = {}) => {
    appels.push({ url: String(url), methode: opts.method || "GET" });
    return { status: 500, ok: false, json: async () => ({}), text: async () => "" };
  };
  await worker.scheduled({ cron: "50 15 * * 1-5" }, { GITHUB_TOKEN: "x" });
  assert.equal(appels.filter((a) => a.url.endsWith("/issues")).length, 0);
});

test("un cron inattendu ne déclenche rien", async () => {
  const appels = faux();
  await worker.scheduled({ cron: "0 3 * * *" }, { GITHUB_TOKEN: "x" });
  assert.equal(appels.length, 0);
});

// ── L'heure, et pourquoi c'est elle ────────────────────────────────────────

test("⚠️ le déclenchement est à 15h45 UTC, jamais plus tôt", () => {
  // La clôture est à 15h30 LOCALES et CDG sert encore la séance PRÉCÉDENTE
  // dans les minutes qui suivent — c'est ce qui a fait reculer 79 titres d'une
  // journée le 28/08/2026. Un guide générique propose 15h35 : cinq minutes
  // après la clôture, en pleine fenêtre.
  const m = SOURCE.match(/CRON_DECLENCHE = "(\d+) (\d+) \* \* 1-5"/);
  assert.ok(m, "le cron de déclenchement doit rester lisible dans la source");
  const [, minute, heure] = m.map(Number);
  assert.equal(heure, 15);
  assert.ok(minute >= 45, `${minute} min après l'heure : trop tôt après la clôture`);
});

test("la vérification passe APRÈS le déclenchement", () => {
  const h = (nom) =>
    SOURCE.match(new RegExp(`${nom} = "(\\d+) (\\d+)`)).slice(1).map(Number);
  const [md, hd] = h("CRON_DECLENCHE");
  const [mv, hv] = h("CRON_VERIFIE");
  assert.ok(hv * 60 + mv > hd * 60 + md, "vérifier avant de déclencher n'a aucun sens");
});

test("les deux crons ne tournent que les jours ouvrés", () => {
  for (const nom of ["CRON_DECLENCHE", "CRON_VERIFIE"]) {
    assert.match(SOURCE, new RegExp(`${nom} = "[^"]*\\* \\* 1-5"`), nom);
  }
});

// ── Ce que l'alerte doit dire ──────────────────────────────────────────────

test("⚠️ l'alerte porte le diagnostic, pas seulement le constat", () => {
  // Une alerte qui dit « ça n'a pas marché » oblige à tout reprendre. Celle-ci
  // nomme la cause la plus fréquente — le jeton expiré, qui est silencieuse —
  // et donne la réparation immédiate.
  const corps = corpsAlerte("2026-09-23 15:50 UTC", null);
  assert.match(corps, /jeton/i, "la cause la plus fréquente doit être nommée");
  assert.match(corps, /EN_COURS\.md/, "où trouver la date d'expiration");
  assert.match(corps, /parse_cdg_bulletin/, "comment vérifier après réparation");
  assert.match(corps, /quinze minutes suivant 15h30/,
    "le piège de la fenêtre transitoire doit être rappelé dans l'alerte même");
});

// ── Le jeton ───────────────────────────────────────────────────────────────

test("⚠️ aucun jeton n'est écrit dans la source", () => {
  // Il vient de `env`, c'est-à-dire des secrets de la plateforme. Ce test
  // rougirait si quelqu'un « testait rapidement » en collant le sien.
  assert.equal(/gh[pousr]_[A-Za-z0-9]{16,}|github_pat_[A-Za-z0-9_]{20,}/.test(SOURCE),
    false, "un jeton semble écrit en dur dans worker.js");
  assert.match(SOURCE, /env\.GITHUB_TOKEN/);
});

test("le User-Agent est envoyé — GitHub refuse les requêtes sans lui", () => {
  // Un 403 sans explication, que rien dans le message d'erreur ne signale.
  assert.match(SOURCE, /"User-Agent":/);
});
