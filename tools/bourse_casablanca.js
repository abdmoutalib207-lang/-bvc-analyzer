#!/usr/bin/env node
/*
 * Bourse de Casablanca — lecture du site public. LECTURE SEULE.
 *
 *   node tools/bourse_casablanca.js accueil        → JSON sur la sortie standard
 *   node tools/bourse_casablanca.js publications   → JSON sur la sortie standard
 *
 * Aucun fichier écrit, aucune donnée du dépôt touchée. Un champ absent vaut null :
 * rien n'est déduit ni complété.
 *
 * TLS : vérification stricte du navigateur. `curl` refuse la chaîne de
 * certificats du site (mesuré le 20/10/2026) ; Chromium l'accepte en strict.
 * Aucun contournement (ni ignoreHTTPSErrors, ni --ignore-certificate-errors).
 *
 * Ce que lit chaque commande (constaté le 20/10/2026) :
 *   accueil
 *     - page d'accueil : date du jour affichée, état de séance, CAPITALISATION,
 *       VOLUME GLOBAL, MASI (valeur + variation). Le carrousel duplique ses
 *       blocs : la première occurrence est retenue, les suivantes doivent être
 *       identiques, sinon une anomalie est rendue.
 *     - /market-data/volume, page vers laquelle pointe « VOLUME GLOBAL » : la
 *       séance qu'elle annonce (« Séance du JJ/MM/AAAA ») et la décomposition
 *       par sous-marché (bloc JSON embarqué boursenova.volume_data). C'est ce
 *       qui permet de MESURER le périmètre du volume global, au lieu de le
 *       supposer.
 *     - l'historique des volumes de cette même page (export CSV,
 *       /api/boursenova/volume/download), lu par fetch DANS la page — donc sous
 *       la même vérification TLS — sur les 14 derniers jours.
 *   publications
 *     - le bloc « Publications » de l'accueil (les plus récentes, sans date
 *       affichée) ; la date du fichier est relevée par l'en-tête HTTP
 *       Last-Modified du PDF (HEAD), étiquetée comme telle ;
 *     - /apropos/publications/emetteurs, BVC_PAGES_PUBLICATIONS pages (défaut 1).
 *       ⚠️ Relevé du 20/10 : 66 pages, de 2009 à 2021 ; les publications de
 *       2026 n'y figurent pas, seul l'accueil les montre.
 *
 * Variables d'environnement :
 *   BVC_PLAYWRIGHT          module playwright (défaut /home/user/-bvc-analyzer/node_modules/playwright)
 *   BVC_CHROMIUM            exécutable Chromium (défaut /opt/pw-browsers/chromium s'il existe ;
 *                           vide ou absent du disque → celui que Playwright a installé)
 *   BVC_PAGES_PUBLICATIONS  pages de la liste des publications à lire (défaut 1)
 */
'use strict';
const fs = require('fs');

const SITE = 'https://www.casablanca-bourse.com';
const MOD_PW = process.env.BVC_PLAYWRIGHT || '/home/user/-bvc-analyzer/node_modules/playwright';
const EXE_DEFAUT = '/opt/pw-browsers/chromium';
const EXE = process.env.BVC_CHROMIUM !== undefined ? process.env.BVC_CHROMIUM : EXE_DEFAUT;

const MOIS = { janvier: 1, fevrier: 2, mars: 3, avril: 4, mai: 5, juin: 6, juillet: 7, aout: 8,
  septembre: 9, octobre: 10, novembre: 11, decembre: 12 };
const sansAccent = (s) => s.normalize('NFD').replace(/[̀-ͯ]/g, '');
const propre = (s) => (s == null ? null : String(s).replace(/[\s  ]+/g, ' ').trim() || null);
const iso = (a, m, j) => `${a}-${String(m).padStart(2, '0')}-${String(j).padStart(2, '0')}`;

// « 998 007 899 516 » → 998007899516 ; « 16 966,23 » → 16966.23 ; « 113 956 983.12 » → 113956983.12.
// Tout autre format → null : un nombre qu'on ne sait pas lire n'est pas un nombre.
function nombre(txt) {
  const t = propre(txt);
  if (!t) return null;
  const m = t.replace(/[\s]/g, '').match(/^([+-]?)(\d+)(?:[.,](\d+))?$/);
  if (!m) return null;
  return parseFloat(`${m[1]}${m[2]}.${m[3] || '0'}`);
}

