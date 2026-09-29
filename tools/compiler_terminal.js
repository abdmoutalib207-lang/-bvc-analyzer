#!/usr/bin/env node
/*
 * Compile le terminal : terminal.src.html (JSX) → index.html (JavaScript).
 *
 * ⚠️ POURQUOI — mesuré le 29/09/2026, copie locale, sans réseau :
 *
 *                        compilé au navigateur   précompilé
 *   ordinateur                  4,9 s               0,8 s
 *   téléphone (CPU ×4)         14,8 s               2,6 s
 *
 * Le navigateur téléchargeait Babel (2,85 Mo) puis recompilait 250 000
 * caractères à CHAQUE ouverture. Et une faute de syntaxe cassait le site
 * entier sans que rien ne prévienne : elle échoue maintenant ICI, avant
 * publication.
 *
 * ⚠️ ON MODIFIE terminal.src.html, JAMAIS index.html. Un test de la CI
 * recompile la source et exige l'égalité octet pour octet avec index.html :
 * un index.html retouché à la main, ou une source oubliée, fait rougir.
 *
 *     node tools/compiler_terminal.js            écrit index.html
 *     node tools/compiler_terminal.js --stdout   écrit sur la sortie standard
 *
 * Dépendance : @babel/standalone, version épinglée dans BABEL_VERSION.
 */
"use strict";
const fs = require("fs");
const path = require("path");

const BABEL_VERSION = "7.29.9";
const RACINE = path.resolve(__dirname, "..");
const B = require("@babel/standalone");
if (B.version !== BABEL_VERSION) {
  console.error(`Babel ${B.version} au lieu de ${BABEL_VERSION} : la sortie ne serait pas reproductible.`);
  process.exit(2);
}

const src = fs.readFileSync(path.join(RACINE, "terminal.src.html"), "utf8");
let n = 0;
let out = src.replace(
  /<script([^>]*)type="text\/babel"([^>]*)>([\s\S]*?)<\/script>/g,
  (_, a, b, code) => {
    n += 1;
    const js = B.transform(code, { presets: ["react"], comments: false }).code;
    return `<script>${js}</script>`;
  });
if (n === 0) { console.error("aucun bloc JSX trouvé"); process.exit(1); }
// Le compilateur du navigateur n'a plus rien à compiler : on ne le charge plus.
const avant = out.length;
out = out.replace(/\s*<script src="[^"]*@babel\/standalone[^"]*"><\/script>/, "");
if (out.length === avant) { console.error("balise Babel introuvable"); process.exit(1); }
out = out.replace(/<head>/,
  "<head>\n<!-- ⚠️ FICHIER GÉNÉRÉ par tools/compiler_terminal.js depuis terminal.src.html. " +
  "Ne pas le modifier : modifier la source, puis recompiler. -->");

if (process.argv.includes("--stdout")) process.stdout.write(out);
else { fs.writeFileSync(path.join(RACINE, "index.html"), out); console.log(`index.html écrit — ${n} bloc(s) compilé(s), ${out.length} caractères`); }
