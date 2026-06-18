#!/usr/bin/env python3
"""
BVC Validator — pipeline/validate.py
Vérifie l'intégrité de bpa.json, fondamentaux.json et news.json.
Exit 1 si des erreurs critiques sont détectées.
"""
import json, sys, re
from pathlib import Path
from datetime import datetime, timedelta

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

try:
    from bvc_config import ISIN_MAP, TICKERS_ALL
except ImportError:
    import warnings
    warnings.warn("bvc_config introuvable — TICKERS_ALL=[] : la vérification de couverture est désactivée")
    TICKERS_ALL, ISIN_MAP = [], {}

errors: list = []
warnings: list = []

def ok(msg):    print(f"  ✅ {msg}")
def warn(msg):  warnings.append(msg); print(f"  ⚠️  {msg}")
def err(msg):   errors.append(msg);   print(f"  ❌ {msg}")
def hdr(title): print(f"\n── {title} {'─'*(55-len(title))}")

VALID_SENTIMENTS      = {"POSITIF", "NEGATIF", "NEUTRE"}
# Champs obligatoires dans fondamentaux.json (bpa_2025/dps_2025 sont optionnels — FY anciens)
REQUIRED_FOND_FIELDS  = ["secteur","per","croissance_ca","dette_nette_ebitda",
                          "roic","marge_nette","source","date_maj"]
OPTIONAL_FOND_FIELDS  = ["bpa_2025","dps_2025"]
REQUIRED_ARTICLE_FLDS = ["title","url","date","sentiment","tickers"]


# ── bpa.json ──────────────────────────────────────────────────────────────────
def validate_bpa():
    hdr("bpa.json")
    path = ROOT / "bpa.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        err(f"Lecture impossible : {e}"); return

    ok(f"{len(data)} tickers chargés")

    no_bpa, neg_bpa, neg_div, missing_flds = [], [], [], []

    for ticker, v in data.items():
        if not isinstance(v, dict):
            err(f"{ticker} : structure non-dict"); continue
        bpa     = v.get("bpa")
        # Le champ dividende est div_dh dans les entrées mises à jour, div dans les anciennes
        div_val = v.get("div_dh") if "div_dh" in v else v.get("div")
        if bpa is None:
            no_bpa.append(ticker)
        elif bpa < 0:
            neg_bpa.append(f"{ticker}(bpa={bpa})")
        if div_val is not None and div_val < 0:
            neg_div.append(f"{ticker}(div={div_val})")
        if "bpa" not in v:
            missing_flds.append(f"{ticker}.bpa")

    if neg_bpa:
        err(f"BPA négatifs ({len(neg_bpa)}) : {', '.join(neg_bpa[:8])}")
    elif no_bpa:
        warn(f"BPA manquants ({len(no_bpa)}) : {', '.join(no_bpa[:8])}")
    else:
        ok("Tous les BPA > 0")

    if neg_div:
        err(f"Dividendes négatifs : {', '.join(neg_div)}")

    if missing_flds:
        err(f"Champs manquants : {', '.join(missing_flds[:8])}")
    else:
        ok("Champs requis présents (bpa, div)")

    missing_tickers = [t for t in TICKERS_ALL if t not in data]
    if missing_tickers:
        warn(f"{len(missing_tickers)} tickers sans BPA : {', '.join(missing_tickers[:10])}")
    else:
        ok(f"Couverture complète ({len(TICKERS_ALL)} tickers TICKERS_ALL)")


# ── fondamentaux.json ─────────────────────────────────────────────────────────
def validate_fondamentaux():
    hdr("fondamentaux.json")
    path = ROOT / "fondamentaux.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        err(f"Lecture impossible : {e}"); return

    ok(f"{len(data)} tickers avec données fondamentales")

    issues, stale = [], []
    cutoff_180 = (datetime.now() - timedelta(days=180)).strftime("%Y-%m-%d")

    for ticker, v in data.items():
        if not isinstance(v, dict):
            err(f"{ticker} : structure non-dict"); continue

        missing = [f for f in REQUIRED_FOND_FIELDS if f not in v]
        if missing:
            issues.append(f"{ticker} : manquants [{', '.join(missing)}]")
        # Champs optionnels (FY2025) — avertissement seulement
        missing_opt = [f for f in OPTIONAL_FOND_FIELDS if f not in v]
        if missing_opt and "bpa_2025" not in v:
            warn(f"{ticker} : sans bpa_2025/dps_2025 (données FY non renseignées)")

        bpa   = v.get("bpa_2025")
        per   = v.get("per")
        marge = v.get("marge_nette")
        roic  = v.get("roic")

        if bpa is not None and bpa < 0:
            issues.append(f"{ticker} : bpa_2025={bpa} négatif")
        if per is not None and (per < 0 or per > 2000):
            issues.append(f"{ticker} : per={per} hors plage [0–2000]")
        if marge is not None and (marge < -200 or marge > 100):
            issues.append(f"{ticker} : marge_nette={marge}% hors plage")
        if roic is not None and (roic < -100 or roic > 100):
            issues.append(f"{ticker} : roic={roic}% hors plage")

        date_maj = v.get("date_maj","")
        if date_maj and date_maj < cutoff_180:
            stale.append(f"{ticker}({date_maj})")

    if issues:
        for i in issues[:6]: err(i)
        if len(issues) > 6: err(f"...et {len(issues)-6} autres problèmes")
    else:
        ok("Valeurs dans plages acceptables (per/marge/roic/bpa)")

    if stale:
        warn(f"{len(stale)} entrées non mises à jour depuis 180j : {', '.join(stale[:6])}")
    else:
        ok("Données récentes (< 180 jours)")


