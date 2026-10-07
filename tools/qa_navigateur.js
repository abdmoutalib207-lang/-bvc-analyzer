#!/usr/bin/env node
/* Contrôle navigateur du terminal — lecture seule.
 *
 * Adapté de la compétence `browser-qa` du projet ECC (MIT), réduit à ce qui
 * a déjà cassé chez nous : erreur de rendu (« Cannot access 'sym' before
 * initialization », 04/10), débordement sur téléphone, graphique absent,
 * FIB qui plante, fiche qui ne s'ouvre pas.
 *
 * Usage :
 *   python3 -m http.server 8818 &        # depuis la racine du dépôt
 *   npm install --no-save --no-package-lock playwright react@18 react-dom@18 lightweight-charts@4.2.0
 *   node tools/qa_navigateur.js [TICKER ...] [--sortie DOSSIER]
 *
 * Les bibliothèques des CDN sont servies depuis node_modules : le contrôle
 * ne dépend pas du réseau. Chromium : /opt/pw-browsers/chromium si présent.
 * Code de sortie : 0 = PUBLIABLE, 1 = À CORRIGER.
 */
const fs = require('fs');
const path = require('path');
const { chromium } = require('playwright');

const args = process.argv.slice(2);
const iS = args.indexOf('--sortie');
const SORTIE = iS >= 0 ? args[iS + 1] : null;
const TITRES = args.filter((a, i) => !a.startsWith('--') && !(iS >= 0 && i === iS + 1));
if (!TITRES.length) TITRES.push('IAM');
const URL = process.env.QA_URL || 'http://localhost:8818/index.html';
const NM = path.resolve('node_modules');
const LIBS = {
  'react@18/umd/react.production.min.js': 'react/umd/react.production.min.js',
  'react-dom@18/umd/react-dom.production.min.js': 'react-dom/umd/react-dom.production.min.js',
  'lightweight-charts@4.2.0/dist/lightweight-charts.standalone.production.js':
    'lightweight-charts/dist/lightweight-charts.standalone.production.js',
};
const ECRANS = [['telephone', 390, 844], ['tablette', 768, 1024], ['bureau', 1440, 900]];

(async () => {
  const exe = fs.existsSync('/opt/pw-browsers/chromium') ? '/opt/pw-browsers/chromium' : undefined;
  const nav = await chromium.launch({ executablePath: exe });
  const constats = [];
  for (const [nom, w, h] of ECRANS) {
    const ctx = await nav.newContext({ viewport: { width: w, height: h }, hasTouch: w < 500, isMobile: w < 500 });
    await ctx.addInitScript(() => { try { localStorage.setItem('bvc_tab', 'ranking'); } catch (e) {} });
    const p = await ctx.newPage();
    const erreurs = [];
    p.on('pageerror', e => erreurs.push(e.message));
    p.on('console', m => { if (m.type() === 'error') erreurs.push('console: ' + m.text()); });
    await p.route(/^https:\/\//, r => {
      const u = r.request().url();
      const k = Object.keys(LIBS).find(k => u.includes(k));
      return k ? r.fulfill({ path: path.join(NM, LIBS[k]), contentType: 'application/javascript' })
               : r.fulfill({ status: 204, body: '' });
    });
    const ouvrir = async () => {
      await p.goto(URL);
      await p.waitForTimeout(2500);
      if (await p.locator('.intro').count()) { await p.locator('.intro').click(); await p.waitForTimeout(1200); }
    };
    await ouvrir();
    const rendu = await p.locator('text=Erreur de rendu').count();
    if (rendu) constats.push(`${nom} : ÉCRAN « Erreur de rendu »`);
    const lignes = await p.locator('.classement tr').count();
    if (lignes < 50) constats.push(`${nom} : classement à ${lignes} lignes (attendu ≥ 50)`);
    const deborde = await p.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
    if (deborde > 2) constats.push(`${nom} : défilement horizontal de ${deborde} px`);
    for (const t of TITRES) {
      try {
        await p.fill('input[aria-label="Rechercher un titre"], input[placeholder*="Rechercher"]', t);
        await p.waitForTimeout(400);
        await p.locator('.classement tr').nth(1).click();
        await p.waitForTimeout(2000);
        if (!(await p.locator('canvas').count())) constats.push(`${nom} ${t} : aucun graphique`);
        const fib = p.getByRole('button', { name: 'FIB', exact: true }).first();
        if (await fib.count()) { await fib.click(); await p.waitForTimeout(500); await fib.click(); }
        if (SORTIE) {
          fs.mkdirSync(SORTIE, { recursive: true });
          await p.screenshot({ path: path.join(SORTIE, `${nom}_${t}.png`), fullPage: false });
        }
        await ouvrir();   // le site n'a pas d'historique : on recharge
      } catch (e) {
        constats.push(`${nom} ${t} : fiche inaccessible (${e.message.split('\n')[0]})`);
      }
    }
    erreurs.forEach(e => constats.push(`${nom} : ${e.slice(0, 160)}`));
    await ctx.close();
  }
  await nav.close();
  console.log(`Contrôle navigateur — ${URL} — titres : ${TITRES.join(', ')}`);
  console.log(`Écrans : ${ECRANS.map(e => e[0] + ' ' + e[1] + 'px').join(' · ')}`);
  if (!constats.length) { console.log('VERDICT : PUBLIABLE (0 constat)'); process.exit(0); }
  constats.forEach(c => console.log('  ✗ ' + c));
  console.log(`VERDICT : À CORRIGER (${constats.length} constat(s))`);
  process.exit(1);
})();
