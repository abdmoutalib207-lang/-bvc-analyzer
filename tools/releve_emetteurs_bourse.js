#!/usr/bin/env node
/*
 * Relevé de la liste officielle des émetteurs — Bourse de Casablanca.
 * LECTURE SEULE : ouvre une page publique, déplie chaque émetteur, écrit
 * datasets/bourse_emetteurs.json. Ne touche à aucune autre donnée.
 *
 * Comment la page livre ses données (constaté le 20/10/2026) :
 *   - le tableau des émetteurs est dans le HTML ;
 *   - le détail d'un émetteur apparaît au clic sur le chevron (button.expand-btn),
 *     SANS requête réseau : la page le tire d'un bloc JSON embarqué
 *     (drupal-settings-json, clé boursenova.emetteurs) ;
 *   - le détail AFFICHÉ donne : intitulé, type, nombre de titres, compartiment.
 *     Il n'affiche ni code, ni ISIN, ni statut.
 * On relève donc ce que le dépliage affiche, et le CODE depuis le bloc embarqué
 * de la même page, apparié ligne à ligne (intitulé + type + nombre de titres).
 * Un code qui ne s'apparie pas exactement vaut null. Rien n'est inventé.
 *
 * TLS : vérification stricte du navigateur, aucun contournement.
 *
 * Variables d'environnement :
 *   BVC_PLAYWRIGHT   module playwright  (défaut /home/user/-bvc-analyzer/node_modules/playwright)
 *   BVC_CHROMIUM     exécutable Chromium (défaut /opt/pw-browsers/chromium)
 *   BVC_SORTIE       fichier de sortie   (défaut datasets/bourse_emetteurs.json)
 */
'use strict';
const fs = require('fs');
const path = require('path');
const crypto = require('crypto');

const URL_SOURCE = 'https://www.casablanca-bourse.com/emetteurs/liste-emetteurs';
const RACINE = path.resolve(__dirname, '..');
const MOD_PW = process.env.BVC_PLAYWRIGHT || '/home/user/-bvc-analyzer/node_modules/playwright';
const EXE = process.env.BVC_CHROMIUM || '/opt/pw-browsers/chromium';
const SORTIE = process.env.BVC_SORTIE || path.join(RACINE, 'datasets', 'bourse_emetteurs.json');

const STATUTS = /\b(suspendu[e]?s?|radi[ée]e?s?|en liquidation|liquidation|retir[ée]e?|délist[ée]e?)\b/i;
const sha256 = (s) => crypto.createHash('sha256').update(s, 'utf8').digest('hex');
const propre = (s) => (s == null ? null : String(s).replace(/\s+/g, ' ').trim() || null);

// « 1,053,404 » → 1053404 ; tout autre format → null (la forme brute est gardée à côté).
function entier(txt) {
  const t = propre(txt);
  if (!t) return null;
  if (/^\d{1,3}(,\d{3})*$/.test(t) || /^\d+$/.test(t)) return parseInt(t.replace(/,/g, ''), 10);
  return null;
}