# ── news.json ─────────────────────────────────────────────────────────────────
def validate_news():
    hdr("news.json")
    path = ROOT / "news.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        err(f"Lecture impossible : {e}"); return

    articles = data.get("articles", [])
    ok(f"{len(articles)} articles · updated={data.get('updated','?')}")

    # Fraîcheur
    updated = data.get("updated","")
    if updated:
        try:
            upd_dt = datetime.fromisoformat(updated.replace("Z","").split(".")[0])
            age_h = (datetime.now() - upd_dt).total_seconds() / 3600
            if age_h > 48:
                warn(f"news.json vieux de {age_h:.0f}h (> 48h attendu)")
            else:
                ok(f"Fraîcheur OK ({age_h:.1f}h)")
        except Exception:
            warn(f"Format date invalide : {updated}")

    valid_tickers_set = set(TICKERS_ALL) | set(ISIN_MAP.keys())
    bad_sent, missing_flds, invalid_tck, empty_tck = [], [], [], []

    for i, a in enumerate(articles[:300]):
        if not isinstance(a, dict): continue

        for f in REQUIRED_ARTICLE_FLDS:
            if f not in a:
                missing_flds.append(f"#{i}.{f}")

        sent = a.get("sentiment","")
        if sent not in VALID_SENTIMENTS:
            bad_sent.append(f"#{i}:{repr(sent)}")

        tickers = a.get("tickers", [])
        if not isinstance(tickers, list) or not tickers:
            empty_tck.append(i)
        else:
            for t in tickers:
                if t not in valid_tickers_set:
                    invalid_tck.append(f"#{i}:{t}")

    if missing_flds:
        err(f"Champs manquants dans articles : {', '.join(missing_flds[:6])}")
    else:
        ok("Champs requis présents dans tous les articles")

    if bad_sent:
        err(f"Sentiments invalides ({len(bad_sent)}) : {', '.join(bad_sent[:5])}")
    else:
        ok("Sentiments valides (POSITIF / NEGATIF / NEUTRE)")

    if invalid_tck:
        uniq = sorted(set(t.split(":")[1] for t in invalid_tck))
        warn(f"Tickers inconnus dans articles : {', '.join(uniq[:8])}")

    if empty_tck and len(empty_tck) > len(articles) * 0.6:
        warn(f"{len(empty_tck)}/{len(articles)} articles sans tickers (taux > 60%)")

    # Distribution sentiments
    dist = {s: sum(1 for a in articles if a.get("sentiment")==s) for s in VALID_SENTIMENTS}
    ok(f"Sentiment : ✅ {dist['POSITIF']} positifs · ❌ {dist['NEGATIF']} négatifs · ◦ {dist['NEUTRE']} neutres")

    # Couverture par ticker (top 10 les plus cités)
    from collections import Counter
    all_tickers = [t for a in articles for t in a.get("tickers",[])]
    top = Counter(all_tickers).most_common(10)
    if top:
        ok(f"Top tickers : {', '.join(f'{t}({c})' for t,c in top[:6])}")


# ── Résumé final ──────────────────────────────────────────────────────────────
if __name__ == "__main__":
    banner = "  BVC Analyzer — Validation Intégrité"
    print("═"*60)
    print(banner)
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("═"*60)

    validate_bpa()
    validate_fondamentaux()
    validate_news()

    print("\n" + "═"*60)
    print(f"  RÉSUMÉ : {len(errors)} erreur(s) critique(s) · {len(warnings)} avertissement(s)")
    print("═"*60)

    if errors:
        print("\n❌ ERREURS CRITIQUES — commit bloqué :")
        for e in errors:
            print(f"   → {e}")
        sys.exit(1)
    elif warnings:
        print("\n⚠️  Avertissements (non-bloquants) :")
        for w in warnings:
            print(f"   → {w}")
        print("\n✅ Données valides (avec avertissements)")
        sys.exit(0)
    else:
        print("\n✅ Toutes les vérifications passées — données saines !")
        sys.exit(0)