const centimes = (x) => (typeof x === 'number' && isFinite(x) ? Math.round(x * 100) / 100 : null);

// « -0,06% » → -0.06 (en points de pourcentage).
function pourcentage(txt) {
  const t = propre(txt);
  if (!t || !/%$/.test(t)) return null;
  return nombre(t.replace(/%$/, ''));
}

// « Mardi 20 octobre 2026 » → 2026-10-20.
function dateLongue(txt) {
  const m = sansAccent(propre(txt) || '').toLowerCase()
    .match(/^(?:lundi|mardi|mercredi|jeudi|vendredi|samedi|dimanche)\s+(\d{1,2})(?:er)?\s+([a-z]+)\s+(\d{4})$/);
  return m && MOIS[m[2]] ? iso(m[3], MOIS[m[2]], m[1]) : null;
}

// « 20/10/2026 » → 2026-10-20.
function dateCourte(txt) {
  const m = (propre(txt) || '').match(/^(\d{2})\/(\d{2})\/(\d{4})$/);
  return m ? iso(m[3], m[2], m[1]) : null;
}

/* Analyse du texte visible de l'accueil (innerText du <body>). Fonction pure. */
function analyserAccueil(texte) {
  const lignes = String(texte || '').split(/\r?\n/).map(propre).filter(Boolean);
  const anomalies = [];
  let dateAffichee = null;
  let etat = null;
  for (const l of lignes.slice(0, 15)) {
    if (!dateAffichee && dateLongue(l)) dateAffichee = dateLongue(l);
    if (!etat && /^s[ée]ance\s+\S/i.test(l) && !/^s[ée]ance du\b/i.test(l)) etat = l;
  }
  // Un bloc = un libellé exact, suivi de ses lignes de valeur. Toutes les
  // occurrences sont relevées ; elles doivent concorder.
  function bloc(libelle, lire) {
    const vus = [];
    lignes.forEach((l, i) => { if (l === libelle) vus.push(lire(lignes.slice(i + 1, i + 3))); });
    const ok = vus.filter((v) => v != null);
    if (!ok.length) return null;
    const ref = JSON.stringify(ok[0]);
    if (ok.some((v) => JSON.stringify(v) !== ref))
      anomalies.push({ bloc: libelle, anomalie: 'occurrences discordantes', valeurs: ok });
    return ok[0];
  }
  const enMAD = ([v, unite]) => (unite === 'MAD' && nombre(v) != null ? nombre(v) : null);
  const indice = ([v, n]) => (pourcentage(v) != null && nombre(n) != null
    ? { valeur: nombre(n), variation_pct: pourcentage(v) } : null);
  const masi = bloc('MASI', indice);
  return {
    date_affichee: dateAffichee,
    etat_seance: etat,
    capitalisation_mad: bloc('CAPITALISATION', enMAD),
    volume_global_mad: bloc('VOLUME GLOBAL', enMAD),
    masi: masi ? masi.valeur : null,
    masi_variation_pct: masi ? masi.variation_pct : null,
    masi20: (bloc('MASI 20', indice) || {}).valeur ?? null,
    anomalies,
  };
}

/* La page /market-data/volume : texte visible + bloc boursenova.volume_data. Fonction pure. */
function analyserPageVolume(texte, volumeData) {
  const m = String(texte || '').match(/S[ée]ance du\s+(\d{2}\/\d{2}\/\d{4})/);
  const vd = volumeData || {};
  const info = ((vd.MARKET_INFO || {}).comptant) || {};
  const sous = ((vd.SUB_MARKET_DATA || {}).comptant || []).map((s) => ({
    marche: propre(s.name),
    volume_mad: centimes(typeof s.volume === 'number' ? s.volume : nombre(s.volume)),
  }));
  return {
    seance: m ? dateCourte(m[1]) : null,
    volume_global_mad: centimes(typeof info.totalVol === 'number' ? info.totalVol : nombre(info.volume)),
    quantites_echangees: typeof info.transactions === 'number' ? info.transactions : null,
    sous_marches: sous,
  };
}