async function main() {
  const { chromium } = require(MOD_PW);
  const nav = await chromium.launch({ executablePath: EXE });
  const page = await nav.newPage();
  const requetesClic = [];
  try {
    await page.goto(URL_SOURCE, { waitUntil: 'networkidle', timeout: 120000 });

    const embarque = await page.evaluate(() => {
      const el = document.querySelector('script[data-drupal-selector="drupal-settings-json"]');
      if (!el) return null;
      try { return (JSON.parse(el.textContent).boursenova || {}).emetteurs || null; } catch (e) { return null; }
    });
    const texteEmbarque = embarque ? JSON.stringify(embarque) : null;

    page.on('request', (r) => requetesClic.push({ methode: r.method(), url: r.url(), type: r.resourceType() }));

    const boutons = page.locator('button.expand-btn');
    const n = await boutons.count();
    const enregistrements = [];
    const anomalies = [];
    const emetteurs = [];

    for (let k = 0; k < n; k++) {
      const btn = boutons.nth(k);
      const ligne = btn.locator('xpath=ancestor::tr[1]');
      const nom = propre(await ligne.locator('.em-emetteur-name').innerText().catch(() => null));
      const secteur = propre(await ligne.locator('.em-secteur').innerText().catch(() => null));
      const badge = propre(await ligne.locator('.em-inst-badge').innerText().catch(() => null));
      const nAnnonce = badge && /^(\d+)\s+instruments?$/.test(badge) ? parseInt(badge, 10) : null;
      const dataId = await btn.getAttribute('data-id');
      const statutLigne = (propre(await ligne.innerText()) || '').match(STATUTS);

      await btn.scrollIntoViewIfNeeded();
      await btn.click();
      const detail = ligne.locator('xpath=following-sibling::tr[1]');
      await detail.locator('table.inner-table').waitFor({ state: 'visible', timeout: 15000 });
      const lignes = await detail.locator('table.inner-table tbody tr').evaluateAll((trs) =>
        trs.map((tr) => Array.from(tr.querySelectorAll('td')).map((td) => td.innerText)));
      const texteDetail = propre(await detail.innerText()) || '';

      // Bloc embarqué correspondant : même rang ET même nom, sinon on n'en tire rien.
      let emb = null;
      const idx = dataId != null && /^\d+$/.test(dataId) ? parseInt(dataId, 10) : null;
      if (embarque && idx != null && embarque[idx] && propre((embarque[idx].label || {}).fr) === nom) emb = embarque[idx];
      else anomalies.push({ emetteur: nom, anomalie: 'bloc embarqué non apparié — codes laissés à null' });

      const utilises = new Set();
      for (const cells of lignes) {
        const [intitule, type, nbTxt, compartiment] = cells.map(propre);
        const nb = entier(nbTxt);
        let code = null;
        if (emb) {
          const cands = (emb.instruments || []).map((ins, j) => ({ ins, j })).filter(({ ins, j }) =>
            !utilises.has(j) && propre((ins.label || {}).fr) === intitule &&
            propre((ins.type || {}).fr) === type && ins.shares === nb);
          if (cands.length === 1) { utilises.add(cands[0].j); code = propre(cands[0].ins.symbol); }
          else anomalies.push({ emetteur: nom, instrument: intitule, anomalie: `code non apparié (${cands.length} candidats)` });
        }
        const isin = (cells.join(' ').match(/\bMA\d{10}\b/) || [null])[0];
        const st = cells.join(' ').match(STATUTS) || statutLigne;
        enregistrements.push({
          emetteur: nom,
          secteur,
          instrument: intitule,
          type_instrument: type,
          code,
          code_origine: code ? 'bloc_json_embarque_de_la_page' : null,
          isin: isin || null,
          nombre_titres: nb,
          nombre_titres_affiche: nbTxt,
          compartiment,
          statut: st ? propre(st[0]) : null,
        });
      }
      if (nAnnonce != null && nAnnonce !== lignes.length)
        anomalies.push({ emetteur: nom, anomalie: `badge ${nAnnonce} instrument(s), ${lignes.length} ligne(s) dépliée(s)` });
      emetteurs.push({ emetteur: nom, secteur, instruments_annonces: nAnnonce, instruments_deplies: lignes.length, isin_dans_detail: /\bMA\d{10}\b/.test(texteDetail) });
    }

    const texte = await page.innerText('body');
    // Seules comptent les requêtes vers le site de la Bourse ; la mesure d'audience
    // (Google Analytics) est comptée à part et son URL n'est pas conservée.
    const duSite = requetesClic.filter((r) => /^https:\/\/(www\.)?casablanca-bourse\.com\//.test(r.url));
    const json = duSite.filter((r) => r.type === 'xhr' || r.type === 'fetch');
    const sortie = {
      _quoi: "Relevé de la liste officielle des émetteurs de la Bourse de Casablanca : un enregistrement par instrument déplié. Lecture seule ; aucun champ inventé (absent = null).",
      _comment: "Dépliage de chaque émetteur par son chevron (button.expand-btn). Le détail affiché ne porte ni code, ni ISIN, ni statut ; le code vient du bloc JSON embarqué dans la même page (drupal-settings-json), apparié par intitulé + type + nombre de titres.",
      releve_le: new Date().toISOString(),
      url_source: URL_SOURCE,
      sha256_texte_page: sha256(texte),
      sha256_texte_page_portee: 'innerText du <body> après dépliage de tous les émetteurs (contient la date du jour et l\'état de séance affichés en tête)',
      sha256_bloc_embarque: texteEmbarque ? sha256(texteEmbarque) : null,
      requetes_pendant_depliage: { vers_le_site: duSite.length, xhr_fetch_vers_le_site: json.map((r) => r.url), autres_hotes: requetesClic.length - duSite.length },
      n_emetteurs: emetteurs.length,
      n_instruments: enregistrements.length,
      n_emetteurs_bloc_embarque: embarque ? embarque.length : null,
      emetteurs,
      enregistrements,
      anomalies,
    };
    fs.mkdirSync(path.dirname(SORTIE), { recursive: true });
    fs.writeFileSync(SORTIE, JSON.stringify(sortie, null, 1) + '\n');
    console.log(`${emetteurs.length} émetteurs, ${enregistrements.length} instruments, ${anomalies.length} anomalie(s), ` +
      `${duSite.length} requête(s) vers le site pendant le dépliage (${json.length} xhr/fetch) → ${path.relative(RACINE, SORTIE)}`);
  } finally {
    await nav.close();
  }
}

main().catch((e) => { console.error('ÉCHEC du relevé :', e.message); process.exit(1); });
