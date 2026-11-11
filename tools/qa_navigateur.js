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
 *
 * ⚠️ 11/11/2026 — « États financiers » : un chiffre à moitié caché sous la
 * colonne figée se lit comme un autre (« 16 373 » lu « 6 373 »). Pour chaque
 * titre qui a la carte, dans les deux vues : aucune colonne de période
 * visible n'est coupée (ni par la colonne figée, ni par le bord droit) et
 * aucun nombre ne déborde de sa case — au chargement, puis après trois
 * défilements arrêtés sur un pixel arbitraire et relâchés (position fixée par
 * script, molette, glisser au doigt sur téléphone).
 */
const fs = require('fs');
const path = require('path');
const { chromium } = require('playwright');

const args = process.argv.slice(2);
const iS = args.indexOf('--sortie');
const SORTIE = iS >= 0 ? args[iS + 1] : null;
const TITRES = args.filter((a, i) => !a.startsWith('--') && !(iS >= 0 && i === iS + 1));
if (!TITRES.length) TITRES.push('IAM');
// L'ouverture se fait toujours sur l'Accueil (07/10/2026) : le classement
// se demande par l'adresse.
const URL = (process.env.QA_URL || 'http://localhost:8818/index.html') + '#onglet=ranking';
const NM = path.resolve('node_modules');
const LIBS = {
  'react@18/umd/react.production.min.js': 'react/umd/react.production.min.js',
  'react-dom@18/umd/react-dom.production.min.js': 'react-dom/umd/react-dom.production.min.js',
  'lightweight-charts@4.2.0/dist/lightweight-charts.standalone.production.js':
    'lightweight-charts/dist/lightweight-charts.standalone.production.js',
};
const ECRANS = [['telephone', 390, 844], ['tablette', 768, 1024], ['bureau', 1440, 900]];

// Colonnes coupées et nombres débordants du tableau « États financiers ».
const coupes = p => p.evaluate(() => {
  const d = document.querySelector('.fiche-etats .ef-defile');
  if (!d) return null;
  const r = d.getBoundingClientRect(), g = d.querySelector('thead th.ef-lib').getBoundingClientRect().right;
  const out = [];
  d.querySelectorAll('thead th:not(.ef-lib)').forEach(th => {
    const b = th.getBoundingClientRect(), vu = Math.min(b.right, r.right) - Math.max(b.left, g);
    if (vu > 0.5 && vu < b.width - 0.5) out.push(`${th.textContent} visible sur ${vu.toFixed(1)} px de ${b.width.toFixed(1)}`);
  });
  // Le contenu (valeur, marque, variation) dans la boîte intérieure de la case.
  // Pas scrollWidth : sur écran tactile, la zone de toucher élargie (button::after,
  // 2 px de chaque côté) le gonfle sans rien tronquer.
  d.querySelectorAll('.ef-c').forEach(c => {
    const r = c.getBoundingClientRect(), s = getComputedStyle(c);
    const g0 = r.left + parseFloat(s.paddingLeft) - 0.5, d0 = r.right - parseFloat(s.paddingRight) + 0.5;
    if ([...c.children].some(e => { const x = e.getBoundingClientRect(); return x.width && (x.left < g0 || x.right > d0); }))
      out.push(`débordement : ${c.getAttribute('aria-label')}`);
  });
  return out;
});
const controlerEtats = async (p, nom, t, tactile) => {
  const constats = [];
  if (!(await p.locator('.fiche-etats .ef-defile').count())) return constats;
  for (const vue of ['Annuel', 'Semestriel']) {
    await p.locator('.fiche-etats').getByRole('button', { name: vue, exact: true }).click();
    await p.waitForTimeout(400);
    const note = async quand => (await coupes(p) || []).forEach(c => constats.push(`${nom} ${t} ${vue} ${quand} : ${c}`));
    await note('au chargement');
    const max = await p.evaluate(() => { const d = document.querySelector('.fiche-etats .ef-defile'); return d.scrollWidth - d.clientWidth; });
    if (max < 1) continue;
    // 1. position arbitraire fixée par script
    await p.evaluate(x => { document.querySelector('.fiche-etats .ef-defile').scrollLeft = x; }, Math.round(max * 0.37) + 13);
    await p.waitForTimeout(700); await note('après défilement par script');
    // 2. molette horizontale d'un nombre arbitraire de pixels
    const b = await p.locator('.fiche-etats .ef-defile').boundingBox();
    await p.mouse.move(b.x + b.width * 0.7, b.y + 60); await p.mouse.wheel(-29, 0);
    await p.waitForTimeout(900); await note('après molette de 29 px');
    // 3. glisser au doigt, relâché à mi-colonne (téléphone)
    if (tactile) {
      const cdp = await p.context().newCDPSession(p), y = b.y + 60, x0 = b.x + b.width * 0.8;
      await cdp.send('Input.dispatchTouchEvent', { type: 'touchStart', touchPoints: [{ x: x0, y }] });
      for (let i = 1; i <= 6; i++) await cdp.send('Input.dispatchTouchEvent', { type: 'touchMove', touchPoints: [{ x: x0 - i * 7.3, y }] });
      await cdp.send('Input.dispatchTouchEvent', { type: 'touchEnd', touchPoints: [] });
      await p.waitForTimeout(900); await note('après glisser de 44 px');
    }
  }
  return constats;
};

(async () => {
  const exe = fs.existsSync('/opt/pw-browsers/chromium') ? '/opt/pw-browsers/chromium' : undefined;
  const nav = await chromium.launch({ executablePath: exe });
  const constats = [];
  for (const [nom, w, h] of ECRANS) {
    const ctx = await nav.newContext({ viewport: { width: w, height: h }, hasTouch: w < 500, isMobile: w < 500 });
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
      await p.goto(URL.replace('#', '?t=' + Date.now() + '#'));  // nouvelle adresse : vrai rechargement
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
        constats.push(...await controlerEtats(p, nom, t, w < 500));
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
