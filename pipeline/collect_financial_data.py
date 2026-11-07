#!/usr/bin/env python3
"""
BVC ANALYZER DATA PIPELINE v9.0
================================
Collecte les données financières des 19 sociétés MASI 1.
Produit :
  - financial_data.json  : format v9 complet (pour analyses avancées)
  - data.json            : format legacy (pour index.html / GitHub Pages)

Usage :
  python collect_financial_data.py
  python collect_financial_data.py --dry-run
  python collect_financial_data.py --tickers MNG,SMI,ADI
"""
import argparse
import json
import logging
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

# Résolution des imports relatifs
sys.path.insert(0, str(Path(__file__).parent.parent))

from pipeline.scrapers.constants      import TICKERS, IPO_RECENT
from pipeline.scrapers.market         import fetch_market_data
from bvc_config import NOTE_METIER_PUBLIEE
from pipeline.smart_money.fond_score  import reload as fond_reload
from pipeline.smart_money.fond_score_sectoriel import detail_publie, noter_depuis_fichiers
from pipeline.technical.indicators  import compute_technical
from pipeline.utils.validation      import validate_ticker_data
from pipeline.utils.logging_config  import setup_logging

ROOT       = Path(__file__).parent
OUT_V9     = ROOT.parent / "financial_data.json"
OUT_LEGACY = ROOT.parent / "data.json"

# ⚠️ PLUS DE `fallback_data.json` — 22/10/2026 (audit).
#
# Ce fichier — une table de juillet saisie à la main, archivée sous
# `archive/fallback_data_2026-07.json` — servait de repli à TOUT ce que les
# scrapers ne rendaient pas, c'est-à-dire, depuis que Médias24 répond 403, à
# TOUS les fondamentaux et à tous les indicateurs : le run du 21/10 publiait
# `"fundamentals": "fallback"` et `"rsi": "fallback"` sur 19 titres sur 19.
# Mesuré contre data.json le même jour : ADH PER 13,85 au lieu de 29,7, SGTM
# capitalisation 5 062 MDHS au lieu de 34 800, CMT dividende 120 DH au lieu
# de 0 (« Dividende 0,00 dirhams », RFA 2025 p.79).
#
# Le repli est désormais ce que `update_data.py` — propriétaire unique de
# data.json, calculé sur les comptes déposés — a PUBLIÉ pour ce titre, avec sa
# séance. Ce qu'il ne publie pas reste `null` : on ne comble pas une absence.
# Les fondamentaux ne sont plus scrapés du tout : Médias24 / casabourse /
# Zonebourse sont des sources tierces non vérifiées, et la note du moteur ne
# les lit pas.
SOURCE_PUBLIEE = "data.json publié (update_data.py)"


def charger_publie(chemin: Path = OUT_LEGACY) -> dict:
    """Valeurs PUBLIÉES par update_data.py, par titre, au format v9. Pure en
    lecture ; `{}` si le fichier manque ou se lit mal.

    Les clés absentes de data.json valent `None` — jamais une valeur par défaut.
    """
    try:
        d = json.loads(Path(chemin).read_text(encoding="utf-8"))
    except Exception as e:                                    # noqa: BLE001
        logging.warning(f"data.json publié illisible ({e}) : aucun repli")
        return {}
    out = {}
    for t in d.get("tickers") or []:
        sym = t.get("symbol")
        if not sym:
            continue
        meta = t.get("_meta") or {}
        bpa = t.get("bpa_12m") if t.get("bpa_12m") is not None else t.get("bpa")
        out[sym] = {
            "market": {"price": t.get("price"), "open": t.get("open"),
                       "volume": t.get("vol"), "variation_pct": t.get("chg")},
            "technical": {"rsi_14": t.get("rsi"), "ma20": t.get("ma20"),
                          "ma50": t.get("ma50"), "high_90d": t.get("h90"),
                          "low_90d": t.get("l90")},
            # Mêmes champs que la fiche du terminal : PER (12 mois s'il existe,
            # sur le BPA correspondant), P/B sur faits AMMC, dividende sur pièce.
            "fundamentals": {"pe_ratio_ttm": t.get("pe"), "pe_ratio_2026e": None,
                             "pb_ratio": t.get("pb"), "eps_ttm": bpa,
                             "dividend_per_share": t.get("div_dh"),
                             "dividend_yield": t.get("div"),
                             "market_cap_mdh": t.get("cap")},
            "asof": meta.get("prix_asof"),
            "source_fond": meta.get("source_fond"),
        }
    return out