/* Export CSV de l'historique des volumes. Fonction pure.
 * « Séance;Marché;Volume (MAD);Transactions;Titres échangés »
 * « 19/10/2026;Marché central;113 956 983.12;3 671;876 356 » */
function analyserHistoriqueCsv(csv) {
  const lignes = String(csv || '').replace(/^﻿/, '').split(/\r?\n/).filter((l) => l.trim());
  if (!lignes.length || !/^s[ée]ance;/i.test(lignes[0])) return null;
  return lignes.slice(1).map((l) => {
    const [s, marche, vol, tr, ti] = l.split(';');
    return { seance: dateCourte(s), marche: propre(marche), volume_mad: nombre(vol),
      transactions: nombre(tr), titres: nombre(ti) };
  }).filter((r) => r.seance);
}

// « Ennakl Automobiles - Résultats… » / « IAM : 2016 consolidated results » → l'émetteur.
// Sans séparateur, l'émetteur n'est pas dans le titre : null, jamais deviné.
function emetteurDuTitre(titre) {
  const t = propre(titre) || '';
  const m = t.match(/^(.+?)\s+(?:-|–|:)\s+\S/);
  return m ? propre(m[1]) : null;
}

// /sites/default/files/pemetteur/2026-10/x.pdf → « 2026-10 » (mois du DOSSIER de dépôt sur le
// site, pas une date de publication : les archives de 2009 y sont rangées sous 2026-07).
function moisDossier(url) {
  const m = String(url || '').match(/\/pemetteur\/(\d{4}-\d{2})\//);
  return m ? m[1] : null;
}

async function ouvrir() {
  const { chromium } = require(MOD_PW);
  const opts = {};
  if (EXE && fs.existsSync(EXE)) opts.executablePath = EXE;
  return chromium.launch(opts);
}

async function accueil(nav) {
  const page = await nav.newPage();
  await page.goto(SITE + '/', { waitUntil: 'networkidle', timeout: 120000 });
  const a = analyserAccueil(await page.innerText('body'));

  const pv = await nav.newPage();
  await pv.goto(SITE + '/market-data/volume', { waitUntil: 'networkidle', timeout: 120000 });
  const vd = await pv.evaluate(() => {
    const el = document.querySelector('script[data-drupal-selector="drupal-settings-json"]');
    try { return (JSON.parse(el.textContent).boursenova || {}).volume_data || null; } catch (e) { return null; }
  });
  const v = analyserPageVolume(await pv.innerText('body'), vd);

  // Historique : 14 jours jusqu'à la séance annoncée (ou la date affichée).
  let historique = null;
  let historiqueErreur = null;
  const fin = v.seance || a.date_affichee;
  if (fin) {
    const d = new Date(fin + 'T00:00:00Z');
    const debut = new Date(d.getTime() - 14 * 86400000).toISOString().slice(0, 10);
    const url = `/api/boursenova/volume/download?from=${debut}&to=${fin}&marche=XCAS`;
    const rep = await pv.evaluate(async (u) => {
      try { const r = await fetch(u); return { s: r.status, t: await r.text() }; } catch (e) { return { s: 0, t: String(e) }; }
    }, url);
    if (rep.s === 200) historique = analyserHistoriqueCsv(rep.t);
    if (historique == null) historiqueErreur = `HTTP ${rep.s}`;
  }
  return {
    _quoi: "Page d'accueil de la Bourse de Casablanca, et page des volumes vers laquelle pointe « VOLUME GLOBAL ». Lecture seule ; absent = null.",
    releve_le: new Date().toISOString(),
    url_source: SITE + '/',
    ...a,
    page_volume: { url_source: SITE + '/market-data/volume', ...v },
    historique_volumes: historique,
    historique_erreur: historiqueErreur,
  };
}

async function publications(nav) {
  const page = await nav.newPage();
  await page.goto(SITE + '/', { waitUntil: 'networkidle', timeout: 120000 });
  const recentes = await page.$$eval('li.info-item', (lis) => lis.map((li) => {
    const a = li.querySelector('a.download-link[href]');
    const h = li.querySelector('h6');
    return a && /\/pemetteur\//.test(a.getAttribute('href')) ? { titre: h ? h.innerText : null, url: a.href } : null;
  }).filter(Boolean));
  // Date du fichier : en-tête Last-Modified, par HEAD dans la page (même TLS strict).
  for (const r of recentes) {
    r.fichier_modifie_le = await page.evaluate(async (u) => {
      try { const x = await fetch(u, { method: 'HEAD' }); return x.ok ? x.headers.get('last-modified') : null; } catch (e) { return null; }
    }, r.url);
  }

  const n = Math.max(0, parseInt(process.env.BVC_PAGES_PUBLICATIONS || '1', 10) || 0);
  const liste = [];
  let nPages = null;
  for (let k = 0; k < n; k++) {
    await page.goto(`${SITE}/apropos/publications/emetteurs?page=${k}`, { waitUntil: 'domcontentloaded', timeout: 120000 });
    const cartes = await page.$$eval('article.pub-card', (as) => as.map((a) => ({
      type_site: (a.querySelector('.pub-type-badge') || {}).innerText || null,
      date: (a.querySelector('.pub-date') || {}).innerText || null,
      titre: (a.querySelector('.pub-title') || {}).innerText || null,
      url: (a.querySelector('a.btn-download') || {}).href || null,
    })));
    if (nPages == null) {
      nPages = await page.$$eval('.pager__item--last a[href]', (as) => {
        const m = as.length ? as[0].getAttribute('href').match(/page=(\d+)/) : null;
        return m ? parseInt(m[1], 10) + 1 : null;
      });
    }
    if (!cartes.length) break;
    liste.push(...cartes);
  }

  const norm = (x, origine) => {
    const d = propre(x.date);
    return {
      date: d && /^\d{4}-\d{2}-\d{2}$/.test(d) ? d : null,
      emetteur: emetteurDuTitre(x.titre),
      titre: propre(x.titre),
      url: x.url || null,
      type_site: propre(x.type_site) || null,
      mois_dossier: moisDossier(x.url),
      fichier_modifie_le: x.fichier_modifie_le ? new Date(x.fichier_modifie_le).toISOString().slice(0, 10) : null,
      origine,
    };
  };
  const out = [...recentes.map((x) => norm(x, 'accueil')), ...liste.map((x) => norm(x, 'liste'))];
  // Un même PDF vu aux deux endroits n'est compté qu'une fois (l'entrée datée prime).
  const parUrl = new Map();
  for (const p of out) {
    const deja = parUrl.get(p.url);
    if (!deja || (!deja.date && p.date)) parUrl.set(p.url, { ...deja, ...p, fichier_modifie_le: p.fichier_modifie_le || (deja || {}).fichier_modifie_le || null });
  }
  return {
    _quoi: "Publications d'émetteurs listées par la Bourse de Casablanca. Lecture seule ; absent = null. « mois_dossier » est le dossier de dépôt sur le site, pas une date de publication ; « fichier_modifie_le » est l'en-tête HTTP Last-Modified du PDF.",
    releve_le: new Date().toISOString(),
    url_source: [SITE + '/', SITE + '/apropos/publications/emetteurs'],
    pages_liste_lues: n,
    pages_liste_total: nPages,
    publications: [...parUrl.values()],
  };
}

async function main() {
  const cmd = process.argv[2];
  const f = { accueil, publications }[cmd];
  if (!f) {
    console.error('usage : node tools/bourse_casablanca.js accueil|publications');
    process.exit(2);
  }
  const nav = await ouvrir();
  try {
    process.stdout.write(JSON.stringify(await f(nav), null, 1) + '\n');
  } finally {
    await nav.close();
  }
}

module.exports = { analyserAccueil, analyserPageVolume, analyserHistoriqueCsv, emetteurDuTitre, moisDossier, nombre, pourcentage, dateLongue };

if (require.main === module) {
  main().catch((e) => { console.error('ÉCHEC de la lecture :', e.message); process.exit(1); });
}
