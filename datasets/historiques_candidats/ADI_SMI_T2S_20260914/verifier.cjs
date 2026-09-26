// Contrôle en lecture seule du premier dossier, sans dépendance externe.
// Node.js >=18. Exécuter depuis la racine du dépôt :
// node datasets/historiques_candidats/ADI_SMI_T2S_20260914/verifier.cjs
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');

function parseExport(text,ticker,instrument) {
  const headers=["Séance","Ticker","Instrument","Ouverture","Dernier Cours","Plus Haut","Plus Bas","Volume (MAD)","Titres Échangés","Nb Transactions","Capitalisation"];
  const lines=text.replace(/^\uFEFF/,"").trim().split(/\r?\n/);
  if(JSON.stringify(lines.shift().split(";"))!==JSON.stringify(headers)) throw Error("En-tête inattendu");
  const seen=new Set();
  return lines.map((line,index)=>{
    const x=line.split(";");
    if(x.length!==11 || x[1].trim()!==ticker || x[2].trim()!==instrument) throw Error("Identité/colonnes invalides ligne "+(index+2));
    const m=/^(\d{2})\/(\d{2})\/(\d{4})$/.exec(x[0]);
    if(!m) throw Error("Date invalide");
    const d=`${m[3]}-${m[2]}-${m[1]}`;
    if(!Number.isFinite(Date.parse(d)) || new Date(d).toISOString().slice(0,10)!==d || seen.has(d)) throw Error("Date invalide ou dupliquée: "+d);
    seen.add(d);
    const numeric=x.slice(3).map(s=>{
      if(s==="-")return null;
      if(!/^\d+(?:\.\d+)?$/.test(s))throw Error("Nombre invalide: "+s);
      const n=Number(s);
      if(!Number.isFinite(n))throw Error("Nombre non fini");
      return n;
    });
    const [o,c,h,l,amount_mad,v,transactions,capitalisation_mad]=numeric;
    if(c===null||c<=0)throw Error("Dernier cours invalide: "+d);
    if([o,h,l].some(n=>n!==null && n<=0))throw Error("Prix invalide: "+d);
    if(v!==null&&!Number.isSafeInteger(v) || transactions!==null&&!Number.isSafeInteger(transactions)) throw Error("Quantité non entière");
    const full=[o,h,l,v].every(n=>n!==null);
    if([o,h,l].every(n=>n!==null) && !(l<=Math.min(o,c)&&h>=Math.max(o,c))) throw Error("OHLC incohérent: "+d);
    return {d,ticker,instrument,o,h,l,c,v,amount_mad,transactions,capitalisation_mad,details:full?"ohlcv_renseignes":"details_manquants",source_line:index+2};
  }).sort((a,b)=>a.d.localeCompare(b.d));
}

function compareExport(rows,baseline) {
  const dates=new Map(baseline.map(x=>[x.d,x]));
  if(dates.size!==baseline.length)throw Error("Date de référence dupliquée");
  return rows.map(r=>{
    const before=dates.get(r.d)??null;
    const differences=before?Object.fromEntries(["o","h","l","c","v"].filter(k=>r[k]!==null&&r[k]!==before[k]).map(k=>[k,{avant:before[k],source:r[k]}])):null;
    const unknown=["o","h","l","v"].filter(k=>r[k]===null);
    return {d:r.d,before,source:r,differences,missing_source_fields:unknown,status:before?(unknown.length?"details_source_manquants":Object.keys(differences).length?"ecart":"identique"):"absent_du_fichier"};
  });
}

function summaryIndicators(rows) {
  if(rows.some(r=>r.c===null||!Number.isFinite(r.c)))throw Error("Cours manquant");
  const c=rows.map(r=>r.c),n=c.length;
  const sma=p=>n>=p?c.slice(-p).reduce((a,b)=>a+b,0)/p:null;
  let rsi=null;
  if(n>=15){
    let gain=0,loss=0;
    for(let i=1;i<=14;i++){let v=c[i]-c[i-1];gain+=Math.max(v,0)/14;loss+=Math.max(-v,0)/14;}
    for(let i=15;i<n;i++){let v=c[i]-c[i-1];gain=(gain*13+Math.max(v,0))/14;loss=(loss*13+Math.max(-v,0))/14;}
    rsi=loss===0?(gain===0?50:100):100-100/(1+gain/loss);
  }
  return {n,first_date:rows[0]?.d??null,last_date:rows.at(-1)?.d??null,last_close:c.at(-1)??null,rsi14_wilder:rsi,sma20:sma(20),sma50:sma(50),sma200:sma(200),high_observed:Math.max(...rows.map(r=>r.h)),low_observed:Math.min(...rows.map(r=>r.l))};
}

const root = process.cwd();
const lot = path.join(__dirname);
const report = JSON.parse(fs.readFileSync(path.join(lot,'rapport_partiel.json'),'utf8'));
const result = {};
for (const ticker of ['ADI','SMI','T2S']) {
  const src = path.join(lot,'sources',ticker+(ticker==='T2S'?'':'_extraits')+'.csv');
  const rows = parseExport(fs.readFileSync(src,'utf8'),ticker,ticker==='ADI'?'ALLIANCES':ticker==='T2S'?'T2S GROUP HOLDING':'SMI');
  const file = path.join(root,'pipeline','candles',ticker+'.json');
  let baseline = [];
  if (ticker === 'T2S') {
    if (fs.existsSync(file)) throw Error('T2S existe maintenant: revalider la base avant comparaison');
    const candidate = JSON.parse(fs.readFileSync(path.join(lot,'T2S_candidat.json'),'utf8'));
    const expected = rows.map(({d,o,h,l,c,v})=>({d,o,h,l,c,v}));
    if (JSON.stringify(candidate)!==JSON.stringify(expected)) throw Error('Candidat T2S différent de la source');
    result.T2S = summaryIndicators(rows);
    if (JSON.stringify(result.T2S)!==JSON.stringify(report.T2S_independent_calculations)) throw Error('Calculs T2S différents du rapport');
  } else {
    const bytes = fs.readFileSync(file);
    const blob = crypto.createHash('sha1').update('blob '+bytes.length+'\0').update(bytes).digest('hex');
    if (blob !== report.reference_blobs[ticker]) throw Error('Base '+ticker+' modifiée: refaire la comparaison');
    baseline = JSON.parse(bytes.toString('utf8'));
    result[ticker] = compareExport(rows,baseline);
    if (JSON.stringify(result[ticker])!==JSON.stringify(report.comparisons[ticker])) throw Error('Comparaison différente du rapport: '+ticker);
  }
}
console.log(JSON.stringify({status:'controle_partiel_conforme',T2S:result.T2S,limites:report.remaining},null,2));