def _source_publiee(pub: dict) -> str:
    return f"{SOURCE_PUBLIEE}, séance {pub.get('asof') or 'non datée'}"


def collect_ticker(sym: str, publie: dict, dry_run: bool = False) -> tuple[str, dict]:
    """`publie` : sortie de `charger_publie()` — le seul repli admis."""
    log = logging.getLogger(sym)
    pub = publie.get(sym) or {}
    pub_market = pub.get("market") or {}
    pub_tech   = pub.get("technical") or {}
    # Toutes les clés, `None` comprises : un fondamental absent de data.json
    # est publié `null`, et `_sources` dit pourquoi.
    pub_fund   = dict(pub.get("fundamentals") or dict.fromkeys(
        ["pe_ratio_ttm", "pe_ratio_2026e", "pb_ratio", "eps_ttm",
         "dividend_per_share", "dividend_yield", "market_cap_mdh"]))
    src_pub    = _source_publiee(pub) if pub else "non_disponible (titre absent de data.json)"

    result = {
        "market":                {},
        "technical":             {},
        "fundamentals":          {},
        "financials_performance":{},
        "flags": {
            "stale":        False,
            "partial_data": sym in IPO_RECENT,
            "ipo_recent":   sym in IPO_RECENT,
        },
        "_sources": {},
    }

    if dry_run:
        log.info("DRY-RUN — valeurs publiées de data.json uniquement")
        result["market"]       = {k: v for k, v in pub_market.items() if v is not None}
        result["technical"]    = {k: v for k, v in pub_tech.items() if v is not None}
        result["fundamentals"] = pub_fund
        result["flags"]["stale"] = True
        result["_sources"] = {"all": f"{src_pub} (dry-run)"}
        return sym, result

    # ── 1. Données de marché ─────────────────────────────────────────────────
    try:
        market = fetch_market_data(sym)
        if market and market.get("price"):
            result["_sources"]["price"] = market.pop("_source", "live")
            result["market"] = market
        else:
            raise ValueError("no price")
    except Exception as e:
        log.warning(f"market FAIL: {e} → valeurs publiées de data.json")
        result["market"] = {k: v for k, v in pub_market.items() if v is not None}
        result["flags"]["stale"] = True
        result["_sources"]["price"] = src_pub

    # ── 2. Indicateurs techniques (RSI calculé) ──────────────────────────────
    try:
        tech = compute_technical(sym)
        if tech and tech.get("rsi_14") is not None:
            result["_sources"]["technical"] = tech.pop("_source", "calculated")
            result["_sources"]["rsi"]       = "calculated_wilder_ema"
            result["technical"] = tech
        else:
            raise ValueError("RSI non calculé")
    except Exception as e:
        log.warning(f"technical FAIL: {e} → valeurs publiées de data.json")
        result["technical"] = {k: v for k, v in pub_tech.items() if v is not None}
        result["flags"]["stale"] = True
        result["_sources"]["rsi"] = src_pub

    # ── 3. Fondamentaux ──────────────────────────────────────────────────────
    # ⚠️ 22/10/2026 : ceux que le moteur PUBLIE (comptes déposés, voir en tête
    # de fichier), jamais scrapés ni tirés d'une table figée. Absents : `null`.
    result["fundamentals"] = pub_fund
    result["_sources"]["fundamentals"] = src_pub

    # ── 4. Performance financière ── désactivé
    #    fetch_financials scrape des articles de presse Médias24 (jusqu'à 20 req/ticker)
    #    et n'a jamais retourné de données (CA={}, RN={} sur tous les tickers).
    #    Non consommé par to_legacy_format() ni par fond_score.py.
    #    Cause principale du timeout à 20 min — à réactiver avec une source API structurée.

    # ── 5. Smart Money ── retiré le 29/10/2026
    #    `pipeline/smart_money/alpha.py` servait des constantes écrites en dur
    #    (alpha 12 mois, taux de réussite, sentiment) tirées du corpus WhatsApp.
    #    Retrait du pilier NLP (décision d'Abd Moutalib du 28/10, lot 2) :
    #    plus de bloc `smart_money` dans financial_data.json.

    # ── 6. Flags ──────────────────────────────────────────────────────────────
    has_price  = bool(result["market"].get("price"))
    has_rsi    = bool(result["technical"].get("rsi_14"))
    has_per    = bool(result["fundamentals"].get("pe_ratio_ttm"))
    if not all([has_price, has_rsi, has_per]) or sym in IPO_RECENT:
        result["flags"]["partial_data"] = True

    result = validate_ticker_data(result, sym)

    log.info(
        f"✓ price={result['market'].get('price')} "
        f"RSI={result['technical'].get('rsi_14')} "
        f"PER={result['fundamentals'].get('pe_ratio_ttm')} "
        f"stale={result['flags']['stale']} partial={result['flags']['partial_data']}"
    )
    return sym, result


# ── Conversion format legacy (data.json pour index.html) ─────────────────────

def to_legacy_format(pipeline_out: dict) -> dict:
    """Convertit le format v9 → format data.json consommé par index.html."""
    # ⚠️ NOTE FONDAMENTALE PAR FAMILLE — second point d'application (avec
    # `update_data.appliquer_note_sectorielle`) : les deux bougent ENSEMBLE, selon
    # `bvc_config.NOTE_METIER_PUBLIEE`. Elle est jointe (`note_fond_metier`) ; en
    # mode comparaison (faux), sa panne n'interrompt pas la publication. Les valorisations étant RELATIVES,
    # elle a besoin des cours de tout l'univers : ce pipeline ne couvre que ses
    # propres titres, le reste vient du data.json publié.
    try:
        notes = noter_depuis_fichiers({s: (d.get("market") or {}).get("price")
                                       for s, d in pipeline_out.get("data", {}).items()})
    except Exception as exc:                                   # noqa: BLE001 — isolation voulue
        if NOTE_METIER_PUBLIEE:
            raise                                              # la note publiée en dépend
        # Comparaison : sa panne ne doit pas interrompre la publication (12/10/2026).
        logging.warning(f"note par famille (comparaison) indisponible : {type(exc).__name__}: {exc}")
        notes = {}

    tickers = []
    for sym, d in pipeline_out.get("data", {}).items():
        m  = d.get("market", {})
        t  = d.get("technical", {})
        f  = d.get("fundamentals", {})

        # ⚠️ 06/11/2026 — RETRAIT DE LA NOTE v5.3 (lot 2, décision d'Abd
        # Moutalib : « l'ancien scoring doit disparaître »). Ce fichier portait
        # la SECONDE formule du score (Tech 27,78 % + Fond 72,22 %, écrite en
        # dur ici quand `update_data.py` la modulait par titre) et ses paliers
        # ACHETER … ÉVITER FORT. Les deux points d'application de R8 bougent
        # ENSEMBLE : `v53`, `score_fond` et `sig` ne sont plus émis ici non
        # plus. Le score publié est le Score BVC, calculé par update_data.py
        # (propriétaire unique de data.json).
        rsi    = t.get("rsi_14") or 50   # inchangé (repli 50 : hors du périmètre de ce lot)

        tickers.append({
            "symbol":   sym,
            "price":    m.get("price"),
            "open":     m.get("open"),
            "close":    m.get("price"),
            # None si non servie (R9, 22/10/2026) : une variation absente n'est pas 0,00 %.
            "chg":      m.get("variation_pct"),
            "vol":      m.get("volume"),            # index.html lit t.vol, pas t.volume
            "pe":       f.get("pe_ratio_ttm"),
            "pb":       f.get("pb_ratio"),
            "div":      f.get("dividend_yield"),
            "cap":      f.get("market_cap_mdh"),
            "h90":      t.get("high_90d"),
            "l90":      t.get("low_90d"),
            "rsi":      rsi,
            "ma20":     t.get("ma20"),
            "ma50":     t.get("ma50"),
            # Note par famille, jointe (comparaison tant que NOTE_METIER_PUBLIEE est faux).
            "note_fond_metier": (detail_publie(notes.get(sym)) if notes else {"indisponible": True}),
            "stale":    d["flags"]["stale"],
            "partial":  d["flags"]["partial_data"],
        })

    # ⚠️ 06/11/2026 : le tri par `v53` décroissant part avec la note. Ce format
    # ne porte pas le Score BVC (calculé par update_data.py sur les chandelles) :
    # tri par symbole, stable d'un run à l'autre.
    tickers.sort(key=lambda x: x.get("symbol") or "")
    return {
        "updated": pipeline_out["timestamp"],
        "version": "v9.0",
        "source":  "BVC Pipeline v9.0",
        "tickers": tickers,
    }


# ── Main ──────────────────────────────────────────────────────────────────────

def run(tickers=None, dry_run=False, max_workers=3):
    setup_logging()
    log = logging.getLogger("pipeline")
    log.info("=" * 60)
    log.info(f"BVC DATA PIPELINE v9.0 — {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    log.info("=" * 60)

    publie   = charger_publie()
    selected = tickers or TICKERS

    output = {
        "timestamp":   datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "version":     "v9.0_unified",
        "sources_used": {},
        "data":        {},
    }

    t0 = time.time()
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {pool.submit(collect_ticker, sym, publie, dry_run): sym for sym in selected}
        for fut in as_completed(futures):
            sym = futures[fut]
            try:
                s, data = fut.result(timeout=120)
                output["data"][s]          = data
                output["sources_used"][s]  = data.pop("_sources", {})
                log.info(f"[{s}] ✓")
            except Exception as e:
                log.error(f"[{sym}] FATAL: {e}")

    elapsed = round(time.time() - t0, 1)
    nb_ok   = len(output["data"])
    nb_stale= sum(1 for d in output["data"].values() if d["flags"].get("stale"))
    log.info(f"Pipeline terminé: {nb_ok}/{len(selected)} tickers, {nb_stale} stale, {elapsed}s")

    # Écriture financial_data.json (format v9)
    OUT_V9.write_text(json.dumps(output, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    log.info(f"→ {OUT_V9}")

    # Écriture data.json (format legacy index.html)
    legacy = to_legacy_format(output)
    # ── Garde : ne jamais appauvrir data.json ────────────────────────────────
    # Ce pipeline ne couvre que TICKERS_ACTIFS (19 valeurs) et n'émet ni
    # code_bvc ni _meta. update_data.py, lui, publie les 81 titres avec les
    # deux. Les deux écrivent le même fichier : le 11/08 à 15h29, celui-ci a
    # écrasé la version complète de 15h14. Conséquence en production —
    # 62 titres disparus du terminal, Sonasid réaffiché sous notre code
    # interne, et « Données insuffisantes » partout, puisque l'absence de
    # _meta vaut confiance nulle côté frontend.
    #
    # On refuse donc d'écrire une version qui perdrait des titres ou des
    # champs. R1 : jamais de régression sur les données.
    _neufs = legacy.get("tickers") or []
    _refus = None
    if OUT_LEGACY.exists():
        try:
            _av = (json.loads(OUT_LEGACY.read_text(encoding="utf-8")).get("tickers") or [])
            if len(_av) > len(_neufs):
                _refus = f"{len(_av)} titres déjà publiés contre {len(_neufs)} ici"
            elif _av and _neufs:
                _perdus = {c for c in ("code_bvc", "_meta") if c in _av[0]} - set(_neufs[0])
                if _perdus:
                    _refus = f"champs perdus : {', '.join(sorted(_perdus))}"
        except Exception as _e:
            log.warning(f"data.json existant illisible ({_e}) — écriture autorisée")

    if _refus:
        log.warning(f"⚠️  data.json NON réécrit — {_refus}. "
                    f"financial_data.json reste à jour ; c'est update_data.py "
                    f"qui publie data.json.")
    else:
        OUT_LEGACY.write_text(json.dumps(legacy, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
        log.info(f"→ {OUT_LEGACY}")

    return output


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="BVC Financial Data Pipeline v9.0")
    parser.add_argument("--dry-run",  action="store_true", help="Sans réseau : valeurs publiées de data.json uniquement")
    parser.add_argument("--tickers",  type=str,  help="Tickers séparés par virgule, ex: MNG,SMI")
    parser.add_argument("--workers",  type=int,  default=3, help="Nb threads parallèles (défaut: 3)")
    args = parser.parse_args()

    tickers = [t.strip().upper() for t in args.tickers.split(",")] if args.tickers else None
    run(tickers=tickers, dry_run=args.dry_run, max_workers=args.workers)
